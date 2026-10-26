"""
app.py - StockWise: Inventory Reorder & Stock Alert System.

Start it with:   python app.py
Then open:       http://127.0.0.1:5000

Layout of this file:
  1. create_app()      - sets up Flask, the database and security
  2. Dashboard         - /
  3. Products          - /products ...
  4. Suppliers         - /suppliers ...
  5. Stock in / out    - /stock-in, /stock-out
  6. Transactions      - /transactions
  7. Reports + CSV     - /reports
"""
import csv
import io
import os
import secrets
from datetime import date

from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, session, url_for)

import services
from db import BASE_DIR, close_db, get_db, init_db
from validation import (STOCK_OUT_REASONS, validate_movement, validate_product,
                        validate_supplier)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        DATABASE=os.environ.get("STOCKWISE_DB", os.path.join(BASE_DIR, "instance", "stockwise.db")),
        CSRF_ENABLED=True,
        CURRENCY=os.environ.get("STOCKWISE_CURRENCY", "$"),
    )
    if test_config:
        app.config.update(test_config)

    init_db(app.config["DATABASE"])  # creates tables only if they are missing
    app.teardown_appcontext(close_db)

    # ---------------------------------------------------------------- security
    # CSRF protection: every form carries a secret token. A malicious website
    # cannot guess it, so it cannot submit forms on the user's behalf.
    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    @app.before_request
    def check_csrf():
        if app.config["CSRF_ENABLED"] and request.method == "POST":
            sent = request.form.get("csrf_token", "")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400, "Your session expired or the form was invalid. Please go back and try again.")

    @app.context_processor
    def inject_globals():
        db = get_db()
        low = db.execute(
            "SELECT COUNT(*) FROM products WHERE is_active = 1 AND quantity <= reorder_level"
        ).fetchone()[0]
        return {
            "csrf_token": csrf_token,
            "currency": app.config["CURRENCY"],
            "low_stock_count": low,
            "today": date.today().isoformat(),
            "active_page": request.endpoint or "",
        }

    @app.template_filter("money")
    def money(value):
        return f"{app.config['CURRENCY']}{(value or 0):,.2f}"

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", title="Request problem", message=error.description), 400

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", title="Page not found",
                               message="The page or record you asked for does not exist."), 404

    # ------------------------------------------------------------- helpers
    def suppliers_list():
        return get_db().execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()

    def categories_list():
        rows = get_db().execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
        return [r["category"] for r in rows]

    def get_product_or_404(product_id):
        row = get_db().execute(
            """SELECT p.*, s.name AS supplier_name FROM products p
               LEFT JOIN suppliers s ON s.id = p.supplier_id WHERE p.id = ?""", (product_id,)
        ).fetchone()
        if row is None:
            abort(404)
        return row

    def get_supplier_or_404(supplier_id):
        row = get_db().execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if row is None:
            abort(404)
        return row

    # =========================================================== 2. DASHBOARD
    @app.route("/")
    def dashboard():
        data = services.dashboard_numbers(get_db())
        return render_template("dashboard.html", **data)

    # ============================================================ 3. PRODUCTS
    @app.route("/products")
    def products():
        q = request.args.get("q", "").strip()
        category = request.args.get("category", "")
        supplier = request.args.get("supplier", "")
        status = request.args.get("status", "")
        show_archived = request.args.get("archived") == "1"

        sql = ["""SELECT p.*, s.name AS supplier_name FROM products p
                  LEFT JOIN suppliers s ON s.id = p.supplier_id WHERE 1 = 1"""]
        params = []
        if not show_archived:
            sql.append("AND p.is_active = 1")
        if q:
            sql.append("AND (p.name LIKE ? OR p.sku LIKE ? OR p.category LIKE ?)")
            params += [f"%{q}%"] * 3
        if category:
            sql.append("AND p.category = ?")
            params.append(category)
        if supplier.isdigit():
            sql.append("AND p.supplier_id = ?")
            params.append(int(supplier))
        if status == "low":
            sql.append("AND p.quantity <= p.reorder_level AND p.quantity > 0")
        elif status == "out":
            sql.append("AND p.quantity = 0")
        elif status == "ok":
            sql.append("AND p.quantity > p.reorder_level")
        sql.append("ORDER BY p.name COLLATE NOCASE")

        rows = get_db().execute(" ".join(sql), params).fetchall()
        return render_template(
            "products.html", products=rows, categories=categories_list(), suppliers=suppliers_list(),
            filters={"q": q, "category": category, "supplier": supplier, "status": status,
                     "archived": show_archived},
        )

    def render_product_form(product, values, errors, editing):
        return render_template(
            "product_form.html", product=product, v=values, errors=errors, editing=editing,
            suppliers=suppliers_list(), categories=categories_list(),
        )

    @app.route("/products/new", methods=["GET", "POST"])
    def product_new():
        if request.method == "POST":
            clean, errors = validate_product(request.form)
            if not errors:
                try:
                    services.create_product(get_db(), clean, date.today().isoformat())
                    flash(f"Product “{clean['name']}” was added.", "success")
                    return redirect(url_for("products"))
                except services.StockError as e:
                    errors[e.field or "form"] = e.message
            flash("Please fix the highlighted problems.", "error")
            return render_product_form(None, request.form, errors, False), 400
        return render_product_form(None, {"reorder_level": 5, "quantity": 0, "unit_price": ""}, {}, False)

    @app.route("/products/<int:product_id>")
    def product_detail(product_id):
        product = get_product_or_404(product_id)
        history = get_db().execute(
            "SELECT * FROM stock_transactions WHERE product_id = ? ORDER BY id DESC", (product_id,)
        ).fetchall()
        return render_template("product_detail.html", product=product, history=history,
                               suggested=services.suggested_reorder(product["quantity"], product["target_level"]))

    @app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
    def product_edit(product_id):
        product = get_product_or_404(product_id)
        if request.method == "POST":
            clean, errors = validate_product(request.form, editing=True)
            if not errors:
                try:
                    services.update_product(get_db(), product_id, clean)
                    flash(f"Product “{clean['name']}” was updated.", "success")
                    return redirect(url_for("products"))
                except services.StockError as e:
                    errors[e.field or "form"] = e.message
            flash("Please fix the highlighted problems.", "error")
            return render_product_form(product, request.form, errors, True), 400
        return render_product_form(product, dict(product), {}, True)

    @app.route("/products/<int:product_id>/delete", methods=["POST"])
    def product_delete(product_id):
        product = get_product_or_404(product_id)
        try:
            services.delete_product(get_db(), product_id)
            flash(f"Product “{product['name']}” was deleted.", "success")
        except services.StockError as e:
            flash(e.message, "error")
        return redirect(url_for("products"))

    @app.route("/products/<int:product_id>/archive", methods=["POST"])
    def product_archive(product_id):
        product = get_product_or_404(product_id)
        archive = request.form.get("action") != "restore"
        services.set_archived(get_db(), product_id, archive)
        flash(f"“{product['name']}” was {'archived' if archive else 'restored'}.", "success")
        return redirect(request.form.get("next") or url_for("products"))

    # =========================================================== 4. SUPPLIERS
    @app.route("/suppliers")
    def suppliers():
        rows = get_db().execute(
            """SELECT s.*, COUNT(p.id) AS product_count FROM suppliers s
               LEFT JOIN products p ON p.supplier_id = s.id AND p.is_active = 1
               GROUP BY s.id ORDER BY s.name COLLATE NOCASE"""
        ).fetchall()
        return render_template("suppliers.html", suppliers=rows)

    @app.route("/suppliers/new", methods=["GET", "POST"])
    def supplier_new():
        if request.method == "POST":
            clean, errors = validate_supplier(request.form)
            if not errors:
                try:
                    new_id = services.create_supplier(get_db(), clean)
                    flash(f"Supplier “{clean['name']}” was added.", "success")
                    return redirect(url_for("supplier_detail", supplier_id=new_id))
                except services.StockError as e:
                    errors[e.field or "form"] = e.message
            flash("Please fix the highlighted problems.", "error")
            return render_template("supplier_form.html", v=request.form, errors=errors, editing=False), 400
        return render_template("supplier_form.html", v={}, errors={}, editing=False)

    @app.route("/suppliers/<int:supplier_id>")
    def supplier_detail(supplier_id):
        supplier = get_supplier_or_404(supplier_id)
        items = get_db().execute(
            "SELECT * FROM products WHERE supplier_id = ? ORDER BY is_active DESC, name COLLATE NOCASE",
            (supplier_id,),
        ).fetchall()
        return render_template("supplier_detail.html", supplier=supplier, products=items)

    @app.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
    def supplier_edit(supplier_id):
        supplier = get_supplier_or_404(supplier_id)
        if request.method == "POST":
            clean, errors = validate_supplier(request.form)
            if not errors:
                try:
                    services.update_supplier(get_db(), supplier_id, clean)
                    flash(f"Supplier “{clean['name']}” was updated.", "success")
                    return redirect(url_for("supplier_detail", supplier_id=supplier_id))
                except services.StockError as e:
                    errors[e.field or "form"] = e.message
            flash("Please fix the highlighted problems.", "error")
            return render_template("supplier_form.html", v=request.form, errors=errors, editing=True,
                                   supplier=supplier), 400
        return render_template("supplier_form.html", v=dict(supplier), errors={}, editing=True, supplier=supplier)

    # ====================================================== 5. STOCK IN / OUT
    def movement_page(kind):
        title = "Stock In" if kind == "IN" else "Stock Out"
        db = get_db()
        products_rows = db.execute(
            "SELECT id, name, sku, quantity FROM products WHERE is_active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()

        def render(values, errors, status=200):
            return render_template("movement.html", kind=kind, products=products_rows, v=values,
                                   errors=errors, title=title, reasons=STOCK_OUT_REASONS), status

        if request.method == "POST":
            clean, errors = validate_movement(request.form, kind)
            if not errors:
                try:
                    services.record_movement(db, clean, kind)
                    product = db.execute("SELECT name, quantity, reorder_level FROM products WHERE id = ?",
                                         (clean["product_id"],)).fetchone()
                    verb = "received" if kind == "IN" else "removed"
                    flash(f"{clean['quantity']} unit(s) {verb}. {product['name']} now has "
                          f"{product['quantity']} in stock.", "success")
                    if product["quantity"] <= product["reorder_level"]:
                        flash(f"Low stock: {product['name']} is at {product['quantity']} "
                              f"(reorder level {product['reorder_level']}).", "warning")
                    return redirect(url_for("stock_in" if kind == "IN" else "stock_out"))
                except services.StockError as e:
                    errors[e.field or "form"] = e.message
            flash("The transaction was not saved. Please fix the problems below.", "error")
            return render(request.form, errors, 400)

        preselect = request.args.get("product_id", "")
        return render({"product_id": preselect, "transaction_date": date.today().isoformat()}, {})

    @app.route("/stock-in", methods=["GET", "POST"])
    def stock_in():
        return movement_page("IN")

    @app.route("/stock-out", methods=["GET", "POST"])
    def stock_out():
        return movement_page("OUT")

    # ====================================================== 6. TRANSACTIONS
    @app.route("/transactions")
    def transactions():
        q = request.args.get("q", "").strip()
        kind = request.args.get("type", "")
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        rows = query_movements(get_db(), kind=kind, date_from=date_from, date_to=date_to, q=q, limit=300)
        return render_template("transactions.html", rows=rows,
                               filters={"q": q, "type": kind, "date_from": date_from, "date_to": date_to})

    # ======================================================= 7. REPORTS + CSV
    def query_movements(db, kind="", date_from="", date_to="", category="", q="", limit=None):
        sql = ["""SELECT t.*, p.name AS product_name, p.sku, p.category FROM stock_transactions t
                  JOIN products p ON p.id = t.product_id WHERE 1 = 1"""]
        params = []
        if kind in ("IN", "OUT"):
            sql.append("AND t.type = ?")
            params.append(kind)
        if valid_date(date_from):
            sql.append("AND t.transaction_date >= ?")
            params.append(date_from)
        if valid_date(date_to):
            sql.append("AND t.transaction_date <= ?")
            params.append(date_to)
        if category:
            sql.append("AND p.category = ?")
            params.append(category)
        if q:
            sql.append("AND (p.name LIKE ? OR p.sku LIKE ? OR t.reference LIKE ? OR t.notes LIKE ?)")
            params += [f"%{q}%"] * 4
        sql.append("ORDER BY t.id DESC")
        if limit:
            sql.append("LIMIT ?")
            params.append(limit)
        return db.execute(" ".join(sql), params).fetchall()

    def valid_date(text):
        try:
            date.fromisoformat(text)
            return True
        except (TypeError, ValueError):
            return False

    def report_data(args):
        db = get_db()
        category = args.get("category", "")
        kind = args.get("type", "")
        date_from = args.get("date_from", "")
        date_to = args.get("date_to", "")

        where, params = "WHERE p.is_active = 1", []
        if category:
            where += " AND p.category = ?"
            params.append(category)
        stock = db.execute(
            f"""SELECT p.*, s.name AS supplier_name, p.quantity * p.unit_price AS stock_value
                  FROM products p LEFT JOIN suppliers s ON s.id = p.supplier_id {where}
                 ORDER BY p.name COLLATE NOCASE""", params).fetchall()
        low = [p for p in services.low_stock_products(db) if not category or p["category"] == category]
        by_category = db.execute(
            f"""SELECT p.category, COUNT(*) AS products, SUM(p.quantity) AS units,
                       SUM(p.quantity * p.unit_price) AS value
                  FROM products p {where} GROUP BY p.category ORDER BY value DESC""", params).fetchall()
        movements = query_movements(db, kind=kind, date_from=date_from, date_to=date_to, category=category)
        return {
            "stock": stock, "low": low, "by_category": by_category, "movements": movements,
            "total_value": round(sum(r["stock_value"] for r in stock), 2),
            "total_units": sum(r["quantity"] for r in stock),
            "filters": {"category": category, "type": kind, "date_from": date_from, "date_to": date_to},
        }

    @app.route("/reports")
    def reports():
        data = report_data(request.args)
        return render_template("reports.html", categories=categories_list(), **data)

    def csv_safe(value):
        """Stop spreadsheet formula injection: a cell starting with = + - @ is treated as text."""
        if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
            return "'" + value
        return value

    @app.route("/reports/export/<kind>.csv")
    def export_csv(kind):
        data = report_data(request.args)
        out = io.StringIO()
        writer = csv.writer(out)
        if kind == "stock":
            writer.writerow(["SKU", "Product", "Category", "Supplier", "Quantity", "Unit price",
                             "Stock value", "Reorder level", "Target level", "Needs reorder"])
            for r in data["stock"]:
                writer.writerow([csv_safe(x) for x in [
                    r["sku"], r["name"], r["category"], r["supplier_name"] or "", r["quantity"],
                    f"{r['unit_price']:.2f}", f"{r['stock_value']:.2f}", r["reorder_level"],
                    r["target_level"], "Yes" if r["quantity"] <= r["reorder_level"] else "No"]])
        elif kind == "low-stock":
            writer.writerow(["SKU", "Product", "Category", "Supplier", "Current quantity",
                             "Reorder level", "Target level", "Suggested order quantity"])
            for r in data["low"]:
                writer.writerow([csv_safe(x) for x in [
                    r["sku"], r["name"], r["category"], r["supplier_name"] or "", r["quantity"],
                    r["reorder_level"], r["target_level"], r["suggested_order"]]])
        elif kind == "movements":
            writer.writerow(["Transaction ID", "Date", "SKU", "Product", "Category", "Type", "Quantity",
                             "Previous quantity", "New quantity", "Reference", "Reason", "Notes"])
            for r in data["movements"]:
                writer.writerow([csv_safe(x) for x in [
                    r["id"], r["transaction_date"], r["sku"], r["product_name"], r["category"],
                    "Stock in" if r["type"] == "IN" else "Stock out", r["quantity"], r["previous_qty"],
                    r["new_qty"], r["reference"], r["reason"], r["notes"]]])
        else:
            abort(404)
        filename = f"stockwise-{kind}-{date.today().isoformat()}.csv"
        return Response("﻿" + out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={filename}"})

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)

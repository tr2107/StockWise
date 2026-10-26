"""
services.py - the business rules. All database changes happen here.

The most important idea: changing a product's quantity and writing the history
row are ONE database transaction. Either both are saved, or neither is.
"""
import sqlite3


class StockError(Exception):
    """A business-rule problem that should be shown to the user (not a crash)."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


def _integrity_to_error(error):
    """Turn a database constraint failure into a friendly message."""
    text = str(error)
    if "products.sku" in text:
        return StockError("A product with this SKU already exists.", "sku")
    return StockError("The database rejected these values: " + text)


# --------------------------------------------------------------------------
# Suppliers
# --------------------------------------------------------------------------
def create_supplier(db, data):
    try:
        cur = db.execute(
            "INSERT INTO suppliers (name, contact_person, phone, email, address) VALUES (?, ?, ?, ?, ?)",
            (data["name"], data["contact_person"], data["phone"], data["email"], data["address"]),
        )
    except sqlite3.IntegrityError:
        raise StockError("A supplier with this name already exists.", "name")
    return cur.lastrowid


def update_supplier(db, supplier_id, data):
    try:
        db.execute(
            "UPDATE suppliers SET name = ?, contact_person = ?, phone = ?, email = ?, address = ? WHERE id = ?",
            (data["name"], data["contact_person"], data["phone"], data["email"], data["address"], supplier_id),
        )
    except sqlite3.IntegrityError:
        raise StockError("A supplier with this name already exists.", "name")


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
def _check_supplier_exists(db, supplier_id):
    if supplier_id is not None:
        found = db.execute("SELECT 1 FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        if not found:
            raise StockError("Please choose a valid supplier.", "supplier_id")


def create_product(db, data, transaction_date):
    """
    Add a product. If it starts with some stock, an 'opening stock' IN transaction
    is recorded too, so the history always adds up to the current quantity.
    """
    _check_supplier_exists(db, data["supplier_id"])
    db.execute("BEGIN IMMEDIATE")
    try:
        cur = db.execute(
            """INSERT INTO products (name, sku, category, quantity, unit_price, reorder_level, target_level, supplier_id)
               VALUES (?, ?, ?, 0, ?, ?, ?, ?)""",
            (data["name"], data["sku"], data["category"], data["unit_price"],
             data["reorder_level"], data["target_level"], data["supplier_id"]),
        )
        product_id = cur.lastrowid
        if data["quantity"] > 0:
            _apply_movement(db, product_id, "IN", data["quantity"], transaction_date,
                            reference="OPENING", reason="", notes="Opening stock when product was added")
        db.execute("COMMIT")
    except sqlite3.IntegrityError as error:
        db.execute("ROLLBACK")
        raise _integrity_to_error(error)
    except Exception:
        db.execute("ROLLBACK")
        raise
    return product_id


def update_product(db, product_id, data):
    """Edit details. Quantity is deliberately NOT editable here (see validation.py)."""
    _check_supplier_exists(db, data["supplier_id"])
    try:
        db.execute(
            """UPDATE products SET name = ?, sku = ?, category = ?, unit_price = ?,
                      reorder_level = ?, target_level = ?, supplier_id = ? WHERE id = ?""",
            (data["name"], data["sku"], data["category"], data["unit_price"],
             data["reorder_level"], data["target_level"], data["supplier_id"], product_id),
        )
    except sqlite3.IntegrityError as error:
        raise _integrity_to_error(error)


def count_transactions(db, product_id):
    return db.execute(
        "SELECT COUNT(*) FROM stock_transactions WHERE product_id = ?", (product_id,)
    ).fetchone()[0]


def delete_product(db, product_id):
    """
    Delete only products with NO history. Otherwise refuse and suggest archiving.
    (The database also enforces this with ON DELETE RESTRICT.)
    """
    if count_transactions(db, product_id) > 0:
        raise StockError(
            "This product has stock history, so it cannot be deleted. Archive it instead to hide it "
            "while keeping its transaction records."
        )
    try:
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    except sqlite3.IntegrityError:
        raise StockError("This product is still referenced by other records and cannot be deleted.")


def set_archived(db, product_id, archived):
    db.execute("UPDATE products SET is_active = ? WHERE id = ?", (0 if archived else 1, product_id))


# --------------------------------------------------------------------------
# Stock movements
# --------------------------------------------------------------------------
def _apply_movement(db, product_id, kind, quantity, transaction_date, reference, reason, notes):
    """
    Update the quantity and record the movement. Must be called inside an open
    transaction (BEGIN ... COMMIT) so both steps succeed or fail together.
    """
    row = db.execute("SELECT name, quantity FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        raise StockError("Product not found.", "product_id")
    previous = row["quantity"]
    new = previous + quantity if kind == "IN" else previous - quantity
    if new < 0:
        raise StockError(
            f"Not enough stock for {row['name']}: you have {previous} but tried to remove {quantity}.",
            "quantity",
        )
    db.execute("UPDATE products SET quantity = ? WHERE id = ?", (new, product_id))
    cur = db.execute(
        """INSERT INTO stock_transactions
               (product_id, type, quantity, previous_qty, new_qty, transaction_date, reference, reason, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (product_id, kind, quantity, previous, new, transaction_date, reference, reason, notes),
    )
    return cur.lastrowid


def record_movement(db, data, kind):
    """Record a stock-in ('IN') or stock-out ('OUT') as one atomic database transaction."""
    product = db.execute("SELECT is_active FROM products WHERE id = ?", (data["product_id"],)).fetchone()
    if product is None:
        raise StockError("Product not found.", "product_id")
    if not product["is_active"]:
        raise StockError("This product is archived. Restore it before recording stock changes.", "product_id")

    # BEGIN IMMEDIATE locks the database for writing straight away, so two people
    # cannot both read "10 in stock" and both remove 8.
    db.execute("BEGIN IMMEDIATE")
    try:
        transaction_id = _apply_movement(
            db, data["product_id"], kind, data["quantity"], data["transaction_date"],
            data["reference"], data["reason"], data["notes"],
        )
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")  # nothing is saved if anything went wrong
        raise
    return transaction_id


# --------------------------------------------------------------------------
# Low stock + dashboard numbers
# --------------------------------------------------------------------------
def suggested_reorder(quantity, target_level):
    """How many units to order to get back up to the target level."""
    return max(target_level - quantity, 0)


def low_stock_products(db):
    """Active products where quantity <= reorder level, most urgent (emptiest) first."""
    rows = db.execute(
        """SELECT p.*, s.name AS supplier_name
             FROM products p LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.is_active = 1 AND p.quantity <= p.reorder_level
            ORDER BY p.quantity * 1.0 / MAX(p.reorder_level, 1), p.name"""
    ).fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["suggested_order"] = suggested_reorder(r["quantity"], r["target_level"])
        item["out_of_stock"] = r["quantity"] == 0
        result.append(item)
    return result


def dashboard_numbers(db):
    totals = db.execute(
        """SELECT COUNT(*)                         AS products,
                  COALESCE(SUM(quantity), 0)       AS units,
                  COALESCE(SUM(quantity * unit_price), 0) AS value,
                  COALESCE(SUM(quantity <= reorder_level), 0) AS reorder
             FROM products WHERE is_active = 1"""
    ).fetchone()
    by_category = db.execute(
        """SELECT category, SUM(quantity) AS units FROM products
            WHERE is_active = 1 GROUP BY category ORDER BY units DESC, category"""
    ).fetchall()
    recent = db.execute(
        """SELECT t.*, p.name AS product_name, p.sku
             FROM stock_transactions t JOIN products p ON p.id = t.product_id
            ORDER BY t.id DESC LIMIT 8"""
    ).fetchall()
    return {
        "total_products": totals["products"],
        "total_units": totals["units"],
        "reorder_count": totals["reorder"],
        "inventory_value": round(totals["value"], 2),
        "categories": [{"category": r["category"], "units": r["units"]} for r in by_category],
        "recent": [dict(r) for r in recent],
        "low_stock": low_stock_products(db),
    }


def history_matches_stock(db):
    """
    Data-integrity check used by the tests (and the /health page):
    for every product, the net of all transactions must equal its quantity,
    and each transaction's 'previous' must equal the one before's 'new'.
    Returns a list of problems (empty list = everything consistent).
    """
    problems = []
    for p in db.execute("SELECT id, name, quantity FROM products").fetchall():
        rows = db.execute(
            "SELECT type, quantity, previous_qty, new_qty FROM stock_transactions WHERE product_id = ? ORDER BY id",
            (p["id"],),
        ).fetchall()
        running = 0
        for t in rows:
            if t["previous_qty"] != running:
                problems.append(f"{p['name']}: a transaction starts at {t['previous_qty']} but expected {running}")
            running = t["new_qty"]
        if running != p["quantity"]:
            problems.append(f"{p['name']}: history ends at {running} but stock is {p['quantity']}")
    return problems

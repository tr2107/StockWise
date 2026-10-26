"""
Automated tests for StockWise.

Run them with:      python -m unittest -v
(or, if you have pytest installed:   pytest -v)

Every test uses its own temporary database file, so your real data is never touched.
Tests named test_01 ... test_10 match the 10 required cases in docs/TEST_CASES.md.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services  # noqa: E402
from app import create_app  # noqa: E402
from db import connect  # noqa: E402

TODAY = date.today().isoformat()


class StockWiseTestCase(unittest.TestCase):
    """Creates a fresh app + empty database before every test."""

    csrf = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test.db")
        self.app = create_app({"DATABASE": self.db_path, "TESTING": True, "CSRF_ENABLED": self.csrf})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    # ---- helpers -------------------------------------------------------
    def db(self):
        """A direct connection to the test database, for checking what was really saved."""
        conn = connect(self.db_path)
        self.addCleanup(conn.close)
        return conn

    def add_product(self, **overrides):
        form = {"name": "Blue Pen", "sku": "PEN-001", "category": "Stationery", "quantity": "20",
                "unit_price": "2.50", "reorder_level": "5", "target_level": "", "supplier_id": ""}
        form.update(overrides)
        return self.client.post("/products/new", data=form, follow_redirects=True)

    def product(self, sku="PEN-001"):
        return self.db().execute("SELECT * FROM products WHERE sku = ?", (sku,)).fetchone()

    def stock_in(self, product_id, quantity, **extra):
        data = {"product_id": str(product_id), "quantity": str(quantity), "transaction_date": TODAY}
        data.update(extra)
        return self.client.post("/stock-in", data=data, follow_redirects=True)

    def stock_out(self, product_id, quantity, reason="Sold", **extra):
        data = {"product_id": str(product_id), "quantity": str(quantity), "transaction_date": TODAY,
                "reason": reason}
        data.update(extra)
        return self.client.post("/stock-out", data=data, follow_redirects=True)

    def count(self, table):
        return self.db().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ===========================================================================
# The 10 required test cases
# ===========================================================================
class RequiredCases(StockWiseTestCase):

    def test_01_add_valid_product(self):
        response = self.add_product()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"was added", response.data)
        row = self.product()
        self.assertEqual(row["name"], "Blue Pen")
        self.assertEqual(row["quantity"], 20)
        self.assertEqual(row["unit_price"], 2.5)
        self.assertEqual(row["reorder_level"], 5)
        self.assertEqual(row["target_level"], 15)  # blank target defaults to 3 x reorder level

    def test_02_reject_duplicate_sku(self):
        self.add_product()
        response = self.add_product(name="Another Pen")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"A product with this SKU already exists", response.data)
        self.assertEqual(self.count("products"), 1)
        # SKUs are compared ignoring upper/lower case
        response = self.add_product(name="Another Pen", sku="pen-001")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count("products"), 1)

    def test_03_reject_negative_quantity(self):
        response = self.add_product(quantity="-5")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Quantity cannot be negative", response.data)
        self.assertEqual(self.count("products"), 0)

    def test_04_record_stock_received(self):
        self.add_product()
        pid = self.product()["id"]
        response = self.stock_in(pid, 10, reference="PO-77", notes="Weekly delivery")
        self.assertIn(b"now has 30 in stock", response.data)
        self.assertEqual(self.product()["quantity"], 30)
        t = self.db().execute("SELECT * FROM stock_transactions WHERE type = 'IN' AND reference = 'PO-77'").fetchone()
        self.assertIsNotNone(t)
        self.assertEqual((t["quantity"], t["previous_qty"], t["new_qty"]), (10, 20, 30))
        self.assertEqual(t["notes"], "Weekly delivery")

    def test_05_record_stock_removed(self):
        self.add_product()
        pid = self.product()["id"]
        response = self.stock_out(pid, 8, reason="Sold", reference="INV-5")
        self.assertIn(b"now has 12 in stock", response.data)
        self.assertEqual(self.product()["quantity"], 12)
        t = self.db().execute("SELECT * FROM stock_transactions WHERE type = 'OUT'").fetchone()
        self.assertEqual((t["quantity"], t["previous_qty"], t["new_qty"], t["reason"]), (8, 20, 12, "Sold"))

    def test_06_reject_stock_out_exceeding_available(self):
        self.add_product()
        pid = self.product()["id"]
        before = self.count("stock_transactions")
        response = self.stock_out(pid, 21)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Not enough stock", response.data)
        self.assertEqual(self.product()["quantity"], 20)               # unchanged
        self.assertEqual(self.count("stock_transactions"), before)     # nothing recorded

    def test_07_alert_when_quantity_reaches_reorder_level(self):
        self.add_product()  # 20 in stock, reorder level 5
        pid = self.product()["id"]
        # 6 left: still above the level, so no alert
        response = self.stock_out(pid, 14)
        self.assertNotIn(b"Low stock:", response.data)
        self.assertEqual(services.low_stock_products(self.db()), [])
        # exactly 5 left: equals the level, so the alert must appear
        response = self.stock_out(pid, 1)
        self.assertIn(b"Low stock: Blue Pen is at 5", response.data)
        low = services.low_stock_products(self.db())
        self.assertEqual(len(low), 1)
        self.assertEqual((low[0]["name"], low[0]["quantity"], low[0]["reorder_level"]), ("Blue Pen", 5, 5))
        self.assertEqual(low[0]["suggested_order"], 10)  # target 15 - current 5
        # the dashboard and product list show it too
        dashboard = self.client.get("/").data
        self.assertIn(b"Low-stock alerts", dashboard)
        self.assertIn(b"Order 10", dashboard)
        self.assertIn(b'badge badge-warn">Reorder', self.client.get("/products").data)  # the badge, not just the column title

    def test_08_dashboard_updates_after_transaction(self):
        self.add_product(quantity="20", unit_price="2.50", reorder_level="5")
        before = services.dashboard_numbers(self.db())
        self.assertEqual((before["total_products"], before["total_units"], before["inventory_value"]),
                         (1, 20, 50.0))
        self.stock_out(self.product()["id"], 15)
        after = services.dashboard_numbers(self.db())
        self.assertEqual((after["total_units"], after["inventory_value"], after["reorder_count"]), (5, 12.5, 1))
        self.assertEqual(after["categories"], [{"category": "Stationery", "units": 5}])
        self.assertEqual(after["recent"][0]["type"], "OUT")
        page = self.client.get("/").data.decode()
        self.assertIn("$12.50", page)
        self.assertIn("Removed 15", page)

    def test_09_records_preserved_after_restart(self):
        self.add_product()
        pid = self.product()["id"]
        self.stock_in(pid, 5)
        self.stock_out(pid, 3)
        # "Restart": build a brand-new application on the same database file.
        restarted = create_app({"DATABASE": self.db_path, "TESTING": True, "CSRF_ENABLED": False})
        client = restarted.test_client()
        self.assertIn(b"Blue Pen", client.get("/products").data)
        self.assertEqual(self.product()["quantity"], 22)
        self.assertEqual(self.count("stock_transactions"), 3)  # opening + in + out
        history_page = client.get("/transactions").data
        self.assertIn(b"OPENING", history_page)  # the opening-stock record survived the restart
        self.assertEqual(services.history_matches_stock(self.db()), [])

    def test_10_history_matches_stock_changes(self):
        self.add_product(quantity="10")
        self.add_product(name="Notebook", sku="NB-1", quantity="0", reorder_level="2")
        pen, nb = self.product()["id"], self.product("NB-1")["id"]
        self.stock_in(pen, 15)
        self.stock_out(pen, 7)
        self.stock_in(nb, 30)
        self.stock_out(nb, 12)
        self.stock_out(pen, 99)  # rejected, must leave no trace
        self.assertEqual(services.history_matches_stock(self.db()), [])
        rows = self.db().execute(
            "SELECT * FROM stock_transactions WHERE product_id = ? ORDER BY id", (pen,)).fetchall()
        self.assertEqual([(r["type"], r["quantity"], r["previous_qty"], r["new_qty"]) for r in rows],
                         [("IN", 10, 0, 10), ("IN", 15, 10, 25), ("OUT", 7, 25, 18)])
        self.assertEqual(self.product()["quantity"], 18)
        self.assertEqual(self.product("NB-1")["quantity"], 18)


# ===========================================================================
# Extra tests: validation, data safety, suppliers, reports
# ===========================================================================
class ProductRules(StockWiseTestCase):

    def test_required_fields_and_bad_numbers(self):
        for bad in [dict(name=""), dict(sku=""), dict(unit_price="abc"), dict(unit_price="-1"),
                    dict(reorder_level="-2"), dict(quantity="1.5"), dict(quantity="abc"),
                    dict(sku="bad sku!"), dict(reorder_level="10", target_level="3")]:
            with self.subTest(bad=bad):
                self.assertEqual(self.add_product(**bad).status_code, 400)
        self.assertEqual(self.count("products"), 0)

    def test_opening_stock_creates_history_row(self):
        self.add_product(quantity="12")
        t = self.db().execute("SELECT * FROM stock_transactions").fetchone()
        self.assertEqual((t["type"], t["quantity"], t["previous_qty"], t["new_qty"], t["reference"]),
                         ("IN", 12, 0, 12, "OPENING"))

    def test_zero_opening_stock_has_no_history_row(self):
        self.add_product(quantity="0")
        self.assertEqual(self.count("stock_transactions"), 0)

    def test_edit_product_changes_details_but_not_quantity(self):
        self.add_product()
        pid = self.product()["id"]
        response = self.client.post(f"/products/{pid}/edit", follow_redirects=True, data={
            "name": "Black Pen", "sku": "pen-002", "category": "Office", "unit_price": "3.10",
            "reorder_level": "8", "target_level": "40", "supplier_id": "",
            "quantity": "9999",  # must be ignored
        })
        self.assertIn(b"was updated", response.data)
        row = self.product("PEN-002")
        self.assertEqual((row["name"], row["category"], row["unit_price"], row["reorder_level"], row["target_level"]),
                         ("Black Pen", "Office", 3.1, 8, 40))
        self.assertEqual(row["quantity"], 20)
        self.assertEqual(self.count("stock_transactions"), 1)

    def test_edit_cannot_steal_another_products_sku(self):
        self.add_product()
        self.add_product(name="Pencil", sku="PEN-002")
        pid = self.product("PEN-002")["id"]
        response = self.client.post(f"/products/{pid}/edit", data={
            "name": "Pencil", "sku": "PEN-001", "category": "Stationery", "unit_price": "1",
            "reorder_level": "1", "target_level": "", "supplier_id": ""})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"already exists", response.data)

    def test_search_and_filters(self):
        self.add_product()
        self.add_product(name="Stapler", sku="STP-1", category="Office", quantity="2", reorder_level="5")
        self.assertIn(b"Stapler", self.client.get("/products?q=stap").data)
        self.assertNotIn(b"Blue Pen", self.client.get("/products?q=stap").data)
        self.assertNotIn(b"Blue Pen", self.client.get("/products?category=Office").data)
        low = self.client.get("/products?status=low").data
        self.assertIn(b"Stapler", low)
        self.assertNotIn(b"Blue Pen", low)
        self.assertIn(b"No products match your filters", self.client.get("/products?q=zzz").data)

    def test_search_is_safe_against_sql_injection(self):
        self.add_product()
        response = self.client.get("/products?q=' OR 1=1; DROP TABLE products; --")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.count("products"), 1)


class DeleteAndArchive(StockWiseTestCase):

    def test_product_with_history_cannot_be_deleted(self):
        self.add_product()  # has an opening-stock transaction
        pid = self.product()["id"]
        response = self.client.post(f"/products/{pid}/delete", follow_redirects=True)
        self.assertIn(b"cannot be deleted", response.data)
        self.assertIsNotNone(self.product())
        self.assertEqual(self.count("stock_transactions"), 1)

    def test_database_itself_blocks_deleting_history(self):
        self.add_product()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db().execute("DELETE FROM products")

    def test_product_without_history_can_be_deleted(self):
        self.add_product(quantity="0")
        pid = self.product()["id"]
        response = self.client.post(f"/products/{pid}/delete", follow_redirects=True)
        self.assertIn(b"was deleted", response.data)
        self.assertIsNone(self.product())

    def test_archive_hides_product_but_keeps_history(self):
        self.add_product()
        pid = self.product()["id"]
        self.client.post(f"/products/{pid}/archive", data={"action": "archive"})
        # (the success banner mentions the name, so look for the SKU, which only appears in the table)
        self.assertNotIn(b"PEN-001", self.client.get("/products").data)
        self.assertIn(b"PEN-001", self.client.get("/products?archived=1").data)
        self.assertEqual(services.dashboard_numbers(self.db())["total_products"], 0)
        self.assertIn(b"Blue Pen", self.client.get("/transactions").data)  # history still there
        # archived products cannot receive stock
        self.assertEqual(self.stock_in(pid, 5).status_code, 400)
        self.client.post(f"/products/{pid}/archive", data={"action": "restore"})
        self.assertIn(b"now has 25", self.stock_in(pid, 5).data)


class MovementRules(StockWiseTestCase):

    def test_invalid_movement_forms_are_rejected(self):
        self.add_product()
        pid = self.product()["id"]
        future = (date.today() + timedelta(days=3)).isoformat()
        cases = [
            dict(quantity="0"), dict(quantity="-3"), dict(quantity="abc"), dict(quantity=""),
            dict(transaction_date=future), dict(transaction_date="31/12/2026"), dict(transaction_date=""),
            dict(product_id=""), dict(product_id="9999"),
        ]
        for bad in cases:
            with self.subTest(bad=bad):
                self.assertEqual(self.stock_in(**{"product_id": pid, "quantity": 1, **bad}).status_code, 400)
        self.assertEqual(self.product()["quantity"], 20)
        self.assertEqual(self.count("stock_transactions"), 1)

    def test_stock_out_requires_valid_reason(self):
        self.add_product()
        pid = self.product()["id"]
        self.assertEqual(self.stock_out(pid, 1, reason="").status_code, 400)
        self.assertEqual(self.stock_out(pid, 1, reason="Because").status_code, 400)
        self.assertEqual(self.product()["quantity"], 20)

    def test_can_remove_exactly_all_stock(self):
        self.add_product()
        self.stock_out(self.product()["id"], 20)
        self.assertEqual(self.product()["quantity"], 0)
        self.assertIn(b"Out of stock", self.client.get("/products").data)

    def test_failed_save_rolls_back_quantity_and_history_together(self):
        """Atomicity: if writing the history row fails, the quantity change is undone too."""
        self.add_product()
        pid = self.product()["id"]
        conn = self.db()
        conn.execute("""CREATE TRIGGER boom BEFORE INSERT ON stock_transactions
                        WHEN NEW.notes = 'boom' BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
        data = dict(product_id=pid, quantity=5, transaction_date=TODAY, reference="", reason="Sold", notes="boom")
        with self.assertRaises(sqlite3.IntegrityError):
            services.record_movement(conn, data, "OUT")
        self.assertEqual(self.product()["quantity"], 20)
        self.assertEqual(self.count("stock_transactions"), 1)

    def test_database_rejects_inconsistent_history_and_negative_stock(self):
        self.add_product()
        conn = self.db()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE products SET quantity = -1")
        with self.assertRaises(sqlite3.IntegrityError):  # 20 + 5 is not 99
            conn.execute("""INSERT INTO stock_transactions (product_id, type, quantity, previous_qty, new_qty,
                            transaction_date) VALUES (1, 'IN', 5, 20, 99, '2026-01-01')""")


class Suppliers(StockWiseTestCase):

    def add_supplier(self, **overrides):
        form = {"name": "Acme Ltd", "contact_person": "Jo Smith", "phone": "+1 555 0100",
                "email": "jo@acme.example", "address": "1 High Street"}
        form.update(overrides)
        return self.client.post("/suppliers/new", data=form, follow_redirects=True)

    def test_add_edit_and_view_supplier_with_products(self):
        self.assertIn(b"was added", self.add_supplier().data)
        sid = self.db().execute("SELECT id FROM suppliers").fetchone()["id"]
        self.add_product(supplier_id=str(sid))
        self.add_product(name="Ruler", sku="RUL-1", supplier_id=str(sid))
        page = self.client.get(f"/suppliers/{sid}").data
        self.assertIn(b"Blue Pen", page)
        self.assertIn(b"Ruler", page)
        response = self.client.post(f"/suppliers/{sid}/edit", follow_redirects=True, data={
            "name": "Acme Ltd", "contact_person": "Pat Lee", "phone": "", "email": "", "address": ""})
        self.assertIn(b"was updated", response.data)
        self.assertEqual(self.db().execute("SELECT contact_person FROM suppliers").fetchone()[0], "Pat Lee")

    def test_supplier_validation(self):
        self.assertEqual(self.add_supplier(name="").status_code, 400)
        self.assertEqual(self.add_supplier(email="not-an-email").status_code, 400)
        self.assertEqual(self.add_supplier(phone="call me").status_code, 400)
        self.add_supplier()
        self.assertEqual(self.add_supplier(name="acme ltd").status_code, 400)  # duplicate ignoring case
        self.assertEqual(self.count("suppliers"), 1)

    def test_product_rejects_unknown_supplier(self):
        self.assertEqual(self.add_product(supplier_id="999").status_code, 400)
        self.assertEqual(self.count("products"), 0)


class ReportsAndCsv(StockWiseTestCase):

    def setUp(self):
        super().setUp()
        self.add_product(quantity="20", unit_price="2.50", reorder_level="5")
        self.add_product(name="Stapler", sku="STP-1", category="Office", quantity="4", unit_price="10",
                         reorder_level="6")
        self.pen = self.product()["id"]
        self.stock_out(self.pen, 3)

    def test_report_page_totals(self):
        page = self.client.get("/reports").data.decode()
        self.assertIn("$82.50", page)      # 17 x 2.50 + 4 x 10
        self.assertIn("Stapler", page)

    def test_stock_csv(self):
        response = self.client.get("/reports/export/stock.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        text = response.data.decode("utf-8-sig")
        self.assertIn("SKU,Product,Category,Supplier,Quantity,Unit price,Stock value", text)
        self.assertIn("PEN-001,Blue Pen,Stationery,,17,2.50,42.50", text)
        self.assertIn("STP-1,Stapler,Office,,4,10.00,40.00,6,18,Yes", text)

    def test_low_stock_csv_and_category_filter(self):
        text = self.client.get("/reports/export/low-stock.csv").data.decode("utf-8-sig")
        self.assertIn("Stapler", text)
        self.assertIn(",14", text)  # suggested order: target 18 - 4
        self.assertNotIn("Blue Pen", text)
        filtered = self.client.get("/reports/export/stock.csv?category=Office").data.decode("utf-8-sig")
        self.assertIn("Stapler", filtered)
        self.assertNotIn("Blue Pen", filtered)

    def test_movement_filters(self):
        text = self.client.get("/reports/export/movements.csv?type=OUT").data.decode("utf-8-sig")
        self.assertIn("Stock out", text)
        self.assertNotIn("Stock in", text)
        none = self.client.get("/reports/export/movements.csv?date_from=2999-01-01").data.decode("utf-8-sig")
        self.assertEqual(len(none.strip().splitlines()), 1)  # header only
        page = self.client.get("/transactions?type=IN").data
        self.assertNotIn(b"badge-out", page)

    def test_csv_blocks_spreadsheet_formula_injection(self):
        self.add_product(name="=HYPERLINK(\"http://evil\")", sku="EVIL-1")
        text = self.client.get("/reports/export/stock.csv").data.decode("utf-8-sig")
        self.assertIn("\"'=HYPERLINK", text)

    def test_unknown_export_is_404(self):
        self.assertEqual(self.client.get("/reports/export/secrets.csv").status_code, 404)


class PagesAndSecurity(StockWiseTestCase):

    def test_every_page_loads_with_and_without_data(self):
        urls = ["/", "/products", "/products/new", "/suppliers", "/suppliers/new", "/stock-in", "/stock-out",
                "/transactions", "/reports"]
        for url in urls:  # empty database -> empty states
            with self.subTest(url=url, data=False):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertIn(b"Add your first product", self.client.get("/").data)
        self.client.post("/suppliers/new", data={"name": "S1"})
        self.add_product(supplier_id="1")
        self.stock_out(1, 2)
        for url in urls + ["/products/1", "/products/1/edit", "/suppliers/1", "/suppliers/1/edit"]:
            with self.subTest(url=url, data=True):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get("/products/999").status_code, 404)
        self.assertEqual(self.client.get("/no-such-page").status_code, 404)

    def test_output_is_html_escaped(self):
        self.add_product(name="<script>alert(1)</script>", sku="XSS-1")
        page = self.client.get("/products").data
        self.assertNotIn(b"<script>alert(1)</script>", page)
        self.assertIn(b"&lt;script&gt;", page)


class CsrfProtection(StockWiseTestCase):
    csrf = True

    def test_post_without_token_is_rejected_and_with_token_is_accepted(self):
        payload = {"name": "Pen", "sku": "P-1", "category": "X", "quantity": "1", "unit_price": "1",
                   "reorder_level": "0", "target_level": "", "supplier_id": ""}
        self.assertEqual(self.client.post("/products/new", data=payload).status_code, 400)
        self.assertEqual(self.count("products"), 0)
        page = self.client.get("/products/new").data.decode()
        token = page.split('name="csrf_token" value="')[1].split('"')[0]
        response = self.client.post("/products/new", data={**payload, "csrf_token": token}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.count("products"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

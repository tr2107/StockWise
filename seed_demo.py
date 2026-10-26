"""
seed_demo.py - loads sample data so you can explore StockWise straight away.

    python seed_demo.py          adds sample data (only if the database has no products)
    python seed_demo.py --reset  deletes ALL data first, then adds sample data

Everything is added through the same service functions the website uses, so
the transaction history is consistent with the stock quantities.
"""
import os
import sys
from datetime import date, timedelta

import services
from db import BASE_DIR, connect, init_db

DB_PATH = os.environ.get("STOCKWISE_DB", os.path.join(BASE_DIR, "instance", "stockwise.db"))

SUPPLIERS = [
    ("BrightOffice Supplies", "Anita Rao", "+1 555 0101", "orders@brightoffice.example", "12 Market Street, Springfield"),
    ("TechParts Wholesale", "David Chen", "+1 555 0142", "sales@techparts.example", "48 Industrial Park Road, Rivertown"),
    ("CleanCo Distribution", "Maria Lopez", "+1 555 0177", "maria@cleanco.example", "7 Harbour Lane, Portside"),
    ("Fresh Break Foods", "Samuel Okoye", "+1 555 0188", "hello@freshbreak.example", "90 Orchard Avenue, Greenfield"),
]

# name, sku, category, opening qty, price, reorder level, target level, supplier index
PRODUCTS = [
    ("A4 Copy Paper (500 sheets)", "PAP-A4-500", "Stationery", 120, 4.50, 40, 150, 0),
    ("Blue Ballpoint Pens (box of 50)", "PEN-BLU-50", "Stationery", 18, 7.25, 20, 80, 0),
    ("Sticky Notes 3x3 (12 pack)", "STK-3X3-12", "Stationery", 60, 5.10, 25, 100, 0),
    ("USB-C Cable 1m", "USB-C-1M", "Electronics", 45, 6.80, 20, 90, 1),
    ("Wireless Mouse", "MOU-WL-01", "Electronics", 9, 14.99, 10, 40, 1),
    ("HDMI Cable 2m", "HDMI-2M", "Electronics", 0, 8.40, 8, 30, 1),
    ("Laptop Stand", "LAP-STD-01", "Electronics", 22, 24.00, 8, 30, 1),
    ("All-Purpose Cleaner 1L", "CLN-AP-1L", "Cleaning", 35, 3.20, 15, 60, 2),
    ("Hand Soap Refill 500ml", "CLN-HS-500", "Cleaning", 14, 2.75, 15, 60, 2),
    ("Paper Towels (6 rolls)", "CLN-PT-6", "Cleaning", 50, 6.10, 20, 80, 2),
    ("Instant Coffee 200g", "KIT-COF-200", "Kitchen", 26, 5.90, 12, 48, 3),
    ("Tea Bags (100 count)", "KIT-TEA-100", "Kitchen", 8, 3.60, 10, 40, 3),
    ("Bottled Water 24 pack", "KIT-WAT-24", "Kitchen", 30, 7.80, 10, 40, 3),
    ("Disposable Cups (100)", "KIT-CUP-100", "Kitchen", 40, 4.15, 15, 60, 3),
]


def main():
    reset = "--reset" in sys.argv
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Existing database deleted.")
    init_db(DB_PATH)
    db = connect(DB_PATH)

    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] > 0:
        print("The database already contains products, so nothing was added.")
        print("Run  python seed_demo.py --reset  to wipe it and start with sample data.")
        return

    today = date.today()
    supplier_ids = [
        services.create_supplier(db, dict(name=n, contact_person=c, phone=p, email=e, address=a))
        for n, c, p, e, a in SUPPLIERS
    ]

    product_ids = {}
    opening_day = (today - timedelta(days=30)).isoformat()
    for name, sku, cat, qty, price, reorder, target, sup in PRODUCTS:
        # Open with 30 extra units; the monthly-usage removals below then bring each
        # product down to the quantity listed in PRODUCTS.
        start = qty + 30
        product_ids[sku] = services.create_product(
            db,
            dict(name=name, sku=sku, category=cat, quantity=start, unit_price=price,
                 reorder_level=reorder, target_level=target, supplier_id=supplier_ids[sup]),
            opening_day,
        )

    def move(sku, kind, quantity, days_ago, reference="", reason="", notes=""):
        services.record_movement(
            db,
            dict(product_id=product_ids[sku], quantity=quantity, reference=reference, reason=reason,
                 notes=notes, transaction_date=(today - timedelta(days=days_ago)).isoformat()),
            kind,
        )

    # Removals that bring some products down to (or below) their reorder level.
    for sku, qty in [("PAP-A4-500", 30), ("PEN-BLU-50", 30), ("STK-3X3-12", 30), ("USB-C-1M", 30),
                     ("MOU-WL-01", 30), ("HDMI-2M", 30), ("LAP-STD-01", 30), ("CLN-AP-1L", 30),
                     ("CLN-HS-500", 30), ("CLN-PT-6", 30), ("KIT-COF-200", 30), ("KIT-TEA-100", 30),
                     ("KIT-WAT-24", 30), ("KIT-CUP-100", 30)]:
        move(sku, "OUT", qty, 21, reason="Used internally", notes="Monthly usage")

    move("PAP-A4-500", "IN", 60, 14, reference="PO-1001", notes="Regular delivery")
    move("PEN-BLU-50", "OUT", 4, 12, reference="INV-2201", reason="Sold")
    move("USB-C-1M", "OUT", 8, 10, reference="INV-2210", reason="Sold")
    move("MOU-WL-01", "IN", 5, 9, reference="PO-1002")
    move("MOU-WL-01", "OUT", 6, 5, reference="INV-2231", reason="Sold")
    move("CLN-HS-500", "OUT", 5, 4, reason="Used internally", notes="Office refill")
    move("KIT-TEA-100", "OUT", 5, 3, reason="Used internally")
    move("LAP-STD-01", "OUT", 2, 2, reference="INV-2250", reason="Sold")
    move("KIT-WAT-24", "OUT", 6, 1, reason="Used internally", notes="Client event")
    move("PAP-A4-500", "OUT", 22, 1, reference="INV-2255", reason="Sold")

    print(f"Sample data added: {len(SUPPLIERS)} suppliers, {len(PRODUCTS)} products.")
    problems = services.history_matches_stock(db)
    print("History check:", "all consistent." if not problems else problems)
    print("Start the app with:  python app.py")


if __name__ == "__main__":
    main()

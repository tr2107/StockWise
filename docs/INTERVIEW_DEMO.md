# Interview Demonstration (about 8 minutes)

**Preparation:** `python seed_demo.py --reset` then `python app.py`. Open http://127.0.0.1:5000.

## Story to tell first (30 seconds)
"A small office-supply business tracked stock in a spreadsheet. They only found out items had run out when
someone asked for them, and nobody could explain why a count had changed. I built StockWise to give them
accurate stock, early reorder warnings and a full audit trail."

## Walk-through

| Step | What to do | What to say |
|---|---|---|
| 1. Dashboard | Show the four cards and the low-stock table | "Every number comes from SQL queries, not hard-coded values. 5 products are at or below their reorder level; HDMI Cable is out of stock. The suggested order is *target level − current stock*." |
| 2. Add a product | Products → Add product. First try to save a **negative quantity**, then reuse an **existing SKU** | "Validation happens on the server, with clear messages. Even if I bypassed the browser, the database has `CHECK` and `UNIQUE` constraints as a second line of defence." |
| 3. Stock in | Dashboard → *Receive stock* on HDMI Cable → receive 30 with reference PO-5001 | "Quantity goes up and a history row is written in one database transaction." Show it leave the low-stock table. |
| 4. Stock out (the key moment) | Stock Out → Wireless Mouse → remove more than available | "It's blocked: nothing is saved." Then remove 1–2 units and point out the **warning banner** and the alert |
| 5. Transaction history | Transactions page; filter *Stock out* | "Each row stores previous and new quantity, so I can audit every change. They can't be edited or deleted." |
| 6. Protecting history | Try to delete a product that has history | "Refused — it has history. I offer *Archive* instead, which hides it but keeps reports accurate." |
| 7. Suppliers | Open a supplier | "Shows the products they supply, so purchasing knows who to call." |
| 8. Reports | Reports → filter category *Electronics* → Export CSV | "Reports filter by date, category and type, and export to CSV for the accountant." |
| 9. Persistence | Stop the server (Ctrl + C), start it again, refresh | "Data is in SQLite, so it survives restarts." |
| 10. Tests | Run `python -m unittest -v` | "38 automated tests, including the ten business scenarios, atomic rollback, and a check that history always reconciles to stock." |

## Questions you may get — and honest answers

- **Why does quantity appear in two places (products and history)?** Speed and simplicity for the dashboard.
  The risk of disagreement is handled by one function updating both inside one transaction, database CHECK constraints,
  and a reconciliation function used by tests.
- **What if two people remove stock at the same time?** `BEGIN IMMEDIATE` takes the write lock before reading
  the quantity, so the second person sees the updated number.
- **Why can't I edit quantity on the product page?** Every change must have a record. Editing the number would
  create stock with no history.
- **What would you add next?** Login and roles, purchase orders, e-mail alerts for low stock, barcode scanning,
  pagination, and switching to PostgreSQL for several simultaneous users.
- **What are the limits today?** No authentication (local, single-user use), whole-unit quantities, development
  server only.

## Skills this project demonstrates
Requirements analysis (BRD, acceptance criteria) · relational design with constraints · parameterised SQL ·
database transactions · server-side validation · automated and manual testing · reporting/CSV · basic security
(CSRF, XSS escaping, SQL-injection safety) · clear documentation.

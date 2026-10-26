# StockWise — Inventory Reorder & Stock Alert System

A small-business inventory app that tracks products, suppliers and stock movements,
and warns you when something needs reordering.

**Stack:** Python Flask · SQLite · HTML/CSS/JavaScript · Chart.js

| Feature | Where |
|---|---|
| Dashboard (totals, low-stock table, chart, recent activity) | `/` |
| Products: add, edit, search, filter, archive, safe delete | `/products` |
| Suppliers: add, edit, see products supplied | `/suppliers` |
| Stock in / Stock out (with stock checks) | `/stock-in`, `/stock-out` |
| Transaction history (before/after quantities) | `/transactions` |
| Reports with filters + CSV export | `/reports` |

---

## 1. Install and run

You need **Python 3.9 or newer** (the project was built and tested on Python 3.13).
Check with `python --version` (on macOS/Linux you may need `python3`).

Open a terminal **inside the `stockwise` folder**, then:

**Windows (PowerShell)**
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python seed_demo.py        # optional: loads sample data
python app.py
```

**macOS / Linux**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 seed_demo.py       # optional: loads sample data
python3 app.py
```

Now open **http://127.0.0.1:5000** in your browser. Stop the server with `Ctrl + C`.

> Without `seed_demo.py` the app starts empty and shows friendly "add your first product" screens.
> To wipe everything and reload the sample data: `python seed_demo.py --reset`.

The database file is created automatically at `instance/stockwise.db`. Stop and restart the
server as often as you like — your data stays.

> The dashboard chart loads Chart.js from the internet (jsDelivr CDN). If you are offline, the
> same numbers are shown as a list instead.

## 2. Run the tests

```bash
python -m unittest -v
```

Expected ending: `Ran 38 tests ... OK`. The tests use temporary databases, so your real data is never touched.
(`pytest -v` also works if you have pytest installed.)

## 3. Project structure

```
stockwise/
├── app.py            Flask app: all web pages (routes)
├── services.py       Business rules + every database change (stock in/out, delete rules, alerts)
├── validation.py     Checks what the user typed (server-side)
├── db.py             Opens the SQLite connection
├── schema.sql        The database tables and constraints
├── seed_demo.py      Optional sample data
├── templates/        HTML pages (Jinja2)
├── static/           CSS and JavaScript
├── tests/            Automated tests
└── docs/             BRD, requirements, schema, workflow, test cases, interview demo
```

## 4. How it works (the parts worth explaining)

1. **Browser → route → service → database.** A route in `app.py` receives the form,
   `validation.py` checks it, `services.py` applies the business rule and writes to SQLite.
2. **Stock changes are atomic.** Changing a product's quantity *and* writing the history row happen
   inside one database transaction (`BEGIN IMMEDIATE … COMMIT`). If anything fails, `ROLLBACK`
   undoes both, so the quantity and the history can never disagree.
3. **The database protects itself.** `CHECK (quantity >= 0)`, `UNIQUE` SKU, foreign keys with
   `ON DELETE RESTRICT`, and a CHECK that `new_qty = previous_qty ± quantity` mean bad data is
   rejected even if the application code had a bug.
4. **Low stock rule:** a product needs reordering when `quantity <= reorder_level`.
   **Suggested order** = `target_level − quantity` (target defaults to 3 × reorder level when left blank).
5. **History is never silently lost.** Products that have transactions cannot be deleted — they can be
   *archived* (hidden but kept). Transactions cannot be edited or deleted in the app.
6. **Quantity is not editable on the product form.** It changes only through Stock In / Stock Out,
   so every unit is accounted for. A new product with an opening quantity gets an "OPENING" history row.
7. **Security basics:** all SQL uses `?` parameters (no SQL injection), Jinja escapes output (no XSS),
   every form carries a CSRF token, and CSV exports neutralise spreadsheet formulas.

## 5. Settings (optional environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `STOCKWISE_DB` | `instance/stockwise.db` | Path to the database file |
| `STOCKWISE_CURRENCY` | `$` | Currency symbol shown for prices |
| `SECRET_KEY` | dev value | Set a long random value if you ever deploy this |

Example (PowerShell): `$env:STOCKWISE_CURRENCY="₹"; python app.py`

## 6. Known limitations (be upfront about these in an interview)

- **No login / user roles.** Anyone who can open the site can change data. It is meant for a single
  trusted user on a local machine. Adding authentication is the natural next step.
- **Whole-unit quantities only** (no 2.5 kg). Prices are stored as decimal numbers rounded to 2 places.
- **No purchase-order or sales-order documents** — stock in/out are recorded as movements with an optional reference.
- **No pagination:** the transactions page shows the latest 300 records (reports/CSV include everything that matches).
- Built with Flask's development server; use a production server (e.g. gunicorn/waitress) for real deployment.

## 7. Documentation

See the `docs/` folder: `BRD.md`, `FUNCTIONAL_REQUIREMENTS.md`, `DATABASE_SCHEMA.md`,
`WORKFLOW.md`, `TEST_CASES.md`, `INTERVIEW_DEMO.md`.

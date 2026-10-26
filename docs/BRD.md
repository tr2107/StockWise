# Business Requirements Document (BRD)

**Project:** StockWise — Inventory Reorder & Stock Alert System
**Version:** 1.0

## 1. Purpose
Small businesses often track stock in spreadsheets or on paper. Counts drift out of date, nobody
notices an item has run low until a customer asks for it, and nobody can explain *why* a quantity changed.
StockWise gives a small business one place to record what it holds, what comes in and goes out, and
which items must be reordered.

## 2. Business problem and impact
| Problem today | Business impact |
|---|---|
| Low stock is noticed late | Lost sales, rushed (more expensive) purchases |
| Stock counts are edited by hand with no trail | Shrinkage and errors cannot be investigated |
| Supplier details are scattered | Slow reordering |
| Value of stock on hand is unknown | Poor cash-flow decisions |
| Reports are built by hand | Staff time wasted each month |

## 3. Objectives and success measures
| # | Objective | Measure of success |
|---|---|---|
| O1 | Know current stock at any time | Every product shows an accurate quantity; history reconciles to it (checked by automated test) |
| O2 | Be warned before running out | Any product at or below its reorder level appears on the dashboard and product list immediately |
| O3 | Reorder the right amount | Each alert shows a suggested order quantity (target level − current stock) |
| O4 | Have a trustworthy audit trail | Every change to stock has a permanent record with before/after quantities |
| O5 | Reduce manual reporting | Stock, low-stock and movement reports can be filtered and exported to CSV in a few clicks |

## 4. Scope
**In scope:** products, suppliers, stock-in, stock-out, low-stock alerts and reorder suggestions,
transaction history, dashboard, filtered reports with CSV export, persistent storage.

**Out of scope (future work):** user accounts and permissions, purchase-order and sales-order documents,
barcode scanning, multi-location warehouses, fractional quantities, e-mail/SMS alerts, accounting integration, supplier price lists.

## 5. Stakeholders
| Role | Interest |
|---|---|
| Business owner / manager | Stock value, avoiding stock-outs, reports |
| Stock clerk / storekeeper | Fast, simple recording of stock received and removed |
| Purchasing staff | Knowing what to order, how much, and from whom |
| Accountant (indirect) | Inventory value and movement reports |

## 6. Business requirements
| ID | Requirement | Priority |
|---|---|---|
| BR-01 | The business can maintain a list of products with SKU, category, price, quantity, reorder level and supplier | Must |
| BR-02 | The business can record stock received and stock removed, each with date and notes | Must |
| BR-03 | The system must never allow stock to be removed that does not exist | Must |
| BR-04 | The system must alert staff when stock reaches the reorder level and suggest an order quantity | Must |
| BR-05 | The business can maintain supplier details and see which products each supplier provides | Must |
| BR-06 | A permanent history of all stock changes must be kept and stay consistent with quantities | Must |
| BR-07 | Management can see headline figures (products, units, value, items to reorder) at a glance | Must |
| BR-08 | Management can produce and export reports filtered by date, category and transaction type | Should |
| BR-09 | Data must survive restarts and be saved reliably | Must |
| BR-10 | The system must be usable on a desktop and a phone without training | Should |

## 7. Business rules
1. A SKU identifies exactly one product (case-insensitive).
2. Quantity, price and reorder level cannot be negative.
3. A product **needs reorder** when `quantity <= reorder level`.
4. **Suggested order quantity** = `target stock level − current quantity` (never below 0).
5. Stock can only change through a recorded stock-in or stock-out.
6. Transactions are permanent; corrections are made with a new opposite transaction.
7. A product that has any transaction cannot be deleted; it can be archived.
8. Stock-out requires a reason (sold, used internally, damaged, expired, returned to supplier, lost, other).
9. Transaction dates cannot be in the future.

## 8. Assumptions and constraints
- Single business, single location, one trusted user at a time (no login in version 1).
- Runs on a local computer using Python 3 with Flask and SQLite; no paid software.
- Quantities are whole units.
- Prices are shown in one currency (configurable symbol).

## 9. Risks
| Risk | Mitigation |
|---|---|
| Quantities and history disagree | Single atomic transaction for both; database CHECK constraints; automated reconciliation test |
| Wrong data typed | Server-side validation with clear messages; database constraints as a second line of defence |
| Data loss | Data lives in a SQLite file that can be backed up by copying; `.gitignore` keeps it out of source control |
| Unauthorised changes | Accepted limitation in v1 (local use); authentication listed as next step |

## 10. Acceptance
The project is accepted when every functional requirement in `FUNCTIONAL_REQUIREMENTS.md` meets its acceptance
criteria and the test cases in `TEST_CASES.md` pass.

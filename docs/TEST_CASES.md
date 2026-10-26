# Test Cases — Expected and Actual Results

**Test run:** 25 Oct 2026 · Python 3.13 · Flask 3.1 · SQLite 3.45 · Chromium (screenshots)
**Command:** `python -m unittest -v`
**Result:** `Ran 38 tests … OK` — 38 passed, 0 failed.

Each automated test creates a fresh temporary database, so tests cannot affect each other or your real data.
You can re-run them any time; re-record the "Actual" column if your results differ.

## 1. The ten required test cases

| ID | Test case | Steps | Expected result | Actual result | Status |
|---|---|---|---|---|---|
| TC-01 | Add a valid product | Submit the product form: "Blue Pen", SKU PEN-001, qty 20, price 2.50, reorder level 5 | Product saved; success message; target level defaults to 15 | Saved with quantity 20, price 2.5, reorder 5, target 15; "was added" shown | **Pass** |
| TC-02 | Reject duplicate SKU | Add PEN-001 twice; then add "pen-001" | Second and third attempts rejected with "A product with this SKU already exists"; only 1 product in database | Second attempt rejected (HTTP 400) with that message; lower-case "pen-001" also rejected (HTTP 400); still 1 row in `products` | **Pass** |
| TC-03 | Reject negative quantity | Add a product with quantity −5 | Rejected with "Quantity cannot be negative"; nothing saved | Rejected (HTTP 400), message shown, 0 rows saved | **Pass** |
| TC-04 | Record stock received | 20 in stock; receive 10 with reference PO-77 and notes | Quantity 30; IN transaction with previous 20, new 30, reference and notes saved | Quantity 30; transaction (10, 20→30) with reference "PO-77" and the notes | **Pass** |
| TC-05 | Record stock removed | 20 in stock; remove 8, reason Sold | Quantity 12; OUT transaction previous 20, new 12, reason saved | Quantity 12; transaction (8, 20→12, "Sold") | **Pass** |
| TC-06 | Reject stock-out above available stock | 20 in stock; remove 21 | Error "Not enough stock"; quantity stays 20; no transaction saved | HTTP 400 with message; quantity 20; transaction count unchanged | **Pass** |
| TC-07 | Alert when quantity reaches reorder level | Level 5; remove down to 6 (no alert), then to exactly 5 | No alert at 6. At 5: warning message, product in low-stock list, "Order 10" suggestion, "Reorder" badge in product list and on dashboard | No alert at 6. At 5: "Low stock: Blue Pen is at 5" shown; low-stock list had 1 item with suggested order 10; dashboard and product list showed it | **Pass** |
| TC-08 | Dashboard updates after a transaction | 1 product (20 × 2.50); view dashboard; remove 15; view again | Before: 1 product, 20 units, $50.00. After: 5 units, $12.50, 1 needs reorder, category total 5, newest transaction is OUT | Matched exactly; page showed "$12.50" and "Removed 15" | **Pass** |
| TC-09 | Records preserved after restart | Add product, receive 5, remove 3; build a brand-new app on the same database file | Product, quantity 22 and all 3 transactions still present | Present after restart; history reconciled | **Pass** |
| TC-10 | History matches stock changes | Two products; several in/out movements plus one rejected removal | For each product the history chain adds up to the quantity; rejected movement leaves no row | `history_matches_stock()` returned no problems; chain for Blue Pen was IN 10 (0→10), IN 15 (10→25), OUT 7 (25→18) | **Pass** |

## 2. Additional automated tests

| ID | Test (method name) | What it proves | Status |
|---|---|---|---|
| PR-01 | `test_required_fields_and_bad_numbers` | Empty name/SKU, non-numeric or negative price/level, decimal or text quantity, bad SKU characters, target < reorder level are all rejected | Pass |
| PR-02 | `test_opening_stock_creates_history_row` | Opening quantity creates an `OPENING` IN transaction (0 → qty) | Pass |
| PR-03 | `test_zero_opening_stock_has_no_history_row` | No history row for a product starting at 0 | Pass |
| PR-04 | `test_edit_product_changes_details_but_not_quantity` | Edits save; a tampered `quantity` field is ignored | Pass |
| PR-05 | `test_edit_cannot_steal_another_products_sku` | Editing cannot create a duplicate SKU | Pass |
| PR-06 | `test_search_and_filters` | Search, category and low-stock filters; empty-state message | Pass |
| PR-07 | `test_search_is_safe_against_sql_injection` | `' OR 1=1; DROP TABLE …` in search is harmless | Pass |
| DA-01 | `test_product_with_history_cannot_be_deleted` | App refuses delete; history kept | Pass |
| DA-02 | `test_database_itself_blocks_deleting_history` | Even a raw `DELETE` is blocked by the foreign key | Pass |
| DA-03 | `test_product_without_history_can_be_deleted` | Delete allowed when no history | Pass |
| DA-04 | `test_archive_hides_product_but_keeps_history` | Archive hides the product everywhere, keeps history, blocks stock changes, restore works | Pass |
| MV-01 | `test_invalid_movement_forms_are_rejected` | Quantity 0/negative/text/blank, future or malformed or blank date, no/unknown product → all rejected, stock unchanged | Pass |
| MV-02 | `test_stock_out_requires_valid_reason` | Missing or invalid reason rejected | Pass |
| MV-03 | `test_can_remove_exactly_all_stock` | Removing all stock gives 0 and "Out of stock" | Pass |
| AT-01 | `test_failed_save_rolls_back_quantity_and_history_together` | A failure while writing history undoes the quantity change (atomicity) | Pass |
| AT-02 | `test_database_rejects_inconsistent_history_and_negative_stock` | Database CHECK constraints reject negative stock and history rows whose numbers do not add up | Pass |
| SU-01 | `test_add_edit_and_view_supplier_with_products` | Add/edit supplier; supplier page lists its products | Pass |
| SU-02 | `test_supplier_validation` | Name required; bad e-mail/phone rejected; duplicate name (any case) rejected | Pass |
| SU-03 | `test_product_rejects_unknown_supplier` | Product cannot reference a non-existent supplier | Pass |
| RP-01 | `test_report_page_totals` | Inventory value total correct ($82.50) | Pass |
| RP-02 | `test_stock_csv` | CSV headers, content type, attachment header and values | Pass |
| RP-03 | `test_low_stock_csv_and_category_filter` | Low-stock CSV and suggested order; category filter | Pass |
| RP-04 | `test_movement_filters` | Type and date filters on CSV and transactions page | Pass |
| RP-05 | `test_csv_blocks_spreadsheet_formula_injection` | Cells starting with `=` are neutralised | Pass |
| RP-06 | `test_unknown_export_is_404` | Unknown export name returns 404 | Pass |
| PG-01 | `test_every_page_loads_with_and_without_data` | All pages return 200 on an empty database (empty states) and with data; missing records return 404 | Pass |
| SC-01 | `test_post_without_token_is_rejected_and_with_token_is_accepted` | CSRF protection | Pass |
| SC-02 | `test_output_is_html_escaped` | `<script>` in a product name is shown as text | Pass |

## 3. Manual / live checks performed

| Check | Expected | Actual | Status |
|---|---|---|---|
| Real server: POST a form with no CSRF token | Rejected | HTTP 400 | Pass |
| Real server: add product (12), remove 9, try to remove 99 | 302, 302, then rejected | 302, 302, 400; stock 3 | Pass |
| Real server: **stop the process and start a new one** | Product, quantity 3 and both transactions (+12, −9) still shown | All present; dashboard showed suggested "Order 12" (target 15 − 3) | Pass |
| Seed script | 4 suppliers, 14 products, history consistent | "History check: all consistent." Dashboard: 14 products, 484 units, 5 need reorder | Pass |
| Rule sensitivity ("does the test really test?") | Changing `<=` to `<` in the alert rule should make a test fail | `test_07` failed; restored and re-ran: 38 OK | Pass |
| Visual check at 1366 px and 390 px (Chromium) | Layout readable, sidebar collapses on mobile | Dashboard and Stock Out form rendered correctly; mobile stacks cards | Pass |

## 4. Not verified in the test environment

- **The Chart.js bar chart itself.** The test environment could not reach the Chart.js CDN, so only the
  offline fallback (a list of the same figures) was seen. The chart code is short (`static/js/dashboard.js`);
  please confirm the bar chart appears when you run it with internet access.
- Running on Windows/macOS, other browsers (Firefox, Safari), and Python versions other than 3.13.

## 5. How to record your own run

1. Run `python -m unittest -v` and copy the final lines into your notes.
2. Start the app, repeat the manual checks in §3 by hand, and write what you actually saw.

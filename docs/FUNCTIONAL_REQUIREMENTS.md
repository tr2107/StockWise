# Functional Requirements and Acceptance Criteria

Format: *Given* a starting situation, *When* the user acts, *Then* the expected result.
"Test" shows which automated test checks it (see `TEST_CASES.md`).

## Dashboard
| ID | Requirement | Acceptance criteria | Test |
|---|---|---|---|
| FR-01 | Show total products, total units, products needing reorder and inventory value, all calculated from the database | Given 1 product with 20 units at 2.50, when the dashboard loads, then it shows 1 product, 20 units, $50.00. After removing 15 units it shows 5 units, $12.50 and 1 product needing reorder | TC-08 |
| FR-02 | Show a table of low-stock products with name, quantity, reorder level, suggested order and supplier | Given a product at or below its reorder level, then it is listed; products above it are not | TC-07 |
| FR-03 | Show a chart of units in stock by category | Given products in several categories, then the chart (or, offline, a list) shows each category's total units | TC-08 (data), manual (chart) |
| FR-04 | Show the 8 most recent stock transactions | After a stock-out the newest entry is that transaction | TC-08 |

## Product management
| ID | Requirement | Acceptance criteria | Test |
|---|---|---|---|
| FR-05 | Add a product with name, SKU, category, quantity, unit price, reorder level, optional target level and supplier | Given valid data, then the product is saved and a success message is shown | TC-01 |
| FR-06 | Edit product details | Given an existing product, when details are changed, then they are saved. Quantity is not editable here | PR-04 |
| FR-07 | View all products; search by name/SKU/category; filter by category, supplier, stock status | Given a search term, only matching products appear; with no matches an empty-state message appears | PR-06 |
| FR-08 | Delete a product only if it has no transaction history; otherwise offer archive | Given a product with history, when Delete is pressed, then it is refused with an explanation and the history remains. Given a product with no history, it is deleted | DA-01…DA-04 |
| FR-09 | SKU must be unique | Given SKU "PEN-001" exists, when another product uses "PEN-001" or "pen-001", then it is rejected | TC-02 |
| FR-10 | Quantity cannot be negative | Given quantity −5, then the product is rejected with "Quantity cannot be negative" | TC-03 |

## Stock in / stock out
| ID | Requirement | Acceptance criteria | Test |
|---|---|---|---|
| FR-11 | Record stock received: product, quantity, date, optional reference and notes | Given 20 in stock, when 10 are received, then quantity is 30 and a transaction IN (previous 20, new 30) is saved | TC-04 |
| FR-12 | Record stock removed: product, quantity, date, reason, notes | Given 20 in stock, when 8 are removed for "Sold", then quantity is 12 and a transaction OUT (previous 20, new 12) is saved | TC-05 |
| FR-13 | Block stock-out larger than available stock | Given 20 in stock, when 21 are removed, then an error is shown, the quantity stays 20 and no transaction is saved | TC-06 |
| FR-13a | Validate movement forms | Quantity must be a whole number ≥ 1; date must be valid and not in the future; stock-out needs a valid reason; archived products are refused | MV-01…MV-03 |

## Alerts
| ID | Requirement | Acceptance criteria | Test |
|---|---|---|---|
| FR-14 | Each product has a configurable reorder level; at or below it the product is flagged "Reorder" (or "Out of stock" at 0) with a visible warning | Given level 5, when stock falls from 6 to 5, then a warning appears after the transaction, the product shows "Reorder", and it appears on the dashboard and in the header count | TC-07 |
| FR-15 | Show a suggested reorder quantity = target level − current stock | Given target 15 and stock 5, then "Order 10" is shown | TC-07 |

## Suppliers
| ID | Requirement | Acceptance criteria | Test |
|---|---|---|---|
| FR-16 | Add and edit suppliers (name, contact person, phone, email, address) | Valid data is saved; duplicate names, bad e-mail or phone are rejected | SU-01, SU-02 |
| FR-17 | Link products to a supplier | The product form lists suppliers; unknown suppliers are rejected | SU-03 |
| FR-18 | View the products supplied by each supplier | The supplier page lists its products with stock status | SU-01 |

## Transaction history
| ID | Requirement | Acceptance criteria | Test |
|---|---|---|---|
| FR-19 | List all transactions with ID, product, type, quantity, previous, new, date, reference/notes | Every row shows these fields; filters by type, date range and text | RP-04 |
| FR-20 | History stays consistent with quantities and is never silently erased | For every product, the movements chain (previous → new) and end at the current quantity; products with history cannot be deleted | TC-09, TC-10, DA-01, DA-02 |

## Reports
| ID | Requirement | Acceptance criteria | Test |
|---|---|---|---|
| FR-21 | Reports page: stock by product, low-stock products, inventory value, movement history | Totals match the data | RP-01 |
| FR-22 | Filter by date, category and transaction type | Category filters all sections; date and type filter movements | RP-03, RP-04 |
| FR-23 | Export stock, low-stock and movement reports to CSV (respecting filters) | Download opens in Excel with correct columns and values; cells beginning `= + - @` are neutralised | RP-02, RP-05 |

## Non-functional requirements
| ID | Requirement | Verified by |
|---|---|---|
| NFR-01 | Data persists after refresh, navigation and server restart | TC-09 and a live server restart (TEST_CASES.md §3) |
| NFR-02 | Quantity change and history record succeed or fail together | AT-01 |
| NFR-03 | Parameterised SQL, escaped output, CSRF tokens | PR-07, SC-02, SC-01 |
| NFR-04 | Responsive layout, clear success/error messages, empty states | Screenshots at 1366 px and 390 px; PG-01 |

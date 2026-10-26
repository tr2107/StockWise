# Workflows

## 1. Overall stock lifecycle

```mermaid
flowchart TD
    A[Add supplier] --> B[Add product<br/>SKU, category, price, reorder level, target level, supplier]
    B --> C{Opening quantity > 0?}
    C -- yes --> D[System records OPENING stock-in]
    C -- no --> E[Product ready]
    D --> E
    E --> F[Stock In: goods received]
    E --> G[Stock Out: sold / used / removed]
    F --> H[(Quantity up + history row<br/>one database transaction)]
    G --> I{Enough stock?}
    I -- no --> J[Error shown. Nothing saved]
    I -- yes --> K[(Quantity down + history row<br/>one database transaction)]
    H --> L{Quantity <= reorder level?}
    K --> L
    L -- yes --> M[Low-stock warning + dashboard alert<br/>+ suggested order = target - quantity]
    L -- no --> N[No alert]
    M --> O[Purchasing orders from supplier]
    O --> F
```

## 2. Stock-out step by step

1. User opens **Stock Out**, picks a product (current stock is shown), enters quantity, date and reason.
2. The browser checks the basics (required fields, `max` quantity).
3. The server **validates again** (browser checks can be bypassed): whole number ≥ 1, valid non-future date, valid reason.
4. `BEGIN IMMEDIATE` locks the database for writing.
5. The server reads the current quantity. If `quantity > available` → `ROLLBACK`, show an error.
6. Otherwise it updates `products.quantity` and inserts a `stock_transactions` row (previous, new, reason, notes).
7. `COMMIT`. If anything failed in steps 5–6, `ROLLBACK` undoes everything.
8. The user sees a success message, and a warning if the new quantity is at or below the reorder level.

## 3. Handling a mistake
Transactions cannot be edited. If 10 units were received by mistake, record a Stock Out of 10 with reason
"Other" and a note. The history then shows both entries and the quantity is correct.

## 4. Deleting vs archiving a product

```mermaid
flowchart TD
    A[User presses Delete] --> B{Product has any transactions?}
    B -- no --> C[Product deleted]
    B -- yes --> D[Refused with explanation]
    D --> E[User can Archive instead]
    E --> F[Hidden from lists, dashboard, stock forms.<br/>History and reports keep working.<br/>Can be restored.]
```

## 5. Reorder process
1. Dashboard / product list shows products at or below their reorder level (most urgent first).
2. Purchasing reads the suggested order quantity and supplier, and exports **Low-stock CSV** if needed.
3. Goods arrive → **Receive stock** records Stock In with the purchase-order reference.
4. The product leaves the alert list automatically once it is above its reorder level.

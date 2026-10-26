-- StockWise database schema (SQLite)
-- "IF NOT EXISTS" means running this file again never wipes existing data.

CREATE TABLE IF NOT EXISTS suppliers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    contact_person TEXT NOT NULL DEFAULT '',
    phone          TEXT NOT NULL DEFAULT '',
    email          TEXT NOT NULL DEFAULT '',
    address        TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    sku           TEXT    NOT NULL UNIQUE COLLATE NOCASE,        -- no two products share a SKU
    category      TEXT    NOT NULL DEFAULT 'General',
    quantity      INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0), -- stock can never go negative
    unit_price    REAL    NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    reorder_level INTEGER NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
    target_level  INTEGER NOT NULL DEFAULT 0 CHECK (target_level >= reorder_level),
    supplier_id   INTEGER REFERENCES suppliers(id) ON DELETE RESTRICT,
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),  -- 0 = archived
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS stock_transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id       INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,  -- history is protected
    type             TEXT    NOT NULL CHECK (type IN ('IN', 'OUT')),
    quantity         INTEGER NOT NULL CHECK (quantity > 0),   -- how many units moved
    previous_qty     INTEGER NOT NULL CHECK (previous_qty >= 0),
    new_qty          INTEGER NOT NULL CHECK (new_qty >= 0),
    transaction_date TEXT    NOT NULL,                         -- YYYY-MM-DD
    reference        TEXT    NOT NULL DEFAULT '',              -- e.g. purchase order number
    reason           TEXT    NOT NULL DEFAULT '',              -- used for stock-out
    notes            TEXT    NOT NULL DEFAULT '',
    created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    -- The numbers must always add up, whatever the application does:
    CHECK (
        (type = 'IN'  AND new_qty = previous_qty + quantity) OR
        (type = 'OUT' AND new_qty = previous_qty - quantity)
    )
);

CREATE INDEX IF NOT EXISTS idx_products_category    ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_supplier    ON products(supplier_id);
CREATE INDEX IF NOT EXISTS idx_transactions_product ON stock_transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date    ON stock_transactions(transaction_date);

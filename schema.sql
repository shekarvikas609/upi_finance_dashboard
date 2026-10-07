-- SQLite schema for the finance dashboard. Created automatically by src/db.py,
-- kept here as a readable reference you can run yourself: sqlite3 data/finance.db < schema.sql

CREATE TABLE IF NOT EXISTS statements (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    filename       TEXT NOT NULL,
    file_hash      TEXT NOT NULL UNIQUE,   -- prevents loading the same file twice
    uploaded_at    TEXT NOT NULL,
    n_transactions INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    statement_id    INTEGER NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
    date            TEXT NOT NULL,
    narration       TEXT NOT NULL,
    merchant        TEXT NOT NULL,
    amount          REAL NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('DR','CR')),
    txn_type        TEXT NOT NULL,
    month           TEXT NOT NULL,
    category        TEXT NOT NULL,
    category_source TEXT NOT NULL,          -- rule | ml | learned | you | needs review
    confidence      REAL NOT NULL,
    is_anomaly      INTEGER NOT NULL DEFAULT 0,
    flag_reasons    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tx_month    ON transactions(month);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category);
CREATE INDEX IF NOT EXISTS idx_tx_merchant ON transactions(merchant);

-- "Teach it once, it remembers": when you fix a category in the app, the merchant
-- goes here and every future transaction from that merchant is auto-categorised.
CREATE TABLE IF NOT EXISTS merchant_overrides (
    merchant   TEXT PRIMARY KEY,
    category   TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Audit trail of every fix you've made, for "how much did I have to correct the model" reporting.
CREATE TABLE IF NOT EXISTS category_corrections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    old_category    TEXT NOT NULL,
    new_category    TEXT NOT NULL,
    corrected_at    TEXT NOT NULL
);

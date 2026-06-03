-- Receipt Tracker — Database Schema
-- Run this in the Supabase SQL editor (or any PostgreSQL 15+ instance).
-- For local dev, this file is auto-run by docker-compose via initdb.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ── Categories (lookup table, seeded below) ─────────────────────────────────

CREATE TABLE IF NOT EXISTS categories (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        VARCHAR(50) UNIQUE NOT NULL,
    label       VARCHAR(100) NOT NULL
);

-- ── Stores ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stores (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    branch      VARCHAR(255),
    address     VARCHAR(500),
    city        VARCHAR(100),
    province    CHAR(2),
    postal_code VARCHAR(7),
    phone       VARCHAR(20),
    type        VARCHAR(50),   -- 'grocery' | 'dollar' | null
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- NULL-safe unique store: same store name + branch + city = one row
CREATE UNIQUE INDEX IF NOT EXISTS uq_store_name_branch_city
    ON stores (name, COALESCE(branch, ''), COALESCE(city, ''));

-- ── Items (normalized product names for comparison) ──────────────────────────

CREATE TABLE IF NOT EXISTS items (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_name TEXT        NOT NULL,
    category_id     UUID        REFERENCES categories(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_items_name_trgm
    ON items USING GIN (normalized_name gin_trgm_ops);

-- ── Receipts ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS receipts (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id           UUID        NOT NULL REFERENCES stores(id),
    purchase_date      DATE,
    transaction_number VARCHAR(100),
    customer_name      VARCHAR(255),
    subtotal           NUMERIC(10, 2),
    tax                NUMERIC(10, 2),
    total              NUMERIC(10, 2),
    image_count        INTEGER     DEFAULT 1,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_receipts_purchase_date ON receipts (purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_store_id      ON receipts (store_id);

-- ── Receipt Items ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS receipt_items (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id  UUID        NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    item_id     UUID        NOT NULL REFERENCES items(id),
    raw_name    VARCHAR(500) NOT NULL,
    quantity    NUMERIC(10, 3),
    unit        VARCHAR(20),
    unit_price  NUMERIC(10, 2),
    total_price NUMERIC(10, 2) NOT NULL,
    savings     NUMERIC(10, 2),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_receipt_items_receipt_id ON receipt_items (receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipt_items_item_id    ON receipt_items (item_id);
CREATE INDEX IF NOT EXISTS idx_receipt_items_raw_name   ON receipt_items USING GIN (raw_name gin_trgm_ops);

-- ── Seed categories ───────────────────────────────────────────────────────────

INSERT INTO categories (slug, label) VALUES
    ('fruits',         'Fruits'),
    ('vegetables',     'Vegetables'),
    ('dairy',          'Dairy'),
    ('meat',           'Meat'),
    ('seafood',        'Seafood'),
    ('bakery',         'Bakery'),
    ('beverages',      'Beverages'),
    ('snacks',         'Snacks'),
    ('frozen',         'Frozen'),
    ('canned_goods',   'Canned Goods'),
    ('household',      'Household'),
    ('cleaning',       'Cleaning'),
    ('stationery',     'Stationery'),
    ('electronics',    'Electronics'),
    ('clothing',       'Clothing'),
    ('health_beauty',  'Health & Beauty'),
    ('tools_hardware', 'Tools & Hardware'),
    ('other',          'Other')
ON CONFLICT (slug) DO NOTHING;

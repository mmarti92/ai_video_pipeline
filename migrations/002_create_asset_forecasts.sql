-- Migration: Create asset_forecasts table
--
-- Apply with:
--   psql "$PG_CONNECTION_STRING" -f migrations/002_create_asset_forecasts.sql
--
-- Compatible with CockroachDB and standard PostgreSQL.

CREATE TABLE IF NOT EXISTS asset_forecasts (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_symbol    VARCHAR(10)  NOT NULL,
    forecast_date   DATE         NOT NULL,
    current_price   DECIMAL(12, 2) NOT NULL,
    predicted_price DECIMAL(12, 2) NOT NULL,
    confidence      DECIMAL(5, 2),
    analyst_rating  VARCHAR(20),
    key_factors     TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_asset_forecasts_stock_symbol
    ON asset_forecasts (stock_symbol);

CREATE INDEX IF NOT EXISTS idx_asset_forecasts_date
    ON asset_forecasts (forecast_date);

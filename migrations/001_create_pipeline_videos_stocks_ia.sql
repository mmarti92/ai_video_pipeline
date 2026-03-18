-- Migration: Create pipeline_videos_stocks_ia table
--
-- Apply with:
--   psql "$PG_CONNECTION_STRING" -f migrations/001_create_pipeline_videos_stocks_ia.sql
--
-- Compatible with CockroachDB and standard PostgreSQL.

CREATE TABLE IF NOT EXISTS pipeline_videos_stocks_ia (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_symbol  VARCHAR(10)  NOT NULL,
    title         VARCHAR(255),
    description   TEXT,
    status        VARCHAR(20)  NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    output_path   VARCHAR(500),
    error_message TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_videos_stocks_ia_status
    ON pipeline_videos_stocks_ia (status);

CREATE INDEX IF NOT EXISTS idx_pipeline_videos_stocks_ia_stock_symbol
    ON pipeline_videos_stocks_ia (stock_symbol);

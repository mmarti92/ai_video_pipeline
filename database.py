"""
Database module for the AI video pipeline.

Manages the PostgreSQL / CockroachDB connection and all CRUD operations
against the `pipeline_videos_stocks_ia` table.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

TABLE_NAME = "pipeline_videos_stocks_ia"

# Module-level connection pool (initialised by init_db)
_pool: Optional[ThreadedConnectionPool] = None


def init_db(connection_string: str, min_conn: int = 1, max_conn: int = 5) -> None:
    """Initialise the connection pool and ensure the table exists."""
    global _pool
    _pool = ThreadedConnectionPool(min_conn, max_conn, dsn=connection_string)
    logger.info("Database connection pool initialised.")
    _create_table_if_not_exists()


def close_db() -> None:
    """Close all connections in the pool."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        logger.info("Database connection pool closed.")


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager that yields a pooled connection and returns it afterwards."""
    if _pool is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    conn = _pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        _pool.putconn(conn)


def _create_table_if_not_exists() -> None:
    """Create the pipeline_videos_stocks_ia table if it does not exist."""
    ddl = f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            stock_symbol VARCHAR(10) NOT NULL,
            title        VARCHAR(255),
            description  TEXT,
            status       VARCHAR(20)  NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
            output_path  VARCHAR(500),
            error_message TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
    logger.info("Table '%s' verified / created.", TABLE_NAME)


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def fetch_pending_jobs(limit: int = 10) -> list[dict]:
    """Return up to *limit* rows with status='pending'."""
    sql = f"""
        SELECT id, stock_symbol, title, description
        FROM   {TABLE_NAME}
        WHERE  status = 'pending'
        ORDER  BY created_at
        LIMIT  %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (limit,))
            return [dict(row) for row in cur.fetchall()]


def mark_processing(job_id: str) -> None:
    """Set the job status to 'processing'."""
    sql = f"""
        UPDATE {TABLE_NAME}
        SET    status = 'processing', updated_at = NOW()
        WHERE  id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (job_id,))


def mark_completed(job_id: str, output_path: str) -> None:
    """Set the job status to 'completed' and store the output path."""
    sql = f"""
        UPDATE {TABLE_NAME}
        SET    status = 'completed', output_path = %s, updated_at = NOW()
        WHERE  id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (output_path, job_id))


def mark_failed(job_id: str, error_message: str) -> None:
    """Set the job status to 'failed' and store the error message."""
    sql = f"""
        UPDATE {TABLE_NAME}
        SET    status = 'failed', error_message = %s, updated_at = NOW()
        WHERE  id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (error_message, job_id))


def insert_job(
    stock_symbol: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """Insert a new pending job and return its UUID."""
    sql = f"""
        INSERT INTO {TABLE_NAME} (stock_symbol, title, description)
        VALUES (%s, %s, %s)
        RETURNING id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (stock_symbol, title, description))
            return cur.fetchone()[0]

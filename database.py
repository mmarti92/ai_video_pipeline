"""
Database module for the AI video pipeline.

Manages the PostgreSQL / CockroachDB connection and all CRUD operations
against the `pipeline_videos_stocks_ia` table.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional
from urllib.parse import urlparse, parse_qs, urlunparse

import psycopg2
import psycopg2.extras
import requests
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

TABLE_NAME = "pipeline_videos_stocks_ia"
FORECASTS_TABLE_NAME = "asset_forecasts"

# Module-level connection pool (initialised by init_db)
_pool: Optional[ThreadedConnectionPool] = None

# Well-known CA bundle paths across Linux distributions and macOS.
_CA_BUNDLE_CANDIDATES = [
    "/etc/ssl/certs/ca-certificates.crt",  # Debian / Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",    # RHEL / CentOS / Fedora
    "/etc/ssl/ca-bundle.pem",              # openSUSE
    "/etc/ssl/cert.pem",                   # Alpine / macOS
]

# Default path where libpq looks for the root CA certificate.
_DEFAULT_ROOT_CERT = os.path.expanduser("~/.postgresql/root.crt")


def _download_crdb_cert(url: str) -> Optional[str]:
    """Download the CockroachDB cluster CA cert to ``~/.postgresql/root.crt``.

    Returns the path on success, or *None* on failure.  If the file
    already exists it is **not** re-downloaded.  Only HTTPS URLs are
    accepted to prevent insecure certificate downloads.
    """
    if os.path.isfile(_DEFAULT_ROOT_CERT):
        logger.info("CockroachDB root cert already present at %s.", _DEFAULT_ROOT_CERT)
        return _DEFAULT_ROOT_CERT

    if not url.lower().startswith("https://"):
        logger.warning("Refusing to download CA cert over insecure URL: %s", url)
        return None

    try:
        os.makedirs(os.path.dirname(_DEFAULT_ROOT_CERT), exist_ok=True)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(_DEFAULT_ROOT_CERT, "wb") as f:
            f.write(resp.content)
        logger.info("Downloaded CockroachDB root cert to %s.", _DEFAULT_ROOT_CERT)
        return _DEFAULT_ROOT_CERT
    except Exception:
        logger.warning(
            "Failed to download CockroachDB cert from %s.", url, exc_info=True
        )
        return None


def _find_ca_bundle() -> Optional[str]:
    """Locate the system CA certificate bundle."""
    for path in _CA_BUNDLE_CANDIDATES:
        if os.path.isfile(path):
            return path
    try:                           # pragma: no cover – certifi may not be installed
        import certifi
        return certifi.where()
    except ImportError:
        return None


def _ensure_sslrootcert(
    connection_string: str,
    crdb_ca_cert_url: str = "",
) -> str:
    """Append ``sslrootcert`` to the DSN when CockroachDB Cloud needs it.

    CockroachDB Cloud connection strings normally carry
    ``sslmode=verify-full``.  libpq then looks for a root CA at
    ``~/.postgresql/root.crt``, which rarely exists inside CI runners or
    Docker containers.

    Resolution order:

    1. ``sslrootcert`` already in DSN → no-op.
    2. ``~/.postgresql/root.crt`` already on disk → no-op (libpq finds it).
    3. *crdb_ca_cert_url* is set → download the cluster cert to
       ``~/.postgresql/root.crt`` and let libpq find it.
    4. Fall back to appending the system CA bundle path.
    """
    parsed = urlparse(connection_string)
    params = parse_qs(parsed.query)

    sslmode = params.get("sslmode", [""])[0]
    if sslmode not in ("verify-full", "verify-ca"):
        return connection_string

    if "sslrootcert" in params:
        return connection_string

    if os.path.isfile(_DEFAULT_ROOT_CERT):
        return connection_string

    # Try downloading the cluster-specific cert.
    if crdb_ca_cert_url:
        downloaded = _download_crdb_cert(crdb_ca_cert_url)
        if downloaded:
            # libpq will now find ~/.postgresql/root.crt automatically.
            return connection_string

    ca_bundle = _find_ca_bundle()
    if ca_bundle is None:
        logger.warning(
            "sslmode=%s but no system CA bundle found; "
            "the connection may fail.",
            sslmode,
        )
        return connection_string

    separator = "&" if parsed.query else ""
    new_query = f"{parsed.query}{separator}sslrootcert={ca_bundle}"
    result = urlunparse(parsed._replace(query=new_query))
    logger.info("Appended sslrootcert=%s for TLS verification.", ca_bundle)
    return result


def init_db(
    connection_string: str,
    min_conn: int = 1,
    max_conn: int = 5,
    crdb_ca_cert_url: str = "",
) -> None:
    """Initialise the connection pool and ensure the table exists."""
    global _pool
    dsn = _ensure_sslrootcert(connection_string, crdb_ca_cert_url=crdb_ca_cert_url)
    _pool = ThreadedConnectionPool(min_conn, max_conn, dsn=dsn)
    logger.info("Database connection pool initialised.")
    _create_table_if_not_exists()
    _create_forecasts_table_if_not_exists()


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


def _create_forecasts_table_if_not_exists() -> None:
    """Create the asset_forecasts table if it does not exist."""
    ddl = f"""
        CREATE TABLE IF NOT EXISTS {FORECASTS_TABLE_NAME} (
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
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
    logger.info("Table '%s' verified / created.", FORECASTS_TABLE_NAME)


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


# ---------------------------------------------------------------------------
# Forecast helpers
# ---------------------------------------------------------------------------

def fetch_forecasts(stock_symbol: str) -> list[dict]:
    """Return all forecast rows for *stock_symbol*, ordered by date."""
    sql = f"""
        SELECT stock_symbol, forecast_date, current_price, predicted_price,
               confidence, analyst_rating, key_factors
        FROM   {FORECASTS_TABLE_NAME}
        WHERE  stock_symbol = %s
        ORDER  BY forecast_date
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (stock_symbol,))
            return [dict(row) for row in cur.fetchall()]


def insert_forecast(
    stock_symbol: str,
    forecast_date: str,
    current_price: float,
    predicted_price: float,
    confidence: Optional[float] = None,
    analyst_rating: Optional[str] = None,
    key_factors: Optional[str] = None,
) -> str:
    """Insert a forecast row and return its UUID."""
    sql = f"""
        INSERT INTO {FORECASTS_TABLE_NAME}
            (stock_symbol, forecast_date, current_price, predicted_price,
             confidence, analyst_rating, key_factors)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                stock_symbol, forecast_date, current_price, predicted_price,
                confidence, analyst_rating, key_factors,
            ))
            return cur.fetchone()[0]

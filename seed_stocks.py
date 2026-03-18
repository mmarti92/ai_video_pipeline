"""
Seed the pipeline_videos_stocks_ia table with a default set of stock symbols.

Usage
-----
    python seed_stocks.py [--symbols AAPL MSFT GOOG ...]

If no symbols are provided the script inserts the DEFAULT_SYMBOLS list.
Symbols whose rows already exist (any status) are skipped to avoid duplicates.
"""

from __future__ import annotations

import argparse
import logging
import sys

import config
import database

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS: list[tuple[str, str]] = [
    ("AAPL", "Apple Inc. Weekly Analysis"),
    ("MSFT", "Microsoft Corporation Weekly Analysis"),
    ("GOOG", "Alphabet Inc. Weekly Analysis"),
    ("AMZN", "Amazon.com Inc. Weekly Analysis"),
    ("NVDA", "NVIDIA Corporation Weekly Analysis"),
    ("TSLA", "Tesla Inc. Weekly Analysis"),
    ("META", "Meta Platforms Inc. Weekly Analysis"),
    ("NFLX", "Netflix Inc. Weekly Analysis"),
]


def seed(symbols: list[tuple[str, str]]) -> None:
    """Insert pending jobs for each (symbol, title) pair that is not already present."""
    database.init_db(config.PG_CONNECTION_STRING, crdb_ca_cert_url=config.CRDB_CA_CERT_URL)
    inserted = 0
    skipped = 0
    try:
        for symbol, title in symbols:
            if _job_exists(symbol):
                logger.info("Skipping '%s' — a job already exists.", symbol)
                skipped += 1
                continue
            job_id = database.insert_job(stock_symbol=symbol, title=title)
            logger.info("Inserted job for %s (id=%s).", symbol, job_id)
            inserted += 1
    finally:
        database.close_db()

    logger.info("Done. Inserted %d job(s), skipped %d.", inserted, skipped)


def _job_exists(stock_symbol: str) -> bool:
    """Return True if at least one row exists for this stock symbol."""
    # TABLE_NAME is a module-level constant defined in database.py, not user input,
    # so embedding it directly in the query string is safe here.
    sql = f"""
        SELECT 1 FROM {database.TABLE_NAME}
        WHERE stock_symbol = %s
        LIMIT 1
    """
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (stock_symbol,))
            return cur.fetchone() is not None


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )

    parser = argparse.ArgumentParser(description="Seed pipeline stock jobs")
    parser.add_argument(
        "--symbols",
        nargs="+",
        metavar="SYMBOL",
        help="Ticker symbols to seed (default: a curated list of popular stocks).",
    )
    args = parser.parse_args()

    if args.symbols:
        symbols = [(s.upper(), f"{s.upper()} Stock Analysis") for s in args.symbols]
    else:
        symbols = DEFAULT_SYMBOLS

    seed(symbols)


if __name__ == "__main__":
    main()

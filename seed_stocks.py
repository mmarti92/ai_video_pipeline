"""
Seed the pipeline_videos_stocks_ia table with a default set of stock symbols,
and the asset_forecasts table with sample forecast data.

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
from datetime import date, timedelta

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

# Base prices and forecast parameters for each symbol.
# (base_price, daily_drift, predicted_delta, confidence, rating, key_factors)
_FORECAST_PARAMS: dict[str, tuple[float, float, float, float, str, str]] = {
    "AAPL": (178.50, 1.2, 16.70, 0.82, "buy",
             "Strong iPhone sales, Services revenue growth, AI integration momentum"),
    "MSFT": (415.30, 1.5, 24.50, 0.85, "buy",
             "Azure cloud growth, Copilot AI adoption, Enterprise spending recovery"),
    "GOOG": (155.80, 0.9, 12.40, 0.78, "buy",
             "Search ad revenue strength, Cloud momentum, Gemini AI expansion"),
    "AMZN": (186.20, 1.1, 15.80, 0.80, "buy",
             "AWS growth acceleration, Retail margin improvement, Advertising revenue"),
    "NVDA": (875.50, 3.5, 65.00, 0.88, "buy",
             "Data-center GPU demand, AI training infrastructure, Blackwell chip ramp"),
    "TSLA": (172.40, 2.8, -8.50, 0.62, "hold",
             "EV price competition, Robotaxi timeline uncertainty, Energy storage growth"),
    "META": (505.60, 1.8, 30.20, 0.79, "buy",
             "Reels monetisation, Reality Labs progress, AI-driven ad targeting"),
    "NFLX": (628.90, 1.4, 22.10, 0.76, "hold",
             "Subscriber growth slowdown, Ad-tier traction, Content cost discipline"),
}


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

        # Seed forecast data for all symbols.
        forecast_count = _seed_forecasts([s for s, _ in symbols])
        logger.info("Seeded %d forecast row(s).", forecast_count)
    finally:
        database.close_db()

    logger.info("Done. Inserted %d job(s), skipped %d.", inserted, skipped)


def _seed_forecasts(symbols: list[str]) -> int:
    """Insert 7-day forecast data for each symbol that lacks forecasts."""
    inserted = 0
    today = date.today()
    for symbol in symbols:
        if _forecast_exists(symbol):
            logger.info("Skipping forecasts for '%s' — data already exists.", symbol)
            continue

        params = _FORECAST_PARAMS.get(symbol)
        if params is None:
            # Generate generic parameters for unknown symbols.
            params = (100.0, 1.0, 5.0, 0.70, "hold", "General market conditions")

        base_price, drift, pred_delta, confidence, rating, factors = params
        price = base_price
        for day_offset in range(7):
            forecast_date = today - timedelta(days=6 - day_offset)
            # Simulate a realistic daily price walk.
            price += drift * (1 if day_offset % 2 == 0 else -0.5)
            predicted = base_price + pred_delta
            database.insert_forecast(
                stock_symbol=symbol,
                forecast_date=str(forecast_date),
                current_price=round(price, 2),
                predicted_price=round(predicted, 2),
                confidence=confidence,
                analyst_rating=rating,
                key_factors=factors,
            )
            inserted += 1
    return inserted


def _forecast_exists(stock_symbol: str) -> bool:
    """Return True if forecasts already exist for this stock symbol."""
    sql = f"""
        SELECT 1 FROM {database.FORECASTS_TABLE_NAME}
        WHERE stock_symbol = %s
        LIMIT 1
    """
    with database.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (stock_symbol,))
            return cur.fetchone() is not None


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

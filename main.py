"""
Entry point for the AI video pipeline.

Usage
-----
    # Run one batch and exit
    python main.py

    # Run continuously, polling for new jobs
    python main.py --continuous

    # Insert a test job and exit (useful for local testing)
    python main.py --seed AAPL "Apple Inc. Weekly Analysis"
"""

from __future__ import annotations

import argparse
import logging
import sys

import config
import database
import pipeline


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


def main() -> None:
    _configure_logging()

    parser = argparse.ArgumentParser(description="AI Video Pipeline")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--continuous",
        action="store_true",
        help="Poll for new jobs continuously instead of running once.",
    )
    group.add_argument(
        "--seed",
        nargs="+",
        metavar=("SYMBOL", "TITLE"),
        help="Insert a new pending job (SYMBOL required, TITLE optional) and exit.",
    )
    args = parser.parse_args()

    database.init_db(config.PG_CONNECTION_STRING, crdb_ca_cert_url=config.CRDB_CA_CERT_URL)

    try:
        if args.seed:
            symbol = args.seed[0]
            title = " ".join(args.seed[1:]) or None
            job_id = database.insert_job(stock_symbol=symbol, title=title)
            logging.getLogger(__name__).info(
                "Inserted new job for %s (id=%s).", symbol, job_id
            )
        elif args.continuous:
            pipeline.run_continuous()
        else:
            pipeline.run_once()
    finally:
        database.close_db()


if __name__ == "__main__":
    main()

"""
Unit tests for seed_stocks.py

All database calls are mocked — no real database needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call


class TestSeed:
    def test_inserts_new_symbols(self):
        """Each symbol that does not yet exist should be inserted."""
        import seed_stocks
        import database

        symbols = [("AAPL", "Apple Analysis"), ("MSFT", "Microsoft Analysis")]

        with (
            patch.object(database, "init_db"),
            patch.object(database, "close_db"),
            patch("seed_stocks._job_exists", return_value=False),
            patch.object(database, "insert_job", return_value="new-uuid") as mock_insert,
        ):
            seed_stocks.seed(symbols)

        assert mock_insert.call_count == 2
        mock_insert.assert_any_call(stock_symbol="AAPL", title="Apple Analysis")
        mock_insert.assert_any_call(stock_symbol="MSFT", title="Microsoft Analysis")

    def test_skips_existing_symbols(self):
        """Symbols that already have a row in the DB must be skipped."""
        import seed_stocks
        import database

        symbols = [("AAPL", "Apple Analysis")]

        with (
            patch.object(database, "init_db"),
            patch.object(database, "close_db"),
            patch("seed_stocks._job_exists", return_value=True),
            patch.object(database, "insert_job") as mock_insert,
        ):
            seed_stocks.seed(symbols)

        mock_insert.assert_not_called()

    def test_partial_skip(self):
        """Some symbols exist, others don't — only new ones are inserted."""
        import seed_stocks
        import database

        symbols = [("AAPL", "Apple"), ("NVDA", "NVIDIA"), ("GOOG", "Google")]
        existing = {"AAPL"}

        def job_exists(symbol):
            return symbol in existing

        with (
            patch.object(database, "init_db"),
            patch.object(database, "close_db"),
            patch("seed_stocks._job_exists", side_effect=job_exists),
            patch.object(database, "insert_job", return_value="uuid") as mock_insert,
        ):
            seed_stocks.seed(symbols)

        assert mock_insert.call_count == 2
        inserted_symbols = [c.kwargs["stock_symbol"] for c in mock_insert.call_args_list]
        assert "NVDA" in inserted_symbols
        assert "GOOG" in inserted_symbols
        assert "AAPL" not in inserted_symbols

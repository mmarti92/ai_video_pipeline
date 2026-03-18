"""
Unit tests for the database module.

All database calls are mocked so these tests run without a real database.
"""

from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_pool(rows=None):
    """Return a mock ThreadedConnectionPool whose cursors yield *rows*."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchall.return_value = rows or []
    mock_cursor.fetchone.return_value = ("test-uuid",)

    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor

    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    return mock_pool, mock_conn, mock_cursor


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_init_db_creates_pool_and_table(self):
        import database
        mock_pool, mock_conn, mock_cursor = _make_mock_pool()
        with patch("database.ThreadedConnectionPool", return_value=mock_pool):
            database._pool = None
            database.init_db("postgresql://test/db")
            assert database._pool is mock_pool
            # Ensure a CREATE TABLE statement was executed
            executed_sqls = [
                str(c.args[0]) for c in mock_cursor.execute.call_args_list
            ]
            assert any("CREATE TABLE" in sql.upper() for sql in executed_sqls)


class TestFetchPendingJobs:
    def test_returns_list_of_dicts(self):
        import database
        fake_row = {"id": "abc", "stock_symbol": "AAPL", "title": None, "description": None}
        mock_pool, mock_conn, mock_cursor = _make_mock_pool(rows=[fake_row])
        mock_cursor.fetchall.return_value = [fake_row]
        # RealDictCursor rows need to behave like dicts
        database._pool = mock_pool
        result = database.fetch_pending_jobs(limit=5)
        assert isinstance(result, list)
        mock_cursor.execute.assert_called_once()
        # Limit value should be passed as a parameter
        assert mock_cursor.execute.call_args.args[1] == (5,)


class TestMarkFunctions:
    def setup_method(self):
        import database
        self.db = database
        self.mock_pool, self.mock_conn, self.mock_cursor = _make_mock_pool()
        self.db._pool = self.mock_pool

    def test_mark_processing(self):
        self.db.mark_processing("job-1")
        sql, params = self.mock_cursor.execute.call_args.args
        assert "processing" in sql.lower()
        assert params == ("job-1",)

    def test_mark_completed(self):
        self.db.mark_completed("job-2", "/output/job-2.mp4")
        sql, params = self.mock_cursor.execute.call_args.args
        assert "completed" in sql.lower()
        assert params == ("/output/job-2.mp4", "job-2")

    def test_mark_failed(self):
        self.db.mark_failed("job-3", "Some error")
        sql, params = self.mock_cursor.execute.call_args.args
        assert "failed" in sql.lower()
        assert params == ("Some error", "job-3")


class TestInsertJob:
    def test_insert_returns_uuid(self):
        import database
        mock_pool, mock_conn, mock_cursor = _make_mock_pool()
        mock_cursor.fetchone.return_value = ("new-uuid",)
        database._pool = mock_pool
        result = database.insert_job("TSLA", "Tesla Analysis")
        assert result == "new-uuid"
        sql, params = mock_cursor.execute.call_args.args
        assert "INSERT" in sql.upper()
        assert params[0] == "TSLA"
        assert params[1] == "Tesla Analysis"

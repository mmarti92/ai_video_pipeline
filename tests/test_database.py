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
            # Ensure CREATE TABLE statements were executed for both tables
            executed_sqls = [
                str(c.args[0]) for c in mock_cursor.execute.call_args_list
            ]
            assert any("CREATE TABLE" in sql.upper() for sql in executed_sqls)
            assert any("asset_forecasts" in sql for sql in executed_sqls)


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


class TestFetchForecasts:
    def test_returns_list_of_dicts(self):
        import database
        fake_row = {
            "stock_symbol": "AAPL",
            "forecast_date": "2026-03-18",
            "current_price": 178.50,
            "predicted_price": 195.20,
            "confidence": 0.82,
            "analyst_rating": "buy",
            "key_factors": "Strong sales",
        }
        mock_pool, mock_conn, mock_cursor = _make_mock_pool(rows=[fake_row])
        mock_cursor.fetchall.return_value = [fake_row]
        database._pool = mock_pool
        result = database.fetch_forecasts("AAPL")
        assert isinstance(result, list)
        mock_cursor.execute.assert_called_once()
        assert mock_cursor.execute.call_args.args[1] == ("AAPL",)

    def test_returns_empty_list_when_no_rows(self):
        import database
        mock_pool, mock_conn, mock_cursor = _make_mock_pool(rows=[])
        database._pool = mock_pool
        result = database.fetch_forecasts("UNKNOWN")
        assert result == []


class TestInsertForecast:
    def test_insert_returns_uuid(self):
        import database
        mock_pool, mock_conn, mock_cursor = _make_mock_pool()
        mock_cursor.fetchone.return_value = ("forecast-uuid",)
        database._pool = mock_pool
        result = database.insert_forecast(
            stock_symbol="AAPL",
            forecast_date="2026-03-18",
            current_price=178.50,
            predicted_price=195.20,
            confidence=0.82,
            analyst_rating="buy",
            key_factors="Strong sales",
        )
        assert result == "forecast-uuid"
        sql, params = mock_cursor.execute.call_args.args
        assert "INSERT" in sql.upper()
        assert "asset_forecasts" in sql
        assert params[0] == "AAPL"


# ---------------------------------------------------------------------------
# SSL root certificate helper tests
# ---------------------------------------------------------------------------

class TestEnsureSslRootCert:
    """Tests for _ensure_sslrootcert() and _find_ca_bundle()."""

    DSN_VERIFY_FULL = (
        "postgresql://u:p@host:26257/db?sslmode=verify-full"
    )
    DSN_VERIFY_CA = (
        "postgresql://u:p@host:26257/db?sslmode=verify-ca"
    )
    DSN_REQUIRE = "postgresql://u:p@host:26257/db?sslmode=require"
    DSN_NO_SSL = "postgresql://u:p@host:26257/db"

    def test_noop_when_sslmode_not_verify(self):
        import database
        assert database._ensure_sslrootcert(self.DSN_REQUIRE) == self.DSN_REQUIRE
        assert database._ensure_sslrootcert(self.DSN_NO_SSL) == self.DSN_NO_SSL

    def test_noop_when_sslrootcert_already_present(self):
        import database
        dsn = self.DSN_VERIFY_FULL + "&sslrootcert=/custom/ca.crt"
        assert database._ensure_sslrootcert(dsn) == dsn

    def test_noop_when_default_root_cert_exists(self):
        import database
        with patch("os.path.isfile", return_value=True):
            assert database._ensure_sslrootcert(self.DSN_VERIFY_FULL) == self.DSN_VERIFY_FULL

    def test_appends_ca_bundle_for_verify_full(self):
        import database
        with (
            patch("os.path.isfile", side_effect=lambda p: p == "/etc/ssl/certs/ca-certificates.crt"),
            patch.object(database, "_DEFAULT_ROOT_CERT", "/nonexistent/.postgresql/root.crt"),
        ):
            result = database._ensure_sslrootcert(self.DSN_VERIFY_FULL)
            assert "sslrootcert=" in result
            assert "/etc/ssl/certs/ca-certificates.crt" in result

    def test_appends_ca_bundle_for_verify_ca(self):
        import database
        with (
            patch("os.path.isfile", side_effect=lambda p: p == "/etc/ssl/certs/ca-certificates.crt"),
            patch.object(database, "_DEFAULT_ROOT_CERT", "/nonexistent/.postgresql/root.crt"),
        ):
            result = database._ensure_sslrootcert(self.DSN_VERIFY_CA)
            assert "sslrootcert=" in result

    def test_returns_unchanged_when_no_ca_bundle_found(self):
        import database
        with (
            patch("os.path.isfile", return_value=False),
            patch.object(database, "_DEFAULT_ROOT_CERT", "/nonexistent/.postgresql/root.crt"),
            patch.dict(sys.modules, {"certifi": None}),
        ):
            result = database._ensure_sslrootcert(self.DSN_VERIFY_FULL)
            assert result == self.DSN_VERIFY_FULL

    def test_downloads_cert_when_url_provided(self):
        import database
        with (
            patch.object(database, "_DEFAULT_ROOT_CERT", "/nonexistent/.postgresql/root.crt"),
            patch.object(database, "_download_crdb_cert", return_value="/nonexistent/.postgresql/root.crt") as mock_dl,
        ):
            result = database._ensure_sslrootcert(
                self.DSN_VERIFY_FULL,
                crdb_ca_cert_url="https://example.com/cert",
            )
            mock_dl.assert_called_once_with("https://example.com/cert")
            # Returns unchanged DSN (libpq will find the downloaded cert).
            assert result == self.DSN_VERIFY_FULL

    def test_falls_back_to_ca_bundle_when_download_fails(self):
        import database
        with (
            patch.object(database, "_DEFAULT_ROOT_CERT", "/nonexistent/.postgresql/root.crt"),
            patch.object(database, "_download_crdb_cert", return_value=None),
            patch("os.path.isfile", side_effect=lambda p: p == "/etc/ssl/certs/ca-certificates.crt"),
        ):
            result = database._ensure_sslrootcert(
                self.DSN_VERIFY_FULL,
                crdb_ca_cert_url="https://example.com/cert",
            )
            assert "sslrootcert=" in result
            assert "/etc/ssl/certs/ca-certificates.crt" in result

    def test_find_ca_bundle_returns_first_match(self):
        import database
        with patch("os.path.isfile", side_effect=lambda p: p == "/etc/pki/tls/certs/ca-bundle.crt"):
            assert database._find_ca_bundle() == "/etc/pki/tls/certs/ca-bundle.crt"

    def test_find_ca_bundle_falls_back_to_certifi(self):
        import database
        fake_certifi = types.ModuleType("certifi")
        fake_certifi.where = lambda: "/certifi/cacert.pem"
        with (
            patch("os.path.isfile", return_value=False),
            patch.dict(sys.modules, {"certifi": fake_certifi}),
        ):
            assert database._find_ca_bundle() == "/certifi/cacert.pem"

    def test_find_ca_bundle_returns_none_when_nothing_available(self):
        import database
        with (
            patch("os.path.isfile", return_value=False),
            patch.dict(sys.modules, {"certifi": None}),
        ):
            assert database._find_ca_bundle() is None


class TestDownloadCrdbCert:
    """Tests for _download_crdb_cert()."""

    def test_skips_download_if_file_exists(self):
        import database
        with patch("os.path.isfile", return_value=True):
            result = database._download_crdb_cert("https://example.com/cert")
            assert result == database._DEFAULT_ROOT_CERT

    def test_downloads_cert_on_success(self):
        import database
        mock_resp = MagicMock()
        mock_resp.content = b"-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----"
        mock_resp.raise_for_status = MagicMock()
        with (
            patch("os.path.isfile", return_value=False),
            patch("os.makedirs"),
            patch("database.requests.get", return_value=mock_resp) as mock_get,
            patch("builtins.open", MagicMock()),
        ):
            result = database._download_crdb_cert("https://example.com/cert")
            mock_get.assert_called_once_with("https://example.com/cert", timeout=30)
            assert result == database._DEFAULT_ROOT_CERT

    def test_returns_none_on_http_error(self):
        import database
        with (
            patch("os.path.isfile", return_value=False),
            patch("os.makedirs"),
            patch("database.requests.get", side_effect=Exception("network error")),
        ):
            result = database._download_crdb_cert("https://example.com/cert")
            assert result is None

    def test_rejects_non_https_url(self):
        import database
        with patch("os.path.isfile", return_value=False):
            result = database._download_crdb_cert("http://example.com/cert")
            assert result is None

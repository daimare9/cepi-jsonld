"""Tests for native adapters (v1.1) — Google Sheets, Snowflake, BigQuery,
Databricks, Canvas, OneRoster, and PowerSchool/Blackbaud factory functions.

These adapters wrap external cloud/SaaS services that require live
credentials, so we mock the third-party library objects at the adapter
boundary.  This is the correct use of mocks per project testing rules:
"Mocks are only acceptable for true external services — live APIs with
auth tokens, production databases, Azure Cosmos DB endpoints".

We test:
- Constructor validation (required args, mutual exclusion, etc.)
- Import-failure paths (friendly error when optional dep missing)
- read() / read_batch() / count() with mock connectors
- Factory function wiring (PowerSchool, Blackbaud)
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ceds_jsonld.adapters.api_adapter import APIAdapter
from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError

# ===================================================================
# SAMPLE DATA shared across tests
# ===================================================================

SAMPLE_ROWS = [
    {"FirstName": "Alice", "LastName": "Smith", "Grade": "10"},
    {"FirstName": "Bob", "LastName": "Jones", "Grade": "11"},
    {"FirstName": "Carol", "LastName": "Lee", "Grade": "12"},
]


# ===================================================================
# GoogleSheetsAdapter
# ===================================================================


class TestGoogleSheetsAdapter:
    """Tests for GoogleSheetsAdapter."""

    def test_is_source_adapter(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        assert issubclass(GoogleSheetsAdapter, SourceAdapter)

    def test_empty_spreadsheet_raises(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        with pytest.raises(AdapterError, match="spreadsheet identifier must not be empty"):
            GoogleSheetsAdapter("", service_account_file="key.json")

    def test_no_auth_raises(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        with pytest.raises(AdapterError, match="No authentication provided"):
            GoogleSheetsAdapter("My Sheet")

    def test_multiple_auth_raises(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        with pytest.raises(AdapterError, match="Multiple authentication methods"):
            GoogleSheetsAdapter(
                "My Sheet",
                service_account_file="key.json",
                api_key="abc",
            )

    def test_read_yields_dicts(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        adapter = GoogleSheetsAdapter("My Sheet", api_key="test_key")

        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = SAMPLE_ROWS

        mock_sheet = MagicMock()
        mock_sheet.get_worksheet.return_value = mock_ws

        mock_client = MagicMock()
        mock_client.open.return_value = mock_sheet

        mock_gspread = MagicMock()
        mock_gspread.api_key.return_value = mock_client
        mock_gspread.exceptions.SpreadsheetNotFound = type("SpreadsheetNotFound", (Exception,), {})

        with patch.object(adapter, "_import_gspread", return_value=mock_gspread):
            rows = list(adapter.read())

        assert rows == SAMPLE_ROWS
        assert len(rows) == 3

    def test_read_by_url(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        adapter = GoogleSheetsAdapter(
            "https://docs.google.com/spreadsheets/d/abc123",
            api_key="test",
        )

        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = [SAMPLE_ROWS[0]]
        mock_sheet = MagicMock()
        mock_sheet.get_worksheet.return_value = mock_ws
        mock_client = MagicMock()
        mock_client.open_by_url.return_value = mock_sheet
        mock_gspread = MagicMock()
        mock_gspread.api_key.return_value = mock_client
        mock_gspread.exceptions.SpreadsheetNotFound = type("SNF", (Exception,), {})

        with patch.object(adapter, "_import_gspread", return_value=mock_gspread):
            rows = list(adapter.read())

        mock_client.open_by_url.assert_called_once()
        assert len(rows) == 1

    def test_read_by_key(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        # 44-character spreadsheet key (no spaces)
        key = "a" * 44
        adapter = GoogleSheetsAdapter(key, api_key="test")

        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = SAMPLE_ROWS
        mock_sheet = MagicMock()
        mock_sheet.get_worksheet.return_value = mock_ws
        mock_client = MagicMock()
        mock_client.open_by_key.return_value = mock_sheet
        mock_gspread = MagicMock()
        mock_gspread.api_key.return_value = mock_client
        mock_gspread.exceptions.SpreadsheetNotFound = type("SNF", (Exception,), {})

        with patch.object(adapter, "_import_gspread", return_value=mock_gspread):
            rows = list(adapter.read())

        mock_client.open_by_key.assert_called_once_with(key)
        assert len(rows) == 3

    def test_worksheet_by_name(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        adapter = GoogleSheetsAdapter("Sheet", worksheet="Students", api_key="k")

        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = SAMPLE_ROWS
        mock_sheet = MagicMock()
        mock_sheet.worksheet.return_value = mock_ws
        mock_client = MagicMock()
        mock_client.open.return_value = mock_sheet
        mock_gspread = MagicMock()
        mock_gspread.api_key.return_value = mock_client
        mock_gspread.exceptions.SpreadsheetNotFound = type("SNF", (Exception,), {})

        with patch.object(adapter, "_import_gspread", return_value=mock_gspread):
            rows = list(adapter.read())

        mock_sheet.worksheet.assert_called_once_with("Students")
        assert len(rows) == 3

    def test_count_returns_int(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        adapter = GoogleSheetsAdapter("Sheet", api_key="k")

        mock_ws = MagicMock()
        mock_ws.row_count = 101  # 100 data rows + 1 header
        mock_sheet = MagicMock()
        mock_sheet.get_worksheet.return_value = mock_ws
        mock_client = MagicMock()
        mock_client.open.return_value = mock_sheet
        mock_gspread = MagicMock()
        mock_gspread.api_key.return_value = mock_client
        mock_gspread.exceptions.SpreadsheetNotFound = type("SNF", (Exception,), {})

        with patch.object(adapter, "_import_gspread", return_value=mock_gspread):
            assert adapter.count() == 100

    def test_missing_gspread_raises(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        adapter = GoogleSheetsAdapter("Sheet", api_key="k")
        with patch.dict(sys.modules, {"gspread": None}), pytest.raises(AdapterError, match="gspread is required"):
            list(adapter.read())

    def test_service_account_auth(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        adapter = GoogleSheetsAdapter("Sheet", service_account_file="sa.json")

        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = SAMPLE_ROWS
        mock_sheet = MagicMock()
        mock_sheet.get_worksheet.return_value = mock_ws
        mock_client = MagicMock()
        mock_client.open.return_value = mock_sheet
        mock_gspread = MagicMock()
        mock_gspread.service_account.return_value = mock_client
        mock_gspread.exceptions.SpreadsheetNotFound = type("SNF", (Exception,), {})

        with patch.object(adapter, "_import_gspread", return_value=mock_gspread):
            rows = list(adapter.read())

        mock_gspread.service_account.assert_called_once_with(filename="sa.json")
        assert len(rows) == 3

    def test_credentials_auth(self) -> None:
        from ceds_jsonld.adapters.google_sheets_adapter import GoogleSheetsAdapter

        mock_creds = MagicMock()
        adapter = GoogleSheetsAdapter("Sheet", credentials=mock_creds)

        mock_ws = MagicMock()
        mock_ws.get_all_records.return_value = SAMPLE_ROWS
        mock_sheet = MagicMock()
        mock_sheet.get_worksheet.return_value = mock_ws
        mock_client = MagicMock()
        mock_client.open.return_value = mock_sheet
        mock_gspread = MagicMock()
        mock_gspread.authorize.return_value = mock_client
        mock_gspread.exceptions.SpreadsheetNotFound = type("SNF", (Exception,), {})

        with patch.object(adapter, "_import_gspread", return_value=mock_gspread):
            rows = list(adapter.read())

        mock_gspread.authorize.assert_called_once_with(mock_creds)
        assert len(rows) == 3


# ===================================================================
# SnowflakeAdapter
# ===================================================================


class TestSnowflakeAdapter:
    """Tests for SnowflakeAdapter."""

    def test_is_source_adapter(self) -> None:
        from ceds_jsonld.adapters.snowflake_adapter import SnowflakeAdapter

        assert issubclass(SnowflakeAdapter, SourceAdapter)

    def test_empty_query_raises(self) -> None:
        from ceds_jsonld.adapters.snowflake_adapter import SnowflakeAdapter

        with pytest.raises(AdapterError, match="query must not be empty"):
            SnowflakeAdapter("", account="org-acct")

    def test_empty_account_raises(self) -> None:
        from ceds_jsonld.adapters.snowflake_adapter import SnowflakeAdapter

        with pytest.raises(AdapterError, match="account must not be empty"):
            SnowflakeAdapter("SELECT 1", account="")

    def test_read_yields_dicts(self) -> None:
        from ceds_jsonld.adapters.snowflake_adapter import SnowflakeAdapter

        adapter = SnowflakeAdapter(
            "SELECT * FROM students",
            account="org-acct",
            user="u",
            password="p",
        )

        mock_cursor = MagicMock()
        mock_cursor.__iter__ = MagicMock(return_value=iter(SAMPLE_ROWS))
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_sf = MagicMock()
        mock_sf.DictCursor = "DictCursor"
        mock_sf.connect.return_value = mock_conn

        with patch.object(adapter, "_import_snowflake", return_value=mock_sf):
            rows = list(adapter.read())

        assert rows == SAMPLE_ROWS
        mock_conn.cursor.assert_called_once_with("DictCursor")
        mock_cursor.execute.assert_called_once_with("SELECT * FROM students", {})
        mock_conn.close.assert_called_once()

    def test_read_batch_yields_chunks(self) -> None:
        from ceds_jsonld.adapters.snowflake_adapter import SnowflakeAdapter

        adapter = SnowflakeAdapter("SELECT 1", account="org-acct", user="u", password="p")

        mock_cursor = MagicMock()
        mock_cursor.fetchmany.side_effect = [SAMPLE_ROWS[:2], SAMPLE_ROWS[2:], []]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_sf = MagicMock()
        mock_sf.DictCursor = "DC"
        mock_sf.connect.return_value = mock_conn

        with patch.object(adapter, "_import_snowflake", return_value=mock_sf):
            batches = list(adapter.read_batch(batch_size=2))

        assert len(batches) == 2
        assert batches[0] == SAMPLE_ROWS[:2]
        assert batches[1] == SAMPLE_ROWS[2:]

    def test_count_returns_none(self) -> None:
        from ceds_jsonld.adapters.snowflake_adapter import SnowflakeAdapter

        adapter = SnowflakeAdapter("SELECT 1", account="org-acct", user="u", password="p")
        assert adapter.count() is None

    def test_missing_lib_raises(self) -> None:
        from ceds_jsonld.adapters.snowflake_adapter import SnowflakeAdapter

        adapter = SnowflakeAdapter("SELECT 1", account="org-acct", user="u", password="p")
        with (
            patch.dict(sys.modules, {"snowflake": None, "snowflake.connector": None}),
            pytest.raises(AdapterError, match="snowflake-connector-python is required"),
        ):
            list(adapter.read())

    def test_connection_params_forwarded(self) -> None:
        from ceds_jsonld.adapters.snowflake_adapter import SnowflakeAdapter

        adapter = SnowflakeAdapter(
            "SELECT 1",
            account="org-acct",
            user="etl",
            warehouse="wh",
            database="db",
            schema="public",
            role="reader",
        )

        mock_sf = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = MagicMock(return_value=iter([]))
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sf.connect.return_value = mock_conn

        with patch.object(adapter, "_import_snowflake", return_value=mock_sf):
            list(adapter.read())

        call_kwargs = mock_sf.connect.call_args[1]
        assert call_kwargs["account"] == "org-acct"
        assert call_kwargs["user"] == "etl"
        assert call_kwargs["warehouse"] == "wh"
        assert call_kwargs["database"] == "db"
        assert call_kwargs["schema"] == "public"
        assert call_kwargs["role"] == "reader"


# ===================================================================
# BigQueryAdapter
# ===================================================================


class TestBigQueryAdapter:
    """Tests for BigQueryAdapter."""

    def test_is_source_adapter(self) -> None:
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        assert issubclass(BigQueryAdapter, SourceAdapter)

    def test_no_query_or_table_raises(self) -> None:
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        with pytest.raises(AdapterError, match="Provide either 'query'"):
            BigQueryAdapter()

    def test_both_query_and_table_raises(self) -> None:
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        with pytest.raises(AdapterError, match="not both"):
            BigQueryAdapter(query="SELECT 1", table="proj.ds.tbl")

    def test_read_query_mode(self) -> None:
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(query="SELECT * FROM tbl", project="p")

        # Mock Row objects that support dict(row)
        mock_rows = []
        for row in SAMPLE_ROWS:
            mock_row = MagicMock()
            mock_row.keys.return_value = row.keys()
            mock_row.__iter__ = MagicMock(return_value=iter(row.items()))
            mock_row.items.return_value = row.items()
            # Make dict(mock_row) work
            type(mock_row).__iter__ = lambda self: iter(dict.fromkeys(SAMPLE_ROWS[0]))
            mock_rows.append(row)  # Just use real dicts for simplicity

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter(mock_rows))

        mock_job = MagicMock()
        mock_job.result.return_value = mock_result

        mock_client = MagicMock()
        mock_client.query.return_value = mock_job

        mock_bq = MagicMock()
        mock_bq.Client.return_value = mock_client
        mock_bq.QueryJobConfig.return_value = MagicMock()
        mock_bq.ScalarQueryParameter = MagicMock()

        with (
            patch.object(adapter, "_import_bigquery", return_value=mock_bq),
            # dict(row) on a real dict returns itself, so this works
            patch.object(adapter, "_get_client", return_value=mock_client),
        ):
            rows = list(adapter.read())

        assert len(rows) == 3

    def test_read_table_mode(self) -> None:
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(table="proj.ds.students")

        mock_rows = MagicMock()
        mock_rows.__iter__ = MagicMock(return_value=iter(SAMPLE_ROWS))

        mock_client = MagicMock()
        mock_client.list_rows.return_value = mock_rows

        mock_bq = MagicMock()
        mock_bq.Client.return_value = mock_client

        with (
            patch.object(adapter, "_import_bigquery", return_value=mock_bq),
            patch.object(adapter, "_get_client", return_value=mock_client),
        ):
            rows = list(adapter.read())

        assert len(rows) == 3
        mock_client.list_rows.assert_called_once_with("proj.ds.students", max_results=None)

    def test_count_table_mode(self) -> None:
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(table="proj.ds.students")

        mock_table = MagicMock()
        mock_table.num_rows = 42

        mock_client = MagicMock()
        mock_client.get_table.return_value = mock_table

        mock_bq = MagicMock()
        mock_bq.Client.return_value = mock_client

        with (
            patch.object(adapter, "_import_bigquery", return_value=mock_bq),
            patch.object(adapter, "_get_client", return_value=mock_client),
        ):
            assert adapter.count() == 42

    def test_count_query_mode_returns_none(self) -> None:
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(query="SELECT 1")
        assert adapter.count() is None

    def test_missing_lib_raises(self) -> None:
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(query="SELECT 1")
        with (
            patch.dict(sys.modules, {"google.cloud": None, "google.cloud.bigquery": None}),
            pytest.raises(AdapterError, match="google-cloud-bigquery is required"),
        ):
            list(adapter.read())

    def test_params_build_job_config(self) -> None:
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(
            query="SELECT * FROM t WHERE grade = @grade AND name = @name",
            params={"grade": 10, "name": "Alice"},
        )

        mock_bq = MagicMock()
        mock_bq.QueryJobConfig.return_value = MagicMock()

        with patch.object(adapter, "_import_bigquery", return_value=mock_bq):
            adapter._build_job_config(mock_bq)

        # Should create ScalarQueryParameter for each param
        assert mock_bq.ScalarQueryParameter.call_count == 2


# ===================================================================
# DatabricksAdapter
# ===================================================================


class TestDatabricksAdapter:
    """Tests for DatabricksAdapter."""

    def test_is_source_adapter(self) -> None:
        from ceds_jsonld.adapters.databricks_adapter import DatabricksAdapter

        assert issubclass(DatabricksAdapter, SourceAdapter)

    def test_empty_query_raises(self) -> None:
        from ceds_jsonld.adapters.databricks_adapter import DatabricksAdapter

        with pytest.raises(AdapterError, match="query must not be empty"):
            DatabricksAdapter("", server_hostname="h", http_path="/p")

    def test_empty_hostname_raises(self) -> None:
        from ceds_jsonld.adapters.databricks_adapter import DatabricksAdapter

        with pytest.raises(AdapterError, match="server_hostname must not be empty"):
            DatabricksAdapter("SELECT 1", server_hostname="", http_path="/p")

    def test_empty_http_path_raises(self) -> None:
        from ceds_jsonld.adapters.databricks_adapter import DatabricksAdapter

        with pytest.raises(AdapterError, match="http_path must not be empty"):
            DatabricksAdapter("SELECT 1", server_hostname="h", http_path="")

    def test_read_yields_dicts(self) -> None:
        from ceds_jsonld.adapters.databricks_adapter import DatabricksAdapter

        adapter = DatabricksAdapter(
            "SELECT * FROM students",
            server_hostname="host",
            http_path="/path",
            access_token="tok",
        )

        # Create mock Row objects with asDict()
        mock_rows = []
        for row in SAMPLE_ROWS:
            mock_row = MagicMock()
            mock_row.asDict.return_value = row
            mock_rows.append(mock_row)

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_sql = MagicMock()
        mock_sql.connect.return_value = mock_conn

        with patch.object(adapter, "_import_databricks", return_value=mock_sql):
            rows = list(adapter.read())

        assert rows == SAMPLE_ROWS
        mock_cursor.execute.assert_called_once_with("SELECT * FROM students", None)

    def test_read_batch_yields_chunks(self) -> None:
        from ceds_jsonld.adapters.databricks_adapter import DatabricksAdapter

        adapter = DatabricksAdapter(
            "SELECT 1",
            server_hostname="h",
            http_path="/p",
            access_token="t",
        )

        mock_row_objs: list[list[MagicMock]] = []
        for chunk in [SAMPLE_ROWS[:2], SAMPLE_ROWS[2:]]:
            batch = []
            for row in chunk:
                mr = MagicMock()
                mr.asDict.return_value = row
                batch.append(mr)
            mock_row_objs.append(batch)

        mock_cursor = MagicMock()
        mock_cursor.fetchmany.side_effect = [mock_row_objs[0], mock_row_objs[1], []]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_sql = MagicMock()
        mock_sql.connect.return_value = mock_conn

        with patch.object(adapter, "_import_databricks", return_value=mock_sql):
            batches = list(adapter.read_batch(batch_size=2))

        assert len(batches) == 2
        assert batches[0] == SAMPLE_ROWS[:2]

    def test_count_returns_none(self) -> None:
        from ceds_jsonld.adapters.databricks_adapter import DatabricksAdapter

        adapter = DatabricksAdapter("SELECT 1", server_hostname="h", http_path="/p", access_token="t")
        assert adapter.count() is None

    def test_missing_lib_raises(self) -> None:
        from ceds_jsonld.adapters.databricks_adapter import DatabricksAdapter

        adapter = DatabricksAdapter("SELECT 1", server_hostname="h", http_path="/p", access_token="t")
        with (
            patch.dict(sys.modules, {"databricks": None, "databricks.sql": None}),
            pytest.raises(AdapterError, match="databricks-sql-connector is required"),
        ):
            list(adapter.read())

    def test_connect_params_forwarded(self) -> None:
        from ceds_jsonld.adapters.databricks_adapter import DatabricksAdapter

        adapter = DatabricksAdapter(
            "SELECT 1",
            server_hostname="host.net",
            http_path="/sql/1.0",
            access_token="dapi_tok",
            catalog="main",
            schema="education",
        )

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        mock_sql = MagicMock()
        mock_sql.connect.return_value = mock_conn

        with patch.object(adapter, "_import_databricks", return_value=mock_sql):
            list(adapter.read())

        call_kwargs = mock_sql.connect.call_args[1]
        assert call_kwargs["server_hostname"] == "host.net"
        assert call_kwargs["http_path"] == "/sql/1.0"
        assert call_kwargs["access_token"] == "dapi_tok"
        assert call_kwargs["catalog"] == "main"
        assert call_kwargs["schema"] == "education"


# ===================================================================
# CanvasAdapter
# ===================================================================


class TestCanvasAdapter:
    """Tests for CanvasAdapter."""

    def test_is_source_adapter(self) -> None:
        from ceds_jsonld.adapters.canvas_adapter import CanvasAdapter

        assert issubclass(CanvasAdapter, SourceAdapter)

    def test_empty_base_url_raises(self) -> None:
        from ceds_jsonld.adapters.canvas_adapter import CanvasAdapter

        with pytest.raises(AdapterError, match="base_url must not be empty"):
            CanvasAdapter("", "key", "users")

    def test_empty_api_key_raises(self) -> None:
        from ceds_jsonld.adapters.canvas_adapter import CanvasAdapter

        with pytest.raises(AdapterError, match="api_key must not be empty"):
            CanvasAdapter("https://school.instructure.com", "", "users")

    def test_invalid_resource_raises(self) -> None:
        from ceds_jsonld.adapters.canvas_adapter import CanvasAdapter

        with pytest.raises(AdapterError, match="Unknown resource 'widgets'"):
            CanvasAdapter("https://school.instructure.com", "key", "widgets")

    def test_course_resource_without_course_id_raises(self) -> None:
        from ceds_jsonld.adapters.canvas_adapter import CanvasAdapter

        with pytest.raises(AdapterError, match="course_id is required"):
            CanvasAdapter("https://school.instructure.com", "key", "enrollments")

    def test_read_account_resource(self) -> None:
        from ceds_jsonld.adapters.canvas_adapter import CanvasAdapter

        adapter = CanvasAdapter(
            "https://school.instructure.com",
            "test_key",
            "users",
            account_id=1,
        )

        # Create mock Canvas objects
        mock_user_objs = []
        for row in SAMPLE_ROWS:
            obj = MagicMock()
            obj.__dict__ = {**row, "_requester": "x", "requester": "x"}
            mock_user_objs.append(obj)

        mock_account = MagicMock()
        mock_account.get_users.return_value = mock_user_objs

        mock_canvas = MagicMock()
        mock_canvas.get_account.return_value = mock_account

        mock_canvasapi = MagicMock()
        mock_canvasapi.Canvas.return_value = mock_canvas

        with patch.object(adapter, "_import_canvasapi", return_value=mock_canvasapi):
            rows = list(adapter.read())

        assert len(rows) == 3
        # Verify requester and private attrs are stripped
        for row in rows:
            assert "requester" not in row
            assert "_requester" not in row

    def test_read_course_resource(self) -> None:
        from ceds_jsonld.adapters.canvas_adapter import CanvasAdapter

        adapter = CanvasAdapter(
            "https://school.instructure.com",
            "key",
            "enrollments",
            course_id=123,
        )

        mock_enrollment = MagicMock()
        mock_enrollment.__dict__ = {"user_id": 1, "course_id": 123, "type": "student"}

        mock_course = MagicMock()
        mock_course.get_enrollments.return_value = [mock_enrollment]

        mock_canvas = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        mock_canvasapi = MagicMock()
        mock_canvasapi.Canvas.return_value = mock_canvas

        with patch.object(adapter, "_import_canvasapi", return_value=mock_canvasapi):
            rows = list(adapter.read())

        assert len(rows) == 1
        assert rows[0]["user_id"] == 1
        mock_canvas.get_course.assert_called_once_with(123)

    def test_count_returns_none(self) -> None:
        from ceds_jsonld.adapters.canvas_adapter import CanvasAdapter

        adapter = CanvasAdapter("https://x.com", "k", "users")
        assert adapter.count() is None

    def test_missing_lib_raises(self) -> None:
        from ceds_jsonld.adapters.canvas_adapter import CanvasAdapter

        adapter = CanvasAdapter("https://x.com", "k", "users")
        with patch.dict(sys.modules, {"canvasapi": None}), pytest.raises(AdapterError, match="canvasapi is required"):
            list(adapter.read())


# ===================================================================
# OneRosterAdapter
# ===================================================================


class TestOneRosterAdapter:
    """Tests for OneRosterAdapter."""

    def test_is_source_adapter(self) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        assert issubclass(OneRosterAdapter, SourceAdapter)

    def test_empty_base_url_raises(self) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        with pytest.raises(AdapterError, match="base_url must not be empty"):
            OneRosterAdapter("", "users", bearer_token="tok")

    def test_invalid_resource_raises(self) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        with pytest.raises(AdapterError, match="Unknown OneRoster resource"):
            OneRosterAdapter("https://sis.example.com", "widgets", bearer_token="tok")

    def test_no_auth_raises(self) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        with pytest.raises(AdapterError, match="No authentication provided"):
            OneRosterAdapter("https://sis.example.com", "users")

    def test_oauth_without_token_url_raises(self) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        with pytest.raises(AdapterError, match="token_url is required"):
            OneRosterAdapter(
                "https://sis.example.com",
                "users",
                client_id="id",
                client_secret="secret",
            )

    def test_read_with_bearer_token(self, httpserver: Any) -> None:
        """Test OneRoster adapter using pytest-httpserver as real HTTP server."""
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        # First page returns 2 records
        httpserver.expect_ordered_request(
            "/users",
            query_string={"offset": "0", "limit": "2"},
        ).respond_with_json(
            {
                "users": [
                    {"sourcedId": "u1", "givenName": "Alice", "familyName": "Smith", "role": "student"},
                    {"sourcedId": "u2", "givenName": "Bob", "familyName": "Jones", "role": "student"},
                ],
            }
        )

        # Second page returns 1 record (less than page_size → stop)
        httpserver.expect_ordered_request(
            "/users",
            query_string={"offset": "2", "limit": "2"},
        ).respond_with_json(
            {
                "users": [
                    {"sourcedId": "u3", "givenName": "Carol", "familyName": "Lee", "role": "teacher"},
                ],
            }
        )

        adapter = OneRosterAdapter(
            base_url=httpserver.url_for(""),
            resource="users",
            bearer_token="test_token",
            page_size=2,
            flatten=False,
        )

        rows = list(adapter.read())
        assert len(rows) == 3
        assert rows[0]["givenName"] == "Alice"
        assert rows[2]["role"] == "teacher"

    def test_read_with_filter(self, httpserver: Any) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        httpserver.expect_ordered_request(
            "/users",
            query_string={"offset": "0", "limit": "100", "filter": "role='student'"},
        ).respond_with_json(
            {
                "users": [
                    {"sourcedId": "u1", "givenName": "Alice", "familyName": "Smith", "role": "student"},
                ],
            }
        )

        adapter = OneRosterAdapter(
            base_url=httpserver.url_for(""),
            resource="users",
            bearer_token="tok",
            filter_expr="role='student'",
            flatten=False,
        )

        rows = list(adapter.read())
        assert len(rows) == 1

    def test_flatten_nested_objects(self, httpserver: Any) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        httpserver.expect_ordered_request("/enrollments").respond_with_json(
            {
                "enrollments": [
                    {
                        "sourcedId": "e1",
                        "user": {"sourcedId": "u1", "givenName": "Alice"},
                        "orgs": [{"sourcedId": "org1", "type": "school"}],
                        "role": "student",
                    },
                ],
            }
        )

        adapter = OneRosterAdapter(
            base_url=httpserver.url_for(""),
            resource="enrollments",
            bearer_token="tok",
            page_size=100,
            flatten=True,
        )

        rows = list(adapter.read())
        assert len(rows) == 1
        row = rows[0]
        # Nested dict should be flattened
        assert row["user_sourcedId"] == "u1"
        assert row["user_givenName"] == "Alice"
        # Nested list should flatten first element
        assert row["org_sourcedId"] == "org1"
        assert row["org_type"] == "school"
        # Scalar fields preserved
        assert row["sourcedId"] == "e1"
        assert row["role"] == "student"

    def test_oauth_client_credentials(self, httpserver: Any) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        # Token endpoint
        httpserver.expect_ordered_request("/oauth/token", method="POST").respond_with_json(
            {
                "access_token": "fresh_token",
                "token_type": "bearer",
            }
        )

        # Data endpoint
        httpserver.expect_ordered_request("/users").respond_with_json(
            {
                "users": [{"sourcedId": "u1", "givenName": "Test"}],
            }
        )

        adapter = OneRosterAdapter(
            base_url=httpserver.url_for(""),
            resource="users",
            client_id="cid",
            client_secret="csecret",
            token_url=httpserver.url_for("/oauth/token"),
            flatten=False,
        )

        rows = list(adapter.read())
        assert len(rows) == 1

    def test_count_returns_none(self) -> None:
        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        adapter = OneRosterAdapter("https://x.com", "users", bearer_token="tok")
        assert adapter.count() is None


# ===================================================================
# PowerSchool Factory
# ===================================================================


class TestPowerSchoolFactory:
    """Tests for powerschool_adapter() factory."""

    def test_returns_api_adapter(self) -> None:
        from ceds_jsonld.adapters.sis_factories import powerschool_adapter

        adapter = powerschool_adapter(
            "https://district.powerschool.com",
            "token123",
            "students",
        )
        assert isinstance(adapter, APIAdapter)

    def test_url_built_correctly(self) -> None:
        from ceds_jsonld.adapters.sis_factories import powerschool_adapter

        adapter = powerschool_adapter(
            "https://district.powerschool.com",
            "token123",
            "staff",
        )
        assert adapter._url == "https://district.powerschool.com/ws/v1/district/staff"

    def test_auth_header_set(self) -> None:
        from ceds_jsonld.adapters.sis_factories import powerschool_adapter

        adapter = powerschool_adapter(
            "https://d.powerschool.com",
            "mytoken",
            "students",
        )
        assert adapter._headers["Authorization"] == "Bearer mytoken"

    def test_empty_base_url_raises(self) -> None:
        from ceds_jsonld.adapters.sis_factories import powerschool_adapter

        with pytest.raises(AdapterError, match="base_url must not be empty"):
            powerschool_adapter("", "token", "students")

    def test_empty_token_raises(self) -> None:
        from ceds_jsonld.adapters.sis_factories import powerschool_adapter

        with pytest.raises(AdapterError, match="access_token must not be empty"):
            powerschool_adapter("https://d.ps.com", "", "students")

    def test_invalid_resource_raises(self) -> None:
        from ceds_jsonld.adapters.sis_factories import powerschool_adapter

        with pytest.raises(AdapterError, match="Unknown PowerSchool resource"):
            powerschool_adapter("https://d.ps.com", "tok", "widgets")

    def test_all_resources_supported(self) -> None:
        from ceds_jsonld.adapters.sis_factories import powerschool_adapter

        for resource in ("students", "staff", "schools", "sections", "enrollments"):
            adapter = powerschool_adapter("https://d.ps.com", "tok", resource)
            assert isinstance(adapter, APIAdapter)

    def test_pagination_configured(self) -> None:
        from ceds_jsonld.adapters.sis_factories import powerschool_adapter

        adapter = powerschool_adapter("https://d.ps.com", "tok", "students")
        assert adapter._pagination == "offset"


# ===================================================================
# Blackbaud Factory
# ===================================================================


class TestBlackbaudFactory:
    """Tests for blackbaud_adapter() factory."""

    def test_returns_api_adapter(self) -> None:
        from ceds_jsonld.adapters.sis_factories import blackbaud_adapter

        adapter = blackbaud_adapter("token", "sub_key", "students")
        assert isinstance(adapter, APIAdapter)

    def test_url_built_correctly(self) -> None:
        from ceds_jsonld.adapters.sis_factories import blackbaud_adapter

        adapter = blackbaud_adapter("tok", "key", "courses")
        assert adapter._url == "https://api.sky.blackbaud.com/school/v1/academics/courses"

    def test_headers_set(self) -> None:
        from ceds_jsonld.adapters.sis_factories import blackbaud_adapter

        adapter = blackbaud_adapter("tok", "subkey", "students")
        assert adapter._headers["Authorization"] == "Bearer tok"
        assert adapter._headers["Bb-Api-Subscription-Key"] == "subkey"

    def test_empty_token_raises(self) -> None:
        from ceds_jsonld.adapters.sis_factories import blackbaud_adapter

        with pytest.raises(AdapterError, match="access_token must not be empty"):
            blackbaud_adapter("", "key", "students")

    def test_empty_subscription_key_raises(self) -> None:
        from ceds_jsonld.adapters.sis_factories import blackbaud_adapter

        with pytest.raises(AdapterError, match="subscription_key must not be empty"):
            blackbaud_adapter("tok", "", "students")

    def test_invalid_resource_raises(self) -> None:
        from ceds_jsonld.adapters.sis_factories import blackbaud_adapter

        with pytest.raises(AdapterError, match="Unknown Blackbaud resource"):
            blackbaud_adapter("tok", "key", "widgets")

    def test_all_resources_supported(self) -> None:
        from ceds_jsonld.adapters.sis_factories import blackbaud_adapter

        for resource in ("users", "students", "sections", "enrollments", "schools", "courses"):
            adapter = blackbaud_adapter("tok", "key", resource)
            assert isinstance(adapter, APIAdapter)

    def test_custom_base_url(self) -> None:
        from ceds_jsonld.adapters.sis_factories import blackbaud_adapter

        adapter = blackbaud_adapter(
            "tok",
            "key",
            "students",
            base_url="https://custom.blackbaud.com",
        )
        assert adapter._url.startswith("https://custom.blackbaud.com/")


# ===================================================================
# Import / Export Tests
# ===================================================================


class TestAdapterImports:
    """Verify all new adapters are importable from the public API."""

    def test_import_from_adapters_package(self) -> None:
        from ceds_jsonld.adapters import (
            BigQueryAdapter,
            CanvasAdapter,
            DatabricksAdapter,
            GoogleSheetsAdapter,
            OneRosterAdapter,
            SnowflakeAdapter,
            blackbaud_adapter,
            powerschool_adapter,
        )

        # All are real classes/functions
        assert callable(GoogleSheetsAdapter)
        assert callable(SnowflakeAdapter)
        assert callable(BigQueryAdapter)
        assert callable(DatabricksAdapter)
        assert callable(CanvasAdapter)
        assert callable(OneRosterAdapter)
        assert callable(powerschool_adapter)
        assert callable(blackbaud_adapter)

    def test_import_from_top_level(self) -> None:
        from ceds_jsonld import (
            BigQueryAdapter,
            CanvasAdapter,
            DatabricksAdapter,
            GoogleSheetsAdapter,
            OneRosterAdapter,
            SnowflakeAdapter,
            blackbaud_adapter,
            powerschool_adapter,
        )

        # Verify all are SourceAdapter subclasses (or functions)
        assert issubclass(GoogleSheetsAdapter, SourceAdapter)
        assert issubclass(SnowflakeAdapter, SourceAdapter)
        assert issubclass(BigQueryAdapter, SourceAdapter)
        assert issubclass(DatabricksAdapter, SourceAdapter)
        assert issubclass(CanvasAdapter, SourceAdapter)
        assert issubclass(OneRosterAdapter, SourceAdapter)
        assert callable(powerschool_adapter)
        assert callable(blackbaud_adapter)

    def test_all_in_dunder_all(self) -> None:
        import ceds_jsonld

        expected = {
            "BigQueryAdapter",
            "CanvasAdapter",
            "DatabricksAdapter",
            "GoogleSheetsAdapter",
            "OneRosterAdapter",
            "SnowflakeAdapter",
            "blackbaud_adapter",
            "powerschool_adapter",
        }
        assert expected.issubset(set(ceds_jsonld.__all__))

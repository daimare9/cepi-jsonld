"""Tests for issues #36 and #40.

#36 — BigQueryAdapter._build_job_config types bool params as INT64 because
      isinstance(value, int) is checked before isinstance(value, bool),
      and bool is a subclass of int in Python.

#40 — (a) BigQueryAdapter accepts whitespace-only queries while
      Snowflake/Databricks/Database adapters properly reject them.
      (b) OneRosterAdapter._fetch_page uses a bare `import httpx` instead
      of the _import_httpx() wrapper, bypassing the friendly error message.
"""

from __future__ import annotations

import pytest

from ceds_jsonld.exceptions import AdapterError

# ======================================================================
# Issue #36 — BigQuery bool params must be typed as BOOL, not INT64
# ======================================================================


class TestBigQueryBoolParamTyping:
    """_build_job_config must check isinstance(value, bool) BEFORE int."""

    def test_bool_param_typed_as_bool(self) -> None:
        """True/False parameters must produce BOOL, not INT64."""
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(
            query="SELECT * FROM t WHERE active = @active",
            project="test-project",
            params={"active": True},
        )

        class MockScalarQueryParameter:
            def __init__(self, name: str, type_: str, value: object) -> None:
                self.name = name
                self.type_ = type_
                self.value = value

        class MockQueryJobConfig:
            def __init__(self, query_parameters: list | None = None) -> None:
                self.query_parameters = query_parameters or []

        class MockBQ:
            ScalarQueryParameter = MockScalarQueryParameter
            QueryJobConfig = MockQueryJobConfig

        config = adapter._build_job_config(MockBQ)
        type_map = {p.name: p.type_ for p in config.query_parameters}

        assert type_map["active"] == "BOOL"

    def test_false_param_typed_as_bool(self) -> None:
        """False value must also produce BOOL."""
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(
            query="SELECT * FROM t WHERE active = @active",
            project="test-project",
            params={"active": False},
        )

        class MockScalarQueryParameter:
            def __init__(self, name: str, type_: str, value: object) -> None:
                self.name = name
                self.type_ = type_
                self.value = value

        class MockQueryJobConfig:
            def __init__(self, query_parameters: list | None = None) -> None:
                self.query_parameters = query_parameters or []

        class MockBQ:
            ScalarQueryParameter = MockScalarQueryParameter
            QueryJobConfig = MockQueryJobConfig

        config = adapter._build_job_config(MockBQ)
        type_map = {p.name: p.type_ for p in config.query_parameters}

        assert type_map["active"] == "BOOL"

    def test_int_param_still_typed_as_int64(self) -> None:
        """Regular int values must still produce INT64."""
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(
            query="SELECT * FROM t WHERE grade = @grade",
            project="test-project",
            params={"grade": 10},
        )

        class MockScalarQueryParameter:
            def __init__(self, name: str, type_: str, value: object) -> None:
                self.name = name
                self.type_ = type_
                self.value = value

        class MockQueryJobConfig:
            def __init__(self, query_parameters: list | None = None) -> None:
                self.query_parameters = query_parameters or []

        class MockBQ:
            ScalarQueryParameter = MockScalarQueryParameter
            QueryJobConfig = MockQueryJobConfig

        config = adapter._build_job_config(MockBQ)
        type_map = {p.name: p.type_ for p in config.query_parameters}

        assert type_map["grade"] == "INT64"

    def test_mixed_bool_int_float_string_params(self) -> None:
        """All four param types must be correctly detected in one call."""
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(
            query="SELECT * FROM t WHERE a=@a AND b=@b AND c=@c AND d=@d",
            project="test-project",
            params={
                "a": True,
                "b": 42,
                "c": 3.14,
                "d": "hello",
            },
        )

        class MockScalarQueryParameter:
            def __init__(self, name: str, type_: str, value: object) -> None:
                self.name = name
                self.type_ = type_
                self.value = value

        class MockQueryJobConfig:
            def __init__(self, query_parameters: list | None = None) -> None:
                self.query_parameters = query_parameters or []

        class MockBQ:
            ScalarQueryParameter = MockScalarQueryParameter
            QueryJobConfig = MockQueryJobConfig

        config = adapter._build_job_config(MockBQ)
        type_map = {p.name: p.type_ for p in config.query_parameters}

        assert type_map == {
            "a": "BOOL",
            "b": "INT64",
            "c": "FLOAT64",
            "d": "STRING",
        }


# ======================================================================
# Issue #40a — BigQuery must reject whitespace-only queries
# ======================================================================


class TestBigQueryWhitespaceQueryValidation:
    """BigQuery must reject whitespace-only queries like other adapters do."""

    def test_whitespace_only_query_raises(self) -> None:
        """Whitespace-only query must raise AdapterError."""
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        with pytest.raises(AdapterError, match="query must not be empty"):
            BigQueryAdapter(query="   ", project="test-project")

    def test_tabs_and_newlines_query_raises(self) -> None:
        """Tabs/newlines-only query must raise AdapterError."""
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        with pytest.raises(AdapterError, match="query must not be empty"):
            BigQueryAdapter(query="\t\n  \n\t", project="test-project")

    def test_valid_query_accepted(self) -> None:
        """A real query with leading/trailing whitespace must be accepted."""
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter

        adapter = BigQueryAdapter(query="  SELECT 1  ", project="test-project")
        assert adapter._query == "  SELECT 1  "

    def test_consistency_with_snowflake(self) -> None:
        """BigQuery whitespace rejection must match Snowflake behaviour."""
        from ceds_jsonld.adapters.bigquery_adapter import BigQueryAdapter
        from ceds_jsonld.adapters.snowflake_adapter import SnowflakeAdapter

        # Both must reject whitespace-only queries with the same message
        with pytest.raises(AdapterError, match="query must not be empty"):
            BigQueryAdapter(query="   ", project="test")

        with pytest.raises(AdapterError, match="query must not be empty"):
            SnowflakeAdapter(query="   ", account="a", user="u", password="p")


# ======================================================================
# Issue #40b — OneRoster _fetch_page must not bypass _import_httpx()
# ======================================================================


class TestOneRosterImportBypass:
    """_fetch_page must use _import_httpx(), not a bare import statement."""

    def test_fetch_page_no_bare_import(self) -> None:
        """_fetch_page source must not contain 'import httpx'."""
        import inspect

        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        source = inspect.getsource(OneRosterAdapter._fetch_page)
        # Must NOT have a bare `import httpx` statement
        assert "import httpx" not in source

    def test_fetch_page_uses_import_httpx_wrapper(self) -> None:
        """_fetch_page must call _import_httpx() for the httpx module."""
        import inspect

        from ceds_jsonld.adapters.oneroster_adapter import OneRosterAdapter

        source = inspect.getsource(OneRosterAdapter._fetch_page)
        # Must use the wrapper method
        assert "_import_httpx" in source

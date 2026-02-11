"""Databricks SQL source adapter — read records via databricks-sql-connector.

Requires the ``databricks-sql-connector`` optional dependency
(``pip install ceds-jsonld[databricks]``).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError


class DatabricksAdapter(SourceAdapter):
    """Execute a SQL query against Databricks SQL and yield rows as dicts.

    Uses ``Row.asDict()`` from the native connector so every row is
    returned as a plain ``dict``.

    Example:
        >>> adapter = DatabricksAdapter(
        ...     query="SELECT * FROM education.students LIMIT 100",
        ...     server_hostname="adb-1234567890.1.azuredatabricks.net",
        ...     http_path="/sql/1.0/warehouses/abc123",
        ...     access_token="dapi...",
        ... )
        >>> for row in adapter.read():
        ...     print(row["first_name"])
    """

    def __init__(
        self,
        query: str,
        *,
        server_hostname: str,
        http_path: str,
        access_token: str | None = None,
        credentials_provider: Any | None = None,
        auth_type: str | None = None,
        catalog: str | None = None,
        schema: str | None = None,
        params: list[Any] | None = None,
    ) -> None:
        """Initialize with a SQL query and Databricks connection details.

        Args:
            query: SQL SELECT statement to execute.
            server_hostname: Databricks workspace hostname
                (e.g. ``adb-123.1.azuredatabricks.net``).
            http_path: SQL warehouse or cluster HTTP path.
            access_token: Databricks personal access token.
            credentials_provider: Custom credentials provider for OAuth.
            auth_type: Authentication type (e.g. ``"databricks-oauth"``).
            catalog: Default Unity Catalog catalog.
            schema: Default schema within the catalog.
            params: Positional bind parameters for the query.

        Raises:
            AdapterError: If *query*, *server_hostname*, or *http_path*
                is empty.
        """
        if not query or not query.strip():
            msg = "query must not be empty"
            raise AdapterError(msg)
        if not server_hostname:
            msg = "server_hostname must not be empty"
            raise AdapterError(msg)
        if not http_path:
            msg = "http_path must not be empty"
            raise AdapterError(msg)

        self._query = query
        self._server_hostname = server_hostname
        self._http_path = http_path
        self._access_token = access_token
        self._credentials_provider = credentials_provider
        self._auth_type = auth_type
        self._catalog = catalog
        self._schema = schema
        self._params = params

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Execute the query and yield each row as a dict.

        Returns:
            Iterator of dicts keyed by column name.

        Raises:
            AdapterError: If the connector is missing, connection fails,
                or the query errors out.
        """
        sql_mod = self._import_databricks()
        try:
            with self._connect(sql_mod) as conn, conn.cursor() as cursor:
                cursor.execute(self._query, self._params)
                rows = cursor.fetchall()
                for row in rows:
                    yield row.asDict()
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"Databricks query failed: {exc}"
            raise AdapterError(msg) from exc

    def read_batch(self, batch_size: int = 1000, **kwargs: Any) -> Iterator[list[dict[str, Any]]]:
        """Execute the query and yield rows in batches via ``fetchmany``.

        Args:
            batch_size: Number of records per batch.

        Returns:
            Iterator of lists of dicts.
        """
        sql_mod = self._import_databricks()
        try:
            with self._connect(sql_mod) as conn, conn.cursor() as cursor:
                cursor.execute(self._query, self._params)
                while True:
                    batch = cursor.fetchmany(batch_size)
                    if not batch:
                        break
                    yield [row.asDict() for row in batch]
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"Databricks query failed: {exc}"
            raise AdapterError(msg) from exc

    def count(self) -> int | None:
        """Return ``None`` — count requires executing the query."""
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_databricks() -> Any:
        """Lazy-import databricks.sql."""
        try:
            from databricks import sql  # noqa: WPS433

            return sql
        except ImportError as exc:
            msg = (
                "databricks-sql-connector is required for Databricks support. "
                "Install with: pip install ceds-jsonld[databricks]"
            )
            raise AdapterError(msg) from exc

    def _connect(self, sql_mod: Any) -> Any:
        """Create a Databricks SQL connection."""
        connect_kwargs: dict[str, Any] = {
            "server_hostname": self._server_hostname,
            "http_path": self._http_path,
        }
        if self._access_token is not None:
            connect_kwargs["access_token"] = self._access_token
        if self._credentials_provider is not None:
            connect_kwargs["credentials_provider"] = self._credentials_provider
        if self._auth_type is not None:
            connect_kwargs["auth_type"] = self._auth_type
        if self._catalog is not None:
            connect_kwargs["catalog"] = self._catalog
        if self._schema is not None:
            connect_kwargs["schema"] = self._schema

        try:
            return sql_mod.connect(**connect_kwargs)
        except Exception as exc:
            msg = f"Failed to connect to Databricks at '{self._server_hostname}': {exc}"
            raise AdapterError(msg) from exc

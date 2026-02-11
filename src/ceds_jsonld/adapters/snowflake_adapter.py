"""Snowflake source adapter — read records via the native Snowflake connector.

Requires the ``snowflake-connector-python`` optional dependency
(``pip install ceds-jsonld[snowflake]``).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError


class SnowflakeAdapter(SourceAdapter):
    """Execute a SQL query against Snowflake and yield rows as dicts.

    Uses the native ``snowflake-connector-python`` ``DictCursor`` so every
    row is returned as a plain ``dict``.

    Example:
        >>> adapter = SnowflakeAdapter(
        ...     query="SELECT * FROM students WHERE grade = %(grade)s",
        ...     account="myorg-myaccount",
        ...     user="etl_user",
        ...     private_key_file="/path/to/key.p8",
        ...     warehouse="compute_wh",
        ...     database="education_db",
        ...     schema="public",
        ...     params={"grade": 10},
        ... )
        >>> for row in adapter.read():
        ...     print(row["FIRST_NAME"])
    """

    def __init__(
        self,
        query: str,
        *,
        account: str,
        user: str | None = None,
        password: str | None = None,
        private_key_file: str | Path | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        role: str | None = None,
        authenticator: str | None = None,
        connection_name: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Initialize with a SQL query and Snowflake connection details.

        Args:
            query: SQL SELECT statement to execute.
            account: Snowflake account identifier (``org-account``).
            user: Login user name.
            password: Login password (prefer key-pair auth in production).
            private_key_file: Path to a PEM private-key file for key-pair auth.
            warehouse: Snowflake warehouse to use.
            database: Default database.
            schema: Default schema.
            role: Snowflake role to assume.
            authenticator: Authentication method (e.g. ``externalbrowser``).
            connection_name: Named connection from ``~/.snowflake/connections.toml``.
            params: Bind parameters for the query.

        Raises:
            AdapterError: If *query* or *account* is empty.
        """
        if not query or not query.strip():
            msg = "query must not be empty"
            raise AdapterError(msg)
        if not account:
            msg = "account must not be empty"
            raise AdapterError(msg)

        self._query = query
        self._account = account
        self._user = user
        self._password = password
        self._private_key_file = str(Path(private_key_file)) if private_key_file else None
        self._warehouse = warehouse
        self._database = database
        self._schema = schema
        self._role = role
        self._authenticator = authenticator
        self._connection_name = connection_name
        self._params = params or {}

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
        sf = self._import_snowflake()
        conn = self._connect(sf)
        try:
            cur = conn.cursor(sf.DictCursor)
            try:
                cur.execute(self._query, self._params)
                yield from cur
            finally:
                cur.close()
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"Snowflake query failed: {exc}"
            raise AdapterError(msg) from exc
        finally:
            conn.close()

    def read_batch(self, batch_size: int = 1000, **kwargs: Any) -> Iterator[list[dict[str, Any]]]:
        """Execute the query and yield rows in batches via ``fetchmany``.

        Args:
            batch_size: Number of records per batch.

        Returns:
            Iterator of lists of dicts.
        """
        sf = self._import_snowflake()
        conn = self._connect(sf)
        try:
            cur = conn.cursor(sf.DictCursor)
            try:
                cur.execute(self._query, self._params)
                while True:
                    batch = cur.fetchmany(batch_size)
                    if not batch:
                        break
                    yield list(batch)
            finally:
                cur.close()
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"Snowflake query failed: {exc}"
            raise AdapterError(msg) from exc
        finally:
            conn.close()

    def count(self) -> int | None:
        """Return ``None`` — count requires executing the query."""
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_snowflake() -> Any:
        """Lazy-import snowflake.connector."""
        try:
            import snowflake.connector as sf  # noqa: WPS433

            return sf
        except ImportError as exc:
            msg = (
                "snowflake-connector-python is required for Snowflake support. "
                "Install with: pip install ceds-jsonld[snowflake]"
            )
            raise AdapterError(msg) from exc

    def _connect(self, sf: Any) -> Any:
        """Create a Snowflake connection."""
        connect_kwargs: dict[str, Any] = {"account": self._account}
        if self._user is not None:
            connect_kwargs["user"] = self._user
        if self._password is not None:
            connect_kwargs["password"] = self._password
        if self._private_key_file is not None:
            connect_kwargs["private_key_file"] = self._private_key_file
        if self._warehouse is not None:
            connect_kwargs["warehouse"] = self._warehouse
        if self._database is not None:
            connect_kwargs["database"] = self._database
        if self._schema is not None:
            connect_kwargs["schema"] = self._schema
        if self._role is not None:
            connect_kwargs["role"] = self._role
        if self._authenticator is not None:
            connect_kwargs["authenticator"] = self._authenticator
        if self._connection_name is not None:
            connect_kwargs["connection_name"] = self._connection_name

        try:
            return sf.connect(**connect_kwargs)
        except Exception as exc:
            msg = f"Failed to connect to Snowflake account '{self._account}': {exc}"
            raise AdapterError(msg) from exc

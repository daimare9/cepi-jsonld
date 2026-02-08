"""Database source adapter — read records via SQLAlchemy.

Requires the ``sqlalchemy`` optional dependency
(``pip install ceds-jsonld[database]``).  A database-specific driver
(e.g. ``pyodbc``, ``psycopg2``, ``pymysql``) must also be installed.
"""

from __future__ import annotations

from typing import Any, Iterator

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError


class DatabaseAdapter(SourceAdapter):
    """Execute a SQL query and yield each row as a dict.

    Example:
        >>> adapter = DatabaseAdapter(
        ...     connection_string="sqlite:///school.db",
        ...     query="SELECT * FROM students",
        ... )
        >>> for row in adapter.read():
        ...     print(row["FirstName"])
    """

    def __init__(
        self,
        connection_string: str,
        query: str,
        *,
        params: dict[str, Any] | None = None,
        connect_args: dict[str, Any] | None = None,
    ) -> None:
        """Initialize with a SQLAlchemy connection string and a query.

        Args:
            connection_string: SQLAlchemy-style URL, e.g.
                ``"mssql+pyodbc://…"`` or ``"sqlite:///data.db"``.
            query: SQL SELECT statement to execute.
            params: Optional bind parameters for the query.
            connect_args: Additional keyword arguments forwarded to
                ``sqlalchemy.create_engine(connect_args=…)``.
        """
        if not connection_string:
            msg = "connection_string must not be empty"
            raise AdapterError(msg)
        if not query or not query.strip():
            msg = "query must not be empty"
            raise AdapterError(msg)
        self._connection_string = connection_string
        self._query = query
        self._params = params or {}
        self._connect_args = connect_args or {}

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Execute the query and yield each row as a dict.

        Returns:
            Iterator of dicts keyed by column name.
        """
        try:
            from sqlalchemy import create_engine, text
        except ImportError as exc:
            msg = "sqlalchemy is required for database support. Install with: pip install ceds-jsonld[database]"
            raise AdapterError(msg) from exc

        try:
            engine = create_engine(
                self._connection_string,
                connect_args=self._connect_args,
            )
        except Exception as exc:
            msg = f"Failed to create database engine: {exc}"
            raise AdapterError(msg) from exc

        try:
            with engine.connect() as conn:
                result = conn.execute(text(self._query), self._params)
                columns = list(result.keys())
                for row in result:
                    yield dict(zip(columns, row, strict=False))
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"Database query failed: {exc}"
            raise AdapterError(msg) from exc
        finally:
            engine.dispose()

    def count(self) -> int | None:
        """Return ``None`` — row count requires executing the query.

        Override if you want to run ``SELECT COUNT(*)`` separately.
        """
        return None

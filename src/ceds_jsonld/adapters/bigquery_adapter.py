"""Google BigQuery source adapter — read records via google-cloud-bigquery.

Requires the ``google-cloud-bigquery`` optional dependency
(``pip install ceds-jsonld[bigquery]``).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError


class BigQueryAdapter(SourceAdapter):
    """Execute a SQL query or read a table from Google BigQuery.

    Each row is yielded as a plain ``dict`` via ``dict(row)``.

    Example:
        >>> adapter = BigQueryAdapter(
        ...     query="SELECT * FROM `project.dataset.students` WHERE grade = @grade",
        ...     project="my-gcp-project",
        ...     params={"grade": 10},
        ... )
        >>> for row in adapter.read():
        ...     print(row["first_name"])

    You can also read directly from a table without SQL:

        >>> adapter = BigQueryAdapter(
        ...     table="my-project.education.students",
        ...     max_results=5000,
        ... )
    """

    def __init__(
        self,
        query: str | None = None,
        table: str | None = None,
        *,
        project: str | None = None,
        credentials: Any | None = None,
        service_account_file: str | Path | None = None,
        params: dict[str, Any] | None = None,
        max_results: int | None = None,
    ) -> None:
        """Initialize with either a SQL query or a fully-qualified table name.

        Args:
            query: BigQuery SQL SELECT statement.  Mutually exclusive with *table*.
            table: Fully-qualified table reference
                (``project.dataset.table``).  Mutually exclusive with *query*.
            project: GCP project ID.  If ``None``, the default project from
                Application Default Credentials is used.
            credentials: A pre-built ``google.auth.credentials.Credentials`` object.
            service_account_file: Path to a service-account JSON key file.
            params: Named query parameters (for parameterised queries).
            max_results: Maximum rows to return (applies to both query and
                table-read modes).  ``None`` means return all rows.

        Raises:
            AdapterError: If neither *query* nor *table* is provided, or if
                both are provided.
        """
        if query and table:
            msg = "Provide either 'query' or 'table', not both."
            raise AdapterError(msg)
        if not query and not table:
            msg = "Provide either 'query' (SQL) or 'table' (project.dataset.table)."
            raise AdapterError(msg)
        if query and not query.strip():
            msg = "query must not be empty"
            raise AdapterError(msg)

        self._query = query
        self._table = table
        self._project = project
        self._credentials = credentials
        self._service_account_file = str(Path(service_account_file)) if service_account_file else None
        self._params = params or {}
        self._max_results = max_results

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Execute the query / table read and yield each row as a dict.

        Returns:
            Iterator of dicts keyed by column name.

        Raises:
            AdapterError: If the library is missing, auth fails, or the
                query errors out.
        """
        bigquery = self._import_bigquery()
        client = self._get_client(bigquery)

        try:
            if self._query:
                job_config = self._build_job_config(bigquery)
                query_job = client.query(self._query, job_config=job_config)
                rows = query_job.result(max_results=self._max_results)
            else:
                rows = client.list_rows(self._table, max_results=self._max_results)

            for row in rows:
                yield dict(row)
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"BigQuery operation failed: {exc}"
            raise AdapterError(msg) from exc

    def count(self) -> int | None:
        """Return the row count for a table, or ``None`` for queries.

        Only works in table-read mode; queries would need to be executed
        to determine total rows.
        """
        if not self._table:
            return None
        bigquery = self._import_bigquery()
        client = self._get_client(bigquery)
        try:
            table_ref = client.get_table(self._table)
            return int(table_ref.num_rows)  # type: ignore[arg-type]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_bigquery() -> Any:
        """Lazy-import google.cloud.bigquery."""
        try:
            from google.cloud import bigquery  # noqa: WPS433

            return bigquery
        except ImportError as exc:
            msg = (
                "google-cloud-bigquery is required for BigQuery support. "
                "Install with: pip install ceds-jsonld[bigquery]"
            )
            raise AdapterError(msg) from exc

    def _get_client(self, bigquery: Any) -> Any:
        """Create a BigQuery Client with configured credentials."""
        client_kwargs: dict[str, Any] = {}
        if self._project:
            client_kwargs["project"] = self._project

        if self._credentials is not None:
            client_kwargs["credentials"] = self._credentials
        elif self._service_account_file:
            try:
                from google.oauth2 import service_account  # noqa: WPS433

                creds = service_account.Credentials.from_service_account_file(
                    self._service_account_file,
                )
                client_kwargs["credentials"] = creds
            except ImportError as exc:
                msg = (
                    "google-auth is required for service-account authentication. "
                    "It is usually installed with google-cloud-bigquery."
                )
                raise AdapterError(msg) from exc
            except Exception as exc:
                msg = f"Failed to load service account credentials: {exc}"
                raise AdapterError(msg) from exc

        try:
            return bigquery.Client(**client_kwargs)
        except Exception as exc:
            msg = f"Failed to create BigQuery client: {exc}"
            raise AdapterError(msg) from exc

    def _build_job_config(self, bigquery: Any) -> Any:
        """Build a QueryJobConfig with any bind parameters."""
        if not self._params:
            return bigquery.QueryJobConfig()

        query_params = []
        for name, value in self._params.items():
            if isinstance(value, bool):
                bq_type = "BOOL"
            elif isinstance(value, int):
                bq_type = "INT64"
            elif isinstance(value, float):
                bq_type = "FLOAT64"
            else:
                bq_type = "STRING"
            query_params.append(
                bigquery.ScalarQueryParameter(name, bq_type, value),
            )
        return bigquery.QueryJobConfig(query_parameters=query_params)

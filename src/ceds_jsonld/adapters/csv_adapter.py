"""CSV source adapter — read CSV files using pandas.

Handles encoding, delimiter, quoting, and multi-value pipe/comma encoding
commonly found in CEDS data exports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError


class CSVAdapter(SourceAdapter):
    """Read records from a CSV file.

    Example:
        >>> adapter = CSVAdapter("students.csv")
        >>> for row in adapter.read():
        ...     print(row["FirstName"])
    """

    def __init__(
        self,
        path: str | Path,
        *,
        encoding: str = "utf-8",
        delimiter: str = ",",
        dtype: type | dict[str, type] | None = str,
        na_values: list[str] | None = None,
        **pandas_kwargs: Any,
    ) -> None:
        """Initialize with a file path and optional pandas read_csv options.

        Args:
            path: Path to the CSV file.
            encoding: File encoding (default: utf-8).
            delimiter: Column delimiter (default: comma).
            dtype: Column dtypes. Defaults to ``str`` to avoid pandas
                auto-converting identifiers to float.
            na_values: Additional strings to treat as NA / missing.
            **pandas_kwargs: Any additional keyword arguments forwarded to
                ``pandas.read_csv()``.
        """
        self._path = Path(path)
        if not self._path.exists():
            msg = f"CSV file not found: {self._path}"
            raise AdapterError(msg)
        self._encoding = encoding
        self._delimiter = delimiter
        self._dtype = dtype
        self._na_values = na_values
        self._pandas_kwargs = pandas_kwargs

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Yield each CSV row as a dict.

        Missing / NaN values are converted to empty strings.

        Returns:
            Iterator of dicts keyed by column header.
        """
        try:
            df = pd.read_csv(
                self._path,
                encoding=self._encoding,
                delimiter=self._delimiter,
                dtype=self._dtype,
                na_values=self._na_values,
                keep_default_na=True,
                **self._pandas_kwargs,
            )
        except Exception as exc:
            msg = f"Failed to read CSV '{self._path}': {exc}"
            raise AdapterError(msg) from exc

        # Replace NaN with empty string for downstream mapper compatibility
        df = df.fillna("")

        for record in df.to_dict(orient="records"):
            yield record

    def read_batch(self, batch_size: int = 1000, **kwargs: Any) -> Iterator[list[dict[str, Any]]]:
        """Yield batches by reading with pandas chunksize.

        Args:
            batch_size: Number of rows per chunk.

        Returns:
            Iterator of lists of dicts.
        """
        try:
            reader = pd.read_csv(
                self._path,
                encoding=self._encoding,
                delimiter=self._delimiter,
                dtype=self._dtype,
                na_values=self._na_values,
                keep_default_na=True,
                chunksize=batch_size,
                **self._pandas_kwargs,
            )
        except Exception as exc:
            msg = f"Failed to read CSV '{self._path}': {exc}"
            raise AdapterError(msg) from exc

        for chunk in reader:
            chunk = chunk.fillna("")
            yield chunk.to_dict(orient="records")

    def count(self) -> int | None:
        """Return the number of data rows in the CSV (excludes header)."""
        try:
            # Fast line count without loading data
            with self._path.open(encoding=self._encoding) as f:
                return sum(1 for _ in f) - 1  # subtract header
        except OSError:
            return None

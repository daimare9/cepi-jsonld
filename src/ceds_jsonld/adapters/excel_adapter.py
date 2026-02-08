"""Excel source adapter — read .xlsx/.xls files using pandas + openpyxl.

Requires the ``openpyxl`` optional dependency (``pip install ceds-jsonld[excel]``).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError

if TYPE_CHECKING:
    import pandas as pd


class ExcelAdapter(SourceAdapter):
    """Read records from an Excel workbook.

    Example:
        >>> adapter = ExcelAdapter("students.xlsx", sheet_name="Sheet1")
        >>> for row in adapter.read():
        ...     print(row["FirstName"])
    """

    def __init__(
        self,
        path: str | Path,
        *,
        sheet_name: str | int = 0,
        header: int = 0,
        dtype: type | dict[str, type] | None = str,
        **pandas_kwargs: Any,
    ) -> None:
        """Initialize with a file path and optional sheet/header options.

        Args:
            path: Path to the Excel file (.xlsx or .xls).
            sheet_name: Sheet name or zero-based index (default: first sheet).
            header: Row number for column headers (default: 0).
            dtype: Column dtypes. Defaults to ``str``.
            **pandas_kwargs: Additional keyword arguments forwarded to
                ``pandas.read_excel()``.
        """
        self._path = Path(path)
        if not self._path.exists():
            msg = f"Excel file not found: {self._path}"
            raise AdapterError(msg)
        self._sheet_name = sheet_name
        self._header = header
        self._dtype = dtype
        self._pandas_kwargs = pandas_kwargs

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Yield each row as a dict.

        Returns:
            Iterator of dicts keyed by column header.
        """
        try:
            import openpyxl  # noqa: F401 — verify available
        except ImportError as exc:
            msg = "openpyxl is required for Excel support. Install with: pip install ceds-jsonld[excel]"
            raise AdapterError(msg) from exc

        try:
            df = self._load_dataframe()
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"Failed to read Excel '{self._path}': {exc}"
            raise AdapterError(msg) from exc

        yield from df.to_dict(orient="records")

    def count(self) -> int | None:
        """Return the number of data rows in the sheet."""
        try:
            df = self._load_dataframe()
            return len(df)
        except Exception:
            return None

    def _load_dataframe(self) -> pd.DataFrame:
        """Load the Excel sheet into a pandas DataFrame."""
        import pandas as pd

        df = pd.read_excel(
            self._path,
            sheet_name=self._sheet_name,
            header=self._header,
            dtype=self._dtype,
            **self._pandas_kwargs,
        )
        return df.fillna("")

"""Google Sheets source adapter — read records via gspread.

Requires the ``gspread`` optional dependency
(``pip install ceds-jsonld[sheets]``).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError


class GoogleSheetsAdapter(SourceAdapter):
    """Read education data from a Google Sheets spreadsheet.

    Uses `gspread <https://docs.gspread.org/>`_ to fetch all rows from a
    worksheet and yield them as plain dicts.

    Example:
        >>> adapter = GoogleSheetsAdapter(
        ...     spreadsheet="Student Enrollment Data",
        ...     worksheet="Sheet1",
        ...     service_account_file="service_account.json",
        ... )
        >>> for row in adapter.read():
        ...     print(row["FirstName"])
    """

    def __init__(
        self,
        spreadsheet: str,
        worksheet: str | int = 0,
        *,
        credentials: Any | None = None,
        service_account_file: str | Path | None = None,
        api_key: str | None = None,
        header_row: int = 1,
        value_render_option: str = "FORMATTED_VALUE",
    ) -> None:
        """Initialize with a spreadsheet identifier and auth credentials.

        Args:
            spreadsheet: Spreadsheet title, key (44-char ID), or full URL.
            worksheet: Worksheet name (str) or 0-based index (int).
                Defaults to the first sheet.
            credentials: A pre-built ``google.auth.credentials.Credentials``
                object.  Takes precedence over other auth parameters.
            service_account_file: Path to a Google Cloud service-account
                JSON key file.  Recommended for server-side pipelines.
            api_key: Google API key (read-only, public sheets only).
            header_row: Row number containing column headers (1-based).
            value_render_option: How cell values are rendered.
                ``"FORMATTED_VALUE"`` (default) or ``"UNFORMATTED_VALUE"``.

        Raises:
            AdapterError: If *spreadsheet* is empty or no auth method is
                provided.
        """
        if not spreadsheet:
            msg = "spreadsheet identifier must not be empty"
            raise AdapterError(msg)

        auth_count = sum(x is not None for x in (credentials, service_account_file, api_key))
        if auth_count == 0:
            msg = "No authentication provided. Supply one of: credentials, service_account_file, or api_key."
            raise AdapterError(msg)
        if auth_count > 1:
            msg = (
                "Multiple authentication methods provided. Supply exactly "
                "one of: credentials, service_account_file, or api_key."
            )
            raise AdapterError(msg)

        self._spreadsheet = spreadsheet
        self._worksheet = worksheet
        self._credentials = credentials
        self._service_account_file = Path(service_account_file) if service_account_file else None
        self._api_key = api_key
        self._header_row = header_row
        self._value_render_option = value_render_option

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Fetch all rows from the worksheet and yield each as a dict.

        Returns:
            Iterator of dicts keyed by column header.

        Raises:
            AdapterError: If gspread is missing, auth fails, or the
                spreadsheet/worksheet cannot be found.
        """
        gspread = self._import_gspread()
        client = self._get_client(gspread)
        sheet = self._open_spreadsheet(client, gspread)
        ws = self._select_worksheet(sheet)

        try:
            records = ws.get_all_records(
                head=self._header_row,
                value_render_option=self._value_render_option,
            )
        except Exception as exc:
            msg = f"Failed to read worksheet records: {exc}"
            raise AdapterError(msg) from exc

        yield from records

    def count(self) -> int | None:
        """Return the approximate row count (excluding the header).

        This opens the spreadsheet to read ``row_count``, which includes
        empty trailing rows.  For an exact count, iterate ``read()``.
        """
        gspread = self._import_gspread()
        client = self._get_client(gspread)
        sheet = self._open_spreadsheet(client, gspread)
        ws = self._select_worksheet(sheet)
        return max(0, ws.row_count - self._header_row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_gspread() -> Any:
        """Lazy-import gspread, raising a friendly error if missing."""
        try:
            import gspread as gs  # noqa: WPS433

            return gs
        except ImportError as exc:
            msg = "gspread is required for Google Sheets support. Install with: pip install ceds-jsonld[sheets]"
            raise AdapterError(msg) from exc

    def _get_client(self, gspread: Any) -> Any:
        """Create a gspread ``Client`` using the configured auth method."""
        try:
            if self._credentials is not None:
                return gspread.authorize(self._credentials)
            if self._service_account_file is not None:
                return gspread.service_account(
                    filename=str(self._service_account_file),
                )
            # api_key path
            return gspread.api_key(api_key=self._api_key)
        except Exception as exc:
            msg = f"Google Sheets authentication failed: {exc}"
            raise AdapterError(msg) from exc

    def _open_spreadsheet(self, client: Any, gspread: Any) -> Any:
        """Open a spreadsheet by title, key, or URL."""
        target = self._spreadsheet
        try:
            if target.startswith("https://"):
                return client.open_by_url(target)
            if len(target) == 44 and " " not in target:
                # Likely a spreadsheet key (44-character alphanumeric ID)
                return client.open_by_key(target)
            return client.open(target)
        except gspread.exceptions.SpreadsheetNotFound as exc:
            msg = (
                f"Spreadsheet '{target}' not found. Check the title, "
                "key, or URL and ensure the service account has access."
            )
            raise AdapterError(msg) from exc
        except Exception as exc:
            msg = f"Failed to open spreadsheet '{target}': {exc}"
            raise AdapterError(msg) from exc

    def _select_worksheet(self, spreadsheet: Any) -> Any:
        """Select a worksheet by name or 0-based index."""
        try:
            if isinstance(self._worksheet, int):
                return spreadsheet.get_worksheet(self._worksheet)
            return spreadsheet.worksheet(self._worksheet)
        except Exception as exc:
            msg = (
                f"Worksheet '{self._worksheet}' not found in spreadsheet "
                f"'{self._spreadsheet}'. Available sheets: "
                f"{[ws.title for ws in spreadsheet.worksheets()]}"
            )
            raise AdapterError(msg) from exc

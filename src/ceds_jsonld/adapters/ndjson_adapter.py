"""Newline-delimited JSON (NDJSON) source adapter — streaming, line-by-line.

Each line of the input file must be a valid JSON object.  Lines are parsed
one at a time so the entire file is never loaded into memory.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError


class NDJSONAdapter(SourceAdapter):
    """Read records from a newline-delimited JSON file.

    Example:
        >>> adapter = NDJSONAdapter("records.ndjson")
        >>> for row in adapter.read():
        ...     print(row["FirstName"])
    """

    def __init__(
        self,
        path: str | Path,
        *,
        encoding: str = "utf-8",
    ) -> None:
        """Initialize with a file path.

        Args:
            path: Path to the NDJSON file.
            encoding: File encoding (default: utf-8).
        """
        self._path = Path(path)
        if not self._path.exists():
            msg = f"NDJSON file not found: {self._path}"
            raise AdapterError(msg)
        self._encoding = encoding

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Yield each line as a parsed dict.

        Blank lines are silently skipped.

        Returns:
            Iterator of dicts, one per JSON line.
        """
        try:
            with self._path.open(encoding=self._encoding) as fh:
                for lineno, raw_line in enumerate(fh, start=1):
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        msg = f"Invalid JSON on line {lineno} of '{self._path}': {exc}"
                        raise AdapterError(msg) from exc
                    if not isinstance(record, dict):
                        msg = f"Line {lineno} of '{self._path}' is not a JSON object"
                        raise AdapterError(msg)
                    yield record
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"Failed to read NDJSON '{self._path}': {exc}"
            raise AdapterError(msg) from exc

    def count(self) -> int | None:
        """Return the number of non-blank lines in the file.

        Returns:
            Line count, or ``None`` on error.
        """
        try:
            total = 0
            with self._path.open(encoding=self._encoding) as fh:
                for raw_line in fh:
                    if raw_line.strip():
                        total += 1
            return total
        except Exception:
            return None

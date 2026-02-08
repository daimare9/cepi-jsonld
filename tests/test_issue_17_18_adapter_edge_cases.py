"""Tests for issues #17, #18 — adapter edge cases.

#17: CSVAdapter.count() returns -1 for empty files and miscounts blank lines.
#18: NDJSONAdapter crashes on UTF-8 BOM files.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ceds_jsonld.adapters.csv_adapter import CSVAdapter
from ceds_jsonld.adapters.ndjson_adapter import NDJSONAdapter


class TestCSVAdapterCountEdgeCases:
    """Issue #17 — count() must match read() for empty files, blank lines, trailing newlines."""

    def test_empty_file_returns_zero(self, tmp_path: Path):
        """An empty (0-byte) CSV file should return 0, not -1."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")
        adapter = CSVAdapter(csv_file)
        assert adapter.count() == 0

    def test_header_only_returns_zero(self, tmp_path: Path):
        """A CSV with only a header row should return 0 data rows."""
        csv_file = tmp_path / "header_only.csv"
        csv_file.write_text("Name,Age\n")
        adapter = CSVAdapter(csv_file)
        assert adapter.count() == 0

    def test_blank_lines_between_rows(self, tmp_path: Path):
        """Blank lines between data rows should not be counted."""
        csv_file = tmp_path / "blanks.csv"
        csv_file.write_text("Name,Age\nAlice,30\n\n\nBob,25\n")
        adapter = CSVAdapter(csv_file)
        count = adapter.count()
        actual_rows = len(list(adapter.read()))
        assert count == actual_rows

    def test_trailing_newlines(self, tmp_path: Path):
        """Trailing newlines should not inflate the count."""
        csv_file = tmp_path / "trailing.csv"
        csv_file.write_text("Name,Age\nAlice,30\nBob,25\n\n\n\n")
        adapter = CSVAdapter(csv_file)
        count = adapter.count()
        actual_rows = len(list(adapter.read()))
        assert count == actual_rows

    def test_count_matches_read_normal_file(self, tmp_path: Path):
        """Normal CSV — count() and len(read()) must agree."""
        csv_file = tmp_path / "normal.csv"
        csv_file.write_text("Name,Age\nAlice,30\nBob,25\nCharlie,35\n")
        adapter = CSVAdapter(csv_file)
        assert adapter.count() == 3
        assert adapter.count() == len(list(adapter.read()))


class TestNDJSONAdapterBOM:
    """Issue #18 — NDJSONAdapter must handle UTF-8 BOM transparently."""

    def test_bom_file_reads_successfully(self, tmp_path: Path):
        """NDJSON file with UTF-8 BOM should parse without errors."""
        ndjson_file = tmp_path / "bom.ndjson"
        bom = b"\xef\xbb\xbf"
        ndjson_file.write_bytes(bom + b'{"Name": "Alice"}\n{"Name": "Bob"}\n')
        adapter = NDJSONAdapter(ndjson_file)
        records = list(adapter.read())
        assert len(records) == 2
        assert records[0]["Name"] == "Alice"
        assert records[1]["Name"] == "Bob"

    def test_no_bom_still_works(self, tmp_path: Path):
        """NDJSON file without BOM still works normally."""
        ndjson_file = tmp_path / "no_bom.ndjson"
        ndjson_file.write_bytes(b'{"Name": "Charlie"}\n')
        adapter = NDJSONAdapter(ndjson_file)
        records = list(adapter.read())
        assert len(records) == 1
        assert records[0]["Name"] == "Charlie"

    def test_bom_count(self, tmp_path: Path):
        """count() also works with BOM files."""
        ndjson_file = tmp_path / "bom_count.ndjson"
        bom = b"\xef\xbb\xbf"
        ndjson_file.write_bytes(bom + b'{"Name": "Alice"}\n{"Name": "Bob"}\n')
        adapter = NDJSONAdapter(ndjson_file)
        assert adapter.count() == 2

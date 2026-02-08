"""Source adapters for ingesting data from CSV, Excel, APIs, databases, and more."""

from __future__ import annotations

from ceds_jsonld.adapters.api_adapter import APIAdapter
from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.adapters.csv_adapter import CSVAdapter
from ceds_jsonld.adapters.database_adapter import DatabaseAdapter
from ceds_jsonld.adapters.dict_adapter import DictAdapter
from ceds_jsonld.adapters.excel_adapter import ExcelAdapter
from ceds_jsonld.adapters.ndjson_adapter import NDJSONAdapter

__all__ = [
    "APIAdapter",
    "CSVAdapter",
    "DatabaseAdapter",
    "DictAdapter",
    "ExcelAdapter",
    "NDJSONAdapter",
    "SourceAdapter",
]

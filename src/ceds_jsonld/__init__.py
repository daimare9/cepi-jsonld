"""ceds-jsonld — Python library for CEDS/CEPI JSON-LD generation."""

from __future__ import annotations

from ceds_jsonld.adapters import (
    APIAdapter,
    CSVAdapter,
    DatabaseAdapter,
    DictAdapter,
    ExcelAdapter,
    NDJSONAdapter,
    SourceAdapter,
)
from ceds_jsonld.builder import JSONLDBuilder
from ceds_jsonld.cosmos import CosmosLoader, prepare_for_cosmos
from ceds_jsonld.introspector import NodeShapeInfo, PropertyInfo, SHACLIntrospector
from ceds_jsonld.logging import get_logger
from ceds_jsonld.mapping import FieldMapper
from ceds_jsonld.pipeline import Pipeline, PipelineResult
from ceds_jsonld.registry import ShapeDefinition, ShapeRegistry
from ceds_jsonld.sanitize import sanitize_iri_component, sanitize_string_value, validate_base_uri
from ceds_jsonld.validator import (
    FieldIssue,
    PreBuildValidator,
    SHACLValidator,
    ValidationMode,
    ValidationResult,
)

__version__ = "0.9.0"
__all__ = [
    "APIAdapter",
    "CSVAdapter",
    "CosmosLoader",
    "DatabaseAdapter",
    "DictAdapter",
    "ExcelAdapter",
    "FieldIssue",
    "JSONLDBuilder",
    "FieldMapper",
    "NDJSONAdapter",
    "NodeShapeInfo",
    "Pipeline",
    "PipelineResult",
    "PreBuildValidator",
    "PropertyInfo",
    "SHACLIntrospector",
    "SHACLValidator",
    "ShapeDefinition",
    "ShapeRegistry",
    "SourceAdapter",
    "ValidationMode",
    "ValidationResult",
    "get_logger",
    "prepare_for_cosmos",
    "sanitize_iri_component",
    "sanitize_string_value",
    "validate_base_uri",
]

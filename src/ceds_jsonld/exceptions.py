"""Custom exceptions for the ceds-jsonld library."""

from __future__ import annotations


class CEDSJSONLDError(Exception):
    """Base exception for all ceds-jsonld errors."""


class ShapeLoadError(CEDSJSONLDError):
    """Raised when a shape definition cannot be loaded.

    This typically means missing files (SHACL, context, mapping YAML)
    in the shape directory.
    """


class MappingError(CEDSJSONLDError):
    """Raised when field mapping fails.

    Common causes: required source field missing, transform function
    not found, or cardinality mismatch in multi-value fields.
    """


class BuildError(CEDSJSONLDError):
    """Raised when JSON-LD document construction fails."""


class ValidationError(CEDSJSONLDError):
    """Raised when SHACL validation or pre-build validation fails."""


class SerializationError(CEDSJSONLDError):
    """Raised when JSON serialization fails."""


class AdapterError(CEDSJSONLDError):
    """Raised when a source adapter fails to read data.

    Common causes: file not found, invalid format, network error,
    or database connection failure.
    """


class PipelineError(CEDSJSONLDError):
    """Raised when the ingestion pipeline encounters an error."""


class CosmosError(CEDSJSONLDError):
    """Raised when a Cosmos DB operation fails.

    Common causes: missing ``azure-cosmos`` package, authentication failure,
    endpoint unreachable, or document preparation error.
    """

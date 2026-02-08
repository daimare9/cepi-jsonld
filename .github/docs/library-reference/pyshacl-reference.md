# pySHACL Reference — ceds-jsonld

**Version:** 0.29.0
**Docs:** https://github.com/RDFLib/pySHACL
**Last updated:** 2025-01-20

## Installation

```bash
pip install pyshacl
```

## Role in This Project

pySHACL is used **only** for optional validation. It is NOT in the hot path.
- Use it to validate a sample of records during development/testing
- Use it in round-trip tests to verify JSON-LD conformance
- Do NOT use it for 100% of production records (too slow)

## API Reference

### validate()

```python
from pyshacl import validate

conforms, results_graph, results_text = validate(
    data_graph,          # rdflib.Graph or file path — the data to validate
    shacl_graph=None,    # rdflib.Graph or file path — SHACL shapes
    ont_graph=None,      # rdflib.Graph or file path — ontology for reasoning
    inference=None,      # "rdfs", "owlrl", "both", or None
    abort_on_first=False,  # Stop on first violation
    allow_infos=False,   # Treat sh:Info as passing
    allow_warnings=False,  # Treat sh:Warning as passing
    meta_shacl=False,    # Validate SHACL shapes themselves
    advanced=False,      # Enable SHACL-AF (advanced features)
    js=False,            # Enable SHACL-JS
    debug=False,         # Print debug output
    do_owl_imports=False,  # Follow owl:imports
    serialize_report_graph=False,  # Return serialized report
    focus_nodes=None,    # List of focus node URIs to validate (subset)
    use_shapes=None,     # List of shape URIs to use
)
```

### Return Value

```python
conforms: bool         # True if data conforms to all shapes
results_graph: Graph   # rdflib Graph with validation results (sh:ValidationReport)
results_text: str      # Human-readable validation report
```

### Error Types

- `ReportableRuntimeError` — Raised on critical SHACL processing errors
- `ConstraintLoadError` — Raised when a constraint cannot be loaded
- `ShapeLoadError` — Raised when a shape cannot be loaded

## Usage Patterns for This Project

### Round-Trip Validation Test Pattern

```python
import json
from rdflib import Graph
from pyshacl import validate

def validate_jsonld_against_shacl(
    jsonld_doc: dict,
    shacl_path: str,
) -> tuple[bool, str]:
    """Validate a JSON-LD document against its SHACL shape."""
    # Parse JSON-LD into an rdflib graph
    data_graph = Graph()
    data_graph.parse(
        data=json.dumps(jsonld_doc),
        format="json-ld",
    )

    # Load SHACL shapes
    shacl_graph = Graph()
    shacl_graph.parse(shacl_path, format="turtle")

    # Validate
    conforms, _, results_text = validate(
        data_graph,
        shacl_graph=shacl_graph,
        abort_on_first=False,
    )

    return conforms, results_text
```

### Selective Validation (Single Shape)

```python
from rdflib import URIRef

conforms, _, report = validate(
    data_graph,
    shacl_graph=shacl_graph,
    use_shapes=[URIRef("http://cepi-dev.state.mi.us/PersonShape")],
)
```

### Focus Node Filtering

```python
conforms, _, report = validate(
    data_graph,
    shacl_graph=shacl_graph,
    focus_nodes=[URIRef("cepi:person/123456789")],
)
```

## Gotchas & Notes

- pySHACL needs the full ontology if shapes reference classes/properties defined elsewhere. Pass via `ont_graph`.
- `sh:closed true` shapes will reject ANY property not listed in `sh:property` or `sh:ignoredProperties`.
- `inference="rdfs"` enables RDFS reasoning, which can be helpful but is slow.
- For JSON-LD data, ensure `@context` resolves all terms — unresolved terms become blank nodes and fail validation.
- The `results_text` output is multi-line and includes the violation path — parse it for structured error reporting.

## Performance Notes

- Validating a single Person document: ~50-100ms (too slow for 100% of records in bulk)
- Use for spot-checking during development and in test suites
- For production, use lightweight pre-build validation (check required fields, value lists) instead

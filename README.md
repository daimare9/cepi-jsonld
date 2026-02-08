# ceds-jsonld

[![PyPI version](https://img.shields.io/pypi/v/ceds-jsonld.svg)](https://pypi.org/project/ceds-jsonld/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/daimare9/ceds-jsonld/actions/workflows/ci.yml/badge.svg)](https://github.com/daimare9/ceds-jsonld/actions/workflows/ci.yml)
[![Tests: 398 passed](https://img.shields.io/badge/tests-398%20passed-brightgreen.svg)](tests/)
[![Coverage: 88%](https://img.shields.io/badge/coverage-88%25-yellowgreen.svg)]()

**Python library for converting education data into standards-compliant JSON-LD documents backed by the [CEDS ontology](https://ceds.ed.gov/).**

Read data from CSV, Excel, databases, APIs, or plain dicts. Map it to SHACL-defined shapes like Person, Organization, or K-12 Enrollment. Get back clean JSON-LD that validates against the ontology and is ready for Cosmos DB or any downstream system.

```
CSV / Excel / API / DB
        │
        ▼
  ┌───────────┐     ┌───────────┐     ┌───────────┐
  │  Source    │────▶│  Field    │────▶│  JSON-LD  │────▶  .json / .ndjson / Cosmos DB
  │  Adapter   │     │  Mapper   │     │  Builder  │
  └───────────┘     └───────────┘     └───────────┘
        ▲                 ▲                 ▲
        │                 │                 │
        └─────── Pipeline orchestrates ─────┘
```

---

## Installation

```bash
# Core library (CSV + NDJSON + dict support included)
pip install ceds-jsonld

# With Excel support
pip install ceds-jsonld[excel]

# With REST API support
pip install ceds-jsonld[api]

# With database support (SQL Server, PostgreSQL, SQLite, etc.)
pip install ceds-jsonld[database]

# With fast JSON serialization (recommended for production)
pip install ceds-jsonld[fast]

# Everything for development
pip install ceds-jsonld[dev]

# Or install from source
pip install -e ".[dev]"
```

Requires **Python 3.12+**.

---

## Quick Start

### The simplest path: CSV to JSON-LD in 5 lines

```python
from ceds_jsonld import Pipeline, ShapeRegistry, CSVAdapter

registry = ShapeRegistry()
registry.load_shape("person")

pipeline = Pipeline(source=CSVAdapter("students.csv"), shape="person", registry=registry)
pipeline.to_json("output/students.json")
```

That's it. The library reads your CSV, maps each row to the Person SHACL shape using the declarative YAML config, builds JSON-LD documents, and writes them to a file.

> **Tip:** All adapters (`CSVAdapter`, `ExcelAdapter`, `APIAdapter`, etc.) are importable directly from `ceds_jsonld` — no need to reach into sub-packages.

### What comes out

Each record becomes a self-contained JSON-LD document:

```json
{
    "@context": "https://cepi-dev.state.mi.us/ontology/context-person.json",
    "@type": "Person",
    "@id": "cepi:person/989897099",
    "hasPersonName": {
        "@type": "PersonName",
        "FirstName": "EDITH",
        "MiddleName": "M",
        "LastOrSurname": "ADAMS",
        "GenerationCodeOrSuffix": "III",
        "hasRecordStatus": { ... },
        "hasDataCollection": { ... }
    },
    "hasPersonBirth": {
        "@type": "PersonBirth",
        "Birthdate": { "@type": "xsd:date", "@value": "1965-05-15" },
        ...
    },
    ...
}
```

---

## Core Concepts

### Shapes

A **shape** is a self-contained definition of a data collection type. The Person shape, for example, defines what a Person document looks like — its fields, sub-shapes, data types, and cardinalities. Shapes are defined by:

| File | Purpose |
|------|---------|
| `Person_SHACL.ttl` | SHACL constraints — what properties are required, their types, and allowed values |
| `person_context.json` | JSON-LD context — maps short names to full ontology IRIs |
| `person_mapping.yaml` | Field mapping — how your source columns map to JSON-LD properties |
| `person_sample.csv` | Sample data for testing |

The library ships with the **Person** shape. Additional shapes (Organization, K-12 Enrollment, Staff, etc.) follow the same pattern.

### The Pipeline

The `Pipeline` is the main entry point for most users. It connects a data source to a shape and handles the full transformation chain:

```python
pipeline = Pipeline(
    source=CSVAdapter("students.csv"),  # Where to read data
    shape="person",                      # Which shape to map to
    registry=registry,                   # Shape definitions
)
```

### Adapters

Adapters are how data gets into the pipeline. Pick the one that matches your data source:

| Adapter | Input | Install |
|---------|-------|---------|
| `CSVAdapter` | `.csv` files | included |
| `ExcelAdapter` | `.xlsx` / `.xls` files | `pip install ceds-jsonld[excel]` |
| `DictAdapter` | Python dicts (for APIs, tests, etc.) | included |
| `NDJSONAdapter` | Newline-delimited JSON files | included |
| `APIAdapter` | REST/HTTP endpoints with pagination | `pip install ceds-jsonld[api]` |
| `DatabaseAdapter` | SQL databases via SQLAlchemy | `pip install ceds-jsonld[database]` |

---

## Usage Examples

### Validation

Validate your data before building, or validate built documents against the SHACL shape:

```python
from ceds_jsonld import Pipeline, ShapeRegistry, CSVAdapter

registry = ShapeRegistry()
registry.load_shape("person")
pipeline = Pipeline(source=CSVAdapter("students.csv"), shape="person", registry=registry)

# Pre-build validation (fast — checks required fields, datatypes, allowed values)
result = pipeline.validate(mode="report")
print(result.summary())  # "100 records checked: 3 errors, 1 warning"

# Full SHACL round-trip validation (thorough — validates against the SHACL shape)
result = pipeline.validate(mode="report", shacl=True)

# Inline validation during streaming — invalid rows are skipped automatically
for doc in pipeline.stream(validate=True):
    send_to_downstream_system(doc)

# Strict mode raises on the first error
try:
    docs = pipeline.build_all(validate=True, validation_mode="strict")
except ValidationError as e:
    print(f"Validation failed: {e}")
```

Three validation modes are available:

| Mode | Behaviour |
|------|-----------|
| `"report"` | Collect all issues, never raise. Invalid rows skipped in `stream()`. |
| `"strict"` | Raise `ValidationError` on the first failure. |
| `"sample"` | Validate a random subset (default 1%) — ideal for large batches. |

### Stream processing (constant memory)

For large datasets, use `stream()` to process one record at a time without loading everything into memory:

```python
for doc in pipeline.stream():
    send_to_downstream_system(doc)
```

### Batch processing

Build all documents at once when the dataset fits in memory:

```python
docs = pipeline.build_all()
print(f"Built {len(docs)} documents")
```

### File output

```python
# JSON array (human-readable)
pipeline.to_json("output/persons.json")

# NDJSON (one document per line — ideal for streaming ingestion)
pipeline.to_ndjson("output/persons.ndjson")
```

### Production features

The `Pipeline` returns a `PipelineResult` with detailed metrics, and supports progress tracking and dead-letter queues for failed records:

```python
from ceds_jsonld import Pipeline, ShapeRegistry, CSVAdapter

registry = ShapeRegistry()
registry.load_shape("person")

pipeline = Pipeline(
    source=CSVAdapter("students.csv"),
    shape="person",
    registry=registry,
    progress=True,              # show tqdm progress bar (install ceds-jsonld[observability])
    dead_letter_path="failures.ndjson",  # failed records written here
)

result = pipeline.to_json("output/students.json")
print(f"Wrote {result.records_out} records in {result.elapsed_seconds:.2f}s")
print(f"Throughput: {result.records_per_second:.0f} rec/s")
print(f"Failed: {result.records_failed}")
```

Structured logging with PII masking is built in:

```python
from ceds_jsonld import get_logger

log = get_logger("my_app")
log.info("pipeline.complete", records=1000, ssn="123-45-6789")
# ssn is automatically redacted in log output
```

### Reading from Excel

```python
from ceds_jsonld import ExcelAdapter

pipeline = Pipeline(
    source=ExcelAdapter("students.xlsx", sheet_name="Enrollment"),
    shape="person",
    registry=registry,
)
```

### Reading from a database

```python
from ceds_jsonld import DatabaseAdapter

pipeline = Pipeline(
    source=DatabaseAdapter(
        connection_string="mssql+pyodbc://server/db?driver=ODBC+Driver+17+for+SQL+Server",
        query="SELECT * FROM dbo.Students WHERE SchoolYear = 2026",
    ),
    shape="person",
    registry=registry,
)
```

### Reading from a REST API

```python
from ceds_jsonld import APIAdapter

pipeline = Pipeline(
    source=APIAdapter(
        url="https://sis.example.com/api/v2/students",
        headers={"Authorization": "Bearer YOUR_TOKEN"},
        pagination="offset",
        page_size=500,
        results_key="data",
    ),
    shape="person",
    registry=registry,
)
```

### Using in-memory data

```python
from ceds_jsonld import DictAdapter

records = [
    {"FirstName": "Jane", "LastName": "Doe", "Birthdate": "1990-01-15", ...},
    {"FirstName": "John", "LastName": "Smith", "Birthdate": "1985-06-20", ...},
]
pipeline = Pipeline(source=DictAdapter(records), shape="person", registry=registry)
```

---

## Customizing Mappings

The default mapping YAML works out of the box for the standard CSV column names. But your data likely has different column names. There are three ways to handle that:

### Option 1: Override column names at runtime (via Pipeline)

Pass `source_overrides` directly to the Pipeline — no extra setup needed:

```python
pipeline = Pipeline(
    source=CSVAdapter("students.csv"),
    shape="person",
    registry=registry,
    source_overrides={
        "hasPersonName": {
            "FirstName": "FIRST_NM",
            "LastOrSurname": "LAST_NM",
        },
        "hasPersonBirth": {
            "Birthdate": "DOB",
        },
    },
    id_source="STUDENT_ID",
)
pipeline.to_json("output/students.json")
```

Or use the lower-level `FieldMapper` directly:

```python
from ceds_jsonld import FieldMapper

person_shape = registry.get_shape("person")
mapper = FieldMapper(person_shape.mapping_config)

# Override specific column names for your source
my_mapper = mapper.with_overrides(
    id_source="STUDENT_ID",
    source_overrides={
        "hasPersonName": {
            "FirstName": "FIRST_NM",
            "LastOrSurname": "LAST_NM",
        },
        "hasPersonBirth": {
            "Birthdate": "DOB",
        },
    },
)
```

### Option 2: Compose a base mapping with per-source overrides

```python
import yaml
from ceds_jsonld import FieldMapper

person_shape = registry.get_shape("person")

# Load your district-specific overlay
with open("district_47_overlay.yaml") as f:
    overlay = yaml.safe_load(f)

# Merge it on top of the base Person mapping
mapper = FieldMapper.compose(
    base_config=person_shape.mapping_config,
    overlay_config=overlay,
)
```

### Option 3: Write your own mapping YAML

Copy the default `person_mapping.yaml` and modify it to match your source columns. Then load it with a custom shape directory:

```python
registry = ShapeRegistry()
registry.load_shape("person", path="my_shapes/person")
```

### Custom transforms

If your data needs custom transformations beyond the built-in ones, pass them to the pipeline:

```python
def clean_ssn(value: str) -> str:
    """Strip dashes from SSN."""
    return value.replace("-", "")

pipeline = Pipeline(
    source=CSVAdapter("students.csv"),
    shape="person",
    registry=registry,
    custom_transforms={"clean_ssn": clean_ssn},
)
```

Then reference `clean_ssn` by name in your mapping YAML.

---

## Loading to Azure Cosmos DB

The library includes an async bulk loader for Azure Cosmos DB NoSQL. Documents are automatically prepared (Cosmos-required `id` and `partitionKey` fields are injected).

### Via Pipeline (simplest)

```python
from azure.identity import DefaultAzureCredential

pipeline = Pipeline(
    source=CSVAdapter("students.csv"),
    shape="person",
    registry=registry,
)
result = pipeline.to_cosmos(
    endpoint="https://myaccount.documents.azure.com:443/",
    credential=DefaultAzureCredential(),
    database="ceds",
)
print(f"Loaded {result.succeeded}/{result.total} docs ({result.total_ru:.0f} RU)")
```

The container defaults to the shape name (`"person"`). You can override it:

```python
result = pipeline.to_cosmos(
    endpoint="https://myaccount.documents.azure.com:443/",
    credential="your-master-key",  # string key works for local emulator
    database="ceds",
    container="my_custom_container",
    partition_value="collection_2026",  # explicit partition key
    concurrency=50,                     # parallel upserts (default 25)
)
```

### Via CosmosLoader (advanced)

```python
from ceds_jsonld import CosmosLoader
from azure.identity.aio import DefaultAzureCredential

async with CosmosLoader(
    endpoint="https://myaccount.documents.azure.com:443/",
    credential=DefaultAzureCredential(),
    database="ceds",
    container="person",
) as loader:
    result = await loader.upsert_many(docs)
    # or one at a time:
    single = await loader.upsert_one(doc)
```

### Document preparation

If you need to prepare documents manually (e.g., for a different data store):

```python
from ceds_jsonld import prepare_for_cosmos

cosmos_doc = prepare_for_cosmos(jsonld_doc)
# cosmos_doc now has "id" (from @id) and "partitionKey" (from @type)
```

---

## Command-Line Interface

The library includes a full CLI for common workflows. Install with `pip install ceds-jsonld[cli]`.

### Convert data to JSON-LD

```bash
# CSV to JSON file
ceds-jsonld convert -s person -i students.csv -o students.json

# CSV to NDJSON (one document per line, ideal for streaming)
ceds-jsonld convert -s person -i students.csv -o students.ndjson

# Excel with sheet selection
ceds-jsonld convert -s person -i data.xlsx --sheet Enrollment -o out.json

# Compact output (no indentation)
ceds-jsonld convert -s person -i students.csv -o students.json --compact
```

### Validate data

```bash
# Pre-build validation (fast — checks types, required fields, allowed values)
ceds-jsonld validate -s person -i students.csv

# Full SHACL round-trip validation
ceds-jsonld validate -s person -i students.csv --shacl

# Sample-based validation for large files
ceds-jsonld validate -s person -i students.csv --shacl --mode sample --sample-rate 0.05
```

### Inspect SHACL shapes

```bash
# Human-readable shape tree
ceds-jsonld introspect --shacl ontologies/person/Person_SHACL.ttl

# JSON output
ceds-jsonld introspect --shacl Person_SHACL.ttl --json
```

### Generate mapping templates

```bash
# Generate a starter mapping YAML from a SHACL shape
ceds-jsonld generate-mapping --shacl Person_SHACL.ttl -o person_mapping.yaml

# With context file for human-readable property names
ceds-jsonld generate-mapping --shacl Person_SHACL.ttl --context-file person_context.json
```

### Other commands

```bash
# List available shapes
ceds-jsonld list-shapes

# Benchmark a shape (default: 100K records)
ceds-jsonld benchmark -s person
ceds-jsonld benchmark -s person -n 1000000
```

---

## SHACL Introspection

The `SHACLIntrospector` lets you examine SHACL shapes programmatically — useful for generating mapping templates, validating mappings, or building tooling:

```python
from ceds_jsonld import SHACLIntrospector

introspector = SHACLIntrospector("ontologies/person/Person_SHACL.ttl")

# See the full shape tree
for shape in introspector.shapes.values():
    print(f"{shape.name}: {len(shape.properties)} properties")

# Generate a starter mapping YAML from a SHACL shape
template = introspector.generate_mapping_template("PersonShape")

# Validate an existing mapping against the SHACL constraints
errors, warnings = introspector.validate_mapping(
    mapping_config=person_shape.mapping_config,
    shape_name="PersonShape",
)
```

---

## Lower-Level API

For advanced use cases, you can use the components individually instead of the Pipeline:

```python
from ceds_jsonld import ShapeRegistry, FieldMapper, JSONLDBuilder
from ceds_jsonld.serializer import write_json

# 1. Load shape
registry = ShapeRegistry()
person = registry.load_shape("person")

# 2. Create mapper and builder
mapper = FieldMapper(person.mapping_config)
builder = JSONLDBuilder(person)

# 3. Transform a row
raw_row = {"FirstName": "Jane", "LastName": "Doe", ...}
mapped = mapper.map(raw_row)
doc = builder.build_one(mapped)

# 4. Serialize
write_json(doc, "output/jane.json")
```

---

## Performance

The library is designed for high throughput. JSON-LD documents are built as plain Python dicts — no RDF graph construction, no JSON-LD compaction algorithms. This approach is **161x faster** than the rdflib + PyLD alternative (proven in our benchmarks).

| Operation | Time |
|-----------|------|
| Single record (map + build) | ~0.1 ms |
| 10,000 records | < 2 seconds |
| 100,000 records → NDJSON file | < 10 seconds |

JSON serialization uses [orjson](https://github.com/ijl/orjson) (Rust-backed, ~10x faster than stdlib `json`) when installed, with automatic fallback to stdlib.

---

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| 0 — Research | ✅ Complete | Performance benchmarks, architecture decisions |
| 1 — Core Foundation | ✅ Complete | Registry, mapper, builder, serializer. 89 tests. |
| 2 — SHACL Engine | ✅ Complete | Introspector, mapping templates, validation, overrides. 142 tests. |
| 3 — Data Ingestion | ✅ Complete | 6 source adapters, Pipeline class. 213 tests, 87% coverage. |
| 4 — Cosmos DB | ✅ Complete | CosmosLoader, Pipeline.to_cosmos(), document prep. 241 tests. |
| 5 — Validation | ✅ Complete | PreBuildValidator, SHACLValidator, 3 modes, Pipeline.validate(). 331 tests, 88% coverage. |
| 6 — CLI & Docs | ✅ Complete | Full CLI (6 commands), Sphinx API docs, user guides. 356 tests. |
| 7 — Production | ✅ Complete | Structured logging, PipelineResult metrics, dead-letter queue, progress tracking, PII masking, IRI sanitization. 398 tests. |
| 8 — Publishing | 🔄 In Progress | Open source on PyPI, GitHub Actions CI/CD, monthly releases. |

See [ROADMAP.md](ROADMAP.md) for the full plan.

---

## Optional Dependencies

| Extra | Packages | Purpose |
|-------|----------|---------|
| `fast` | orjson | 10x faster JSON serialization |
| `excel` | openpyxl | Excel file reading |
| `api` | httpx | REST API adapter |
| `database` | sqlalchemy | Database adapter |
| `cosmos` | azure-cosmos, azure-identity | Cosmos DB loading |
| `observability` | structlog, tqdm | Structured logging & progress bars |
| `validation` | pyshacl | SHACL validation |
| `cli` | click | Command-line interface |
| `all` | all of the above | Everything for production |
| `dev` | pytest, ruff, mypy, etc. | Development and testing |

---

## Development

```bash
# Clone and install
git clone https://github.com/daimare9/ceds-jsonld.git
cd ceds-jsonld
pip install -e ".[dev,cli]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src/ceds_jsonld --cov-report=term-missing

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Build documentation
cd docs
make html   # or on Windows: .\make.bat html
```

---

## License

MIT

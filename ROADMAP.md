# CEDS JSON-LD Generator Library — Full Roadmap

**Project:** `ceds-jsonld` — A Python library for ingesting education data from any source, mapping it to CEDS/CEPI ontology-backed RDF shapes, outputting conformant JSON-LD, and loading it into Azure Cosmos DB.

**Date:** February 8, 2026
**Status:** v1.0 Complete — v2.0 Phase 1 (Synthetic Data Generator) In Planning

---

## Table of Contents

1. [Vision & Goals](#1-vision--goals)
2. [Architecture Overview](#2-architecture-overview)
3. [Ontology & Shape Management Strategy](#3-ontology--shape-management-strategy)
4. [v1.0 Release History](#v10-release-history)
5. [v2.0 — Phase 1: Synthetic Data Generator](#v20--phase-1-synthetic-data-generator)
6. [v2.0 — Future Features (Backlog)](#v20--future-features-backlog)
7. [Key Technical Decisions](#key-technical-decisions)
8. [Risk Register](#risk-register)
9. [Dependency Map](#dependency-map)
10. [Appendix: Research Backlog](#appendix-research-backlog)

---

## 1. Vision & Goals

### The Problem

CEPI needs to ingest education data from diverse sources (APIs, spreadsheets, flat files, databases) across many different data collection shapes (Person, Organization, Student, Staff, K12 Enrollment, etc.). Each shape is backed by the [CEDS ontology](https://ceds.ed.gov/) as a base, extended by CEPI-specific properties and named individuals. Data must be:

1. **Mapped** to RDF-conformant structures defined by SHACL shapes
2. **Serialized** as compacted, human-readable JSON-LD with a hosted `@context`
3. **Validated** against the SHACL shapes before persistence
4. **Loaded** into Azure Cosmos DB as self-contained documents

### The Solution

A reusable Python library (`ceds-jsonld`) that provides:

- **Shape Registry** — Load and manage multiple SHACL shapes + their JSON-LD contexts + ontology extensions, each as a self-contained "collection definition"
- **Source Adapters** — Pluggable ingestion from CSV/Excel, REST APIs, databases, single-record dicts
- **Field Mapping Engine** — Declarative column-to-property mapping with transformations (type coercion, code list lookups, multi-value splitting)
- **JSON-LD Builder** — High-performance direct-dict construction (161x faster than rdflib+PyLD, proven in our benchmarks) driven by metadata extracted from SHACL shapes
- **SHACL Validator** — Optional pre-persist validation via pySHACL
- **Cosmos DB Loader** — Async bulk upsert to Azure Cosmos DB NoSQL API with partition key management
- **CLI & Scripting API** — Both programmatic and command-line interfaces

### Performance Target

Based on our prior benchmarking:

| Metric | Target |
|:---|:---|
| Single record build | < 0.05 ms |
| 1M records end-to-end (build + serialize + write) | < 60 seconds |
| Cosmos DB bulk upsert 100K records | < 5 minutes (at 10K RU/s) |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ceds-jsonld Library                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐   ┌───────────────┐   ┌────────────────────────┐ │
│  │  Source       │   │  Field        │   │  Shape Registry        │ │
│  │  Adapters     │──▶│  Mapping      │◀──│  (SHACL + Context +   │ │
│  │              │   │  Engine       │   │   Ontology Extensions) │ │
│  │  - CSV/Excel │   │              │   │                        │ │
│  │  - REST API  │   │  - Column    │   │  - PersonShape         │ │
│  │  - Database  │   │    mapping   │   │  - OrganizationShape   │ │
│  │  - Dict/JSON │   │  - Type      │   │  - K12EnrollmentShape  │ │
│  │  - NDJSON    │   │    coercion  │   │  - StaffShape          │ │
│  └──────────────┘   │  - Code list │   │  - ...N more           │ │
│                      │    lookups   │   └────────────────────────┘ │
│                      │  - Multi-val │                              │
│                      │    splitting │                              │
│                      └──────┬───────┘                              │
│                             │                                      │
│                      ┌──────▼───────┐                              │
│                      │  JSON-LD     │                              │
│                      │  Builder     │                              │
│                      │              │                              │
│                      │  Direct dict │                              │
│                      │  construction│                              │
│                      │  (no rdflib) │                              │
│                      └──────┬───────┘                              │
│                             │                                      │
│              ┌──────────────┼──────────────┐                       │
│              │              │              │                        │
│       ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐                │
│       │  SHACL      │ │  JSON    │ │  Cosmos DB  │                │
│       │  Validator  │ │  Output  │ │  Loader     │                │
│       │  (optional) │ │  (orjson)│ │  (async)    │                │
│       └─────────────┘ └──────────┘ └─────────────┘                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Ontology & Shape Management Strategy

### 3.1 File Organization Pattern

Each data collection shape will be a self-contained package:

```
ontologies/
├── base/
│   ├── CEDS-Ontology.rdf           # Full CEDS ontology (master reference)
│   ├── ceds_context.json           # Full CEDS JSON-LD context (26K lines)
│   └── Common.ttl                  # Shared CEPI extensions (RecordStatus, DataCollection, etc.)
│
├── person/
│   ├── Person_SHACL.ttl            # SHACL shape for Person + sub-shapes
│   ├── Person_CEPI_Extensions.ttl  # CEPI-specific named individuals, extra properties
│   ├── person_context.json         # JSON-LD context scoped to Person terms
│   ├── person_mapping.yaml         # Declarative field mapping config
│   └── person_sample.csv           # Sample data for testing
│
├── organization/
│   ├── Organization_SHACL.ttl
│   ├── Organization_CEPI_Extensions.ttl
│   ├── organization_context.json
│   ├── organization_mapping.yaml
│   └── organization_sample.csv
│
├── k12_enrollment/
│   ├── ...same pattern...
│
├── staff_assignment/
│   └── ...same pattern...
│
└── ... (one folder per collection shape)
```

### 3.2 Mapping Configuration (YAML-driven)

Each shape gets a declarative mapping file that the engine uses at runtime:

```yaml
# person_mapping.yaml
shape: PersonShape
context_url: "https://cepi-dev.state.mi.us/ontology/context-person.json"
context_file: person_context.json
base_uri: "cepi:person/"
id_source: PersonIdentifiers   # CSV column or field that provides the @id
id_transform: first_pipe_split  # take first value from pipe-delimited field

# Top-level type
type: Person

# Sub-shape mappings
properties:
  hasPersonName:
    type: PersonName
    cardinality: single          # one per person record
    include_record_status: true
    include_data_collection: true
    fields:
      FirstName:
        source: FirstName        # source column/field name
        target: FirstName        # JSON-LD term
        datatype: string
      MiddleName:
        source: MiddleName
        target: MiddleName
        datatype: string
        optional: true
      LastOrSurname:
        source: LastName
        target: LastOrSurname
        datatype: string
      GenerationCodeOrSuffix:
        source: GenerationCodeOrSuffix
        target: GenerationCodeOrSuffix
        datatype: string
        optional: true

  hasPersonBirth:
    type: PersonBirth
    cardinality: single
    include_record_status: true
    include_data_collection: true
    fields:
      Birthdate:
        source: Birthdate
        target: Birthdate
        datatype: xsd:date

  hasPersonSexGender:
    type: PersonSexGender
    cardinality: single
    include_record_status: true
    include_data_collection: true
    fields:
      hasSex:
        source: Sex
        target: hasSex
        transform: sex_prefix    # "Female" → "Sex_Female"

  hasPersonDemographicRace:
    type: PersonDemographicRace
    cardinality: multiple        # pipe-delimited groups
    split_on: "|"
    include_record_status: true
    include_data_collection: true
    fields:
      hasRaceAndEthnicity:
        source: RaceEthnicity
        target: hasRaceAndEthnicity
        transform: race_prefix   # "White" → "RaceAndEthnicity_White"
        multi_value_split: ","   # within each group, comma-separated

  hasPersonIdentification:
    type: PersonIdentification
    cardinality: multiple
    split_on: "|"
    include_record_status: true
    include_data_collection: true
    fields:
      PersonIdentifier:
        source: PersonIdentifiers
        target: PersonIdentifier
        datatype: xsd:token
      hasPersonIdentificationSystem:
        source: IdentificationSystems
        target: hasPersonIdentificationSystem
      hasPersonIdentifierType:
        source: PersonIdentifierTypes
        target: hasPersonIdentifierType

# Reusable sub-shapes applied when include_record_status/include_data_collection = true
record_status_defaults:
  type: RecordStatus
  RecordStartDateTime:
    value: "1900-01-01T00:00:00"
    datatype: xsd:dateTime
  RecordEndDateTime:
    value: "9999-12-31T00:00:00"
    datatype: xsd:dateTime
  CommittedByOrganization:
    value_id: "cepi:organization/3000000789"

data_collection_defaults:
  type: DataCollection
  value_id: "http://example.org/dataCollection/45678"
```

### 3.3 Why This Pattern?

- **Adding a new shape** = create a folder, write the SHACL, context, and YAML mapping. Zero library code changes.
- **Separation of concerns** — The SHACL is the canonical constraint definition (for validation). The YAML is the practical field mapping (for construction). The context.json is the semantic compaction layer (for JSON-LD).
- **CEPI extensions per shape** — Each shape can have its own named individuals, extra properties, etc., without polluting the global ontology.
- **Testable in isolation** — Each shape folder has its own sample data and can be tested independently.

---

## v1.0 Release History

> v1.0 development ran ~7 months across 9 phases. Detailed task tables, deliverable
> checklists, and per-issue bug fix notes are preserved in git history. Below is the
> compact summary.

| Phase | Focus | Key Deliverable |
|-------|-------|----------------|
| **0** | Research & PoC | Performance benchmarks, architecture decisions, go/no-go = GO |
| **1** | Core Foundation | Installable library: registry, mapper, builder, serializer. 89 tests, 90% coverage. |
| **2** | SHACL Engine | SHACLIntrospector, mapping templates, YAML validation, mapping overrides/composition, URI fetching. 142 tests, 91% coverage. |
| **3** | Ingestion Layer | 6 adapters (CSV, Excel, Dict, NDJSON, API, Database), Pipeline class, stream & batch modes. 210 tests, 87% coverage. |
| **4** | Cosmos Integration | CosmosLoader (async bulk upsert), prepare_for_cosmos, Pipeline.to_cosmos(). 241 tests. |
| **5** | Validation | PreBuildValidator + SHACLValidator, 3 validation modes, Pipeline.validate(). 331 tests, 88% coverage. |
| **6** | CLI & Docs | Full CLI (6 commands), Sphinx docs, 3 user guides, 5 ADRs. 356 tests. |
| **7** | Production Hardening | Structured logging, PipelineResult metrics, dead-letter queue, progress tracking, PII masking, IRI sanitization. 398 tests. |
| **8** | Open Source Publishing | Versioning (0.9.0+), PyPI publishing, GitHub Actions CI/CD, issue templates, CONTRIBUTING.md. |
| **—** | Pre-1.0 Stabilization | Bug fixes (#2–#30): transform hardening, validation improvements, adapter edge cases. **557 tests.** |

### Architectural Decisions Made in v1.0

1. **Direct dict construction** — 161x faster than rdflib + PyLD (0.02 ms/record vs. 7.2 ms)
2. **YAML mapping configs** — SHACL defines constraints; YAML defines source→target mappings
3. **orjson serialization** — 4-5x faster JSON output, stdlib fallback
4. **One Cosmos container per shape** — Tuned indexing/partitioning per query pattern
5. **Optional SHACL validation** — Lightweight pre-build for 100%; full pySHACL on sample

> **v1.0 completed February 2026.** All phases delivered, 557 tests passing, library
> published to PyPI as `ceds-jsonld` with extras: `[fast]`, `[excel]`, `[cosmos]`,
> `[validation]`, `[api]`, `[database]`, `[cli]`, `[observability]`, `[all]`.

---

<!-- BEGIN v2.0 -->

## v2.0 — Phase 1: Synthetic Data Generator

**Status:** 📋 Planning (Research Complete)
**Research:** See `ResearchFiles/FEATURE4_SYNTHETIC_DATA_RESEARCH.md` for full analysis.
**Target extras group:** `pip install ceds-jsonld[sdg]`

### Overview

Generate fully valid, realistic CEDS-conformant synthetic data for any registered shape.
Two-tier approach:

1. **Concept Scheme properties** (enumerated values like Sex, Race, GradeLevel) — extract
   valid `NamedIndividual` IRIs directly from the ontology RDF. Random selection, zero LLM cost.
2. **Literal value properties** (names, dates, IDs) — local LLM generates contextually
   appropriate values using ontology metadata (rdfs:label, dc:description, constraints).

**Runtime:** `llama-cpp-python` (in-process, no background service, loads/unloads with code).
Ollama auto-detected as power-user alternative. Three-tier fallback: LLM → cache → deterministic generators.

**Model:** Qwen3 4B default (~2.5 GB GGUF, auto-downloaded via `huggingface-hub` on first use).

### Task Table

| # | Task | Details |
|---|------|---------|
| 1.1 | `ConceptSchemeResolver` class | Parse ontology RDF, resolve `sh:in` IRIs → notation/label values from NamedIndividuals |
| 1.2 | `FallbackGenerators` module | Pure-Python generators for all XSD types + name-aware string defaults |
| 1.3 | `MappingAwareAssembler` class | Read mapping YAML, assemble CSV rows, handle pipe-delimited multi-value fields |
| 1.4 | `SyntheticDataGenerator` class | Core orchestrator: concept scheme + fallback generation |
| 1.5 | CSV + NDJSON output writers | Write to file or stdout |
| 1.6 | Round-trip integration tests | Generate CSV → Pipeline → JSON-LD → SHACL validate → pass |
| 1.7 | Add `[sdg]` extras to `pyproject.toml` | `llama-cpp-python>=0.3`, `huggingface-hub>=0.20` |
| 1.8 | `OntologyMetadataExtractor` class | Extract rdfs:label, dc:description, maxLength, rangeIncludes from ontology for prompt context |
| 1.9 | `LLMValueGenerator` class | Build prompts from metadata, call llama-cpp-python with JSON schema enforcement, parse responses |
| 1.10 | Ollama auto-detection | If Ollama is running on localhost:11434, prefer it over in-process llama-cpp-python |
| 1.11 | File-based caching layer | `~/.ceds_jsonld/cache/` with model-keyed entries; cache LLM-generated values for reuse |
| 1.12 | Three-tier fallback logic | LLM (in-process or Ollama) → cache → deterministic fallback generators |
| 1.13 | Post-generation validation | Verify LLM values match datatype constraints (maxLength, date format, numeric ranges) |
| 1.14 | `generate-sample` CLI command | Options: `--shape`, `--count`, `--format`, `--model`, `--seed`, `--no-llm`, `--cache-dir` |
| 1.15 | `generate-cache` CLI command | Pre-warm cache for CI environments (no LLM needed at CI time) |
| 1.16 | Ship default Person cache | Commit pre-generated cache files for zero-setup CI |
| 1.17 | Streaming mode | Iterator/generator pattern for 100K+ row generation |
| 1.18 | JSON-LD output mode | Generate → Pipeline → JSON-LD documents (end-to-end) |
| 1.19 | Benchmark suite | Time: LLM generation, cached generation, 10K/100K/1M row assembly |
| 1.20 | Model comparison tests | Test Qwen3 4B vs. Granite4 3B vs. Phi-4 Mini for value quality |
| 1.21 | Distribution profiles | Optional YAML config for demographic distributions |
| 1.22 | Documentation | Sphinx docs, README examples, getting-started guide |

### Deliverables

- [ ] `ConceptSchemeResolver` + `FallbackGenerators` — zero-LLM synthetic data for any shape
- [ ] `LLMValueGenerator` + `OntologyMetadataExtractor` — LLM-powered realistic literals
- [ ] Caching layer — generate once, reuse everywhere (including CI)
- [ ] CLI commands: `generate-sample`, `generate-cache`
- [ ] `[sdg]` extras group in `pyproject.toml`
- [ ] Round-trip tests: generated data passes full Pipeline + SHACL validation
- [ ] Benchmark: LLM vs. cached vs. fallback generation speed
- [ ] Docs: user guide, API reference, README section

### End-User Experience

**Install:**
```bash
pip install ceds-jsonld[sdg]
```

**Python API:**
```python
from ceds_jsonld import Pipeline, SyntheticDataGenerator

gen = SyntheticDataGenerator("Person")
df = gen.generate(count=500)  # pandas DataFrame, ready for Pipeline
```

**CLI:**
```bash
ceds-jsonld generate-sample --shape Person --count 1000 --format csv -o sample.csv
ceds-jsonld generate-sample --shape Person --count 50 --format jsonld -o sample.jsonld
```

Under the hood: first run auto-downloads model (~2.5 GB), subsequent runs use cache.
No background service, no `ollama pull`, no config files.

---

## v2.0 — Future Features (Backlog)

**Status:** 💡 Brainstorming / Feasibility Research

These are **candidate features** for v2.1+ and beyond. Nothing here is committed —
each item needs dedicated research, feasibility analysis, and prioritization before
being promoted to a real phase.

---

### Feature 1: AI-Assisted Mapping Wizard

> *The one that makes people say "holy shit."*

- Feed a CSV/Excel sample → LLM suggests field → CEDS shape mappings + transform code snippets.
- One-click "apply & preview JSON-LD" in CLI or a lightweight Streamlit/Gradio UI.

**Research needed:**
- [ ] LLM provider strategy (local vs. cloud, cost, latency)
- [ ] Prompt engineering for CEDS-specific mapping suggestions
- [ ] Confidence scoring / human-in-the-loop approval flow
- [ ] Privacy implications (sending PII column names to cloud LLMs)

---

### Feature 2: Visual Mapping Dashboard (Web UI)

- Drag-and-drop column → shape property with live JSON-LD preview.
- "Save mapping profile" → reusable YAML that the library can load.

**Research needed:**
- [ ] Framework choice (Streamlit, Gradio, FastAPI + React, Panel)
- [ ] Hosting model (local-only, optional cloud, embeddable)
- [ ] Integration with existing YAML mapping config format
- [ ] Scope boundary — keep the library headless, ship UI as a separate package?

---

### Feature 3: Verifiable Credentials (VC) Generator

- Turn a Person + Enrollment + Course record into a W3C Verifiable Credential.
- Built-in support for Open Badges 3.0 / CLR 2.0.

**Research needed:**
- [ ] W3C VC Data Model 2.0 compatibility
- [ ] DID method support (did:web, did:key, did:ion)
- [ ] Open Badges 3.0 / CLR 2.0 spec alignment with CEDS shapes
- [ ] Signing libraries (PyJWT, didkit) + key management

---

### Feature 5: Multi-format Round-trip (JSON-LD ↔ RDF ↔ CSV/Parquet)

- `to_turtle()`, `to_rdf_graph()`, `from_rdf()` — one-liner triplestore/SPARQL integration.

**Research needed:**
- [ ] rdflib round-trip fidelity (context compaction loss?)
- [ ] Parquet schema generation from SHACL shapes
- [ ] SPARQL query patterns for CEDS data
- [ ] Triplestore compatibility (GraphDB, Stardog, Oxigraph, Fuseki)

---

### Feature 6: CEDS Version Migration Tool

- Auto-detect source CEDS version → target version. Apply predefined migration rules.

**Research needed:**
- [ ] CEDS versioning scheme and changelog analysis
- [ ] Breaking vs. non-breaking changes between CEDS releases
- [ ] Migration rule format (declarative YAML? Python transforms?)

---

### Feature 7: Native Adapters People Actually Use

- Google Sheets, SIS platforms (PowerSchool, Canvas, Blackbaud), cloud warehouses (Snowflake, BigQuery), streaming (Kafka, Event Hubs).

**Research needed:**
- [ ] API authentication patterns for each SIS platform
- [ ] Spark DataFrame → adapter bridge (lazy evaluation)
- [ ] Kafka consumer group management + Event Hubs partition strategy

---

### Feature 8: Observability That Actually Matters

- OpenTelemetry traces + metrics, Grafana dashboard, PII leakage alerts.

**Research needed:**
- [ ] OpenTelemetry Python SDK integration patterns
- [ ] Span design: per-record vs. per-batch vs. per-pipeline-stage
- [ ] Compatibility with Azure Monitor / Application Insights exporters

---

### Feature 9: Community Shape Marketplace / Contrib System

- `ceds-jsonld list-shapes --remote` — pull community shapes from a central repo.

**Research needed:**
- [ ] Shape packaging format and versioning
- [ ] Central registry (GitHub org? PyPI sub-packages? OCI artifacts?)
- [ ] Governance model for community shapes

---

### Feature 10: PyPI + Conda + Docker + One-click Deploy

- Docker image with all extras, Helm chart / Azure Container App template.

**Research needed:**
- [ ] Docker image size optimization (slim base, multi-stage build)
- [ ] Conda-forge recipe and submission process
- [ ] ARM/Bicep template for full infra (Cosmos + Container App + Key Vault)

---

### Quick-Wins

| # | Feature | Notes |
|---|---------|-------|
| QW-1 | `--validate-only` mode with HTML report | Beautiful pass/fail per record, SHACL violations highlighted |
| QW-2 | `introspect` → Markdown table output | Every shape + required properties in copy-paste-ready table |
| QW-3 | Built-in `benchmark` command | Compare pipeline run vs. baseline, auto-generate speedup report |

---

### v2.0+ Prioritization

> With Synthetic Data Generator committed as v2.0 Phase 1, remaining features will be
> prioritized after Phase 1 ships. Scoring criteria: **impact** (user value) vs.
> **effort** (dev weeks), with dependencies between features considered.

---

---

## Key Technical Decisions

### Decision 1: Direct Dict Construction (Not rdflib+PyLD)

**Decision:** Build JSON-LD documents as plain Python dicts, not through rdflib graph creation + PyLD compaction.

**Rationale:** Our benchmarking proved:
- Direct dict: **0.02 ms/record** (161x faster)
- rdflib + PyLD: **7.2 ms/record**
- 1M records: **33 seconds** vs **2+ hours**

PyLD is the bottleneck (73.4% of time) due to context re-parsing on every call (GitHub issue #85, open since 2018).

**Tradeoff:** We lose the ability to produce an RDF graph as an intermediate. SHACL validation requires reconstituting a graph from the JSON-LD. We handle this by making validation a separate, optional step.

### Decision 2: YAML Mapping Config (Not Pure SHACL)

**Decision:** Use YAML mapping files alongside SHACL, not SHACL alone.

**Rationale:** SHACL defines *constraints* (what is valid), not *mappings* (where data comes from). SHACL cannot express:
- Which CSV column maps to which property
- How to split pipe-delimited values
- What transform to apply ("Female" → "Sex_Female")
- Default values for RecordStatus/DataCollection

SHACL *can* be used to auto-generate a mapping template skeleton and to validate the mapping config.

### Decision 3: orjson for Serialization

**Decision:** Use `orjson` (Rust-backed) for JSON serialization, falling back to stdlib `json`.

**Rationale:** 4-5x faster at scale. At 1M records, saves ~15 seconds of serialization time.

### Decision 4: One Cosmos Container Per Shape

**Decision:** Create a separate Cosmos DB container for each shape type (person, organization, etc.).

**Rationale:**
- Each shape has different query patterns → different indexing needs
- Partition key can be tuned per shape (e.g., `orgId` for organization, `collectionId` for person)
- TTL policies may differ per data collection type
- Cleaner cost attribution

### Decision 5: Optional SHACL Validation

**Decision:** SHACL validation is opt-in, not a required pipeline step.

**Rationale:** pySHACL validation costs ~50ms/record (requires materializing an rdflib graph from JSON-LD). For bulk loads of 1M records, that's ~14 hours of validation time. Instead:
- Use lightweight pre-build validation (schema checks from introspected SHACL) for 100% of records
- Use full SHACL validation on a configurable sample (e.g., 1%) or in a post-load quality gate

---

## Risk Register

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|------------|------------|
| R1 | SHACL shapes vary too much across collections to have a generic builder | High | Medium | Phase 0.4 tests with 2+ shapes; YAML mapping absorbs structural differences |
| R2 | Cosmos DB query performance on nested JSON-LD is poor | High | Low | Test early with emulator (Phase 0.3). Consider flattening for query-heavy fields. |
| R3 | Python SDK async bulk performance for Cosmos is insufficient | Medium | Medium | Benchmark in Phase 4. Fallback: batch via Azure Functions or .NET SDK bridge. |
| R4 | CEPI extension ontologies are not yet stable | Medium | High | The YAML mapping layer insulates builder from ontology changes. Only context.json needs updating. |
| R5 | pySHACL validation is too slow for inline use | Medium | High (confirmed) | Already mitigated: sample-based validation, lightweight pre-build checks. |
| R6 | Context URL hosting becomes a dependency | Low | Medium | Support embedded context mode as fallback. Cache contexts locally. |
| R7 | Shape definitions need to support versioning over time | Medium | Medium | Add `version` field to mapping YAML. Cosmos documents include `@context` URL which implicitly versions. |
| R8 | Local LLM model too large for user's hardware | Medium | Medium | Default model is ~2.5 GB; fallback generators produce valid data without LLM. `--no-llm` flag bypasses entirely. |
| R9 | PyPI package size limit (100 MB) prevents bundling model | Low | High (confirmed) | Model auto-downloaded via `huggingface-hub` on first use. Pre-generated cache ships for CI. |
| R10 | LLM-generated values fail SHACL validation | Medium | Medium | Post-generation validation checks constraints. Invalid values fall back to deterministic generators. |

---

## Dependency Map

### Runtime Dependencies

| Package | Purpose | Required? |
|---------|---------|-----------|
| `orjson` | Fast JSON serialization | Optional (falls back to stdlib) |
| `pyyaml` | Mapping config parsing | Required |
| `rdflib` | SHACL introspection, round-trip validation | Required |
| `pandas` | CSV/Excel adapter | Required |
| `openpyxl` | Excel .xlsx support | Optional (`[excel]`) |
| `httpx` | REST API adapter | Optional (`[api]`) |
| `azure-cosmos` | Cosmos DB loader | Optional (`[cosmos]`) |
| `azure-identity` | Azure auth | Optional (`[cosmos]`) |
| `pyshacl` | Full SHACL validation | Optional (`[validation]`) |
| `click` | CLI | Optional (`[cli]`) |
| `structlog` | Structured logging | Optional |
| `tqdm` | Progress bars | Optional |
| `llama-cpp-python` | Local LLM inference (synthetic data) | Optional (`[sdg]`) |
| `huggingface-hub` | Model auto-download | Optional (`[sdg]`) |

### Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Testing |
| `pytest-cov` | Coverage |
| `hypothesis` | Property-based testing |
| `ruff` | Linting & formatting |
| `mypy` | Type checking |
| `mkdocs` | Documentation |

---

## Appendix: Research Backlog

These are open questions that should be investigated as the project progresses:

### A.1 JSON-LD 1.1 Features

- [ ] Can we use `@nest` to group properties without creating new nodes? (e.g., group name fields under a "name" key without a separate PersonName type)
- [ ] Can `@import` in contexts reduce duplication across shape-specific contexts?
- [ ] Does `@container: @set` help normalize arrays (always array vs. sometimes single value)?

### A.2 Alternative Validation Approaches

- [ ] **JSON Schema from SHACL**: Generate a JSON Schema from the SHACL shape for ultra-fast validation (no RDF round-trip). Tools: `shacl2jsonschema` or custom.
- [ ] **Pydantic models from SHACL**: Generate Pydantic models for type-safe, fast Python object validation.
- [ ] **Cosmos DB stored procedures**: Server-side validation on upsert.

### A.3 Graph Database Integration

- [ ] If CEPI ever needs *graph* queries (traverse person→organization→school relationships), consider:
  - Azure Cosmos DB Gremlin API (graph queries on same data)
  - Apache Jena / Oxigraph for SPARQL endpoints
  - Neo4j import from JSON-LD

### A.4 Change Data Capture

- [ ] Cosmos DB Change Feed for propagating data changes to downstream systems
- [ ] Event-driven architecture: new JSON-LD document → Azure Function → notification/ETL

### A.5 CEDS Ontology Evolution

- [ ] How will CEDS ontology updates (new properties, deprecated terms) propagate through the system?
- [ ] Recommended: version-pin ontology files, test against new versions in CI, explicit migration step

### A.6 Data Quality Dashboard

- [ ] Web UI showing: records processed, validation error rates, per-shape statistics
- [ ] Integration with Azure Monitor / Application Insights

---

## Summary Timeline

| Phase | Status | Key Deliverable |
|-------|--------|----------------|
| **v1.0 (Phases 0–8)** | ✅ Complete | Full library: registry, mapper, builder, serializer, 6 adapters, Cosmos loader, validation, CLI, docs, CI/CD. 557 tests. |
| **v2.0 Phase 1** | 📋 Planning | Synthetic Data Generator — concept scheme extraction + local LLM, `[sdg]` extras, CLI commands. |

---

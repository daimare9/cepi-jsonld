# Feature 4: Synthetic Data Generator — Revised Deep Dive Research

**Date:** February 8, 2026
**Branch:** `research/feature4-synthetic-data-generator`
**Status:** Research Complete — Revised Approach (LLM-Assisted Generation)

---

## 1. Executive Summary

Build a **hybrid synthetic data generator** that uses two distinct strategies based
on the property type in the CEDS ontology:

1. **Concept Scheme properties (object properties with `sh:in`)** — Deterministic
   random selection from the full set of `owl:NamedIndividual` members of the concept
   scheme. No AI needed. The ontology already contains ~19,500 NamedIndividuals across
   hundreds of concept schemes. We just randomly select from the enum.

2. **Literal value properties (strings, dates, tokens, etc.)** — Use a **lightweight
   local LLM** running in-process via `llama-cpp-python` to generate contextually-appropriate
   values. The LLM receives the ontology metadata for each property (label, description,
   definition, datatype, maxLength, textFormat) and returns structured JSON arrays of
   realistic values. The model auto-downloads on first use — no external services needed.

**Why this is better than the Faker approach:**
- Faker requires hand-coded per-property generators that break when new shapes are added.
- An LLM reading `rdfs:label: "First Name"` + `dc:description: "The full legal first name
  given to a person at birth..."` + `maxLength: 75` can generate realistic first names
  **without any property-specific code**.
- The generator becomes **truly generic** — add any new CEDS shape and it generates
  valid data automatically, because the LLM reads the ontology metadata.

---

## 2. The Two Property Categories in CEDS

Auditing the CEDS ontology (258,596 lines, 2,301 properties, 19,489 NamedIndividuals)
reveals a clean split:

### 2.1 Concept Scheme Properties (Enumerated — Easy)

These are object properties whose range is a CEDS class (concept scheme). The valid
values are the `owl:NamedIndividual` members of that class. In SHACL, they appear as
`sh:in` lists.

**Example — `hasPersonIdentificationSystem` (P001571):**

```turtle
ceds:hasPersonIdentificationSystemShape a sh:PropertyShape ;
    sh:in ( ceds:NI001571173132 ceds:NI001571173129 ... cepi:NI001571100001 ) ;
    sh:path ceds:P001571 .
```

Each NamedIndividual in the ontology has rich metadata:
```xml
<owl:NamedIndividual rdf:about="http://ceds.ed.gov/terms#NI001571173116">
    <rdf:type rdf:resource="http://ceds.ed.gov/terms#C001571" />
    <rdf:type rdf:resource="http://www.w3.org/2004/02/skos/core#Concept" />
    <rdfs:label>Canadian Social Insurance Number</rdfs:label>
    <dc:description>The related Person Identifier uses the person's Canadian
        Social Insurance Number.</dc:description>
    <skos:notation>CanadianSIN</skos:notation>
    <skos:prefLabel>Canadian Social Insurance Number</skos:prefLabel>
    <skos:inScheme rdf:resource="http://ceds.ed.gov/terms#C001571"/>
</owl:NamedIndividual>
```

**Generation strategy:** Parse the `sh:in` list from SHACL → resolve each IRI to its
`skos:notation` or `rdfs:label` → randomly select. Zero LLM involvement needed.
This is fast, deterministic, and guaranteed correct.

### 2.2 Literal Value Properties (Need Generated Data)

These are datatype properties whose range is an XSD type (`xsd:string`, `xsd:date`,
`xsd:token`, etc.). The ontology describes what the value *means* but doesn't
enumerate valid values.

**Example — `FirstName` (P000115):**

```xml
<rdf:Property rdf:about="http://ceds.ed.gov/terms#P000115">
    <rdfs:label>First Name</rdfs:label>
    <schema:rangeIncludes rdf:resource="http://www.w3.org/2001/XMLSchema#string" />
    <skos:notation>FirstName</skos:notation>
    <dc:description>The full legal first name given to a person at birth,
        baptism, or through legal change.</dc:description>
    <maxLength>75</maxLength>
    <textFormat>Alphanumeric</textFormat>
</rdf:Property>
```

**Example — `Birthdate` (P000033):**

```xml
<rdf:Property rdf:about="http://ceds.ed.gov/terms#P000033">
    <rdfs:label>Birthdate</rdfs:label>
    <schema:rangeIncludes rdf:resource="http://www.w3.org/2001/XMLSchema#date" />
    <skos:notation>Birthdate</skos:notation>
    <dc:description>The year, month and day on which a person was born.</dc:description>
    <textFormat>YYYY-MM-DD</textFormat>
</rdf:Property>
```

**Generation strategy:** Send the property metadata to a local LLM with a structured
JSON output schema → get back an array of realistic values → cache and draw from them.

---

## 3. Revised Architecture

### 3.1 High-Level Design

```
┌───────────────────────────────────────────────────────────────────┐
│                     SyntheticDataGenerator                        │
│                                                                   │
│  ┌───────────────┐   ┌────────────────────────────────────────┐  │
│  │ ShapeRegistry  │──>│  SHACLIntrospector                     │  │
│  │ (load shape)   │   │  (extract constraints, sh:in lists)   │  │
│  └───────────────┘   └─────────────┬──────────────────────────┘  │
│                                    │                              │
│                   ┌────────────────┴────────────────┐            │
│                   │                                  │            │
│          ┌────────v─────────┐            ┌──────────v─────────┐  │
│          │  ConceptScheme    │            │  LiteralValue       │  │
│          │  Generator        │            │  Generator          │  │
│          │                   │            │                     │  │
│          │  sh:in → random   │            │  OntologyMetadata   │  │
│          │  select from      │            │  → LLM prompt       │  │
│          │  NamedIndividuals │            │  → structured JSON  │  │
│          │                   │            │  → value cache       │  │
│          │  ⚡ No LLM needed │            │  🤖 Local LLM       │  │
│          └────────┬─────────┘            └──────────┬─────────┘  │
│                   │                                  │            │
│                   └────────────────┬────────────────┘            │
│                                    │                              │
│                        ┌───────────v────────────┐                │
│                        │  MappingAwareAssembler   │                │
│                        │  reads mapping YAML      │                │
│                        │  assembles CSV rows       │                │
│                        │  handles pipe-delimited   │                │
│                        │  multi-value fields       │                │
│                        └───────────┬────────────┘                │
│                                    │                              │
│                        ┌───────────v────────────┐                │
│                        │  OutputWriter            │                │
│                        │  CSV / NDJSON / JSON-LD  │                │
│                        └────────────────────────┘                │
└───────────────────────────────────────────────────────────────────┘
```

### 3.2 The LLM Value Generation Flow

For literal properties, the LLM generates values in bulk, not per-record:

```
1. Introspect shape → identify all literal properties
2. For each literal property:
   a. Extract metadata from ontology:
      - rdfs:label, dc:description, skos:definition
      - schema:rangeIncludes (XSD datatype)
      - maxLength, textFormat
      - Parent class context (e.g., "PersonName" → education domain)
   b. Build a structured prompt (see Section 4)
   c. Call local LLM with JSON schema constraint
   d. Receive array of N values
   e. Cache the values (keyed by property IRI + shape context)
3. For each record to generate:
   a. For enumerated properties → random.choice(named_individuals)
   b. For literal properties → random.choice(cached_llm_values)
   c. Assemble into CSV row per mapping YAML
```

**Key insight: Generate-then-sample.** We call the LLM once per property to generate
a pool of (e.g.) 200 values, then randomly sample from that pool for each record.
Generating 10,000 records does NOT mean 10,000 LLM calls — it means ~5-10 LLM calls
(one per literal property) that each return 200 values, then pure random selection.

---

## 4. LLM Prompt Design

### 4.1 The Prompt Template

```
You are a synthetic data generator for education data systems.

Generate exactly {count} realistic values for the following CEDS
(Common Education Data Standards) property:

Property: {rdfs:label}
Description: {dc:description}
Definition: {skos:definition}  (if available)
Data Type: {schema:rangeIncludes → human readable}
Format: {textFormat}  (if available)
Max Length: {maxLength}  (if available)
Parent Class: {parent class rdfs:label}

Context: This data is used in US K-12 and postsecondary education records
managed by state education agencies.

Requirements:
- Values must be realistic and diverse (not repetitive)
- Values must conform to the data type and format constraints
- For string values: respect the max length
- For date values: use ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
- For numeric tokens: generate realistic ID numbers
- Return ONLY the JSON array, no explanation

Return your response as a JSON object matching this schema.
```

### 4.2 The JSON Schema Constraint

```json
{
  "type": "object",
  "properties": {
    "values": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 200,
      "maxItems": 200
    }
  },
  "required": ["values"]
}
```

### 4.3 Example: Prompting for "First Name"

**Prompt:**
```
Generate exactly 200 realistic values for the following CEDS property:

Property: First Name
Description: The full legal first name given to a person at birth, baptism,
    or through legal change.
Data Type: string
Format: Alphanumeric
Max Length: 75
Parent Class: PersonName

Context: This data is used in US K-12 and postsecondary education records.
Ensure the names are diverse and representative of US school populations.
```

**Expected LLM response (JSON-constrained):**
```json
{
  "values": [
    "Maria", "James", "Aiden", "Sophia", "DeShawn", "Yuki", "Mohammed",
    "Isabella", "Carlos", "Priya", "Liam", "Aaliyah", "Wei", "Fatima",
    "Connor", "Valentina", "Jayden", "Amara", "Lucas", "Mei-Ling", ...
  ]
}
```

### 4.4 Example: Prompting for "Birthdate"

**Prompt:**
```
Generate exactly 200 realistic values for the following CEDS property:

Property: Birthdate
Description: The year, month and day on which a person was born.
Data Type: date
Format: YYYY-MM-DD
Parent Class: PersonBirth

Context: This data is for K-12 and postsecondary education records.
Generate dates spanning realistic ages for students (5-22) and staff (22-70).
```

**Expected response:**
```json
{
  "values": [
    "2018-03-15", "2012-11-22", "2001-07-08", "1978-01-30", "2015-09-04",
    "1985-12-17", "2010-06-25", "1992-04-11", "2019-02-28", "1970-08-19", ...
  ]
}
```

---

## 5. LLM Runtime Options — Detailed Comparison

### 5.1 Option A: llama-cpp-python + huggingface-hub (Recommended)

| Aspect | Details |
|--------|---------|
| **What** | Python ctypes bindings to llama.cpp — runs the model **in-process**, no server or background service |
| **Install** | `pip install llama-cpp-python huggingface-hub` — pre-built Windows wheels available on PyPI |
| **Structured JSON** | `response_format={"type": "json_object", "schema": {...}}` — GBNF grammar engine constrains tokens at generation time |
| **Model management** | `Llama.from_pretrained()` auto-downloads GGUF from HuggingFace Hub to `~/.cache/huggingface/` on first use |
| **Memory** | 1B model ≈ 1GB RAM, 4B ≈ 3GB, 8B ≈ 6GB — loaded on demand, freed when done |
| **GPU support** | Pre-built wheels include CUDA support; falls back to CPU automatically |
| **No background service** | Model loads when code runs, unloads when code exits — **zero footprint when idle** |
| **Maturity** | 10K+ GitHub stars, active development, same llama.cpp backend used by Ollama |
| **Downside** | Larger pip install (~20-30MB compiled binary); some Windows machines may need the Visual C++ Redistributable |

**Why this is the right default for end users:**
- `pip install ceds-jsonld[sdg]` is the **only install step** — no external binary, no service, no `ollama pull`
- The model auto-downloads on first use with a progress bar, cached permanently
- When the user's code finishes, **nothing remains running** — no tray icon, no background service, no VRAM held
- For someone who generates synthetic data once a month, this is the respectful approach

**Python usage:**
```python
from llama_cpp import Llama

# Auto-downloads model on first use (~2.6GB), cached in ~/.cache/huggingface/
llm = Llama.from_pretrained(
    repo_id="Qwen/Qwen3-4B-GGUF",
    filename="*q4_k_m.gguf",
    n_ctx=4096,
)
result = llm.create_chat_completion(
    messages=[{"role": "user", "content": prompt}],
    response_format={
        "type": "json_object",
        "schema": {
            "type": "object",
            "properties": {"values": {"type": "array", "items": {"type": "string"}}},
            "required": ["values"],
        },
    },
    temperature=0.8,
)
```

### 5.2 Option B: Ollama (Power-User Alternative)

| Aspect | Details |
|--------|---------|
| **What** | Local LLM server with REST API, native structured output support |
| **Install** | Separate binary install: `winget install Ollama.Ollama` + `ollama pull qwen3:4b` |
| **Structured JSON** | Native `format` parameter accepts JSON schema — grammar-constrained at token level |
| **Python client** | `pip install ollama` — 1st-party, Pydantic-friendly |
| **Models** | Pull any GGUF model: `ollama pull qwen3:4b` |
| **GPU support** | Auto-detects CUDA, ROCm, Metal; falls back to CPU |
| **Startup** | Runs as background Windows service — **always on, even when not needed** |
| **Maturity** | 78K+ GitHub stars, massive community |
| **Downside** | Background service consumes ~200MB RAM when idle; keeps last model warm in VRAM; 3-step install process |

**When Ollama makes sense:** For users who already run Ollama for other projects and
want to share the same model cache. Our code auto-detects Ollama via
`shutil.which("ollama")` and uses it if available, preferring it over in-process
loading for faster warm-start times.

**Python usage with structured output:**
```python
from ollama import chat
from pydantic import BaseModel

class GeneratedValues(BaseModel):
    values: list[str]

response = chat(
    model="qwen3:4b",
    messages=[{"role": "user", "content": prompt}],
    format=GeneratedValues.model_json_schema(),
)
result = GeneratedValues.model_validate_json(response.message.content)
# result.values is guaranteed to be list[str] — grammar-enforced
```

### 5.3 Option C: Outlines (Grammar-Constrained Generation)

| Aspect | Details |
|--------|---------|
| **What** | Library for guaranteed-valid structured generation from any LLM |
| **Install** | `pip install outlines` |
| **Structured JSON** | Compiles JSON schema → finite-state machine → token-level enforcement. Zero chance of invalid JSON. |
| **Models** | Works with transformers models (HuggingFace), vLLM, Ollama, OpenAI |
| **Unique strength** | Can enforce regex patterns, CFG grammars, not just JSON schema |
| **Downside** | Heavier dependency (pulls in torch if using local transformers); overkill if Ollama handles it natively |
| **Stars** | 13.4K |

**Python usage:**
```python
import outlines
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

class GeneratedValues(BaseModel):
    values: list[str]

model = outlines.from_transformers(
    AutoModelForCausalLM.from_pretrained("microsoft/Phi-3-mini-4k-instruct"),
    AutoTokenizer.from_pretrained("microsoft/Phi-3-mini-4k-instruct"),
)
result = model(prompt, GeneratedValues)
```

### 5.4 Option D: Instructor + Ollama (Structured Extraction Layer)

| Aspect | Details |
|--------|---------|
| **What** | Pydantic-based structured output wrapper for any LLM provider |
| **Install** | `pip install instructor` |
| **How** | Adds automatic validation, retry on Pydantic errors, streaming |
| **Works with** | OpenAI, Anthropic, Ollama, llama-cpp-python, Gemini, etc. |
| **Stars** | 12.3K |
| **Downside** | Another dependency layer; Ollama's native structured output already does most of this |

### 5.5 Comparison Matrix

| Criteria | llama-cpp-python | Ollama | Outlines | Instructor+Ollama |
|----------|------------------|--------|----------|-------------------|
| **Install ease (Windows)** | ⭐⭐⭐⭐ (pre-built wheels) | ⭐⭐⭐ (3-step external install) | ⭐⭐⭐ (pulls torch) | ⭐⭐⭐ (needs Ollama) |
| **`pip install` only** | ✅ everything via pip | ❌ needs external binary + model pull | ✅ but huge | ❌ needs Ollama |
| **Structured JSON** | ⭐⭐⭐⭐⭐ native GBNF | ⭐⭐⭐⭐⭐ native GBNF | ⭐⭐⭐⭐⭐ strongest | ⭐⭐⭐⭐ via Ollama |
| **Background service** | ❌ none (in-process) | ⚠️ always-on Windows svc | ❌ none | ⚠️ always-on |
| **Idle footprint** | 0 MB | ~200 MB RAM + VRAM | 0 MB | ~200 MB RAM |
| **Model auto-download** | ✅ via huggingface-hub | ❌ manual `ollama pull` | ✅ via HF | ❌ manual |
| **Model flexibility** | ⭐⭐⭐⭐⭐ any GGUF | ⭐⭐⭐⭐⭐ any GGUF | ⭐⭐⭐⭐ HF/vLLM | ⭐⭐⭐⭐⭐ any provider |
| **Community/stability** | ⭐⭐⭐⭐ (10K stars) | ⭐⭐⭐⭐⭐ (78K stars) | ⭐⭐⭐⭐ (13.4K stars) | ⭐⭐⭐⭐ (12.3K stars) |
| **End-user friendliness** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

### 5.6 Recommendation: **llama-cpp-python** (primary) + **Ollama** (auto-detected alternative)

**Primary:** `llama-cpp-python` + `huggingface-hub` as the default LLM runtime.

Reasons:
1. **Single `pip install`** — `pip install ceds-jsonld[sdg]` is the only step. No
   external binary download. No `ollama pull`. No service configuration.
2. **No background service** — the model loads when the user's code runs and unloads
   when it finishes. Nothing sits in the system tray eating RAM and VRAM when idle.
   For someone who generates synthetic data once a month, this is the respectful approach.
3. **Auto-download model** — `Llama.from_pretrained()` pulls the GGUF from HuggingFace
   Hub on first use with a progress bar, cached permanently at `~/.cache/huggingface/`.
   Subsequent loads are ~3 seconds from disk.
4. **Same engine** — llama-cpp-python uses the exact same llama.cpp backend and GBNF
   grammar engine as Ollama. Identical JSON schema enforcement, identical model support.
5. **Pre-built Windows wheels** — PyPI has pre-built wheels for Windows x64 with CUDA.
   Most users won't need a C compiler.

**Auto-detected alternative:** If Ollama is already running on the user's machine
(detected via `shutil.which("ollama")` or a quick `httpx.get("http://localhost:11434")`),
prefer it for faster warm-start times. Power users who already have Ollama get the
best of both worlds.

**Fallback:** If neither `llama-cpp-python` nor Ollama is available, fall back to
cached values or built-in generators (see Section 8).

---

## 6. Model Selection for Structured JSON Generation

### 6.1 The Task Characteristics

Our generation task is:
- **Low complexity** — generating lists of names, dates, IDs (not reasoning or coding)
- **Highly constrained** — output must match a JSON schema exactly
- **Batch-oriented** — one call per property type, requesting 200 values
- **Domain-specific** — education context, US demographics
- **Prompt is short** — ~200 tokens input, ~2000 tokens output

This means we want: **small, fast, instruction-following models with strong JSON adherence.**

### 6.2 Recommended Models

| Model | Size | VRAM | Speed (est.) | JSON Quality | Notes |
|-------|------|------|-------------|-------------|-------|
| **Qwen3 4B** | 2.6GB Q4 | ~3GB | ~80 tok/s | ⭐⭐⭐⭐⭐ | Best small model for structured output; native tool calling; thinking mode can be disabled for speed |
| **Phi-4 Mini 3.8B** | 2.4GB Q4 | ~3GB | ~90 tok/s | ⭐⭐⭐⭐ | Microsoft's small model, strong instruction following |
| **Llama 3.2 3B** | 2.0GB Q4 | ~2.5GB | ~100 tok/s | ⭐⭐⭐⭐ | Meta's efficient small model |
| **Granite4 3B** | 2.0GB Q4 | ~2.5GB | ~100 tok/s | ⭐⭐⭐⭐⭐ | IBM's model, specifically optimized for tool calling and structured output |
| **Granite4 1B** | 0.7GB Q4 | ~1GB | ~200 tok/s | ⭐⭐⭐ | Ultra-light option for CI; may need retry on complex properties |
| **FunctionGemma 270M** | 0.2GB | ~0.5GB | ~500 tok/s | ⭐⭐⭐ | Google's function-calling specialist at 270M params; experimental but ultra-fast |
| **Qwen3 0.6B** | 0.5GB Q4 | ~0.8GB | ~300 tok/s | ⭐⭐⭐ | Smallest model with thinking capability; may struggle with diverse names |

### 6.3 Recommended Default: **Qwen3 4B** or **Granite4 3B**

- **Qwen3 4B** — Best overall quality for structured JSON. Its `/no_think` mode
  skips chain-of-thought and goes straight to the answer, which is exactly what we want
  for "give me 200 first names as JSON".
- **Granite4 3B** — IBM specifically optimized this for tool calling and structured
  output. Strong JSON schema adherence at small size.
- Make the model configurable — `--model qwen3:4b` flag on CLI, environment variable
  `CEDS_SYNTH_MODEL`, or constructor parameter.

### 6.4 Model Delivery

With `llama-cpp-python`, models auto-download from HuggingFace Hub on first use.
The user never runs a separate command — the library handles it transparently:

```python
# This single line auto-downloads on first use, loads from cache after that
llm = Llama.from_pretrained(
    repo_id="Qwen/Qwen3-4B-GGUF",       # 2.6 GB — recommended default
    filename="*q4_k_m.gguf",
    n_ctx=4096,
)
```

Recommended model repo IDs:
```
Qwen/Qwen3-4B-GGUF           # 2.6 GB — recommended default
ibm-granite/granite-3b-GGUF   # 2.0 GB — alternative, JSON-specialized
Qwen/Qwen3-0.6B-GGUF         # 0.5 GB — ultra-light CI option
microsoft/Phi-4-mini-GGUF     # 2.4 GB — Microsoft alternative
```

The model is configurable via `--model` CLI flag, `CEDS_SYNTH_MODEL` env var,
or `SyntheticDataGenerator(model="...")` constructor parameter.

For users who already have Ollama installed, the same models work there too:
```bash
ollama pull qwen3:4b  # if they prefer the Ollama workflow
```

---

## 7. Caching Strategy

### 7.1 Why Cache?

LLM calls are slow (1-5 seconds each). For CI and repeated runs, we don't want to
re-generate the same value pools. Cache the generated values per property.

### 7.2 Cache Design

```
~/.ceds_jsonld/cache/
  synthetic_values/
    person/
      P000115_FirstName_200.json     # 200 first names
      P000172_LastOrSurname_200.json  # 200 last names
      P000033_Birthdate_200.json      # 200 birthdates
      P000121_GenerationCodeOrSuffix_200.json
    organization/
      P000204_OrganizationName_200.json
      ...
```

Each cache file:
```json
{
  "property_iri": "http://ceds.ed.gov/terms#P000115",
  "property_label": "First Name",
  "model": "qwen3:4b",
  "generated_at": "2026-02-08T14:30:00",
  "count": 200,
  "values": ["Maria", "James", "Aiden", ...]
}
```

### 7.3 Cache Behavior

| Scenario | Behavior |
|----------|----------|
| Cache file exists and has enough values | Use cached values (no LLM call) |
| Cache file missing | Generate via LLM, save to cache |
| `--no-cache` flag | Always regenerate |
| `--cache-size N` | Generate N values per property (default: 200) |
| Different model requested | Regenerate (model name is part of cache key) |

### 7.4 Pre-warming

For CI, ship a pre-generated cache in the repo:
```bash
ceds-jsonld generate-cache --shape person --count 200 --seed 42
# Creates deterministic cache files that can be committed to the repo
```

This means CI environments **need no LLM runtime at all** — they use the
pre-warmed cache with deterministic values.

---

## 8. Fallback Strategy (No LLM Available)

The generator MUST work even without `llama-cpp-python` installed. Three-tier fallback:

### Tier 1: LLM Available → In-Process Generation (llama-cpp-python or Ollama)
Best quality. Generates contextually-appropriate values based on ontology metadata.
Uses `llama-cpp-python` in-process by default. If Ollama is detected running locally,
uses that instead (faster warm-start, shared model cache with other tools).

### Tier 2: Cache Available → Cached Values  
Good quality. Uses previously-generated LLM values from disk cache.
Ship default cache files in the package for the Person shape.

### Tier 3: No LLM, No Cache → Built-in Fallback Generators
Acceptable quality. Use simple rule-based generators:

```python
FALLBACK_GENERATORS: dict[str, Callable] = {
    "xsd:string": lambda prop_name, rng: _fallback_string(prop_name, rng),
    "xsd:date": lambda prop_name, rng: _fallback_date(rng),
    "xsd:dateTime": lambda prop_name, rng: _fallback_datetime(rng),
    "xsd:token": lambda prop_name, rng: str(rng.randint(100000000, 999999999)),
    "xsd:integer": lambda prop_name, rng: str(rng.randint(1, 999999)),
    "xsd:boolean": lambda prop_name, rng: rng.choice(["true", "false"]),
    "xsd:decimal": lambda prop_name, rng: f"{rng.uniform(0, 100):.2f}",
}

# Name-aware string fallbacks (no external dependency)
_STRING_FALLBACKS: dict[str, list[str]] = {
    "FirstName": ["James", "Maria", "Aiden", "Sophia", "Liam", "Olivia",
                   "Noah", "Emma", "Carlos", "Priya", "Wei", "Fatima"],
    "LastOrSurname": ["Smith", "Johnson", "Williams", "Brown", "Jones",
                       "Garcia", "Martinez", "Anderson", "Taylor", "Lee"],
    "MiddleName": ["Marie", "James", "Lee", "Ann", "Ray", "Grace"],
    "GenerationCodeOrSuffix": ["Jr", "Sr", "II", "III", "IV", "V", ""],
}
```

This tier has **zero external dependencies** — pure Python stdlib `random` module.
It's less realistic than LLM-generated data but produces valid, pipeline-compatible
output.

---

## 9. Concept Scheme Value Extraction

### 9.1 How It Works

For `sh:in`-constrained properties, we already have everything we need. The process:

1. **From SHACL:** `PropertyInfo.allowed_values` gives us the list of IRIs
   (e.g., `["ceds:NI001571173132", "ceds:NI001571173129", ...]`)

2. **From the ontology RDF:** Resolve each IRI to its human-readable form:
   - `skos:notation` → the short code (e.g., `"CanadianSIN"`, `"District"`)
   - `rdfs:label` → the human label (e.g., `"Canadian Social Insurance Number"`)
   - `skos:prefLabel` → the preferred label

3. **For generation:** Randomly select from the resolved list. The mapping YAML's
   `transform` field tells us whether to use the full IRI prefix form
   (e.g., `"PersonIdentificationSystem_CanadianSIN"`) or the short form.

### 9.2 Implementation

```python
class ConceptSchemeResolver:
    """Resolve sh:in IRIs to their skos:notation values from the ontology."""

    def __init__(self, ontology_graph: Graph) -> None:
        self._graph = ontology_graph

    def resolve_allowed_values(
        self, iris: list[str]
    ) -> list[dict[str, str]]:
        """Resolve a list of NamedIndividual IRIs to their metadata.

        Returns:
            List of dicts with keys: iri, notation, label, prefLabel
        """
        results = []
        for iri_str in iris:
            iri = URIRef(iri_str)
            notation = self._graph.value(iri, SKOS.notation)
            label = self._graph.value(iri, RDFS.label)
            pref = self._graph.value(iri, SKOS.prefLabel)
            results.append({
                "iri": iri_str,
                "notation": str(notation) if notation else _local_name(iri_str),
                "label": str(label) if label else "",
                "prefLabel": str(pref) if pref else "",
            })
        return results
```

**Performance note:** Loading a 258K-line RDF file into an rdflib Graph takes ~3-5
seconds. We do this once at generator init time, not per record. This is fine —
it's the same load we already do for SHACL introspection.

---

## 10. Complete Generation Flow — Person Shape Example

Let's trace through generating 100 Person CSV rows:

### Step 1: Load Shape + Ontology

```python
gen = SyntheticDataGenerator(model="Qwen/Qwen3-4B-GGUF")

# Internally:
# - Loads Person_SHACL.ttl via SHACLIntrospector
# - Loads person_mapping.yaml
# - Loads CEDS-Ontology.rdf into rdflib Graph (for NamedIndividual resolution)
# - On first use: auto-downloads model GGUF to ~/.cache/huggingface/ (~2.6GB)
# - On subsequent uses: loads model from cache in ~3 seconds
```

### Step 2: Classify Properties

| Property | Type | Strategy |
|----------|------|----------|
| `FirstName` (P000115) | `xsd:string` | LLM → "Generate 200 first names" |
| `LastOrSurname` (P000172) | `xsd:string` | LLM → "Generate 200 last names" |
| `MiddleName` (P000184) | `xsd:string` | LLM → "Generate 200 middle names" |
| `GenerationCodeOrSuffix` (P000121) | `xsd:string` | LLM → "Generate 200 name suffixes" |
| `Birthdate` (P000033) | `xsd:date` | LLM → "Generate 200 birthdates" |
| `hasSex` (P000011 → range C000011) | Concept Scheme | Random from sh:in NamedIndividuals |
| `hasRaceAndEthnicity` (P000282) | Concept Scheme | Random from NamedIndividuals |
| `hasPersonIdentificationSystem` (P001571) | Concept Scheme | Random from sh:in list (21 values) |
| `hasPersonIdentifierType` (P001573) | Concept Scheme | Random from NamedIndividuals |
| `PersonIdentifier` (P001572) | `xsd:token` | LLM → "Generate 200 person ID numbers" |

### Step 3: Generate Value Pools

**LLM calls (5-6 calls, ~2-5 seconds each, parallelizable):**
- Call 1: 200 first names → cache
- Call 2: 200 last names → cache
- Call 3: 200 middle names → cache
- Call 4: 200 suffixes → cache
- Call 5: 200 birthdates → cache
- Call 6: 200 person ID tokens → cache

**Concept scheme lookups (instant, from ontology):**
- Sex values: resolve from sh:in → `["Male", "Female"]`
- Race values: resolve from NamedIndividuals of C000282
- ID systems: resolve 21 sh:in IRIs → `["CanadianSIN", "District", ...]`
- ID types: resolve from NamedIndividuals

### Step 4: Assemble CSV Rows (100 rows)

For each row, random.choice from the value pools:
```python
{
    "FirstName": random.choice(first_names_pool),      # "Maria"
    "MiddleName": random.choice(middle_names_pool),     # "Elena"  (70% chance)
    "LastName": random.choice(last_names_pool),          # "Gonzalez"
    "GenerationCodeOrSuffix": random.choice(suffix_pool), # ""  (70% chance)
    "Birthdate": random.choice(birthdates_pool),         # "1998-04-15"
    "Sex": random.choice(sex_values),                    # "Female"
    "RaceEthnicity": ",".join(random.sample(race_values, k=rng.randint(1,3))),
    "PersonIdentifiers": "|".join(id_pool_sample),       # pipe-delimited
    "IdentificationSystems": "|".join(sys_pool_sample),
    "PersonIdentifierTypes": "|".join(type_pool_sample),
}
```

**Total time:** ~15-30 seconds for the LLM calls (one-time), then milliseconds to
assemble 100 rows. Second run with cache: milliseconds total.

---

## 11. Pros & Cons of LLM-Assisted Approach

### Pros

| Advantage | Details |
|-----------|---------|
| **Truly generic** | Add any new CEDS shape, and the generator works automatically — the LLM reads the ontology metadata and generates appropriate values. No per-shape code needed. |
| **Contextually realistic** | LLM understands "First Name in education records" produces diverse US student names, not random words. Faker's `fake.first_name()` is generic, not domain-aware. |
| **No Faker dependency** | One fewer library to maintain. `random` + `ollama` client is lighter than `faker`. |
| **Self-documenting** | The prompt IS the specification. Reading the prompt tells you exactly what values are expected. |
| **Multi-language support** | For localized CEDS deployments, the LLM can generate names in Spanish, Mandarin, etc. Faker requires locale installation. |
| **Future-proof** | As shapes get more complex properties (addresses, course names, assessment titles), the LLM handles them without new code. |
| **Concept scheme handling is free** | For enumerated properties (the majority of object properties), we need zero LLM — just random.choice from the ontology. |

### Cons

| Disadvantage | Impact | Mitigation |
|--------------|--------|------------|
| **Model download on first use** | Medium — ~2.6GB one-time download | Auto-downloads with progress bar. Cached permanently. Ship pre-warmed value cache for CI. |
| **Non-deterministic by default** | Medium for tests | Seed the RNG for row assembly. LLM-generated pools are cached deterministically. |
| **LLM cold start is slow** | ~3s model load from disk | Cache eliminates most LLM calls. Only ~6 calls per shape, ever. |
| **LLM can produce bad values** | Low — grammar constraint prevents invalid JSON | Validate values post-generation: check maxLength, date format, etc. Retry once on failure. |
| **Larger pip install** | ~20-30MB for llama-cpp-python | Still small vs. torch (~2GB). Pre-built wheels handle most platforms. |
| **Can't use in air-gapped CI** | Medium | Ship cache files in repo. Fallback generators work offline with zero deps. |
| **More complex than Faker** | Medium | Clean abstraction layers. Each tier is independent and testable. |

### Cons We're NOT Worried About

| Non-Issue | Why |
|-----------|-----|
| **LLM performance** | We make 5-10 calls total per shape, not per record. Cached after first run. |
| **LLM accuracy** | We're generating names and dates, not solving math. Even a 1B model excels at this. |
| **Cost** | Local LLM = zero API cost. Ollama is free and open source. |
| **Privacy** | Data never leaves the machine. No cloud API calls. |

---

## 12. Comparison: LLM Approach vs. Original Faker Approach

| Dimension | Faker Approach (v1 Research) | LLM Approach (This Research) |
|-----------|------------------------------|------------------------------|
| **New shape support** | Must add property-specific generators in code for each shape | Automatic — reads ontology metadata |
| **Value quality** | Generic (`fake.first_name()` = any culture) | Domain-specific (diverse US education names) |
| **Concept schemes** | Hard-coded lists in a `CEDSProvider` class | Direct from ontology NamedIndividuals — always in sync |
| **Dependencies** | `faker` (~3MB, pure Python) | `llama-cpp-python` + `huggingface-hub` (~25MB pip, ~2.6GB model auto-cached) |
| **CI friendliness** | Always works (no LLM needed) | Ship pre-warmed cache for CI; fallback generators for zero-dep mode |
| **Speed (first run)** | Instant | ~15-30s for LLM value pool generation (one-time, cached) |
| **Speed (cached run)** | Instant | Instant (same as Faker — just random.choice) |
| **Maintenance burden** | Must update when shapes change | Zero — ontology metadata drives everything |
| **Offline support** | Full | Full (with cache or fallback generators) |

**Winner:** The LLM approach is superior for a library that will support 20+ shapes.
Writing custom Faker providers for each shape's properties doesn't scale. Reading the
ontology metadata does.

---

## 13. Implementation Plan — Revised Task Breakdown

### Phase 1: Core Generator — Concept Schemes + Fallback (Est. ~2 sessions)

| # | Task | Details |
|---|------|---------|
| 1.1 | `ConceptSchemeResolver` class | Parse ontology RDF, resolve `sh:in` IRIs to notation/label values |
| 1.2 | `FallbackGenerators` module | Pure-Python generators for all XSD types + name-aware string defaults |
| 1.3 | `MappingAwareAssembler` class | Read mapping YAML, assemble CSV rows, handle pipe-delimited multi-value |
| 1.4 | `SyntheticDataGenerator` class | Core orchestrator with concept scheme + fallback generation |
| 1.5 | CSV + NDJSON output writers | Write to file or stdout |
| 1.6 | Tests: round-trip through Pipeline | Generate CSV → Pipeline → JSON-LD → validate SHACL → pass |

### Phase 2: LLM Integration (Est. ~2 sessions)

| # | Task | Details |
|---|------|---------|
| 2.1 | Add `llama-cpp-python` + `huggingface-hub` to `[sdg]` extras | `pip install ceds-jsonld[sdg]` |
| 2.2 | `OntologyMetadataExtractor` class | Extract rdfs:label, dc:description, maxLength, rangeIncludes from ontology for each property |
| 2.3 | `LLMValueGenerator` class | Build prompts from metadata, call llama-cpp-python with JSON schema, parse responses; auto-detect Ollama as alternative |
| 2.4 | Caching layer | File-based cache under `~/.ceds_jsonld/cache/` with model-keyed entries |
| 2.5 | Three-tier fallback logic | LLM (in-process or Ollama) → cache → fallback generators |
| 2.6 | Post-generation validation | Verify LLM values match datatype constraints (maxLength, date format, etc.) |
| 2.7 | Tests: LLM value quality | Test with live LLM if `[sdg]` installed, skip gracefully if not |

### Phase 3: CLI + Integration (Est. ~1-2 sessions)

| # | Task | Details |
|---|------|---------|
| 3.1 | `generate-sample` CLI command | All options: shape, count, format, model, seed, cache control |
| 3.2 | `generate-cache` CLI command | Pre-warm cache for CI environments |
| 3.3 | Ship default Person cache | Commit pre-generated cache files for zero-setup CI |
| 3.4 | Streaming mode | Iterator/generator pattern for 100K+ records |
| 3.5 | Integration tests | End-to-end: CLI → CSV → Pipeline → validate |
| 3.6 | Documentation | Sphinx docs, README examples, getting-started guide for Ollama setup |

### Phase 4: Polish (Est. ~1 session)

| # | Task | Details |
|---|------|---------|
| 4.1 | Benchmark | Time: LLM generation, cached generation, 10K/100K/1M row assembly |
| 4.2 | Model comparison | Test Qwen3 4B vs. Granite4 3B vs. Phi-4 Mini for value quality |
| 4.3 | JSON-LD output mode | Generate rows → Pipeline → JSON-LD documents |
| 4.4 | Distribution profiles | Optional YAML config for demographic distributions |

---

## 14. Installation & End-User Experience

### 14.1 The `[sdg]` Extras Group

Following the project's existing extras pattern (`[cli]`, `[excel]`, `[cosmos]`, etc.):

```toml
# In pyproject.toml [project.optional-dependencies]
sdg = ["llama-cpp-python>=0.3", "huggingface-hub>=0.20"]
```

**For the end user:**
```bash
pip install ceds-jsonld[sdg]
```

That's it. No external binary. No service configuration. No `ollama pull`.

### 14.2 What the User Types (Python API)

```python
from ceds_jsonld import Pipeline, SyntheticDataGenerator

# First run: auto-downloads model (~2.6GB) with progress bar
# Subsequent runs: loads from ~/.cache/huggingface/ in ~3 seconds
gen = SyntheticDataGenerator(shape="person")
gen.to_csv(count=500, output="test_data.csv")

# Or as a one-liner through Pipeline
pipeline = Pipeline.from_shape("person")
docs = pipeline.run_synthetic(count=100)  # generates CSV → runs full pipeline
```

### 14.3 What the User Types (CLI)

```bash
# First run prints: "Downloading model Qwen3-4B (2.6 GB)... done."
# Subsequent runs print: "Loading model from cache... done."
ceds-jsonld generate-sample --shape person --count 500 --output test_data.csv

# Pre-warm the value cache (e.g., before committing cache files for CI)
ceds-jsonld generate-cache --shape person --count 200
```

### 14.4 What Happens Under the Hood

1. Check if value cache exists for this shape+model → if yes, use it (instant, no LLM)
2. Check if Ollama is running locally → if yes, use it (faster warm-start)
3. Load model in-process via `llama-cpp-python` → auto-download GGUF if needed
4. Generate value pools (~6 calls for Person, ~20-30s total)
5. Save value pools to `~/.ceds_jsonld/cache/` for next time
6. **Unload model** — RAM freed, GPU freed, nothing running
7. Assemble CSV rows from cached pools (milliseconds)

### 14.5 Dependency Impact

| Package | Size | Required? | When |
|---------|------|-----------|------|
| `llama-cpp-python` | ~20-30MB pip (pre-built wheel) | Optional (`[sdg]` extra) | LLM generation (Tier 1) |
| `huggingface-hub` | ~5MB pip | Optional (`[sdg]` extra) | Model auto-download |
| Model GGUF file | ~2.6GB (auto-cached) | Auto-downloaded on first use | Stored in `~/.cache/huggingface/` |
| No new deps for Tier 2/3 | — | — | Cache files + stdlib `random` |
| **NOT adding `faker`** | — | — | Replaced by LLM + fallback generators |
| **NOT requiring Ollama** | — | — | Auto-detected as optional alternative |

---

## 15. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| No LLM runtime in CI | High | Ship pre-warmed value cache. Fallback generators need zero deps. |
| Model download fails (network) | Medium | Cache persists across runs. Ship default cache in package. Fallback generators as safety net. |
| LLM generates inappropriate values | Low | Post-validation checks. Education-context prompt. Cache review before shipping. |
| LLM generates duplicate values | Low | Request 200 values, deduplicate, fall back to generating more if needed. |
| Model generates non-UTF-8 characters | Very Low | JSON schema constraint enforces string type. Post-validate encoding. |
| `llama-cpp-python` wheel not available for platform | Low | Pre-built wheels cover Windows x64, Linux x64, macOS. Ollama fallback for exotic platforms. |
| Large ontology RDF load time | Low | ~3-5 seconds one-time. Cache the parsed Graph. |
| New shape has properties with no ontology metadata | Medium | Fallback to generic string generation. Log a warning. |

---

## 16. Open Questions for Discussion

### Resolved Questions

1. ~~**Should we use `ollama` Python client or just `httpx` + Ollama REST API?**~~
   - **Resolved:** Neither as primary. Use `llama-cpp-python` for in-process execution
     (no server needed). Auto-detect Ollama as an alternative for power users who already
     have it running.

2. ~~**Should this be a separate extras install?**~~
   - **Resolved:** Yes. `pip install ceds-jsonld[sdg]` installs `llama-cpp-python` and
     `huggingface-hub`. Follows the existing pattern of `[cli]`, `[excel]`, `[cosmos]`.

3. ~~**What about the Ollama background service problem?**~~
   - **Resolved:** `llama-cpp-python` runs in-process — model loads when code runs,
     unloads when code exits. Zero footprint when idle. No background service, no tray
     icon, no VRAM held. Ollama is only used when it's already running.

### Open Questions

4. **How many values should we generate per LLM call?**
   - Recommendation: 200 per call. Big enough for diverse sampling, small enough for
     fast LLM response (~2000 tokens output). Configurable via `--cache-size`.

5. **Should we allow cloud LLM providers as an alternative?**
   - Recommendation: Yes, as a future extension. `llama-cpp-python` has an
     OpenAI-compatible API wrapper, so swapping to a cloud endpoint is a one-line change.
     But local-first for privacy (education data context).

6. **Should we pre-ship cache files for all shapes or just Person?**
   - Recommendation: Ship Person cache immediately. Add other shapes as they're created.
     Provide `generate-cache` CLI command for users to generate their own.

7. **Should the LLM prompt include the parent shape context (e.g., "this is a Person record")?**
   - Recommendation: Yes. The parent class label adds important context. "Generate first
     names for a PersonName in K-12 education records" is much better than "Generate
     first names."

8. **What about `faker` as a fallback instead of hardcoded lists?**
   - Recommendation: No. The hardcoded lists in Tier 3 are sufficient for fallback.
     Adding `faker` as a fallback reintroduces the dependency we're avoiding, and the
     built-in lists cover the common cases. If a property has no hardcoded fallback,
     we generate `f"value_{i}"` placeholder strings — good enough for structural testing.

9. **Should we include the model in the `pip install`?**
   - **No.** PyPI has a hard 100MB package size limit. The smallest usable model
     (Qwen3 0.6B Q4) is ~500MB. Instead, `huggingface-hub` auto-downloads the model
     on first use with a progress bar, cached permanently at `~/.cache/huggingface/`.
     This is the same pattern used by `spacy`, `nltk`, `sentence-transformers`, etc.

---

## 17. Conclusion & Recommendation

**The hybrid approach (concept scheme extraction + local LLM generation) is the right
design for a library that will grow to support many shapes.**

**Key advantages over the original Faker approach:**
- **Zero per-shape code** for enumerated properties (concept schemes from ontology)
- **Zero per-property code** for literal values (LLM reads ontology metadata)
- **Truly generic** — add new shapes and get synthetic data automatically
- **Contextually realistic** — LLM understands "education data" context
- **Privacy-preserving** — local in-process LLM, no cloud API calls, no background service
- **Graceful degradation** — works without LLM via cache and fallback generators
- **Respectful to the end user** — `pip install ceds-jsonld[sdg]` is the only setup step;
  model auto-downloads on first use; nothing runs in the background when idle

**The concept scheme handling alone justifies this approach.** 19,489 NamedIndividuals
across hundreds of concept schemes, all resolvable from the ontology we already load —
no need to hand-code any of those enumerations in a Faker provider.

**The `llama-cpp-python` runtime choice ensures a clean user experience.** No external
binary installs, no background service, no VRAM held when idle. The model loads when
the user's code runs and unloads when it finishes — like any other library.

**Estimated effort:** 6-8 sessions for complete implementation.

**Next step:** Get approval on this revised design, then start with Phase 1 (concept
scheme resolver + fallback generators + CSV assembly) which works end-to-end without
any LLM dependency.

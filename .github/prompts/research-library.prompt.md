---
description: "Research a library or tool, fetch its documentation, and save a local reference copy for future sessions."
---
# Research a Library

## Purpose

Fetch documentation for a library or tool and save a structured reference locally so future sessions don't need to re-fetch.

## Procedure

### 1. Identify the Library
Ask the user what library to research, or infer from context. Supported libraries already have reference docs:
- `.github/docs/library-reference/rdflib-reference.md`
- `.github/docs/library-reference/pyshacl-reference.md`
- `.github/docs/library-reference/azure-cosmos-reference.md`
- `.github/docs/library-reference/orjson-reference.md`
- `.github/docs/library-reference/pyyaml-reference.md`

For new libraries, create a new file in the same directory.

### 2. Fetch Documentation
Use web fetch to get:
- Official README or getting-started guide
- API reference for the functions/classes we use
- Common usage patterns and examples
- Known gotchas and performance characteristics

### 3. Save Reference Document
Create/update `.github/docs/library-reference/{library}-reference.md` with:

```markdown
# {Library Name} Reference — ceds-jsonld

**Version:** X.Y.Z
**Docs:** [URL]
**Last updated:** YYYY-MM-DD

## Installation
pip install {package}

## API Reference
### function_name(param1, param2, ...)
Description. Returns X.

## Usage Patterns
[Patterns relevant to our project — not generic examples]

## Gotchas & Notes
[Things that tripped us up or are non-obvious]

## Performance Notes
[Relevant benchmarks or performance characteristics]
```

### 4. Confirm
Report what was saved and where:
> "Saved {library} reference to `.github/docs/library-reference/{library}-reference.md`. Key APIs documented: [list]."

## When to Update
- If a library version changes significantly
- If we discover new API patterns we need to document
- If a gotcha is discovered during development

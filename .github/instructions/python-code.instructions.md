---
applyTo: "**/*.py"
---
# Python Coding Standards — ceds-jsonld

## Style Rules

- Follow PEP 8. Use `ruff` for linting and formatting.
- Max line length: 120 characters.
- Use type hints on all public functions and methods.
- Use `from __future__ import annotations` at the top of every module.
- Prefer `pathlib.Path` over `os.path` for file operations.
- Use f-strings for string formatting, never `%` or `.format()`.

## Naming Conventions

- Classes: `PascalCase` (e.g., `ShapeRegistry`, `JSONLDBuilder`)
- Functions/methods: `snake_case` (e.g., `build_person_direct`, `load_shape`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `CEDS_NAMESPACE`, `DEFAULT_BATCH_SIZE`)
- Private methods: prefix with `_` (e.g., `_parse_shacl_property`)
- Module-level variables that are effectively constants: `UPPER_SNAKE_CASE`

## Import Organization

1. Standard library imports
2. Third-party imports (rdflib, orjson, pyyaml, pandas, azure)
3. Local imports (ceds_jsonld.*)

Separate each group with a blank line. Use absolute imports within the package.

## Performance Rules (CRITICAL)

- **Never use rdflib+PyLD for production JSON-LD output.** Direct dict construction is 161x faster.
- Use `orjson.dumps()` for JSON serialization. Fall back to `json.dumps()` only if orjson is unavailable.
- Avoid unnecessary object creation in hot loops. Pre-compute constants outside loops.
- For bulk operations, prefer list comprehensions over `for` + `append`.
- Do not use multiprocessing for direct-dict construction — it's counterproductive (proven in benchmarks).

## Error Handling

- Use specific exceptions, not bare `except:`.
- Create custom exception classes in `src/ceds_jsonld/exceptions.py` for domain errors.
- Always provide actionable error messages that tell the user what went wrong and how to fix it.
- Example: `raise MappingError(f"Field '{field}' in mapping config does not match any column in source data. Available columns: {cols}")`

## Docstrings

- Use Google-style docstrings on all public classes, methods, and functions.
- Include: one-line summary, Args, Returns, Raises, and Example sections where appropriate.
- Example:
  ```python
  def build_one(self, row: dict[str, Any]) -> dict[str, Any]:
      """Build a single JSON-LD document from a mapped data row.

      Args:
          row: A dictionary of mapped field names to values.

      Returns:
          A JSON-LD document as a plain Python dict with @context, @type, and @id.

      Raises:
          MappingError: If a required field is missing from the row.
      """
  ```

## Module Structure

Every Python module should follow this order:
1. Module docstring
2. `from __future__ import annotations`
3. Imports (three groups as above)
4. Module-level constants
5. Exception classes (if module-specific)
6. Main classes and functions
7. `if __name__ == "__main__":` block (only in scripts)

## Dependency Rules

- `orjson` is preferred but optional — always provide a fallback:
  ```python
  try:
      import orjson
      def dumps(obj): return orjson.dumps(obj, option=orjson.OPT_INDENT_2)
  except ImportError:
      import json
      def dumps(obj): return json.dumps(obj, indent=2).encode()
  ```
- `rdflib` is used ONLY for SHACL introspection and optional validation — never for production output.
- `pandas` is used in source adapters for CSV/Excel, not in the core builder.

## API Design Principles — User Experience First

Every public API should be designed from the end user's perspective first, then implemented.

### Progressive Disclosure
- **Make common things easy, rare things possible.** The `Pipeline` class should handle 90% of use cases with minimal arguments. Power-user options (custom transforms, mapping overrides, composition) should be available but not required.
- The simplest valid usage of any class should require the fewest possible arguments. Use sensible defaults for everything else.
- Example: `Pipeline(source=CSVAdapter("file.csv"), shape="person", registry=registry)` works with zero configuration beyond the essentials.

### Convenience over Ceremony
- If users have to perform 3+ steps of boilerplate setup before doing useful work, add a convenience path. The Pipeline's `source_overrides` parameter exists specifically so users don't have to drop to the lower-level `FieldMapper` API just to rename columns.
- All commonly-used classes should be importable from the top-level package: `from ceds_jsonld import Pipeline, CSVAdapter, ShapeRegistry` — never force users into sub-package imports for standard workflows.

### Sensible Defaults
- Every optional parameter should have a default that does the right thing for most users.
- Adapters should auto-detect formats when possible (e.g., CSV encoding, Excel sheet selection).
- Mapping configs ship with standard column names — overrides are optional.

### Consistent Patterns
- All adapters follow the same interface (`SourceAdapter` ABC with `read()`, `read_batch()`, `count()`).
- All file-output methods (`to_json`, `to_ndjson`) auto-create parent directories — no `mkdir` needed.
- Error messages always tell the user what went wrong AND how to fix it.

### Composability
- Components should work independently or together. `FieldMapper`, `JSONLDBuilder`, and `Serializer` can each be used standalone, but the `Pipeline` wires them together for the common case.
- Methods like `FieldMapper.with_overrides()` and `FieldMapper.compose()` return new instances — no mutation, no surprises.

## Testing Requirement

Every function and class MUST have corresponding tests. See `.github/instructions/testing.instructions.md`.

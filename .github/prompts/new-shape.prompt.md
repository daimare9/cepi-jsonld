---
description: "Scaffold a new SHACL shape with all companion files: SHACL, context, mapping, sample data, and tests."
---
# Create a New Shape

## Input Required

Ask the user:
1. **Shape name** (e.g., "Organization", "K12Enrollment")
2. **Source data format** (CSV columns, API fields, or existing mapping)
3. **CEDS elements** this shape covers (or let me look them up in the ontology)

## Step-by-Step Creation

### 1. Read Reference Files
- Read `ResearchFiles/Person_SHACL.ttl` for the canonical shape pattern
- Read `ResearchFiles/Person_context.json` for the context pattern
- Read `ResearchFiles/person_example.json` for the output format pattern
- Read `ResearchFiles/Common.ttl` for shared sub-shapes (RecordStatus, DataCollection)

### 2. Create Shape Folder
Create `ontologies/{shape_name}/` with these files:

```
ontologies/{shape_name}/
├── {Shape}_SHACL.ttl              ← SHACL NodeShape + PropertyShapes
├── {Shape}_CEPI_Extensions.ttl    ← CEPI custom properties and named individuals
├── {shape}_context.json           ← JSON-LD context mapping terms to IRIs
├── {shape}_mapping.yaml           ← Source-to-JSON-LD field mapping config
├── sample_{shape}.csv             ← Sample data (30+ records, covers edge cases)
└── {shape}_example.json           ← Golden file: expected JSON-LD output
```

### 3. SHACL File
Follow the pattern in `ontology.instructions.md`:
- Use `sh:closed true`
- Include `sh:ignoredProperties`
- Reference RecordStatusShape and DataCollectionShape
- Define PropertyShapes with correct datatypes and cardinality

### 4. Context File
- Map each SHACL property path to a human-readable term
- Use `@type: @id` for named individual references
- Include `@vocab` and `@base`

### 5. Mapping YAML
Follow `yaml-mapping.instructions.md`:
- Map source columns to JSON-LD terms
- Define transforms for value conversion
- Specify cardinality and split delimiters

### 6. Sample Data
Create CSV with:
- 30+ rows covering normal cases
- Rows with missing optional fields
- Rows with multi-value fields (varying counts)
- Edge cases: empty strings, special characters, date formats

### 7. Golden File
- Build a JSON-LD document from row 1 of the sample data by hand
- This is the test reference — must be 100% correct

### 8. Tests
Create `tests/shapes/test_{shape}_shape.py` with:
- Golden file comparison test
- Round-trip SHACL validation test
- Missing optional fields test
- Multi-value handling test
- Edge case tests
- **User journey test:** A complete Pipeline-based test that reads sample CSV → produces JSON-LD via Pipeline(source_overrides=...) if column names differ from the standard mapping

### 9. Register Shape
Add the shape to `ShapeRegistry` so it can be loaded by name.

### 10. Verify User Experience
Before marking the shape as complete, verify from the end user's perspective:
- Can the user load and use this shape with just `registry.load_shape("{name}")` + `Pipeline(...)`?
- Does the default mapping YAML work with the sample CSV without any overrides?
- Are error messages helpful if the user's data is missing required columns?
- Is the shape importable and discoverable via `registry.list_available()`?

## After Creation
- Run all tests: `pytest tests/shapes/test_{shape}_shape.py -v`
- Report results
- Update ROADMAP.md if this was a roadmap task

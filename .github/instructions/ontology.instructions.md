---
applyTo: "ontologies/**,ResearchFiles/**/*.ttl,ResearchFiles/**/*.rdf,**/*.ttl,**/*.rdf"
---
# Ontology & SHACL Instructions — ceds-jsonld

## SHACL Shape Patterns

All SHACL shapes in this project follow a consistent pattern established in `ResearchFiles/Person_SHACL.ttl`. When creating or modifying shapes:

### NodeShape Structure
- Every NodeShape MUST have `sh:closed true` to prevent extra properties.
- Every NodeShape MUST have `sh:ignoredProperties` that includes at minimum: `(rdf:type rdf:id rdf:value rdfs:label)`.
- Every entity NodeShape (Person, Organization, etc.) MUST reference `RecordStatusShape` and `DataCollectionShape` sub-shapes.
- Use `sh:node` to reference nested shapes (not `sh:class` alone).

### PropertyShape Structure
- Use `sh:path` to specify the RDF property.
- Use `sh:datatype` for literal values (e.g., `xsd:string`, `xsd:date`, `xsd:dateTime`).
- Use `sh:maxCount 1` for single-valued properties. Omit for multi-valued.
- Use `sh:minCount 1` for required properties.
- Use `sh:in` for enumerated values (named individuals from CEDS or CEPI).
- Use `sh:class` + `sh:node` together when a property points to a typed node with its own shape.

### Example Pattern (from Person_SHACL.ttl)
```turtle
cepi:PersonShape a sh:NodeShape ;
    sh:targetClass ceds:C200275 ;
    sh:closed true ;
    sh:ignoredProperties (rdf:type rdf:id rdf:value rdfs:label) ;
    sh:property cepi:hasPersonBirthShape,
                cepi:hasPersonNameShape,
                cepi:hasPersonSexGenderShape,
                cepi:hasPersonDemographicRaceShape,
                cepi:hasPersonIdentificationShape .
```

## Namespace Conventions

| Prefix | URI | Usage |
|--------|-----|-------|
| `ceds` | `http://ceds.ed.gov/terms#` | Base CEDS ontology classes and properties |
| `cepi` | `http://cepi-dev.state.mi.us/` | CEPI extension properties, named individuals, shapes |
| `sh` | `http://www.w3.org/ns/shacl#` | SHACL vocabulary |
| `xsd` | `http://www.w3.org/2001/XMLSchema#` | XML Schema datatypes |
| `rdf` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` | RDF vocabulary |
| `rdfs` | `http://www.w3.org/2000/01/rdf-schema#` | RDF Schema |
| `schema` | `http://schema.org/` | Schema.org (used in CEPI extensions for `domainIncludes`) |
| `skos` | `http://www.w3.org/2004/02/skos/core#` | SKOS (used for named individual labels) |

## CEPI Extension Ontology Pattern

CEPI extensions follow the pattern in `ResearchFiles/Common.ttl`:

- Custom properties use `cepi:P######` URIs with `schema:domainIncludes` to link to CEDS classes.
- Named individuals use `cepi:NI############` URIs with `skos:prefLabel` for human-readable names.
- Each shape's extensions are in a separate `.ttl` file (e.g., `Person_CEPI_Extensions.ttl`).
- Shared extensions (RecordStatus, DataCollection) live in `Common.ttl`.

## JSON-LD Context Rules

- Each shape has its own context file (e.g., `person_context.json`).
- `@vocab` and `@base` should point to the CEPI namespace.
- Map human-readable terms to CEDS/CEPI IRIs (e.g., `"Person": "ceds:C200275"`).
- Use `@type: @id` for properties that reference named individuals.
- Use `@container: @set` for properties that are always arrays.
- The context file is what gets hosted at a URL and referenced by `@context` in the JSON-LD output.

## Adding a New Shape Checklist

1. Create the shape folder under `ontologies/` (e.g., `ontologies/organization/`)
2. Write the SHACL file following the patterns above
3. Write the CEPI extensions file for shape-specific properties/named individuals
4. Write the JSON-LD context file mapping terms to IRIs
5. Write the mapping YAML (see `.github/instructions/yaml-mapping.instructions.md`)
6. Create sample data (CSV with 30+ records covering edge cases)
7. Write tests (see `.github/instructions/testing.instructions.md`)
8. Register the shape in the `ShapeRegistry`

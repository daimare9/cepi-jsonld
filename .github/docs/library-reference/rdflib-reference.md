# rdflib Reference — ceds-jsonld

**Version:** 7.1.4
**Docs:** https://rdflib.readthedocs.io/en/stable/
**Last updated:** 2025-01-20

## Installation

```bash
pip install rdflib
```

## Role in This Project

rdflib is used **only** for:
1. SHACL shape introspection (parsing `.ttl` files and querying properties)
2. Optional round-trip validation (parsing JSON-LD back to a graph for pySHACL validation)

**It is NOT used for production JSON-LD output.** Direct dict construction is 161x faster.

## API Reference

### Graph

```python
from rdflib import Graph, Namespace, URIRef, Literal, BNode

g = Graph()
```

- `Graph()` — Create an empty RDF graph
- `Graph(store, identifier)` — Create with specific store/identifier

### Parsing

```python
# From file
g.parse("file.ttl", format="turtle")
g.parse("file.rdf", format="xml")
g.parse("file.json", format="json-ld")

# From string
g.parse(data=ttl_string, format="turtle")
g.parse(data=json_string, format="json-ld")

# Format auto-detection from file extension works for common formats
g.parse("file.ttl")  # auto-detects turtle
```

Supported formats: `turtle`, `xml`, `json-ld`, `n3`, `nt`, `trig`, `nquads`

### Triples Iteration

```python
# All triples
for s, p, o in g:
    print(s, p, o)

# Pattern matching (None = wildcard)
for s, p, o in g.triples((None, RDF.type, SH.NodeShape)):
    print(s)  # All NodeShapes

# Single match
g.value(subject, predicate)  # Returns first object or None
```

### Namespaces

```python
from rdflib.namespace import RDF, RDFS, XSD, SKOS, SH

# Custom namespaces
CEDS = Namespace("http://ceds.ed.gov/terms#")
CEPI = Namespace("http://cepi-dev.state.mi.us/")

# Bind for pretty serialization
g.bind("ceds", CEDS)
g.bind("cepi", CEPI)
```

### SPARQL Queries

```python
results = g.query("""
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    SELECT ?shape ?path ?datatype
    WHERE {
        ?shape a sh:NodeShape .
        ?shape sh:property ?prop .
        ?prop sh:path ?path .
        OPTIONAL { ?prop sh:datatype ?datatype }
    }
""")

for row in results:
    print(row.shape, row.path, row.datatype)
```

### Serialization

```python
# To string
output = g.serialize(format="turtle")
output = g.serialize(format="json-ld")

# To file
g.serialize(destination="output.ttl", format="turtle")
```

## Usage Patterns for This Project

### SHACL Introspection Pattern

```python
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, SH

def get_shape_properties(shacl_path: str) -> list[dict]:
    """Extract property definitions from a SHACL shape file."""
    g = Graph()
    g.parse(shacl_path, format="turtle")

    props = []
    for shape in g.subjects(RDF.type, SH.NodeShape):
        for prop_node in g.objects(shape, SH.property):
            path = g.value(prop_node, SH.path)
            datatype = g.value(prop_node, SH.datatype)
            max_count = g.value(prop_node, SH.maxCount)
            min_count = g.value(prop_node, SH.minCount)
            props.append({
                "path": str(path),
                "datatype": str(datatype) if datatype else None,
                "required": int(min_count) > 0 if min_count else False,
                "single": int(max_count) == 1 if max_count else False,
            })
    return props
```

## Gotchas & Notes

- `g.value()` returns `None` if no match, not raising an exception.
- `URIRef` comparisons are string-based. Use `str(uri)` for dict keys.
- Parsing JSON-LD requires the `json-ld` extra: `pip install rdflib[json-ld]` (but we primarily parse Turtle).
- Graph iteration order is not guaranteed.
- `SH` namespace is built-in as of rdflib 6.x.

## Performance Notes

- Parsing a SHACL Turtle file is fast (<10ms for our shapes).
- Building RDF graphs triple-by-triple then serializing to JSON-LD is ~161x slower than direct dict construction (see PERFORMANCE_REPORT.md).
- Use rdflib for introspection only, never in the hot path.

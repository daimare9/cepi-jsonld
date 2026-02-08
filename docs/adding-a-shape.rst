Adding a New Shape
==================

This guide walks through creating a new shape definition (e.g. Organization,
K-12 Enrollment, Staff) from scratch. Each shape is a self-contained folder
with five files.

Overview
--------

A shape folder looks like this::

    ontologies/
    └── organization/
        ├── Organization_SHACL.ttl       # SHACL constraints
        ├── organization_context.json    # JSON-LD context
        ├── organization_mapping.yaml    # Field mapping rules
        ├── organization_sample.csv      # Sample data for testing
        └── organization_example.json    # Golden-file expected output (optional)

Step 1: Create the SHACL Shape
------------------------------

Define the shape's constraints in a Turtle file. Follow the pattern from
the Person shape::

    @prefix sh:   <http://www.w3.org/ns/shacl#> .
    @prefix ceds: <http://ceds.ed.gov/terms#> .
    @prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

    ceds:OrganizationShape
        a sh:NodeShape ;
        sh:targetClass ceds:C200320 ;
        sh:closed true ;
        sh:ignoredProperties ( rdf:type ) ;
        sh:property [
            sh:path ceds:P000204 ;      # OrganizationName
            sh:datatype xsd:string ;
            sh:minCount 1 ;
            sh:maxCount 1 ;
        ] ;
        sh:property [
            sh:path ceds:P000826 ;      # OrganizationIdentifier
            sh:datatype xsd:string ;
        ] .

Key rules:

- Use ``sh:closed true`` to enforce that no unexpected properties appear.
- Use ``sh:minCount 1`` for required fields.
- Use ``sh:in`` for enumerated values (e.g. state codes).
- Nest sub-shapes with ``sh:node`` for complex properties.

Step 2: Create the JSON-LD Context
-----------------------------------

Map CEDS property IRIs to human-readable names:

.. code-block:: json

    {
        "@context": {
            "ceds": "http://ceds.ed.gov/terms#",
            "Organization": "ceds:C200320",
            "OrganizationName": "ceds:P000204",
            "OrganizationIdentifier": "ceds:P000826"
        }
    }

Step 3: Generate a Mapping Template
------------------------------------

Use the CLI or the introspector to scaffold the mapping YAML::

    ceds-jsonld generate-mapping \
        --shacl ontologies/organization/Organization_SHACL.ttl \
        --context-file ontologies/organization/organization_context.json \
        -o ontologies/organization/organization_mapping.yaml

Or in Python:

.. code-block:: python

    from ceds_jsonld import SHACLIntrospector
    import yaml

    intro = SHACLIntrospector("ontologies/organization/Organization_SHACL.ttl")
    template = intro.generate_mapping_template(
        context_url="https://cepi-dev.state.mi.us/ontology/context-organization.json",
    )
    with open("organization_mapping.yaml", "w") as f:
        yaml.dump(template, f, sort_keys=False)

Step 4: Fill in the Mapping YAML
---------------------------------

Edit the generated template. For each property, fill in the ``source`` field
to match your data's column name:

.. code-block:: yaml

    shape: OrganizationShape
    context_url: "https://cepi-dev.state.mi.us/ontology/context-organization.json"
    base_uri: "cepi:organization/"
    id_source: "OrgId"
    type: Organization

    properties:
      OrganizationName:
        type: OrganizationName
        fields:
          OrganizationName:
            source: "ORG_NAME"
          OrganizationIdentifier:
            source: "ORG_ID"

Step 5: Create Sample Data
--------------------------

Create a CSV file with representative test data::

    OrgId,ORG_NAME,ORG_ID
    1001,Springfield Elementary,IL-SPR-001
    1002,Shelbyville High,IL-SHE-002

Step 6: Register and Test
-------------------------

.. code-block:: python

    from ceds_jsonld import ShapeRegistry, Pipeline, CSVAdapter

    registry = ShapeRegistry()
    registry.load_shape("organization")  # auto-discovers from ontologies/

    pipeline = Pipeline(
        source=CSVAdapter("ontologies/organization/organization_sample.csv"),
        shape="organization",
        registry=registry,
    )

    # Quick sanity check
    for doc in pipeline.stream():
        print(doc)

Step 7: Write Tests
-------------------

Create ``tests/test_organization_shape.py`` with:

1. **Golden file test** — compare output against hand-verified JSON.
2. **Round-trip test** — parse output with rdflib, validate with pySHACL.
3. **Edge case tests** — missing optional fields, special characters, etc.

.. code-block:: python

    def test_organization_roundtrip():
        registry = ShapeRegistry()
        registry.load_shape("organization")
        pipeline = Pipeline(
            source=CSVAdapter("ontologies/organization/organization_sample.csv"),
            shape="organization",
            registry=registry,
        )
        docs = pipeline.build_all()
        assert len(docs) > 0
        assert all(d["@type"] == "Organization" for d in docs)

Checklist
---------

.. list-table::
   :widths: 5 95
   :header-rows: 0

   * - ☐
     - SHACL Turtle file with ``sh:closed true`` and all property constraints
   * - ☐
     - JSON-LD context mapping CEDS IRIs to readable names
   * - ☐
     - Mapping YAML with source column mappings
   * - ☐
     - Sample CSV with representative data
   * - ☐
     - Tests: golden file, round-trip, edge cases
   * - ☐
     - Shape loads via ``registry.load_shape("name")``
   * - ☐
     - Full pipeline produces valid JSON-LD

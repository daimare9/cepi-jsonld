Getting Started
===============

This guide walks you through installing ``ceds-jsonld`` and converting your
first CSV file to CEDS-compliant JSON-LD.

Installation
------------

Core library (CSV, NDJSON, and dict support included)::

    pip install ceds-jsonld

With optional extras::

    pip install ceds-jsonld[fast]        # orjson for faster serialization
    pip install ceds-jsonld[excel]       # Excel file support
    pip install ceds-jsonld[cli]         # Command-line interface
    pip install ceds-jsonld[sheets]      # Google Sheets adapter
    pip install ceds-jsonld[snowflake]   # Snowflake adapter
    pip install ceds-jsonld[bigquery]    # BigQuery adapter
    pip install ceds-jsonld[databricks]  # Databricks adapter
    pip install ceds-jsonld[canvas]      # Canvas LMS adapter
    pip install ceds-jsonld[oneroster]   # OneRoster 1.1 SIS adapter
    pip install ceds-jsonld[warehouse]   # All cloud warehouse adapters
    pip install ceds-jsonld[sis]         # All SIS adapters (Canvas + OneRoster)
    pip install ceds-jsonld[all-adapters] # Every adapter extra
    pip install ceds-jsonld[all]         # Everything for production
    pip install ceds-jsonld[dev]         # Development and testing tools

Requires **Python 3.12+**.

Your First Conversion
---------------------

The fastest path from data to JSON-LD — five lines of Python:

.. code-block:: python

    from ceds_jsonld import Pipeline, ShapeRegistry, CSVAdapter

    registry = ShapeRegistry()
    registry.load_shape("person")

    pipeline = Pipeline(source=CSVAdapter("students.csv"), shape="person", registry=registry)
    pipeline.to_json("output/students.json")

Or use the CLI::

    ceds-jsonld convert -s person -i students.csv -o students.json

What Happens
~~~~~~~~~~~~

1. The **ShapeRegistry** loads the Person shape definition — SHACL constraints,
   JSON-LD context, and field mapping rules.
2. The **CSVAdapter** reads each row from your CSV file.
3. The **Pipeline** maps each row's columns to the Person shape properties, builds
   a JSON-LD document, and serializes the result.
4. Output is written as a JSON array to ``students.json``.

Understanding the Output
------------------------

Each record becomes a self-contained JSON-LD document:

.. code-block:: json

    {
        "@context": "https://cepi-dev.state.mi.us/ontology/context-person.json",
        "@type": "Person",
        "@id": "cepi:person/989897099",
        "hasPersonName": {
            "@type": "PersonName",
            "FirstName": "EDITH",
            "MiddleName": "M",
            "LastOrSurname": "ADAMS"
        },
        "hasPersonBirth": {
            "@type": "PersonBirth",
            "Birthdate": {"@type": "xsd:date", "@value": "1965-05-15"}
        }
    }

Key elements:

- ``@context`` — Points to the JSON-LD context that maps short names to full
  ontology IRIs.
- ``@type`` — The shape type (e.g. ``Person``).
- ``@id`` — A unique IRI for this record.
- Nested sub-shapes (``hasPersonName``, ``hasPersonBirth``, etc.) group
  related properties.

Handling Different Column Names
-------------------------------

Your CSV columns probably don't match the standard names. Override them at
runtime:

.. code-block:: python

    pipeline = Pipeline(
        source=CSVAdapter("students.csv"),
        shape="person",
        registry=registry,
        source_overrides={
            "hasPersonName": {
                "FirstName": "FIRST_NM",
                "LastOrSurname": "LAST_NM",
            },
        },
        id_source="STUDENT_ID",
    )

Validating Data
---------------

Check your data before (or after) building:

.. code-block:: python

    result = pipeline.validate(mode="report")
    if not result.conforms:
        for rec_id, issues in result.issues.items():
            print(f"Record {rec_id}: {[i.message for i in issues]}")

Or from the CLI::

    ceds-jsonld validate -s person -i students.csv

NDJSON Output
-------------

For large datasets, use NDJSON (one document per line). This streams records
to disk with constant memory:

.. code-block:: python

    pipeline.to_ndjson("output/students.ndjson")

Or::

    ceds-jsonld convert -s person -i students.csv -o students.ndjson

Next Steps
----------

- :doc:`adding-a-shape` — Learn how to create a new shape (Organization, K-12
  Enrollment, etc.).
- :doc:`cosmos-setup` — Load documents into Azure Cosmos DB.
- :doc:`cli` — Full CLI reference.

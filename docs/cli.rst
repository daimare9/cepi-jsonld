CLI Reference
=============

The ``ceds-jsonld`` command-line interface provides six commands for common
data conversion, validation, and inspection workflows.

Install the CLI with::

    pip install ceds-jsonld[cli]

Commands
--------

convert
~~~~~~~

Convert a data file (CSV, Excel, NDJSON) to JSON-LD::

    ceds-jsonld convert -s person -i students.csv -o students.json
    ceds-jsonld convert -s person -i data.csv -o out.ndjson --compact

Options:

- ``-s, --shape`` — Shape name (required)
- ``-i, --input`` — Input file path (required)
- ``-o, --output`` — Output file path (required)
- ``-f, --format`` — Output format: ``json`` or ``ndjson`` (auto-detected from extension)
- ``--shapes-dir`` — Additional shape search directory
- ``--sheet`` — Sheet name for Excel files
- ``--validate / --no-validate`` — Run pre-build validation
- ``--pretty / --compact`` — Pretty-print or compact JSON (default: pretty)

validate
~~~~~~~~

Validate data against a SHACL shape::

    ceds-jsonld validate -s person -i students.csv
    ceds-jsonld validate -s person -i students.csv --shacl --mode sample

Options:

- ``-s, --shape`` — Shape name (required)
- ``-i, --input`` — Input file path (required)
- ``--shapes-dir`` — Additional shape search directory
- ``--mode`` — Validation mode: ``strict``, ``report``, or ``sample`` (default: report)
- ``--shacl / --no-shacl`` — Enable full SHACL round-trip validation
- ``--sample-rate`` — SHACL sample rate (default: 0.01 = 1%)

introspect
~~~~~~~~~~

Inspect a SHACL shape file::

    ceds-jsonld introspect --shacl Person_SHACL.ttl
    ceds-jsonld introspect --shacl Person_SHACL.ttl --json

Options:

- ``--shacl`` — Path to SHACL Turtle file (required)
- ``--json`` — Output as JSON instead of human-readable text

generate-mapping
~~~~~~~~~~~~~~~~

Generate a mapping YAML template from a SHACL shape::

    ceds-jsonld generate-mapping --shacl Person_SHACL.ttl -o person_mapping.yaml

Options:

- ``--shacl`` — Path to SHACL Turtle file (required)
- ``-o, --output`` — Output YAML path (prints to stdout if omitted)
- ``--context-url`` — JSON-LD @context URL
- ``--base-uri`` — Base URI prefix for @id values
- ``--context-file`` — JSON-LD context file for human-readable names

list-shapes
~~~~~~~~~~~

List all available shapes::

    ceds-jsonld list-shapes
    ceds-jsonld list-shapes --shapes-dir ./my-shapes

benchmark
~~~~~~~~~

Run a performance benchmark::

    ceds-jsonld benchmark -s person
    ceds-jsonld benchmark -s person -n 1000000

Options:

- ``-s, --shape`` — Shape name (required)
- ``-n, --records`` — Number of records (default: 100,000)
- ``--shapes-dir`` — Additional shape search directory

ADR-002: YAML Mapping Configuration
====================================

**Status:** Accepted

**Date:** 2025

Context
-------

The library needs a way to describe how source data columns map to JSON-LD
properties. Two approaches were considered:

1. **SHACL-only** — Derive all mapping information from the SHACL shape.
2. **YAML alongside SHACL** — Use a separate YAML file for mappings, with
   SHACL defining constraints.

Decision
--------

**Use YAML mapping files alongside SHACL shapes.**

Rationale
---------

SHACL defines *constraints* (what is valid), not *mappings* (where data comes
from). SHACL cannot express:

- Which CSV column maps to which property
- How to split pipe-delimited multi-value fields
- What transform to apply (e.g. ``"Female"`` → ``"Sex_Female"``)
- Default values for ``RecordStatus``/``DataCollection`` sub-shapes

YAML provides a clean, human-editable format for this information:

.. code-block:: yaml

    properties:
      hasPersonName:
        type: PersonName
        fields:
          FirstName:
            source: "FIRST_NM"
            transform: "strip"
          LastOrSurname:
            source: "LAST_NM"

Tradeoffs
---------

**We gain:** Full control over source-to-target mapping, including transforms,
defaults, and composition (base + overlay configs).

**We accept:** An additional file to maintain per shape. Mitigated by the
``generate-mapping`` CLI/API which scaffolds a YAML template from SHACL.

**Validation:** The ``SHACLIntrospector.validate_mapping()`` method checks
that a mapping YAML is consistent with its SHACL shape.

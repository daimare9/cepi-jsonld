ceds-jsonld Documentation
=========================

**Python library for converting education data into standards-compliant JSON-LD
documents backed by the** `CEDS ontology <https://ceds.ed.gov/>`_.

Read data from CSV, Excel, databases, APIs, Google Sheets, SIS platforms
(Canvas, OneRoster, PowerSchool, Blackbaud), cloud data warehouses
(Snowflake, BigQuery, Databricks), or plain dicts. Map it to
SHACL-defined shapes. Get conformant JSON-LD ready for Cosmos DB or any
downstream system.

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   getting-started
   adding-a-shape
   cosmos-setup

.. toctree::
   :maxdepth: 2
   :caption: CLI Reference

   cli

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/pipeline
   api/registry
   api/builder
   api/mapping
   api/adapters
   api/validator
   api/introspector
   api/serializer
   api/cosmos
   api/cli
   api/exceptions

.. toctree::
   :maxdepth: 2
   :caption: Architecture

   adr/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

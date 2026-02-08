Cosmos DB Setup
===============

This guide covers loading JSON-LD documents into Azure Cosmos DB NoSQL.

Prerequisites
-------------

1. An Azure Cosmos DB NoSQL account (or the local emulator).
2. Install the Cosmos extra::

       pip install ceds-jsonld[cosmos]

Container Strategy
------------------

The library follows a **one container per shape** pattern:

- ``person`` container for Person documents
- ``organization`` container for Organization documents
- etc.

This provides:

- Shape-specific indexing policies for optimal query performance
- Independent throughput (RU/s) and TTL per shape
- Simpler partition key management
- Cost isolation between data domains

Document Preparation
--------------------

Before upserting, each document needs two Cosmos-required fields:

- ``id`` — Cosmos's required document identifier (copied from ``@id``)
- ``partitionKey`` — The partition key value (defaults to ``@type``)

The library handles this automatically via ``prepare_for_cosmos()``:

.. code-block:: python

    from ceds_jsonld import prepare_for_cosmos

    # Before:
    # {"@context": "...", "@type": "Person", "@id": "cepi:person/12345", ...}

    cosmos_doc = prepare_for_cosmos(doc)

    # After — same doc with "id" and "partitionKey" injected:
    # {"@context": "...", "@type": "Person", "@id": "cepi:person/12345",
    #  "id": "cepi:person/12345", "partitionKey": "Person", ...}

Loading via Pipeline (Recommended)
-----------------------------------

The simplest approach — Pipeline handles building, preparation, and uploading:

.. code-block:: python

    from azure.identity import DefaultAzureCredential
    from ceds_jsonld import Pipeline, ShapeRegistry, CSVAdapter

    registry = ShapeRegistry()
    registry.load_shape("person")

    pipeline = Pipeline(
        source=CSVAdapter("students.csv"),
        shape="person",
        registry=registry,
    )

    result = pipeline.to_cosmos(
        endpoint="https://myaccount.documents.azure.com:443/",
        credential=DefaultAzureCredential(),
        database="ceds",
    )

    print(f"Loaded {result.succeeded}/{result.total} ({result.total_ru:.0f} RU)")

Parameters:

- ``endpoint`` — Your Cosmos DB account URI.
- ``credential`` — An ``azure.identity`` TokenCredential (or master key string
  for the local emulator).
- ``database`` — Target database name.
- ``container`` — Container name (defaults to the shape name).
- ``partition_value`` — Explicit partition key (defaults to ``@type``).
- ``concurrency`` — Max parallel upserts (default 25).
- ``create_if_missing`` — Create database/container if they don't exist.

Loading via CosmosLoader (Advanced)
------------------------------------

For more control, use ``CosmosLoader`` directly:

.. code-block:: python

    import asyncio
    from azure.identity.aio import DefaultAzureCredential
    from ceds_jsonld import CosmosLoader

    async def upload(docs):
        async with CosmosLoader(
            endpoint="https://myaccount.documents.azure.com:443/",
            credential=DefaultAzureCredential(),
            database="ceds",
            container="person",
        ) as loader:
            # Bulk upsert
            result = await loader.upsert_many(docs)

            # Or one at a time
            single = await loader.upsert_one(docs[0])

        return result

    result = asyncio.run(upload(my_docs))

Authentication
--------------

**Recommended: Managed Identity / DefaultAzureCredential**

.. code-block:: python

    from azure.identity import DefaultAzureCredential
    credential = DefaultAzureCredential()

This works in Azure (Managed Identity), local development (``az login``),
and CI/CD (environment variables).

**Master key (emulator/development only)**

.. code-block:: python

    credential = "your-master-key-here"

.. warning::

    Never store master keys in source code for production deployments.
    Use Azure Key Vault and managed identity instead.

Indexing Policy
---------------

The library provides a recommended indexing policy optimized for JSON-LD
documents::

    from ceds_jsonld.cosmos import RECOMMENDED_INDEXING_POLICY

This policy:

- **Includes**: ``/id``, ``/partitionKey``, ``/@type``
- **Excludes**: ``/*`` (all deep-nested paths)

This saves RU cost on writes. Add manual includes for any fields you
query often.

Error Handling
--------------

The loader handles common Cosmos errors:

- **429 Too Many Requests** — Automatic retry with exponential backoff (handled
  by the Azure SDK).
- **413 Payload Too Large** — Raised as ``CosmosError`` with the document ``@id``.
- **409 Conflict** — Upsert semantics mean this is handled automatically (insert
  or replace).

Local Emulator
--------------

For development without an Azure account, use the
`Cosmos DB emulator <https://learn.microsoft.com/en-us/azure/cosmos-db/emulator>`_::

    docker run -p 8081:8081 -p 10250-10255:10250-10255 \
        mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator

Then connect with::

    pipeline.to_cosmos(
        endpoint="https://localhost:8081/",
        credential="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==",
        database="ceds",
    )

.. note::

    The emulator uses a fixed well-known master key (shown above) and a
    self-signed TLS certificate. You may need to disable certificate
    verification in development.

# Azure Cosmos DB Python SDK Reference — ceds-jsonld

**Version:** 4.14.6 (azure-cosmos)
**Docs:** https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/sdk-python
**Last updated:** 2025-01-20

## Installation

```bash
pip install azure-cosmos azure-identity
```

## Role in This Project

Cosmos DB NoSQL is the target data store. Each SHACL shape maps to a dedicated container.
JSON-LD documents are upserted after building.

## API Reference

### Client Initialization

```python
# Sync client (for batch scripts)
from azure.cosmos import CosmosClient

client = CosmosClient(url=ENDPOINT, credential=KEY)

# Async client (for high-throughput loading)
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient
from azure.identity.aio import DefaultAzureCredential

async with AsyncCosmosClient(ENDPOINT, credential=DefaultAzureCredential()) as client:
    ...

# AAD authentication (preferred for production)
from azure.identity import DefaultAzureCredential
client = CosmosClient(url=ENDPOINT, credential=DefaultAzureCredential())
```

### Database Operations

```python
# Create if not exists
database = client.create_database_if_not_exists(id="ceds-jsonld")

# Get existing
database = client.get_database_client("ceds-jsonld")

# List databases
for db in client.list_databases():
    print(db["id"])
```

### Container Operations

```python
from azure.cosmos import PartitionKey

# Create with partition key
container = database.create_container_if_not_exists(
    id="person",
    partition_key=PartitionKey(path="/partitionKey"),
    offer_throughput=400,  # RU/s (minimum)
)

# Get existing
container = database.get_container_client("person")
```

### Document Operations

```python
# Create (fails if exists)
container.create_item(body=doc)

# Upsert (create or replace) — PREFERRED
container.upsert_item(body=doc)

# Read by ID + partition key
item = container.read_item(item="doc-id", partition_key="partition-value")

# Query
items = container.query_items(
    query="SELECT * FROM c WHERE c.partitionKey = @pk",
    parameters=[{"name": "@pk", "value": "some-value"}],
    enable_cross_partition_query=False,
)
for item in items:
    print(item)

# Delete
container.delete_item(item="doc-id", partition_key="partition-value")
```

### Async Operations

```python
from azure.cosmos.aio import CosmosClient

async with CosmosClient(ENDPOINT, credential=credential) as client:
    database = client.get_database_client("ceds-jsonld")
    container = database.get_container_client("person")

    # Async upsert
    await container.upsert_item(body=doc)

    # Async query
    async for item in container.query_items(
        query="SELECT * FROM c WHERE c['@type'] = 'Person'",
    ):
        print(item)
```

### Transactional Batch

```python
# All operations in a batch must have the same partition key
batch = [
    ("upsert", (doc1,), {}),
    ("upsert", (doc2,), {}),
    ("upsert", (doc3,), {}),
]
container.execute_item_batch(batch_operations=batch, partition_key="pk-value")
```

### Response Headers (RU Tracking)

```python
response = container.upsert_item(body=doc)
# Access request charge from headers
ru_charge = container.client_connection.last_response_headers.get("x-ms-request-charge")
```

## Usage Patterns for This Project

### Document Preparation

```python
def prepare_for_cosmos(jsonld_doc: dict, partition_value: str) -> dict:
    """Add Cosmos-required fields to a JSON-LD document."""
    doc = jsonld_doc.copy()
    doc["id"] = jsonld_doc["@id"].rsplit("/", 1)[-1]
    doc["partitionKey"] = partition_value
    return doc
```

### Bulk Loading Pattern

```python
import asyncio
from azure.cosmos.aio import CosmosClient

async def bulk_load(docs: list[dict], container_name: str):
    async with CosmosClient(ENDPOINT, credential=credential) as client:
        db = client.get_database_client("ceds-jsonld")
        container = db.get_container_client(container_name)

        sem = asyncio.Semaphore(25)  # Control concurrency
        async def _upsert(doc):
            async with sem:
                await container.upsert_item(body=doc)

        await asyncio.gather(*[_upsert(d) for d in docs])
```

### Container-per-Shape Setup

```python
SHAPES = ["person", "organization", "k12enrollment"]

async def setup_containers(database):
    for shape in SHAPES:
        await database.create_container_if_not_exists(
            id=shape,
            partition_key=PartitionKey(path="/partitionKey"),
        )
```

## Gotchas & Notes

- Document max size is 2MB. Our JSON-LD docs are ~4KB so this is not a concern.
- `id` field is required and must be a string. Auto-generate from `@id`.
- `partitionKey` must be consistent — all queries must provide it for single-partition queries.
- Boolean values in queries: use `true`/`false` (lowercase), not Python `True`/`False`.
- The SDK auto-retries 429 (throttled) with exponential backoff — do not add custom retry.
- Use `enable_cross_partition_query=True` for queries that span partitions (slower, more RU).
- Cosmos DB creates system properties (`_rid`, `_self`, `_etag`, `_ts`) automatically.

## Error Handling

```python
from azure.cosmos.exceptions import (
    CosmosResourceExistsError,    # 409 - already exists
    CosmosResourceNotFoundError,  # 404 - not found
    CosmosHttpResponseError,      # Generic HTTP error
)

try:
    container.upsert_item(body=doc)
except CosmosHttpResponseError as e:
    print(f"Status: {e.status_code}, Message: {e.message}")
```

## Performance Notes

- Upsert is ~5-10 RU for a 4KB document
- Query by partition key: ~3-5 RU
- Cross-partition query: significantly more RU
- Use async client for bulk loading (25-50x faster than sync for large batches)
- Monitor RU consumption via `x-ms-request-charge` header

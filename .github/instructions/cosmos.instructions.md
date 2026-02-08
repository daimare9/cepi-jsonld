---
applyTo: "**/cosmos/**/*.py,**/cosmos.py"
---
# Cosmos DB Integration Instructions — ceds-jsonld

## SDK Reference

Always read `.github/docs/library-reference/azure-cosmos-reference.md` before writing Cosmos DB code.

## Client Pattern

- Use a SINGLE `CosmosClient` instance per application. Do not create a new client per operation.
- Use `DefaultAzureCredential` for production auth, master key only for local/emulator.
- Always use `async with` context manager for the async client.
- Set `preferred_locations` for multi-region read optimization.

```python
# Production pattern
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

async def get_client():
    credential = DefaultAzureCredential()
    async with CosmosClient(ENDPOINT, credential=credential) as client:
        yield client

# Emulator pattern (local dev)
from azure.cosmos import CosmosClient

client = CosmosClient(
    "https://localhost:8081",
    credential="C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==",
)
```

## Container Strategy

- **One container per shape type** (Person, Organization, etc.)
- Container naming: lowercase shape name (e.g., `person`, `organization`, `k12enrollment`)
- Partition key: use `/partitionKey` field (injected by the loader), value = data collection ID or `@type`

## Document Design

JSON-LD documents need adaptation for Cosmos DB:

1. **`id` field required** — Cosmos requires a string `id` at the root. Copy from `@id` and strip the URI prefix.
2. **`partitionKey` field** — Inject this from the mapping config before upsert.
3. **`@context` handling** — Store as a URL string reference, not an embedded object (saves space, avoids drift).

```python
def prepare_for_cosmos(doc: dict, partition_value: str) -> dict:
    """Prepare a JSON-LD document for Cosmos DB upsert."""
    cosmos_doc = doc.copy()
    # Cosmos requires 'id' at root
    cosmos_doc["id"] = doc["@id"].rsplit("/", 1)[-1]
    # Inject partition key
    cosmos_doc["partitionKey"] = partition_value
    return cosmos_doc
```

## Indexing Policy

For JSON-LD documents, use a selective indexing policy to reduce RU cost on writes:

```json
{
    "indexingMode": "consistent",
    "automatic": true,
    "includedPaths": [
        {"path": "/id/?"},
        {"path": "/partitionKey/?"},
        {"path": "/\"@type\"/?"}
    ],
    "excludedPaths": [
        {"path": "/*"}
    ]
}
```

Only index fields you query on. Deep nested fields like `hasRecordStatus` and `hasDataCollection` should be excluded.

## Bulk Operations

The Python SDK does NOT have a native bulk executor. Use async concurrency:

```python
import asyncio

async def bulk_upsert(container, docs: list[dict], concurrency: int = 25):
    """Upsert documents with bounded concurrency."""
    semaphore = asyncio.Semaphore(concurrency)
    total_ru = 0.0

    async def _upsert_one(doc):
        nonlocal total_ru
        async with semaphore:
            response = await container.upsert_item(doc)
            total_ru += response.get_response_headers().get("x-ms-request-charge", 0)

    await asyncio.gather(*[_upsert_one(doc) for doc in docs])
    return total_ru
```

## Error Handling

- **429 Too Many Requests** — The SDK handles retry automatically with exponential backoff. Do not add custom retry for 429.
- **413 Payload Too Large** — Document exceeds 2MB. Log it and skip. JSON-LD Person docs are ~4KB so this should never happen for normal shapes.
- **409 Conflict** — `upsert_item` handles this by design (upsert = update if exists).
- Always surface the RU charge in logs for cost monitoring.

## Testing

- Use the Cosmos DB emulator for integration tests
- Never run tests against production Cosmos DB
- Mock the Cosmos client for unit tests of the loader logic
- Integration tests should create/destroy containers in setup/teardown

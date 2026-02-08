"""CosmosLoader — async bulk loader for Azure Cosmos DB NoSQL.

Wraps the ``azure-cosmos`` async SDK with sensible defaults for
uploading JSON-LD documents produced by the ceds-jsonld pipeline.

Supports:
- ``DefaultAzureCredential`` (production / managed identity)
- Master key string (local emulator / dev)
- Single and bulk upsert with bounded concurrency
- Automatic ``id`` / ``partitionKey`` injection via :func:`prepare_for_cosmos`
- Per-batch RU cost tracking
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ceds_jsonld.cosmos.prepare import prepare_for_cosmos
from ceds_jsonld.exceptions import CosmosError
from ceds_jsonld.logging import get_logger

_log = get_logger(__name__)


# ------------------------------------------------------------------
# Result types
# ------------------------------------------------------------------


@dataclass
class UpsertResult:
    """Summary of a single upsert operation."""

    document_id: str
    status: str  # "success" or "error"
    ru_charge: float = 0.0
    error: str | None = None


@dataclass
class BulkResult:
    """Summary of a bulk upsert batch."""

    total: int = 0
    succeeded: int = 0
    failed: int = 0
    total_ru: float = 0.0
    errors: list[UpsertResult] = field(default_factory=list)


# ------------------------------------------------------------------
# Indexing policy recommendation
# ------------------------------------------------------------------

#: Recommended Cosmos DB indexing policy for JSON-LD containers.
#: Indexes only ``id``, ``partitionKey``, and ``@type``.  All other
#: paths (deep nested sub-shapes) are excluded to reduce RU cost on
#: writes.
RECOMMENDED_INDEXING_POLICY: dict[str, Any] = {
    "indexingMode": "consistent",
    "automatic": True,
    "includedPaths": [
        {"path": "/id/?"},
        {"path": "/partitionKey/?"},
        {"path": '/"@type"/?'},
    ],
    "excludedPaths": [
        {"path": "/*"},
    ],
}


# ------------------------------------------------------------------
# CosmosLoader
# ------------------------------------------------------------------


class CosmosLoader:
    """Async loader for upserting JSON-LD documents into Cosmos DB NoSQL.

    Instantiate once and reuse — the underlying ``CosmosClient`` is
    designed as a singleton per application.

    Args:
        endpoint: Cosmos DB account URI (e.g. ``https://myaccount.documents.azure.com:443/``).
        credential: Either an ``azure.identity`` *TokenCredential* (recommended
            for production — pass ``DefaultAzureCredential()`` or
            ``ManagedIdentityCredential()``) or a plain master-key string
            (acceptable for the local emulator or development).
        database: Database name.  Created automatically on first use if
            *create_if_missing* is ``True``.
        container: Container name.  Created automatically on first use if
            *create_if_missing* is ``True``.
        partition_key_path: Cosmos partition key path used when auto-creating
            the container.  Defaults to ``/partitionKey``.
        partition_value: Value injected into every document's ``partitionKey``
            field.  Defaults to the document's ``@type``.
        create_if_missing: If ``True`` (default), the database and container
            are created automatically on the first operation.
        concurrency: Maximum number of parallel upserts in
            :meth:`upsert_many`.  The Azure SDK retries 429 (throttled)
            automatically; tuning this controls how aggressively we push.

    Example::

        from azure.identity.aio import DefaultAzureCredential
        from ceds_jsonld.cosmos import CosmosLoader

        loader = CosmosLoader(
            endpoint="https://myaccount.documents.azure.com:443/",
            credential=DefaultAzureCredential(),
            database="ceds",
            container="person",
        )
        async with loader:
            result = await loader.upsert_many(docs)
            print(f"Loaded {result.succeeded} docs, {result.total_ru:.1f} RU")
    """

    def __init__(
        self,
        endpoint: str,
        credential: Any,
        database: str,
        container: str,
        *,
        partition_key_path: str = "/partitionKey",
        partition_value: str | None = None,
        create_if_missing: bool = True,
        concurrency: int = 25,
    ) -> None:
        self._endpoint = endpoint
        self._credential = credential
        self._database_name = database
        self._container_name = container
        self._partition_key_path = partition_key_path
        self._partition_value = partition_value
        self._create_if_missing = create_if_missing
        self._concurrency = concurrency

        # Lazy-initialised SDK objects.
        self._client: Any = None
        self._database: Any = None
        self._container: Any = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> CosmosLoader:
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying Cosmos client."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._database = None
            self._container = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upsert_one(self, doc: dict[str, Any]) -> UpsertResult:
        """Upsert a single JSON-LD document.

        The document is automatically prepared for Cosmos (``id`` and
        ``partitionKey`` injected) if those fields are not already present.

        Args:
            doc: A JSON-LD document dict.

        Returns:
            An :class:`UpsertResult` with status and RU charge.
        """
        container = await self._ensure_container()
        cosmos_doc = self._prepare(doc)
        doc_id = cosmos_doc.get("id", "unknown")

        try:
            response = await container.upsert_item(body=cosmos_doc)
            ru = self._extract_ru(response)
            _log.debug("cosmos.upserted", doc_id=doc_id, ru=ru)
            return UpsertResult(document_id=doc_id, status="success", ru_charge=ru)
        except Exception as exc:
            _log.error("cosmos.upsert_failed", doc_id=doc_id, error=str(exc))
            return UpsertResult(document_id=doc_id, status="error", error=str(exc))

    async def upsert_many(
        self,
        docs: list[dict[str, Any]],
        *,
        concurrency: int | None = None,
    ) -> BulkResult:
        """Upsert multiple JSON-LD documents with bounded concurrency.

        Uses ``asyncio.Semaphore`` to limit parallel requests.  The Azure
        SDK handles 429-retry automatically with exponential backoff.

        Args:
            docs: List of JSON-LD document dicts.
            concurrency: Override the instance-level concurrency limit.

        Returns:
            A :class:`BulkResult` summarising the batch.
        """
        container = await self._ensure_container()
        sem = asyncio.Semaphore(concurrency or self._concurrency)
        result = BulkResult(total=len(docs))

        async def _upsert(doc: dict[str, Any]) -> UpsertResult:
            cosmos_doc = self._prepare(doc)
            doc_id = cosmos_doc.get("id", "unknown")
            async with sem:
                try:
                    response = await container.upsert_item(body=cosmos_doc)
                    ru = self._extract_ru(response)
                    return UpsertResult(document_id=doc_id, status="success", ru_charge=ru)
                except Exception as exc:
                    return UpsertResult(document_id=doc_id, status="error", error=str(exc))

        results = await asyncio.gather(*[_upsert(d) for d in docs])

        for r in results:
            if r.status == "success":
                result.succeeded += 1
                result.total_ru += r.ru_charge
            else:
                result.failed += 1
                result.errors.append(r)

        _log.info(
            "cosmos.bulk_complete",
            succeeded=result.succeeded,
            total=result.total,
            ru=result.total_ru,
            failed=result.failed,
        )
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _prepare(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Prepare a document for Cosmos, injecting id/partitionKey if needed."""
        if "id" in doc and "partitionKey" in doc:
            return doc
        return prepare_for_cosmos(doc, partition_value=self._partition_value)

    @staticmethod
    def _extract_ru(response: Any) -> float:
        """Extract request-unit charge from the SDK response.

        The async SDK returns the upserted document dict directly; the RU
        charge is in the response headers accessed through the container's
        ``client_connection``.  However, the async SDK surfaces this via
        the response headers property.  We try multiple known paths.
        """
        # The response from upsert_item is the document dict itself.
        # RU charge is typically in response headers — try common patterns.
        try:
            headers = getattr(response, "get_response_headers", None)
            if callable(headers):
                return float(headers().get("x-ms-request-charge", 0))
        except Exception:
            pass
        return 0.0

    async def _ensure_client(self) -> Any:
        """Lazily create the async CosmosClient."""
        if self._client is not None:
            return self._client

        try:
            from azure.cosmos.aio import CosmosClient
        except ImportError as exc:
            msg = "azure-cosmos is required for Cosmos DB integration. Install it with: pip install ceds-jsonld[cosmos]"
            raise CosmosError(msg) from exc

        self._client = CosmosClient(self._endpoint, credential=self._credential)
        return self._client

    async def _ensure_database(self) -> Any:
        """Get or create the database."""
        if self._database is not None:
            return self._database

        client = await self._ensure_client()
        if self._create_if_missing:
            self._database = await client.create_database_if_not_exists(id=self._database_name)
        else:
            self._database = client.get_database_client(self._database_name)
        return self._database

    async def _ensure_container(self) -> Any:
        """Get or create the container with the recommended indexing policy."""
        if self._container is not None:
            return self._container

        try:
            from azure.cosmos import PartitionKey
        except ImportError as exc:
            msg = "azure-cosmos is required for Cosmos DB integration. Install it with: pip install ceds-jsonld[cosmos]"
            raise CosmosError(msg) from exc

        database = await self._ensure_database()
        if self._create_if_missing:
            self._container = await database.create_container_if_not_exists(
                id=self._container_name,
                partition_key=PartitionKey(path=self._partition_key_path),
                indexing_policy=RECOMMENDED_INDEXING_POLICY,
            )
        else:
            self._container = database.get_container_client(self._container_name)
        return self._container

"""Document preparation utilities for Cosmos DB.

Transforms JSON-LD documents into Cosmos-ready format by injecting the
required ``id`` and ``partitionKey`` fields.
"""

from __future__ import annotations

from typing import Any


def prepare_for_cosmos(
    doc: dict[str, Any],
    *,
    partition_value: str | None = None,
    id_field: str = "@id",
) -> dict[str, Any]:
    """Prepare a JSON-LD document for Cosmos DB upsert.

    Cosmos DB requires a string ``id`` at the document root and benefits
    from an explicit ``partitionKey`` field.  This function copies the
    original document (no mutation) and injects both fields.

    Args:
        doc: A JSON-LD document dict (must contain *id_field*).
        partition_value: Value for the ``partitionKey`` field.  Defaults to
            the document's ``@type`` if not provided.
        id_field: The key in *doc* that holds the document identifier.
            Defaults to ``"@id"``.  The URI prefix is stripped automatically
            (everything up to and including the last ``/``).

    Returns:
        A shallow copy of *doc* with ``id`` and ``partitionKey`` injected.

    Raises:
        KeyError: If *id_field* is missing from *doc*.

    Example::

        >>> from ceds_jsonld.cosmos import prepare_for_cosmos
        >>> doc = {"@id": "cepi:person/12345", "@type": "Person", ...}
        >>> cosmos_doc = prepare_for_cosmos(doc)
        >>> cosmos_doc["id"]
        '12345'
        >>> cosmos_doc["partitionKey"]
        'Person'
    """
    if id_field not in doc:
        msg = (
            f"Document is missing '{id_field}'. Cannot prepare for Cosmos DB. "
            f"Available keys: {sorted(doc.keys())}"
        )
        raise KeyError(msg)

    cosmos_doc = doc.copy()

    # Extract the trailing identifier from the URI.
    raw_id = str(doc[id_field])
    cosmos_doc["id"] = raw_id.rsplit("/", 1)[-1] if "/" in raw_id else raw_id

    # Partition key: explicit value, or fall back to @type.
    if partition_value is not None:
        cosmos_doc["partitionKey"] = partition_value
    elif "@type" in doc:
        cosmos_doc["partitionKey"] = str(doc["@type"])
    else:
        cosmos_doc["partitionKey"] = cosmos_doc["id"]

    return cosmos_doc

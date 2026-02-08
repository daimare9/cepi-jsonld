"""Abstract base class for all source adapters.

Every adapter must implement ``read()`` (single-record iterator) and
``read_batch()`` (chunked iterator).  Adapters yield plain Python dicts
ready for :class:`~ceds_jsonld.mapping.FieldMapper`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class SourceAdapter(ABC):
    """Abstract base for all data source adapters.

    Subclasses provide access to raw records as plain dicts.
    """

    @abstractmethod
    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Yield raw records one at a time.

        Returns:
            An iterator of dicts, each representing a single source record.
        """
        ...

    def read_batch(self, batch_size: int = 1000, **kwargs: Any) -> Iterator[list[dict[str, Any]]]:
        """Yield batches of raw records.

        Default implementation chunks the output of ``read()``.
        Subclasses may override for more efficient native batching.

        Args:
            batch_size: Number of records per batch.

        Returns:
            An iterator of lists of dicts.
        """
        batch: list[dict[str, Any]] = []
        for record in self.read(**kwargs):
            batch.append(record)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def count(self) -> int | None:
        """Return the total number of records, or ``None`` if unknown.

        Subclasses may override to provide an efficient count without
        reading all records (e.g., ``SELECT COUNT(*)`` or file row count).
        """
        return None

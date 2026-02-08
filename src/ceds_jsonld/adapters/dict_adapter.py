"""Dictionary source adapter — pass-through for in-memory data.

No external dependencies required. Accepts a single dict, a list of dicts,
or any iterable of dicts.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Iterator

from ceds_jsonld.adapters.base import SourceAdapter


class DictAdapter(SourceAdapter):
    """Wrap in-memory dicts as a source adapter.

    This is the simplest adapter — useful for tests, API handlers, or
    any code that already has data in dict form.

    Example:
        >>> data = [{"FirstName": "Alice"}, {"FirstName": "Bob"}]
        >>> adapter = DictAdapter(data)
        >>> list(adapter.read())
        [{'FirstName': 'Alice'}, {'FirstName': 'Bob'}]
    """

    def __init__(self, data: dict[str, Any] | Iterable[dict[str, Any]]) -> None:
        """Initialize with one dict or an iterable of dicts.

        Args:
            data: A single record dict **or** an iterable (list, generator, etc.)
                of record dicts.
        """
        if isinstance(data, dict):
            self._data: list[dict[str, Any]] = [data]
        else:
            # Materialise so count() and repeated read() work.
            self._data = list(data)

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Yield each dict in order.

        Returns:
            Iterator of dicts.
        """
        yield from self._data

    def count(self) -> int | None:
        """Return the number of records.

        Returns:
            Length of the internal list.
        """
        return len(self._data)

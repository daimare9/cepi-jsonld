"""HTTP/REST API source adapter — fetch records via paginated API calls.

Requires the ``httpx`` optional dependency (``pip install ceds-jsonld[api]``).
Supports cursor-based, offset-based, and link-header pagination out of the box.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError


class APIAdapter(SourceAdapter):
    """Fetch records from a paginated REST/HTTP API.

    Example:
        >>> adapter = APIAdapter(
        ...     url="https://api.example.com/students",
        ...     headers={"Authorization": "Bearer TOKEN"},
        ...     pagination="offset",
        ...     page_size=100,
        ...     results_key="data",
        ... )
        >>> for row in adapter.read():
        ...     print(row["FirstName"])
    """

    # Supported pagination strategies
    _STRATEGIES = {"none", "offset", "cursor", "link"}

    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        results_key: str | None = None,
        pagination: str = "none",
        page_size: int = 100,
        offset_param: str = "offset",
        limit_param: str = "limit",
        cursor_param: str = "cursor",
        cursor_response_key: str = "next_cursor",
        timeout: float = 30.0,
    ) -> None:
        """Initialize the API adapter.

        Args:
            url: Base URL for the API endpoint.
            method: HTTP method (default ``GET``).
            headers: Optional HTTP headers (auth, content-type, etc.).
            params: Optional base query-string parameters.
            body: Optional JSON body for POST/PUT requests.
            results_key: JSON key that contains the list of records in the
                response.  When ``None``, the response itself must be a list.
            pagination: One of ``"none"``, ``"offset"``, ``"cursor"``, or
                ``"link"`` (RFC 8288 Link header).
            page_size: Number of records per request (for offset/cursor modes).
            offset_param: Query-param name for the offset value.
            limit_param: Query-param name for the page-size value.
            cursor_param: Query-param name for cursor value.
            cursor_response_key: Response JSON key containing the next cursor.
            timeout: Request timeout in seconds.
        """
        if pagination not in self._STRATEGIES:
            msg = f"Unknown pagination strategy '{pagination}'. Use one of {sorted(self._STRATEGIES)}."
            raise AdapterError(msg)

        self._url = url
        self._method = method.upper()
        self._headers = headers or {}
        self._base_params = params or {}
        self._body = body
        self._results_key = results_key
        self._pagination = pagination
        self._page_size = page_size
        self._offset_param = offset_param
        self._limit_param = limit_param
        self._cursor_param = cursor_param
        self._cursor_response_key = cursor_response_key
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Yield records from the API, following pagination automatically.

        Returns:
            Iterator of dicts.
        """
        client = self._make_client()
        try:
            if self._pagination == "none":
                yield from self._fetch_single(client)
            elif self._pagination == "offset":
                yield from self._fetch_offset(client)
            elif self._pagination == "cursor":
                yield from self._fetch_cursor(client)
            elif self._pagination == "link":
                yield from self._fetch_link(client)
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"API request failed: {exc}"
            raise AdapterError(msg) from exc
        finally:
            client.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_client(self) -> Any:
        """Create an httpx.Client with configured headers/timeout."""
        try:
            import httpx
        except ImportError as exc:
            msg = "httpx is required for API support. Install with: pip install ceds-jsonld[api]"
            raise AdapterError(msg) from exc
        return httpx.Client(headers=self._headers, timeout=self._timeout)

    def _request(self, client: Any, params: dict[str, Any]) -> Any:
        """Perform a single HTTP request and return the parsed JSON."""
        import httpx

        merged = {**self._base_params, **params}
        try:
            if self._method == "GET":
                resp = client.get(self._url, params=merged)
            else:
                resp = client.request(
                    self._method,
                    self._url,
                    params=merged,
                    json=self._body,
                )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            msg = f"API returned HTTP {exc.response.status_code} for {self._url}"
            raise AdapterError(msg) from exc
        return resp

    def _extract_records(self, data: Any) -> list[dict[str, Any]]:
        """Pull the record list out of a parsed JSON response.

        Supports dot-notation paths (e.g. ``"students.student"``) for
        nested response structures such as PowerSchool's API.
        """
        if self._results_key:
            obj = data
            for segment in self._results_key.split("."):
                if not isinstance(obj, dict) or segment not in obj:
                    msg = f"Response missing expected key '{self._results_key}'"
                    raise AdapterError(msg)
                obj = obj[segment]
            records = obj
        else:
            records = data
        if not isinstance(records, list):
            msg = "Expected a list of records from the API response"
            raise AdapterError(msg)
        return records

    # -- Strategies ------------------------------------------------

    def _fetch_single(self, client: Any) -> Iterator[dict[str, Any]]:
        """No pagination — single request."""
        resp = self._request(client, {})
        yield from self._extract_records(resp.json())

    def _fetch_offset(self, client: Any) -> Iterator[dict[str, Any]]:
        """Offset-based: increment ``offset`` until an empty page."""
        offset = 0
        while True:
            params = {self._offset_param: offset, self._limit_param: self._page_size}
            resp = self._request(client, params)
            records = self._extract_records(resp.json())
            if not records:
                break
            yield from records
            if len(records) < self._page_size:
                break
            offset += self._page_size

    def _fetch_cursor(self, client: Any) -> Iterator[dict[str, Any]]:
        """Cursor-based: follow ``cursor_response_key`` until absent/null."""
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {self._limit_param: self._page_size}
            if cursor is not None:
                params[self._cursor_param] = cursor
            resp = self._request(client, params)
            data = resp.json()
            records = self._extract_records(data)
            if not records:
                break
            yield from records
            cursor = data.get(self._cursor_response_key) if isinstance(data, dict) else None
            if not cursor:
                break

    def _fetch_link(self, client: Any) -> Iterator[dict[str, Any]]:
        """Link-header (RFC 8288) pagination: follow ``rel="next"``."""
        import httpx

        params: dict[str, Any] = {self._limit_param: self._page_size}
        url: str | None = self._url
        while url:
            if url == self._url:
                resp = self._request(client, params)
            else:
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    msg = f"API returned HTTP {exc.response.status_code} for {url}"
                    raise AdapterError(msg) from exc
            records = self._extract_records(resp.json())
            if not records:
                break
            yield from records
            url = self._parse_next_link(resp.headers.get("link", ""))

    @staticmethod
    def _parse_next_link(header: str) -> str | None:
        """Extract the ``rel="next"`` URL from a Link header value."""
        for part in header.split(","):
            segment = part.strip()
            if 'rel="next"' in segment or "rel='next'" in segment:
                url_start = segment.find("<")
                url_end = segment.find(">")
                if url_start != -1 and url_end != -1:
                    return segment[url_start + 1 : url_end]
        return None

"""OneRoster 1.1 source adapter — read from any OneRoster-compliant SIS.

Works with Infinite Campus, ClassLink, Clever, Aeries, and any other
platform that implements the IMS OneRoster 1.1 REST specification.

Requires ``httpx`` (``pip install ceds-jsonld[oneroster]``).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError

# Standard OneRoster 1.1 resource endpoints
_ONEROSTER_RESOURCES = {
    "users",
    "students",
    "teachers",
    "orgs",
    "enrollments",
    "courses",
    "classes",
    "academicSessions",
    "demographics",
    "lineItems",
    "results",
    "gradingPeriods",
    "terms",
    "categories",
}


class OneRosterAdapter(SourceAdapter):
    """Read education data from any OneRoster 1.1 compliant SIS.

    The adapter handles pagination, OAuth authentication, and flattening
    of the OneRoster JSON envelope.

    Example:
        >>> adapter = OneRosterAdapter(
        ...     base_url="https://sis.example.com/ims/oneroster/v1p1",
        ...     resource="users",
        ...     bearer_token="eyJ...",
        ...     filter_expr="role='student'",
        ... )
        >>> for row in adapter.read():
        ...     print(row["givenName"], row["familyName"])

    With OAuth client-credentials:

        >>> adapter = OneRosterAdapter(
        ...     base_url="https://sis.example.com/ims/oneroster/v1p1",
        ...     resource="enrollments",
        ...     client_id="my_client_id",
        ...     client_secret="my_client_secret",
        ...     token_url="https://sis.example.com/oauth/token",
        ... )
    """

    def __init__(
        self,
        base_url: str,
        resource: str,
        *,
        bearer_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_url: str | None = None,
        filter_expr: str | None = None,
        page_size: int = 100,
        flatten: bool = True,
        timeout: float = 30.0,
    ) -> None:
        """Initialize with a OneRoster base URL and resource type.

        Args:
            base_url: Root OneRoster endpoint, typically ending in
                ``/ims/oneroster/v1p1``.
            resource: OneRoster resource to fetch (e.g. ``"users"``,
                ``"enrollments"``, ``"orgs"``).
            bearer_token: Pre-obtained OAuth bearer token.
            client_id: OAuth2 client ID for client-credentials flow.
            client_secret: OAuth2 client secret.
            token_url: OAuth2 token endpoint URL (required when using
                client_id/client_secret).
            filter_expr: OneRoster filter expression
                (e.g. ``"role='student'"``).
            page_size: Records per page (``limit`` parameter).
            flatten: If ``True`` (default), flatten nested objects such as
                ``orgs[0].sourcedId`` → ``org_sourcedId``.
            timeout: HTTP request timeout in seconds.

        Raises:
            AdapterError: If required arguments are missing or invalid.
        """
        if not base_url:
            msg = "base_url must not be empty"
            raise AdapterError(msg)
        if resource not in _ONEROSTER_RESOURCES:
            msg = f"Unknown OneRoster resource '{resource}'. Choose one of: {sorted(_ONEROSTER_RESOURCES)}"
            raise AdapterError(msg)

        has_token = bearer_token is not None
        has_oauth = client_id is not None and client_secret is not None
        if not has_token and not has_oauth:
            msg = "No authentication provided. Supply either 'bearer_token' or both 'client_id' and 'client_secret'."
            raise AdapterError(msg)

        if has_oauth and not token_url:
            msg = "token_url is required when using client_id/client_secret OAuth authentication."
            raise AdapterError(msg)

        self._base_url = base_url.rstrip("/")
        self._resource = resource
        self._bearer_token = bearer_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._filter_expr = filter_expr
        self._page_size = page_size
        self._flatten = flatten
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Paginate through the OneRoster resource and yield dicts.

        Returns:
            Iterator of dicts, one per OneRoster record.

        Raises:
            AdapterError: If httpx is missing, auth fails, or any API
                call errors out.
        """
        httpx = self._import_httpx()
        token = self._resolve_token(httpx)
        client = self._make_client(httpx, token)

        try:
            offset = 0
            while True:
                records = self._fetch_page(client, offset)
                if not records:
                    break
                for record in records:
                    yield self._process_record(record)
                if len(records) < self._page_size:
                    break
                offset += self._page_size
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"OneRoster API request failed: {exc}"
            raise AdapterError(msg) from exc
        finally:
            client.close()

    def count(self) -> int | None:
        """Return ``None`` — OneRoster does not expose total counts."""
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_httpx() -> Any:
        """Lazy-import httpx."""
        try:
            import httpx  # noqa: WPS433

            return httpx
        except ImportError as exc:
            msg = "httpx is required for OneRoster support. Install with: pip install ceds-jsonld[oneroster]"
            raise AdapterError(msg) from exc

    def _resolve_token(self, httpx: Any) -> str:
        """Return a bearer token, fetching via OAuth if needed."""
        if self._bearer_token:
            return self._bearer_token

        # Client-credentials OAuth2 flow
        try:
            resp = httpx.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            token = data.get("access_token")
            if not token:
                msg = f"OAuth token response missing 'access_token'. Response keys: {list(data.keys())}"
                raise AdapterError(msg)
            return str(token)
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"OAuth token request failed: {exc}"
            raise AdapterError(msg) from exc

    def _make_client(self, httpx: Any, token: str) -> Any:
        """Create an httpx.Client with auth headers."""
        return httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=self._timeout,
        )

    def _fetch_page(self, client: Any, offset: int) -> list[dict[str, Any]]:
        """Fetch one page of records from the OneRoster endpoint."""
        httpx_mod = self._import_httpx()

        url = f"{self._base_url}/{self._resource}"
        params: dict[str, Any] = {
            "offset": offset,
            "limit": self._page_size,
        }
        if self._filter_expr:
            params["filter"] = self._filter_expr

        try:
            resp = client.get(url, params=params)
            resp.raise_for_status()
        except httpx_mod.HTTPStatusError as exc:
            msg = f"OneRoster API returned HTTP {exc.response.status_code} for {url}"
            raise AdapterError(msg) from exc

        data = resp.json()

        # OneRoster wraps records in a key matching the resource name
        if isinstance(data, dict) and self._resource in data:
            records: list[dict[str, Any]] = data[self._resource]
            return records
        if isinstance(data, list):
            return data  # type: ignore[return-value]

        msg = (
            f"Unexpected OneRoster response structure. Expected key "
            f"'{self._resource}' in response. Got keys: "
            f"{list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
        )
        raise AdapterError(msg)

    def _process_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Optionally flatten nested OneRoster objects."""
        if not self._flatten:
            return record
        return self._flatten_record(record)

    @staticmethod
    def _flatten_record(record: dict[str, Any]) -> dict[str, Any]:
        """Flatten nested lists/dicts in a OneRoster record.

        Nested dicts are flattened with a ``key_subkey`` prefix.
        Lists of dicts use indexed keys to preserve **all** elements:
        ``{"orgs": [{"sourcedId": "A"}, {"sourcedId": "B"}]}`` becomes
        ``{"org_0_sourcedId": "A", "org_1_sourcedId": "B", "orgs_count": 2}``.

        Raises:
            AdapterError: If a generated key would collide with an
                existing key in the record.
        """
        flat: dict[str, Any] = {}

        def _safe_set(target: dict[str, Any], k: str, v: Any) -> None:
            if k in target:
                msg = (
                    f"Key collision during record flattening: '{k}' "
                    f"already exists with value {target[k]!r}. "
                    f"Cannot overwrite with {v!r}."
                )
                raise AdapterError(msg)
            target[k] = v

        for key, value in record.items():
            if isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    _safe_set(flat, f"{key}_{sub_key}", sub_val)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                singular = key.rstrip("s") if key.endswith("s") else key
                for idx, element in enumerate(value):
                    for sub_key, sub_val in element.items():
                        _safe_set(flat, f"{singular}_{idx}_{sub_key}", sub_val)
                _safe_set(flat, f"{key}_count", len(value))
            else:
                _safe_set(flat, key, value)
        return flat

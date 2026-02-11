"""Factory functions for SIS platforms that use standard REST APIs.

PowerSchool and Blackbaud SKY work with the existing
:class:`~ceds_jsonld.adapters.api_adapter.APIAdapter`; these helpers
pre-configure the adapter with vendor-specific defaults so users only
provide their credentials and district URL.

Requires ``httpx`` (``pip install ceds-jsonld[api]``).
"""

from __future__ import annotations

from typing import Any

from ceds_jsonld.adapters.api_adapter import APIAdapter
from ceds_jsonld.exceptions import AdapterError

# ------------------------------------------------------------------
# PowerSchool
# ------------------------------------------------------------------

_POWERSCHOOL_RESOURCES: dict[str, str] = {
    "students": "/ws/v1/district/student",
    "staff": "/ws/v1/district/staff",
    "schools": "/ws/v1/district/school",
    "sections": "/ws/v1/district/section",
    "enrollments": "/ws/v1/district/enrollment",
}

_POWERSCHOOL_RESULTS_KEYS: dict[str, str] = {
    "students": "students.student",
    "staff": "staff.staff",
    "schools": "schools.school",
    "sections": "sections.section",
    "enrollments": "enrollments.enrollment",
}


def powerschool_adapter(
    base_url: str,
    access_token: str,
    resource: str = "students",
    *,
    page_size: int = 100,
    extra_params: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> APIAdapter:
    """Create an :class:`APIAdapter` pre-configured for PowerSchool SIS.

    PowerSchool uses OAuth2 client-credentials for its Plugin Data Access
    API.  Obtain an ``access_token`` by POSTing to
    ``{base_url}/oauth/access_token`` with your plugin credentials.

    Example:
        >>> adapter = powerschool_adapter(
        ...     base_url="https://district.powerschool.com",
        ...     access_token="<your_bearer_token>",
        ...     resource="students",
        ... )
        >>> for row in adapter.read():
        ...     print(row["local_id"], row["name"])

    Args:
        base_url: PowerSchool instance URL
            (e.g. ``https://district.powerschool.com``).
        access_token: OAuth2 bearer token.
        resource: Data resource to fetch.  One of ``"students"``,
            ``"staff"``, ``"schools"``, ``"sections"``, ``"enrollments"``.
        page_size: Records per API page.
        extra_params: Additional query-string parameters.
        timeout: HTTP request timeout in seconds.

    Returns:
        A configured :class:`APIAdapter` instance.

    Raises:
        AdapterError: If arguments are invalid.
    """
    if not base_url:
        msg = "base_url must not be empty"
        raise AdapterError(msg)
    if not access_token:
        msg = "access_token must not be empty"
        raise AdapterError(msg)
    if resource not in _POWERSCHOOL_RESOURCES:
        msg = f"Unknown PowerSchool resource '{resource}'. Choose one of: {sorted(_POWERSCHOOL_RESOURCES)}"
        raise AdapterError(msg)

    url = f"{base_url.rstrip('/')}{_POWERSCHOOL_RESOURCES[resource]}"
    results_key = _POWERSCHOOL_RESULTS_KEYS[resource]

    return APIAdapter(
        url=url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        params=extra_params,
        results_key=results_key,
        pagination="offset",
        page_size=page_size,
        offset_param="page",
        limit_param="pagesize",
        timeout=timeout,
    )


# ------------------------------------------------------------------
# Blackbaud SKY API
# ------------------------------------------------------------------

_BLACKBAUD_RESOURCES: dict[str, str] = {
    "users": "/school/v1/users",
    "students": "/school/v1/students",
    "sections": "/school/v1/sections",
    "enrollments": "/school/v1/enrollment",
    "schools": "/school/v1/schools",
    "courses": "/school/v1/academics/courses",
}


def blackbaud_adapter(
    access_token: str,
    subscription_key: str,
    resource: str = "students",
    *,
    base_url: str = "https://api.sky.blackbaud.com",
    page_size: int = 100,
    extra_params: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> APIAdapter:
    """Create an :class:`APIAdapter` pre-configured for Blackbaud SKY API.

    Blackbaud requires both an OAuth2 bearer token AND a subscription key
    (``Bb-Api-Subscription-Key`` header).  The token is obtained via the
    OAuth2 Authorization Code flow through
    `developer.blackbaud.com <https://developer.blackbaud.com/skyapi>`_.

    Example:
        >>> adapter = blackbaud_adapter(
        ...     access_token="<your_bearer_token>",
        ...     subscription_key="<your_subscription_key>",
        ...     resource="students",
        ... )
        >>> for row in adapter.read():
        ...     print(row["first_name"], row["last_name"])

    Args:
        access_token: OAuth2 bearer token.
        subscription_key: Blackbaud developer subscription key.
        resource: Data resource to fetch.  One of ``"users"``,
            ``"students"``, ``"sections"``, ``"enrollments"``,
            ``"schools"``, ``"courses"``.
        base_url: Blackbaud SKY API base URL (default is production).
        page_size: Records per API page.
        extra_params: Additional query-string parameters.
        timeout: HTTP request timeout in seconds.

    Returns:
        A configured :class:`APIAdapter` instance.

    Raises:
        AdapterError: If arguments are invalid.
    """
    if not access_token:
        msg = "access_token must not be empty"
        raise AdapterError(msg)
    if not subscription_key:
        msg = "subscription_key must not be empty"
        raise AdapterError(msg)
    if resource not in _BLACKBAUD_RESOURCES:
        msg = f"Unknown Blackbaud resource '{resource}'. Choose one of: {sorted(_BLACKBAUD_RESOURCES)}"
        raise AdapterError(msg)

    url = f"{base_url.rstrip('/')}{_BLACKBAUD_RESOURCES[resource]}"

    return APIAdapter(
        url=url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Bb-Api-Subscription-Key": subscription_key,
            "Accept": "application/json",
        },
        params=extra_params,
        results_key="value",
        pagination="offset",
        page_size=page_size,
        timeout=timeout,
    )

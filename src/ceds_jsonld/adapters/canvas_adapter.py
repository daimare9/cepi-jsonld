"""Canvas LMS source adapter — read records via canvasapi.

Requires the ``canvasapi`` optional dependency
(``pip install ceds-jsonld[canvas]``).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ceds_jsonld.adapters.base import SourceAdapter
from ceds_jsonld.exceptions import AdapterError

# Resources that live under an account
_ACCOUNT_RESOURCES = {"users", "courses", "sis_imports"}
# Resources that live under a course
_COURSE_RESOURCES = {"enrollments", "students", "assignments", "sections"}


class CanvasAdapter(SourceAdapter):
    """Read education data from Canvas LMS via the canvasapi library.

    Handles the ``PaginatedList`` objects returned by canvasapi and
    converts each Canvas object to a plain dict.

    Example:
        >>> adapter = CanvasAdapter(
        ...     base_url="https://school.instructure.com",
        ...     api_key="your_token",
        ...     resource="users",
        ...     account_id=1,
        ... )
        >>> for row in adapter.read():
        ...     print(row["name"])

    Course-scoped resources:

        >>> adapter = CanvasAdapter(
        ...     base_url="https://school.instructure.com",
        ...     api_key="your_token",
        ...     resource="enrollments",
        ...     course_id=12345,
        ... )
    """

    _VALID_RESOURCES = _ACCOUNT_RESOURCES | _COURSE_RESOURCES

    def __init__(
        self,
        base_url: str,
        api_key: str,
        resource: str,
        *,
        account_id: int | str = "self",
        course_id: int | None = None,
        include: list[str] | None = None,
        per_page: int = 100,
    ) -> None:
        """Initialize with Canvas instance URL, API key, and resource type.

        Args:
            base_url: Root URL of the Canvas instance
                (e.g. ``https://school.instructure.com``).
            api_key: Personal access token or OAuth2 bearer token.
            resource: Which data to fetch.  One of ``"users"``,
                ``"courses"``, ``"enrollments"``, ``"students"``,
                ``"assignments"``, ``"sections"``, ``"sis_imports"``.
            account_id: Canvas account ID (default ``"self"``).
                Used for account-scoped resources.
            course_id: Canvas course ID.  Required for course-scoped
                resources (enrollments, students, assignments, sections).
            include: Extra fields to include in the response
                (e.g. ``["email", "enrollments"]``).
            per_page: Results per API page (max 100).

        Raises:
            AdapterError: If required arguments are missing or invalid.
        """
        if not base_url:
            msg = "base_url must not be empty"
            raise AdapterError(msg)
        if not api_key:
            msg = "api_key must not be empty"
            raise AdapterError(msg)
        if resource not in self._VALID_RESOURCES:
            msg = f"Unknown resource '{resource}'. Choose one of: {sorted(self._VALID_RESOURCES)}"
            raise AdapterError(msg)
        if resource in _COURSE_RESOURCES and course_id is None:
            msg = f"course_id is required for resource '{resource}'. Provide the Canvas course ID."
            raise AdapterError(msg)

        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._resource = resource
        self._account_id = account_id
        self._course_id = course_id
        self._include = include or []
        self._per_page = min(per_page, 100)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        """Iterate all Canvas objects for the configured resource.

        Returns:
            Iterator of dicts, one per Canvas object.

        Raises:
            AdapterError: If canvasapi is missing, auth fails, or the
                API call errors out.
        """
        canvasapi = self._import_canvasapi()
        canvas = self._get_canvas(canvasapi)
        paginated = self._get_resource(canvas)

        try:
            for obj in paginated:
                yield self._to_dict(obj)
        except AdapterError:
            raise
        except Exception as exc:
            msg = f"Canvas API request failed: {exc}"
            raise AdapterError(msg) from exc

    def count(self) -> int | None:
        """Return ``None`` — Canvas does not expose total counts."""
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_canvasapi() -> Any:
        """Lazy-import canvasapi."""
        try:
            import canvasapi as ca  # noqa: WPS433

            return ca
        except ImportError as exc:
            msg = "canvasapi is required for Canvas LMS support. Install with: pip install ceds-jsonld[canvas]"
            raise AdapterError(msg) from exc

    def _get_canvas(self, canvasapi: Any) -> Any:
        """Create a Canvas API client."""
        try:
            return canvasapi.Canvas(self._base_url, self._api_key)
        except Exception as exc:
            msg = f"Failed to connect to Canvas at '{self._base_url}': {exc}"
            raise AdapterError(msg) from exc

    def _get_resource(self, canvas: Any) -> Any:
        """Retrieve the paginated resource list from Canvas."""
        kwargs: dict[str, Any] = {"per_page": self._per_page}
        if self._include:
            kwargs["include"] = self._include

        try:
            if self._resource in _ACCOUNT_RESOURCES:
                account = canvas.get_account(self._account_id)
                method = getattr(account, f"get_{self._resource}")
                return method(**kwargs)
            else:
                course = canvas.get_course(self._course_id)
                method = getattr(course, f"get_{self._resource}")
                return method(**kwargs)
        except Exception as exc:
            msg = f"Failed to fetch '{self._resource}' from Canvas: {exc}"
            raise AdapterError(msg) from exc

    @staticmethod
    def _to_dict(obj: Any) -> dict[str, Any]:
        """Convert a canvasapi object to a flat dict.

        Strips private/internal attributes (those starting with ``_``)
        and the ``requester`` reference.
        """
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_") and k != "requester"}

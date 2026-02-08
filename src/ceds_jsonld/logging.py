"""Structured logging — structlog with stdlib logging fallback.

Provides a unified logging API regardless of whether ``structlog`` is installed.
Similar to the orjson/json pattern used in serializer.py.

Usage::

    from ceds_jsonld.logging import get_logger

    logger = get_logger(__name__)
    logger.info("pipeline.started", shape="person", records=1000)

When ``structlog`` is installed, log entries are structured (JSON-friendly key-value
pairs).  When not installed, falls back to stdlib ``logging`` with a readable format.

PII masking is built in — any key listed in ``PII_FIELDS`` is automatically redacted
before being emitted.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

# ---------------------------------------------------------------------------
# PII masking configuration
# ---------------------------------------------------------------------------

#: Field names whose values must never appear in log output.
PII_FIELDS: frozenset[str] = frozenset(
    {
        "ssn",
        "social_security_number",
        "date_of_birth",
        "dob",
        "birthdate",
        "person_identifier",
        "personidentifier",
        "personidentifiers",
        "first_name",
        "firstname",
        "last_name",
        "lastname",
        "lastorsurname",
        "middle_name",
        "middlename",
        "generationcodeorsuffix",
    }
)

_REDACTED = "***REDACTED***"


def _mask_pii(event_dict: dict[str, Any]) -> dict[str, Any]:
    """Redact PII fields from a log event dict.

    Args:
        event_dict: The structured log event.

    Returns:
        The event dict with sensitive values replaced by ``***REDACTED***``.
    """
    for key in list(event_dict.keys()):
        if key.lower() in PII_FIELDS:
            event_dict[key] = _REDACTED
    return event_dict


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

try:
    import structlog

    _BACKEND = "structlog"

    def _configure_structlog() -> None:
        """Configure structlog with sensible defaults for ceds-jsonld."""
        if structlog.is_configured():
            return

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                _structlog_pii_processor,  # type: ignore[list-item]
                structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    def _structlog_pii_processor(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        """structlog processor that redacts PII fields."""
        return _mask_pii(event_dict)

    _configure_structlog()

    def get_logger(name: str | None = None, **initial_values: Any) -> Any:
        """Get a structlog bound logger.

        Args:
            name: Logger name (typically ``__name__``).
            **initial_values: Key-value pairs bound to every log entry.

        Returns:
            A structlog ``BoundLogger`` instance.
        """
        return structlog.get_logger(name, **initial_values)

except ImportError:
    _BACKEND = "logging"

    class _StdlibStructuredLogger:
        """Stdlib logger wrapper that accepts structured key-value pairs.

        Provides the same ``logger.info("event", key=val)`` API as structlog
        but emits via the stdlib ``logging`` module with PII masking.
        """

        def __init__(self, logger: logging.Logger, **bound: Any) -> None:
            self._logger = logger
            self._bound: dict[str, Any] = bound

        def bind(self, **new_values: Any) -> _StdlibStructuredLogger:
            """Return a new logger with additional bound context."""
            merged = {**self._bound, **new_values}
            return _StdlibStructuredLogger(self._logger, **merged)

        def unbind(self, *keys: str) -> _StdlibStructuredLogger:
            """Return a new logger with specified keys removed."""
            merged = {k: v for k, v in self._bound.items() if k not in keys}
            return _StdlibStructuredLogger(self._logger, **merged)

        def _format(self, event: str, **kw: Any) -> str:
            """Format a structured log message."""
            merged = {**self._bound, **kw}
            merged = _mask_pii(merged)
            if merged:
                pairs = " ".join(f"{k}={v!r}" for k, v in merged.items())
                return f"{event} [{pairs}]"
            return event

        def debug(self, event: str, **kw: Any) -> None:
            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug(self._format(event, **kw))

        def info(self, event: str, **kw: Any) -> None:
            if self._logger.isEnabledFor(logging.INFO):
                self._logger.info(self._format(event, **kw))

        def warning(self, event: str, **kw: Any) -> None:
            if self._logger.isEnabledFor(logging.WARNING):
                self._logger.warning(self._format(event, **kw))

        def error(self, event: str, **kw: Any) -> None:
            if self._logger.isEnabledFor(logging.ERROR):
                self._logger.error(self._format(event, **kw))

        def exception(self, event: str, **kw: Any) -> None:
            self._logger.exception(self._format(event, **kw))

    def get_logger(name: str | None = None, **initial_values: Any) -> Any:  # type: ignore[misc]
        """Get a stdlib-backed structured logger.

        Args:
            name: Logger name (typically ``__name__``).
            **initial_values: Key-value pairs bound to every log entry.

        Returns:
            A ``_StdlibStructuredLogger`` that mimics the structlog API.
        """
        stdlib_logger = logging.getLogger(name or "ceds_jsonld")
        return _StdlibStructuredLogger(stdlib_logger, **initial_values)


def get_backend() -> str:
    """Return the name of the active logging backend ('structlog' or 'logging')."""
    return _BACKEND

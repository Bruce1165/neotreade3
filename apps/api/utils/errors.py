"""API error handling utilities."""

from http import HTTPStatus
from typing import Any, Optional


class ApiError(Exception):
    """Structured API exception used by router and handler."""

    def __init__(
        self,
        status_code: HTTPStatus,
        code: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def format_api_error(exc: Exception) -> tuple[HTTPStatus, dict[str, Any]]:
    """Format exception into HTTP status and JSON error payload."""
    if isinstance(exc, ApiError):
        return exc.status_code, {
            "_meta": {"status": "error"},
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        }

    # Fallback for unexpected exceptions
    return HTTPStatus.INTERNAL_SERVER_ERROR, {
        "_meta": {"status": "error"},
        "error": {
            "code": "INTERNAL_ERROR",
            "message": str(exc),
            "details": {},
        },
    }

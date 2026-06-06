"""Shared types for the NeoTrade3 bootstrap API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Optional


@dataclass
class ApiBinaryResponse:
    body: bytes
    content_type: str
    headers: dict[str, str]


def _safe_ref_path(raw: str) -> str:
    p = Path(str(raw or "")).name.strip()
    return "internal" if p else ""


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

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "details": self.details,
                "message": self.message,
            }
        }


def format_api_error(exc: Exception) -> tuple[HTTPStatus, dict[str, Any]]:
    _logger = logging.getLogger(__name__)

    if isinstance(exc, ApiError):
        return exc.status_code, exc.to_payload()
    if isinstance(exc, ValueError):
        error = ApiError(
            status_code=HTTPStatus.BAD_REQUEST,
            code="bad_request",
            message=str(exc),
        )
        return error.status_code, error.to_payload()
    _logger.error("Unhandled API exception: %s", exc, exc_info=True)
    error = ApiError(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="an unexpected internal error occurred",
    )
    return error.status_code, error.to_payload()

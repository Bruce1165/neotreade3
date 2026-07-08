"""HTTP handler and response utilities for the NeoTrade3 bootstrap API."""

from __future__ import annotations

import json
import logging
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any, Optional, TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from apps.api.service import BootstrapApiService

logger = logging.getLogger(__name__)


def build_handler(service: "BootstrapApiService") -> type[BaseHTTPRequestHandler]:
    from apps.api.router import BootstrapApiRouter
    from apps.api.shared import ApiBinaryResponse, ApiError, format_api_error

    router = BootstrapApiRouter(service)

    class RequestHandler(BaseHTTPRequestHandler):
        def _log_request_result(self, method: str, status: int, started_at: float) -> None:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            logger.warning(
                "API %s %s -> %s in %.1fms",
                method,
                self.path,
                int(status),
                elapsed_ms,
            )

        def _is_loopback_client(self) -> bool:
            try:
                ip = str(self.client_address[0] or "").strip()
            except Exception:
                return False
            return ip in {"127.0.0.1", "::1"}

        def _cors_origin(self) -> Optional[str]:
            origin = self.headers.get("Origin")
            if not origin:
                return None
            try:
                parsed = urlparse(origin)
            except Exception:
                return None
            host = (parsed.hostname or "").strip().lower()
            # Allow local development origins
            if host in {"127.0.0.1", "localhost", "0.0.0.0"}:
                return origin
            return None

        def _wants_debug_access(self) -> bool:
            try:
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
            except Exception:
                return False
            raw_debug = query.get("debug", ["false"])[0]
            return str(raw_debug).strip().lower() in {"1", "true", "yes", "y", "on"}

        def _require_api_key(
            self, *, allow_if_not_configured: bool, allow_loopback: bool = True
        ) -> None:
            if service.api_key is None:
                if allow_if_not_configured or (allow_loopback and self._is_loopback_client()):
                    return
                raise ApiError(
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                    code="api_key_not_configured",
                    message="API key is required",
                )
            provided = self.headers.get("X-API-Key")
            if provided and provided == service.api_key:
                return
            if allow_loopback and self._is_loopback_client():
                return
            raise ApiError(
                status_code=HTTPStatus.UNAUTHORIZED,
                code="unauthorized",
                message="missing or invalid API key",
            )

        def _accept_legacy_api_key(self) -> None:
            # API key auth is retained only as a backward-compatible header contract.
            # Active local write paths are no longer gated on it.
            provided = self.headers.get("X-API-Key")
            if not provided:
                return
            if service.api_key is None or provided == service.api_key:
                return
            raise ApiError(
                status_code=HTTPStatus.UNAUTHORIZED,
                code="unauthorized",
                message="invalid API key",
            )

        def _send_json_response(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True).encode(
                "utf-8"
            )
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            cors_origin = self._cors_origin()
            if cors_origin is not None:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
            self.end_headers()
            self.wfile.write(body)

        def _send_binary_response(self, status: int, payload: ApiBinaryResponse) -> None:
            self.send_response(int(status))
            self.send_header("Content-Type", payload.content_type)
            self.send_header("Content-Length", str(len(payload.body)))
            cors_origin = self._cors_origin()
            if cors_origin is not None:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
            for header_name, value in payload.headers.items():
                self.send_header(header_name, value)
            self.end_headers()
            self.wfile.write(payload.body)

        def _send_json_headers(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True).encode(
                "utf-8"
            )
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            cors_origin = self._cors_origin()
            if cors_origin is not None:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
            self.end_headers()

        def _send_binary_headers(self, status: int, payload: ApiBinaryResponse) -> None:
            self.send_response(int(status))
            self.send_header("Content-Type", payload.content_type)
            self.send_header("Content-Length", str(len(payload.body)))
            cors_origin = self._cors_origin()
            if cors_origin is not None:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
            for header_name, value in payload.headers.items():
                self.send_header(header_name, value)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            started_at = time.perf_counter()
            try:
                if self._wants_debug_access():
                    self._require_api_key(allow_if_not_configured=False, allow_loopback=False)
                status, payload = router.dispatch(self.path)
            except Exception as exc:
                status, payload = format_api_error(exc)
            self._log_request_result("GET", int(status), started_at)
            if isinstance(payload, ApiBinaryResponse):
                self._send_binary_response(int(status), payload)
            else:
                self._send_json_response(int(status), payload)

        def do_HEAD(self) -> None:  # noqa: N802
            started_at = time.perf_counter()
            try:
                if self._wants_debug_access():
                    self._require_api_key(allow_if_not_configured=False, allow_loopback=False)
                status, payload = router.dispatch(self.path)
            except Exception as exc:
                status, payload = format_api_error(exc)
            self._log_request_result("HEAD", int(status), started_at)
            if isinstance(payload, ApiBinaryResponse):
                self._send_binary_headers(int(status), payload)
            else:
                self._send_json_headers(int(status), payload)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(int(HTTPStatus.NO_CONTENT))
            cors_origin = self._cors_origin()
            if cors_origin is not None:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            started_at = time.perf_counter()
            try:
                self._accept_legacy_api_key()
                content_length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                if not isinstance(payload, dict):
                    raise ApiError(
                        status_code=HTTPStatus.BAD_REQUEST,
                        code="invalid_json",
                        message="request JSON body must be an object",
                    )
                status, response_payload = router.dispatch_post(self.path, payload)
            except Exception as exc:
                status, response_payload = format_api_error(exc)

            self._log_request_result("POST", int(status), started_at)
            self._send_json_response(int(status), response_payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    return RequestHandler

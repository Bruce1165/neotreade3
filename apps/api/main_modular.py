"""
NeoTrade3 API - Modular Version (2.0)

This is a refactored, modular version of the original main.py.
The original main.py is kept as backup for compatibility.

Usage:
    ./.venv/bin/python -m apps.api.main_modular --port 18031

Structure:
    - utils/: Error handling, caching utilities
    - handlers/: API endpoint handlers (to be expanded)
    - Original main.py: Kept as backup
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import traceback
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.api.utils.errors import ApiError, format_api_error
from apps.api.utils.cache import ApiCache
from neotrade3.common.python_runtime import log_python_runtime, require_python_310

logger = logging.getLogger(__name__)


@dataclass
class ApiContext:
    """API request context."""
    project_root: Path
    cache: ApiCache
    api_key: Optional[str] = None


class ModularApiHandler(BaseHTTPRequestHandler):
    """Modular HTTP request handler."""

    context: ApiContext

    def log_message(self, format: str, *args) -> None:
        """Override to use structured logging."""
        logger.info(f"{self.address_string()} - {format % args}")

    def _send_json(self, status: int, data: dict) -> None:
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))

    def _send_error(self, status: int, message: str) -> None:
        """Send error response."""
        self._send_json(status, {"_meta": {"status": "error"}, "error": {"message": message}})

    def _check_api_key(self) -> bool:
        """Check API key if configured."""
        if not self.context.api_key:
            return True
        auth_header = self.headers.get("X-API-Key", "")
        return auth_header == self.context.api_key

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests."""
        try:
            if not self._check_api_key():
                self._send_error(HTTPStatus.UNAUTHORIZED, "Invalid API key")
                return

            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            # Route to appropriate handler
            handler = self._get_handler(path)
            if handler:
                result = handler(params)
                self._send_json(HTTPStatus.OK, result)
            else:
                self._send_error(HTTPStatus.NOT_FOUND, f"Endpoint not found: {path}")

        except Exception as e:
            logger.error(f"Error handling GET {self.path}: {e}")
            logger.error(traceback.format_exc())
            status, error_data = format_api_error(e)
            self._send_json(status.value, error_data)

    def do_POST(self) -> None:
        """Handle POST requests."""
        try:
            if not self._check_api_key():
                self._send_error(HTTPStatus.UNAUTHORIZED, "Invalid API key")
                return

            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON body")
                return

            parsed = urlparse(self.path)
            path = parsed.path

            # Route to appropriate handler
            handler = self._post_handler(path)
            if handler:
                result = handler(data)
                self._send_json(HTTPStatus.OK, result)
            else:
                self._send_error(HTTPStatus.NOT_FOUND, f"Endpoint not found: {path}")

        except Exception as e:
            logger.error(f"Error handling POST {self.path}: {e}")
            logger.error(traceback.format_exc())
            status, error_data = format_api_error(e)
            self._send_json(status.value, error_data)

    def _get_handler(self, path: str):
        """Get GET handler for path."""
        handlers = {
            "/api/v1/health": self._health_check,
            "/api/v1/data/status": self._data_status,
            "/api/v1/sectors/hot": self._hot_sectors,
            "/api/v1/screeners": self._list_screeners,
        }
        return handlers.get(path)

    def _post_handler(self, path: str):
        """Get POST handler for path."""
        handlers = {
            "/api/v1/data/update": self._update_data,
            "/api/v1/model/run": self._run_model,
            "/api/v1/screeners/run-all": self._run_all_screeners,
        }
        return handlers.get(path)

    # ==================== Handlers ====================

    def _health_check(self, params: dict) -> dict:
        """Health check endpoint."""
        return {
            "_meta": {"status": "ok"},
            "service": "NeoTrade3 API Modular",
            "version": "2.0",
        }

    def _data_status(self, params: dict) -> dict:
        """Get data status."""
        cache_key = "data_status"
        cached = self.context.cache.get(cache_key)
        if cached:
            return cached

        try:
            import sqlite3
            db_path = self.context.project_root / "var" / "db" / "stock_data.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Get latest trade date
            cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
            latest_date = cursor.fetchone()[0]

            # Get total trading days
            cursor.execute("SELECT COUNT(DISTINCT trade_date) FROM daily_prices")
            total_days = cursor.fetchone()[0]

            # Get stock count for latest date
            cursor.execute(
                "SELECT COUNT(*) FROM daily_prices WHERE trade_date = ?",
                (latest_date,)
            )
            stock_count = cursor.fetchone()[0]

            conn.close()

            result = {
                "_meta": {"status": "ok"},
                "latest_trade_date": latest_date,
                "total_trading_days": total_days,
                "stock_count_latest": stock_count,
            }

            self.context.cache.set(cache_key, result, ttl_seconds=30)
            return result

        except Exception as e:
            logger.error(f"Error getting data status: {e}")
            raise ApiError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "DATA_STATUS_ERROR",
                f"Failed to get data status: {e}",
            )

    def _hot_sectors(self, params: dict) -> dict:
        """Get hot sectors."""
        raise ApiError(
            HTTPStatus.NOT_IMPLEMENTED,
            "NOT_IMPLEMENTED",
            "hot sectors endpoint is not implemented in main_modular.py yet",
        )

    def _list_screeners(self, params: dict) -> dict:
        """List available screeners."""
        try:
            from neotrade3.screeners.registry import load_screener_registry
            registry = load_screener_registry()
            screeners = [
                {
                    "id": sid,
                    "name": info.get("name", sid),
                    "description": info.get("description", ""),
                    "enabled": info.get("enabled", True),
                }
                for sid, info in registry.items()
            ]
            return {
                "_meta": {"status": "ok"},
                "screeners": screeners,
            }
        except Exception as e:
            logger.error(f"Error listing screeners: {e}")
            raise ApiError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "SCREENERS_REGISTRY_ERROR",
                f"Failed to load screener registry: {e}",
            )

    def _update_data(self, data: dict) -> dict:
        """Update local data."""
        raise ApiError(
            HTTPStatus.NOT_IMPLEMENTED,
            "NOT_IMPLEMENTED",
            "data update endpoint is not implemented in main_modular.py yet",
        )

    def _run_model(self, data: dict) -> dict:
        """Run quant model."""
        raise ApiError(
            HTTPStatus.NOT_IMPLEMENTED,
            "NOT_IMPLEMENTED",
            "model run endpoint is not implemented in main_modular.py yet",
        )

    def _run_all_screeners(self, data: dict) -> dict:
        """Run all screeners."""
        raise ApiError(
            HTTPStatus.NOT_IMPLEMENTED,
            "NOT_IMPLEMENTED",
            "run-all screeners endpoint is not implemented in main_modular.py yet",
        )


def build_handler(context: ApiContext) -> type[BaseHTTPRequestHandler]:
    """Build HTTP handler class with context."""
    handler_context = context

    class Handler(ModularApiHandler):
        context = handler_context

    return Handler


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="NeoTrade3 Modular API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=18030, help="Port to listen on")
    parser.add_argument("--api-key", default=os.environ.get("NEO_API_KEY", ""), help="API key for authentication")
    parser.add_argument("--project-root", type=Path, default=project_root, help="Project root directory")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    log_python_runtime(entrypoint="apps.api.main_modular", logger=logger)
    try:
        require_python_310(entrypoint="apps.api.main_modular")
    except RuntimeError as exc:
        logger.error(str(exc))
        return 2

    # Create context
    context = ApiContext(
        project_root=args.project_root,
        cache=ApiCache(),
        api_key=args.api_key if args.api_key else None,
    )

    # Build handler
    handler_class = build_handler(context)

    # Start server
    server = ThreadingHTTPServer((args.host, args.port), handler_class)
    logger.info(f"NeoTrade3 Modular API Server starting on {args.host}:{args.port}")
    logger.info(f"Project root: {args.project_root}")
    logger.info(f"API key required: {bool(args.api_key)}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

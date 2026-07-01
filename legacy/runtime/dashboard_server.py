#!/usr/bin/env python3
"""Deprecated dashboard server kept only as a historical reference.

The official V3 external release path is now:
cpolar -> Node frontend gateway -> dist/ + API proxy.
Do not extend this Python server as the formal release carrier.
"""

import http.server
import http.client
import json
import socketserver
from pathlib import Path
import socket
import socket as _socket
from urllib.parse import urlsplit

# Configuration
PORT = 5174
API_BASE = "http://127.0.0.1:18030"
STATIC_DIR = Path(__file__).parent / "neotrade3-dashboard" / "dist"
PROXY_TIMEOUT_SECONDS = 300


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Handler that serves static files and proxies API requests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        if self.path.startswith("/api") or self.path == "/healthz":
            self.proxy_request()
        else:
            # For SPA, serve index.html for non-file paths
            path = self.path.split("?")[0]
            file_path = STATIC_DIR / path.lstrip("/")
            
            if path != "/" and not file_path.exists():
                # Check if it's an asset path
                asset_path = STATIC_DIR / "assets" / path.lstrip("/assets/")
                if not asset_path.exists():
                    # Serve index.html for SPA routing
                    self.path = "/"
            
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api"):
            self.proxy_request()
        else:
            self.send_error(404, "Not Found")

    def proxy_request(self):
        """Proxy request to API server."""
        api = urlsplit(API_BASE)
        if api.scheme != "http":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unsupported API_BASE scheme"}).encode())
            return

        target_path = self.path

        try:
            # Read request body if present
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else None

            # Build headers (forward only what we need; keep X-API-Key intact)
            headers = {}
            for key, value in self.headers.items():
                lk = key.lower()
                if lk in ("host", "content-length", "connection", "proxy-connection"):
                    continue
                if lk == "accept-encoding":
                    continue
                headers[key] = value

            headers["Host"] = api.netloc
            headers["Connection"] = "close"
            if body is not None:
                headers["Content-Length"] = str(len(body))

            conn = http.client.HTTPConnection(
                host=api.hostname,
                port=api.port or 80,
                timeout=PROXY_TIMEOUT_SECONDS,
            )
            try:
                conn.request(self.command, target_path, body=body, headers=headers)
                resp = conn.getresponse()
                response_body = resp.read()

                self.send_response(resp.status)
                for key, value in resp.getheaders():
                    lk = key.lower()
                    if lk in ("transfer-encoding", "connection", "content-length", "server", "date"):
                        continue
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        except (OSError, http.client.HTTPException) as e:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

        except _socket.timeout:
            self.send_response(504)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "upstream timeout"}).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def end_headers(self):
        # Add CORS headers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress logging for cleaner output
        pass


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except OSError:
            pass
        super().server_bind()


if __name__ == "__main__":
    print(f"Starting NeoTrade3 Dashboard server...")
    print(f"  Dashboard: http://127.0.0.1:{PORT}/")
    print(f"  Dashboard (localhost alias): http://localhost:{PORT}/")
    print(f"  API Proxy: {API_BASE}")
    print(f"  Static Dir: {STATIC_DIR}")
    
    with ThreadedTCPServer(("::", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")

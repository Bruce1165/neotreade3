from __future__ import annotations

import json
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from apps.api.http import build_handler


class _HealthyService:
    api_key = None

    def health(self) -> dict[str, str]:
        return {"status": "ok"}


class _BrokenService:
    api_key = None

    def health(self) -> dict[str, str]:
        raise RuntimeError("boom")


@contextmanager
def _serve(service):
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(service))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _read(url: str) -> tuple[int, dict[str, str], dict]:
    request = Request(url)
    with urlopen(request, timeout=5) as response:
        status = int(getattr(response, "status", 200))
        body = json.loads(response.read().decode("utf-8"))
        return status, dict(response.headers.items()), body


def test_http_logs_successful_get_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[tuple[object, ...]] = []

    def _capture(*args: object, **_kwargs: object) -> None:
        messages.append(args)

    monkeypatch.setattr("apps.api.http.logger.warning", _capture)

    with _serve(_HealthyService()) as server:
        status, _, payload = _read(f"http://127.0.0.1:{server.server_port}/healthz")

    assert status == 200
    assert payload["status"] == "ok"
    assert messages
    fmt, method, path, status_code, elapsed_ms = messages[-1]
    assert fmt == "API %s %s -> %s in %.1fms"
    assert method == "GET"
    assert path == "/healthz"
    assert status_code == 200
    assert isinstance(elapsed_ms, float)


def test_http_logs_failed_get_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[tuple[object, ...]] = []

    def _capture(*args: object, **_kwargs: object) -> None:
        messages.append(args)

    monkeypatch.setattr("apps.api.http.logger.warning", _capture)

    with _serve(_BrokenService()) as server:
        with pytest.raises(HTTPError) as exc_info:
            _read(f"http://127.0.0.1:{server.server_port}/healthz")

    assert exc_info.value.code == 500
    assert messages
    fmt, method, path, status_code, elapsed_ms = messages[-1]
    assert fmt == "API %s %s -> %s in %.1fms"
    assert method == "GET"
    assert path == "/healthz"
    assert status_code == 500
    assert isinstance(elapsed_ms, float)

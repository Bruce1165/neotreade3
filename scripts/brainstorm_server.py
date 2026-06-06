#!/usr/bin/env python3
import argparse
import json
import os
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class SessionPaths:
    session_dir: Path
    screen_dir: Path
    state_dir: Path


FRAME_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>可视化伴侣</title>
    <style>
      :root {{
        --bg: #0b0d12;
        --panel: #121624;
        --panel2: #0f1320;
        --text: #e7e7ea;
        --muted: #a9adbb;
        --border: rgba(255,255,255,0.10);
        --accent: #6ea8ff;
        --accent2: #7ee7c0;
      }}
      * {{ box-sizing: border-box; }}
      html, body {{ height: 100%; }}
      body {{
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft Yahei", Arial, sans-serif;
        background: radial-gradient(1200px 600px at 20% -10%, rgba(110,168,255,0.22), transparent 50%),
                    radial-gradient(900px 500px at 100% 0%, rgba(126,231,192,0.16), transparent 55%),
                    var(--bg);
        color: var(--text);
      }}
      header {{
        padding: 14px 18px;
        border-bottom: 1px solid var(--border);
        background: rgba(18,22,36,0.72);
        backdrop-filter: blur(8px);
        position: sticky;
        top: 0;
        z-index: 10;
      }}
      .row {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
      }}
      .title {{
        font-weight: 650;
        letter-spacing: 0.2px;
      }}
      .meta {{
        color: var(--muted);
        font-size: 12px;
      }}
      main {{
        max-width: 1080px;
        margin: 0 auto;
        padding: 22px 18px 80px;
      }}
      h2 {{
        margin: 0 0 8px;
        font-size: 22px;
        font-weight: 680;
      }}
      p.subtitle {{
        margin: 0 0 18px;
        color: var(--muted);
      }}
      .options {{
        display: grid;
        gap: 12px;
      }}
      .option {{
        display: grid;
        grid-template-columns: 34px 1fr;
        gap: 12px;
        padding: 14px 14px;
        border: 1px solid var(--border);
        border-radius: 14px;
        background: linear-gradient(180deg, rgba(18,22,36,0.85), rgba(15,19,32,0.85));
        cursor: pointer;
        user-select: none;
      }}
      .option:hover {{
        border-color: rgba(110,168,255,0.35);
      }}
      .option.selected {{
        border-color: rgba(110,168,255,0.70);
        box-shadow: 0 0 0 1px rgba(110,168,255,0.22), 0 18px 48px rgba(0,0,0,0.35);
      }}
      .letter {{
        height: 28px;
        width: 28px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        color: #0b0d12;
        background: linear-gradient(135deg, rgba(110,168,255,1), rgba(126,231,192,1));
      }}
      .content h3 {{
        margin: 0 0 6px;
        font-size: 16px;
      }}
      .content p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.55;
      }}
      .indicator {{
        position: fixed;
        left: 18px;
        right: 18px;
        bottom: 18px;
        padding: 12px 14px;
        border: 1px solid var(--border);
        border-radius: 14px;
        background: rgba(18,22,36,0.72);
        backdrop-filter: blur(8px);
        max-width: 1080px;
        margin: 0 auto;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }}
      .indicator .hint {{
        color: var(--muted);
        font-size: 13px;
      }}
      .pill {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 10px;
        border-radius: 999px;
        background: rgba(110,168,255,0.16);
        border: 1px solid rgba(110,168,255,0.25);
        font-size: 13px;
      }}
      code {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 12px;
      }}
    </style>
  </head>
  <body>
    <header>
      <div class="row">
        <div class="title">可视化伴侣</div>
        <div class="meta">{meta}</div>
      </div>
    </header>
    <main>
      {content}
    </main>
    <div class="indicator">
      <div class="hint">点击选项即可选择；多选时可点选/取消。</div>
      <div class="pill">已选：<code id="sel">无</code></div>
    </div>
    <script>
      function postEvent(payload) {{
        try {{
          fetch('/events', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(payload),
            keepalive: true,
          }});
        }} catch (e) {{}}
      }}

      function getRootOptionsEl(el) {{
        let cur = el;
        while (cur && cur !== document.body) {{
          if (cur.classList && cur.classList.contains('options')) return cur;
          cur = cur.parentElement;
        }}
        return null;
      }}

      function toggleSelect(optionEl) {{
        const root = getRootOptionsEl(optionEl);
        const multi = root && root.hasAttribute('data-multiselect');
        const choice = optionEl.getAttribute('data-choice') || '';
        if (!multi) {{
          document.querySelectorAll('.option.selected').forEach(el => el.classList.remove('selected'));
          optionEl.classList.add('selected');
        }} else {{
          optionEl.classList.toggle('selected');
        }}
        const selected = Array.from(document.querySelectorAll('.option.selected')).map(el => el.getAttribute('data-choice')).filter(Boolean);
        document.getElementById('sel').textContent = selected.length ? selected.join(', ') : '无';
        postEvent({{ ts: new Date().toISOString(), type: 'select', selected, last: choice }});
      }}

      postEvent({{ ts: new Date().toISOString(), type: 'screen_view' }});
    </script>
  </body>
</html>
"""


def _new_session(project_dir: Path) -> SessionPaths:
    root = project_dir / ".superpowers" / "brainstorm"
    root.mkdir(parents=True, exist_ok=True)
    session_id = f"{os.getpid()}-{int(time.time())}"
    session_dir = root / session_id
    screen_dir = session_dir / "content"
    state_dir = session_dir / "state"
    screen_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    return SessionPaths(session_dir=session_dir, screen_dir=screen_dir, state_dir=state_dir)


def _find_latest_html(screen_dir: Path) -> Optional[Path]:
    candidates: list[Path] = []
    for p in screen_dir.iterdir():
        if p.is_file() and p.suffix.lower() in {".html", ".htm"}:
            candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _wrap_if_needed(html_text: str, *, meta: str) -> str:
    stripped = html_text.lstrip()
    if stripped.startswith("<!DOCTYPE") or stripped.startswith("<html"):
        return html_text
    return FRAME_TEMPLATE.format(meta=meta, content=html_text)


class _Handler(BaseHTTPRequestHandler):
    server_version = "BrainstormServer/0.1"

    def do_GET(self) -> None:
        if self.path not in {"/", "/index.html"}:
            self.send_error(HTTPStatus.NOT_FOUND, "not found")
            return

        screen_dir: Path = self.server.screen_dir  # type: ignore[attr-defined]
        latest = _find_latest_html(screen_dir)
        if latest is None:
            content = (
                "<h2>等待内容</h2>"
                "<p class=\"subtitle\">继续在终端里沟通，我会把下一页推送到这里。</p>"
                "<div style=\"display:flex;align-items:center;justify-content:center;min-height:40vh\">"
                "<p class=\"subtitle\">No screens yet.</p>"
                "</div>"
            )
            body = FRAME_TEMPLATE.format(meta="未检测到页面", content=content)
        else:
            raw = latest.read_text(encoding="utf-8", errors="replace")
            meta = f"{latest.name} · {time.strftime('%Y-%m-%d %H:%M:%S')}"
            body = _wrap_if_needed(raw, meta=meta)

        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        if self.path != "/events":
            self.send_error(HTTPStatus.NOT_FOUND, "not found")
            return

        raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        try:
            payload: Any = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = {"raw": raw.decode("utf-8", errors="replace")}

        state_dir: Path = self.server.state_dir  # type: ignore[attr-defined]
        events_path = state_dir / "events"
        with events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b"{\"ok\":true}")

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    session = _new_session(project_dir)

    httpd = ThreadingHTTPServer((args.host, int(args.port)), _Handler)
    httpd.screen_dir = session.screen_dir  # type: ignore[attr-defined]
    httpd.state_dir = session.state_dir  # type: ignore[attr-defined]

    host, port = httpd.server_address[0], httpd.server_address[1]
    url = f"http://{host}:{port}"
    info = {
        "type": "server-started",
        "port": port,
        "url": url,
        "screen_dir": str(session.screen_dir),
        "state_dir": str(session.state_dir),
    }

    (session.state_dir / "server-info").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(info, ensure_ascii=False))

    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            (session.state_dir / "server-stopped").write_text(
                json.dumps({"ts": time.time()}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

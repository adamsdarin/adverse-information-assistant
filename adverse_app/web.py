"""Dependency-free local browser interface.

It binds to loopback by default and never serves arbitrary files.
"""
from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from . import core
from . import codex_host


STYLE = """
body{font-family:system-ui,sans-serif;background:#f4f1ea;color:#1f2933;margin:0}
main{max-width:720px;margin:7vh auto;background:white;padding:2.5rem;border-radius:18px;box-shadow:0 12px 35px #0002}
h1{font-size:1.55rem;margin-top:0} .notice{background:#fff4ce;border-left:4px solid #a56b00;padding:1rem}
textarea,input{box-sizing:border-box;width:100%;padding:.9rem;border:1px solid #9aa5b1;border-radius:8px;font:inherit}
textarea{min-height:10rem} button{margin-top:1rem;padding:.8rem 1.2rem;border:0;border-radius:8px;background:#275d52;color:white;font-weight:650}
.meta{color:#52606d;font-size:.92rem}.error{color:#8b1e1e}.progress{margin:.8rem 0 1.5rem}
.chat{display:flex;flex-direction:column;gap:.8rem;margin:1.5rem 0}.msg{padding:.85rem 1rem;border-radius:12px;white-space:pre-wrap}.assistant{background:#e7f0ed}.user{background:#eef1f5;margin-left:12%}.busy{color:#52606d}
"""


def page(body: str, title: str = "Adverse Information Assistant") -> bytes:
    return f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>{html.escape(title)}</title><style>{STYLE}</style></head><body><main>{body}</main></body></html>".encode()


class AppHandler(BaseHTTPRequestHandler):
    session_path: Path

    def log_message(self, format: str, *args: object) -> None:
        # Do not write request paths or form contents to access logs.
        return

    def send_page(self, body: str, status: int = 200) -> None:
        data = page(body)
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_page("<h1>Not found</h1>", 404)
            return
        try:
            data = core.read_session(self.session_path)
        except core.SessionError:
            host = "Connected to the local Codex model host" if codex_host.available() else "AI model host unavailable"
            self.send_page(f"""<h1>Start a private working session</h1><p class='meta'>{host} · the conductor and specialist agents will run behind this chat</p><p class='notice'>This local working file is plaintext and unencrypted. Never enter classified information, a Social Security number, or a date of birth. Delete the working file after submission.</p><form method='post' action='/start'><label>Privacy tier</label><input name='privacy' value='high' required><button>Start AI-guided session</button></form>""")
            return
        messages = data.get("_runner", {}).get("browser_messages", [])
        rendered = "".join(f"<div class='msg {html.escape(m.get('role','assistant'))}'>{html.escape(m.get('text',''))}</div>" for m in messages)
        host = "Connected to the local Codex model host" if codex_host.available() else "AI model host unavailable"
        self.send_page(f"<h1>Adverse Information Assistant</h1><p class='meta'>{host} · checkpoint validation is enforced after every turn</p><p class='notice'>Do not enter classified information, an SSN, or a date of birth. This plaintext working session stays on this computer.</p><div class='chat'>{rendered}</div><form method='post' action='/message'><textarea name='message' required autofocus></textarea><button>Send</button></form>")

    def form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 100_000:
            raise core.SessionError("The submitted answer is too large.")
        values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        return {key: items[0] for key, items in values.items()}

    def redirect(self) -> None:
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_POST(self) -> None:
        try:
            if self.path == "/start":
                core.start(self.session_path, self.form().get("privacy", "high"))
                greeting = codex_host.turn(self.session_path, "Begin the session. I selected the privacy tier already recorded in the checkpoint.")
                codex_host.append_chat(self.session_path, "assistant", greeting)
            elif self.path == "/message":
                message = self.form().get("message", "").strip()
                if not message:
                    raise core.SessionError("Enter a response before sending.")
                codex_host.append_chat(self.session_path, "user", message)
                response = codex_host.turn(self.session_path, message)
                codex_host.append_chat(self.session_path, "assistant", response)
            elif self.path == "/validate":
                ok, detail = core.validate(self.session_path)
                if not ok:
                    raise core.SessionError(detail)
            else:
                self.send_page("<h1>Not found</h1>", 404)
                return
            self.redirect()
        except core.SessionError as exc:
            self.send_page(f"<h1>That could not be saved</h1><p class='error'>{html.escape(str(exc))}</p><p>Your last valid checkpoint is preserved.</p><p><a href='/'>Return</a></p>", 400)


def serve(session_path: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise core.SessionError("Phase 2 permits only a loopback host. Use 127.0.0.1.")
    handler = type("BoundAppHandler", (AppHandler,), {"session_path": session_path})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Local interface: http://{host}:{server.server_port}/")
    print("Press Ctrl+C to stop. No narrative content is written to access logs.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

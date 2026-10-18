"""stdlib HTTP portal — instructions + donor intent API."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from privatemind.portal.config import instruction_path, load_portal_config
from privatemind.portal.intents import append_donor_intent, list_donor_intents

PORTAL_VERSION = "0.1.0-skeleton"


def _html_hub() -> str:
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>PrivateMind portal</title></head>
<body>
<h1>PrivateMind resource portal</h1>
<p>Local entry for instructions and donor intents. Secrets stay in the CLI vault.</p>
<ul>
<li><a href="/instructions/admin">First-boot administrator</a></li>
<li><a href="/instructions/donor">Contributor / donor</a></li>
<li><a href="/instructions/helper">Helper (no servers)</a></li>
<li><a href="/api/v1/status">API status (JSON)</a></li>
</ul>
<p>POST donor intent: <code>/api/v1/donor/intent</code> (JSON)</p>
</body></html>"""


def make_handler(
    *,
    data_dir: Path,
    status_provider: Any,
) -> type[BaseHTTPRequestHandler]:
    config = load_portal_config()

    class PortalHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _send_json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, code: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
            body = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/":
                self._send_text(HTTPStatus.OK, _html_hub(), "text/html; charset=utf-8")
                return
            if path.startswith("/instructions/"):
                role = path.removeprefix("/instructions/").strip("/")
                try:
                    doc = instruction_path(config, role)
                    self._send_text(HTTPStatus.OK, doc.read_text(encoding="utf-8"))
                except (KeyError, OSError):
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "unknown_or_missing_instruction"})
                return
            if path == "/api/v1/status":
                base = status_provider()
                base["portal_version"] = PORTAL_VERSION
                base["donor_intent_count"] = len(list_donor_intents(data_dir))
                self._send_json(HTTPStatus.OK, base)
                return
            if path == "/api/v1/donor/intents":
                self._send_json(
                    HTTPStatus.OK,
                    {"intents": list_donor_intents(data_dir)},
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/api/v1/donor/intent":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
                return
            for field in ("display_name", "contact", "offer"):
                if not str(payload.get(field) or "").strip():
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"missing_{field}"})
                    return
            record = append_donor_intent(
                data_dir,
                display_name=str(payload["display_name"]),
                contact=str(payload["contact"]),
                offer=str(payload["offer"]),
                notes=str(payload.get("notes") or ""),
            )
            self._send_json(HTTPStatus.CREATED, {"intent": record})

    return PortalHandler


def serve_portal(
    *,
    host: str,
    port: int,
    data_dir: Path,
    status_provider: Any,
) -> None:
    handler = make_handler(data_dir=data_dir, status_provider=status_provider)
    server = ThreadingHTTPServer((host, port), handler)
    server.serve_forever()

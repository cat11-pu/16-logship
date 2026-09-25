"""server.py：本机服务（append/sync/state/recover）。"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from ship import Ship

SHIP = Ship()


class Handler(BaseHTTPRequestHandler):
    def _ship(self):
        return getattr(self.server, "ship", SHIP)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/sync"):
            offset = int(parse_qs(parsed.query).get("offset", ["0"])[0])
            result = self._ship().sync(offset)
        else:
            result = self._ship().state()
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        if self.path.startswith("/append"):
            result = self._ship().append(payload["key"], payload.get("value", ""), payload.get("offset"))
        elif self.path.startswith("/recover"):
            result = self._ship().recover()
        else:
            result = {}
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve(port: int = 0, ship: Ship | None = None):
    server = HTTPServer(("127.0.0.1", port), Handler)
    server.ship = ship if ship is not None else SHIP
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print("listening on http://127.0.0.1:%d" % port)
    serve(port, Ship(wal_path="ship.wal")).serve_forever()

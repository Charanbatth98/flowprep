"""Local web server for the visual canvas. Stdlib only - no web framework.

    flowprep serve            # http://127.0.0.1:8765
    python -m flowprep.server
"""
from __future__ import annotations
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .engine import catalog_for_ui, run_workflow

WEB = os.path.join(os.path.dirname(__file__), "web")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(json.dumps(obj).encode(), "application/json", code)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(WEB, "index.html"), "rb") as f:
                return self._send(f.read(), "text/html; charset=utf-8")
        if self.path == "/api/tools":
            return self._json({"tools": catalog_for_ui()})
        if self.path == "/api/health":
            return self._json({"ok": True})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/run":
            return self._json({"error": "not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            result = run_workflow(payload["workflow"], base_dir=payload.get("base_dir", "."))
            return self._json(result)
        except Exception as e:  # surface engine errors to the canvas, don't crash the server
            return self._json({"error": f"{type(e).__name__}: {e}"}, 400)


def main(port: int = 8765):
    print(f"FlowPrep canvas at http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()

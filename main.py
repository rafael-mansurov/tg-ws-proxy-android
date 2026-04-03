"""
HTTP server entry point for the WebView bootstrap.
Serves the UI and provides a REST API to control the proxy service.
"""
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST_PROXY = "127.0.0.1"
PORT_PROXY = 1443
SECRET = secrets.token_hex(16)
SERVE_PORT = int(os.environ.get("APP_SERVING_PORT", 8080))

UI_FILE = Path(__file__).parent / "ui" / "index.html"

_running = False


# ── service control ──────────────────────────────────────────────────────────

def _request_permissions() -> None:
    try:
        from android.permissions import Permission, check_permission, request_permissions
        if not check_permission(Permission.POST_NOTIFICATIONS):
            request_permissions([Permission.POST_NOTIFICATIONS])
    except Exception:
        pass


def _start_service() -> None:
    global _running
    from jnius import autoclass

    Service = autoclass("unofficial.tgws.tgwsproxy.ServiceProxy")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Service.start(PythonActivity.mActivity, json.dumps({"secret": SECRET}))
    _running = True


def _stop_service() -> None:
    global _running
    from jnius import autoclass

    Service = autoclass("unofficial.tgws.tgwsproxy.ServiceProxy")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Service.stop(PythonActivity.mActivity)
    _running = False


# ── HTTP handler ─────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence request logs

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            try:
                html = UI_FILE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif self.path == "/api/status":
            self._send_json({
                "running": _running,
                "host": HOST_PROXY,
                "port": PORT_PROXY,
                "secret": SECRET if _running else None,
            })

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        if self.path == "/api/start":
            _request_permissions()
            _start_service()
            self._send_json({"ok": True, "running": _running, "secret": SECRET})

        elif self.path == "/api/stop":
            _stop_service()
            self._send_json({"ok": True, "running": _running})

        else:
            self.send_response(404)
            self.end_headers()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", SERVE_PORT), Handler)
    server.serve_forever()

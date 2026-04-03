"""
HTTP server entry point for the WebView bootstrap.
Serves the UI and provides a REST API to control the proxy service.
"""
import json
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST_PROXY = "127.0.0.1"
PORT_PROXY = 1443
SECRET = secrets.token_hex(16)
SERVE_PORT = int(os.environ.get("APP_SERVING_PORT", 8080))

UI_FILE = Path(__file__).parent / "ui" / "index.html"

_running = False
_desktop_loop = None


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
    try:
        from jnius import autoclass
        Service = autoclass("unofficial.tgws.tgwsproxy.ServiceProxy")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Service.start(PythonActivity.mActivity, json.dumps({"secret": SECRET}))
        _running = True
    except ImportError:
        _start_desktop()


def _stop_service() -> None:
    global _running
    try:
        from jnius import autoclass
        Service = autoclass("unofficial.tgws.tgwsproxy.ServiceProxy")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Service.stop(PythonActivity.mActivity)
    except ImportError:
        _stop_desktop()
    _running = False


def _start_desktop() -> None:
    """Run proxy in a background thread when jnius is unavailable (desktop testing)."""
    global _desktop_loop, _running
    import asyncio
    import sys

    sys.argv = ["tg-ws-proxy", "--host", HOST_PROXY, "--port", str(PORT_PROXY), "--secret", SECRET]

    def run() -> None:
        global _desktop_loop
        _desktop_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_desktop_loop)
        from proxy.tg_ws_proxy import main as proxy_main
        _desktop_loop.run_until_complete(proxy_main())

    threading.Thread(target=run, daemon=True).start()
    _running = True


def _stop_desktop() -> None:
    global _desktop_loop
    if _desktop_loop and _desktop_loop.is_running():
        _desktop_loop.call_soon_threadsafe(_desktop_loop.stop)


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

"""
HTTP server entry point for the WebView bootstrap.
Serves the UI and provides a REST API to control the proxy service.
"""
import json
import os
import secrets
import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional, Tuple

HOST_PROXY = "127.0.0.1"
PORT_PROXY = 1443
LOG_FILENAME = "tgws_proxy.log"
LOG_TAIL_LINES = 120


def _current_device_ip() -> str:
    """IP текущего сетевого интерфейса — то, что Telegram примет как адрес прокси."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return "127.0.0.1"
# Заполняется в _init_app_state(): должен совпадать с секретом в уже запущенном сервисе
# после перезапуска процесса WebView (иначе Telegram открывают с новым secret, прокси — со старым).
SECRET = ""
SERVE_PORT = int(os.environ.get("APP_SERVING_PORT", 8080))

UI_FILE = Path(__file__).parent / "ui" / "index.html"

_running = False


def _secret_storage_path() -> Path:
    try:
        from jnius import autoclass

        act = autoclass("org.kivy.android.PythonActivity").mActivity
        if act is not None:
            return Path(act.getFilesDir().getAbsolutePath()) / "tgws_proxy_secret.hex"
    except Exception:
        pass
    return Path(__file__).resolve().parent / ".tgws_proxy_secret.hex"


def _load_persisted_secret() -> Optional[str]:
    p = _secret_storage_path()
    try:
        raw = p.read_text(encoding="utf-8").strip().lower()
        if len(raw) == 32 and all(c in "0123456789abcdef" for c in raw):
            return raw
    except OSError:
        pass
    return None


def _save_secret(hex32: str) -> None:
    p = _secret_storage_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(hex32, encoding="utf-8")
    except OSError:
        pass


def _ensure_secret() -> str:
    s = _load_persisted_secret()
    if s:
        return s
    s = secrets.token_hex(16)
    _save_secret(s)
    return s


def _probe_proxy_port_open() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.35)
        s.connect((HOST_PROXY, PORT_PROXY))
        s.close()
        return True
    except OSError:
        return False


def _init_app_state() -> None:
    global SECRET, _running
    SECRET = _ensure_secret()
    if _probe_proxy_port_open():
        _running = True


def _webview_open_tg_and_https_externally() -> None:
    """tg://proxy?… is not a web page; p4a WebView must hand off to external apps."""
    try:
        from jnius import autoclass

        autoclass("org.kivy.android.PythonActivity").mOpenExternalLinksInBrowser = True
    except Exception:
        pass


# ── service control ──────────────────────────────────────────────────────────

def _request_permissions() -> None:
    try:
        from android.permissions import Permission, check_permission, request_permissions
        if not check_permission(Permission.POST_NOTIFICATIONS):
            request_permissions([Permission.POST_NOTIFICATIONS])
    except Exception:
        pass


def _wait_proxy_listen(timeout_s: float = 25.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            s.connect((HOST_PROXY, PORT_PROXY))
            s.close()
            return True
        except OSError:
            time.sleep(0.12)
    return False


def _toast(msg: str) -> None:
    """Toast только с UI-потока активности — иначе на Android часто не видно."""
    try:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        Toast = autoclass("android.widget.Toast")
        Py = autoclass("org.kivy.android.PythonActivity")

        @run_on_ui_thread
        def _go():
            Toast.makeText(Py.mActivity, msg, Toast.LENGTH_LONG).show()

        _go()
    except Exception:
        pass


def _notify_proxy_ready() -> None:
    """Отдельный канал с IMPORTANCE_HIGH; вызов с UI-потока."""
    try:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        @run_on_ui_thread
        def _go():
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            Context = autoclass("android.content.Context")
            Build = autoclass("android.os.Build")
            NotificationManager = autoclass("android.app.NotificationManager")
            NotificationChannel = autoclass("android.app.NotificationChannel")
            Intent = autoclass("android.content.Intent")
            PendingIntent = autoclass("android.app.PendingIntent")
            PyAct = autoclass("org.kivy.android.PythonActivity")

            nm = activity.getSystemService(Context.NOTIFICATION_SERVICE)
            channel_id = "tgws_proxy_user_alert"
            sdk = int(Build.VERSION.SDK_INT)

            if sdk >= 26:
                ch = NotificationChannel(
                    channel_id,
                    "TG WS Proxy · статус",
                    NotificationManager.IMPORTANCE_HIGH,
                )
                ch.setDescription("Сообщения о готовности прокси")
                nm.createNotificationChannel(ch)

            intent = Intent(activity, PyAct)
            intent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
            pi = PendingIntent.getActivity(
                activity,
                0,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE,
            )

            Builder = autoclass("android.app.Notification$Builder")
            b = Builder(activity, channel_id) if sdk >= 26 else Builder(activity)
            b.setSmallIcon(activity.getApplicationInfo().icon)
            b.setContentTitle("Прокси включён")
            b.setContentText("Можно открывать Telegram")
            b.setContentIntent(pi)
            b.setAutoCancel(True)
            nm.notify(88302, b.build())

        _go()
    except Exception:
        _toast("Прокси включён — можно открывать Telegram")


def _start_service() -> Tuple[bool, Optional[str]]:
    """Start foreground service; wait until TCP accepts (avoids Telegram 'connecting' to dead port)."""
    global _running
    from jnius import autoclass

    if _probe_proxy_port_open():
        _running = True
        return True, None

    if len(SECRET) != 32:
        return False, "Секрет не готов. Закрой приложение и открой снова."

    # Сервис читает этот же файл, если PYTHON_SERVICE_ARGUMENT не доехал (типичная проблема p4a).
    _save_secret(SECRET)

    Service = autoclass("unofficial.tgws.tgwsproxy.ServiceProxy")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    # 5-arg start: notification contentTitle/contentText (Android 8+), see p4a Service.tmpl.java
    Service.start(
        PythonActivity.mActivity,
        "",
        "TG WS Proxy",
        "Прокси 127.0.0.1:1443 · нажми, чтобы открыть приложение",
        json.dumps({"secret": SECRET}),
    )
    if not _wait_proxy_listen():
        try:
            Service.stop(PythonActivity.mActivity)
        except Exception:
            pass
        return False, "Прокси не поднялся за 25 с. Проверь разрешения и попробуй снова."
    # Короткая пауза: прокси теперь обрабатывает клиентов параллельно с warmup, но первому
    # коннекту иногда нужен крошечный буфер после accept.
    time.sleep(1.2)
    _running = True
    _notify_proxy_ready()
    return True, None


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
        global _running
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

        elif self.path == "/api/logs":
            try:
                log_path = Path(_secret_storage_path().parent / LOG_FILENAME)
                if log_path.exists():
                    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    tail = "\n".join(lines[-LOG_TAIL_LINES:])
                else:
                    tail = "(лог-файл ещё не создан — запустите прокси)"
            except Exception as e:
                tail = f"(ошибка чтения лога: {e})"
            self._send_json({"log": tail})

        elif self.path == "/api/status":
            alive = _running or _probe_proxy_port_open()
            if alive:
                _running = True
            self._send_json({
                "running": alive,
                "host": HOST_PROXY,
                "port": PORT_PROXY,
                "secret": SECRET if alive else None,
                "link_host": _current_device_ip() if alive else None,
            })

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        if self.path == "/api/start":
            _request_permissions()
            ok, err = _start_service()
            if ok:
                self._send_json({"ok": True, "running": _running, "secret": SECRET})
            else:
                self._send_json({"ok": False, "running": False, "error": err})

        elif self.path == "/api/stop":
            _stop_service()
            self._send_json({"ok": True, "running": _running, "secret": None})

        else:
            self.send_response(404)
            self.end_headers()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _webview_open_tg_and_https_externally()
    _init_app_state()
    server = HTTPServer(("127.0.0.1", SERVE_PORT), Handler)
    server.serve_forever()

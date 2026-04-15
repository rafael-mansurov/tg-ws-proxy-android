"""
HTTP server entry point for the WebView bootstrap.
Serves the UI and provides a REST API to control the proxy service.
"""
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional, Tuple

HOST_PROXY = "127.0.0.1"
PORT_PROXY = 1443
LOG_FILENAME = "tgws_proxy.log"
START_TS_FILENAME = "tgws_proxy_started_at.txt"
METRICS_FILENAME = "tgws_proxy_metrics.json"
LOG_TAIL_LINES = 120
LOG_MAX_AGE_SECONDS = 3600
READY_NOTIFICATION_ID = 88302
PREFS_NAME = "tgws_proxy_prefs"
PREF_AUTOSTART_ON_BOOT = "autostart_on_boot"
PREF_RESTART_INTERVAL_SECONDS = "restart_interval_seconds"
DEFAULT_RESTART_INTERVAL_SECONDS = 3600

try:
    from version import APP_VERSION
except ImportError:
    APP_VERSION = "1.0.0"


def _is_ignoring_battery_optimizations() -> bool:
    """True — приложение исключено из оптимизации (сервис не убивается)."""
    try:
        from jnius import autoclass
        Context = autoclass("android.content.Context")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        pm = activity.getSystemService(Context.POWER_SERVICE)
        return bool(pm.isIgnoringBatteryOptimizations(activity.getPackageName()))
    except Exception:
        return True  # на не-Android — считаем что всё ок


def _open_battery_optimization_settings() -> None:
    """Открывает системный диалог исключения из оптимизации батареи."""
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        pkg = activity.getPackageName()
        intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
        intent.setData(Uri.parse(f"package:{pkg}"))
        activity.startActivity(intent)
    except Exception:
        pass


_SHARE_TEXT = (
    "TG WS Proxy — бесплатный прокси для Telegram\n\n"
    "Скачать файл:\n"
    "https://github.com/rafael-mansurov/tg-ws-proxy-android/releases/"
    "download/latest-apk/tg-ws-proxy-release.apk"
)


def _cover_jpg_path() -> Path:
    return Path(__file__).resolve().parent / "cover.jpg"


def _share_app() -> bool:
    """Android Sharesheet: текст + ссылка (+ cover.jpg через FileProvider, если файл есть).

    Соответствует руководству «Send simple data to other apps» (ACTION_SEND + createChooser /
    эквивалент) и androidx ShareCompat.IntentBuilder — без устаревшего from(Activity), только
    конструктор IntentBuilder(Context) с API 1.5.0+.
    https://developer.android.com/training/sharing/send
    https://developer.android.com/reference/androidx/core/app/ShareCompat.IntentBuilder
    """
    log = logging.getLogger(__name__)
    done = threading.Event()
    outcome = {"ok": False}

    def _run_share_on_ui() -> None:
        try:
            from jnius import autoclass

            # androidx.core.app.ShareCompat.IntentBuilder — единый поддерживаемый способ:
            # выставляет ClipData, FLAG_GRANT_READ_URI_PERMISSION и вызывает системный chooser.
            IntentBuilder = autoclass("androidx.core.app.ShareCompat$IntentBuilder")
            JavaString = autoclass("java.lang.String")
            File = autoclass("java.io.File")
            FileProvider = autoclass("androidx.core.content.FileProvider")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            if activity is None:
                log.warning("_share_app: mActivity is None")
                return

            chooser_title = JavaString("Поделиться")
            subject = JavaString("TG WS Proxy")
            body = JavaString(_SHARE_TEXT)

            cover_path = str(_cover_jpg_path())
            authority = f"{activity.getPackageName()}.tgws.share"
            try:
                ib = IntentBuilder(activity)
            except Exception:
                # pyjnius иногда не находит IntentBuilder(Context); from(Activity) в Java — from_ в Python.
                log.debug("_share_app: IntentBuilder(activity) failed, using from_", exc_info=True)
                ib = IntentBuilder.from_(activity)

            if os.path.isfile(cover_path):
                # Документация: бинарный контент — ACTION_SEND, конкретный MIME (не */*).
                uri = FileProvider.getUriForFile(activity, authority, File(cover_path))
                ib.setType("image/jpeg")
                ib.setStream(uri)
                ib.setText(body)
                ib.setSubject(subject)
                ib.setChooserTitle(chooser_title)
                log.debug("_share_app: image/jpeg + text, uri=%s", uri)
            else:
                ib.setType("text/plain")
                ib.setText(body)
                ib.setSubject(subject)
                ib.setChooserTitle(chooser_title)
                log.debug("_share_app: text/plain only (нет cover.jpg)")

            ib.startChooser()
            outcome["ok"] = True
        except Exception as exc:
            log.warning("_share_app failed: %s", exc, exc_info=True)
        finally:
            done.set()

    try:
        from android.runnable import run_on_ui_thread

        @run_on_ui_thread
        def _post():
            _run_share_on_ui()

        _post()
    except ImportError:
        _run_share_on_ui()

    if not done.wait(timeout=20.0):
        log.warning("_share_app: UI thread timeout")
        return False
    return bool(outcome["ok"])


def _proxy_link_host() -> str:
    """Return the device IP Telegram can actually reach on this phone."""
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return HOST_PROXY
# Заполняется в _init_app_state(): должен совпадать с секретом в уже запущенном сервисе
# после перезапуска процесса WebView (иначе Telegram открывают с новым secret, прокси — со старым).
SECRET = ""
SERVE_PORT = int(os.environ.get("APP_SERVING_PORT", 8080))

UI_FILE = Path(__file__).parent / "ui" / "index.html"
PROXY_FILTER_LAB_FILE = Path(__file__).parent / "ui" / "proxy-filter-lab.html"
ROUNDED_QR_FILE = Path(__file__).parent / "ui" / "rounded-qr.js"

_running = False
_ready_notification_shown = False


def _icon_png_path() -> Optional[Path]:
    root = Path(__file__).parent
    for p in (root / "icon.png", root / "ui" / "icon.png"):
        if p.is_file():
            return p
    return None
_app_ready = False   # True after _init_app_state() completes


def _secret_storage_path() -> Path:
    try:
        from jnius import autoclass

        act = autoclass("org.kivy.android.PythonActivity").mActivity
        if act is not None:
            return Path(act.getFilesDir().getAbsolutePath()) / "tgws_proxy_secret.hex"
    except Exception:
        pass
    return Path(__file__).resolve().parent / ".tgws_proxy_secret.hex"


def _service_start_ts_path() -> Path:
    return _secret_storage_path().parent / START_TS_FILENAME


def _read_service_start_ts() -> Optional[int]:
    p = _service_start_ts_path()
    try:
        raw = p.read_text(encoding="utf-8").strip()
        ts = int(raw)
        if ts > 0:
            return ts
    except (OSError, ValueError):
        pass
    return None


def _write_service_start_ts_now() -> None:
    p = _service_start_ts_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def _clear_service_start_ts() -> None:
    p = _service_start_ts_path()
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


def _proxy_uptime_seconds() -> Optional[int]:
    ts = _read_service_start_ts()
    if not ts:
        return None
    delta = int(time.time()) - ts
    return delta if delta >= 0 else 0


def _read_live_metrics() -> dict:
    p = _secret_storage_path().parent / METRICS_FILENAME
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        rx = float(raw.get("rx_bps", 0.0))
        tx = float(raw.get("tx_bps", 0.0))
        last_ok = float(raw.get("last_session_ok_ts", 0.0))
        return {
            "rx_bps": max(0.0, rx),
            "tx_bps": max(0.0, tx),
            "last_session_ok_ts": max(0.0, last_ok),
        }
    except Exception:
        return {"rx_bps": 0.0, "tx_bps": 0.0, "last_session_ok_ts": 0.0}


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
    global SECRET, _running, _app_ready
    SECRET = _ensure_secret()
    if _probe_proxy_port_open():
        _running = True
    _app_ready = True


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


def _get_autostart_enabled() -> bool:
    try:
        from jnius import autoclass

        Context = autoclass("android.content.Context")
        PyAct = autoclass("org.kivy.android.PythonActivity")
        activity = PyAct.mActivity
        if activity is None:
            return False
        prefs = activity.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return bool(prefs.getBoolean(PREF_AUTOSTART_ON_BOOT, False))
    except Exception:
        return False


def _set_autostart_enabled(enabled: bool) -> bool:
    try:
        from jnius import autoclass

        Context = autoclass("android.content.Context")
        PyAct = autoclass("org.kivy.android.PythonActivity")
        activity = PyAct.mActivity
        if activity is None:
            return False
        prefs = activity.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        editor = prefs.edit()
        editor.putBoolean(PREF_AUTOSTART_ON_BOOT, bool(enabled))
        return bool(editor.commit())
    except Exception:
        return False


def _get_restart_interval_seconds() -> int:
    try:
        from jnius import autoclass

        Context = autoclass("android.content.Context")
        PyAct = autoclass("org.kivy.android.PythonActivity")
        activity = PyAct.mActivity
        if activity is None:
            return DEFAULT_RESTART_INTERVAL_SECONDS
        prefs = activity.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val = int(prefs.getInt(PREF_RESTART_INTERVAL_SECONDS, DEFAULT_RESTART_INTERVAL_SECONDS))
        return max(0, val)
    except Exception:
        return DEFAULT_RESTART_INTERVAL_SECONDS


def _set_restart_interval_seconds(seconds: int) -> bool:
    sec = max(0, int(seconds))
    try:
        from jnius import autoclass

        Context = autoclass("android.content.Context")
        PyAct = autoclass("org.kivy.android.PythonActivity")
        activity = PyAct.mActivity
        if activity is None:
            return False
        prefs = activity.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        editor = prefs.edit()
        editor.putInt(PREF_RESTART_INTERVAL_SECONDS, sec)
        return bool(editor.commit())
    except Exception:
        return False


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    try:
        n = int(handler.headers.get("Content-Length", "0") or "0")
    except ValueError:
        n = 0
    if n <= 0:
        return {}
    raw = handler.rfile.read(n)
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _wait_proxy_stopped(timeout_s: float = 6.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _probe_proxy_port_open():
            return True
        time.sleep(0.1)
    return False


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


_LOG_TS_RE = re.compile(r"^(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\b")


def _filter_recent_log_lines(lines: list[str], max_age_seconds: int = LOG_MAX_AGE_SECONDS) -> list[str]:
    if not lines:
        return []
    now = time.time()
    now_local = time.localtime(now)
    recent: list[str] = []
    for line in lines:
        m = _LOG_TS_RE.match(line)
        if not m:
            continue
        hh = int(m.group("h"))
        mm = int(m.group("m"))
        ss = int(m.group("s"))
        line_ts = time.mktime((
            now_local.tm_year, now_local.tm_mon, now_local.tm_mday,
            hh, mm, ss, now_local.tm_wday, now_local.tm_yday, now_local.tm_isdst
        ))
        if line_ts - now > 60:
            line_ts -= 86400
        if now - line_ts <= max_age_seconds:
            recent.append(line)
    return recent


def _proxy_log_path() -> Path:
    return _secret_storage_path().parent / LOG_FILENAME


def _write_start_log(message: str, reset: bool = False) -> None:
    p = _proxy_log_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if reset else "a"
        with p.open(mode, encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S"))
            f.write("  INFO   ")
            f.write(message)
            f.write("\n")
    except OSError:
        pass


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
    global _ready_notification_shown
    _ready_notification_shown = True
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
            b.setAutoCancel(False)
            b.setOngoing(True)
            b.setOnlyAlertOnce(True)
            nm.notify(READY_NOTIFICATION_ID, b.build())
            _ready_notification_shown = True

        _go()
    except Exception:
        _toast("Прокси включён — можно открывать Telegram")


def _clear_proxy_ready_notification() -> None:
    """Снять закреплённое уведомление готовности при остановке прокси."""
    global _ready_notification_shown
    try:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        @run_on_ui_thread
        def _go():
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            Context = autoclass("android.content.Context")
            nm = activity.getSystemService(Context.NOTIFICATION_SERVICE)
            nm.cancel(READY_NOTIFICATION_ID)
            _ready_notification_shown = False

        _go()
    except Exception:
        pass


def _start_service() -> Tuple[bool, Optional[str]]:
    """Start foreground service from a clean state."""
    global _running
    from jnius import autoclass

    if len(SECRET) != 32:
        return False, "Секрет не готов. Закройте приложение и откройте снова."

    link_host = _proxy_link_host()

    # Сервис читает этот же файл, если PYTHON_SERVICE_ARGUMENT не доехал (типичная проблема p4a).
    _save_secret(SECRET)
    _write_start_log("UI: start requested", reset=True)

    ProxyControl = autoclass("unofficial.tgws.tgwsproxy.ProxyControl")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    activity = PythonActivity.mActivity
    try:
        ProxyControl.stopProxy(activity)
        _write_start_log("UI: stop previous proxy")
    except Exception:
        pass
    if not _wait_proxy_stopped():
        if _probe_proxy_port_open():
            _running = True
            _write_start_log(f"UI: proxy already listening for Telegram on {link_host}:{PORT_PROXY}")
            return True, None
        _write_start_log("UI: previous proxy did not stop cleanly")
        return False, "Не удалось остановить прошлый инстанс прокси. Попробуйте ещё раз."

    started = False
    try:
        started = bool(ProxyControl.startProxy(activity))
    except Exception:
        started = False
    if not started and not _probe_proxy_port_open():
        _write_start_log("UI: ProxyControl.startProxy returned false")
        return False, "Не удалось отправить команду запуска сервиса."
    if not _wait_proxy_listen():
        if _probe_proxy_port_open():
            _running = True
            _notify_proxy_ready()
            _write_start_log("UI: proxy port opened after delayed start")
            return True, None
        try:
            ProxyControl.stopProxy(activity)
        except Exception:
            pass
        _write_start_log(f"UI: proxy failed to listen for Telegram on {link_host}:{PORT_PROXY}")
        return False, "Прокси не поднялся за 25 с. Проверьте разрешения и попробуйте снова."
    if _read_service_start_ts() is None:
        _write_service_start_ts_now()
    # Короткая пауза: прокси теперь обрабатывает клиентов параллельно с warmup, но первому
    # коннекту иногда нужен крошечный буфер после accept.
    time.sleep(1.2)
    _running = True
    _notify_proxy_ready()
    _write_start_log(f"UI: proxy is ready for Telegram on {link_host}:{PORT_PROXY}")
    return True, None


def _stop_service() -> None:
    global _running
    from jnius import autoclass

    ProxyControl = autoclass("unofficial.tgws.tgwsproxy.ProxyControl")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    ProxyControl.stopProxy(PythonActivity.mActivity)
    _running = False
    _clear_service_start_ts()
    _clear_proxy_ready_notification()


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

        elif self.path == "/proxy-filter-lab.html":
            try:
                html = PROXY_FILTER_LAB_FILE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif self.path == "/icon.png":
            icon_path = _icon_png_path()
            if icon_path is None:
                self.send_response(404)
                self.end_headers()
                return
            try:
                data = icon_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except OSError:
                self.send_response(404)
                self.end_headers()

        elif self.path == "/cover.jpg":
            cover = _cover_jpg_path()
            if not cover.is_file():
                self.send_response(404)
                self.end_headers()
                return
            try:
                data = cover.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except OSError:
                self.send_response(404)
                self.end_headers()

        elif self.path == "/rounded-qr.js":
            if not ROUNDED_QR_FILE.is_file():
                self.send_response(404)
                self.end_headers()
                return
            try:
                data = ROUNDED_QR_FILE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except OSError:
                self.send_response(404)
                self.end_headers()

        elif self.path == "/api/version":
            self._send_json({"version": APP_VERSION, "serve_port": SERVE_PORT})

        elif self.path == "/api/battery":
            self._send_json({"optimized": not _is_ignoring_battery_optimizations()})

        elif self.path == "/api/autostart":
            self._send_json({"enabled": _get_autostart_enabled()})

        elif self.path == "/api/restart-interval":
            self._send_json({"seconds": _get_restart_interval_seconds()})

        elif self.path == "/api/logs":
            try:
                log_path = Path(_secret_storage_path().parent / LOG_FILENAME)
                if log_path.exists():
                    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                    recent = _filter_recent_log_lines(lines)
                    if recent:
                        tail = "\n".join(recent[-LOG_TAIL_LINES:])
                    else:
                        tail = "(за последний час логов нет)"
                else:
                    tail = "(лог-файл ещё не создан — запустите прокси)"
            except Exception as e:
                tail = f"(ошибка чтения лога: {e})"
            self._send_json({"log": tail})

        elif self.path == "/api/status":
            if not _app_ready:
                self._send_json({"booting": True, "running": False})
                return
            alive = _probe_proxy_port_open()
            _running = alive
            if alive:
                if not _ready_notification_shown:
                    _notify_proxy_ready()
            else:
                if _ready_notification_shown:
                    _clear_proxy_ready_notification()
            self._send_json({
                "running": alive,
                "host": HOST_PROXY,
                "port": PORT_PROXY,
                "secret": SECRET if alive else None,
                "link_host": _proxy_link_host() if alive else None,
                "uptime_seconds": _proxy_uptime_seconds() if alive else None,
                **(_read_live_metrics() if alive else {"rx_bps": 0.0, "tx_bps": 0.0, "last_session_ok_ts": 0.0}),
            })

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        if self.path == "/api/start":
            _request_permissions()
            ok, err = _start_service()
            if ok:
                self._send_json({
                    "ok": True,
                    "running": _running,
                    "secret": SECRET,
                    "link_host": _proxy_link_host(),
                    "uptime_seconds": _proxy_uptime_seconds(),
                    **_read_live_metrics(),
                })
            else:
                self._send_json({"ok": False, "running": False, "error": err})

        elif self.path == "/api/battery":
            _open_battery_optimization_settings()
            self._send_json({"ok": True})

        elif self.path == "/api/autostart":
            body = _read_json_body(self)
            enabled = bool(body.get("enabled", False))
            ok = _set_autostart_enabled(enabled)
            self._send_json({"ok": ok, "enabled": enabled if ok else _get_autostart_enabled()})

        elif self.path == "/api/restart-interval":
            body = _read_json_body(self)
            try:
                requested = int(body.get("seconds", DEFAULT_RESTART_INTERVAL_SECONDS))
            except (TypeError, ValueError):
                requested = DEFAULT_RESTART_INTERVAL_SECONDS
            ok = _set_restart_interval_seconds(requested)
            self._send_json({
                "ok": ok,
                "seconds": requested if ok else _get_restart_interval_seconds(),
            })

        elif self.path == "/api/stop":
            _stop_service()
            self._send_json({"ok": True, "running": _running, "secret": None})

        elif self.path == "/api/share":
            ok = _share_app()
            self._send_json({"ok": ok})

        else:
            self.send_response(404)
            self.end_headers()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _webview_open_tg_and_https_externally()
    _request_permissions()  # early request so permission is granted before proxy starts
    # Init in background so WebView gets HTML as soon as the server is up (splash hides on first paint of this URL).
    threading.Thread(target=_init_app_state, daemon=True).start()
    server = HTTPServer(("127.0.0.1", SERVE_PORT), Handler)
    server.serve_forever()

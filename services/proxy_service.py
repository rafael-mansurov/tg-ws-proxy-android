"""
Foreground-service entry: MTProto proxy on 0.0.0.0:1443 for Telegram on the same device.
"""
from __future__ import annotations

import json
import os
import sys
import time
import threading
import asyncio
from pathlib import Path
from typing import Optional

from proxy.dc_resolve import resolve_kws_edge_ipv4

_started = False

SECRET_FILENAME = "tgws_proxy_secret.hex"


def _secret_from_service_argument() -> Optional[str]:
    """Аргумент, который p4a передаёт через PYTHON_SERVICE_ARGUMENT (бывает пустым)."""
    arg = os.environ.get("PYTHON_SERVICE_ARGUMENT", "").strip()
    if not arg:
        return None
    try:
        s = json.loads(arg).get("secret")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None
    if not isinstance(s, str):
        return None
    s = s.strip().lower()
    if len(s) == 32 and all(c in "0123456789abcdef" for c in s):
        return s
    return None


def _secret_from_app_file() -> Optional[str]:
    """Тот же файл, что пишет main.py — надёжная связка UI ↔ сервис, если env пустой."""
    try:
        from android.storage import app_storage_path

        base = Path(app_storage_path())
    except Exception:
        try:
            from jnius import autoclass

            PySvc = autoclass("org.kivy.android.PythonService")
            svc = PySvc.mService
            if svc is None:
                return None
            base = Path(svc.getFilesDir().getAbsolutePath())
        except Exception:
            return None
    try:
        raw = (base / SECRET_FILENAME).read_text(encoding="utf-8").strip().lower()
        if len(raw) == 32 and all(c in "0123456789abcdef" for c in raw):
            return raw
    except OSError:
        pass
    return None


LOG_FILENAME = "tgws_proxy.log"
START_TS_FILENAME = "tgws_proxy_started_at.txt"
METRICS_FILENAME = "tgws_proxy_metrics.json"
PREFS_NAME = "tgws_proxy_prefs"
PREF_RESTART_INTERVAL_SECONDS = "restart_interval_seconds"
DEFAULT_RESTART_INTERVAL_SECONDS = 3600
IDLE_SHUTDOWN_SECONDS = 15 * 60


def _app_base_path() -> Optional[Path]:
    try:
        from android.storage import app_storage_path
        return Path(app_storage_path())
    except Exception:
        pass
    try:
        from jnius import autoclass
        PySvc = autoclass("org.kivy.android.PythonService")
        svc = PySvc.mService
        if svc is not None:
            return Path(svc.getFilesDir().getAbsolutePath())
    except Exception:
        pass
    return None


def _resolve_secret() -> Optional[str]:
    return _secret_from_service_argument() or _secret_from_app_file()


def _read_restart_interval_seconds(default: int = DEFAULT_RESTART_INTERVAL_SECONDS) -> int:
    try:
        from jnius import autoclass

        Context = autoclass("android.content.Context")
        PySvc = autoclass("org.kivy.android.PythonService")
        svc = PySvc.mService
        if svc is None:
            return default
        prefs = svc.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        raw = int(prefs.getInt(PREF_RESTART_INTERVAL_SECONDS, int(default)))
        return raw if raw >= 0 else default
    except Exception:
        return default


def _mark_service_start(base: Optional[Path]) -> None:
    if not base:
        return
    try:
        (base / START_TS_FILENAME).write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


def _write_metrics(base: Optional[Path], rx_bps: float, tx_bps: float, last_ok_ts: float = 0.0) -> None:
    if not base:
        return
    payload = {
        "ts": int(time.time()),
        "rx_bps": max(0.0, float(rx_bps)),
        "tx_bps": max(0.0, float(tx_bps)),
        "last_session_ok_ts": float(last_ok_ts),
    }
    try:
        (base / METRICS_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def _start_metrics_monitor(base: Optional[Path], tg_mod) -> None:
    if not base or tg_mod is None:
        return

    def _loop() -> None:
        last_t = time.monotonic()
        last_up = float(getattr(getattr(tg_mod, "_stats", None), "bytes_up", 0) or 0)
        last_down = float(getattr(getattr(tg_mod, "_stats", None), "bytes_down", 0) or 0)
        _write_metrics(base, 0.0, 0.0, 0.0)
        while True:
            time.sleep(1.0)
            now = time.monotonic()
            dt = max(0.2, now - last_t)
            stats = getattr(tg_mod, "_stats", None)
            up = float(getattr(stats, "bytes_up", last_up) or last_up)
            down = float(getattr(stats, "bytes_down", last_down) or last_down)
            tx_bps = (up - last_up) / dt
            rx_bps = (down - last_down) / dt
            last_t = now
            last_up = up
            last_down = down
            last_ok_ts = float(getattr(stats, "last_session_ok_ts", 0.0) or 0.0)
            _write_metrics(base, rx_bps, tx_bps, last_ok_ts)

    t = threading.Thread(target=_loop, name="tgws-metrics", daemon=True)
    t.start()


def _start_idle_shutdown_watcher(
    stop_event: asyncio.Event,
    stop_reason: dict,
    finish_event: threading.Event,
    tg_mod,
    idle_seconds: int = IDLE_SHUTDOWN_SECONDS,
) -> threading.Thread:
    def _loop() -> None:
        stats = getattr(tg_mod, "_stats", None)
        last_up = float(getattr(stats, "bytes_up", 0) or 0)
        last_down = float(getattr(stats, "bytes_down", 0) or 0)
        last_activity = time.monotonic()
        while not finish_event.is_set():
            time.sleep(1.0)
            stats = getattr(tg_mod, "_stats", None)
            up = float(getattr(stats, "bytes_up", last_up) or last_up)
            down = float(getattr(stats, "bytes_down", last_down) or last_down)
            if up != last_up or down != last_down:
                last_activity = time.monotonic()
            last_up = up
            last_down = down
            if (time.monotonic() - last_activity) >= idle_seconds:
                stop_reason["reason"] = "idle"
                stop_event.set()
                return

    t = threading.Thread(target=_loop, name="tgws-idle-stop", daemon=True)
    t.start()
    return t


def _svc_log(base, msg: str) -> None:
    try:
        if base:
            with open(str(base / LOG_FILENAME), "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%H:%M:%S')}  SVC    {msg}\n")
    except Exception:
        pass
    sys.stderr.write(f"tgws-svc: {msg}\n")
    sys.stderr.flush()


def _run_proxy() -> None:
    global _started
    if _started:
        return
    _started = True

    base = _app_base_path()
    _svc_log(base, "service process started")

    secret = _resolve_secret()
    if not secret:
        _svc_log(base, "ERROR: no secret — check pythonServiceArgument extra and app storage")
        sys.exit(1)

    _svc_log(base, f"secret resolved (len={len(secret)})")

    log_file = None
    if base:
        log_file = str(base / LOG_FILENAME)
    _mark_service_start(base)

    argv = [
        "tg-ws-proxy",
        "--host",
        "0.0.0.0",
        "--port",
        "1443",
        "--secret",
        secret,
        "--verbose",
    ]
    if log_file:
        argv.extend(["--log-file", log_file])

    try:
        for dc in (2, 4):
            ip = resolve_kws_edge_ipv4(dc)
            argv.extend(["--dc-ip", f"{dc}:{ip}"])
            _svc_log(base, f"dc{dc} ip={ip}")
    except Exception as _e:
        _svc_log(base, f"ERROR in dc_resolve: {_e!r}")

    sys.argv = argv

    try:
        import proxy.tg_ws_proxy as tg_mod
        _svc_log(base, "proxy module imported OK")
    except Exception as _e:
        _svc_log(base, f"ERROR importing proxy.tg_ws_proxy: {_e!r}")
        raise

    _start_metrics_monitor(base, tg_mod)
    run_proxy = tg_mod.run_proxy
    _svc_log(base, "starting run_proxy loop")

    while True:
        _mark_service_start(base)
        restart_every = _read_restart_interval_seconds()
        if restart_every <= 0:
            run_proxy()
            # если отключили автоперезапуск — не зацикливаемся при штатной работе
            return

        stop_event = asyncio.Event()
        finish_event = threading.Event()
        stop_reason = {"reason": "timer"}
        timer = threading.Timer(float(restart_every), stop_event.set)
        timer.daemon = True
        timer.start()
        idle_watcher = _start_idle_shutdown_watcher(
            stop_event=stop_event,
            stop_reason=stop_reason,
            finish_event=finish_event,
            tg_mod=tg_mod,
            idle_seconds=IDLE_SHUTDOWN_SECONDS,
        )
        try:
            run_proxy(stop_event)
        finally:
            finish_event.set()
            timer.cancel()
            idle_watcher.join(timeout=0.2)

        # если остановились не по таймеру (ошибка/внешняя остановка), небольшой backoff
        if not stop_event.is_set():
            time.sleep(1.0)
            continue

        if stop_reason.get("reason") == "idle":
            return
        # циклический мягкий рестарт по таймеру


_run_proxy()

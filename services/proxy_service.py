"""
Foreground-service entry: MTProto proxy on 0.0.0.0:1443 for Telegram on the same device.
"""
from __future__ import annotations

import json
import os
import sys
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


def _run_proxy() -> None:
    global _started
    if _started:
        return
    _started = True

    secret = _resolve_secret()
    if not secret:
        sys.stderr.write(
            "tgws-proxy: нет секрета (env и "
            f"{SECRET_FILENAME} в app storage). Сервис не стартует.\n"
        )
        sys.stderr.flush()
        sys.exit(1)

    log_file = None
    base = _app_base_path()
    if base:
        log_file = str(base / LOG_FILENAME)

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

    for dc in (2, 4):
        ip = resolve_kws_edge_ipv4(dc)
        argv.extend(["--dc-ip", f"{dc}:{ip}"])

    sys.argv = argv

    from proxy.tg_ws_proxy import main as proxy_main

    proxy_main()


_run_proxy()

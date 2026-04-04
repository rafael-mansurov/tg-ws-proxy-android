"""
Foreground-service entry: MTProto proxy bound to 127.0.0.1 for Telegram on the same device.
"""
from __future__ import annotations

import json
import os
import sys

from proxy.dc_resolve import resolve_kws_edge_ipv4

_started = False


def _run_proxy() -> None:
    global _started
    if _started:
        return
    _started = True

    arg = os.environ.get("PYTHON_SERVICE_ARGUMENT", "")
    secret = None
    if arg:
        try:
            secret = json.loads(arg).get("secret")
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    # 0.0.0.0: на части прошивок надёжнее для входящих от других приложений (Telegram);
    # в tg:// по-прежнему 127.0.0.1 — это тот же слушатель.
    argv = ["tg-ws-proxy", "--host", "0.0.0.0", "--port", "1443"]
    if secret:
        argv.extend(["--secret", secret])

    for dc in (2, 4):
        ip = resolve_kws_edge_ipv4(dc)
        argv.extend(["--dc-ip", f"{dc}:{ip}"])

    sys.argv = argv

    from proxy.tg_ws_proxy import main as proxy_main

    proxy_main()


_run_proxy()

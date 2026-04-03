#!/usr/bin/env python3
"""Локальный запуск прокси на ПК (логика dc-ip как в services/proxy_service.py)."""
from __future__ import annotations

import argparse
import errno
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _prepend_argv(proxy_args: list[str]) -> None:
    sys.argv = ["tg-ws-proxy", *proxy_args]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MTProto→WS bridge на 127.0.0.1 (без APK). "
        "Любые неизвестные флаги передаются в tg_ws_proxy (например -v).",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="listen host (default 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=1443, help="listen port (default 1443)",
    )
    parser.add_argument(
        "--secret",
        default=None,
        help="32 hex chars; если нет — сгенерируется и покажется в логе",
    )
    parser.add_argument(
        "--no-dns-dc-ip",
        action="store_true",
        help="не резолвить kws* — как дефолт Flowseal (один захардкоженный IP на DC)",
    )
    args, forward = parser.parse_known_args()

    proxy_argv: list[str] = ["--host", args.host, "--port", str(args.port)]
    if args.secret:
        proxy_argv.extend(["--secret", args.secret])

    if args.no_dns_dc_ip:
        pass
    else:
        from proxy.dc_resolve import resolve_kws_edge_ipv4

        for dc in (2, 4):
            ip = resolve_kws_edge_ipv4(dc)
            proxy_argv.extend(["--dc-ip", f"{dc}:{ip}"])

    proxy_argv.extend(forward)

    _prepend_argv(proxy_argv)
    os.chdir(ROOT)

    from proxy.tg_ws_proxy import main as proxy_main

    try:
        proxy_main()
    except OSError as e:
        if e.errno != errno.EADDRINUSE:
            raise
        p = args.port
        print(
            f"\nПорт {p} уже занят (EADDRINUSE).\n"
            f"  Кто слушает:    lsof -nP -iTCP:{p} -sTCP:LISTEN\n"
            f"  Свободный порт: python3 scripts/run_local_proxy.py -v --port 11443\n",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

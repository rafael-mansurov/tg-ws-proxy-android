#!/usr/bin/env python3
"""SwiftBar: положить в ~/SwiftBarPlugins/tgwsproxy.1s.py, chmod +x. См. landing/swiftbar-mac.html."""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path.home() / "Documents/proxy/tg-ws-proxy-apk"
PORT = 1443
FIXED_SECRET: str = ""  # опционально: openssl rand -hex 16; иначе секрет в .swiftbar-proxy.log
LOG = REPO / ".swiftbar-proxy.log"
CLIP_TMP = Path("/tmp/tgwsproxy_clip.url")


def _repo_ok() -> bool:
    return (REPO / "scripts" / "run_local_proxy.py").is_file()


def _connects_local() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.25)
        s.connect(("127.0.0.1", PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _listen_pids() -> list[str]:
    r = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{PORT}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0 or not (r.stdout or "").strip():
        return []
    return [x for x in r.stdout.strip().split() if x]


def _secret_from_log() -> str | None:
    if not LOG.is_file():
        return None
    try:
        tail = LOG.read_text(errors="ignore")[-12000:]
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        if "Secret:" in line:
            m = re.search(r"Secret:\s+([0-9a-fA-F]{32})", line)
            if m:
                return m.group(1).lower()
    m2 = re.search(r"Generated secret:\s+([0-9a-fA-F]{32})", tail)
    if m2:
        return m2.group(1).lower()
    return None


def _uptime_hint() -> str:
    pids = _listen_pids()
    if not pids:
        return ""
    r = subprocess.run(
        ["ps", "-p", pids[0], "-o", "etime="],
        capture_output=True,
        text=True,
    )
    et = (r.stdout or "").strip()
    return f" {et}" if et and r.returncode == 0 else ""


def _lan_ip() -> str | None:
    sys.path.insert(0, str(REPO))
    try:
        from proxy.lan_ipv4 import lan_ipv4_preferred

        return lan_ipv4_preferred()
    except Exception:
        return None


def _qr_b64(url: str) -> str | None:
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        from proxy.swiftbar_qr import qr_url_to_png_base64

        return qr_url_to_png_base64(url, scale=4, border_modules=3)
    except Exception:
        return None


def _start() -> None:
    if not _repo_ok():
        print("Нет run_local_proxy.py — проверьте REPO в плагине", file=sys.stderr)
        return
    if _listen_pids():
        return
    LOG.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(REPO / "scripts" / "run_local_proxy.py"),
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT),
    ]
    if FIXED_SECRET.strip():
        cmd.extend(["--secret", FIXED_SECRET.strip()])
    with open(LOG, "a", encoding="utf-8") as lf:
        lf.write(f"\n--- swiftbar start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        lf.flush()
        subprocess.Popen(
            cmd,
            cwd=str(REPO),
            stdout=lf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )


def _stop() -> None:
    for pid in _listen_pids():
        try:
            os.kill(int(pid), 15)
        except (ProcessLookupError, ValueError):
            pass


def _clipboard_from_tmp() -> None:
    try:
        t = CLIP_TMP.read_text(encoding="utf-8")
    except OSError:
        return
    subprocess.run(["pbcopy"], input=t.encode("utf-8"), check=False)


def _emit_menu() -> None:
    me = Path(__file__).resolve()
    py = sys.executable
    on = _connects_local() and _repo_ok()
    secret = (FIXED_SECRET.strip().lower() if FIXED_SECRET.strip() else None) or _secret_from_log()
    up = _uptime_hint() if on else ""
    lan = _lan_ip() if on else None

    if not _repo_ok():
        title = "TG proxy ⚠ | color=#c2410c"
    elif on:
        title = f"TG proxy ●{up} | color=#047857"
    else:
        title = "TG proxy ○ | color=#71717a"

    print(title)
    print("---")

    if _repo_ok():
        print(f"Включить | bash={py} param1={me} param2=start terminal=false refresh=true")
        print(f"Выключить | bash={py} param1={me} param2=stop terminal=false refresh=true")
    else:
        print("Включить недоступно — нет репозитория | disabled=true")

    print("---")
    if secret:
        print(
            f"Telegram (Mac, 127.0.0.1) | href=tg://proxy?server=127.0.0.1&port={PORT}&secret=dd{secret}"
        )
        if lan:
            phone_url = f"tg://proxy?server={lan}&port={PORT}&secret=dd{secret}"
            try:
                CLIP_TMP.write_text(phone_url, encoding="utf-8")
            except OSError:
                pass
            print(f"Telegram (телефон, LAN) | href={phone_url}")
            b64 = _qr_b64(phone_url)
            if b64:
                print(f"QR для телефона | image={b64}")
            print(
                f"Копировать ссылку для телефона | bash={py} param1={me} "
                f"param2=clipboard terminal=false"
            )
    else:
        print("Ссылки tg:// появятся после первого запуска (секрет в логе) | disabled=true")

    print("---")
    print(f"Лог прокси | bash=/usr/bin/open param1={LOG} terminal=false")
    print(f"Папка проекта | bash=/usr/bin/open param1={REPO} terminal=false")


def main() -> None:
    if len(sys.argv) > 1:
        act = sys.argv[1]
        if act == "start":
            _start()
        elif act == "stop":
            _stop()
        elif act == "clipboard":
            _clipboard_from_tmp()
        return
    _emit_menu()


if __name__ == "__main__":
    main()

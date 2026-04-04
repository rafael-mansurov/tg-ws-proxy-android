#!/usr/bin/env python3
"""Windows: иконка в системном трее для TG WS Proxy.

Обычный запуск из клона репозитория:
  pip install -r contrib/requirements-tray-windows.txt
  pythonw.exe contrib/tgwsproxy_tray_windows.py

Сборка one-file (всё в одном .exe, без Python и клона): см. contrib/tgwsproxy_tray_windows.spec
Состояние: %LOCALAPPDATA%\\TGWSProxy\\
"""
from __future__ import annotations

import os
import re
import runpy
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

_WORKER_FLAG = "--tgws-proxy-worker"


def _repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


REPO = _repo_root()
RUN_SCRIPT = REPO / "scripts" / "run_local_proxy.py"


def _run_embedded_proxy_worker() -> None:
    """Тот же .exe в режиме прокси (PyInstaller one-file)."""
    root = _repo_root()
    sys.path.insert(0, str(root))
    try:
        os.chdir(str(root))
    except OSError:
        pass
    args = list(sys.argv)
    try:
        i = args.index(_WORKER_FLAG)
    except ValueError:
        return
    sys.argv = ["run_local_proxy", *args[i + 1 :]]
    runpy.run_path(str(root / "scripts" / "run_local_proxy.py"), run_name="__main__")


PORT = 1443

_default_local = os.environ.get("LOCALAPPDATA")
STATE_DIR = (
    Path(_default_local) / "TGWSProxy" if _default_local else Path.home() / "TGWSProxy"
)
PID_FILE = STATE_DIR / "proxy.pid"
LISTENER_SINCE_FILE = STATE_DIR / "listener_since"
SECRET_FILE = STATE_DIR / "secret.txt"
STARTING_FILE = STATE_DIR / "starting"
RESTARTING_FILE = STATE_DIR / "restarting"
HOME_PROXY_FILE = STATE_DIR / "home_proxy"

STREAM_TICK_SEC = 1.0
STARTING_TIMEOUT_SEC = 30.0

_NETSTAT_LINE = re.compile(
    r"^\s*TCP\s+(\S+)\s+\S+\s+LISTENING\s+(\d+)\s*$", re.IGNORECASE
)


def ensure() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def home_proxy_enabled() -> bool:
    try:
        return HOME_PROXY_FILE.read_text(encoding="utf-8").strip() == "1"
    except OSError:
        return False


def _lan_ipv4_legacy() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return None


def lan_ipv4() -> str | None:
    if not REPO.is_dir():
        return _lan_ipv4_legacy()
    rp = str(REPO)
    try:
        if rp not in sys.path:
            sys.path.insert(0, rp)
        from proxy.lan_ipv4 import lan_ipv4_preferred

        ip = lan_ipv4_preferred()
        if ip:
            return ip
    except Exception:
        pass
    return _lan_ipv4_legacy()


def listen_pids_port() -> list[int]:
    try:
        r = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    pids: list[int] = []
    for line in (r.stdout or "").splitlines():
        m = _NETSTAT_LINE.match(line)
        if not m:
            continue
        local, pid_s = m.group(1), m.group(2)
        if local.endswith(f":{PORT}") or local.endswith(f"]:{PORT}"):
            try:
                pids.append(int(pid_s))
            except ValueError:
                pass
    return pids


def is_running() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.25)
            s.connect(("127.0.0.1", PORT))
        return True
    except OSError:
        return False


def find_pid() -> int | None:
    pids = listen_pids_port()
    if not pids:
        return None
    uniq = frozenset(pids)
    try:
        st = PID_FILE.read_text(encoding="utf-8").strip()
        if st.isdigit():
            v = int(st)
            if v in uniq:
                return v
    except OSError:
        pass
    return min(uniq)


def load_secret() -> str | None:
    if SECRET_FILE.is_file():
        s = SECRET_FILE.read_text(encoding="utf-8").strip()
        if len(s) == 32:
            return s
    return None


def get_or_gen_secret() -> str:
    s = load_secret()
    if s:
        return s
    s = secrets.token_hex(16)
    ensure()
    SECRET_FILE.write_text(s, encoding="utf-8")
    return s


def _clear_listener_anchor() -> None:
    try:
        LISTENER_SINCE_FILE.unlink()
    except OSError:
        pass


def _read_listener_anchor() -> tuple[int | None, float | None]:
    try:
        raw = LISTENER_SINCE_FILE.read_text(encoding="utf-8").strip().splitlines()
        if len(raw) >= 2:
            return int(raw[0]), float(raw[1])
    except (OSError, ValueError, IndexError):
        pass
    return None, None


def _write_listener_anchor(pid: int) -> None:
    ensure()
    LISTENER_SINCE_FILE.write_text(f"{pid}\n{time.time()}\n", encoding="utf-8")


def proxy_uptime_seconds() -> int | None:
    pid = find_pid()
    if pid is None:
        return None
    apid, t0 = _read_listener_anchor()
    if apid != pid or t0 is None:
        _write_listener_anchor(pid)
        return 0
    return max(0, int(time.time() - t0))


def format_uptime_hms(sec: int | None) -> str | None:
    if sec is None:
        return None
    sec = max(0, int(sec))
    h, rest = divmod(sec, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}"


def mark_starting() -> None:
    ensure()
    STARTING_FILE.write_text(str(time.time()), encoding="utf-8")


def clear_starting() -> None:
    try:
        STARTING_FILE.unlink()
    except FileNotFoundError:
        pass


def launching() -> bool:
    if not STARTING_FILE.is_file():
        return False
    if is_running():
        clear_starting()
        return False
    try:
        t0 = float(STARTING_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        clear_starting()
        return False
    if time.time() - t0 > STARTING_TIMEOUT_SEC:
        clear_starting()
        return False
    return True


def mark_restarting() -> None:
    ensure()
    RESTARTING_FILE.write_text(str(time.time()), encoding="utf-8")


def clear_restarting() -> None:
    try:
        RESTARTING_FILE.unlink()
    except FileNotFoundError:
        pass


def restarting() -> bool:
    if not RESTARTING_FILE.is_file():
        return False
    if is_running():
        clear_restarting()
        return False
    try:
        t0 = float(RESTARTING_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        clear_restarting()
        return False
    if time.time() - t0 > STARTING_TIMEOUT_SEC:
        clear_restarting()
        return False
    return True


def _popen_no_window() -> int:
    f = 0
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        f |= subprocess.CREATE_NEW_PROCESS_GROUP
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        f |= subprocess.CREATE_NO_WINDOW
    return f


def _proxy_worker_cmd(bind_host: str, secret: str) -> list[str]:
    """Из .exe — только флаги; из исходников — тот же .py, чтобы Python знал точку входа."""
    tail = [
        _WORKER_FLAG,
        "--host",
        bind_host,
        "--secret",
        secret,
        "--port",
        str(PORT),
    ]
    if getattr(sys, "frozen", False):
        return [sys.executable, *tail]
    return [sys.executable, str(Path(__file__).resolve()), *tail]


def start() -> None:
    ensure()
    if is_running():
        return
    secret = get_or_gen_secret()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    bind_host = "0.0.0.0" if home_proxy_enabled() else "127.0.0.1"
    proc = subprocess.Popen(
        _proxy_worker_cmd(bind_host, secret),
        cwd=str(REPO),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=_popen_no_window(),
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")


def _taskkill_pid(pid: int, force: bool = False) -> None:
    args = ["taskkill", "/PID", str(pid), "/T"]
    if force:
        args.append("/F")
    subprocess.run(
        args,
        capture_output=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "CREATE_NO_WINDOW")
        else 0,
    )


def stop() -> None:
    pid = find_pid()
    if pid:
        _taskkill_pid(pid, force=False)
        time.sleep(0.3)
        if is_running():
            _taskkill_pid(pid, force=True)
    try:
        saved = int(PID_FILE.read_text(encoding="utf-8").strip())
        if saved != pid:
            _taskkill_pid(saved, force=True)
    except (OSError, ValueError):
        pass
    try:
        PID_FILE.unlink()
    except OSError:
        pass
    clear_starting()
    _clear_listener_anchor()


def clear_home_qr_cache() -> None:
    for name in ("tg_proxy_qr.url", "tg_proxy_qr.b64"):
        p = STATE_DIR / name
        try:
            p.unlink()
        except OSError:
            pass


def tg_proxy_url_local() -> str:
    s = get_or_gen_secret()
    return f"tg://proxy?server=127.0.0.1&port={PORT}&secret=dd{s}"


def tg_proxy_url_lan() -> str:
    s = get_or_gen_secret()
    h = lan_ipv4() or "127.0.0.1"
    return f"tg://proxy?server={h}&port={PORT}&secret=dd{s}"


def set_clipboard(text: str) -> None:
    safe = text.replace("'", "''")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"Set-Clipboard -Value '{safe}'",
        ],
        capture_output=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "CREATE_NO_WINDOW")
        else 0,
    )


def open_tg_url(url: str) -> None:
    try:
        os.startfile(url)  # type: ignore[attr-defined]
    except Exception:
        webbrowser.open(url)


def qr_png_bytes(url: str) -> bytes | None:
    if not REPO.is_dir():
        return None
    rp = str(REPO)
    try:
        if rp not in sys.path:
            sys.path.insert(0, rp)
        from proxy.swiftbar_qr import qr_url_to_png_base64
        import base64

        b64 = qr_url_to_png_base64(url)
        if not b64:
            return None
        return base64.standard_b64decode(b64)
    except Exception:
        return None


def _tray_icon_image(running: bool, wait: bool):
    from PIL import Image as PILImage, ImageDraw

    w, h = 64, 64
    im = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    if wait:
        fill = (194, 122, 0, 255)
    elif running:
        fill = (26, 122, 90, 255)
    else:
        fill = (120, 120, 120, 255)
    margin = 6
    draw.ellipse((margin, margin, w - margin, h - margin), fill=fill)
    return im


def _build_menu(pystray, icon_ref: list):
    running = is_running()
    launch_wait = launching()
    restart_wait = restarting()
    wait = launch_wait or restart_wait
    up = format_uptime_hms(proxy_uptime_seconds() if running else None)
    home = home_proxy_enabled()

    MII = pystray.MenuItem

    def refresh_after(fn):
        def inner(_i):
            fn()
            icon = icon_ref[0]
            icon.menu = _build_menu(pystray, icon_ref)
            icon.update_menu()

        return inner

    items: list = []

    if restart_wait:
        items.append(MII("Перезапуск…", None, enabled=False))
    elif launch_wait:
        items.append(MII("Запуск прокси…", None, enabled=False))
    elif running:
        label = f"Прокси запущен ({up})" if up else "Прокси запущен"
        items.append(MII(label, None, enabled=False))
    else:
        items.append(MII("Прокси остановлен", None, enabled=False))

    items.append(pystray.Menu.SEPARATOR)

    def stop_and_clear():
        stop()
        clear_restarting()

    if running:
        items.append(MII("Выключить", refresh_after(stop_and_clear)))
    elif wait:
        items.append(MII("Прервать", refresh_after(stop_and_clear)))
    else:

        def do_start():
            ensure()
            if not is_running():
                mark_starting()
            start()

        items.append(MII("Включить", refresh_after(do_start)))

    def toggle_home():
        ensure()
        was_running = is_running()
        want_on = not home_proxy_enabled()
        if want_on:
            HOME_PROXY_FILE.write_text("1", encoding="utf-8")
            clear_home_qr_cache()
        else:
            try:
                HOME_PROXY_FILE.unlink()
            except FileNotFoundError:
                pass
            clear_home_qr_cache()
        if was_running:
            mark_restarting()
            stop()
            time.sleep(0.5)
            start()

    items.append(
        MII(
            "Домашний прокси (LAN, QR)",
            refresh_after(toggle_home),
            checked=lambda _: home,
        )
    )

    if home and not running and not wait:
        nip = lan_ipv4() or "—"
        items.append(MII(f"След. запуск: {nip}:{PORT}", None, enabled=False))

    items.append(pystray.Menu.SEPARATOR)

    items.append(
        MII(
            "Открыть Telegram (этот ПК)",
            refresh_after(lambda: open_tg_url(tg_proxy_url_local())),
        )
    )

    if running and home:
        items.append(
            MII(
                "Копировать ссылку (телефон, LAN)",
                refresh_after(lambda: set_clipboard(tg_proxy_url_lan())),
            )
        )

        def show_qr():
            data = qr_png_bytes(tg_proxy_url_lan())
            if not data:
                return
            ensure()
            path = STATE_DIR / "tg_proxy_qr_last.png"
            path.write_bytes(data)
            os.startfile(str(path))  # type: ignore[attr-defined]

        items.append(MII("Показать QR для телефона", refresh_after(show_qr)))
    elif running and not home:
        items.append(
            MII(
                "Копировать ссылку (localhost)",
                refresh_after(lambda: set_clipboard(tg_proxy_url_local())),
            )
        )

    items.append(pystray.Menu.SEPARATOR)

    def new_secret():
        clear_restarting()
        stop()
        time.sleep(0.8)
        SECRET_FILE.write_text(secrets.token_hex(16), encoding="utf-8")
        ensure()
        if not is_running():
            mark_starting()
        start()

    items.append(MII("Новый секрет (перезапуск)", refresh_after(new_secret)))
    items.append(
        MII(
            f"Папка состояния ({STATE_DIR.name})",
            refresh_after(lambda: os.startfile(str(STATE_DIR))),  # type: ignore[attr-defined]
        )
    )
    items.append(MII("Выход", lambda _: icon_ref[0].stop()))

    return pystray.Menu(*items)


def main() -> None:
    if sys.platform != "win32":
        print("Нужна ОС Windows.", file=sys.stderr)
        sys.exit(1)
    if not RUN_SCRIPT.is_file():
        print(f"Не найден {RUN_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    try:
        import pystray
    except ImportError:
        print(
            "Установите зависимости: pip install -r contrib/requirements-tray-windows.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    ensure()

    icon = pystray.Icon(
        "tg_ws_proxy",
        icon=_tray_icon_image(False, False),
        title="TG WS Proxy",
        menu=pystray.Menu(),
    )
    icon_ref: list = [icon]

    def setup_fn(ic: object) -> None:
        def tick() -> None:
            while getattr(ic, "visible", True):
                try:
                    r = is_running()
                    w = launching() or restarting()
                    ic.icon = _tray_icon_image(r, w)
                    if w:
                        tip = "TG WS Proxy — перезапуск…" if restarting() else "TG WS Proxy — запуск…"
                    elif r:
                        up = format_uptime_hms(proxy_uptime_seconds())
                        tip = f"TG WS Proxy — работает ({up})" if up else "TG WS Proxy — работает"
                    else:
                        tip = "TG WS Proxy — остановлен"
                    ic.title = tip
                    ic.menu = _build_menu(pystray, icon_ref)
                    ic.update_menu()
                except Exception:
                    pass
                time.sleep(STREAM_TICK_SEC)

        threading.Thread(target=tick, daemon=True).start()
        ic.menu = _build_menu(pystray, icon_ref)
        ic.update_menu()

    icon.run(setup_fn)


if __name__ == "__main__":
    if _WORKER_FLAG in sys.argv:
        _run_embedded_proxy_worker()
        raise SystemExit(0)
    if sys.platform != "win32":
        print("Этот скрипт рассчитан на Windows.", file=sys.stderr)
        raise SystemExit(1)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()

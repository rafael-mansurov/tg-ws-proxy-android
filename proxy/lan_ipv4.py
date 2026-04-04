# Выбор IPv4 для «домашнего» MTProto-прокси (tg://server=…).
# На macOS адрес из UDP connect(8.8.8.8) часто даёт IP VPN (utun), а не Wi‑Fi —
# телефон в локальной сети до него не достучится.

from __future__ import annotations

import platform
import re
import subprocess
from typing import List, Optional, Tuple

_IFACE_HEAD = re.compile(r"^([^:\s]+):")


def _rfc1918(ip: str) -> bool:
    try:
        a, b, _, _ = (int(x) for x in ip.split("."))
    except (ValueError, AttributeError):
        return False
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 192 and b == 168:
        return True
    return False


def _ipconfig_getifaddr(iface: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["ipconfig", "getifaddr", iface],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    ip = (r.stdout or "").strip()
    return ip or None


def _darwin_default_interface() -> Optional[str]:
    try:
        r = subprocess.run(
            ["/usr/sbin/route", "-n", "get", "default"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        s = line.strip()
        if s.startswith("interface: "):
            return s.split(":", 1)[1].strip()
    return None


def _darwin_ifconfig_inet_pairs() -> List[Tuple[str, str]]:
    try:
        r = subprocess.run(
            ["/sbin/ifconfig"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0 or not r.stdout:
        return []
    pairs: List[Tuple[str, str]] = []
    iface: Optional[str] = None
    for line in r.stdout.splitlines():
        m = _IFACE_HEAD.match(line)
        if m and not line.startswith("\t"):
            iface = m.group(1)
            continue
        if iface is None:
            continue
        st = line.strip()
        if not st.startswith("inet "):
            continue
        parts = st.split()
        if len(parts) < 2:
            continue
        ip = parts[1]
        if ip.startswith("127."):
            continue
        pairs.append((iface, ip))
    return pairs


def _darwin_lan_candidates() -> List[Tuple[str, str]]:
    """(iface, ip) пригодные для LAN: en* с частным адресом, без utun/awdl/llw."""
    out: List[Tuple[str, str]] = []
    for iface, ip in _darwin_ifconfig_inet_pairs():
        if not iface.startswith("en"):
            continue
        if not _rfc1918(ip):
            continue
        out.append((iface, ip))
    return out


def _pick_preferred(candidates: List[Tuple[str, str]]) -> Optional[str]:
    if not candidates:
        return None
    for _, ip in candidates:
        if ip.startswith("192.168."):
            return ip
    for _, ip in candidates:
        if ip.startswith("10."):
            return ip
    return candidates[0][1]


def _fallback_udp_trick() -> Optional[str]:
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return None


def lan_ipv4_preferred() -> Optional[str]:
    """Лучший guess IPv4 для подключения с других устройств в той же сети."""
    if platform.system() == "Darwin":
        # 1) Интерфейс маршрута по умолчанию — если это en* и частный IP, берём его
        dr = _darwin_default_interface()
        if dr and dr.startswith("en") and not dr.startswith("utun"):
            lip = _ipconfig_getifaddr(dr)
            if lip and _rfc1918(lip):
                return lip

        # 2) Все частные IPv4 на en*
        cand = _darwin_lan_candidates()
        picked = _pick_preferred(cand)
        if picked:
            return picked

        # 3) Интерфейс по умолчанию — любой не-loopback (например без частного сегмента)
        if dr and dr.startswith("en"):
            lip = _ipconfig_getifaddr(dr)
            if lip and not lip.startswith("127."):
                return lip

    # 4) Старый трюк / запас
    return _fallback_udp_trick()

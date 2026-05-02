"""IPv4 для --dc-ip: резолв kws*.t.me (IP-адрес), SNI — kws*.web.telegram.org."""
from __future__ import annotations

import ipaddress
import socket
from typing import Optional

_FALLBACK_TELEGRAM_WS_EDGE_IP = "149.154.167.220"
# Clash/Surge/sing-box: fake-ip из TEST-NET-2; сырой TCP из Python в туннель не уходит — WS падает.
_FAKE_IP_NET = ipaddress.ip_network("198.18.0.0/15")

_last_edge_ip_ok: Optional[str] = None


def _is_usable_edge_ipv4(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.version != 4:
        return False
    if addr in _FAKE_IP_NET:
        return False
    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return False
    return True


def _tcp443_open(ip: str, timeout_s: float = 2.0) -> bool:
    try:
        with socket.create_connection((ip, 443), timeout=timeout_s):
            return True
    except OSError:
        return False


def _candidate_ips_for_dc(dc: int) -> list[str]:
    """Порядок: как отдаёт DNS по двум именам; дубликаты убираем; в конце — 149.154.167.220."""
    seen: set[str] = set()
    out: list[str] = []
    for name in (
        f"kws{dc}.t.me",
        f"kws{dc}-1.t.me",
    ):
        try:
            infos = socket.getaddrinfo(
                name, 443, socket.AF_INET, socket.SOCK_STREAM,
            )
        except OSError:
            continue
        for _fam, _typ, _proto, _canon, sockaddr in infos:
            ip = sockaddr[0]
            if not ip or not _is_usable_edge_ipv4(ip) or ip in seen:
                continue
            seen.add(ip)
            out.append(ip)
    fb = _FALLBACK_TELEGRAM_WS_EDGE_IP
    if fb not in seen:
        out.append(fb)
    return out


def resolve_kws_edge_ipv4(dc: int) -> str:
    """IP для --dc-ip: из DNS kws*.t.me, проверяем TCP :443.

    kws*.web.telegram.org → 404, kws*.stel.com → 200 (не WS), kws*.t.me → 302, но
    IP из kws*.t.me + SNI kws*.web.telegram.org → 101 Switching Protocols (работает).
    На Android тот же модуль вызывается из services/proxy_service перед стартом tg_ws_proxy.
    """
    global _last_edge_ip_ok
    if _last_edge_ip_ok and _tcp443_open(_last_edge_ip_ok, timeout_s=1.5):
        return _last_edge_ip_ok
    for ip in _candidate_ips_for_dc(dc):
        if _tcp443_open(ip):
            _last_edge_ip_ok = ip
            return ip
    return _FALLBACK_TELEGRAM_WS_EDGE_IP

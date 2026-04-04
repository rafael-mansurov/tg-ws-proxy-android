# PNG QR для SwiftBar: только stdlib + Nayuki qrcodegen (MIT), без Pillow.
# Генератор: scripts/qrcodegen_nayuki.py — https://www.nayuki.io/page/qr-code-generator-library

from __future__ import annotations

import base64
import struct
import sys
import zlib
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[1]
_SCR = _ROOT / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

from qrcodegen_nayuki import QrCode  # noqa: E402


def _inside_round_rect(x: int, y: int, w: int, h: int, r: int) -> bool:
    """Точка (x,y) внутри прямоугольника w×h со скруглением углов радиусом r."""
    if r <= 0:
        return 0 <= x < w and 0 <= y < h
    r = min(r, w // 2, h // 2)
    if not (0 <= x < w and 0 <= y < h):
        return False
    if x < r and y < r:
        return (x - r) ** 2 + (y - r) ** 2 <= r * r
    if x >= w - r and y < r:
        return (x - (w - r)) ** 2 + (y - r) ** 2 <= r * r
    if x < r and y >= h - r:
        return (x - r) ** 2 + (y - (h - r)) ** 2 <= r * r
    if x >= w - r and y >= h - r:
        return (x - (w - r)) ** 2 + (y - (h - r)) ** 2 <= r * r
    return True


def _png_rgba8(rows: list[bytes], width: int, height: int) -> bytes:
    """Truecolor+alpha RGBA 8-bit, filter type 0 per row."""
    raw = bytearray()
    for row in rows:
        raw.append(0)
        raw.extend(row)
    zpayload = zlib.compress(bytes(raw), 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zpayload) + chunk(b"IEND", b"")


def qr_url_to_png_base64(
    url: str,
    scale: int = 6,
    border_modules: int = 4,
    corner_radius_px: Optional[int] = None,
) -> Optional[str]:
    """tg://… → base64 PNG или None при ошибке. Углы слегка скруглены (RGBA, прозрачность снаружи радиуса)."""
    try:
        qr = QrCode.encode_text(url, QrCode.Ecc.MEDIUM)
    except Exception:
        return None
    n = qr.get_size()
    dim = n + 2 * border_modules
    px = dim * scale
    r = corner_radius_px if corner_radius_px is not None else max(8, int(px * 0.045))
    rows: list[bytes] = []
    for py in range(px):
        my = py // scale
        line = bytearray()
        for px_ in range(px):
            if not _inside_round_rect(px_, py, px, px, r):
                line.extend((255, 255, 255, 0))
                continue
            mx = px_ // scale
            dark = False
            if border_modules <= mx < border_modules + n and border_modules <= my < border_modules + n:
                dark = qr.get_module(mx - border_modules, my - border_modules)
            if dark:
                line.extend((0, 0, 0, 255))
            else:
                line.extend((255, 255, 255, 255))
        rows.append(bytes(line))
    png = _png_rgba8(rows, px, px)
    return base64.standard_b64encode(png).decode("ascii")

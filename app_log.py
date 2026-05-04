"""Shared append-only log helpers with size cap for UI + foreground service."""

from __future__ import annotations

import os
import time
from pathlib import Path

# Bounded cumulative log size (~512 KiB default); trims oldest lines when exceeded.
LOG_MAX_BYTES = int(os.environ.get("TGWS_LOG_MAX_BYTES", str(512 * 1024)))


def append_line(path: Path, message: str, *, reset: bool = False) -> None:
    """Append one UTF-8 line with HH:MM:SS prefix (already prefixed columns handled by caller)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if reset else "a"
        if reset:
            with path.open(mode, encoding="utf-8") as f:
                f.write(message if message.endswith("\n") else message + "\n")
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            return

        _truncate_before_append(path, LOG_MAX_BYTES - len(message.encode("utf-8")) - 32)

        with path.open("a", encoding="utf-8") as f:
            f.write(message if message.endswith("\n") else message + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
    except OSError:
        pass


def append_plain_timestamp_line(path: Path, body_after_ts: str, *, reset: bool = False) -> None:
    """Write ``HH:MM:SS`` + body (caller supplies spacing/columns after timestamp)."""
    ts = time.strftime("%H:%M:%S")
    line = f"{ts}{body_after_ts}"
    if not line.endswith("\n"):
        line += "\n"
    append_line(path, line, reset=reset)


def _truncate_before_append(path: Path, budget_bytes: int) -> None:
    """Shrink existing file so approximate tail stays under ``budget_bytes``."""
    if budget_bytes <= 0:
        budget_bytes = 4096
    try:
        sz = path.stat().st_size
    except OSError:
        return
    if sz <= budget_bytes:
        return
    try:
        raw = path.read_bytes()
    except OSError:
        return
    drop = sz - budget_bytes
    cut = raw.find(b"\n", drop)
    if cut == -1:
        cut = drop
    else:
        cut += 1
    try:
        path.write_bytes(raw[cut:])
    except OSError:
        pass

#!/usr/bin/env python3
"""sendPhoto/sendDocument в Telegram с UTF-8 (curl в Git Bash на Windows портит кириллицу в -F caption)."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    crlf = b"\r\n"
    parts: list[bytes] = []
    for name, value in fields.items():
        if value is None:
            continue
        parts.append(f"--{boundary}".encode("ascii") + crlf)
        cd = f'Content-Disposition: form-data; name="{name}"'
        parts.append(cd.encode("utf-8") + crlf + crlf)
        if isinstance(value, bytes):
            parts.append(value + crlf)
        else:
            parts.append(str(value).encode("utf-8") + crlf)
    for name, (filename, content, mime) in files.items():
        parts.append(f"--{boundary}".encode("ascii") + crlf)
        disp = f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
        parts.append(disp.encode("utf-8") + crlf)
        parts.append(f"Content-Type: {mime}".encode("ascii") + crlf + crlf)
        parts.append(content + crlf)
    parts.append(f"--{boundary}--".encode("ascii") + crlf)
    body = b"".join(parts)
    ctype = f"multipart/form-data; boundary={boundary}"
    return body, ctype


def _post(url: str, data: bytes, headers: dict) -> None:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, context=ctx) as r:
        raw = r.read().decode()
    j = json.loads(raw)
    if not j.get("ok"):
        raise RuntimeError(raw[:500])


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        print("Telegram: секреты не заданы, пропуск.")
        return

    thread_raw = (os.environ.get("TELEGRAM_EXE_THREAD_ID") or "").strip()
    thread: str | None = thread_raw or None

    run_no = os.environ.get("GITHUB_RUN_NUMBER", "0")
    srv = os.environ["GITHUB_SERVER_URL"].rstrip("/")
    repo = os.environ["GITHUB_REPOSITORY"]
    dl_zip = f"{srv}/{repo}/releases/download/latest-windows-tray/tg-ws-proxy-windows-tray.zip"
    tg_channel = "https://t.me/+zFHFTrH7SBMzMGZi"

    base_ver = "1.0"
    spec_path = Path("buildozer.spec")
    if spec_path.is_file():
        for line in spec_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("version = "):
                full = s.split("=", 1)[1].strip()
                parts = full.split(".")
                if len(parts) >= 2:
                    base_ver = f"{parts[0]}.{parts[1]}"
                break
    app_ver = f"{base_ver}.{run_no}"
    caption = (
        f"✅ Новая версия Windows. Версия: {app_ver}\n"
        f"Режим: Release\n\n"
        f'<a href="{dl_zip}">Скачать ZIP</a>\n\n'
        f'<a href="{tg_channel}">Подпишись на Telegram канал</a>'
    )

    api = f"https://api.telegram.org/bot{token}"
    fields: dict = {
        "chat_id": chat,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if thread is not None:
        fields["message_thread_id"] = thread

    cover = Path("cover.jpg")
    if cover.is_file():
        body, ctype = _multipart(
            fields,
            {"photo": ("cover.jpg", cover.read_bytes(), "image/jpeg")},
        )
        _post(f"{api}/sendPhoto", body, {"Content-Type": ctype})
    else:
        msg: dict = {
            "chat_id": chat,
            "text": caption,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if thread is not None:
            msg["message_thread_id"] = int(thread)
        raw = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        _post(
            f"{api}/sendMessage",
            raw,
            {"Content-Type": "application/json; charset=utf-8"},
        )

    zip_path = Path("tg-ws-proxy-windows-tray.zip")
    if not zip_path.is_file():
        print("ZIP не найден, sendDocument пропущен.")
        return

    doc_fields: dict = {"chat_id": chat}
    if thread is not None:
        doc_fields["message_thread_id"] = thread
    doc_body, doc_ct = _multipart(
        doc_fields,
        {
            "document": (
                "tg-ws-proxy-windows-tray.zip",
                zip_path.read_bytes(),
                "application/zip",
            )
        },
    )
    try:
        _post(f"{api}/sendDocument", doc_body, {"Content-Type": doc_ct})
    except (urllib.error.HTTPError, OSError, RuntimeError) as e:
        print(f"::warning::Telegram: не удалось отправить ZIP ({e})")


if __name__ == "__main__":
    main()

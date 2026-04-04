#!/usr/bin/env bash
# Одна команда для Mac: SwiftBar (если есть brew) + проект с GitHub + плагин в ~/SwiftBarPlugins.
set -euo pipefail

ARCHIVE_URL="https://github.com/rafael-mansurov/tg-ws-proxy-android/archive/refs/heads/main.zip"
DEST="${DEST_OVERRIDE:-$HOME/Documents/proxy/tg-ws-proxy-apk}"
PLUG_DIR="${HOME}/SwiftBarPlugins"
PLUGIN="tgwsproxy.1s.py"

if command -v brew >/dev/null 2>&1; then
  echo "SwiftBar через Homebrew…"
  brew install --cask swiftbar || true
else
  echo "Нет brew — поставь SwiftBar: https://github.com/swiftbar/SwiftBar/releases" >&2
fi

for need in curl unzip; do
  command -v "$need" >/dev/null 2>&1 || {
    echo "Не найдено: $need" >&2
    exit 1
  }
done

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

echo "Качаю проект с GitHub…"
curl -fsSL "$ARCHIVE_URL" -o "$TMP/repo.zip"
unzip -q "$TMP/repo.zip" -d "$TMP/extract"
EXTRACTED="$(find "$TMP/extract" -mindepth 1 -maxdepth 1 -type d | head -1)"
if [[ -z "${EXTRACTED}" ]]; then
  echo "Архив битый." >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
mv "$EXTRACTED" "$DEST"

if [[ ! -f "${DEST}/contrib/${PLUGIN}" ]]; then
  echo "Нет ${PLUGIN} в архиве." >&2
  exit 1
fi

mkdir -p "$PLUG_DIR"
cp "${DEST}/contrib/${PLUGIN}" "${PLUG_DIR}/${PLUGIN}"
chmod +x "${PLUG_DIR}/${PLUGIN}"

# Запуск, если SwiftBar уже есть (после brew — обычно в /Applications)
open -a SwiftBar 2>/dev/null || true

echo ""
echo "Готово. Если SwiftBar открылся — в настройках папка ${PLUG_DIR}. Иначе поставь SwiftBar и открой вручную."
echo "В меню: TG proxy → Включить."

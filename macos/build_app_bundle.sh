#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/TGWSProxyMenuBar" && pwd)"
cd "$ROOT"
swift build -c release
EXE="$ROOT/.build/release/TGWSProxyMenuBar"
APP="$ROOT/../TGWSProxyMenuBar.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$EXE" "$APP/Contents/MacOS/TGWSProxyMenuBar"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key>
	<string>TGWSProxyMenuBar</string>
	<key>CFBundleIdentifier</key>
	<string>unofficial.tgws.TGWSProxyMenuBar</string>
	<key>CFBundleName</key>
	<string>TG WS Proxy</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>1.0</string>
	<key>LSUIElement</key>
	<true/>
</dict>
</plist>
PLIST
echo "Собрано: $APP"
echo "Перенеси .app в /Applications и открой один раз (может спросить про безопасность)."

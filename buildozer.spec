[app]
title = TG WS Proxy
package.name = tgwsproxy
package.domain = unofficial.tgws
source.dir = .
source.include_exts = py,html
source.include_patterns = ui/*
version = 1.5.3
requirements = python3,openssl,cryptography,cffi,android
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #e8ecf2
services = proxy:services/proxy_service.py:foreground:sticky

android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a,armeabi-v7a
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK,POST_NOTIFICATIONS,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC

p4a.bootstrap = webview
p4a.port = 8080

[buildozer]
log_level = 2
warn_on_root = 1

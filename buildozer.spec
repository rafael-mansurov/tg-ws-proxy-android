[app]
title = TG WS Proxy
package.name = tgwsproxy
package.domain = unofficial.tgws
source.dir = .
source.include_exts = py
version = 1.4.0
requirements = python3,kivy,openssl,cryptography,cffi,android
orientation = portrait
fullscreen = 0
services = proxy:services/proxy_service.py:foreground:sticky

android.api = 34
android.minapi = 24
android.ndk = 23b
android.accept_sdk_license = True
android.archs = arm64-v8a,armeabi-v7a
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK,POST_NOTIFICATIONS,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC

[buildozer]
log_level = 2
warn_on_root = 1

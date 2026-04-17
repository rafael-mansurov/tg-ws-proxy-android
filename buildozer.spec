[app]
title = TG WS Proxy
package.name = tgwsproxy
package.domain = unofficial.tgws
source.dir = .
source.include_exts = py,html,png,css,jpg,js
source.include_patterns = ui/*,icon.png,cover.jpg
version = 1.5.6
requirements = python3,openssl,cryptography,cffi,android
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #0f0f11
services = proxy:services/proxy_service.py:foreground:sticky

android.api = 34
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a,armeabi-v7a
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK,POST_NOTIFICATIONS,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,RECEIVE_BOOT_COMPLETED
# APK для установки с телефона (AAB в CI давал bin/*.aab и ломал шаги с bin/*.apk)
android.release_artifact = apk

p4a.bootstrap = webview
p4a.port = 8080
p4a.hook = tools/p4a_hook.py
android.gradle_dependencies = androidx.core:core:1.12.0,androidx.core:core-splashscreen:1.0.1

# Deep link: tgwsproxy://reset-password#access_token=...&type=recovery
android.manifest.intent_filters = intent_filters.xml

[buildozer]
log_level = 2
warn_on_root = 1

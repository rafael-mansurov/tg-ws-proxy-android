[app]
title = TG WS Proxy
package.name = tgwsproxy
package.domain = unofficial.tgws
source.dir = .
# json — чтобы в APK попал tgws_supabase_public.json рядом с main.py (иначе WebView без Supabase).
source.include_exts = py,html,png,css,jpg,js,json
source.include_patterns = ui/*,icon.png,cover.jpg,tgws_supabase_public.json
version = 1.6.0
# Принудительно держим растущий Android versionCode отдельно от versionName,
# чтобы обновления не ломались при переходе с 1.5.200 на 1.6.x.
android.numeric_version = 102410700
requirements = python3,openssl,cryptography,cffi,android
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #0f0f11
services = proxy:services/proxy_service.py:foreground:sticky

# API 34+ константы ServiceInfo для startForeground(…, type); compileSdk подтягивает hook до ≥34.
android.api = 34
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK,POST_NOTIFICATIONS,FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,RECEIVE_BOOT_COMPLETED
# APK для установки с телефона (AAB в CI давал bin/*.aab и ломал шаги с bin/*.apk)
android.release_artifact = apk

p4a.bootstrap = webview
p4a.port = 8080
p4a.hook = tools/p4a_hook.py
p4a.local_recipes = ./p4a_recipes
android.gradle_dependencies = androidx.core:core:1.12.0,androidx.core:core-splashscreen:1.0.1

# Deep link: tgwsproxy://reset-password#access_token=...&type=recovery
android.manifest.intent_filters = intent_filters.xml

[buildozer]
log_level = 2
warn_on_root = 1

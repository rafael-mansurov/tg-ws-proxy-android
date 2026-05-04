# Прогресс правок (security / UX audit)

Ключи Supabase для работы приложения: скопируйте `tgws_supabase_public.example.json` → `tgws_supabase_public.json` рядом с `main.py` **или** задайте переменные окружения `TGWS_SUPABASE_URL` и `TGWS_SUPABASE_ANON_KEY` при запуске / сборке. Файл с секретами не коммитится (см. `.gitignore`).

## Сделано

- **15–16:** Секрет прокси не передаётся в Intent: `pythonServiceArgument` = `"{}"`; сервис читает секрет только из внутреннего файла приложения.
- **17:** Убраны чувствительные сведения из UI-логов (`main.py`), превью env в `proxy_service.py`, фрагмент handshake из warning в `tg_ws_proxy.py`; startup-логи прокси не печатают секрет и tg:// ссылку.
- **18:** Комментарий о MODE_PRIVATE / internal storage у `_save_secret` в `main.py`.
- **47:** Ротация/усечение общего лога (`app_log.py`, `_write_start_log`, `_svc_log`).
- **52:** Полная очистка при kill процесса Android ограничена платформой; graceful-путь уже есть в `tg_ws_proxy._run` при `stop_event` — без изменений JNI.
- **64 Service:** `ServiceProxy.startType()` → `START_NOT_STICKY`.
- **75 (proxy):** Именованные константы таймаутов/chunk в `tg_ws_proxy.py`.
- **74 / admin + index:** JWT anon убран из статики HTML; подстановка через `window.__TGWS_SUPABASE__` при отдаче `/`, `/index.html` и `/admin.html` (`main.py`), локальные `/supabase.min.js` и `/lucide.min.js` в admin.
- **9:** Блок «Разрешения и фон» в настройках (`index.html`).
- **11:** Skeleton-карточки при обновлении списка пользователей в admin.
- **14:** Баннер и сообщения «нет сети» (`index.html`, `_localFetch`, `onToggle`).
- **41:** Пауза pulse при `prefers-reduced-motion` и когда вкладка/приложение скрыто (`doc-hidden`).
- **44:** Второе поле пароля в admin modal смены пароля.
- **66:** Этапы текста при запуске прокси (`bumpStartingPhase`).
- **75 index:** `disabled` + `aria-disabled` на кнопке Telegram.
- **81:** `viewport-fit=cover` и safe-area в admin.
- **82:** Lucide в admin с локального `/lucide.min.js` (фиксированный файл в APK).
- **85:** Удалены неиспользуемые стили `.search-input` и код дебаунса.
- **86:** Стили баннеров батареи/обновления вынесены в CSS-классы.

## Осталось / частично

- **18 (усиление):** EncryptedSharedPreferences / Keystore для секрета прокси — не делалось.
- **52:** Дополнительная JNI-очистка до `Process.killProcess` — не делалось.
- **64** ref HTML onclick: массовый рефакторинг inline-обработчиков — только запланировано (эпик).

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `TGWS_SUPABASE_URL` | Публичный URL проекта Supabase |
| `TGWS_SUPABASE_ANON_KEY` | Публичный anon JWT |
| `TGWS_LOG_MAX_BYTES` | Предел размера `tgws_proxy.log` перед усечением (по умолчанию 524288) |

package unofficial.tgws.tgwsproxy;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.SystemClock;

import java.util.Locale;

public class BootCompletedReceiver extends BroadcastReceiver {
    private static final String ACTION_AUTOSTART_RETRY =
        "unofficial.tgws.tgwsproxy.action.AUTOSTART_RETRY";
    private static final String EXTRA_ATTEMPT = "attempt";
    private static final long VERIFY_TIMEOUT_MS = 12_000L;
    private static final long[] RETRY_DELAYS_MS = new long[] {15_000L, 45_000L, 120_000L};

    @Override
    public void onReceive(Context context, Intent intent) {
        if (context == null || intent == null) {
            return;
        }
        Context appContext = context.getApplicationContext();
        String action = intent.getAction() == null ? "" : intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action)
            && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)
            && !Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action)
            && !ACTION_AUTOSTART_RETRY.equals(action)) {
            return;
        }
        if (!ProxyControl.isAutostartEnabled(appContext)) {
            return;
        }

        final PendingResult pendingResult = goAsync();
        new Thread(() -> {
            try {
                handleAutostart(appContext, action, intent.getIntExtra(EXTRA_ATTEMPT, 0));
            } finally {
                pendingResult.finish();
            }
        }, "tgws-boot-autostart").start();
    }

    private void handleAutostart(Context context, String action, int attempt) {
        if (ProxyControl.isProxyRunning()) {
            return;
        }

        if (Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action) && ProxyControl.readSecret(context) == null) {
            scheduleRetry(context, attempt, 20_000L);
            return;
        }

        boolean started = ProxyControl.startProxy(context);
        if (started && ProxyControl.waitUntilProxyRunning(VERIFY_TIMEOUT_MS)) {
            return;
        }

        if (attempt < RETRY_DELAYS_MS.length) {
            scheduleRetry(context, attempt, RETRY_DELAYS_MS[attempt]);
            return;
        }

        String reason;
        if (ProxyControl.readSecret(context) == null) {
            reason = "Не удалось прочитать настройки прокси после перезагрузки. Открой приложение и включи прокси снова.";
        } else if (!ProxyControl.isIgnoringBatteryOptimizations(context)) {
            reason = "Android ограничил фоновый запуск. Открой приложение и отключи оптимизацию батареи для TG WS Proxy.";
        } else {
            reason = "Сервис не поднялся автоматически после перезагрузки. Открой приложение и проверь статус прокси.";
        }
        ProxyControl.showBootAutostartIssue(context, reason);
    }

    private void scheduleRetry(Context context, int attempt, long delayMs) {
        try {
            AlarmManager alarmManager =
                (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
            if (alarmManager == null) {
                return;
            }
            Intent retryIntent = new Intent(context, BootCompletedReceiver.class);
            retryIntent.setAction(ACTION_AUTOSTART_RETRY);
            retryIntent.setPackage(context.getPackageName());
            retryIntent.putExtra(EXTRA_ATTEMPT, Math.max(0, attempt) + 1);

            PendingIntent pendingIntent = PendingIntent.getBroadcast(
                context,
                1001,
                retryIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
            );

            long triggerAt = SystemClock.elapsedRealtime() + Math.max(5_000L, delayMs);
            alarmManager.setExactAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                triggerAt,
                pendingIntent
            );
        } catch (Exception ignored) {
            String text = String.format(
                Locale.US,
                "Автозапуск не удался, и повторный запуск не назначился. Открой приложение и проверь прокси."
            );
            ProxyControl.showBootAutostartIssue(context, text);
        }
    }
}

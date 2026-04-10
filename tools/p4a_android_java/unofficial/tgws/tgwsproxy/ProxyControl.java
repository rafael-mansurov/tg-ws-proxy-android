package unofficial.tgws.tgwsproxy;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.PowerManager;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.util.Locale;

public final class ProxyControl {
    public static final String PREFS_NAME = "tgws_proxy_prefs";
    public static final String PREF_AUTOSTART_ON_BOOT = "autostart_on_boot";
    public static final String SECRET_FILENAME = "tgws_proxy_secret.hex";
    public static final int PROXY_PORT = 1443;
    private static final String ALERT_CHANNEL_ID = "tgws_proxy_boot_alerts";
    private static final int BOOT_ALERT_NOTIFICATION_ID = 88312;

    private ProxyControl() {}

    public static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    public static boolean isAutostartEnabled(Context context) {
        return prefs(context).getBoolean(PREF_AUTOSTART_ON_BOOT, false);
    }

    public static String readSecret(Context context) {
        File f = new File(context.getFilesDir(), SECRET_FILENAME);
        if (!f.isFile()) {
            return null;
        }
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String raw = br.readLine();
            if (raw == null) {
                return null;
            }
            raw = raw.trim().toLowerCase(Locale.US);
            if (raw.length() != 32) {
                return null;
            }
            for (int i = 0; i < raw.length(); i++) {
                char c = raw.charAt(i);
                if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) {
                    return null;
                }
            }
            return raw;
        } catch (Exception ignored) {
            return null;
        }
    }

    public static boolean isProxyRunning() {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress("127.0.0.1", PROXY_PORT), 250);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    public static void stopProxy(Context context) {
        try {
            ServiceProxy.stop(context);
        } catch (Exception ignored) {
        }
    }

    public static boolean startProxy(Context context) {
        String secret = readSecret(context);
        if (secret == null) {
            return false;
        }

        stopProxy(context);

        String fgText = "Прокси " + detectLinkHost() + ":" + PROXY_PORT + " · нажми, чтобы открыть приложение";
        try {
            JSONObject payload = new JSONObject();
            payload.put("secret", secret);
            ServiceProxy.start(context, "", "TG WS Proxy", fgText, payload.toString());
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    public static boolean waitUntilProxyRunning(long timeoutMs) {
        long deadline = System.currentTimeMillis() + Math.max(250L, timeoutMs);
        while (System.currentTimeMillis() < deadline) {
            if (isProxyRunning()) {
                return true;
            }
            try {
                Thread.sleep(300L);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
                return isProxyRunning();
            }
        }
        return isProxyRunning();
    }

    public static boolean isIgnoringBatteryOptimizations(Context context) {
        try {
            PowerManager pm = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
            return pm != null && pm.isIgnoringBatteryOptimizations(context.getPackageName());
        } catch (Exception ignored) {
            return true;
        }
    }

    public static void showBootAutostartIssue(Context context, String text) {
        try {
            NotificationManager manager =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager == null) {
                return;
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                NotificationChannel channel = new NotificationChannel(
                    ALERT_CHANNEL_ID,
                    "TG WS Proxy · автозапуск",
                    NotificationManager.IMPORTANCE_DEFAULT
                );
                channel.setDescription("Уведомления о проблемах автозапуска после перезагрузки");
                manager.createNotificationChannel(channel);
            }

            Intent launchIntent =
                context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
            PendingIntent contentIntent = null;
            if (launchIntent != null) {
                launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
                contentIntent = PendingIntent.getActivity(
                    context,
                    0,
                    launchIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
                );
            }

            Notification.Builder builder =
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                    ? new Notification.Builder(context, ALERT_CHANNEL_ID)
                    : new Notification.Builder(context);
            builder
                .setSmallIcon(context.getApplicationInfo().icon)
                .setContentTitle("TG WS Proxy не запустился после перезагрузки")
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setAutoCancel(true)
                .setOnlyAlertOnce(true);
            if (contentIntent != null) {
                builder.setContentIntent(contentIntent);
            }
            manager.notify(BOOT_ALERT_NOTIFICATION_ID, builder.build());
        } catch (Exception ignored) {
        }
    }

    private static String detectLinkHost() {
        try (DatagramSocket socket = new DatagramSocket()) {
            socket.connect(InetAddress.getByName("8.8.8.8"), 80);
            String ip = socket.getLocalAddress().getHostAddress();
            if (ip != null && !ip.startsWith("127.")) {
                return ip;
            }
        } catch (Exception ignored) {
        }
        return "127.0.0.1";
    }
}

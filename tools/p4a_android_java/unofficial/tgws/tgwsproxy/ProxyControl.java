package unofficial.tgws.tgwsproxy;

import android.content.Context;
import android.content.SharedPreferences;
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
    /** Записывается из WebView после проверки подписки; без этого boot/tile не стартуют прокси. */
    public static final String PREF_PROXY_ALLOWED_BY_SUBSCRIPTION = "proxy_allowed_by_subscription";
    public static final String SECRET_FILENAME = "tgws_proxy_secret.hex";
    public static final int PROXY_PORT = 1443;

    private ProxyControl() {}

    public static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    /** Trial или активная оплата — иначе фоновый запуск (перезагрузка, плитка) отключён. */
    public static boolean isProxyAllowedBySubscription(Context context) {
        return prefs(context).getBoolean(PREF_PROXY_ALLOWED_BY_SUBSCRIPTION, false);
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
        if (!isProxyAllowedBySubscription(context)) {
            return false;
        }
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

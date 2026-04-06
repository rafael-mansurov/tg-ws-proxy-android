package unofficial.tgws.tgwsproxy;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.Locale;

public final class ProxyControl {
    public static final String PREFS_NAME = "tgws_proxy_prefs";
    public static final String PREF_AUTOSTART_ON_BOOT = "autostart_on_boot";
    public static final String SECRET_FILENAME = "tgws_proxy_secret.hex";
    public static final int PROXY_PORT = 1443;

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

        String fgText = "Прокси 127.0.0.1:" + PROXY_PORT + " · нажми, чтобы открыть приложение";
        try {
            JSONObject payload = new JSONObject();
            payload.put("secret", secret);
            ServiceProxy.start(context, "", "TG WS Proxy", fgText, payload.toString());
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }
}

package unofficial.tgws.tgwsproxy;

import android.app.Activity;
import android.net.Uri;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.widget.Toast;

import androidx.core.app.ShareCompat;
import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * WebView → нативный шаринг. HTTP POST /api/share из JS иногда даёт ok:false (jnius/потоки);
 * мост вызывается с потока WebView и переносит работу на UI-активность.
 */
public final class TgwsJsBridge {
    private static final String TAG = "TgwsJsBridge";

    /** Должен совпадать с buildozer p4a.port / APP_SERVING_PORT по умолчанию. */
    private static final int LOCAL_UI_PORT = 8080;

    private static final String SHARE_BODY =
            "TG WS Proxy — прокси для Telegram\n"
                    + "Работает локально на телефоне, без серверов и регистрации.\n\n"
                    + "https://github.com/rafael-mansurov/tg-ws-proxy-android/releases/"
                    + "download/latest-apk/tg-ws-proxy-release.apk";

    private final Activity activity;

    public TgwsJsBridge(Activity activity) {
        this.activity = activity;
    }

    @JavascriptInterface
    public void shareApp() {
        activity.runOnUiThread(
                () -> {
                    if (tryShareWithCover()) {
                        return;
                    }
                    if (tryShareTextOnly()) {
                        return;
                    }
                    Toast.makeText(
                                    activity,
                                    "Не удалось открыть «Поделиться»",
                                    Toast.LENGTH_LONG)
                            .show();
                });
    }

    /**
     * Картинка + подпись. Байты обложки: files/app/cover.jpg, поиск по дереву app, иначе GET с
     * локального UI (как fetch('/cover.jpg') в WebView). Telegram без валидного потока показывает
     * только текст — поэтому сначала гарантируем JPEG в cache + ShareCompat.
     */
    private boolean tryShareWithCover() {
        File shareDir = new File(activity.getCacheDir(), "share");
        if (!shareDir.isDirectory() && !shareDir.mkdirs()) {
            Log.w(TAG, "share cache dir mkdirs failed");
        }
        File cacheCopy = new File(shareDir, "tgws-cover.jpg");
        if (!fillCoverCacheFile(cacheCopy) || !looksLikeJpeg(cacheCopy)) {
            Log.w(TAG, "no usable cover.jpg for share (file + loopback)");
            return false;
        }

        String authority = activity.getPackageName() + ".tgws.share";
        try {
            Uri uri = FileProvider.getUriForFile(activity, authority, cacheCopy);
            new ShareCompat.IntentBuilder(activity)
                    .setType("image/jpeg")
                    .setStream(uri)
                    .setText(SHARE_BODY)
                    .setSubject("TG WS Proxy")
                    .setChooserTitle("Поделиться")
                    .startChooser();
            return true;
        } catch (Exception e) {
            Log.w(TAG, "share image+caption failed, try image only", e);
            try {
                Uri uri = FileProvider.getUriForFile(activity, authority, cacheCopy);
                new ShareCompat.IntentBuilder(activity)
                        .setType("image/jpeg")
                        .setStream(uri)
                        .setChooserTitle("Поделиться")
                        .startChooser();
                return true;
            } catch (Exception e2) {
                Log.w(TAG, "share image only failed", e2);
                return false;
            }
        }
    }

    private boolean fillCoverCacheFile(File dst) {
        File appRoot = new File(activity.getFilesDir(), "app");
        File direct = new File(appRoot, "cover.jpg");
        if (direct.isFile() && tryCopyTo(direct, dst)) {
            return true;
        }
        File nested = findCoverJpegUnder(appRoot, 6);
        if (nested != null && tryCopyTo(nested, dst)) {
            return true;
        }
        return downloadCoverFromLoopback(dst);
    }

    private static File findCoverJpegUnder(File dir, int maxDepth) {
        if (maxDepth < 0 || dir == null || !dir.isDirectory()) {
            return null;
        }
        File[] kids = dir.listFiles();
        if (kids == null) {
            return null;
        }
        for (File f : kids) {
            if (f.isFile() && f.getName().equalsIgnoreCase("cover.jpg")) {
                return f;
            }
        }
        for (File f : kids) {
            if (f.isDirectory()) {
                File r = findCoverJpegUnder(f, maxDepth - 1);
                if (r != null) {
                    return r;
                }
            }
        }
        return null;
    }

    private static boolean tryCopyTo(File src, File dst) {
        try {
            copyFileOrThrow(src, dst);
            return dst.length() > 0;
        } catch (IOException e) {
            return false;
        }
    }

    private boolean downloadCoverFromLoopback(File dst) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL("http://127.0.0.1:" + LOCAL_UI_PORT + "/cover.jpg");
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(12000);
            conn.setInstanceFollowRedirects(true);
            if (conn.getResponseCode() != HttpURLConnection.HTTP_OK) {
                Log.w(TAG, "loopback cover HTTP " + conn.getResponseCode());
                return false;
            }
            try (InputStream in = conn.getInputStream();
                    FileOutputStream out = new FileOutputStream(dst)) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0) {
                    out.write(buf, 0, n);
                }
            }
            return dst.length() > 0;
        } catch (Exception e) {
            Log.w(TAG, "loopback cover download", e);
            return false;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static boolean looksLikeJpeg(File f) {
        if (f == null || f.length() < 2) {
            return false;
        }
        try (FileInputStream in = new FileInputStream(f)) {
            int a = in.read();
            int b = in.read();
            return a == 0xff && b == 0xd8;
        } catch (IOException e) {
            return false;
        }
    }

    private static void copyFileOrThrow(File src, File dst) throws IOException {
        try (FileInputStream in = new FileInputStream(src);
                FileOutputStream out = new FileOutputStream(dst)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
            }
        }
    }

    private boolean tryShareTextOnly() {
        try {
            new ShareCompat.IntentBuilder(activity)
                    .setType("text/plain")
                    .setText(SHARE_BODY)
                    .setSubject("TG WS Proxy")
                    .setChooserTitle("Поделиться")
                    .startChooser();
            return true;
        } catch (Exception e) {
            Log.e(TAG, "shareApp text failed", e);
            return false;
        }
    }
}

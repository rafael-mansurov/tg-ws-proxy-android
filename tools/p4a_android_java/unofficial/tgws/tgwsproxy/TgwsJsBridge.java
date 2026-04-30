package unofficial.tgws.tgwsproxy;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
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
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Scanner;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * WebView → нативный шаринг. HTTP POST /api/share из JS иногда даёт ok:false (jnius/потоки);
 * мост вызывается с потока WebView и переносит работу на UI-активность.
 */
public final class TgwsJsBridge {
    private static final String TAG = "TgwsJsBridge";

    private static final Pattern SERVE_PORT_JSON =
            Pattern.compile("\"serve_port\"\\s*:\\s*(\\d+)");

    private static final String SHARE_BODY =
            "TG WS Proxy — бесплатный прокси для Telegram\n\n"
                    + "Скачать файл:\n"
                    + "https://github.com/rafael-mansurov/tg-ws-proxy-android/releases/"
                    + "download/latest-apk/tg-ws-proxy-release.apk";

    private final Activity activity;

    public TgwsJsBridge(Activity activity) {
        this.activity = activity;
    }

    /** Открыть URL в системном браузере, не уводя WebView со страницы приложения. */
    @JavascriptInterface
    public void openUrl(String url) {
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            activity.startActivity(i);
        } catch (Exception e) {
            Log.e(TAG, "openUrl failed: " + url, e);
        }
    }

    @JavascriptInterface
    public void shareApp() {
        shareAppWithPort(0);
    }

    /**
     * @param portHint порт UI-сервера (как у {@code location.port} в WebView); 0 — авто через
     *     /api/version.
     */
    @JavascriptInterface
    public void shareAppWithPort(int portHint) {
        activity.runOnUiThread(
                () -> {
                    if (tryShareWithCover(portHint)) {
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

    private boolean tryShareWithCover(int portHint) {
        File shareDir = new File(activity.getCacheDir(), "share");
        if (!shareDir.isDirectory() && !shareDir.mkdirs()) {
            Log.w(TAG, "share cache dir mkdirs failed");
        }
        File cacheCopy = new File(shareDir, "tgws-cover.jpg");
        if (!fillCoverCacheFile(cacheCopy, portHint) || !looksLikeJpeg(cacheCopy)) {
            Log.w(TAG, "no usable cover.jpg for share (file + loopback)");
            return false;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            if (tryShareJpegViaMediaStore(cacheCopy)) {
                return true;
            }
        }

        String authority = activity.getPackageName() + ".tgws.share";
        try {
            Uri uri = FileProvider.getUriForFile(activity, authority, cacheCopy);
            if (shareImageChooser(uri, true)) {
                return true;
            }
        } catch (Exception e) {
            Log.w(TAG, "FileProvider share failed", e);
        }
        try {
            Uri uri = FileProvider.getUriForFile(activity, authority, cacheCopy);
            return shareImageChooser(uri, false);
        } catch (Exception e2) {
            Log.w(TAG, "image-only share failed", e2);
            return false;
        }
    }

    /**
     * Telegram часто теряет поток FileProvider через chooser без {@link ClipData#newRawUri};
     * MediaStore content:// обычно открывается как фото.
     */
    private boolean tryShareJpegViaMediaStore(File jpegFile) {
        try {
            ContentResolver resolver = activity.getContentResolver();
            String name = "tgws-share-" + System.currentTimeMillis() + ".jpg";
            ContentValues values = new ContentValues();
            values.put(MediaStore.Images.Media.DISPLAY_NAME, name);
            values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
            values.put(
                    MediaStore.Images.Media.RELATIVE_PATH,
                    Environment.DIRECTORY_PICTURES + "/TGWSProxy");
            values.put(MediaStore.Images.Media.IS_PENDING, 1);
            Uri collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
            Uri mediaUri = resolver.insert(collection, values);
            if (mediaUri == null) {
                return false;
            }
            try (InputStream in = new FileInputStream(jpegFile);
                    OutputStream out = resolver.openOutputStream(mediaUri)) {
                if (out == null) {
                    resolver.delete(mediaUri, null, null);
                    return false;
                }
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0) {
                    out.write(buf, 0, n);
                }
            } catch (IOException e) {
                try {
                    resolver.delete(mediaUri, null, null);
                } catch (Exception ignored) {
                }
                Log.w(TAG, "MediaStore copy for share", e);
                return false;
            }
            values.clear();
            values.put(MediaStore.Images.Media.IS_PENDING, 0);
            resolver.update(mediaUri, values, null, null);
            return shareImageChooser(mediaUri, true);
        } catch (Exception e) {
            Log.w(TAG, "MediaStore share path failed", e);
            return false;
        }
    }

    private boolean shareImageChooser(Uri streamUri, boolean withCaption) {
        try {
            Intent send = new Intent(Intent.ACTION_SEND);
            send.setType("image/jpeg");
            send.putExtra(Intent.EXTRA_STREAM, streamUri);
            if (withCaption) {
                send.putExtra(Intent.EXTRA_TEXT, SHARE_BODY);
                send.putExtra(Intent.EXTRA_SUBJECT, "TG WS Proxy");
            }
            send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            send.setClipData(ClipData.newRawUri("", streamUri));
            Intent chooser = Intent.createChooser(send, "Поделиться");
            chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            activity.startActivity(chooser);
            return true;
        } catch (Exception e) {
            Log.w(TAG, "shareImageChooser", e);
            return false;
        }
    }

    private boolean fillCoverCacheFile(File dst, int portHint) {
        File appRoot = new File(activity.getFilesDir(), "app");
        File direct = new File(appRoot, "cover.jpg");
        if (direct.isFile() && tryCopyTo(direct, dst)) {
            return true;
        }
        File nested = findCoverJpegUnder(appRoot, 6);
        if (nested != null && tryCopyTo(nested, dst)) {
            return true;
        }
        return downloadCoverFromLoopback(dst, portHint);
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

    private int resolveServePort() {
        int[] guesses = new int[] {8080, 8081, 8082, 8765, 5000};
        for (int g : guesses) {
            String body = httpGetBody("http://127.0.0.1:" + g + "/api/version");
            if (body == null || body.isEmpty()) {
                continue;
            }
            Matcher m = SERVE_PORT_JSON.matcher(body);
            if (m.find()) {
                try {
                    int p = Integer.parseInt(m.group(1));
                    if (p > 0 && p < 65536) {
                        return p;
                    }
                } catch (NumberFormatException ignored) {
                }
            }
            return g;
        }
        return 8080;
    }

    private static String httpGetBody(String urlString) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(urlString);
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(2500);
            conn.setReadTimeout(4000);
            if (conn.getResponseCode() != HttpURLConnection.HTTP_OK) {
                return null;
            }
            try (InputStream in = conn.getInputStream();
                    Scanner s = new Scanner(in, "UTF-8").useDelimiter("\\A")) {
                return s.hasNext() ? s.next() : "";
            }
        } catch (Exception e) {
            return null;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private boolean downloadCoverFromLoopback(File dst, int portHint) {
        int port = portHint > 0 && portHint < 65536 ? portHint : resolveServePort();
        HttpURLConnection conn = null;
        try {
            URL url = new URL("http://127.0.0.1:" + port + "/cover.jpg");
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(12000);
            conn.setInstanceFollowRedirects(true);
            if (conn.getResponseCode() != HttpURLConnection.HTTP_OK) {
                Log.w(TAG, "loopback cover HTTP " + conn.getResponseCode() + " port=" + port);
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
            Log.w(TAG, "loopback cover download port=" + port, e);
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

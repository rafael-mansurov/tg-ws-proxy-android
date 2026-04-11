package unofficial.tgws.tgwsproxy;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
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

/**
 * WebView → нативный шаринг. HTTP POST /api/share из JS иногда даёт ok:false (jnius/потоки);
 * мост вызывается с потока WebView и переносит работу на UI-активность.
 */
public final class TgwsJsBridge {
    private static final String TAG = "TgwsJsBridge";

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

    /** Картинка + подпись (ссылка в тексте). Копия в cache + явный ClipData — иначе Telegram часто не вставляет фото. */
    private boolean tryShareWithCover() {
        try {
            String authority = activity.getPackageName() + ".tgws.share";
            File cover = new File(new File(activity.getFilesDir(), "app"), "cover.jpg");
            if (!cover.isFile()) {
                return false;
            }
            File shareDir = new File(activity.getCacheDir(), "share");
            if (!shareDir.isDirectory() && !shareDir.mkdirs()) {
                Log.w(TAG, "share cache dir mkdirs failed");
            }
            File cacheCopy = new File(shareDir, "tgws-cover.jpg");
            copyFileOrThrow(cover, cacheCopy);

            Uri uri = FileProvider.getUriForFile(activity, authority, cacheCopy);
            Intent send = new Intent(Intent.ACTION_SEND);
            send.setType("image/*");
            send.putExtra(Intent.EXTRA_STREAM, uri);
            send.putExtra(Intent.EXTRA_TEXT, SHARE_BODY);
            send.putExtra(Intent.EXTRA_SUBJECT, "TG WS Proxy");
            send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            send.setClipData(ClipData.newUri(activity.getContentResolver(), "cover", uri));

            Intent chooser = Intent.createChooser(send, "Поделиться");
            chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            activity.startActivity(chooser);
            return true;
        } catch (Exception e) {
            Log.w(TAG, "share with cover failed, falling back to text", e);
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

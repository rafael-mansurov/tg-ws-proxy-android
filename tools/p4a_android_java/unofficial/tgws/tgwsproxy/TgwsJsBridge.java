package unofficial.tgws.tgwsproxy;

import android.app.Activity;
import android.net.Uri;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.widget.Toast;

import androidx.core.app.ShareCompat;
import androidx.core.content.FileProvider;

import java.io.File;

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

    /** Картинка + текст; при любой ошибке — false, чтобы открыть только текст. */
    private boolean tryShareWithCover() {
        try {
            String authority = activity.getPackageName() + ".tgws.share";
            File cover = new File(new File(activity.getFilesDir(), "app"), "cover.jpg");
            if (!cover.isFile()) {
                return false;
            }
            Uri uri = FileProvider.getUriForFile(activity, authority, cover);
            new ShareCompat.IntentBuilder(activity)
                    .setType("image/jpeg")
                    .setStream(uri)
                    .setText(SHARE_BODY)
                    .setSubject("TG WS Proxy")
                    .setChooserTitle("Поделиться")
                    .startChooser();
            return true;
        } catch (Exception e) {
            Log.w(TAG, "share with cover failed, falling back to text", e);
            return false;
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

package unofficial.tgws.tgwsproxy;

import android.content.Context;
import android.content.Intent;
import android.os.Build;
import org.kivy.android.PythonService;

public class ServiceProxy extends PythonService {

    @Override
    public int startType() {
        return START_NOT_STICKY;
    }

    @Override
    protected int getServiceId() {
        return 1;
    }

    @Override
    protected Intent getThisDefaultIntent(Context ctx, String pythonServiceArgument) {
        return ServiceProxy.getDefaultIntent(ctx, "", "", "", pythonServiceArgument);
    }

    static public Intent getDefaultIntent(Context ctx, String smallIconName,
                                          String contentTitle, String contentText,
                                          String pythonServiceArgument) {
        String argument = ctx.getFilesDir().getAbsolutePath() + "/app";
        Intent intent = new Intent(ctx, ServiceProxy.class);
        intent.putExtra("androidPrivate", ctx.getFilesDir().getAbsolutePath());
        intent.putExtra("androidArgument", argument);
        intent.putExtra("serviceTitle", "TG WS Proxy");
        intent.putExtra("serviceEntrypoint", "services/proxy_service.py");
        intent.putExtra("pythonName", "proxy");
        intent.putExtra("serviceStartAsForeground", "true");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonServiceArgument", pythonServiceArgument);
        intent.putExtra("smallIconName", smallIconName);
        intent.putExtra("contentTitle", contentTitle);
        intent.putExtra("contentText", contentText);
        return intent;
    }

    static public void start(Context ctx, String pythonServiceArgument) {
        start(ctx, "", "TG WS Proxy", "Proxy", pythonServiceArgument);
    }

    static public void start(Context ctx, String smallIconName, String contentTitle,
                             String contentText, String pythonServiceArgument) {
        Intent intent = getDefaultIntent(ctx, smallIconName, contentTitle,
                                         contentText, pythonServiceArgument);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            ctx.startForegroundService(intent);
        } else {
            ctx.startService(intent);
        }
    }

    static public void stop(Context ctx) {
        Intent intent = new Intent(ctx, ServiceProxy.class);
        ctx.stopService(intent);
    }
}

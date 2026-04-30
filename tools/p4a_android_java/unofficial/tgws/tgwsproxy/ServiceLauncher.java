package unofficial.tgws.tgwsproxy;

import android.content.Context;
import android.content.Intent;
import android.os.Build;

/**
 * Static helpers to start/stop ServiceProxy.
 *
 * Lives in a separate class so p4a's code-generator (which emits ServiceProxy.java)
 * never overwrites or conflicts with this file.  Python calls ServiceLauncher
 * instead of ServiceProxy.start/stop directly.
 */
public final class ServiceLauncher {
    private ServiceLauncher() {}

    public static void start(Context ctx, String smallIconName, String contentTitle,
                             String contentText, String pythonServiceArgument) {
        String privateDir = ctx.getFilesDir().getAbsolutePath();
        String argument   = privateDir + "/app";
        Intent intent = new Intent(ctx, ServiceProxy.class);
        intent.putExtra("androidPrivate",          privateDir);
        intent.putExtra("androidArgument",         argument);
        intent.putExtra("serviceTitle",            "TG WS Proxy");
        intent.putExtra("serviceEntrypoint",       "services/proxy_service.py");
        intent.putExtra("pythonName",              "proxy");
        intent.putExtra("serviceStartAsForeground","true");
        intent.putExtra("pythonHome",              argument);
        intent.putExtra("pythonPath",              argument + ":" + argument + "/lib");
        intent.putExtra("pythonServiceArgument",   pythonServiceArgument);
        intent.putExtra("smallIconName",           smallIconName);
        intent.putExtra("contentTitle",            contentTitle);
        intent.putExtra("contentText",             contentText);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            ctx.startForegroundService(intent);
        } else {
            ctx.startService(intent);
        }
    }

    public static void stop(Context ctx) {
        ctx.stopService(new Intent(ctx, ServiceProxy.class));
    }
}

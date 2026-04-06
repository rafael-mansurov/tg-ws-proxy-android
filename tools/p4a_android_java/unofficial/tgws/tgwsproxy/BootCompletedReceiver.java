package unofficial.tgws.tgwsproxy;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootCompletedReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (context == null || intent == null) {
            return;
        }
        String action = intent.getAction();
        if (Intent.ACTION_BOOT_COMPLETED.equals(action)
            || Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)
            || Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action)) {
            if (ProxyControl.isAutostartEnabled(context)) {
                ProxyControl.startProxy(context);
            }
        }
    }
}

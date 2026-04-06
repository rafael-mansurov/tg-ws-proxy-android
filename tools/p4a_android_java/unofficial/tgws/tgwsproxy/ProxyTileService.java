package unofficial.tgws.tgwsproxy;

import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

public class ProxyTileService extends TileService {
    private void refreshTile() {
        Tile tile = getQsTile();
        if (tile == null) {
            return;
        }
        boolean running = ProxyControl.isProxyRunning();
        tile.setState(running ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE);
        tile.setLabel(running ? "TG Proxy: ON" : "TG Proxy: OFF");
        tile.updateTile();
    }

    @Override
    public void onStartListening() {
        super.onStartListening();
        refreshTile();
    }

    @Override
    public void onTileAdded() {
        super.onTileAdded();
        refreshTile();
    }

    @Override
    public void onClick() {
        super.onClick();
        if (ProxyControl.isProxyRunning()) {
            ProxyControl.stopProxy(this);
        } else {
            ProxyControl.startProxy(this);
        }
        refreshTile();
    }
}

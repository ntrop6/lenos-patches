package org.lenos.opsec;

import android.bluetooth.BluetoothAdapter;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.net.ConnectivityManager;
import android.net.wifi.WifiManager;
import android.os.UserHandle;
import android.provider.Settings;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/**
 * One-tap radio kill switch. Airplane mode is the authoritative switch; Wi-Fi
 * and Bluetooth are switched off first so they cannot linger after the tile
 * turns airplane mode on.
 */
public class OfflineTileService extends TileService {
    @Override
    public void onStartListening() {
        super.onStartListening();
        updateTile();
    }

    @Override
    public void onClick() {
        final boolean enable = !isAirplaneModeOn();
        if (enable) {
            turnOffRadios();
        }
        setAirplaneMode(enable);
        updateTile();
    }

    private boolean isAirplaneModeOn() {
        return Settings.Global.getInt(getContentResolver(),
                Settings.Global.AIRPLANE_MODE_ON, 0) != 0;
    }

    private void setAirplaneMode(boolean enable) {
        try {
            final ConnectivityManager cm = getSystemService(ConnectivityManager.class);
            if (cm == null) {
                throw new IllegalStateException("no ConnectivityManager");
            }
            cm.setAirplaneMode(enable);
        } catch (Throwable t) {
            Settings.Global.putInt(getContentResolver(),
                    Settings.Global.AIRPLANE_MODE_ON, enable ? 1 : 0);
            final Intent intent = new Intent(Intent.ACTION_AIRPLANE_MODE_CHANGED);
            intent.putExtra("state", enable);
            sendBroadcastAsUser(intent, UserHandle.ALL);
        }
    }

    private void turnOffRadios() {
        final WifiManager wifi = getSystemService(WifiManager.class);
        if (wifi != null && wifi.isWifiEnabled()) {
            wifi.setWifiEnabled(false);
        }
        final BluetoothAdapter bluetooth = BluetoothAdapter.getDefaultAdapter();
        if (bluetooth != null && bluetooth.isEnabled()) {
            try {
                bluetooth.disable();
            } catch (SecurityException e) {
                // The platform signature grants BLUETOOTH_PRIVILEGED; if the
                // runtime BLUETOOTH_CONNECT grant is missing, do not crash the
                // tile. Airplane mode still cuts the radio.
            }
        }
    }

    private void updateTile() {
        final Tile tile = getQsTile();
        if (tile == null) {
            return;
        }
        final boolean on = isAirplaneModeOn();
        tile.setState(on ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE);
        tile.setLabel(getString(R.string.offline_tile_label));
        tile.setContentDescription(getString(on ? R.string.offline_tile_on
                : R.string.offline_tile_off));
        tile.setIcon(Icon.createWithResource(this, R.drawable.ic_offline));
        tile.updateTile();
    }
}

"""GrapheneOS radio auto-off timers (Wi-Fi and Bluetooth).

Ported from GrapheneOS:

* ``DelayedConditionalAction`` — schedules an alarm after a user-configured
  delay and reschedules it when the relevant state changes.
* ``WifiAutoOff`` — turns Wi-Fi off when it is enabled but not connected for
  the configured timeout.
* ``BluetoothAutoOff`` — turns Bluetooth off when the adapter is on with no
  connected (including LE/GATT) device for the configured timeout.
* ``SystemServerExt`` — trimmed lenOS wiring, called from ``SystemServer``.

The ExtSettings keys (``Settings.Global.wifi_off_timeout`` /
``bluetooth_off_timeout``) were already seeded by ``frameworks_base/0006``;
this patch adds the enforcement. The Settings screen uses a plain
``ListPreference`` instead of GrapheneOS's RadioButtonPickerFragment2
sub-screen (documented UI substitution).
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestRadioAutoOff(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0020-lenos-radio-auto-off.patch"]

    EXT = "services/core/java/com/android/server/ext/"
    SSE = EXT + "SystemServerExt.java"
    DCA = EXT + "DelayedConditionalAction.java"
    WIFI = EXT + "WifiAutoOff.java"
    BT = EXT + "BluetoothAutoOff.java"
    SYSTEM_SERVER = "services/java/com/android/server/SystemServer.java"

    def test_wired_from_system_server(self):
        self.assert_contains(
            self.SYSTEM_SERVER,
            "com.android.server.ext.SystemServerExt.init(mSystemContext, mPackageManagerService);")
        self.assert_contains(
            self.SSE,
            "WifiAutoOff.maybeInit(this);",
            "BluetoothAutoOff.maybeInit(this);",
            "bgHandler = BackgroundThread.getHandler();")

    def test_alarm_infrastructure(self):
        self.assert_contains(
            self.DCA,
            "public abstract class DelayedConditionalAction",
            "alarmManager.setExact(AlarmManager.ELAPSED_REALTIME_WAKEUP, triggerAt,",
            "setting.registerObserver(sse.context, handler, s -> update());",
            "protected abstract boolean shouldScheduleAlarm();")

    def test_wifi_logic(self):
        self.assert_contains(
            self.WIFI,
            "class WifiAutoOff extends DelayedConditionalAction implements "
            "WifiNetworkStateChangedListener",
            "ExtSettings.WIFI_AUTO_OFF",
            "wifiManager.setWifiEnabled(false);",
            "wifiManager.addWifiNetworkStateChangedListener(new HandlerExecutor(handler), this);",
            "WIFI_NETWORK_STATUS_OBTAINING_IPADDR")

    def test_bluetooth_logic(self):
        self.assert_contains(
            self.BT,
            "class BluetoothAutoOff extends DelayedConditionalAction",
            "ExtSettings.BLUETOOTH_AUTO_OFF",
            "adapter.disable(true);",
            "manager.getConnectedDevices(BluetoothProfile.GATT)",
            "adapter.isLeEnabled()",
            "registerReceiverForAllUsers")

    def test_syntax(self):
        for f in (self.SSE, self.DCA, self.WIFI, self.BT, self.SYSTEM_SERVER):
            self.assert_java_syntax(f)


class TestAutoOffSettingsUi(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = ["0001-lenos-ext-settings-ui.patch"]

    XML = "res/xml/more_security_privacy_settings.xml"
    FRAGMENT = "src/com/android/settings/safetycenter/MoreSecurityPrivacyFragment.java"
    CTRL = "src/com/android/settings/ext/AutoOffPrefController.java"
    SETTING = "src/com/android/settings/ext/AutoOffSetting.java"
    STRINGS = "res/values/strings_ext.xml"

    def test_rows_exist(self):
        self.assert_contains(
            self.XML,
            'android:key="wifi_auto_off"',
            'android:key="bluetooth_auto_off"',
            "@string/wifi_auto_off_title",
            "@string/bluetooth_auto_off_title")

    def test_controllers_registered_with_gos_keys(self):
        self.assert_contains(
            self.FRAGMENT,
            "new AutoOffPrefController(context, \"wifi_auto_off\",",
            "ExtSettings.WIFI_AUTO_OFF, PackageManager.FEATURE_WIFI",
            "new AutoOffPrefController(context, \"bluetooth_auto_off\",",
            "ExtSettings.BLUETOOTH_AUTO_OFF, PackageManager.FEATURE_BLUETOOTH")

    def test_controller_persists_millis_values(self):
        self.assert_contains(
            self.CTRL,
            "setting.put(mContext, value)",
            "DateUtils.formatDuration(value)",
            "R.string.auto_off_never",
            "ExtSettingControllerHelper.getGlobalSettingAvailability(mContext)")
        self.assert_contains(
            self.SETTING,
            "15_000, 30_000,",
            "8 * 60 * 60_000,")

    def test_strings(self):
        self.assert_contains(
            self.STRINGS,
            '<string name="auto_off_never">Never</string>',
            "Turn off Wi-Fi automatically",
            "Turn off Bluetooth automatically")

    def test_syntax(self):
        self.assert_java_syntax(self.CTRL)
        self.assert_java_syntax(self.SETTING)


if __name__ == "__main__":
    unittest.main()

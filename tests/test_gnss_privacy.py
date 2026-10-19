"""GrapheneOS GNSS network-assistance privacy (SUPL and PSDS).

Ported from GrapheneOS:

* ``core/java/android/ext/settings/GnssSettings.java`` — the SUPL and PSDS
  settings. Keys and numeric values match GrapheneOS
  (``Settings.Global.GNSS_SUPL`` = ``force_disable_supl`` and
  ``Settings.Global.GNSS_PSDS_STANDARD`` = ``psds_server``).
* ``GnssConfiguration.applyConfigOverrides`` — applies the settings after all
  other property sources (carrier config, debug files) so they cannot be
  silently re-enabled.
* ``GnssLocationProvider`` — reacts to setting changes at runtime and refuses
  PSDS downloads when PSDS is disabled.

Documented deviations from GrapheneOS:

* GrapheneOS defaults SUPL and PSDS to its own privacy proxies and lets users
  choose "GrapheneOS proxy"; lenOS has no such infrastructure, so only
  "Off" and "Standard server" are offered.
* Both settings default to **Off**. With no proxy, disabling is the only
  privacy-preserving default; the user can opt back into the standard servers.
* The location-screen rows live in their own "Network assistance" category
  instead of GrapheneOS's advanced category, which LineageOS removes when the
  new recent-location UI is disabled.

The legacy device-level ``device_nothing_asteroids/0003`` patch (empty
``gps.supl_host``) was removed: the framework setting now owns SUPL, so the
"Standard server" choice is not silently defeated by an empty host.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestGnssFramework(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = [
        "0006-lenos-ext-settings.patch",
        "0021-lenos-gnss-network-assistance.patch",
    ]

    GNSS = "core/java/android/ext/settings/GnssSettings.java"
    CONFIG = ("services/core/java/com/android/server/location/gnss/"
              "GnssConfiguration.java")
    PROVIDER = ("services/core/java/com/android/server/location/gnss/"
                "GnssLocationProvider.java")
    SETTINGS = "core/java/android/provider/Settings.java"

    def test_settings_keys_match_grapheneos(self):
        self.assert_contains(
            self.SETTINGS,
            'String GNSS_SUPL = "force_disable_supl"',
            'String GNSS_PSDS_STANDARD = "psds_server"')

    def test_gnss_settings_default_off(self):
        self.assert_contains(
            self.GNSS,
            "SUPL_SERVER_STANDARD = 0",
            "SUPL_DISABLED = 1",
            "PSDS_SERVER_STANDARD = 1",
            "PSDS_DISABLED = 2",
            "SUPL_SETTING = new IntSetting(",
            "STANDARD_PSDS_SETTING = new IntSetting(",
            "SUPL_DISABLED, // lenOS: disabled by default",
            "PSDS_DISABLED, // lenOS: disabled by default")

    def test_overrides_are_applied_last(self):
        text = self.text(self.CONFIG)
        debug = text.index("loadPropertiesFromGpsDebugConfig(mProperties, "
                           "DEBUG_PROPERTIES_SYSTEM_FILE);")
        apply_at = text.index("applyConfigOverrides(mContext, mProperties);")
        log_at = text.index("logConfigurations();")
        self.assertLess(debug, apply_at)
        self.assertLess(apply_at, log_at)

    def test_supl_disabled_clears_server_properties(self):
        self.assert_contains(
            self.CONFIG,
            'props.setProperty(CONFIG_SUPL_MODE, "0");',
            "props.remove(CONFIG_SUPL_HOST);",
            "props.remove(CONFIG_SUPL_PORT);")

    def test_psds_disabled_clears_servers_and_periodic_download(self):
        self.assert_contains(
            self.CONFIG,
            "private static void clearPsdsServerProps(Properties props)",
            "CONFIG_LONGTERM_PSDS_SERVER_1",
            "CONFIG_NORMAL_PSDS_SERVER",
            "CONFIG_REALTIME_PSDS_SERVER",
            'props.setProperty(CONFIG_ENABLE_PSDS_PERIODIC_DOWNLOAD, "0");')

    def test_provider_observes_settings_and_gates_downloads(self):
        self.assert_contains(
            self.PROVIDER,
            "GnssSettings.SUPL_SETTING.registerObserver(",
            "GnssSettings.STANDARD_PSDS_SETTING.registerObserver(",
            "private boolean isPsdsEnabled()",
            "if (mSupportsPsds && isPsdsEnabled())",
            "if (!isPsdsEnabled()) {")

    def test_force_psds_injection_is_gated(self):
        self.assert_contains(
            self.PROVIDER,
            '"force_psds_injection".equals(command)) {\n'
            "            if (mSupportsPsds) {")

    def test_syntax(self):
        for f in (self.GNSS, self.CONFIG, self.PROVIDER):
            self.assert_java_syntax(f)


class TestGnssSettingsUi(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = ["0001-lenos-ext-settings-ui.patch"]

    BASE = "src/com/android/settings/ext/IntSettingListPrefController.java"
    SUPL = "src/com/android/settings/ext/GnssSuplPrefController.java"
    PSDS = "src/com/android/settings/ext/GnssPsdsPrefController.java"
    STRINGS = "res/values/strings_ext.xml"
    LOCATION = "res/xml/location_settings.xml"

    def test_controllers(self):
        self.assert_contains(
            self.SUPL,
            "GnssSettings.SUPL_SETTING",
            "PackageManager.FEATURE_LOCATION_GPS",
            "R.string.supl_disabled",
            "R.string.supl_enabled_standard_server")
        self.assert_contains(
            self.PSDS,
            "GnssSettings.STANDARD_PSDS_SETTING",
            "R.string.psds_disabled",
            "R.string.psds_enabled_standard_server")

    def test_list_controller_is_system_user_only(self):
        self.assert_contains(
            self.BASE,
            "ExtSettingControllerHelper.getGlobalSettingAvailability(mContext)",
            "setting.put(mContext, value)",
            "preference.setPersistent(false)")

    def test_location_rows(self):
        self.assert_contains(
            self.LOCATION,
            'android:key="gnss_supl"',
            'android:key="gnss_psds"',
            'settings:controller="com.android.settings.ext.'
            'GnssSuplPrefController"',
            'settings:controller="com.android.settings.ext.'
            'GnssPsdsPrefController"',
            "@string/gnss_privacy_category_title")

    def test_strings(self):
        self.assert_contains(
            self.STRINGS,
            '<string name="gnss_privacy_category_title">Network assistance</string>',
            '<string name="pref_gnss_supl_title">'
            "Secure User Plane Location (SUPL)</string>",
            '<string name="pref_gnss_psds_title">'
            "Predicted Satellite Data Service (PSDS)</string>",
            '<string name="supl_disabled">Off</string>',
            '<string name="psds_disabled">Off</string>',
            '<string name="supl_enabled_standard_server">'
            "Standard server</string>",
            '<string name="psds_enabled_standard_server">'
            "Standard server</string>")

    def test_syntax(self):
        for f in (self.BASE, self.SUPL, self.PSDS):
            self.assert_java_syntax(f)

    def test_xml(self):
        self.assert_xml(self.STRINGS)
        self.assert_xml(self.LOCATION)


if __name__ == "__main__":
    unittest.main()

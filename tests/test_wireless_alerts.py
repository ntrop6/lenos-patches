"""Wireless alerts optional (see docs/features.md).

Feature contract (GrapheneOS-faithful port of two commits on
``platform_packages_apps_CellBroadcastReceiver``):

* "allow toggling presidential alerts" (`11e3a8c`): the presidential alerts
  preference becomes visible and user-controllable — the default
  ``show_presidential_alerts_settings`` flips to true, both preferences
  XMLs drop ``android:enabled="false"`` and use the override summary, the
  alert path calls ``checkAlertConfigEnabled`` with
  ``KEY_ENABLE_CMAS_PRESIDENTIAL_ALERTS`` (default true), the channel
  manager stops setting ``mAlwaysOn``, the CDMA category mapping covers
  the presidential category, and the settings fragment wires the toggle
  into the config service.
* "always allow disabling extreme alerts" (`59d96c7`): Brazil's MCC-724
  forced-on override of ``disable_extreme_alert_settings`` is removed.

All alert types remain *enabled* by default — the change makes them
controllable, not disabled. The legacy
``CellBroadcastSettingsOldFragment`` (pre-S / watch UI path) is left
untouched, exactly as GrapheneOS does.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestWirelessAlertsOptional(LenosPatchTest):
    PROJECT = "packages/apps/CellBroadcastReceiver"
    PATCHES = ["0001-lenos-wireless-alerts-optional.patch"]

    SVCDIR = "src/com/android/cellbroadcastreceiver"

    def test_presidential_settings_visible_and_toggleable(self):
        self.assert_contains("res/values/config.xml",
                             'show_presidential_alerts_settings">true<')
        self.assert_contains(
            "res/values/strings.xml",
            '<string name="enable_cmas_presidential_alerts_summary_override">'
            "National warning messages.</string>")
        # Only the presidential preference had android:enabled="false" before
        # the patch; none of the two files may keep it.
        for pref in ("res/xml/preferences.xml", "res/xml-v31/preferences.xml"):
            self.assert_contains(
                pref,
                "@string/enable_cmas_presidential_alerts_summary_override")
            self.assert_not_contains(pref, 'android:enabled="false"')

    def test_alert_path_honours_the_preference(self):
        svc = f"{self.SVCDIR}/CellBroadcastAlertService.java"
        self.assert_contains(
            svc, "CellBroadcastSettings.KEY_ENABLE_CMAS_PRESIDENTIAL_ALERTS, true")
        self.assert_not_contains(svc, "// always enabled")
        self.assert_java_syntax(svc)

    def test_always_on_channel_flag_is_inert(self):
        cm = f"{self.SVCDIR}/CellBroadcastChannelManager.java"
        # GrapheneOS comments the assignment out (the field/readers stay).
        self.assert_contains(
            cm,
            'case KEY_ALWAYS_ON:\n'
            '                                //if (value.equalsIgnoreCase("true")) {')
        self.assert_java_syntax(cm)

    def test_cdma_category_updates_presidential_pref(self):
        rcv = f"{self.SVCDIR}/CellBroadcastReceiver.java"
        self.assert_contains(
            rcv,
            "case CdmaSmsCbProgramData.CATEGORY_CMAS_PRESIDENTIAL_LEVEL_ALERT:",
            "CATEGORY_CMAS_PRESIDENTIAL_LEVEL_ALERT, false)")
        self.assert_java_syntax(rcv)

    def test_settings_fragment_wiring(self):
        st = f"{self.SVCDIR}/CellBroadcastSettings.java"
        self.assert_contains(
            st,
            "mPresidentialCheckBox.setOnPreferenceChangeListener(startConfigServiceListener);",
            "R.array.cmas_presidential_alerts_channels_range_strings).isEmpty());")
        # Note: the legacy CellBroadcastSettingsOldFragment keeps AOSP's
        # always-on wire-up (same as GrapheneOS), so the stale comment still
        # exists there; only the primary fragment is re-wired.
        self.assert_java_syntax(st)

    def test_brazil_forced_extreme_override_removed(self):
        self.assert_not_contains("res/values-mcc724/config.xml",
                                 "disable_extreme_alert_settings")
        # The base default stays false, so extreme alerts are still on.
        self.assert_contains("res/values/config.xml",
                             '<bool name="disable_extreme_alert_settings">false</bool>')

    def test_resources_well_formed(self):
        for rel in ("res/values/config.xml", "res/values/strings.xml",
                    "res/xml/preferences.xml", "res/xml-v31/preferences.xml",
                    "res/values-mcc724/config.xml"):
            self.assert_xml(rel)


if __name__ == "__main__":
    unittest.main()

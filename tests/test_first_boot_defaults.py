"""lenOS first-boot privacy defaults (frameworks/base SettingsProvider).

Feature contract (see docs/features.md):
* A fresh install seeds hardened defaults for Private DNS, NTP and captive
  portal mode. Wi-Fi privacy defaults (per-network MAC randomization and DHCP
  hostname) are carried by the Wi-Fi module patch, not seeded here.
* The stock (non-lenOS) values stay AOSP-compatible: on a build without the
  lenOS product overlay nothing changes.
* Defaults are only written with INSERT OR IGNORE semantics (first boot); a
  value the user changed is never rewritten.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestFirstBootDefaults(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0002-lenos-first-boot-defaults.patch"]
    DB = "packages/SettingsProvider/src/com/android/providers/settings/DatabaseHelper.java"
    XML = "packages/SettingsProvider/res/values/defaults.xml"

    def test_still_syntactically_valid_java(self):
        self.assert_java_syntax(self.DB)

    def test_xml_is_well_formed(self):
        self.assert_xml(self.XML)

    def test_defaults_are_loaded_from_resources(self):
        self.assert_contains(
            self.DB,
            "R.string.def_lenos_private_dns_mode",
            "R.string.def_lenos_private_dns_specifier",
            "R.string.def_lenos_ntp_server",
            "R.integer.def_lenos_captive_portal_mode",
        )

    def test_correct_settings_namespaces_are_used(self):
        self.assert_contains(
            self.DB,
            "Settings.Global.PRIVATE_DNS_MODE",
            "Settings.Global.PRIVATE_DNS_SPECIFIER",
            "Settings.Global.NTP_SERVER",
            "Settings.Global.CAPTIVE_PORTAL_MODE",
        )

    def test_stock_resources_keep_aosp_behaviour(self):
        self.assert_contains(
            self.XML,
            '<string name="def_lenos_private_dns_mode" translatable="false">opportunistic</string>',
            '<string name="def_lenos_ntp_server" translatable="false">time.android.com</string>',
            '<integer name="def_lenos_captive_portal_mode">1</integer>',
        )

    def test_defaults_are_loaded_on_first_boot_only(self):
        # The loads must sit in loadGlobalSettings and use the INSERT OR IGNORE
        # helper, never a forced overwrite of an existing user choice.
        body = self.text(self.DB)
        idx = body.index("lenOS: privacy-hardening defaults")
        end = body.index("private void loadSetting(SQLiteStatement")
        self.assertNotIn("REPLACE INTO", body[idx:end])
        self.assertNotIn("DELETE FROM", body[idx:end])


if __name__ == "__main__":
    unittest.main()

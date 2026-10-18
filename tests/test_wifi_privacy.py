"""Wi-Fi privacy defaults (packages/modules/Wifi patch, ported from GrapheneOS).

Feature contract (see docs/features.md):
* New Wi-Fi networks default to per-connection (non-persistent) MAC
  randomization: macRandomizationSetting starts at RANDOMIZATION_ALWAYS and
  the framework forces non-persistent randomization for that value. The user
  can still pick any other strategy per network; the default never overrides
  an explicit choice.
* DHCP requests never carry the device hostname by default: a new
  WifiConfiguration has SendDhcpHostname disabled, and only a per-network
  opt-in turns it back on.
* Existing saved networks keep their stored values. The XML tag was renamed
  (SendDhcpHostname -> SendDhcpHostname2) so values written by stock Android
  are ignored and the privacy default applies after the upgrade, matching
  GrapheneOS.
* No global force-flags: the old lenOS Settings.Global clamp is gone.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestWifiPrivacyDefaults(LenosPatchTest):
    PROJECT = "packages/modules/Wifi"
    PATCHES = ["0001-privacy-mac-and-dhcp-defaults.patch"]
    CONF = "framework/java/android/net/wifi/WifiConfiguration.java"
    MANAGER = "service/java/com/android/server/wifi/WifiConfigManager.java"
    UTIL = "service/java/com/android/server/wifi/WifiConfigurationUtil.java"
    XML = "service/java/com/android/server/wifi/util/XmlUtil.java"

    def test_java_still_parses(self):
        for rel in (self.CONF, self.MANAGER, self.UTIL, self.XML):
            self.assert_java_syntax(rel)

    def test_always_constant_is_declared_and_intdefed(self):
        self.assert_contains(
            self.CONF,
            "public static final int RANDOMIZATION_ALWAYS = 100;",
            "RANDOMIZATION_AUTO,\n            RANDOMIZATION_ALWAYS})",
        )

    def test_new_networks_default_to_per_connection_randomization(self):
        self.assert_contains(
            self.CONF,
            "public int macRandomizationSetting = RANDOMIZATION_ALWAYS;",
        )

    def test_always_forces_non_persistent_randomization(self):
        self.assert_contains(
            self.MANAGER,
            "if (config.macRandomizationSetting == WifiConfiguration.RANDOMIZATION_ALWAYS) {\n"
            "            return true;\n"
            "        }",
        )

    def test_saving_a_default_network_is_not_a_randomization_change(self):
        self.assert_contains(
            self.UTIL,
            "return newConfig.macRandomizationSetting != WifiConfiguration.RANDOMIZATION_ALWAYS;",
        )

    def test_dhcp_hostname_defaults_to_off(self):
        self.assert_contains(self.CONF, "private boolean mIsSendDhcpHostnameEnabled;")
        self.assert_not_contains(self.CONF, "mIsSendDhcpHostnameEnabled = true")

    def test_existing_networks_keep_working_and_can_opt_in(self):
        self.assert_contains(
            self.UTIL,
            "return newConfig.isSendDhcpHostnameEnabled();",
        )
        self.assert_not_contains(
            self.UTIL,
            "return !newConfig.isSendDhcpHostnameEnabled();",
        )

    def test_xml_tag_rename_ignores_stock_values(self):
        self.assert_contains(
            self.XML,
            'XML_TAG_SEND_DHCP_HOSTNAME = "SendDhcpHostname2";',
            "renamed to SendDhcpHostname2 to",
        )

    def test_legacy_secure_only_backfill_is_removed(self):
        # Stock Android rewrote old configs to "send hostname on secure
        # networks only"; the lenOS default is off for every network type.
        self.assert_not_contains(
            self.XML,
            "sendDhcpHostnameExists",
            "Update legacy configs to send the DHCP hostname",
            "SECURITY_TYPE_OWE));",
        )


if __name__ == "__main__":
    unittest.main()

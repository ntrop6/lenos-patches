"""DHCP hostname privacy (packages/modules/Wifi patch).

Feature contract (see docs/features.md):
* Wi-Fi DHCP requests never carry the device name by default: the Wi-Fi
  module starts with the hostname blocked on open and secure networks.
* The block is a user choice, not hardcoded behaviour: components holding
  NETWORK_SETTINGS (Lineage Settings, SetupWizard, the lenOS security app)
  change it through WifiManager#setSendDhcpHostnameRestriction, and the value
  survives reboots because it is persisted in Settings.Global.
* A provider problem keeps the privacy default instead of crashing the
  Wi-Fi service.
* The stock permission model is not widened.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestDhcpHostnameDefault(LenosPatchTest):
    PROJECT = "packages/modules/Wifi"
    PATCHES = ["0001-privacy-dhcp-hostname-default.patch"]
    GLOBALS = "service/java/com/android/server/wifi/WifiGlobals.java"
    SERVICE = "service/java/com/android/server/wifi/WifiServiceImpl.java"

    def test_java_still_parses(self):
        self.assert_java_syntax(self.GLOBALS)
        self.assert_java_syntax(self.SERVICE)

    def test_settings_key_is_defined_once(self):
        self.assert_contains(
            self.GLOBALS,
            "LENOS_SETTING_SEND_DHCP_HOSTNAME_RESTRICTION",
            '"lenos_wifi_send_dhcp_hostname_restriction"',
        )

    def test_default_blocks_the_hostname_on_all_network_types(self):
        # OPEN|SECURE = do not send the hostname on open nor secure networks.
        self.assert_contains(
            self.GLOBALS,
            "WifiManager.FLAG_SEND_DHCP_HOSTNAME_RESTRICTION_OPEN",
            "WifiManager.FLAG_SEND_DHCP_HOSTNAME_RESTRICTION_SECURE",
            "mSendDhcpHostnameRestriction.set(hostnameRestriction);",
        )

    def test_read_failure_keeps_the_privacy_default(self):
        self.assert_contains(
            self.GLOBALS,
            "catch (Exception e)",
            "keeping the lenOS privacy default",
        )

    def test_changes_are_persisted_for_the_next_boot(self):
        self.assert_contains(
            self.SERVICE,
            "mFacade.setIntegerSetting(mContext.getContentResolver(),",
            "WifiGlobals.LENOS_SETTING_SEND_DHCP_HOSTNAME_RESTRICTION, restriction);",
        )

    def test_stock_permission_model_is_kept(self):
        # The API stays limited to NETWORK_SETTINGS/NETWORK_SETUP_WIZARD
        # holders and device owners; the patch must not widen it.
        self.assert_contains(
            self.SERVICE,
            "!isSettingsOrSuw(callingPid, callingUid)",
            "!mWifiPermissionsUtil.isDeviceOwner(callingUid, packageName)",
        )


if __name__ == "__main__":
    unittest.main()

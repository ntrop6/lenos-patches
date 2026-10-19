"""GrapheneOS LTE-only / 5G-only network mode entries.

Ported from GrapheneOS ``platform_packages_apps_Settings``:

* ``5310142ccc`` "LTE Only Mode" (2022) — adds a "LTE only" choice to the
  preferred-network-type dialog (strips 2G/3G from the modem stack).
* ``8d37b32db6`` "add "5G Only" and "4G or 5G only" Mode" (2025) — adds
  "5G or LTE only" and "5G only" when the carrier/baseband exposes NR
  standalone.

The entries are appended by the ``PreferenceEntriesBuilder`` in
``EnabledNetworkModePreferenceController``; the legacy world-mode
``PreferredNetworkModePreferenceController`` gets the matching LTE-only
summary string. Strings live in ``strings_ext.xml``.

Deliberate deviation: GrapheneOS's 2022 commit also flips the controller
availability check to ``!= PreferredNetworkMode``, which makes the row
visible when the carrier hides network settings (``None``). lenOS keeps the
stock ``== EnabledNetworkMode`` guard.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestLteOnlyMode(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = ["0001-lenos-ext-settings-ui.patch"]

    ENM = ("src/com/android/settings/network/telephony/"
           "EnabledNetworkModePreferenceController.java")
    PNM = ("src/com/android/settings/network/telephony/"
           "PreferredNetworkModePreferenceController.java")
    STRINGS = "res/values/strings_ext.xml"

    def test_lte_only_entry(self):
        self.assert_contains(
            self.ENM,
            "addLteOnlyEntry();",
            "private void addLteOnlyEntry()",
            "mEntriesValue.add(TelephonyManager.NETWORK_MODE_LTE_ONLY);",
            "R.string.network_lte_only",
            "R.string.network_4G_only")

    def test_lte_only_unsupported_cases(self):
        # CDMA without LTE, no-LTE, and "except LTE" builds must not offer it.
        text = self.text(self.ENM)
        self.assertEqual(text.count("lteOnlyUnsupported = true;"), 3)
        self.assertIn("boolean lteOnlyUnsupported = false;", text)
        self.assertIn("if (!lteOnlyUnsupported) {", text)

    def test_nr_only_entries(self):
        self.assert_contains(
            self.ENM,
            "private void addNrOnlyEntry()",
            "private void addNrOrLteOnlyEntry()",
            "mEntriesValue.add(TelephonyManager.NETWORK_MODE_NR_ONLY);",
            "mEntriesValue.add(TelephonyManager.NETWORK_MODE_NR_LTE);",
            "AtomicBoolean is5GSupported = new AtomicBoolean(false);",
            "if (!lteOnlyUnsupported && is5GSupported.get())")

    def test_nr_standalone_detection(self):
        self.assert_contains(
            self.ENM,
            "CarrierConfigManager.KEY_CARRIER_NR_AVAILABILITIES_INT_ARRAY",
            "CarrierConfigManager.CARRIER_NR_AVAILABILITY_SA",
            "TelephonyManager.ALLOWED_NETWORK_TYPES_REASON_USER",
            "TelephonyManager.NETWORK_TYPE_BITMASK_NR")

    def test_summaries_for_new_modes(self):
        self.assert_contains(
            self.ENM,
            "R.string.network_5g_only",
            "R.string.network_5g_or_lte_only",
            "R.string.network_5g_or_4g_only",
            "TelephonyManager.NETWORK_MODE_NR_ONLY);",
            "TelephonyManager.NETWORK_MODE_NR_LTE);")

    def test_world_mode_controller_summary(self):
        self.assert_contains(
            self.PNM,
            "NETWORK_MODE_LTE_ONLY",
            "R.string.preferred_network_mode_lte_only_summary")

    def test_strings(self):
        self.assert_contains(
            self.STRINGS,
            '<string name="network_lte_only">LTE only</string>',
            '<string name="network_4G_only">4G only</string>',
            '<string name="network_5g_only">5G only</string>',
            '<string name="network_5g_or_lte_only">5G or LTE only</string>',
            '<string name="network_5g_or_4g_only">5G or 4G only</string>',
            '<string name="preferred_network_mode_lte_only_summary">'
            'Preferred network mode: LTE only</string>')

    def test_availability_guard_kept(self):
        # Documented deviation: do not expose the row when the type is None.
        self.assert_contains(
            self.ENM,
            "== NetworkModePreferenceType.EnabledNetworkMode")
        self.assertNotIn("!= NetworkModePreferenceType.PreferredNetworkMode",
                         self.text(self.ENM))

    def test_syntax(self):
        for f in (self.ENM, self.PNM):
            self.assert_java_syntax(f)


if __name__ == "__main__":
    unittest.main()

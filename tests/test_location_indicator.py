"""GrapheneOS: status-bar location privacy indicator (Tier 2 #16).

LineageOS 23.2 (Android 16) contains all of the SystemUI location-indicator
machinery, but AOSP's ``bp4a`` release config leaves
``android.location.flags.location_indicators_enabled`` disabled, so the
privacy chip only ever lights up for camera and microphone. GrapheneOS ships
the indicator enabled and makes it cover *all* location access, not just apps
that hold the fine-location op.

Two pieces:

* ``vendor/lenos/release/`` — a lenOS release config map merged into the
  platform's ``bp4a`` config (the short name LineageOS selects through
  ``vendor/lineage/vars/aosp_target_release``). It carries a read-only
  ``location_indicators_enabled = ENABLED`` value. This is the first lenOS
  use of the release-config mechanism; the plumbing is generic so later
  features can flip further aconfig flags without patching AOSP or LineageOS.
* ``patches/frameworks_base/0027-lenos-location-indicator.patch`` —
  ``AppOpsPrivacyItemMonitor`` now watches ``OP_COARSE_LOCATION`` as well as
  ``OP_FINE_LOCATION`` (subscription, item mapping and two filters), matching
  GrapheneOS, so coarse-only apps light the indicator too. System apps and
  background accesses keep GrapheneOS's non-display accounting behaviour.

Not ported: GrapheneOS's accumulated location-usage logger
(``LocationAccumulatedLogger``) and the A17 indicator animation/outline
flags; both are absent from the Android 16 base.
"""
from __future__ import annotations

import subprocess
import unittest

from harness import LenosPatchTest, VENDOR, WORKSPACE


class TestLocationIndicatorPatch(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0027-lenos-location-indicator.patch"]

    MONITOR = ("packages/SystemUI/src/com/android/systemui/privacy/"
               "AppOpsPrivacyItemMonitor.kt")

    def test_location_op_subscription_includes_coarse(self):
        self.assert_contains(
            self.MONITOR,
            "val OPS_LOCATION =\n"
            "            intArrayOf(AppOpsManager.OP_FINE_LOCATION, "
            "AppOpsManager.OP_COARSE_LOCATION)")

    def test_no_fine_only_filters_remain(self):
        self.assert_not_contains(
            self.MONITOR,
            "item.code == AppOpsManager.OP_FINE_LOCATION",
            "appOpItem.code == AppOpsManager.OP_FINE_LOCATION",
            "OP_FINE_LOCATION -> PrivacyType.TYPE_LOCATION")

    def test_location_state_tracking_uses_both_ops(self):
        self.assert_contains(
            self.MONITOR,
            ".filter { item -> item.code in OPS_LOCATION }",
            "if (item.code in OPS_LOCATION) {")

    def test_coarse_maps_to_location_privacy_type(self):
        self.assert_contains(
            self.MONITOR,
            "AppOpsManager.OP_FINE_LOCATION,\n"
            "                AppOpsManager.OP_COARSE_LOCATION -> "
            "PrivacyType.TYPE_LOCATION")

    def test_mic_camera_ops_untouched(self):
        self.assert_contains(
            self.MONITOR,
            "AppOpsManager.OP_CAMERA,",
            "AppOpsManager.OP_PHONE_CALL_CAMERA,",
            "AppOpsManager.OP_RECORD_AUDIO,",
            "AppOpsManager.OP_RECEIVE_SANDBOX_TRIGGER_AUDIO,")

    def test_balanced(self):
        self.assert_balanced(self.MONITOR)


class TestLocationIndicatorReleaseConfig(unittest.TestCase):
    """The lenOS release config must wire the flag value into bp4a."""

    RELEASE = VENDOR / "release"

    def text(self, rel: str) -> str:
        path = self.RELEASE / rel
        self.assertTrue(path.is_file(), f"missing {path}")
        return path.read_text(encoding="utf-8")

    def test_release_config_map(self):
        body = self.text("release_config_map.textproto")
        self.assertIn('name: "bp4a"', body)
        self.assertIn('flag_value_files: "release_configs/bp4a.textproto"', body)
        # The map must stay discoverable by build/make's vendor wildcard:
        # vendor/*/release/release_config_map.textproto
        self.assertEqual(self.RELEASE.name, "release")
        self.assertEqual(self.RELEASE.parent.name, "lenos")
        self.assertEqual(self.RELEASE.parent.parent.name, "vendor")

    def test_release_config_points_at_the_lenos_value_set(self):
        self.assertIn(
            'aconfig_value_sets: "aconfig_value_set-lenos-bp4a"',
            self.text("release_configs/bp4a.textproto"))

    def test_value_set_collects_package_values(self):
        self.assertIn(
            'name: "aconfig_value_set-lenos-bp4a",',
            self.text("aconfig/bp4a/Android.bp"))
        self.assertIn('"*/Android.bp",', self.text("aconfig/bp4a/Android.bp"))

    def test_package_values_declare_the_location_package(self):
        body = self.text("aconfig/bp4a/android.location.flags/Android.bp")
        self.assertIn(
            'name: "aconfig-values-lenos-bp4a-android.location.flags-all",', body)
        self.assertIn('package: "android.location.flags",', body)
        self.assertIn('"*_flag_values.textproto",', body)

    def test_flag_value_enables_the_indicator_read_only(self):
        body = self.text(
            "aconfig/bp4a/android.location.flags/"
            "location_indicators_enabled_flag_values.textproto")
        self.assertIn('package: "android.location.flags"', body)
        self.assertIn('name: "location_indicators_enabled"', body)
        self.assertIn("state: ENABLED", body)
        self.assertIn("permission: READ_ONLY", body)
        self.assertNotIn("state: DISABLED", body)

    def test_flag_name_matches_the_aconfig_declaration(self):
        """The flag must exist in the pinned frameworks/base tree."""
        aconfig = "location/java/android/location/flags/location.aconfig"
        project = WORKSPACE / "frameworks/base"
        path = project / aconfig
        if path.is_file():
            body = path.read_text(encoding="utf-8")
        else:
            # Sparse checkouts may not have the file on disk; the git object
            # database still does.
            proc = subprocess.run(
                ["git", "-C", str(project), "show", f"HEAD:{aconfig}"],
                capture_output=True, text=True)
            if proc.returncode != 0:
                self.skipTest("location.aconfig not available in the workspace")
            body = proc.stdout
        self.assertIn('name: "location_indicators_enabled"', body)
        self.assertIn('namespace: "location"', body)

    def test_patch_is_in_the_series(self):
        series = (VENDOR / "patches/frameworks_base/series").read_text()
        self.assertIn("0027-lenos-location-indicator.patch", series)


if __name__ == "__main__":
    unittest.main()

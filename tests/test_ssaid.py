"""SSAID/ANDROID_ID rotation on reinstall (frameworks/base SettingsProvider).

Feature contract (see docs/features.md):
* An app that is *installed anew* gets a different ANDROID_ID than it had before.
* An app that is merely *upgraded* keeps its ANDROID_ID.
* The identifier stays scoped per user (per-user secret) and per signing key.
* Users can turn the behaviour off, which restores stock AOSP derivation.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestSsaidRotation(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0001-ssaid-rotate-on-reinstall.patch"]
    F = "packages/SettingsProvider/src/com/android/providers/settings/SettingsProvider.java"

    def test_still_syntactically_valid_java(self):
        self.assert_java_syntax(self.F)

    def test_install_generation_is_part_of_the_derivation(self):
        self.assert_contains(
            self.F,
            "final byte[] generation =\n                        ByteBuffer.allocate(8).putLong(callingPkg.firstInstallTime).array();",
            "if (includeInstallGeneration)",
        )

    def test_rotation_is_detected_by_comparing_stored_value(self):
        self.assert_contains(
            self.F,
            "isLenosSsaidRotationEnabled()",
            "!isSsaidUpToDateLocked(ssaid, callingPkg, owningUserId)",
            "computeSsaidLocked(callingPkg, owningUserId,\n                /* includeInstallGeneration= */ true)",
        )

    def test_rotation_can_be_disabled_by_a_user_visible_setting(self):
        self.assert_contains(
            self.F,
            'public static final String LENOS_SSAID_ROTATION_ENABLED = "lenos_ssaid_rotation_enabled";',
            "LENOS_SSAID_ROTATION_ENABLED, 1) != 0;",
        )

    def test_aosp_derivation_is_preserved_without_the_generation(self):
        # When rotation is off, the value must be byte-for-byte the AOSP value:
        # signatures only, no extra HMAC input.
        self.assert_contains(
            self.F,
            "if (includeInstallGeneration) {",
            "return HexEncoding.encodeToString(m.doFinal(), false /* upperCase */)",
        )

    def test_original_behaviour_for_missing_ssaid_is_kept(self):
        # The lazy-initialise path must still store the value it computed.
        self.assert_contains(
            self.F,
            "Setting setting = mSettingsRegistry.generateSsaidLocked(callingPkg, owningUserId);\n"
            "            return mascaradeSsaidSetting(ssaidSettings, setting);",
        )

    def test_no_schema_change(self):
        # The feature must not change the settings database layout: it stores
        # the rotated value in the existing ssaid table entry for the uid.
        body = self.text(self.F)
        self.assertNotIn("ALTER TABLE", body)
        self.assertNotIn("DATABASE_VERSION", body)


if __name__ == "__main__":
    unittest.main()

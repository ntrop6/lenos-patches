"""OPSEC: wipe the clipboard when the screen turns off.

AOSP's only automatic clipboard wipe is a DeviceConfig timer (one hour by
default) and it starts when a clip is read. This lenOS control binds the wipe
to screen-off, so secrets do not survive the moment the user puts the device
down or hands it to someone else. It is opt-in and per-user.
"""
from __future__ import annotations

import unittest

from harness import PATCH_ROOT, LenosPatchTest, VENDOR, patch_paths

FWB_PATCH = "0004-clipboard-clear-on-screen-off.patch"
SETTINGS_PATCH = "0003-clipboard-privacy.patch"


class TestClipboardClearFramework(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = [FWB_PATCH]

    def test_patch_scope(self):
        patch = PATCH_ROOT / "frameworks_base" / FWB_PATCH
        self.assertEqual(
            sorted(patch_paths(patch)),
            sorted([
                "core/java/android/provider/Settings.java",
                "services/core/java/com/android/server/clipboard/ClipboardService.java",
            ]),
        )

    def test_setting_is_off_by_default_and_per_user(self):
        self.assert_contains(
            "core/java/android/provider/Settings.java",
            "CLIPBOARD_CLEAR_ON_SCREEN_OFF",
            '"clipboard_clear_on_screen_off"',
            "0 (default) keeps the clipboard",
        )
        self.assert_contains(
            "services/core/java/com/android/server/clipboard/ClipboardService.java",
            "Settings.Secure.getIntForUser",
            "Settings.Secure.CLIPBOARD_CLEAR_ON_SCREEN_OFF, 0, userId",
            "if (enabled == 0)",
        )

    def test_screen_off_receiver_clears_clipboard(self):
        self.assert_contains(
            "services/core/java/com/android/server/clipboard/ClipboardService.java",
            "Intent.ACTION_SCREEN_OFF",
            "mScreenOffReceiver",
            "Context.RECEIVER_NOT_EXPORTED",
            "clearClipboardsOnScreenOff()",
            "setPrimaryClipInternalLocked(null",
            "UserHandle.getUid(userId, android.os.Process.SYSTEM_UID)",
            "clipboard.primaryClip == null",
        )
        self.assert_contains(
            "services/core/java/com/android/server/clipboard/ClipboardService.java",
            "revokeUris",
        )

    def test_java_parses(self):
        for rel in (
                "core/java/android/provider/Settings.java",
                "services/core/java/com/android/server/clipboard/ClipboardService.java"):
            self.assert_java_syntax(rel)


class TestClipboardClearSettings(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = [SETTINGS_PATCH]

    def test_toggle_is_exposed(self):
        self.assert_contains(
            "src/com/android/settings/security/ClipboardPrivacySettings.java",
            "CLIPBOARD_CLEAR_ON_SCREEN_OFF",
            "SwitchPreference",
            "putInt",
            "enabled ? 1 : 0",
            "clipboard_clear_on_screen_off",
        )
        self.assert_contains(
            "res/xml/more_security_privacy_settings.xml",
            'android:key="clipboard_privacy"',
            'android:fragment="com.android.settings.security.ClipboardPrivacySettings"',
        )
        self.assert_contains(
            "res/values/strings.xml",
            "clipboard_clear_on_screen_off_title",
            "clipboard_clear_on_screen_off_summary",
        )

    def test_resources_and_java_parse(self):
        self.assert_xml("res/xml/more_security_privacy_settings.xml")
        self.assert_xml("res/values/strings.xml")
        self.assert_java_syntax(
            "src/com/android/settings/security/ClipboardPrivacySettings.java")


if __name__ == "__main__":
    unittest.main()

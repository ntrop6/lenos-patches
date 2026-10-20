"""Secure Paste stage 2: per-app clipboard read control.

Android already has an AppOps policy for clipboard reads. This Settings screen
uses it directly, so the feature needs no framework patch and no new
permission. Only user-installed apps are listed; system apps and the default
IME stay on the trusted paste path.
"""
from __future__ import annotations

import unittest

from harness import PATCH_ROOT, LenosPatchTest, VENDOR, patch_paths

PATCH = "0004-clipboard-app-access.patch"


class TestClipboardAppAccess(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = [PATCH]

    def test_patch_scope(self):
        patch = PATCH_ROOT / "packages_apps_Settings" / PATCH
        self.assertEqual(
            sorted(patch_paths(patch)),
            sorted([
                "res/values/strings.xml",
                "res/xml/more_security_privacy_settings.xml",
                "src/com/android/settings/security/ClipboardAppAccessSettings.java",
            ]),
        )

    def test_uses_existing_appop_without_new_framework_surface(self):
        self.assert_contains(
            "src/com/android/settings/security/ClipboardAppAccessSettings.java",
            "AppOpsManager.OP_READ_CLIPBOARD",
            "AppOpsManager.OPSTR_READ_CLIPBOARD",
            "mAppOps.setMode",
            "MODE_IGNORED",
            "MODE_ALLOWED",
            "unsafeCheckOpNoThrow",
            "FLAG_SYSTEM",
            "FLAG_UPDATED_SYSTEM_APP",
            "getInstalledApplications",
            "SwitchPreference",
            "mExecutor.execute",
            "mMainHandler.post",
            "getEnabledInputMethodList",
            "InputMethodInfo",
        )
        self.assert_not_contains(
            "src/com/android/settings/security/ClipboardAppAccessSettings.java",
            "GosPackageState",
            "ClipboardService",
            "INTERNET",
        )

    def test_ui_entry_and_strings(self):
        self.assert_contains(
            "res/xml/more_security_privacy_settings.xml",
            'android:key="clipboard_app_access"',
            'android:fragment="com.android.settings.security.ClipboardAppAccessSettings"',
            'android:order="246"',
        )
        self.assert_contains(
            "res/values/strings.xml",
            "clipboard_app_access_title",
            "clipboard_app_access_summary",
            "clipboard_app_access_note",
            "clipboard_app_access_failed",
        )

    def test_system_apps_and_ime_note_are_not_offered(self):
        body = self.text(
            "src/com/android/settings/security/ClipboardAppAccessSettings.java")
        self.assertIn("(info.flags & ApplicationInfo.FLAG_SYSTEM) != 0", body)
        self.assertIn("(info.flags & ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) != 0", body)
        self.assertIn("system apps and enabled keyboards", body)
        self.assertIn("imePackages.contains(info.packageName)", body)

    def test_resources_and_java_parse(self):
        self.assert_xml("res/values/strings.xml")
        self.assert_xml("res/xml/more_security_privacy_settings.xml")
        self.assert_java_syntax(
            "src/com/android/settings/security/ClipboardAppAccessSettings.java")


if __name__ == "__main__":
    unittest.main()

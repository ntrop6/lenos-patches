"""Experimental partial #23: global native-debugging block.

This is intentionally not a faithful GrapheneOS port. It is a single opt-in
secure setting that clears the kernel dumpable bit for newly started
non-system, non-debuggable, non-profileable app processes. GrapheneOS's
per-app GosPackageState and SELinux policy are still absent.
"""
from __future__ import annotations

import unittest

from harness import PATCH_ROOT, LenosPatchTest, VENDOR, patch_paths

FW_PATCH = "0005-native-debugging-block.patch"
SETTINGS_PATCH = "0005-native-debugging-block.patch"


class TestNativeDebuggingFramework(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = [FW_PATCH]

    def test_patch_scope(self):
        patch = PATCH_ROOT / "frameworks_base" / FW_PATCH
        self.assertEqual(
            sorted(patch_paths(patch)),
            sorted([
                "core/java/android/app/ActivityThread.java",
                "core/java/android/app/NativeDebuggingBlock.java",
                "core/java/android/os/Process.java",
                "core/java/android/provider/Settings.java",
                "core/jni/android_util_Process.cpp",
            ]),
        )

    def test_prctl_and_jni_registration(self):
        self.assert_contains(
            "core/jni/android_util_Process.cpp",
            "#include <sys/prctl.h>",
            "PR_SET_DUMPABLE",
            "android_os_Process_setDumpable",
            '{"setDumpable", "(Z)V"',
        )
        self.assert_contains(
            "core/java/android/os/Process.java",
            "public static native void setDumpable(boolean dumpable);",
        )
        self.assert_contains(
            "core/java/android/provider/Settings.java",
            'BLOCK_NATIVE_DEBUGGING = "block_native_debugging"',
        )

    def test_apply_happens_before_app_code_and_exempts_development(self):
        self.assert_contains(
            "core/java/android/app/ActivityThread.java",
            "NativeDebuggingBlock.apply(data.appInfo, getSystemContext());",
        )
        self.assert_contains(
            "core/java/android/app/NativeDebuggingBlock.java",
            "appInfo.isSystemApp()",
            "appInfo.isUpdatedSystemApp()",
            "appInfo.isDebuggable()",
            "appInfo.isProfileable()",
            "Process.setDumpable(false)",
            "Settings.Secure.getIntForUser",
            "Settings.Secure.BLOCK_NATIVE_DEBUGGING, 0",
        )
        self.assert_not_contains(
            "core/java/android/app/NativeDebuggingBlock.java",
            "Process.setDumpable(true)",
        )

    def test_java_parse_and_jni_registration(self):
        self.assert_java_syntax("core/java/android/app/NativeDebuggingBlock.java")
        self.assert_java_syntax("core/java/android/app/ActivityThread.java")
        self.assert_contains(
            "core/jni/android_util_Process.cpp",
            "static void android_os_Process_setDumpable",
            "jniThrowErrnoException(env, \"setDumpable\", errno)",
        )


class TestNativeDebuggingSettings(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = [SETTINGS_PATCH]

    def test_patch_scope(self):
        patch = PATCH_ROOT / "packages_apps_Settings" / SETTINGS_PATCH
        self.assertEqual(
            sorted(patch_paths(patch)),
            sorted([
                "res/values/strings.xml",
                "res/xml/more_security_privacy_settings.xml",
                "res/xml/native_debugging_block.xml",
                "src/com/android/settings/security/NativeDebuggingBlockSettings.java",
            ]),
        )

    def test_ui_controls_the_secure_setting(self):
        self.assert_contains(
            "src/com/android/settings/security/NativeDebuggingBlockSettings.java",
            "Settings.Secure.BLOCK_NATIVE_DEBUGGING",
            "Settings.Secure.getInt",
            "Settings.Secure.putInt",
            "SwitchPreference",
        )
        self.assert_contains(
            "res/xml/more_security_privacy_settings.xml",
            'android:key="native_debugging_block"',
            'android:fragment="com.android.settings.security.NativeDebuggingBlockSettings"',
            'android:order="247"',
        )
        self.assert_contains(
            "res/xml/native_debugging_block.xml",
            'android:key="block_native_debugging"',
            'android:persistent="false"',
        )
        self.assert_contains(
            "res/values/strings.xml",
            "native_debugging_block_title",
            "native_debugging_block_limitations",
        )

    def test_resources_and_java_parse(self):
        self.assert_xml("res/values/strings.xml")
        self.assert_xml("res/xml/more_security_privacy_settings.xml")
        self.assert_xml("res/xml/native_debugging_block.xml")
        self.assert_java_syntax(
            "src/com/android/settings/security/NativeDebuggingBlockSettings.java")


if __name__ == "__main__":
    unittest.main()

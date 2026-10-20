"""Local crash/ANR log viewer (Tier 2 #17, experimental).

The viewer deliberately has no upload path. It reads the existing local
DropBox records, shows the newest entries first, and only shares an entry after
an explicit user action. This keeps crash reporting useful without introducing
a silent telemetry channel.
"""
from __future__ import annotations

import unittest

from harness import PATCH_ROOT, VENDOR, LenosPatchTest, patch_paths

PATCH = "0001-crash-log-viewer.patch"
ALIAS = "packages_apps_Settings"
JAVA = "src/com/android/settings/lenos/CrashLogSettings.java"
MANIFEST = "AndroidManifest.xml"
STRINGS = "res/values/strings.xml"
ABOUT = "res/xml/my_device_info.xml"


class TestCrashLogViewer(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = [PATCH]

    def test_patch_scope(self):
        patch = PATCH_ROOT / ALIAS / PATCH
        self.assertEqual(
            sorted(patch_paths(patch)),
            sorted([JAVA, MANIFEST, STRINGS, ABOUT]),
        )

    def test_viewer_reads_local_dropbox_records_only(self):
        self.assert_contains(
            JAVA,
            "DropBoxManager",
            "getNextEntry",
            "\"system_app_crash\"",
            "\"data_app_crash\"",
            "\"SYSTEM_TOMBSTONE\"",
            "Intent.ACTION_SEND",
            "never uploads anything",
        )
        source = self.text(JAVA)
        for forbidden in ("HttpURLConnection", "OkHttp", "INTERNET", "Socket(", "URL("):
            self.assertNotIn(forbidden, source)

    def test_viewer_has_a_hard_entry_and_size_cap(self):
        self.assert_contains(
            JAVA,
            "MAX_ENTRIES = 100",
            "MAX_TEXT_BYTES = 64 * 1024",
            "entries.size() > MAX_ENTRIES",
        )

    def test_settings_entry_and_permission_are_declared(self):
        self.assert_contains(
            MANIFEST,
            'android.permission.READ_LOGS',
        )
        self.assert_contains(
            ABOUT,
            'android:key="lenos_crash_logs"',
            'android:fragment="com.android.settings.lenos.CrashLogSettings"',
            "@string/lenos_crash_logs_title",
        )
        self.assert_contains(
            STRINGS,
            'name="lenos_crash_logs_title"',
            'name="lenos_crash_logs_summary"',
            "Nothing is uploaded automatically",
        )

    def test_resources_and_java_are_well_formed(self):
        self.assert_xml(MANIFEST)
        self.assert_xml(STRINGS)
        self.assert_xml(ABOUT)
        self.assert_java_syntax(JAVA)


if __name__ == "__main__":
    unittest.main()

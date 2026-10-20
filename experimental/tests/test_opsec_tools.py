"""OPSEC tools that GrapheneOS does not provide (experimental).

The source lives in ``experimental/app/LenosOpsec`` and is installed only when
``LENOS_EXPERIMENTAL=1``. It is not a patch against a pristine vendor tree.

* a share target that re-encodes an image so EXIF/GPS/XMP/file-name metadata
  cannot leak to the receiving app; and
* an "Offline" Quick Settings tile that turns airplane mode and the remaining
  radios off in one action.

Both are local-only. The app has no INTERNET permission and no network code.
"""
from __future__ import annotations

import unittest

from harness import SourceTreeTest

APP = "experimental/app/LenosOpsec"


class TestOpsecTools(SourceTreeTest):
    def test_image_scrubber_reencodes_without_metadata(self):
        self.assert_contains(
            f"{APP}/src/org/lenos/opsec/ImageScrubber.java",
            "ImageDecoder.decodeBitmap",
            "bitmap.compress",
            "UUID.randomUUID()",
            "MAX_DIMENSION",
            "image/png",
            "image/webp",
            "image/jpeg",
        )
        self.assert_not_contains(
            f"{APP}/src/org/lenos/opsec/ImageScrubber.java",
            "ExifInterface",
            "setAttribute",
            "TAG_GPS",
        )

    def test_share_target_and_save_path(self):
        self.assert_contains(
            f"{APP}/src/org/lenos/opsec/ScrubActivity.java",
            "Intent.ACTION_SEND",
            "Intent.ACTION_SEND_MULTIPLE",
            "FileProvider.getUriForFile",
            "FLAG_GRANT_READ_URI_PERMISSION",
            "MediaStore.Images.Media",
            "RELATIVE_PATH",
            "IS_PENDING",
            "ClipData",
        )
        self.assert_contains(
            f"{APP}/AndroidManifest.xml",
            'android:name=".ScrubActivity"',
            'android:name="android.intent.action.SEND"',
            'android:name="android.intent.action.SEND_MULTIPLE"',
            'android:mimeType="image/*"',
            'androidx.core.content.FileProvider',
        )

    def test_manifest_exports_are_intentional(self):
        self.assert_contains(
            f"{APP}/AndroidManifest.xml",
            'android:name=".ScrubActivity"',
            'android:name=".ScrubTextActivity"',
            'android:name=".OfflineTileService"',
            'android:permission="android.permission.BIND_QUICK_SETTINGS_TILE"',
            'android:authorities="org.lenos.opsec.files"',
            'android:exported="false"',
            'android:grantUriPermissions="true"',
        )

    def test_app_has_no_network_permission_or_code(self):
        manifest = self.text(f"{APP}/AndroidManifest.xml")
        self.assertNotIn("android.permission.INTERNET", manifest)
        for rel in (
                f"{APP}/src/org/lenos/opsec/ImageScrubber.java",
                f"{APP}/src/org/lenos/opsec/ScrubActivity.java",
                f"{APP}/src/org/lenos/opsec/OfflineTileService.java",
                f"{APP}/src/org/lenos/opsec/LinkScrubber.java",
                f"{APP}/src/org/lenos/opsec/ScrubTextActivity.java"):
            body = self.text(rel)
            self.assertNotIn("java.net.", body, rel)
            self.assertNotIn("HttpURLConnection", body, rel)
            self.assertNotIn("Socket", body, rel)

    def test_offline_tile_is_a_radio_kill_switch(self):
        self.assert_contains(
            f"{APP}/src/org/lenos/opsec/OfflineTileService.java",
            "TileService",
            "setAirplaneMode",
            "AIRPLANE_MODE_ON",
            "setWifiEnabled(false)",
            "bluetooth.disable()",
        )
        self.assert_contains(
            f"{APP}/AndroidManifest.xml",
            "android.permission.NETWORK_SETTINGS",
            "android.permission.WRITE_SECURE_SETTINGS",
            "android.permission.BLUETOOTH_PRIVILEGED",
        )

    def test_product_integration_is_opt_in(self):
        experimental = self.text("config/lenos-experimental.mk")
        self.assertIn("LenosOpsec", experimental)
        self.assertIn("ro.lenos.experimental=1", experimental)
        default = self.text("config/lenos.mk")
        self.assertNotIn("LenosOpsec", default)
        self.assertIn("ifneq ($(filter 1 true yes,$(LENOS_EXPERIMENTAL)),)", default)
        self.assert_contains(
            f"{APP}/Android.bp",
            'name: "LenosOpsec"',
            "platform_apis: true",
            'certificate: "platform"',
        )

    def test_resources_and_java_parse(self):
        for rel in (
                f"{APP}/AndroidManifest.xml",
                f"{APP}/res/layout/activity_scrub.xml",
                f"{APP}/res/values/strings.xml",
                f"{APP}/res/xml/file_paths.xml",
                f"{APP}/res/drawable/ic_offline.xml"):
            self.assert_xml(rel)
        for rel in (
                f"{APP}/src/org/lenos/opsec/ImageScrubber.java",
                f"{APP}/src/org/lenos/opsec/ScrubActivity.java",
                f"{APP}/src/org/lenos/opsec/OfflineTileService.java",
                f"{APP}/src/org/lenos/opsec/LinkScrubber.java",
                f"{APP}/src/org/lenos/opsec/ScrubTextActivity.java"):
            self.assert_java_syntax(rel)


if __name__ == "__main__":
    unittest.main()

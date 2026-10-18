"""Screenshot EXIF privacy (SystemUI + Settings, see docs/features.md).

Feature contract (GrapheneOS-faithful port):
* SystemUI screenshots are exported with no timestamp, timezone, sub-second or
  build-identifier EXIF metadata unless ``ExtSettings.SCREENSHOT_TIMESTAMP_EXIF``
  (``Settings.Secure.screenshot_timestamp_exif``, default off) is enabled. The
  gate is applied in ``ImageExporter.writeExif`` by nulling ``captureTime``;
  ``updateExifAttributes`` is nullable and returns before writing any date
  tags. LineageOS's ``TAG_SOFTWARE = "Android " + Build.DISPLAY`` line is
  removed to match GrapheneOS/AOSP, which never write a build string.
* The SystemUI gate reads the per-user ExtSettings value; the Settings toggle
  ``privacy_screenshot_timestamp_exif`` (More security & privacy) writes it
  through ``BoolSettingPrefController``. GrapheneOS wires the row via the
  ``settings:boolSettingField`` XML attribute, which lenOS does not port; the
  controller is registered explicitly in ``MoreSecurityPrivacyFragment``.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestScreenshotExifEnforcement(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0013-lenos-screenshot-exif-privacy.patch"]
    SRC = ("packages/SystemUI/src/com/android/systemui/screenshot/"
           "ImageExporter.java")

    def test_timestamp_gated_by_ext_settings(self):
        self.assert_contains(
            self.SRC,
            "import android.ext.settings.ExtSettings;",
            """if (!ExtSettings.SCREENSHOT_TIMESTAMP_EXIF.get(resolver.getContext())) {
                captureTime = null;
            }""",
        )

    def test_exif_writer_skips_date_tags_when_null(self):
        self.assert_contains(
            self.SRC,
            "@Nullable ZonedDateTime captureTime",
            """if (captureTime == null) {
            return;
        }""",
            "TAG_DATETIME_ORIGINAL",
        )

    def test_no_build_string_is_written(self):
        # LineageOS adds TAG_SOFTWARE = "Android " + Build.DISPLAY; GrapheneOS
        # and AOSP write no software tag, so the line (and its import) go away.
        self.assert_not_contains(self.SRC, "exif.setAttribute(ExifInterface.TAG_SOFTWARE")
        self.assert_not_contains(self.SRC, "import android.os.Build;")

    def test_syntax(self):
        self.assert_java_syntax(self.SRC)


class TestScreenshotExifSetting(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = ["0001-lenos-ext-settings-ui.patch"]
    XML = "res/xml/more_security_privacy_settings.xml"
    FRAGMENT = "src/com/android/settings/safetycenter/MoreSecurityPrivacyFragment.java"
    STRINGS = "res/values/strings_ext.xml"

    def test_row_uses_grapheneos_strings_and_key(self):
        self.assert_contains(
            self.XML,
            'android:key="privacy_screenshot_timestamp_exif"',
            '@string/screenshot_timestamp_exif_title',
            '@string/screenshot_timestamp_exif_summary',
        )
        # The GrapheneOS auto-wiring attribute is not ported.
        self.assert_not_contains(self.XML, 'settings:boolSettingField="')

    def test_strings_match_grapheneos(self):
        self.assert_contains(
            self.STRINGS,
            '<string name="screenshot_timestamp_exif_title">'
            'Save screenshot timestamp to EXIF</string>',
            '<string name="screenshot_timestamp_exif_summary">'
            'Enables adding a timestamp to screenshot EXIF metadata</string>',
        )

    def test_controller_registered_explicitly(self):
        self.assert_contains(
            self.FRAGMENT,
            "import android.ext.settings.ExtSettings;",
            "import com.android.settings.ext.BoolSettingPrefController;",
            '"privacy_screenshot_timestamp_exif"',
            """controllers.add(new BoolSettingPrefController(context, KEY_SCREENSHOT_TIMESTAMP_EXIF,
                ExtSettings.SCREENSHOT_TIMESTAMP_EXIF));""",
        )

    def test_xml_well_formed(self):
        self.assert_xml(self.XML)
        self.assert_xml(self.STRINGS)

    def test_syntax(self):
        self.assert_java_syntax(self.FRAGMENT)


if __name__ == "__main__":
    unittest.main()

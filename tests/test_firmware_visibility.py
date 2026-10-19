"""GrapheneOS firmware-security visibility (engineering-unit warning, bootloader field).

Ported from GrapheneOS's "Other features":

* "Engineering/Prototype ("EVT", "PVT" or "DVT") device warning as these devices
  typically have relaxed security controls for development" — a persistent
  notification posted from ``ActivityManagerService`` at boot.
* "Improved user visibility into persistent firmware security" — the
  bootloader version field in Settings > About phone > Firmware version.

Documented deviations from GrapheneOS:

* GrapheneOS detects prototypes on Pixels via ``ro.revision`` and
  ``ro.boot.secure_boot`` and returns early for every other OEM. lenOS keeps
  that Pixel logic verbatim and adds a phase-marker path for other OEMs
  (Nothing/Qualcomm): an explicit EVT/PVT/DVT marker in one of the bootloader
  hardware-phase properties. Unknown or plain revision values never warn, so
  the notification cannot false-positive on retail units.
* The AOSP "Serial console is enabled" notification already ships in LineageOS,
  so only the prototype notification is added.
* The pre-Treble ``ro.build.expect.bootloader`` / ``ro.build.expect.baseband``
  build-consistency checks GrapheneOS enabled in 2017 were removed upstream
  once devices became Treble/VINTF-verified; ``Build.isBuildConsistent()`` and
  the ``showSystemReadyErrorDialogsIfNeeded`` mismatch dialog already exist in
  LineageOS, so there is nothing to port for the "version and fingerprint
  checks" part beyond the visibility field.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestPrototypeWarning(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0023-lenos-prototype-device-warning.patch"]

    STRINGS = "core/res/res/values/strings.xml"
    PROTO = "proto/src/system_messages.proto"
    AMS = "services/core/java/com/android/server/am/ActivityManagerService.java"

    def test_notification_strings(self):
        self.assert_contains(
            self.STRINGS,
            '<string name="prototype_device_notification_title">'
            "Device is an engineering prototype</string>",
            '<string name="prototype_device_notification_message">'
            "Device security may be affected.</string>")

    def test_system_message_id(self):
        self.assert_contains(
            self.PROTO,
            "// Inform the user that the device appears to be a prototype.",
            "NOTE_PROTOTYPE_DETECTED = 400;")
        # The new note is registered after the last stock note and before the
        # legacy-ID boundary of that same block, like the other post-O notes,
        # so ids stay stable.
        text = self.text(self.PROTO)
        start = text.index("NOTE_PROTOTYPE_DETECTED = 400;")
        self.assertLess(text.index("NOTE_WRONG_HSUM_STATUS = 77;"), start)
        self.assertGreater(
            text.index("ADD_NEW_IDS_ABOVE_THIS_LINE", start), start)

    def test_grapheneos_pixel_logic_verbatim(self):
        self.assert_contains(
            self.AMS,
            "private static boolean isPrototypeDevice() {",
            'switch (Build.BRAND) {',
            'case "google":',
            "// Other OEMs may deal with hardware revisions differently",
            'if (!SystemProperties.get("ro.revision").contains("MP")) {',
            'if (!SystemProperties.get("ro.boot.secure_boot").equals("PRODUCTION")) {')

    def test_non_pixel_phase_markers(self):
        self.assert_contains(
            self.AMS,
            '"ro.boot.hwlevel",',
            '"ro.boot.hardware.revision",',
            '"ro.boot.device_release",',
            'value.contains("EVT") || value.contains("PVT") '
            '|| value.contains("DVT")')

    def test_call_site_is_boot_completion(self):
        self.assert_contains(
            self.AMS,
            "// UART is on if init's console service is running, "
            "send a warning notification.",
            "showConsoleNotificationIfActive();\n"
            "        showMteOverrideNotificationIfActive();\n"
            "        // If device is not a mass production (MP) variant, "
            "send a warning notification.\n"
            "        showPrototypeNotificationIfPrototype();")

    def test_notification_is_persistent_and_public(self):
        self.assert_contains(
            self.AMS,
            "private void showPrototypeNotificationIfPrototype() {",
            "getString(com.android.internal.R.string."
            "prototype_device_notification_title)",
            "getString(com.android.internal.R.string."
            "prototype_device_notification_message)",
            "new Notification.Builder(mContext, "
            "SystemNotificationChannels.DEVELOPER)",
            ".setOngoing(true)",
            ".setVisibility(Notification.VISIBILITY_PUBLIC)",
            "SystemMessage.NOTE_PROTOTYPE_DETECTED, notification, "
            "UserHandle.ALL);")

    def test_console_notification_untouched(self):
        self.assert_contains(
            self.AMS,
            'if (!SystemProperties.get("init.svc.console").equals("running")) {',
            "SystemMessage.NOTE_SERIAL_CONSOLE_ENABLED, notification, "
            "UserHandle.ALL);")
        # lenOS does not add a second cmdline-based UART heuristic: AOSP's
        # init-service check is already accurate on every device, including
        # Nothing/Qualcomm units whose bootloaders don't use the Pixel-style
        # "console=null" convention.
        self.assert_not_contains(self.AMS, "/proc/cmdline")
        self.assertEqual(
            self.text(self.AMS).count(
                "private void showConsoleNotificationIfActive() {"), 1)

    def test_syntax(self):
        self.assert_java_syntax(self.AMS)
        self.assert_xml(self.STRINGS)


class TestFirmwareVisibilitySettings(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = ["0001-lenos-ext-settings-ui.patch"]

    CONTROLLER = ("src/com/android/settings/deviceinfo/firmwareversion/"
                  "BootloaderVersionPreferenceController.java")
    XML = "res/xml/firmware_version.xml"
    STRINGS = "res/values/strings_ext.xml"

    def test_controller_reads_ro_bootloader(self):
        self.assert_contains(
            self.CONTROLLER,
            "extends BasePreferenceController",
            'static final String BOOTLOADER_PROPERTY = "ro.bootloader";',
            "return AVAILABLE;",
            "SystemProperties.get(BOOTLOADER_PROPERTY,\n"
            "                mContext.getString(R.string.device_info_default));")

    def test_firmware_version_row(self):
        text = self.text(self.XML)
        self.assert_contains(
            self.XML,
            'android:key="bootloader_version"',
            'android:title="@string/bootloader_version"',
            'settings:controller="com.android.settings.deviceinfo.'
            'firmwareversion.BootloaderVersionPreferenceController"/>')
        # The row sits between baseband and kernel, matching GrapheneOS.
        self.assertLess(text.index('android:key="base_band"'),
                        text.index('android:key="bootloader_version"'))
        self.assertLess(text.index('android:key="bootloader_version"'),
                        text.index('android:key="kernel_version"'))

    def test_strings(self):
        self.assert_contains(
            self.STRINGS,
            '<string name="bootloader_version">Bootloader version</string>')

    def test_syntax(self):
        self.assert_java_syntax(self.CONTROLLER)
        self.assert_xml(self.XML)
        self.assert_xml(self.STRINGS)


if __name__ == "__main__":
    unittest.main()

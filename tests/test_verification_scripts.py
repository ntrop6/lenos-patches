"""Static checks for the post-build and read-only device verification scripts."""
from __future__ import annotations

import os
import unittest

from harness import VENDOR


class TestVerificationScripts(unittest.TestCase):
    def test_scripts_are_present_and_executable(self):
        for name in ("verify-build.sh", "verify-device.sh"):
            path = VENDOR / "tools" / name
            self.assertTrue(path.is_file(), name)
            self.assertTrue(os.access(path, os.X_OK), f"{name} is not executable")

    def test_scripts_do_not_flash_or_change_the_device(self):
        forbidden = (
            "fastboot", "flash ", "flashall", "erase ", "wipe", "reboot",
            "settings put", "pm clear", "pm uninstall", "am force-stop",
            "cmd usb set", "svc wifi", "svc data", "rm -rf",
        )
        for name in ("verify-build.sh", "verify-device.sh"):
            # Comments explain what the script does not do; only inspect executable lines.
            lines = [line for line in
                     (VENDOR / "tools" / name).read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#")]
            body = "\n".join(lines).lower()
            for needle in forbidden:
                self.assertNotIn(needle, body, f"{name} contains {needle!r}")

    def test_device_probes_are_read_only(self):
        body = (VENDOR / "tools" / "verify-device.sh").read_text(encoding="utf-8")
        for needle in ("getprop", "settings get secure", "dumpsys usb", "pm path",
                       "dmesg_restrict", "/proc/config.gz"):
            self.assertIn(needle, body)
        self.assertIn("made no changes", body)

    def test_build_script_checks_expected_artifacts(self):
        body = (VENDOR / "tools" / "verify-build.sh").read_text(encoding="utf-8")
        for needle in ("framework.jar", "Settings/Settings.apk", "LenosOpsec",
                       "Seedvault", "system.img"):
            self.assertIn(needle, body)


if __name__ == "__main__":
    unittest.main()

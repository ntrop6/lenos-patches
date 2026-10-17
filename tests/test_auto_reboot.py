"""Auto reboot to before-first-unlock (frameworks/base + vendor/lenos).

Feature contract (see docs/features.md):
* LenosAutoRebootService reboots a secured device that has stayed locked
  longer than Settings.Global ``lenos_auto_reboot_timeout_ms``; after the
  reboot the file-based encryption keys are not in memory until the next
  unlock (before-first-unlock state).
* The countdown arms at screen off and disarms on unlock, so it always
  measures time since the device was last used.
* Safety rails: 0 disables the timer, out-of-range values fall back to the
  18 hour ROM default, reboots are skipped without a secure lock and deferred
  while a call is in progress (emergency calls keep working after reboot).
* Plumbing: the settings provider seeds the timeout on first boot
  (def_lenos_auto_reboot_timeout_ms), the product RRO sets it to 18h and the
  lenOS security app writes the same int key.
"""
from __future__ import annotations

import unittest

from harness import VENDOR, LenosPatchTest

APP = "app/LenosSecurity/src/org/lenos/security/MainActivity.java"
RRO = "rro/LenosSettingsProviderOverlay/res/values/defaults.xml"


def read_vendor(rel: str) -> str:
    return (VENDOR / rel).read_text(encoding="utf-8")


class TestAutoRebootService(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = [
        "0002-lenos-first-boot-defaults.patch",
        "0003-lenos-auto-reboot.patch",
    ]
    SERVICE = "services/core/java/com/android/server/LenosAutoRebootService.java"
    SYSTEM_SERVER = "services/java/com/android/server/SystemServer.java"
    DB = "packages/SettingsProvider/src/com/android/providers/settings/DatabaseHelper.java"

    def test_java_still_parses(self):
        self.assert_java_syntax(self.SERVICE)
        self.assert_java_syntax(self.SYSTEM_SERVER)

    def test_started_by_system_server_after_alarm_manager(self):
        self.assert_contains(
            self.SYSTEM_SERVER,
            "StartLenosAutoRebootService",
            "mSystemServiceManager.startService(LenosAutoRebootService.class);",
        )
        # The service schedules through AlarmManager, so it must come later.
        body = self.text(self.SYSTEM_SERVER)
        self.assertLess(body.index("StartAlarmManagerService"),
                        body.index("StartLenosAutoRebootService"))

    def test_setting_key_is_identical_everywhere(self):
        needle = '"lenos_auto_reboot_timeout_ms"'
        self.assert_contains(self.SERVICE, "SETTING_AUTO_REBOOT_TIMEOUT_MS", needle)
        self.assert_contains(self.DB, needle)
        self.assertIn(needle, read_vendor(APP))

    def test_rom_default_is_18_hours_everywhere(self):
        self.assert_contains(self.SERVICE, "DEFAULT_TIMEOUT_MS = 64_800_000")
        self.assertIn("BFU_DEFAULT_MS = 64_800_000", read_vendor(APP))
        self.assertIn(
            '<integer name="def_lenos_auto_reboot_timeout_ms">64800000</integer>',
            read_vendor(RRO))

    def test_timer_arms_at_screen_off_and_disarms_on_unlock(self):
        self.assert_contains(
            self.SERVICE,
            "case Intent.ACTION_SCREEN_OFF:",
            "armTimer();",
            "case Intent.ACTION_USER_PRESENT:",
            "disarmTimer();",
        )

    def test_zero_disables_the_timer(self):
        self.assert_contains(self.SERVICE, "if (value == 0)", "return 0;")

    def test_out_of_range_values_fall_back_to_the_default(self):
        self.assert_contains(
            self.SERVICE,
            "MIN_TIMEOUT_MS = 600_000",
            "MAX_TIMEOUT_MS = 259_200_000",
            "value < MIN_TIMEOUT_MS || value > MAX_TIMEOUT_MS",
        )

    def test_reboot_requires_a_secured_locked_device(self):
        self.assert_contains(
            self.SERVICE,
            "isDeviceSecure()",
            "isKeyguardLocked()",
            "if (!isSecureLockEngaged())",
        )

    def test_call_in_progress_defers_the_reboot(self):
        self.assert_contains(
            self.SERVICE,
            "android.telecom.TelecomManager",
            "telecom.isInCall()",
            "IN_CALL_RETRY_MS",
        )

    def test_reboot_goes_through_power_manager_with_a_lenos_reason(self):
        self.assert_contains(
            self.SERVICE,
            '"lenos-auto-reboot"',
            "powerManager.reboot(REBOOT_REASON);",
        )

    def test_alarm_is_exact_wakeup_and_private(self):
        self.assert_contains(
            self.SERVICE,
            "AlarmManager.ELAPSED_REALTIME_WAKEUP",
            "setExactAndAllowWhileIdle",
            "PendingIntent.FLAG_IMMUTABLE",
            ".setPackage(mContext.getPackageName())",
        )

    def test_setting_changes_take_effect_without_a_relock(self):
        self.assert_contains(
            self.SERVICE,
            "registerContentObserver(",
            "Settings.Global.getUriFor(SETTING_AUTO_REBOOT_TIMEOUT_MS)",
        )


class TestAutoRebootProductWiring(unittest.TestCase):
    def test_backend_status_prop_is_framework(self):
        self.assertIn("ro.lenos.security.auto_bfu=framework",
                      read_vendor("config/lenos.mk"))

    def test_app_writes_and_reads_the_same_int_setting(self):
        app = read_vendor(APP)
        self.assertIn(
            "Settings.Global.putInt(getContentResolver(), BFU_SETTING, value)", app)
        self.assertIn(
            "Settings.Global.getInt(getContentResolver(), BFU_SETTING, BFU_DEFAULT_MS)",
            app)

    def test_app_choices_cover_the_service_range(self):
        app = read_vendor(APP)
        self.assertIn("BFU_CHOICES.put(0, \"Off\")", app)
        self.assertIn("BFU_CHOICES.put(600_000,", app)
        self.assertIn("BFU_CHOICES.put(259_200_000,", app)


if __name__ == "__main__":
    unittest.main()

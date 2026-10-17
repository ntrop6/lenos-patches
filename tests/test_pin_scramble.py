"""Default PIN-scramble (lineage-sdk LineageSettingsProvider + device overlay).

Feature contract (see docs/features.md):
* On a fresh install the lock screen PIN keypad is scrambled, so shoulder
  surfing reveals neither the digits nor their positions.
* The scramble stays a normal user setting: turning it off in Settings keeps
  the value off (INSERT OR IGNORE default, never rewritten).
* Stock LineageOS keeps its own default (off); lenOS turns it on through the
  device overlay resource.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestPinScrambleDefault(LenosPatchTest):
    PROJECT = "lineage-sdk"
    PATCHES = ["0001-pin-scramble-default.patch"]
    DB = ("packages/LineageSettingsProvider/src/org/lineageos/lineagesettings/"
          "LineageDatabaseHelper.java")
    XML = "packages/LineageSettingsProvider/res/values/defaults.xml"

    def test_still_syntactically_valid_java(self):
        self.assert_java_syntax(self.DB)

    def test_xml_is_well_formed(self):
        self.assert_xml(self.XML)

    def test_default_is_loaded_into_the_system_namespace(self):
        # The reader (KeyguardPinViewController, PinScramblePreferenceController)
        # uses LineageSettings.System.LOCKSCREEN_PIN_SCRAMBLE_LAYOUT.
        self.assert_contains(
            self.DB,
            "loadBooleanSetting(stmt, LineageSettings.System.LOCKSCREEN_PIN_SCRAMBLE_LAYOUT,\n"
            "                    R.bool.def_lockscreen_pin_scramble_layout);",
        )

    def test_stock_default_stays_off(self):
        self.assert_contains(
            self.XML,
            '<bool name="def_lockscreen_pin_scramble_layout">false</bool>',
        )


class TestPinScrambleDeviceOverlay(LenosPatchTest):
    PROJECT = "device/nothing/asteroids"
    PATCHES = ["0005-pin-scramble-default.patch"]
    XML = ("overlay-lineage/lineage-sdk/packages/LineageSettingsProvider/"
           "res/values/defaults.xml")

    def test_xml_is_well_formed(self):
        self.assert_xml(self.XML)

    def test_lenos_turns_scrambling_on(self):
        self.assert_contains(
            self.XML,
            '<bool name="def_lockscreen_pin_scramble_layout">true</bool>',
        )


if __name__ == "__main__":
    unittest.main()

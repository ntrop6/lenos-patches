"""PIN-entry scrambling (GrapheneOS-faithful port).

Feature contract (see docs/features.md):
* The PIN pad is scrambled with java.security.SecureRandom whenever it is set
  up, so shoulder surfing reveals neither the digits nor their positions; the
  digit -> view map keeps hardware-key presses on the correct shuffled key.
* The keyguard PIN honours ExtSettings.SCRAMBLE_LOCKSCREEN_PIN_LAYOUT_PRIMARY;
  SIM PIN/PUK views use SCRAMBLE_SIM_PIN_LAYOUT, which inherits the keyguard
  value by default.
* lenOS hardening deviation (documented): the primary scramble default is ON,
  where GrapheneOS ships the toggle default-OFF. The value stays a normal
  Settings.Secure user setting, exposed through GrapheneOS's
  PinScramblingPrefController and the SIM switch in the ICC lock screen.
* The old LineageOS scramble implementation (KeyguardPINView +
  LineageSettings.System.LOCKSCREEN_PIN_SCRAMBLE_LAYOUT) is fully replaced.
"""
from __future__ import annotations

import re
import unittest

from harness import LenosPatchTest


class TestPinScrambleSetting(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0006-lenos-ext-settings.patch"]
    EXT = "core/java/android/ext/settings/ExtSettings.java"
    SETTINGS = "core/java/android/provider/Settings.java"

    def test_java_still_parses(self):
        self.assert_java_syntax(self.EXT)
        self.assert_java_syntax(self.SETTINGS)

    def test_secure_keys_match_grapheneos(self):
        self.assert_contains(
            self.SETTINGS,
            '"lockscreen_scramble_pin_layout"',
            '"lockscreen_scramble_pin_layout_secondary"',
            '"scramble_sim_pin_layout"',
        )

    def test_primary_default_is_on_for_lenos(self):
        body = self.text(self.EXT)
        m = re.search(
            r"SCRAMBLE_LOCKSCREEN_PIN_LAYOUT_PRIMARY = new BoolSetting\((.*?)\);",
            body, re.S)
        self.assertIsNotNone(m, "primary scramble setting missing")
        args = m.group(1)
        self.assertIn("Settings.Secure.SCRAMBLE_PIN_LAYOUT_PRIMARY", args)
        self.assertRegex(args, r"\btrue\s*$")
        self.assertIn("lenOS: scrambled PIN layout is on by default", args)

    def test_sim_layout_inherits_the_keyguard_setting(self):
        body = self.text(self.EXT)
        m = re.search(r"SCRAMBLE_SIM_PIN_LAYOUT = new BoolSetting\((.*?)\);",
                      body, re.S)
        self.assertIsNotNone(m, "SIM scramble setting missing")
        self.assertIn("SCRAMBLE_LOCKSCREEN_PIN_LAYOUT_PRIMARY::get", m.group(1))


class TestPinScrambleSystemUi(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0008-lenos-pin-scramble.patch"]
    BASE_VIEW = "packages/SystemUI/src/com/android/keyguard/KeyguardPinBasedInputView.java"
    BASE_VC = ("packages/SystemUI/src/com/android/keyguard/"
               "KeyguardPinBasedInputViewController.java")
    PIN_VIEW = "packages/SystemUI/src/com/android/keyguard/KeyguardPINView.java"
    PIN_VC = "packages/SystemUI/src/com/android/keyguard/KeyguardPinViewController.java"

    def test_java_still_parses(self):
        for rel in (self.BASE_VIEW, self.BASE_VC, self.PIN_VIEW, self.PIN_VC):
            self.assert_java_syntax(rel)

    def test_shuffle_uses_securerandom(self):
        self.assert_contains(
            self.BASE_VIEW,
            "private final SecureRandom secureRandom = new SecureRandom();",
            "Collections.shuffle(digits, secureRandom);",
            "buttons[i].setDigit(digit);",
        )

    def test_hardware_keys_hit_the_shuffled_key(self):
        self.assert_contains(
            self.BASE_VIEW,
            "mButtons[digitToViewIndexMap[number]].performClick();",
            "digitToViewIndexMap[digit] = i;",
        )
        self.assert_not_contains(self.BASE_VIEW, "getNumberIndex")

    def test_keypad_is_always_remapped_on_setup(self):
        # setupPinScrambling rebuilds the digit->view map even when scrambling
        # is disabled, so hardware keys stay correct in both modes.
        self.assert_contains(
            self.BASE_VC,
            "view.setupPinScrambling(setting.get(ctx, userId));",
        )

    def test_keyguard_pin_reads_the_primary_setting(self):
        self.assert_contains(
            self.BASE_VC,
            "this instanceof KeyguardPinViewController",
            "ExtSettings.SCRAMBLE_LOCKSCREEN_PIN_LAYOUT_PRIMARY",
        )

    def test_sim_views_read_the_sim_setting(self):
        self.assert_contains(self.BASE_VC, "ExtSettings.SCRAMBLE_SIM_PIN_LAYOUT")

    def test_lineage_scramble_is_gone(self):
        self.assert_not_contains(
            self.PIN_VIEW,
            "mScramblePin",
            "updatePinScrambling",
            "shuffle(mNumbers)",
        )
        self.assert_not_contains(
            self.PIN_VC,
            "LineageSettings",
            "LOCKSCREEN_PIN_SCRAMBLE_LAYOUT",
            "updatePinScrambling",
        )


class TestPinScrambleSettingsUi(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = ["0001-lenos-pin-scramble-ui.patch"]
    PICKER = "res/xml/security_settings_picker.xml"
    SIM_XML = "res/xml/sim_lock_settings.xml"
    STRINGS = "res/values/strings_ext.xml"
    CONTROLLER = ("src/com/android/settings/security/screenlock/"
                  "PinScramblingPrefController.java")
    BOOL_CONTROLLER = "src/com/android/settings/ext/BoolSettingPrefController.java"
    CHOOSE = "src/com/android/settings/password/ChooseLockGeneric.java"
    ICC = "src/com/android/settings/IccLockSettings.java"

    def test_java_still_parses(self):
        for rel in (self.CONTROLLER, self.BOOL_CONTROLLER, self.CHOOSE, self.ICC):
            self.assert_java_syntax(rel)

    def test_xml_files_are_well_formed(self):
        for rel in (self.PICKER, self.SIM_XML, self.STRINGS):
            self.assert_xml(rel)

    def test_picker_offers_the_scramble_switch(self):
        self.assert_contains(
            self.PICKER,
            'android:key="scramble_pin_layout"',
            'android:title="@string/scramble_pin_title"',
        )

    def test_lineage_ui_is_gone(self):
        self.assert_not_contains(
            self.PICKER,
            "lockscreen_scramble_pin_layout",
            "unlock_scramble_pin_layout",
        )
        self.assert_not_contains(self.CHOOSE, "PinScramblePreferenceController")

    def test_choose_lock_registers_the_controller(self):
        self.assert_contains(
            self.CHOOSE,
            "new PinScramblingPrefController(",
            "UserHandle.of(mUserId)",
        )

    def test_controller_only_shows_for_pin_credentials(self):
        self.assert_contains(
            self.CONTROLLER,
            "getCredentialTypeForUser(user.getIdentifier())",
            "LockPatternUtils.CREDENTIAL_TYPE_PIN",
            "CONDITIONALLY_UNAVAILABLE",
        )

    def test_sim_lock_screen_has_the_switch(self):
        self.assert_contains(
            self.SIM_XML,
            'android:key="sim_scramble_pin_layout"',
            'android:dependency="sim_toggle"',
        )
        self.assert_contains(
            self.ICC,
            "ExtSettings.SCRAMBLE_SIM_PIN_LAYOUT.put(requireContext(), (boolean) newValue);",
            "mPinScramblingToggle.setChecked("
            "ExtSettings.SCRAMBLE_SIM_PIN_LAYOUT.get(requireContext()));",
        )

    def test_string_is_available(self):
        self.assert_contains(
            self.STRINGS,
            '<string name="scramble_pin_title">Scramble PIN input layout</string>',
        )


if __name__ == "__main__":
    unittest.main()

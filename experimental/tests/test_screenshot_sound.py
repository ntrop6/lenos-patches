"""Screenshot sound follows the system sound-effects setting (Tier 2 #25).

GrapheneOS removes the `screenshotForceShutterSound` aconfig gate around the
non-forced screenshot sound and gates it on `Settings.System.SOUND_EFFECTS_ENABLED`
instead. lenOS evaluates the forced-shutter path first so a mandatory shutter
sound is never suppressed by the touch-sounds setting; the non-forced path is
the only one gated.
"""
from __future__ import annotations

import unittest

from harness import PATCH_ROOT, VENDOR, LenosPatchTest, patch_paths

PATCH = "0002-screenshot-sound-settings.patch"
ALIAS = "frameworks_base"
CONTROLLER = ("packages/SystemUI/src/com/android/systemui/screenshot/"
              "ScreenshotSoundController.kt")
POLICY = ("packages/SystemUI/src/com/android/systemui/screenshot/"
          "ScreenshotSoundPolicy.kt")
CONTROLLER_TEST = ("packages/SystemUI/multivalentTests/src/com/android/systemui/"
                   "screenshot/ScreenshotSoundControllerTest.kt")
POLICY_TEST = ("packages/SystemUI/multivalentTests/src/com/android/systemui/"
               "screenshot/ScreenshotSoundPolicyTest.kt")


class TestScreenshotSound(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = [PATCH]

    def test_patch_is_limited_to_the_screenshot_sound_classes_and_their_tests(self):
        patch = PATCH_ROOT / ALIAS / PATCH
        self.assertEqual(
            sorted(patch_paths(patch)),
            sorted([CONTROLLER, POLICY, CONTROLLER_TEST, POLICY_TEST]),
        )

    def test_existing_tests_are_updated_to_the_new_constructor(self):
        self.assert_contains(
            CONTROLLER_TEST,
            "FakeSystemSettingsRepository",
            "fakeSystemSettingsRepo.setInt(Settings.System.SOUND_EFFECTS_ENABLED, 1)",
            "fakeSystemSettingsRepo.setInt(Settings.System.SOUND_EFFECTS_ENABLED, 0)",
            "soundEffectsDisabled_noSoundPlays",
            "screenshotSoundForced_ignoresSoundEffectsSetting",
            "ScreenshotSoundControllerImpl(",
            "fakeSystemSettingsRepo,",
        )
        self.assert_contains(
            POLICY_TEST,
            "ScreenshotSoundPolicy(",
            "testDispatcher,",
            "testScope,",
            "onBlocking { mustPlayShutterSound() }",
        )
        self.assert_not_contains(
            POLICY_TEST,
            "FLAG_SCREENSHOT_FORCE_SHUTTER_SOUND",
            "Flags.FLAG_SCREENSHOT_FORCE_SHUTTER_SOUND",
        )

    def test_controller_gates_only_the_non_forced_sound(self):
        body = self.text(CONTROLLER)
        force = body.index("if (soundPolicy.shouldForceShutterSound())")
        check = body.index("Settings.System.SOUND_EFFECTS_ENABLED")
        player = body.index("player.await()?.start()")
        self.assertLess(force, check)
        self.assertLess(check, player)
        self.assertIn("return@withContext", body[check:player])

    def test_policy_no_longer_uses_the_aconfig_gate(self):
        self.assert_not_contains(POLICY, "screenshotForceShutterSound")
        self.assert_not_contains(POLICY, "Flags.screenshotForceShutterSound")

    def test_forced_shutter_region_is_unchanged(self):
        self.assert_contains(
            POLICY,
            "suspend fun shouldForceShutterSound(): Boolean",
            "shutterPolicy.mustPlayShutterSound() && cameraOpen",
            "MediaActionSound.mustPlayShutterSound()",
        )

    def test_camera_availability_callback_is_registered_unconditionally(self):
        body = self.text(POLICY)
        self.assertIn("applicationScope.launch(bgDispatcher)", body)
        self.assertIn("registerAvailabilityCallback", body)
        # The old aconfig guard around registration is gone.
        self.assertNotIn("if (screenshotForceShutterSound())", body)

    def test_constructor_and_types_are_consistent(self):
        self.assert_contains(
            POLICY,
            "@Background private val bgDispatcher: CoroutineDispatcher",
            "@Application private val applicationScope: CoroutineScope",
            "suspend fun mustPlayShutterSound(): Boolean",
            "withContext(bgDispatcher) { MediaActionSound.mustPlayShutterSound() }",
        )
        self.assert_contains(
            CONTROLLER,
            "private val systemSettings: com.android.systemui.shared.settings.data.repository.SystemSettingsRepository",
        )
        self.assert_balanced(POLICY)
        self.assert_balanced(CONTROLLER)
        self.assert_balanced(POLICY_TEST)
        self.assert_balanced(CONTROLLER_TEST)
        self.assert_not_contains(
            CONTROLLER_TEST,
            "whenever(soundPolicy.shouldForceShutterSound())",
        )


if __name__ == "__main__":
    unittest.main()

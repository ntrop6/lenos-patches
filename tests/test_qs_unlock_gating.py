"""Quick settings unlock gating (frameworks/base SystemUI patch).

Feature contract (see docs/features.md):
* While the device shows a secure lock screen, quick settings tiles do not
  act: tapping (or long-pressing) a tile only shows "Unlock the device to use
  quick settings". A locked device therefore cannot be used to toggle radios
  or connectivity, e.g. airplane mode to break remote tracking/wipe.
* The flashlight and camera-toggle tiles stay usable on the lock screen: they
  touch no radios/data and stay useful in an emergency.
* Devices without a secure lock, and the normal unlocked case, are unaffected
  — the gate keys off KeyguardManager#isDeviceSecure + isKeyguardLocked.
* Stock paths are preserved: policy-disabled tiles still open the
  admin-support dialog first, and metrics/logging still run for allowed
  clicks only (no logging of blocked actions).
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestQsUnlockGating(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0004-lenos-qs-unlock-gating.patch"]
    QTILE = "packages/SystemUI/src/com/android/systemui/qs/tileimpl/QSTileImpl.java"
    STRINGS = "packages/SystemUI/res/values/strings.xml"

    def test_java_and_xml_still_parse(self):
        self.assert_java_syntax(self.QTILE)
        self.assert_xml(self.STRINGS)

    def test_all_interactions_are_gated(self):
        # Primary click, secondary click and long click go through the gate.
        self.assertEqual(3, self.text(self.QTILE).count("if (requiresUnlock()) {"),
                         "every click path must be gated")

    def test_gate_keys_off_a_secure_locked_device(self):
        self.assert_contains(
            self.QTILE,
            "final KeyguardManager keyguard = mContext.getSystemService(KeyguardManager.class);",
            "keyguard.isDeviceSecure() && keyguard.isKeyguardLocked()",
        )

    def test_flashlight_and_camera_stay_usable(self):
        self.assert_contains(
            self.QTILE,
            "LENOS_LOCKED_ALLOWED_TILES",
            "Set.of(FlashlightTile.TILE_SPEC, CameraToggleTile.TILE_SPEC)",
            "import com.android.systemui.qs.tiles.CameraToggleTile;",
            "import com.android.systemui.qs.tiles.FlashlightTile;",
        )

    def test_policy_disabled_tiles_keep_the_stock_dialog(self):
        body = self.text(self.QTILE)
        self.assertLess(body.index("if (mState.disabledByPolicy)"),
                        body.index("} else if (requiresUnlock()) {"),
                        "the admin-support path must come before the unlock gate")

    def test_blocked_actions_are_not_logged_and_do_not_run(self):
        body = self.text(self.QTILE)
        for needle in (
            "mQSLogger.logHandleClick(mTileSpec, msg.arg1);",
            "mQSLogger.logHandleSecondaryClick(mTileSpec, msg.arg1);",
            "mQSLogger.logHandleLongClick(mTileSpec, msg.arg1);",
            "handleClick((Expandable) msg.obj);",
            "handleSecondaryClick((Expandable) msg.obj);",
            "handleLongClick((Expandable) msg.obj);",
        ):
            self.assertIn(needle, body)
            # each logging/handler call must sit after a requiresUnlock check
            self.assertGreater(body.index(needle), body.index("requiresUnlock()"))

    def test_non_click_messages_are_untouched(self):
        body = self.text(self.QTILE)
        for needle in ("handleRefreshState(msg.obj);", "handleUserSwitch(msg.arg1);",
                       "handleStale();", "handleDestroy();"):
            self.assertIn(needle, body)

    def test_user_gets_feedback(self):
        self.assert_contains(
            self.QTILE,
            "private void showUnlockRequired()",
            "Toast.makeText(mContext, R.string.lenos_qs_unlock_required, "
            "Toast.LENGTH_SHORT).show();",
            "import com.android.systemui.res.R;",
        )

    def test_string_resource_matches_the_toast(self):
        self.assert_contains(
            self.STRINGS,
            '<string name="lenos_qs_unlock_required">Unlock the device to use '
            'quick settings</string>',
        )


if __name__ == "__main__":
    unittest.main()

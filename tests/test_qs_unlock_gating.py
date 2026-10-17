"""Quick settings unlock gating (frameworks/base SystemUI patch).

Feature contract (see docs/features.md), ported from GrapheneOS:
* Every tile action (click, secondary click, long click) is routed through
  QSTileImpl#handleAction. Tiles opt in to lock-screen use by overriding
  isAllowedWhenLocked; the default is "not allowed".
* When a secure keyguard is showing, a non-allowed action does not run and
  is not silently dropped: the keyguard is dismissed with
  ActivityStarter#postQSRunnableDismissingKeyguard, so the user is asked to
  authenticate and the action runs only after a successful unlock.
* Devices without a secure lock, and the normal unlocked case, are
  unaffected.
* The allow-list matches GrapheneOS: flashlight (incl. brightness-level
  variant), QR code scanner, color inversion, color correction, Night Light,
  reduce bright colors, dark theme, rotation lock, battery saver or device
  controls. Sensitive tiles (radios, connectivity, camera, hotspot, DND,
  data saver) are deliberately not allow-listed.
* Stock paths are preserved: policy-disabled tiles still open the
  admin-support dialog first, and metrics logging still happens before the
  gate, as upstream.
"""
from __future__ import annotations

import unittest

from harness import VENDOR, LenosPatchTest

JAVA_TILES = (
    "BatterySaverTile.java",
    "ColorCorrectionTile.java",
    "ColorInversionTile.java",
    "FlashlightTile.java",
    "NightDisplayTile.java",
    "QRCodeScannerTile.java",
    "ReduceBrightColorsTile.java",
    "RotationLockTile.java",
    "UiModeNightTile.java",
)
KOTLIN_TILES = (
    "DeviceControlsTile.kt",
    "FlashlightTileWithLevel.kt",
)
SENSITIVE_TILES = (
    "WifiTile.java",
    "BluetoothTile.java",
    "CameraToggleTile.java",
    "AirplaneModeTile.java",
    "DndTile.java",
    "DataSaverTile.java",
    "HotspotTile.java",
)


class TestQsUnlockGating(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0004-lenos-qs-unlock-gating.patch"]
    QTILE = "packages/SystemUI/src/com/android/systemui/qs/tileimpl/QSTileImpl.java"
    QSHOST = "packages/SystemUI/src/com/android/systemui/qs/QSHost.java"
    ADAPTER = "packages/SystemUI/src/com/android/systemui/qs/QSHostAdapter.kt"
    TILES = "packages/SystemUI/src/com/android/systemui/qs/tiles/"

    def test_java_still_parses(self):
        self.assert_java_syntax(self.QTILE)
        self.assert_java_syntax(self.QSHOST)
        for name in JAVA_TILES:
            self.assert_java_syntax(self.TILES + name)

    def test_all_action_paths_route_through_the_gate(self):
        self.assert_contains(
            self.QTILE,
            "handleAction(Action.CLICK, () -> handleClick(view));",
            "handleAction(Action.SECONDARY_CLICK, () -> handleSecondaryClick(view));",
            "handleAction(Action.LONG_CLICK, () -> handleLongClick(view));",
        )

    def test_gate_requires_unlock_on_a_secure_keyguard(self):
        self.assert_contains(
            self.QTILE,
            "public boolean isAllowedWhenLocked(Action action) {\n"
            "        return false;\n"
            "    }",
            "KeyguardStateController ksc = mHost.getKeyguardStateController();",
            "boolean hasSecureKeyguard = ksc.isMethodSecure() && ksc.isShowing();",
            "mActivityStarter.postQSRunnableDismissingKeyguard(handler);",
        )

    def test_logging_still_runs_before_the_gate(self):
        body = self.text(self.QTILE)
        for log, action in (
            ("mQSLogger.logHandleClick(mTileSpec, msg.arg1);",
             "handleAction(Action.CLICK"),
            ("mQSLogger.logHandleSecondaryClick(mTileSpec, msg.arg1);",
             "handleAction(Action.SECONDARY_CLICK"),
            ("mQSLogger.logHandleLongClick(mTileSpec, msg.arg1);",
             "handleAction(Action.LONG_CLICK"),
        ):
            self.assertIn(log, body)
            self.assertLess(body.index(log), body.index(action),
                            f"{log} must come before the gate, as upstream")

    def test_policy_disabled_tiles_keep_the_stock_dialog(self):
        self.assert_contains(
            self.QTILE,
            "if (mState.disabledByPolicy) {",
            "mActivityStarter.postStartActivityDismissingKeyguard(intent, 0);",
        )

    def test_no_toast_leftovers(self):
        patch = VENDOR / "patches/frameworks_base/0004-lenos-qs-unlock-gating.patch"
        patch_text = patch.read_text(encoding="utf-8")
        for needle in ("lenos_qs_unlock_required", "showUnlockRequired",
                       "Toast.makeText", "LENOS_LOCKED_ALLOWED_TILES"):
            self.assertNotIn(needle, patch_text)
        self.assert_not_contains(self.QTILE, "showUnlockRequired", "Toast.makeText")

    def test_host_exposes_keyguard_state(self):
        self.assert_contains(
            self.QSHOST,
            "com.android.systemui.statusbar.policy.KeyguardStateController "
            "getKeyguardStateController();",
        )
        self.assert_contains(
            self.ADAPTER,
            "private val keyguardStateController_: KeyguardStateController,",
            "override fun getKeyguardStateController() = keyguardStateController_",
        )

    def test_allowlisted_tiles_match_grapheneos(self):
        for name in JAVA_TILES:
            self.assert_contains(
                self.TILES + name,
                "@Override\n"
                "    public boolean isAllowedWhenLocked(QSTileImpl.Action action) {\n"
                "        return true;\n"
                "    }",
            )
        for name in KOTLIN_TILES:
            self.assert_contains(
                self.TILES + name,
                "override fun isAllowedWhenLocked(action: QSTileImpl.Action): Boolean = true",
            )

    def test_sensitive_tiles_are_not_allowlisted(self):
        patch = VENDOR / "patches/frameworks_base/0004-lenos-qs-unlock-gating.patch"
        patch_text = patch.read_text(encoding="utf-8")
        for name in SENSITIVE_TILES:
            self.assertNotIn(name, patch_text,
                             f"{name} must not be allow-listed on the lock screen")


if __name__ == "__main__":
    unittest.main()

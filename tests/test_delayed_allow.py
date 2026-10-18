"""Delayed Allow buttons in permission and USB-debugging dialogs.

Feature contract (GrapheneOS-faithful port; see docs/graphene-porting.md
section 9):

* Runtime permission dialogs: every allow variant (``ALLOW_BUTTON``,
  ``ALLOW_ALWAYS_BUTTON``, ``ALLOW_FOREGROUND_BUTTON``,
  ``ALLOW_ONE_TIME_BUTTON``, ``ALLOW_ALL_BUTTON``, ``ALLOW_SELECTED_BUTTON``)
  is disabled and re-enabled after one second via ``postDelayed``, so an
  accidental tap cannot confirm a grant instantly. Deny/Cancel stay
  immediate.
* USB debugging authorization: the Allow button is likewise re-enabled
  after one second.

Adaptations vs GrapheneOS (documented in the porting inventory): the
permission handler's debug log omits the app package, which this branch no
longer passes into the handheld handler.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestDelayedPermissionAllow(LenosPatchTest):
    PROJECT = "packages/modules/Permission"
    PATCHES = ["0001-lenos-delay-permission-allow.patch"]

    ACT = ("PermissionController/src/com/android/permissioncontroller/"
           "permission/ui/GrantPermissionsActivity.java")
    KT = ("PermissionController/src/com/android/permissioncontroller/"
          "permission/ui/handheld/GrantPermissionsViewHandlerImpl.kt")

    def test_all_allow_variants_recognised(self):
        self.assert_contains(
            self.ACT,
            "public static boolean isAllowButton(int id) {",
            "case ALLOW_BUTTON:",
            "case ALLOW_ALWAYS_BUTTON:",
            "case ALLOW_FOREGROUND_BUTTON:",
            "case ALLOW_ONE_TIME_BUTTON:",
            "case ALLOW_ALL_BUTTON:",
            "case ALLOW_SELECTED_BUTTON:")
        self.assert_java_syntax(self.ACT)

    def test_dialog_gates_allow_buttons(self):
        self.assert_contains(
            self.KT,
            "import android.util.Log",
            "GrantPermissionsActivity.isAllowButton(pos)",
            "button.isEnabled = false",
            "button.postDelayed(action, 1000)")
        # the old immediate-visibility assignment is gone
        self.assert_not_contains(self.KT, "buttons[pos]?.visibility")

    def test_deny_path_unchanged(self):
        self.assert_contains(
            self.KT,
            "if ((pos == DENY_BUTTON || pos == DENY_AND_DONT_ASK_AGAIN_BUTTON)) {")


class TestDelayedUsbAllow(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0014-lenos-delay-usb-adb-allow.patch"]

    F = "packages/SystemUI/src/com/android/systemui/usb/UsbDebuggingActivity.java"

    def test_usb_prompt_gates_allow(self):
        self.assert_contains(
            self.F,
            "import android.widget.Button;",
            "mAlert.getButton(DialogInterface.BUTTON_POSITIVE)",
            "allowButton.setEnabled(false);",
            "getMainThreadHandler().postDelayed(() -> allowButton.setEnabled(true), 1000);")
        self.assert_java_syntax(self.F)

    def test_always_allow_checkbox_unchanged(self):
        self.assert_contains(self.F, "mAlwaysAllow.setText(getString(R.string.usb_debugging_always));")


if __name__ == "__main__":
    unittest.main()

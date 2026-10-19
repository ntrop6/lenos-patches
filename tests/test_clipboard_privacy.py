"""Clipboard privacy: Secure Paste stage 1 and cross-profile clipboard policy.

Feature contracts (GrapheneOS ports; see docs/graphene-porting.md sections 8,
14 and 18):

* Secure Paste stage 1. When ``ExtSettings.ALLOW_CLIPBOARD_READ_BY_DEFAULT`` is
  off, a package may only read clipboard content it owns. The default IME and
  system apps keep access, and a denied reader still gets the mime types (with
  the label stripped) so paste affordances do not disappear. Stage 1 exposes
  the global default only; GrapheneOS's per-app ``GosPackageState`` switch and
  the SystemUI paste toolbar are follow-ups.
* Cross-profile shared clipboard. The per-user Secure setting
  ``cross_profile_clipboard_access`` (GrapheneOS literal) gates exports in
  ``setPrimaryClipInternalLocked``, imports for each related profile, and
  cross-profile drag-and-drop. Default is ``FOLLOW_DEFAULT`` (stock Android
  behaviour), so the feature is opt-in.

The two features share ``ClipboardService.java`` but are separate patches;
each test class applies only its own patch, which also proves the hunks were
split correctly.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestSecurePaste(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0015-lenos-secure-paste.patch"]

    CLIP = "services/core/java/com/android/server/clipboard/ClipboardService.java"

    def test_gate_uses_gos_setting(self):
        self.assert_contains(
            self.CLIP,
            "import android.ext.settings.ExtSettings;",
            "return ExtSettings.ALLOW_CLIPBOARD_READ_BY_DEFAULT.get(getContext());",
            "private boolean clipboardReadAllowedForPackage(")

    def test_clip_owner_and_default_ime_exempt(self):
        self.assert_contains(
            self.CLIP,
            "if (isDefaultIme) {",
            "private static boolean isClipOwnerLocked(",
            "clipboard.primaryClipUid == uid;")

    def test_read_paths_enforce(self):
        self.assert_contains(
            self.CLIP,
            "final boolean readAllowedForPackage = clipboardReadAllowedForPackage(",
            "if (!readAllowedForPackage && !isClipOwnerLocked(clipboard, intendingUid))",
            "new ClipDescription(null, mimeTypes)",
            "return descriptionWithoutLabel;")

    def test_denied_read_keeps_presence_signal(self):
        self.assert_contains(
            self.CLIP,
            "does not expose clip content",
            "if (!readAllowedForPackage && !isClipOwnerLocked(clipboard, intendingUid)) {")

    def test_foreign_import_does_not_leak_cross_profile_class(self):
        # The import block belongs to the Secure Paste patch; the cross-profile
        # patch uses fully-qualified names so the two patches stay independent.
        self.assert_not_contains(
            self.CLIP,
            "import android.ext.settings.CrossProfileClipboardAccessSettings;")

    def test_syntax(self):
        self.assert_java_syntax(self.CLIP)


class TestCrossProfileClipboard(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0016-lenos-cross-profile-clipboard.patch"]

    CLIP = "services/core/java/com/android/server/clipboard/ClipboardService.java"
    SETTINGS_CLASS = ("core/java/android/ext/settings/"
                      "CrossProfileClipboardAccessSettings.java")
    DRAG = "services/core/java/com/android/server/wm/DragState.java"

    def test_policy_class_matches_grapheneos(self):
        self.assert_contains(
            self.SETTINGS_CLASS,
            "Settings.Secure.CROSS_PROFILE_CLIPBOARD_ACCESS",
            "public static final int FOLLOW_DEFAULT = 0;",
            "public static final int ALLOW_IMPORT_DEFAULTS_ONLY = 1;",
            "public static final int ALLOW_EXPORT_DEFAULTS_ONLY = 2;",
            "public static final int BLOCK = 3;",
            "public static boolean isExportAccessAllowed(",
            "public static boolean isImportAccessAllowed(")

    def test_export_gate_runs_before_related_profiles(self):
        self.assert_contains(self.CLIP, "isExportAccessAllowed(getContext(), userId)")
        body = self.text(self.CLIP)
        self.assertLess(body.index("isExportAccessAllowed(getContext(), userId)"),
                        body.index("// Update related users"))

    def test_import_gate_is_per_related_profile(self):
        self.assert_contains(self.CLIP, "isImportAccessAllowed(getContext(), id)")

    def test_drag_and_drop_gate(self):
        self.assert_contains(
            self.DRAG,
            "isExportAccessAllowed(mCurrentDisplayContent.mAtmService.mContext,",
            "mCrossProfileCopyAllowed = false;")

    def test_syntax(self):
        self.assert_java_syntax(self.CLIP)
        self.assert_java_syntax(self.SETTINGS_CLASS)
        self.assert_java_syntax(self.DRAG)


class TestClipboardSettingsUi(LenosPatchTest):
    PROJECT = "packages/apps/Settings"
    PATCHES = ["0001-lenos-ext-settings-ui.patch"]

    XML = "res/xml/more_security_privacy_settings.xml"
    STRINGS = "res/values/strings_ext.xml"
    FRAGMENT = ("src/com/android/settings/safetycenter/"
                "MoreSecurityPrivacyFragment.java")

    def test_rows_present(self):
        self.assert_contains(
            self.XML,
            'android:key="privacy_secure_paste"',
            'android:key="privacy_cross_profile_clipboard"',
            "@string/secure_paste_title",
            "@string/cross_profile_clipboard_access_title")
        self.assert_xml(self.XML)

    def test_strings(self):
        self.assert_contains(
            self.STRINGS,
            'name="secure_paste_title"',
            'name="cross_profile_clipboard_access_disallow_title"',
            'name="cross_profile_clipboard_access_allow_import_defaults_summary"')
        self.assert_xml(self.STRINGS)

    def test_controllers_registered(self):
        self.assert_contains(
            self.FRAGMENT,
            "new SecurePastePrefController(context)",
            "new CrossProfileClipboardPrefController(context)",
            "import com.android.settings.ext.SecurePastePrefController;",
            "import com.android.settings.ext.CrossProfileClipboardPrefController;")

    def test_secure_paste_toggle_inverts_gos_default(self):
        self.assert_contains(
            "src/com/android/settings/ext/SecurePastePrefController.java",
            "return !ExtSettings.ALLOW_CLIPBOARD_READ_BY_DEFAULT.get(mContext);",
            "ExtSettings.ALLOW_CLIPBOARD_READ_BY_DEFAULT.put(mContext, !isChecked)")

    def test_cross_profile_controller_uses_gos_setting(self):
        self.assert_contains(
            "src/com/android/settings/ext/CrossProfileClipboardPrefController.java",
            "CROSS_PROFILE_CLIPBOARD_ACCESS_SETTINGS",
            "FOLLOW_DEFAULT",
            "ALLOW_IMPORT_DEFAULTS_ONLY",
            "ALLOW_EXPORT_DEFAULTS_ONLY",
            "BLOCK")


if __name__ == "__main__":
    unittest.main()

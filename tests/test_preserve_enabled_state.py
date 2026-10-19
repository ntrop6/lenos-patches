"""Package updates preserve the enabled setting of the package.

Direct port of GrapheneOS commit ``bff727d`` ("always preserve package enabled
setting after package update", 2026-07-29) plus its feature flag. AOSP
implicitly re-enables packages on update in three places:

* system packages when the updated package is installed for a user,
* the calling user after ``pm install``,
* users that already had the package installed.

That behavior is a user-hostile default: an app the user disabled (or a
component the OEM disabled) silently comes back after an update. GrapheneOS
removed all three implicit re-enable paths; the explicit
``setApplicationEnabledSettingPersistent`` session flag and its plumbing stay
in place (the API is still used by ``PackageInstallerSession``/metrics), but
updates no longer consult the flag — they simply never touch the enabled
state.

The GrapheneOS feature name is kept verbatim so apps that probe
``PackageManager.hasSystemFeature("grapheneos.package_update_preserves_package_enabled_setting")``
behave the same as on GrapheneOS.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestPreserveEnabledState(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0022-lenos-preserve-enabled-state.patch"]

    HELPER = "services/core/java/com/android/server/pm/InstallPackageHelper.java"
    REQUEST = "services/core/java/com/android/server/pm/InstallRequest.java"
    SYSTEM_CONFIG = "services/core/java/com/android/server/SystemConfig.java"
    SESSION = "services/core/java/com/android/server/pm/PackageInstallerSession.java"

    def test_no_implicit_reenable_on_update(self):
        self.assert_not_contains(
            self.HELPER,
            "installRequest.isApplicationEnabledSettingPersistent()",
            "ps.setEnabled(COMPONENT_ENABLED_STATE_DEFAULT,")

    def test_install_request_getter_removed(self):
        self.assert_not_contains(
            self.REQUEST, "public boolean isApplicationEnabledSettingPersistent()")

    def test_feature_flag_matches_grapheneos(self):
        self.assert_contains(
            self.SYSTEM_CONFIG,
            'addFeature("grapheneos.package_update_preserves_package_enabled_setting", 0);')

    def test_unrelated_enable_path_kept(self):
        # The initial system-stub install still has to enable the package.
        self.assert_contains(
            self.HELPER,
            "ps.setEnabled(PackageManager.COMPONENT_ENABLED_STATE_DEFAULT,\n"
            "                        UserHandle.USER_SYSTEM, \"android\");")

    def test_syntax(self):
        for f in (self.HELPER, self.REQUEST, self.SYSTEM_CONFIG):
            self.assert_java_syntax(f)


if __name__ == "__main__":
    unittest.main()

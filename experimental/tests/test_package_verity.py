"""System-app update verification (Tier 2 #20/#21).

These checks are source-level only: the feature needs a built system image and
a reboot to exercise the boot-time scan path. They pin the GrapheneOS-derived
implementation, the two enforcement points, and the patch's file scope.
"""
from __future__ import annotations

import unittest

from harness import PATCH_ROOT, VENDOR, LenosPatchTest, patch_paths

PATCH = "0001-system-app-update-verity.patch"
ALIAS = "frameworks_base"
VERITY = "services/core/java/com/android/server/pm/PackageVerityExt.java"
HELPER = "services/core/java/com/android/server/pm/InstallPackageHelper.java"


class TestSystemAppUpdateVerity(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = [PATCH]

    def test_patch_creates_only_the_verity_helper_and_hooks_the_installer(self):
        patch = PATCH_ROOT / ALIAS / PATCH
        self.assertEqual(sorted(patch_paths(patch)), sorted([HELPER, VERITY]))

    def test_helper_verifies_every_split(self):
        self.assert_contains(
            VERITY,
            "for (AndroidPackageSplit split : pkg.getSplits())",
            "VerityUtils.hasFsverity(apkPath)",
            "APK doesn't have fs-verity: ",
        )

    def test_helper_rejects_same_or_older_system_updates_at_boot(self):
        self.assert_contains(
            VERITY,
            "systemPkg.getLongVersionCode()\n                        >= systemPkgUpdate.getLongVersionCode()",
            "INSTALL_FAILED_UPDATE_INCOMPATIBLE",
            "versionCode of system image package",
        )

    def test_helper_checks_signing_certificate_capability(self):
        self.assert_contains(
            VERITY,
            "updatePkgSigningDetails.checkCapability(systemPkgSigningDetails",
            "SigningDetails.CertCapabilities.INSTALLED_DATA",
            "systemPkgSigningDetails.checkCapability(updatePkgSigningDetails",
            "SigningDetails.CertCapabilities.ROLLBACK",
        )

    def test_boot_scan_registers_immutable_packages_before_data_updates(self):
        self.assert_contains(
            HELPER,
            "if ((scanFlags & SCAN_BOOTING) != 0) {",
            "PackageVerityExt.addSystemPackage(parsedPackage);",
            "PackageVerityExt.checkSystemPackageUpdate(parsedPackage);",
        )

    def test_install_path_checks_fsverity_before_committing(self):
        helper = self.text(HELPER)
        install = helper.index("PackageVerityExt.checkFsVerity(parsedPackage)")
        same_version = helper.index(
            "Not allowed to update system package to the same versionCode")
        self.assertLess(install, same_version,
                        "install-time fs-verity check must precede the versionCode check")

    def test_debug_escape_hatches_are_debuggable_only(self):
        body = self.text(VERITY)
        for prop in (
                "persist.disable_same_versionCode_sys_pkg_update_check",
                "persist.disable_boot_time_fsverity_check"):
            index = body.index(prop)
            # The property must be inside an `if (Build.IS_DEBUGGABLE)` block.
            guard = body.rfind("if (Build.IS_DEBUGGABLE)", 0, index)
            self.assertGreaterEqual(guard, 0, f"{prop} is not guarded by IS_DEBUGGABLE")
            self.assertLess(index - guard, 600,
                            f"{prop} is too far from its IS_DEBUGGABLE guard")

    def test_helper_and_hook_are_valid_java(self):
        self.assert_java_syntax(VERITY)
        self.assert_java_syntax(HELPER)


if __name__ == "__main__":
    unittest.main()

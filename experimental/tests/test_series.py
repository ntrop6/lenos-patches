"""The experimental series must apply after the stable series and stay in sync."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import unittest

from harness import (PATCH_ROOT, STABLE_PATCH_ROOT, VENDOR, build_sandbox,
                     series_for)


class TestExperimentalSeries(unittest.TestCase):
    def test_reset_driver_includes_rename_destinations(self):
        spec = importlib.util.spec_from_file_location(
            "lenos_patch_tool", VENDOR / "tools/lenos-patch.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        patch = (PATCH_ROOT / "packages_apps_Seedvault"
                 / "0001-grapheneos-app-id-prefix.patch")
        created = set(module.created_paths(patch))
        self.assertIn(
            "contactsbackup/default-permissions_app.grapheneos.backup.contacts.xml",
            created)
        self.assertIn(
            "storage/lib/src/main/java/app/grapheneos/backup/storage/restore/FileSplitter.kt",
            created)

    def test_settings_series_applies_in_series_order(self):
        """The Settings patches must apply after stable and in series order."""
        project = "packages/apps/Settings"
        experimental = series_for(project, PATCH_ROOT)
        sandbox = build_sandbox(project, experimental, apply_extra=False)
        self.addCleanup(shutil.rmtree, sandbox, ignore_errors=True)
        for patch in experimental:
            proc = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", str(patch)],
                cwd=sandbox, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0,
                             f"{patch.name} failed after earlier Settings patches:\n"
                             f"{proc.stderr}")

    def test_default_root_has_no_experimental_patches(self):
        for name in (
                "0001-system-app-update-verity.patch",
                "0001-crash-log-viewer.patch",
                "0001-bootloader-unlocked-warning.patch",
                "0001-grapheneos-app-id-prefix.patch",
                "0001-hardened-thread-stacks.patch"):
            self.assertEqual(list(STABLE_PATCH_ROOT.rglob(name)), [], name)


if __name__ == "__main__":
    unittest.main()

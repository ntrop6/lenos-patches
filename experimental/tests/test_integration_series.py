"""Integration checks for the experimental series.

These are deliberately separate from the per-feature tests: they prove that
each patch applies after the stable series, in series order, and independently.
"""
from __future__ import annotations

import shutil
import unittest

from harness import (PATCH_ROOT, STABLE_PATCH_ROOT, build_sandbox,
                     project_for, series_for)


class TestImportedSeries(unittest.TestCase):
    def test_every_experimental_project_applies_after_stable(self):
        projects = set()
        for pdir in sorted(PATCH_ROOT.iterdir()):
            if not pdir.is_dir() or not (pdir / "series").is_file():
                continue
            project = project_for(pdir.name)
            self.assertIsNotNone(project, f"unknown experimental project: {pdir.name}")
            projects.add(project)
            sandbox = build_sandbox(project, series_for(project, PATCH_ROOT))
            self.addCleanup(shutil.rmtree, sandbox, ignore_errors=True)
        self.assertEqual(projects, {
            "frameworks/base", "packages/apps/Settings",
            "packages/apps/SetupWizard", "packages/apps/Seedvault"})

    def test_each_experimental_patch_applies_independently_after_stable(self):
        for pdir in sorted(PATCH_ROOT.iterdir()):
            if not pdir.is_dir() or not (pdir / "series").is_file():
                continue
            project = project_for(pdir.name)
            self.assertIsNotNone(project, f"unknown experimental project: {pdir.name}")
            for patch in series_for(project, PATCH_ROOT):
                sandbox = build_sandbox(project, [patch])
                shutil.rmtree(sandbox, ignore_errors=True)

    def test_no_duplicate_file_blocks_in_a_patch(self):
        # A duplicated new-file diff cannot be reverse-applied, which breaks
        # reset and applied-state checks. Catch it at source level.
        for patch in PATCH_ROOT.rglob("*.patch"):
            seen: dict[tuple[str, str], int] = {}
            for line in patch.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.startswith("diff --git "):
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    key = (parts[2], parts[3])
                    seen[key] = seen.get(key, 0) + 1
            duplicates = {k: n for k, n in seen.items() if n > 1}
            self.assertEqual(duplicates, {}, f"{patch}: duplicate file blocks {duplicates}")

    def test_no_stray_experimental_patches(self):
        for pdir in sorted(PATCH_ROOT.iterdir()):
            if not pdir.is_dir():
                continue
            series_file = pdir / "series"
            self.assertTrue(series_file.is_file(), f"{pdir.name} has no series file")
            listed = {ln.strip() for ln in series_file.read_text().splitlines()
                      if ln.strip() and not ln.strip().startswith("#")}
            present = {f.name for f in pdir.glob("*.patch")}
            self.assertEqual(present - listed, set(),
                             f"{pdir.name}: patches not in series: "
                             f"{sorted(present - listed)}")
            self.assertEqual(listed - present, set(),
                             f"{pdir.name}: series lists missing patches: "
                             f"{sorted(listed - present)}")

    def test_stable_series_is_not_changed_by_import(self):
        self.assertFalse((PATCH_ROOT / "vendor_lenos").exists())
        stable_projects = {d.name for d in STABLE_PATCH_ROOT.iterdir()
                           if (d / "series").is_file()}
        self.assertNotIn("packages_apps_SetupWizard", stable_projects)
        self.assertNotIn("packages_apps_Seedvault", stable_projects)


if __name__ == "__main__":
    unittest.main()

"""The patchkit `--reset` mode: return projects to their pinned revision.

`--reset` exists because plain `git checkout` is not enough to undo a patch
series: files the series *creates* (e.g. the device tree's
`lenos_asteroids.mk`) are untracked, survive a checkout, and then make
`git apply --check` fail forever ("already exists"). `--reset` must restore
tracked files, delete the files the series creates, and verify the result.

These tests build a small git repository from the pinned device tree files,
apply a real patch from the series, and run the real tool against it.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness import VENDOR, WORKSPACE, patch_created_paths, patch_paths

TOOL = VENDOR / "tools" / "lenos-patch.py"
PROJECT = "device/nothing/asteroids"
PATCH_NAME = "0001-add-lenos-product.patch"
PATCH = VENDOR / "patches" / "device_nothing_asteroids" / PATCH_NAME
CREATED = "lenos_asteroids.mk"


def hermetic_env() -> dict:
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_SYSTEM"] = "/dev/null"
    return env


@unittest.skipUnless(WORKSPACE.is_dir(), f"workspace missing: {WORKSPACE}")
class TestPatchkitReset(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lenos-reset-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdir = self.root / PROJECT
        self.pdir.mkdir(parents=True)

        created = patch_created_paths(PATCH)
        for rel in patch_paths(PATCH):
            if rel in created:
                continue  # created by git apply; must not exist beforehand
            src = WORKSPACE / PROJECT / rel
            if not src.is_file():
                continue
            dst = self.pdir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())

        self.git("init", "--quiet")
        self.git("add", "-A")
        self.git("-c", "user.email=lenos@test", "-c", "user.name=lenos",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "pinned")
        self.apply_patch()

    def git(self, *args: str) -> subprocess.CompletedProcess:
        proc = subprocess.run(["git", *args], cwd=self.pdir,
                              capture_output=True, text=True, env=hermetic_env())
        self.assertEqual(proc.returncode, 0, f"git {' '.join(args)}: {proc.stderr}")
        return proc

    def apply_patch(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(PATCH)],
            cwd=self.pdir, capture_output=True, text=True, env=hermetic_env())

    def run_reset(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(TOOL), "--tree", str(self.root),
             "--reset", "--project", PROJECT],
            capture_output=True, text=True, env=hermetic_env())

    def test_reset_removes_created_files_and_restores_tracked(self):
        self.assertTrue((self.pdir / CREATED).is_file(),
                        "the patch should have created the file")
        products = self.pdir / "AndroidProducts.mk"
        products.write_text(products.read_text(encoding="utf-8") + "\n# stray edit\n",
                            encoding="utf-8")

        proc = self.run_reset()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("discarding tracked edits", proc.stdout)
        self.assertIn("AndroidProducts.mk", proc.stdout)
        self.assertFalse((self.pdir / CREATED).exists(),
                         f"--reset must delete the created file {CREATED}")
        self.assertNotIn("# stray edit", products.read_text(encoding="utf-8"))
        status = self.git("status", "--porcelain", "--untracked-files=no")
        self.assertEqual(status.stdout.strip(), "")

    def test_reset_is_idempotent(self):
        self.assertEqual(self.run_reset().returncode, 0)
        again = self.run_reset()
        self.assertEqual(again.returncode, 0, again.stderr)

    def test_reset_then_apply_works_repeatedly(self):
        # The normal cycle: reset -> apply must keep working, not just once.
        for _ in range(2):
            self.assertEqual(self.run_reset().returncode, 0)
            applied = self.apply_patch()
            self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue((self.pdir / CREATED).is_file())

    def test_reset_refuses_when_a_created_file_is_tracked(self):
        # Safety: if the pinned tree already contains a file the series claims
        # to create, something is wrong with the patch set - do not delete blindly.
        self.assertEqual(self.run_reset().returncode, 0)
        (self.pdir / CREATED).write_text("// tracked in the pinned tree\n",
                                         encoding="utf-8")
        self.git("add", CREATED)
        self.git("-c", "user.email=lenos@test", "-c", "user.name=lenos",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "tracked")
        proc = self.run_reset()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("tracked", proc.stderr)
        self.assertTrue((self.pdir / CREATED).is_file(), "must not be deleted")


if __name__ == "__main__":
    unittest.main()

"""Seedvault GrapheneOS app-id prefix and chunker (Tier 2 #27, experimental).

This is the GrapheneOS-specific part of their Seedvault fork, not a jump to
their Android 17 upstream: internal package names get the ``app.grapheneos``
prefix and the prebuilt chunker is replaced by the GrapheneOS build. The
application id stays ``com.stevesoltys.seedvault`` so the LineageOS product
allowlist and existing app identity keep working.

The source-level tests apply the patch to a throwaway shared clone because it
contains renames and a binary jar. This is still not a build or a restore test;
``docs/verification.md`` lists the required device checks.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness import PATCH_ROOT, VENDOR, WORKSPACE

ALIAS = "packages_apps_Seedvault"
PATCH = "0001-grapheneos-app-id-prefix.patch"
PROJECT = "packages/apps/Seedvault"
GOS_CHUNKER_SHA256 = (
    "121735802e8e8c5e558379c9f3cfd5230e1baa60f73cd3905e935d40208148bb"
)


class TestSeedvaultAppIdPrefix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = PATCH_ROOT / ALIAS / PATCH
        cls.tmp = Path(tempfile.mkdtemp(prefix="lenos-seedvault-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, ignore_errors=True)
        cls.repo = cls.tmp / "Seedvault"
        src = WORKSPACE / PROJECT
        if not (src / ".git").is_dir():
            raise unittest.SkipTest(f"workspace project missing: {src}")
        proc = subprocess.run(
            ["git", "clone", "--shared", "--quiet", str(src), str(cls.repo)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr)
        proc = subprocess.run(
            ["git", "apply", "--check", str(cls.patch)],
            cwd=cls.repo, capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(f"Seedvault patch does not apply: {proc.stderr}")
        proc = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(cls.patch)],
            cwd=cls.repo, capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(f"Seedvault patch failed: {proc.stderr}")

    def read(self, rel: str) -> str:
        return (self.repo / rel).read_text(encoding="utf-8", errors="replace")

    def test_internal_packages_use_the_grapheneos_prefix(self):
        self.assertIn(
            'PACKAGE_NAME_CONTACTS = "app.grapheneos.backup.contacts"',
            self.read("app/src/main/java/com/stevesoltys/seedvault/ui/SystemData.kt"))
        self.assertIn(
            "namespace = \"app.grapheneos.seedvault.core\"",
            self.read("core/build.gradle.kts"))
        self.assertIn(
            "namespace = \"app.grapheneos.backup.storage\"",
            self.read("storage/lib/build.gradle.kts"))
        self.assertIn(
            "package app.grapheneos.backup.storage.backup;",
            self.read("storage/lib/src/main/proto/backup_snapshot.proto"))
        self.assertTrue(
            (self.repo / "core/src/main/java/app/grapheneos/seedvault/core/backends/Backend.kt").is_file())
        self.assertFalse(
            (self.repo / "core/src/main/java/org/calyxos/seedvault").exists())

    def test_application_id_is_unchanged(self):
        # Keeping the app id is what makes this compatible with the Lineage
        # allowlist and with an existing Seedvault installation.
        self.assertIn(
            'namespace = "com.stevesoltys.seedvault"',
            self.read("app/build.gradle.kts"))
        self.assertIn(
            'package="com.stevesoltys.seedvault"',
            self.read("app/src/main/AndroidManifest.xml"))

    def test_grapheneos_chunker_binary_is_used(self):
        jar = self.repo / "libs/seedvault-chunker-0.1.jar"
        digest = hashlib.sha256(jar.read_bytes()).hexdigest()
        self.assertEqual(digest, GOS_CHUNKER_SHA256)
        self.assertIn("GIT binary patch", self.patch.read_text(encoding="utf-8"))

    def test_no_old_internal_package_references_remain(self):
        proc = subprocess.run(
            ["grep", "-RIn", "--include=*.kt", "--include=*.java",
             "--include=*.xml", "--include=*.proto", "--include=*.bp",
             "--include=*.kts", "org.calyxos.seedvault", "."],
            cwd=self.repo, capture_output=True, text=True)
        lines = [line for line in proc.stdout.splitlines()
                 if "BASE_SPLIT" not in line]
        self.assertEqual(lines, [])
        proc = subprocess.run(
            ["grep", "-RIn", "--include=*.kt", "--include=*.java",
             "--include=*.xml", "--include=*.proto", "--include=*.bp",
             "--include=*.kts", "org.calyxos.backup", "."],
            cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(proc.stdout.splitlines(), [])

    def test_contacts_backup_permission_file_is_renamed(self):
        self.assertTrue(
            (self.repo / "contactsbackup/default-permissions_app.grapheneos.backup.contacts.xml").is_file())
        self.assertFalse(
            (self.repo / "contactsbackup/default-permissions_org.calyxos.backup.contacts.xml").exists())
        self.assertIn(
            "default-permissions_app.grapheneos.backup.contacts",
            self.read("contactsbackup/Android.bp"))
        self.assertIn(
            'applicationId = "app.grapheneos.backup.contacts"',
            self.read("contactsbackup/build.gradle.kts"))


if __name__ == "__main__":
    unittest.main()

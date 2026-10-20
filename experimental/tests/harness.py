"""Test harness for the experimental series imported into the main repo.

The experimental patches are *not* standalone against a pristine AOSP tree.
They are applied after the stable lenOS 1.0 series. ``LenosPatchTest`` builds
a sandbox containing the pinned files touched by both series, applies the
stable patches for the project, then applies the requested experimental
patch(es). This is the same strict ``git apply`` path the driver uses, without
touching the workspace checkout.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

MAIN = Path(__file__).resolve().parents[2]
VENDOR = MAIN
PATCH_ROOT = MAIN / "patches-experimental"
STABLE_PATCH_ROOT = MAIN / "patches"
WORKSPACE = Path(os.environ.get(
    "LENOS_WORKSPACE",
    "/mnt/sda/AI WORKSPACE/lenos-workspace"))

sys.path.insert(0, str(MAIN / "tools"))
from lenos_projects import alias_for, project_for  # noqa: E402

try:
    import tree_sitter
    import tree_sitter_java
    _JAVA_PARSER = tree_sitter.Parser(tree_sitter.Language(tree_sitter_java.language()))
except Exception:  # pragma: no cover - optional dependency
    _JAVA_PARSER = None


def java_syntax_errors(path: Path) -> int:
    if _JAVA_PARSER is None:
        raise unittest.SkipTest("tree-sitter-java not installed")
    tree = _JAVA_PARSER.parse(path.read_bytes())

    def walk(node):
        n = 1 if (node.type == "ERROR" or node.is_missing) else 0
        for child in node.children:
            n += walk(child)
        return n

    return walk(tree.root_node)


def patch_paths(patch: Path) -> list[str]:
    """Every file path the patch touches, including rename/copy and binary ends."""
    out: list[str] = []

    def add(p: str) -> None:
        p = p.split("\t")[0].strip()
        if p.startswith("a/") or p.startswith("b/"):
            p = p[2:]
        if p not in ("", "/dev/null") and p not in out:
            out.append(p)

    for line in patch.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                add(parts[2])
                add(parts[3])
        elif line.startswith("--- ") or line.startswith("+++ "):
            add(line[4:])
        elif line.startswith(("rename from ", "rename to ",
                              "copy from ", "copy to ")):
            add(line.split(" ", 2)[2])
    return out


def patch_created_paths(patch: Path) -> set[str]:
    """Files the patch creates or renames to."""
    created: set[str] = set()
    old_is_null = False
    for line in patch.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("--- "):
            old_is_null = line[4:].split("\t")[0].strip() == "/dev/null"
        elif line.startswith("+++ "):
            p = line[4:].split("\t")[0].strip()
            if old_is_null and p not in ("", "/dev/null"):
                created.add(p[2:] if p.startswith("b/") else p)
            old_is_null = False
        elif line.startswith(("rename to ", "copy to ")):
            p = line.split(" to ", 1)[1].strip()
            if p not in ("", "/dev/null"):
                created.add(p[2:] if p.startswith("b/") else p)
    return created


def series_for(project: str, root: Path) -> list[Path]:
    pdir = root / alias_for(project)
    sfile = pdir / "series"
    if not sfile.is_file():
        return []
    out = []
    for line in sfile.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patch = pdir / line
        if not patch.is_file():
            raise AssertionError(f"series lists missing patch: {patch}")
        out.append(patch)
    return out


def build_sandbox(project: str, extra_patches: list[Path],
                  extra_files: list[str] | None = None,
                  apply_extra: bool = True) -> Path:
    """Copy the needed pinned files, apply stable then experimental patches."""
    sandbox = Path(tempfile.mkdtemp(prefix="lenos-exp-test-"))
    project_dir = WORKSPACE / project
    if not project_dir.is_dir():
        raise unittest.SkipTest(f"workspace project missing: {project_dir}")

    stable_patches = series_for(project, STABLE_PATCH_ROOT)
    patches = stable_patches + list(extra_patches)
    files: list[str] = list(extra_files or [])
    created: set[str] = set()
    for patch in patches:
        files += patch_paths(patch)
        created |= patch_created_paths(patch)

    for rel in files:
        src = project_dir / rel
        if not src.is_file():
            if rel in created:
                continue  # git apply creates it in the sandbox
            raise AssertionError(f"pinned file missing in workspace tree: {project}/{rel}")
        dst = sandbox / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_SYSTEM"] = "/dev/null"
    to_apply = stable_patches + (list(extra_patches) if apply_extra else [])
    for patch in to_apply:
        proc = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(patch)],
            cwd=sandbox, capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            shutil.rmtree(sandbox, ignore_errors=True)
            raise AssertionError(f"patch failed to apply: {patch}\n{proc.stderr}")
    return sandbox


class LenosPatchTest(unittest.TestCase):
    """Apply the stable base plus one or more experimental patches."""

    PROJECT: str = ""
    PATCHES: list[str] = []
    EXTRA_FILES: list[str] = []

    sandbox: Path

    @classmethod
    def setUpClass(cls):
        if not cls.PROJECT:
            raise unittest.SkipTest("no PROJECT set")
        pdir = PATCH_ROOT / alias_for(cls.PROJECT)
        patches = [pdir / name for name in cls.PATCHES]
        cls.sandbox = build_sandbox(cls.PROJECT, patches, cls.EXTRA_FILES)
        cls.addClassCleanup(shutil.rmtree, cls.sandbox, ignore_errors=True)

    # --- helpers ---------------------------------------------------------
    def text(self, rel: str) -> str:
        return (self.sandbox / rel).read_text(encoding="utf-8", errors="replace")

    def assert_contains(self, rel: str, *needles: str):
        body = self.text(rel)
        for needle in needles:
            self.assertIn(needle, body, f"{rel} is missing {needle!r}")

    def assert_not_contains(self, rel: str, *needles: str):
        body = self.text(rel)
        for needle in needles:
            self.assertNotIn(needle, body, f"{rel} still contains {needle!r}")

    def assert_java_syntax(self, rel: str):
        errors = java_syntax_errors(self.sandbox / rel)
        self.assertEqual(errors, 0, f"{rel}: {errors} Java parse errors after patching")

    def assert_xml(self, rel: str):
        ET.parse(self.sandbox / rel)

    def assert_balanced(self, rel: str):
        body = self.text(rel)
        for open_c, close_c in (("{", "}"), ("(", ")"), ("[", "]")):
            self.assertEqual(body.count(open_c), body.count(close_c),
                             f"{rel}: unbalanced {open_c}{close_c}")


class SourceTreeTest(unittest.TestCase):
    """Assertions over opt-in source files that are not patch-applied."""

    def text(self, rel: str) -> str:
        return (MAIN / rel).read_text(encoding="utf-8", errors="replace")

    def assert_contains(self, rel: str, *needles: str):
        body = self.text(rel)
        for needle in needles:
            self.assertIn(needle, body, f"{rel} is missing {needle!r}")

    def assert_not_contains(self, rel: str, *needles: str):
        body = self.text(rel)
        for needle in needles:
            self.assertNotIn(needle, body, f"{rel} still contains {needle!r}")

    def assert_java_syntax(self, rel: str):
        errors = java_syntax_errors(MAIN / rel)
        self.assertEqual(errors, 0, f"{rel}: {errors} Java parse errors")

    def assert_xml(self, rel: str):
        ET.parse(MAIN / rel)

#!/usr/bin/env python3
"""lenos-patch — apply lenOS feature patches to a pinned LineageOS tree.

Design rules (see docs/patches.md):

* Patches are ordinary unified diffs produced by ``git diff`` in the pinned
  upstream project. They are applied with ``git apply`` inside the project,
  never with fuzzy matching.
* A patch that does not apply is a hard error. Silently skipping a security
  feature because upstream moved a line is how you ship a broken OS.
* ``--check`` never writes. ``--reverse`` removes a feature (for bisecting).
* Every project has ``patches/<project>/series`` listing patches in apply
  order; a patch not in the series is not applied.

Usage:
    lenos-patch.py --tree /path/to/lineage --check
    lenos-patch.py --tree /path/to/lineage --apply
    lenos-patch.py --tree /path/to/lineage --apply --project frameworks/base
    lenos-patch.py --tree /path/to/lineage --reverse --apply
    lenos-patch.py --list
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lenos_projects import PROJECT_ALIASES, alias_for, project_for  # noqa: E402

HERE = Path(__file__).resolve().parent.parent  # vendor/lenos
PATCH_ROOT = HERE / "patches"


def patch_dir_for(project: str) -> Path:
    return PATCH_ROOT / alias_for(project)


def series(project: str) -> list[Path]:
    pdir = patch_dir_for(project)
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
            raise SystemExit(f"ERROR: {project}: series lists missing patch {line}")
        out.append(patch)
    return out


def projects() -> list[str]:
    out = []
    for d in sorted(PATCH_ROOT.iterdir()):
        if not d.is_dir() or not (d / "series").is_file():
            continue
        project = project_for(d.name)
        if project is not None:
            out.append(project)
    return out


def git_apply(project_dir: Path, patch: Path, *, reverse: bool, check: bool) -> None:
    args = ["git", "apply", "--verbose"]
    if check:
        args.append("--check")
    if reverse:
        args.append("--reverse")
    # whitespace warnings on context lines are normal in AOSP; do not fail on them
    args += [str(patch)]
    proc = subprocess.run(args, cwd=project_dir, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"ERROR: {'reverse ' if reverse else ''}apply failed in {project_dir.name}:\n"
            f"  patch: {patch.name}\n  {proc.stderr.strip()}\n"
            "The tree does not match the pinned source revision. Fix the tree or update the\n"
            "patch set; do not ship with the feature silently missing."
        )
    if check:
        print(f"  ok    {project_dir.name}: {patch.name}")


def is_applied(project_dir: Path, patch: Path) -> bool:
    proc = subprocess.run(
        ["git", "apply", "--reverse", "--check", str(patch)],
        cwd=project_dir, capture_output=True, text=True)
    return proc.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", help="LineageOS source tree root")
    ap.add_argument("--project", action="append", default=[],
                    help="limit to this project path (repeatable)")
    ap.add_argument("--check", action="store_true", help="verify patches apply, do not write")
    ap.add_argument("--apply", action="store_true", help="apply patches")
    ap.add_argument("--reverse", action="store_true", help="reverse direction")
    ap.add_argument("--list", action="store_true", help="list project/patch pairs")
    ap.add_argument("--status", action="store_true",
                    help="report applied/not applied per patch (needs --tree)")
    args = ap.parse_args()

    if args.list:
        for project in projects():
            if args.project and project not in args.project:
                continue
            for patch in series(project):
                print(f"{project}\t{patch.name}")
        return 0

    if not args.tree:
        ap.error("--tree is required unless --list")
    tree = Path(args.tree).resolve()

    targets = args.project or projects()
    if not targets:
        raise SystemExit("ERROR: no projects with a series file found in " + str(PATCH_ROOT))

    rc = 0
    for project in targets:
        patches = series(project)
        if not patches:
            print(f"  skip  {project}: no patches")
            continue
        pdir = tree / project
        if not (pdir / ".git").exists() and not (pdir / ".git").is_file():
            print(f"  WARN  {project}: not a git checkout under {tree}; skipping")
            rc = 1
            continue
        for patch in patches:
            applied = is_applied(pdir, patch)
            if args.status:
                state = "applied" if applied else "missing"
                print(f"  {state:7} {project}: {patch.name}")
                continue
            if args.reverse:
                if not applied:
                    print(f"  skip(reverse) {project}: {patch.name} (not applied)")
                    continue
                git_apply(pdir, patch, reverse=True, check=args.check)
                if not args.check:
                    print(f"  reversed {project}: {patch.name}")
                continue
            if applied:
                print(f"  skip  {project}: {patch.name} (already applied)")
                continue
            git_apply(pdir, patch, reverse=False, check=args.check)
            if args.check:
                continue
            print(f"  applied {project}: {patch.name}")
    return rc


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sanitize an avbroot fastboot-info.txt before it is used to flash.

The sanitizer keeps the order avbroot produced, but:

* comments any firmware/bootloader flash line, because this OTA has no valid
  VBMeta for those images and ``--re-sign`` must not touch them;
* moves vbmeta lines after the logical partitions, because flashing vbmeta
  before the super/logical images can make the device unbootable.

It never invents android-info.txt and never changes the list of logical
partitions. The firmware denylist is read from ``firmware-deny.txt`` next to
this script so the re-sign filter and this sanitizer share one source.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_DENY = Path(__file__).with_name("firmware-deny.txt")
LOGICAL = (
    "system",
    "system_ext",
    "product",
    "vendor",
    "vendor_dlkm",
    "system_dlkm",
    "odm",
    "odm_dlkm",
)
VBMETA = ("vbmeta", "vbmeta_system", "vbmeta_vendor")


def load_deny(path: Path = DEFAULT_DENY) -> set[str]:
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if any(ch.isspace() for ch in line):
            raise ValueError(f"invalid firmware name in {path}: {line!r}")
        names.add(line)
    if not names:
        raise ValueError(f"firmware denylist is empty: {path}")
    return names


def _kind(line: str, firmware: set[str]) -> str:
    stripped = line.strip()
    if stripped.startswith("#") or not stripped:
        return "comment"
    parts = stripped.split()
    if not parts:
        return "comment"
    if parts[0] == "reboot" and "fastboot" in parts:
        return "reboot-fastboot"
    if parts[0] in {"flash", "update-super", "wipe", "format", "erase"}:
        name = parts[1] if len(parts) > 1 else ""
        name = name.split(":")[-1]
        base = name[:-2] if name.endswith("_a") or name.endswith("_b") else name
        if base in firmware:
            return "firmware"
        if base in LOGICAL or parts[0] == "update-super":
            return "logical"
        if base in VBMETA:
            return "vbmeta"
        return "physical"
    return "other"


def sanitize(path: Path, firmware: Iterable[str]) -> tuple[bool, bool]:
    """Rewrite *path* in place; return (saw reboot-fastboot, saw logical)."""
    deny = set(firmware)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(True)
    entries: list[tuple[str, str]] = []
    saw_reboot = False
    saw_logical = False
    for line in lines:
        kind = _kind(line, deny)
        if kind == "firmware":
            if not line.lstrip().startswith("#"):
                line = (
                    "# lenOS: firmware not flashed from this OTA (no VBMeta magic)\n# "
                    + line
                )
            kind = "comment"
        if kind == "reboot-fastboot":
            saw_reboot = True
        if kind == "logical":
            saw_logical = True
        entries.append((kind, line))

    vbmeta = [line for kind, line in entries if kind == "vbmeta"]
    out = [line for kind, line in entries if kind != "vbmeta"]
    if vbmeta and saw_logical:
        # Put every vbmeta line after the last logical line, not merely after
        # the first one. Some fastboot-info generators interleave partitions.
        last_logical = max(i for i, (kind, _) in enumerate(entries) if kind == "logical")
        removed_before = sum(
            1 for i, (kind, _) in enumerate(entries) if kind == "vbmeta" and i <= last_logical
        )
        position = last_logical + 1 - removed_before
        out[position:position] = vbmeta
    elif vbmeta:
        # No logicals to order against; keep the original position rather than
        # inventing an order.
        out = [line for _, line in entries]
    path.write_text("".join(out), encoding="utf-8")
    return saw_reboot, saw_logical


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--deny-file", type=Path, default=DEFAULT_DENY)
    args = parser.parse_args(argv)
    try:
        firmware = load_deny(args.deny_file)
        saw_reboot, saw_logical = sanitize(args.path, firmware)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"sanitized {args.path} reboot_fastboot={saw_reboot} "
        f"logicals={saw_logical}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

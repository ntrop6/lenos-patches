#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract and verify the first signer certificate from an APK v2 signature."""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

EOCD = b"PK\x05\x06"
APK_SIG_MAGIC = b"APK Sig Block 42"
APK_SIGNATURE_SCHEME_V2_BLOCK_ID = 0x7109871A


class ApkError(RuntimeError):
    pass


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ApkError("truncated uint32")
    return struct.unpack_from("<I", data, offset)[0]


def u64(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 8 > len(data):
        raise ApkError("truncated uint64")
    return struct.unpack_from("<Q", data, offset)[0]


def length_prefixed(data: bytes, offset: int, end: int) -> tuple[int, int, int]:
    size = u32(data, offset)
    start = offset + 4
    value_end = start + size
    if value_end > end:
        raise ApkError("length-prefixed field exceeds container")
    return start, value_end, value_end


def first_v2_certificate(path: Path) -> bytes:
    data = path.read_bytes()
    eocd = data.rfind(EOCD, max(0, len(data) - 65557))
    if eocd < 0:
        raise ApkError("ZIP EOCD not found")
    central_directory = u32(data, eocd + 16)
    if central_directory < 24 or central_directory > len(data):
        raise ApkError("invalid central-directory offset")
    if data[central_directory - 16 : central_directory] != APK_SIG_MAGIC:
        raise ApkError("APK Signing Block magic not found")
    block_size = u64(data, central_directory - 24)
    block_start = central_directory - (block_size + 8)
    if block_start < 0 or u64(data, block_start) != block_size:
        raise ApkError("APK Signing Block size mismatch")

    position = block_start + 8
    pairs_end = central_directory - 24
    v2 = None
    while position < pairs_end:
        pair_size = u64(data, position)
        position += 8
        if pair_size < 4 or position + pair_size > pairs_end:
            raise ApkError("invalid APK Signing Block pair")
        block_id = u32(data, position)
        position += 4
        value_size = pair_size - 4
        value = data[position : position + value_size]
        position += value_size
        if block_id == APK_SIGNATURE_SCHEME_V2_BLOCK_ID:
            v2 = value
    if position != pairs_end or v2 is None:
        raise ApkError("APK v2 signature block not found")

    # v2 value: signers -> first signer -> signed data -> digests, certificates.
    signers_start, signers_end, _ = length_prefixed(v2, 0, len(v2))
    signer_start, signer_end, _ = length_prefixed(v2, signers_start, signers_end)
    signed_start, signed_end, _ = length_prefixed(v2, signer_start, signer_end)
    _, _, certificates_offset = length_prefixed(v2, signed_start, signed_end)
    certificates_start, certificates_end, _ = length_prefixed(
        v2, certificates_offset, signed_end
    )
    cert_start, cert_end, _ = length_prefixed(
        v2, certificates_start, certificates_end
    )
    return v2[cert_start:cert_end]


def verify_certificate(
    path: Path,
    *,
    expect_size: int | None = None,
    expect_sha256: str | None = None,
    extract: Path | None = None,
) -> tuple[int, str]:
    cert = first_v2_certificate(path)
    digest = hashlib.sha256(cert).hexdigest()
    if expect_size is not None and len(cert) != expect_size:
        raise ApkError(
            f"signer certificate size mismatch: {len(cert)} != {expect_size}"
        )
    if expect_sha256 is not None and digest != expect_sha256.lower():
        raise ApkError(
            f"signer certificate SHA-256 mismatch: {digest} != {expect_sha256}"
        )
    if extract is not None:
        extract.write_bytes(cert)
    return len(cert), digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--expect-size", type=int)
    parser.add_argument("--expect-sha256")
    parser.add_argument("--extract", type=Path)
    args = parser.parse_args()
    try:
        size, digest = verify_certificate(
            args.apk,
            expect_size=args.expect_size,
            expect_sha256=args.expect_sha256,
            extract=args.extract,
        )
        print(f"size={size}")
        print(f"sha256={digest}")
    except (OSError, ApkError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

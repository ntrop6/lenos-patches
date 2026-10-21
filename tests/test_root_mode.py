"""Source-level checks for the opt-in root path.

These tests prove the repository still defaults to rootless and that the root
mode is a post-build init_boot transform. They do not build, download, flash, or
boot anything.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness import VENDOR

TOOLS = VENDOR / "tools"
DRIVER = VENDOR / "lenos-1.0-shizuku.sh"
ROOT_TOOL = TOOLS / "lenos_root.py"
ROOT_HELPER = TOOLS / "apk_signing_cert.py"
PROFILES = TOOLS / "root-managers.json"

sys.path.insert(0, str(TOOLS))
import lenos_root  # noqa: E402


class TestRootProfiles(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(PROFILES.read_text(encoding="utf-8"))

    def test_profiles_are_pinned_for_the_asteroids_kmi(self):
        self.assertEqual(self.data["schema"], 1)
        self.assertEqual(self.data["kmi"], "android15-6.6")
        self.assertEqual(self.data["arch"], "aarch64")
        self.assertIn("resukisu", self.data["profiles"])
        self.assertIn("kernelsu", self.data["profiles"])

    def test_every_asset_uses_a_full_sha256_and_a_real_url(self):
        blobs = [self.data["patcher"]]
        for profile in self.data["profiles"].values():
            blobs.extend(profile[key] for key in ("manager", "lkm", "init"))
        for blob in blobs:
            self.assertRegex(blob["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(blob["url"].startswith("https://"))
            self.assertNotIn("nightly.link", blob["url"])

    def test_manager_certificates_are_pinned(self):
        for name, profile in self.data["profiles"].items():
            manager = profile["manager"]
            self.assertIsInstance(manager["cert_size"], int)
            self.assertRegex(manager["cert_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(manager["cert_size"] > 0, name)

    def test_expected_pins_have_not_drifted(self):
        resukisu = self.data["profiles"]["resukisu"]
        self.assertEqual(
            resukisu["manager"]["sha256"],
            "78862d9adcca1c1281e0df26680e9cb7d7cb6ebee7cb5994b2ffbde9e0ab377a",
        )
        self.assertEqual(
            resukisu["lkm"]["member_sha256"],
            "8937c94461a3da8d39bb86f968d491fb46a08602bff4132d6ab4ff8acef026cc",
        )
        kernelsu = self.data["profiles"]["kernelsu"]
        self.assertEqual(
            kernelsu["manager"]["sha256"],
            "b4a059ace71de2fa65cc7f12b1c58d55fc23ab25e057ee4230ce779742abe450",
        )
        self.assertEqual(
            kernelsu["lkm"]["member_sha256"],
            "e57ce23de951be6b0dee5030f6724322fed126aa4af71828994437bfb0bb61ad",
        )

    def test_patcher_is_the_host_binary(self):
        patcher = self.data["patcher"]
        self.assertIn("x86_64", patcher["name"])
        self.assertIn("ksud", patcher["name"])
        self.assertEqual(
            patcher["sha256"],
            "29b50f946a3cc40b04aef3dd587adad227fe0f70edf9c56b02c84479f0b0e954",
        )


class TestRootDriver(unittest.TestCase):
    def run_driver(self, *args: str, env: dict[str, str] | None = None):
        command_env = os.environ.copy()
        command_env.pop("LENOS_ROOT", None)
        command_env.update(env or {})
        return subprocess.run(
            [str(DRIVER), *args],
            cwd=str(VENDOR),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=command_env,
        )

    def test_default_flash_plan_is_rootless(self):
        result = self.run_driver("flash-plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ROOTLESS", result.stdout)
        self.assertNotIn("manager.apk", result.stdout)

    def test_resukisu_flash_plan_is_mode_aware(self):
        result = self.run_driver(
            "flash-plan", env={"LENOS_ROOT": "resukisu"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ROOT (resukisu)", result.stdout)
        self.assertIn("lenos-asteroids-resukisu-manager.apk", result.stdout)
        self.assertIn("extracted-resukisu", result.stdout)
        self.assertIn('scp "build-host:', result.stdout)
        self.assertNotIn("ROOTLESS", result.stdout)

    def test_cli_root_flag_matches_environment(self):
        result = self.run_driver("--root", "kernelsu", "flash-plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ROOT (kernelsu)", result.stdout)

    def test_empty_cli_root_is_rejected(self):
        result = self.run_driver("--root=", "package")
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid LENOS_ROOT", result.stderr)

    def test_unknown_root_mode_is_rejected_before_anything_runs(self):
        result = self.run_driver(
            "package", env={"LENOS_ROOT": "magisk"}
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid LENOS_ROOT", result.stderr)

    def test_lock_gates_always_refuse(self):
        for mode in ("resukisu", "kernelsu"):
            result = self.run_driver("lock-gates", env={"LENOS_ROOT": mode})
            self.assertEqual(result.returncode, 1)
            self.assertIn("will not run", result.stdout)
            self.assertIn("does not install or verify", result.stdout)

    def test_root_packaging_uses_prepatched_and_requires_init_boot(self):
        text = DRIVER.read_text(encoding="utf-8")
        self.assertIn('ROOT_MODE="none"', text)
        self.assertIn('args+=(--prepatched "$ROOT_STATE_DIR/init_boot.img")', text)
        self.assertIn(
            "for required in init_boot boot vendor_boot vbmeta", text
        )
        self.assertIn(
            'need_file "$WS/lenos-asteroids-$ROOT_MODE-manager.apk"', text
        )
        self.assertIn('parts_text="$(collect_os_resign)"', text)
        self.assertIn("check-source", text)
        self.assertIn("root-prepare", text)
        self.assertIn("root-status", text)

    def test_rootless_package_uses_rootless_and_not_prepatched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ws = root / "workspace"
            src = root / "source"
            keys = root / "keys"
            for path in (ws, keys, src / "device/nothing/asteroids"):
                path.mkdir(parents=True)
            (src / "device/nothing/asteroids/lineage_asteroids.mk").write_text(
                "x\n", encoding="utf-8"
            )
            (src / "device/nothing/asteroids/BoardConfig.mk").write_text(
                "BOARD_INIT_BOOT_IMAGE_PARTITION_SIZE := 0x800000\n",
                encoding="utf-8",
            )
            base = root / "base.zip"
            base.write_bytes(b"base OTA bytes")
            (ws / "signing-plan.json").write_text(
                json.dumps(
                    {
                        "resign_partitions": [
                            "boot",
                            "init_boot",
                            "vendor_boot",
                            "vbmeta",
                        ]
                    }
                ),
                encoding="utf-8",
            )
            for name in ("avb.key", "ota.key", "ota.crt", "avb_pkmd.bin"):
                (keys / name).write_text("test key material\n", encoding="utf-8")
            wizard = root / "fake-wizard.sh"
            wizard.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            wizard.chmod(0o755)
            log = root / "avbroot.log"
            fake = root / "avbroot"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'printf \'%s\\n\' "$*" >> "${FAKE_AVBROOT_LOG:?}"\n'
                'if [[ "${1:-}" == "--version" ]]; then\n'
                '  echo "avbroot 3.33.0"\n'
                "  exit 0\n"
                "fi\n"
                'if [[ "${1:-}" == "boot" && "${2:-}" == "unpack" '
                '&& "${3:-}" == "--help" ]]; then\n'
                "  exit 0\n"
                "fi\n"
                'if [[ "${1:-}" == "ota" && "${2:-}" == "patch" ]]; then\n'
                '  out=""\n'
                "  saw_rootless=0\n"
                "  shift 2\n"
                "  while (($#)); do\n"
                "    case \"$1\" in\n"
                '      --output) out="$2"; shift 2;;\n'
                '      --rootless) saw_rootless=1; shift;;\n'
                '      --prepatched) echo "unexpected --prepatched" >&2; exit 2;;\n'
                "      *) shift;;\n"
                "    esac\n"
                "  done\n"
                '  [[ -n "$out" ]] || exit 2\n'
                '  [[ "$saw_rootless" -eq 1 ]] || { echo "missing --rootless" >&2; exit 2; }\n'
                '  printf "fake patched OTA\\n" > "$out"\n'
                "  exit 0\n"
                "fi\n"
                'if [[ "${1:-}" == "ota" && "${2:-}" == "verify" ]]; then\n'
                "  exit 0\n"
                "fi\n"
                'if [[ "${1:-}" == "ota" && "${2:-}" == "extract" ]]; then\n'
                '  dir=""\n'
                "  shift 2\n"
                "  while (($#)); do\n"
                "    case \"$1\" in\n"
                '      --directory) dir="$2"; shift 2;;\n'
                "      *) shift;;\n"
                "    esac\n"
                "  done\n"
                '  [[ -n "$dir" ]] || exit 2\n'
                '  mkdir -p "$dir"\n'
                '  printf "boot\\n" > "$dir/boot.img"\n'
                '  printf "init_boot\\n" > "$dir/init_boot.img"\n'
                '  printf "vendor_boot\\n" > "$dir/vendor_boot.img"\n'
                "  exit 0\n"
                "fi\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            result = self.run_driver(
                "package",
                env={
                    "LENOS_WORKSPACE": str(ws),
                    "LENOS_SOURCE": str(src),
                    "LENOS_KEYDIR": str(keys),
                    "LENOS_WIZARD": str(wizard),
                    "LENOS_BASE_OTA": str(base),
                    "AVBROOT": str(fake),
                    "FAKE_AVBROOT_LOG": str(log),
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--rootless", log.read_text(encoding="utf-8"))
            self.assertNotIn("--prepatched", log.read_text(encoding="utf-8"))
            self.assertTrue((ws / "lenos-asteroids-rootless.zip").is_file())

    def test_root_prepare_never_talks_to_a_device(self):
        body = ROOT_TOOL.read_text(encoding="utf-8")
        self.assertNotRegex(body, r'["\']adb["\']')
        self.assertNotRegex(body, r'["\']fastboot["\']')
        self.assertNotIn("flashing lock", body)

    def test_root_tool_is_executable_and_has_help(self):
        self.assertTrue(os.access(ROOT_TOOL, os.X_OK))
        self.assertTrue(os.access(ROOT_HELPER, os.X_OK))
        result = subprocess.run(
            [sys.executable, str(ROOT_TOOL), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("prepare", result.stdout)
        self.assertIn("check-source", result.stdout)
        self.assertIn("verify-image", result.stdout)


class TestRootHelpers(unittest.TestCase):
    def test_cpio_parser_reads_modes_and_duplicate_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            info = Path(directory) / "cpio.toml"
            info.write_text(
                "format = \"Lz4Legacy\"\n"
                "\n[[entries]]\n"
                "path = \"init\"\n"
                "file_type = \"Regular\"\n"
                "file_mode = \"755\"\n"
                "\n[[entries]]\n"
                "path = \"init.real\"\n"
                "file_type = \"Regular\"\n"
                "file_mode = \"750\"\n",
                encoding="utf-8",
            )
            entries = lenos_root.parse_cpio_info(info)
        self.assertEqual(entries["init"]["file_mode"], "755")
        self.assertTrue(lenos_root._is_executable(entries["init"]))
        self.assertTrue(lenos_root._is_executable(entries["init.real"]))
        self.assertFalse(lenos_root._is_executable({"file_mode": "644"}))

    def test_partition_limit_comes_from_the_device_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            board = source / "device/nothing/asteroids/BoardConfig.mk"
            board.parent.mkdir(parents=True)
            board.write_text(
                "BOARD_INIT_BOOT_IMAGE_PARTITION_SIZE := 0x800000\n",
                encoding="utf-8",
            )
            self.assertEqual(lenos_root.board_partition_limit(source), 8 * 1024 * 1024)

    def test_incomplete_root_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory)
            (state_dir / "root-state.json").write_text(
                '{"schema": 1, "mode": "resukisu"}\n', encoding="utf-8"
            )
            with self.assertRaises(lenos_root.RootError):
                lenos_root.load_state(state_dir, "resukisu")

    def test_root_state_rejects_malformed_hashes_and_oversized_images(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory)
            state = {
                "schema": 1,
                "mode": "resukisu",
                "kmi": "android15-6.6",
                "base_ota_sha256": "a" * 64,
                "patched_init_boot_sha256": "b" * 64,
                "source_init_boot_sha256": "c" * 64,
                "stock_init_sha256": "d" * 64,
                "ksuinit_sha256": "e" * 64,
                "lkm_sha256": "f" * 64,
                "manager_sha256": "0" * 64,
                "patched_init_boot_size": 1,
                "partition_limit": 2,
            }
            state_file = state_dir / "root-state.json"
            state["patched_init_boot_size"] = 3
            state_file.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(lenos_root.RootError):
                lenos_root.load_state(state_dir, "resukisu")
            state["patched_init_boot_size"] = 1
            state["manager_sha256"] = "not-a-hash"
            state_file.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(lenos_root.RootError):
                lenos_root.load_state(state_dir, "resukisu")

    def test_check_source_binds_state_to_ota_and_init_boot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.zip"
            base.write_bytes(b"base OTA bytes")
            init = root / "init_boot.img"
            init.write_bytes(b"stock init_boot bytes")
            state_dir = root / "state"
            state_dir.mkdir()
            state = {
                "schema": 1,
                "mode": "resukisu",
                "kmi": "android15-6.6",
                "base_ota_sha256": hashlib.sha256(base.read_bytes()).hexdigest(),
                "source_init_boot_sha256": hashlib.sha256(
                    init.read_bytes()
                ).hexdigest(),
                "patched_init_boot_sha256": "1" * 64,
                "stock_init_sha256": "2" * 64,
                "ksuinit_sha256": "3" * 64,
                "lkm_sha256": "4" * 64,
                "manager_sha256": "5" * 64,
                "patched_init_boot_size": 1,
                "partition_limit": 2,
            }
            (state_dir / "root-state.json").write_text(
                json.dumps(state), encoding="utf-8"
            )
            fake = root / "avbroot"
            fake.write_text(
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                'if [[ "${1:-}" == "--version" ]]; then\n'
                '  echo "avbroot 3.33.0"\n'
                "  exit 0\n"
                "fi\n"
                'if [[ "${1:-}" == "ota" && "${2:-}" == "extract" ]]; then\n'
                '  dir=""\n'
                '  while (($#)); do\n'
                '    case "$1" in\n'
                '      --directory) dir="$2"; shift 2;;\n'
                '      *) shift;;\n'
                "    esac\n"
                "  done\n"
                '  [[ -n "$dir" ]] || exit 1\n'
                '  mkdir -p "$dir"\n'
                f"  cp {shlex.quote(str(init))} \"$dir/init_boot.img\"\n"
                "  exit 0\n"
                "fi\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            command = [
                sys.executable,
                str(ROOT_TOOL),
                "check-source",
                "--mode",
                "resukisu",
                "--state-dir",
                str(state_dir),
                "--base-ota",
                str(base),
                "--avbroot",
                str(fake),
            ]
            result = subprocess.run(
                command, text=True, capture_output=True, check=False
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ok source OTA", result.stdout)
            self.assertIn("source_init_boot_sha256=", result.stdout)

            base.write_bytes(b"different base OTA bytes")
            result = subprocess.run(
                command, text=True, capture_output=True, check=False
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("base OTA changed since root-prepare", result.stderr)

    def test_apk_signer_rejects_non_apk_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-an.apk"
            path.write_bytes(b"not a zip")
            result = subprocess.run(
                [sys.executable, str(ROOT_HELPER), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()

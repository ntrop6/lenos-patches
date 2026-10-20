"""Kernel hardening fragment (Tier 3 #32).

lenOS ships an additive 6.6 GKI config fragment for the portable subset of
GrapheneOS's kernel hardening. It is merged last by ``TARGET_KERNEL_CONFIG``
and only enables options that need no vendor firmware, module re-signing or
device-specific validation. The larger pieces (48-bit VA / 4-level page
tables, forced module signing + lockdown, GrapheneOS's allocator canaries and
MTE-for-apps) remain out of scope and are documented in
``docs/graphene-porting.md`` section 19.

These tests pin the option set, prove each symbol exists in the pinned kernel
tree, and check that the fragment is wired into the device build.
"""
from __future__ import annotations

import re
import subprocess
import unittest

from harness import VENDOR, WORKSPACE, LenosPatchTest, patch_paths
from lenos_projects import alias_for, project_for

KERNEL = WORKSPACE / "kernel/nothing/sm7635"
DEVICE = WORKSPACE / "device/nothing/asteroids"

FRAGMENT = "arch/arm64/configs/vendor/lenos_hardening.config"
KERNEL_PATCH = "0001-lenos-kernel-hardening-config.patch"
DEVICE_PATCH = "0008-kernel-hardening-config.patch"

#: option -> Kconfig file that defines it (cross-checked with ``git show``).
EXPECTED = {
    "CONFIG_INIT_ON_FREE_DEFAULT_ON": "security/Kconfig.hardening",
    "CONFIG_RANDOM_KMALLOC_CACHES": "mm/Kconfig",
    "CONFIG_RANDOMIZE_KSTACK_OFFSET_DEFAULT": "arch/Kconfig",
    "CONFIG_SECURITY_DMESG_RESTRICT": "security/Kconfig",
    "CONFIG_ZERO_CALL_USED_REGS": "security/Kconfig.hardening",
}

BASE_CONFIGS = (
    "arch/arm64/configs/gki_defconfig",
    "arch/arm64/configs/vendor/pineapple_perf.config",
    "arch/arm64/configs/vendor/asteroids_perf.config",
)


class TestKernelHardeningFragment(LenosPatchTest):
    PROJECT = "kernel/nothing/sm7635"
    PATCHES = [KERNEL_PATCH]

    def options(self) -> dict[str, str]:
        body = self.text(FRAGMENT)
        return dict(re.findall(r"(?m)^(CONFIG_[A-Z0-9_]+)=(.*)$", body))

    def test_fragment_enables_exactly_the_portable_subset(self):
        self.assertEqual(self.options(), {opt: "y" for opt in EXPECTED})

    def test_fragment_is_additive_only(self):
        body = self.text(FRAGMENT)
        self.assertIn("# lenOS kernel hardening (Tier 3 #32)", body)
        self.assertNotIn("# CONFIG_", body, "fragments must not disable options")
        for forbidden in (
            "CONFIG_KASAN",
            "CONFIG_KASAN_STACK",
            "CONFIG_DEBUG_KERNEL",
            "CONFIG_MODULE_SIG",
            "CONFIG_SECURITY_LOCKDOWN",
            "CONFIG_ARM64_VA_BITS",
        ):
            self.assertNotIn(forbidden, body)

    def kconfig(self, rel: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(KERNEL), "show", f"HEAD:{rel}"],
            capture_output=True, text=True)
        if proc.returncode != 0:
            self.skipTest(f"cannot read {rel} from the pinned kernel")
        return proc.stdout

    def test_each_option_is_defined_in_this_kernel(self):
        for opt, kconfig in EXPECTED.items():
            self.assertIn(f"config {opt.removeprefix('CONFIG_')}",
                          self.kconfig(kconfig),
                          f"{opt} is not defined in {kconfig}")

    def test_stack_zeroing_is_an_upstream_default_not_a_fragment_option(self):
        # 6.6 already defaults INIT_STACK_ALL_ZERO on when the compiler
        # supports auto-var-init (the GKI Clang does), so the fragment must
        # not claim it as a lenOS delta.
        self.assertIn(
            "default INIT_STACK_ALL_ZERO if CC_HAS_AUTO_VAR_INIT_ZERO",
            self.kconfig("security/Kconfig.hardening"))
        self.assertNotIn("CONFIG_INIT_STACK_ALL_ZERO", self.text(FRAGMENT))

    def test_none_of_the_options_are_already_on_in_the_baseline(self):
        for rel in BASE_CONFIGS:
            body = (KERNEL / rel).read_text(encoding="utf-8")
            for opt in EXPECTED:
                self.assertNotRegex(body, rf"(?m)^{opt}=y\b",
                                    f"{opt} is already enabled in {rel}")

    def test_patch_creates_only_the_fragment(self):
        patch = VENDOR / "patches" / alias_for(self.PROJECT) / KERNEL_PATCH
        self.assertEqual(patch_paths(patch), [FRAGMENT])

    def test_kernel_project_is_registered_for_apply_and_reset(self):
        self.assertEqual(project_for("kernel_nothing_sm7635"),
                         "kernel/nothing/sm7635")


class TestKernelHardeningBoardConfig(LenosPatchTest):
    PROJECT = "device/nothing/asteroids"
    PATCHES = [DEVICE_PATCH]

    def config_lines(self) -> list[str]:
        body = self.text("BoardConfig.mk")
        match = re.search(r"(?m)^TARGET_KERNEL_CONFIG := \\\n((?:    .*\n?)+)", body)
        self.assertIsNotNone(match, "TARGET_KERNEL_CONFIG block is missing")
        return [line.rstrip(" \\") for line in match.group(1).splitlines()]

    def test_fragment_is_merged_after_the_vendor_configs(self):
        lines = self.config_lines()
        self.assertEqual(lines[-1], "    vendor/lenos_hardening.config")
        self.assertGreater(
            lines.index("    vendor/lenos_hardening.config"),
            lines.index("    vendor/asteroids_perf.config"))

    def test_patch_touches_only_boardconfig(self):
        patch = VENDOR / "patches" / alias_for(self.PROJECT) / DEVICE_PATCH
        self.assertEqual(patch_paths(patch), ["BoardConfig.mk"])

    def test_patch_is_the_last_entry_in_the_device_series(self):
        series = (VENDOR / "patches" / alias_for(self.PROJECT) / "series").read_text()
        self.assertEqual(
            [ln.strip() for ln in series.splitlines() if ln.strip()][-1],
            DEVICE_PATCH)

    def test_kernel_series_contains_the_fragment(self):
        series = (VENDOR / "patches" / alias_for("kernel/nothing/sm7635")
                  / "series").read_text()
        self.assertIn(KERNEL_PATCH, series.splitlines())


if __name__ == "__main__":
    unittest.main()

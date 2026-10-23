"""Source-level checks for the opt-in bionic hardened thread-stack patch."""
from __future__ import annotations

import unittest

from harness import LenosPatchTest, PATCH_ROOT, patch_paths

PATCH = (PATCH_ROOT / "bionic" / "0001-hardened-thread-stacks.patch")
SOURCE = "libc/bionic/pthread_create.cpp"


class TestHardenedThreadStacks(LenosPatchTest):
    PROJECT = "bionic"
    PATCHES = ["0001-hardened-thread-stacks.patch"]

    def test_patch_scope_is_the_thread_allocator_only(self):
        self.assertEqual(patch_paths(PATCH), [SOURCE])

    def test_property_gate_is_exact_and_default_off(self):
        self.assert_contains(
            SOURCE,
            '__system_property_get("ro.lenos.hardened_thread_stacks", value)',
            "== 1 &&",
            "value[0] == '1'",
        )
        self.assert_not_contains(SOURCE, "persist.lenos.hardened_thread_stacks")
        self.assert_not_contains(SOURCE, "atoi(")
        # The experimental series is the only switch; no second build flag.
        self.assert_not_contains(SOURCE, "LENOS_HARDENED_THREAD_STACKS")

    def test_stock_mapping_remains_the_fallback(self):
        self.assert_contains(
            SOURCE,
            "mapping = hardened_stacks",
            "? __allocate_hardened_thread_mapping(attr->stack_size, attr->guard_size)",
            ": __allocate_thread_mapping(attr->stack_size, attr->guard_size);",
            "? __allocate_hardened_thread_mapping(0, PTHREAD_GUARD_SIZE)",
            ": __allocate_thread_mapping(0, PTHREAD_GUARD_SIZE);",
        )

    def test_thread_metadata_has_a_dedicated_page_above_the_stack(self):
        self.assert_contains(
            SOURCE,
            "size_t thread_page_size = __builtin_align_up(sizeof(pthread_internal_t), page_size());",
            "result.static_tls = result.libgen_buffers - static_tls_layout_size;",
            "mapping.static_tls - __builtin_align_up(sizeof(pthread_internal_t), page_size())",
            "memset(thread, 0, sizeof(pthread_internal_t));",
        )

    def test_random_gap_is_at_least_one_page(self):
        self.assert_contains(
            SOURCE,
            "gap_size = __builtin_align_up(arc4random_uniform(max_gap_size), page_size());",
            "if (gap_size == 0) gap_size = page_size();",
            "const size_t non_stack_writeable_offset = stack_guard_size + stack_size + gap_size;",
            "mmap_size - non_stack_writeable_offset - PTHREAD_GUARD_SIZE",
        )
        # The stack and the metadata/TLS region must be made writable separately;
        # the randomized gap in between stays PROT_NONE.
        self.assert_contains(
            SOURCE,
            "if (stack_size != 0 && mprotect(space + stack_guard_size, stack_size, prot) != 0)",
            "mprotect(space + non_stack_writeable_offset, non_stack_writeable_size, prot)",
        )

    def test_user_supplied_stack_avoids_a_zero_length_mprotect(self):
        self.assert_contains(
            SOURCE,
            "if (stack_size != 0) {",
            "result.stack_top = space + stack_guard_size;",
        )
        self.assert_contains(SOURCE, "static_cast<char*>(attr->stack_base) + attr->stack_size")

    def test_size_arithmetic_is_overflow_checked(self):
        self.assert_contains(
            SOURCE,
            "__builtin_add_overflow(stack_size, stack_guard_size, &mmap_size)",
            "__builtin_add_overflow(mmap_size, gap_size, &mmap_size)",
            "__builtin_add_overflow(mmap_size, thread_page_size, &mmap_size)",
            "__builtin_add_overflow(mmap_size, static_tls_layout_size, &mmap_size)",
            "__builtin_add_overflow(mmap_size, PTHREAD_GUARD_SIZE, &mmap_size)",
            "__builtin_add_overflow(mmap_size, libgen_buffers_padded_size, &mmap_size)",
        )

    def test_stack_top_randomization_keeps_16_byte_alignment(self):
        self.assert_contains(
            SOURCE,
            "result.stack_top =",
            "space + stack_guard_size + stack_size - arc4random_uniform(sizeof(pthread_internal_t));",
            "__builtin_align_down(result.stack_top, 16);",
        )


if __name__ == "__main__":
    unittest.main()

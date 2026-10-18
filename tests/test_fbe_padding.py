"""FBE filename padding of 32 bytes (see docs/features.md).

Feature contract (GrapheneOS-faithful port, commit ``pad filenames to 32
bytes instead of 16 or 4 bytes`` on ``platform_system_extras``):

* Every file-based-encryption policy this build creates requests the maximum
  ``FSCRYPT_POLICY_FLAGS_PAD_32`` filename padding, instead of AOSP's
  context-dependent 16 (and 4 for pre-R v1 policies). 32-byte padding hides
  filename lengths better. The pre-R compatibility branch is removed
  entirely: the device tree pins ``PRODUCT_SHIPPING_API_LEVEL := 35`` so it
  could never be taken, and lenOS has no shipped installs to stay compatible
  with.
* The lock-library consumers (`vold` links ``libfscrypt``) pick the flags up
  through ``ParseOptionsForApiLevel``; the padding is derived, never parsed
  from or serialized into the options string, so option-string round trips
  are unaffected.
* The in-tree ``fscrypt_test`` expectations are updated to ``PAD_32`` to
  match the ported behavior. GrapheneOS's fork changed the code but left its
  copy of the test file stale — documented, no behavior delta.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestFbePadding(LenosPatchTest):
    PROJECT = "system/extras"
    PATCHES = ["0001-lenos-fbe-pad-32.patch"]
    SRC = "libfscrypt/fscrypt.cpp"
    TEST = "libfscrypt/tests/fscrypt_test.cpp"

    def test_every_policy_requests_pad32(self):
        self.assert_contains(
            self.SRC,
            "options->flags |= FSCRYPT_POLICY_FLAGS_PAD_32;")
        self.assert_not_contains(
            self.SRC,
            "FSCRYPT_POLICY_FLAGS_PAD_16",
            "FSCRYPT_POLICY_FLAGS_PAD_4",
            "first_api_level <= __ANDROID_API_Q__ && options->version == 1")

    def test_unit_test_expectations_match(self):
        self.assert_contains(self.TEST, "FSCRYPT_POLICY_FLAGS_PAD_32")
        self.assert_not_contains(
            self.TEST,
            "FSCRYPT_POLICY_FLAGS_PAD_16",
            "FSCRYPT_POLICY_FLAGS_PAD_4")

    def test_block_size_selection_unchanged(self):
        # The v1/v2 policy-version selection (first_api_level vs Q) is
        # untouched; only the padding branch is replaced.
        self.assert_contains(
            self.SRC,
            "options->version = first_api_level > __ANDROID_API_Q__ ? 2 : 1;")


if __name__ == "__main__":
    unittest.main()

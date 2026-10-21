"""Source-level regression test for the LenosSecurity crash handler."""
from __future__ import annotations

import unittest

from harness import VENDOR

CRASH_APP = (
    VENDOR
    / "app/LenosSecurity/src/org/lenos/security/CrashApp.java"
)


class TestCrashHandler(unittest.TestCase):
    def test_previous_handler_is_captured_before_install(self):
        text = CRASH_APP.read_text(encoding="utf-8")
        self.assertIn("Thread.UncaughtExceptionHandler previous", text)
        self.assertIn("previous.uncaughtException", text)
        self.assertNotIn(
            "Thread.getDefaultUncaughtExceptionHandler().uncaughtException",
            text,
        )


if __name__ == "__main__":
    unittest.main()

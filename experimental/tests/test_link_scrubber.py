"""OPS-5: strip known tracking parameters from shared text.

This is a local text transformation. The app never opens the links, resolves
them, or uploads the text; only the sanitized string is handed to the target
app or the clipboard.
"""
from __future__ import annotations

import unittest

from harness import SourceTreeTest

APP = "experimental/app/LenosOpsec"


class TestLinkScrubber(SourceTreeTest):
    def test_scrubber_is_conservative_and_offline(self):
        self.assert_contains(
            f"{APP}/src/org/lenos/opsec/LinkScrubber.java",
            "URL_PATTERN",
            "utm_",
            "fbclid",
            "gclid",
            "msclkid",
            "srsltid",
            'split("&", -1)',
            "java.util.Locale.ROOT",
        )
        self.assert_not_contains(
            f"{APP}/src/org/lenos/opsec/LinkScrubber.java",
            "HttpURLConnection",
            "openConnection",
            "Socket",
            "URLConnection",
            "java.net.",
        )

    def test_activity_only_shares_text(self):
        self.assert_contains(
            f"{APP}/src/org/lenos/opsec/ScrubTextActivity.java",
            "Intent.ACTION_SEND",
            'setType("text/plain")',
            "Intent.EXTRA_TEXT",
            "ClipboardManager",
            "setPrimaryClip",
            "ClipData.newPlainText",
        )
        self.assert_not_contains(
            f"{APP}/src/org/lenos/opsec/ScrubTextActivity.java",
            "INTERNET",
            "HttpURLConnection",
            "openConnection",
        )

    def test_manifest_filters_text_only(self):
        self.assert_contains(
            f"{APP}/AndroidManifest.xml",
            'android:name=".ScrubTextActivity"',
            'android:mimeType="text/plain"',
        )
        self.assert_contains(
            f"{APP}/res/values/strings.xml",
            "scrub_text_title",
            "scrub_text_explanation",
            "scrub_text_removed",
            "scrub_text_copied",
        )

    def test_resources_and_java_parse(self):
        for rel in (
                f"{APP}/res/layout/activity_scrub_text.xml",
                f"{APP}/res/values/strings.xml",
                f"{APP}/AndroidManifest.xml"):
            self.assert_xml(rel)
        for rel in (
                f"{APP}/src/org/lenos/opsec/LinkScrubber.java",
                f"{APP}/src/org/lenos/opsec/ScrubTextActivity.java"):
            self.assert_java_syntax(rel)


if __name__ == "__main__":
    unittest.main()

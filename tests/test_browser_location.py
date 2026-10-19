"""No implicit location grant for the system/default browser.

GrapheneOS removes the ``DefaultPermissionGrantPolicy`` block that granted
``ACCESS_FINE_LOCATION``/``ACCESS_COARSE_LOCATION`` to the browser role holder
(or to the system handler for ``CATEGORY_APP_BROWSER``) on first boot. A
browser now needs an explicit user grant like any other app.

The GrapheneOS tree has no equivalent block in
``services/core/java/com/android/server/pm/permission/DefaultPermissionGrantPolicy.java``;
lenOS removes it in ``frameworks_base/0019``.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestBrowserLocationGrant(LenosPatchTest):
    PROJECT = "frameworks/base"
    PATCHES = ["0019-lenos-no-browser-location-grant.patch"]

    F = ("services/core/java/com/android/server/pm/permission/"
         "DefaultPermissionGrantPolicy.java")

    def test_browser_grant_block_is_removed(self):
        body = self.text(self.F)
        self.assertNotIn("KnownPackages.PACKAGE_BROWSER", body)
        self.assertNotIn("browserPackage", body)
        self.assertNotIn("CATEGORY_APP_BROWSER", body)
        # The rest of the system-handler grants stay untouched.
        self.assert_contains(
            self.F,
            "// Voice interaction",
            "getDefaultSystemHandlerActivityPackageForCategory(pm,")

    def test_no_other_location_default_for_browsers(self):
        # FOREGROUND_LOCATION_PERMISSIONS is still used by other default
        # grants (e.g. the dialer/emergency path), so it must stay declared.
        self.assert_contains(self.F, "FOREGROUND_LOCATION_PERMISSIONS.add(")

    def test_syntax(self):
        self.assert_java_syntax(self.F)


if __name__ == "__main__":
    unittest.main()

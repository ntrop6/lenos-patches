"""MediaProvider does not expose directory listings to apps without storage access.

GrapheneOS commit ``72492da1c`` ("Storage Scopes feature", 2022) closes a
metadata leak in the FUSE readdir path: upstream MediaProvider returns the
files a caller can see from its database, but the native FUSE daemon then
appends **every** directory name from the lower file system. An app with no
storage permission can therefore enumerate all user-created directory names
even though it cannot open them.

The GrapheneOS fix does two things:

* ``getFilesInDirectoryForFuse`` appends an empty-string separator followed by
  the directory names that actually contain files visible to the caller
  (computed from the media database). Apps with a read-media permission and
  the ``Android/`` directory keep the upstream behavior.
* ``MediaProviderWrapper.cpp`` treats entries after the separator as
  directories and skips appending lower-file-system directories.

lenOS ports the directory-listing part only; GrapheneOS's Storage Scopes
(per-app scopes, ``StorageScope``/``GosPackageState``) are not ported yet, so
``StorageScopesHooks`` only implements this hook. The class keeps GrapheneOS's
name and shape so the future Storage Scopes port can extend it.
"""
from __future__ import annotations

import unittest

from harness import LenosPatchTest


class TestMediaNoDirectoryListing(LenosPatchTest):
    PROJECT = "packages/providers/MediaProvider"
    PATCHES = ["0001-lenos-no-directory-listing.patch"]

    JAVA = "src/com/android/providers/media/MediaProvider.java"
    HOOKS = "src/com/android/providers/media/StorageScopesHooks.java"
    NATIVE = "jni/MediaProviderWrapper.cpp"

    def test_apps_with_media_permissions_keep_upstream_behavior(self):
        self.assert_contains(
            self.JAVA,
            'if (relativePath.equals("Android/")',
            "callingIdentity.hasPermission(PERMISSION_READ_AUDIO)",
            "callingIdentity.hasPermission(PERMISSION_READ_IMAGES)",
            "callingIdentity.hasPermission(PERMISSION_READ_VIDEO)",
            "return fileNamesList.toArray(new String[0]);")

    def test_other_apps_use_restricted_listing(self):
        self.assert_contains(
            self.JAVA,
            "return StorageScopesHooks.obtainDirContents(this, path, volumeUri, relativePath,",
            "callingIdentity, fileNamesList);")

    def test_hook_returns_only_directories_with_visible_files(self):
        self.assert_contains(
            self.HOOKS,
            "MediaColumns.MIME_TYPE + \" not like 'null'\"",
            "QUERY_ARG_SQL_GROUP_BY, MediaColumns.RELATIVE_PATH",
            'maybeAddDirEntry("Android", dirEntries, dirNamesList);',
            '// separator between files and dirs',
            'fileNamesList.add("");',
            "maybeExtractChildDirNameFromRelativePaths(")

    def test_native_skips_lower_fs_directories(self):
        self.assert_contains(
            self.NATIVE,
            "const string& path, bool* skip_add_dirs)",
            "int de_type = DT_REG;",
            "if (d_name.c_str()[0] == 0) { // see StorageScopesHooks#obtainDirContents",
            "de_type = DT_DIR;",
            "*skip_add_dirs = true;",
            "if (!skip_add_dirs) {")

    def test_single_empty_entry_still_means_no_access(self):
        # The upstream "no access to this path" contract must survive: a
        # one-element [""] array is handled before the separator logic.
        text = self.text(self.NATIVE)
        no_access = text.index("// Calling package has no storage permissions.")
        separator = text.index("if (d_name.c_str()[0] == 0) {")
        self.assertLess(no_access, separator)
        self.assert_contains(self.NATIVE, 'std::make_shared<DirectoryEntry>("", EPERM)')

    def test_javadoc_matches(self):
        self.assert_contains(
            self.JAVA,
            "<p>When the app has a storage permission, directory names are obtained from lower "
            "file system.")

    def test_syntax(self):
        for f in (self.JAVA, self.HOOKS):
            self.assert_java_syntax(f)


if __name__ == "__main__":
    unittest.main()

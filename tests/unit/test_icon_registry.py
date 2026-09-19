import unittest

from omega_serv.domain.routing.icon_registry import (
    DIRECTORY_ICON,
    EXTENSION_ICONS,
    FALLBACK_ICON,
    ICON_FILENAMES,
    MIME_ICONS,
    icon_for_file,
)


class TestIconForFile(unittest.TestCase):
    def test_directory_always_returns_folder_icon_regardless_of_name(self):
        self.assertEqual(icon_for_file("anything.txt", is_directory=True), DIRECTORY_ICON)

    def test_mime_type_takes_priority_when_known(self):
        self.assertEqual(icon_for_file("mystery-file", mime_type="application/pdf"), "pdf.svg")

    def test_unknown_mime_type_falls_back_to_extension(self):
        self.assertEqual(icon_for_file("archive.zip", mime_type="application/x-something-unheard-of"), "package.svg")

    def test_extension_used_when_no_mime_type_given(self):
        self.assertEqual(icon_for_file("script.py"), "python.svg")

    def test_extension_lookup_is_case_insensitive(self):
        self.assertEqual(icon_for_file("REPORT.PDF"), "pdf.svg")

    def test_multi_part_extension_matches_before_single_extension(self):
        self.assertEqual(icon_for_file("app-1.0.pkg.tar.zst"), "package.svg")

    def test_literal_makefile_without_extension_gets_script_icon(self):
        self.assertEqual(icon_for_file("Makefile"), "script.svg")
        self.assertEqual(icon_for_file("makefile"), "script.svg")

    def test_literal_dockerfile_gets_script_icon(self):
        self.assertEqual(icon_for_file("Dockerfile"), "script.svg")

    def test_unrecognized_file_falls_back_to_generic_icon(self):
        self.assertEqual(icon_for_file("mystery.xyzabc"), FALLBACK_ICON)

    def test_file_without_any_extension_falls_back_to_generic_icon(self):
        self.assertEqual(icon_for_file("README"), FALLBACK_ICON)

    def test_pub_extension_resolves_to_key_not_publisher(self):
        self.assertEqual(icon_for_file("id_rsa.pub"), "key.svg")


class TestIconRegistryIntegrity(unittest.TestCase):
    def test_all_mime_icon_values_are_known_filenames(self):
        self.assertTrue(set(MIME_ICONS.values()).issubset(ICON_FILENAMES))

    def test_all_extension_icon_values_are_known_filenames(self):
        self.assertTrue(set(EXTENSION_ICONS.values()).issubset(ICON_FILENAMES))

    def test_extension_keys_all_start_with_a_dot(self):
        self.assertTrue(all(ext.startswith(".") for ext in EXTENSION_ICONS))

    def test_fallback_and_directory_icons_are_known_filenames(self):
        self.assertIn(FALLBACK_ICON, ICON_FILENAMES)
        self.assertIn(DIRECTORY_ICON, ICON_FILENAMES)


if __name__ == "__main__":
    unittest.main()

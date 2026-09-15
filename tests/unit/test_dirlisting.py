# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.routing.dirlisting import DirlistingSettings, render_directory_listing_html


class TestRenderDirectoryListingHtml(unittest.TestCase):
    def test_lists_visible_entries(self):
        html_out = render_directory_listing_html("/downloads/", ["a.txt", "b.txt"], SecurityConfig())
        self.assertIn("a.txt", html_out)
        self.assertIn("b.txt", html_out)

    def test_hides_dotfiles(self):
        html_out = render_directory_listing_html("/downloads/", [".env", "a.txt"], SecurityConfig())
        self.assertNotIn(".env", html_out)
        self.assertIn("a.txt", html_out)

    def test_hides_sensitive_extensions(self):
        html_out = render_directory_listing_html("/downloads/", ["backup.sql", "a.txt"], SecurityConfig())
        self.assertNotIn("backup.sql", html_out)

    def test_escapes_malicious_filename(self):
        html_out = render_directory_listing_html("/downloads/", ["<script>alert(1)</script>.txt"], SecurityConfig())
        self.assertNotIn("<script>", html_out)
        self.assertIn("&lt;script&gt;", html_out)

    def test_escapes_url_path_in_title(self):
        html_out = render_directory_listing_html('/"><script>x</script>/', [], SecurityConfig())
        self.assertNotIn("<script>x</script>", html_out)

    def test_default_settings_include_base_css(self):
        html_out = render_directory_listing_html("/downloads/", [], SecurityConfig())
        self.assertIn("<style>", html_out)
        # Theme par defaut "omega-base" (retour utilisateur : CSS de
        # base aux couleurs d'omega-base) - une de ses couleurs reelles
        # doit apparaitre dans le CSS genere.
        self.assertIn("#00d4ff", html_out)

    def test_external_css_adds_link(self):
        html_out = render_directory_listing_html(
            "/downloads/", [], SecurityConfig(), DirlistingSettings(external_css="/.assets/css/folder.css"),
        )
        self.assertIn('<link rel="stylesheet" href="/.assets/css/folder.css">', html_out)

    def test_no_external_css_by_default(self):
        html_out = render_directory_listing_html("/downloads/", [], SecurityConfig())
        self.assertNotIn("<link rel=\"stylesheet\"", html_out)

    def test_header_shown_verbatim_when_encode_disabled(self):
        html_out = render_directory_listing_html(
            "/downloads/", [], SecurityConfig(), DirlistingSettings(show_header=True),
            header_content="<b>bienvenue</b>",
        )
        self.assertIn("<b>bienvenue</b>", html_out)

    def test_header_escaped_when_encode_enabled(self):
        html_out = render_directory_listing_html(
            "/downloads/", [], SecurityConfig(), DirlistingSettings(show_header=True, encode_header=True),
            header_content="<b>bienvenue</b>",
        )
        self.assertNotIn("<b>bienvenue</b>", html_out)
        self.assertIn("&lt;b&gt;bienvenue&lt;/b&gt;", html_out)

    def test_header_not_shown_when_show_header_disabled(self):
        html_out = render_directory_listing_html(
            "/downloads/", [], SecurityConfig(), DirlistingSettings(show_header=False),
            header_content="ne doit pas apparaitre",
        )
        self.assertNotIn("ne doit pas apparaitre", html_out)

    def test_readme_shown_when_enabled(self):
        html_out = render_directory_listing_html(
            "/downloads/", [], SecurityConfig(), DirlistingSettings(show_readme=True),
            readme_content="lisez-moi",
        )
        self.assertIn("lisez-moi", html_out)

    def test_hides_header_and_readme_files_from_listing_by_default(self):
        html_out = render_directory_listing_html(
            "/downloads/", ["HEADER.txt", "README.txt", "a.txt"], SecurityConfig(),
        )
        self.assertNotIn(">HEADER.txt<", html_out)
        self.assertNotIn(">README.txt<", html_out)
        self.assertIn("a.txt", html_out)

    def test_keeps_header_and_readme_files_when_hide_disabled(self):
        html_out = render_directory_listing_html(
            "/downloads/", ["HEADER.txt", "README.txt"], SecurityConfig(),
            DirlistingSettings(hide_header_file=False, hide_readme_file=False),
        )
        self.assertIn(">HEADER.txt<", html_out)
        self.assertIn(">README.txt<", html_out)

    def test_from_dict_uses_defaults_for_missing_keys(self):
        settings = DirlistingSettings.from_dict({})
        self.assertEqual(settings, DirlistingSettings())

    def test_from_dict_reads_provided_keys(self):
        settings = DirlistingSettings.from_dict({
            "theme": "omega-neon", "external_css": "/x.css", "show_header": True,
            "header_file": "H.txt", "encode_header": True, "hide_header_file": False,
            "show_readme": True, "readme_file": "R.txt", "encode_readme": True, "hide_readme_file": False,
        })
        self.assertEqual(settings.theme, "omega-neon")
        self.assertEqual(settings.header_file, "H.txt")
        self.assertTrue(settings.show_header)
        self.assertFalse(settings.hide_header_file)


if __name__ == "__main__":
    unittest.main()

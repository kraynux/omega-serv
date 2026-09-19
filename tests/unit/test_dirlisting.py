import unittest

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.routing.dirlisting import DirlistingSettings, render_directory_listing_html
from omega_serv.domain.routing.dirlisting_sort import DirEntryInfo


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

    def test_header_appears_above_the_index_title(self):
        html_out = render_directory_listing_html(
            "/downloads/", [], SecurityConfig(), DirlistingSettings(show_header=True),
            header_content="<p>bienvenue</p>",
        )
        self.assertLess(html_out.index("bienvenue"), html_out.index('<h1 class="omega-listing-title">Index de'))

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
        self.assertIn("HEADER.txt<", html_out)
        self.assertIn("README.txt<", html_out)

    def test_parent_directory_link_shown_when_not_at_root(self):
        html_out = render_directory_listing_html("/downloads/sub/", [], SecurityConfig())
        self.assertIn(
            '<li class="omega-dir omega-parent"><a class="omega-listing-name" href="/downloads/">'
            '<img class="omega-listing-icon" src="/.omega-serv-icons/folder.svg" alt="">'
            ".. (dossier parent)</a>"
            '<span class="omega-listing-mtime"></span><span class="omega-listing-size"></span></li>',
            html_out,
        )

    def test_parent_directory_link_absent_at_root(self):
        html_out = render_directory_listing_html("/", [], SecurityConfig())
        self.assertNotIn("dossier parent", html_out)

    def test_parent_directory_link_from_single_level_points_to_root(self):
        html_out = render_directory_listing_html("/downloads/", [], SecurityConfig())
        self.assertIn(
            '<li class="omega-dir omega-parent"><a class="omega-listing-name" href="/">'
            '<img class="omega-listing-icon" src="/.omega-serv-icons/folder.svg" alt="">'
            ".. (dossier parent)</a>"
            '<span class="omega-listing-mtime"></span><span class="omega-listing-size"></span></li>',
            html_out,
        )

    def test_folder_icon_shown_for_directory_entries(self):
        html_out = render_directory_listing_html(
            "/downloads/", ["sub", "a.txt"], SecurityConfig(),
            entry_info={"sub": DirEntryInfo(is_directory=True)},
        )
        self.assertIn(
            '<li class="omega-dir"><a class="omega-listing-name" href="/downloads/sub">'
            '<img class="omega-listing-icon" src="/.omega-serv-icons/folder.svg" alt="">sub/</a>'
            '<span class="omega-listing-mtime"></span><span class="omega-listing-size">-</span></li>',
            html_out,
        )
        self.assertIn(
            '<li class="omega-file"><a class="omega-listing-name" href="/downloads/a.txt">'
            '<img class="omega-listing-icon" src="/.omega-serv-icons/text-generic.svg" alt="">a.txt</a>',
            html_out,
        )

    def test_all_entries_default_to_file_class_without_entry_info(self):
        html_out = render_directory_listing_html("/downloads/", ["sub"], SecurityConfig())
        self.assertIn(
            '<li class="omega-file"><a class="omega-listing-name" href="/downloads/sub">'
            '<img class="omega-listing-icon" src="/.omega-serv-icons/unknow.svg" alt="">sub</a>',
            html_out,
        )

    def test_footer_shown_by_default(self):
        html_out = render_directory_listing_html("/downloads/", [], SecurityConfig())
        self.assertIn("Propuls&eacute; par OMEGA-SERV", html_out)
        self.assertIn('<hr class="omega-listing-footer-rule">', html_out)

    def test_footer_hidden_when_user_readme_is_shown(self):
        html_out = render_directory_listing_html(
            "/downloads/", [], SecurityConfig(), DirlistingSettings(show_readme=True),
            readme_content="lisez-moi",
        )
        self.assertNotIn("Propuls&eacute; par OMEGA-SERV", html_out)

    def test_footer_lives_outside_the_listing_container(self):
        html_out = render_directory_listing_html("/downloads/", [], SecurityConfig())
        self.assertIn('</div><div class="omega-listing-footer-wrap">', html_out)

    def test_no_separator_between_regular_entries(self):
        html_out = render_directory_listing_html("/downloads/", ["a.txt", "b.txt"], SecurityConfig())
        self.assertNotIn("li{padding:.4rem .2rem;border-bottom", html_out)
        self.assertIn("li.omega-parent{border-bottom", html_out)

    def test_criteria_row_appears_above_parent_directory_link(self):
        html_out = render_directory_listing_html("/downloads/sub/", [], SecurityConfig())
        self.assertLess(
            html_out.index('<li class="omega-listing-header">'),
            html_out.index('<li class="omega-dir omega-parent">'),
        )

    def test_criteria_row_has_no_border_like_regular_entries(self):
        html_out = render_directory_listing_html("/downloads/", [], SecurityConfig())
        self.assertNotIn("li.omega-listing-header{border-bottom", html_out)

    def test_criteria_row_labels_are_present_and_sortable(self):
        html_out = render_directory_listing_html("/downloads/", [], SecurityConfig())
        self.assertIn('<a class="omega-listing-name" href="?sort=name&order=desc">NOM</a>', html_out)
        self.assertIn(
            '<a class="omega-listing-mtime" href="?sort=mtime&order=asc">DERNIÈRE MODIFICATION</a>', html_out,
        )
        self.assertIn('<a class="omega-listing-size" href="?sort=size&order=asc">TAILLE</a>', html_out)

    def test_criteria_row_is_smaller_and_muted_compared_to_entries(self):
        html_out = render_directory_listing_html("/downloads/", [], SecurityConfig())
        self.assertIn(".omega-listing-header{font-size:.75rem}", html_out)
        self.assertIn(".omega-listing-header a{color:#00d4ff;opacity:.7}", html_out)

    def test_entry_shows_formatted_size_and_modification_date(self):
        html_out = render_directory_listing_html(
            "/downloads/", ["a.txt"], SecurityConfig(),
            entry_info={"a.txt": DirEntryInfo(size=2048, mtime=0.0)},
        )
        self.assertIn('<span class="omega-listing-size">2.0 Ko</span>', html_out)
        self.assertIn('<span class="omega-listing-mtime">1970-01-01 00:00 UTC</span>', html_out)

    def test_directory_shows_dash_instead_of_a_size(self):
        html_out = render_directory_listing_html(
            "/downloads/", ["sub"], SecurityConfig(),
            entry_info={"sub": DirEntryInfo(is_directory=True, mtime=0.0)},
        )
        self.assertIn('<span class="omega-listing-size">-</span>', html_out)

    def test_sort_query_reorders_entries_by_size_descending(self):
        html_out = render_directory_listing_html(
            "/downloads/", ["small.txt", "big.txt"], SecurityConfig(),
            entry_info={
                "small.txt": DirEntryInfo(size=10, mtime=0.0),
                "big.txt": DirEntryInfo(size=10_000, mtime=0.0),
            },
            query="sort=size&order=desc",
        )
        self.assertLess(html_out.index("big.txt"), html_out.index("small.txt"))

    def test_invalid_sort_query_falls_back_to_name_order(self):
        html_out = render_directory_listing_html(
            "/downloads/", ["b.txt", "a.txt"], SecurityConfig(), query="sort=nonsense",
        )
        self.assertLess(html_out.index("a.txt"), html_out.index("b.txt"))

    def test_file_links_use_a_distinct_color_from_directories(self):
        html_out = render_directory_listing_html("/downloads/", [], SecurityConfig())
        self.assertIn("li.omega-file>a{color:#b4c2e0}", html_out)

    def test_footer_still_shown_when_show_readme_enabled_but_file_absent(self):
        html_out = render_directory_listing_html(
            "/downloads/", [], SecurityConfig(), DirlistingSettings(show_readme=True),
            readme_content=None,
        )
        self.assertIn("Propuls&eacute; par OMEGA-SERV", html_out)

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

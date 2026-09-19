import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.serve_static_file import serve_static_file
from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.cache_policy import CachePolicy
from omega_serv.domain.routing.dirlisting import DirlistingSettings
from omega_serv.domain.routing.zone_resolver import Zone
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver


def _make_request(method: str, path: str) -> HttpRequest:
    return HttpRequest(
        request_id="test-id",
        remote_ip="203.0.113.10",
        peer_ip="203.0.113.10",
        method=method,
        path=path,
        raw_path=path,
        query="",
        headers=HttpHeaders.from_pairs([]),
        body=None,
        content_length=None,
        is_tls=False,
    )


class TestServeStaticFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.webroot = Path(self._tmp.name) / "webroot"
        self.webroot.mkdir()
        (self.webroot / "index.html").write_text("<html>ok</html>")
        (self.webroot / ".env").write_text("SECRET=1")
        (self.webroot / "backup.sql").write_text("dump")
        (self.webroot / "public").mkdir()
        (self.webroot / "public" / "index.html").write_text("public index")

        self.filesystem = LocalFilesystem()
        self.resolver = SafePathResolver(self.filesystem, self.webroot)
        self.security = SecurityConfig()

    def tearDown(self):
        self._tmp.cleanup()

    def _serve(self, method: str, path: str):
        request = _make_request(method, path)
        return serve_static_file(
            request, self.resolver, self.filesystem, self.security, index_files=("index.html",),
        )

    def test_get_existing_file(self):
        response = self._serve("GET", "/index.html")
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"<html>ok</html>")
        self.assertEqual(response.headers["Content-Length"], str(len(b"<html>ok</html>")))
        self.assertIn("text/html", response.headers["Content-Type"])

    def test_head_existing_file_has_no_body(self):
        response = self._serve("HEAD", "/index.html")
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"")
        self.assertEqual(response.headers["Content-Length"], str(len(b"<html>ok</html>")))

    def test_missing_file_is_404(self):
        response = self._serve("GET", "/does-not-exist.html")
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_dotfile_is_403(self):
        response = self._serve("GET", "/.env")
        self.assertEqual(response.status, HttpStatus.FORBIDDEN)

    def test_dotfile_with_access_control_override_bypasses_deny_hidden_files(self):
        request = _make_request("GET", "/.env")
        response = serve_static_file(
            request, self.resolver, self.filesystem, self.security, index_files=("index.html",),
            access_control_override=True,
        )
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"SECRET=1")

    def test_sensitive_extension_is_403(self):
        response = self._serve("GET", "/backup.sql")
        self.assertEqual(response.status, HttpStatus.FORBIDDEN)

    def test_traversal_is_403(self):
        response = self._serve("GET", "/../secure/anything")
        self.assertEqual(response.status, HttpStatus.FORBIDDEN)

    def test_directory_serves_index_file(self):
        response = self._serve("GET", "/public")
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertEqual(response.body, b"public index")

    def test_directory_without_index_is_404(self):
        (self.webroot / "empty-dir").mkdir()
        response = self._serve("GET", "/empty-dir")
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_post_method_not_allowed(self):
        response = self._serve("POST", "/index.html")
        self.assertEqual(response.status, HttpStatus.METHOD_NOT_ALLOWED)
        self.assertEqual(response.headers["Allow"], "GET, HEAD")

    def test_directory_listing_when_zone_allows_it(self):
        (self.webroot / "empty-dir").mkdir()
        request = _make_request("GET", "/empty-dir")
        response = serve_static_file(
            request, self.resolver, self.filesystem, self.security, index_files=("index.html",),
            dirlisting_zones=(Zone("/empty-dir", True),),
        )
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertIn(b"<html", response.body.lower())

    def test_directory_listing_not_shown_outside_configured_zone(self):
        (self.webroot / "empty-dir").mkdir()
        request = _make_request("GET", "/empty-dir")
        response = serve_static_file(
            request, self.resolver, self.filesystem, self.security, index_files=("index.html",),
            dirlisting_zones=(Zone("/other-zone", True),),
        )
        self.assertEqual(response.status, HttpStatus.NOT_FOUND)

    def test_directory_listing_reads_header_and_readme_from_disk(self):
        (self.webroot / "empty-dir").mkdir()
        (self.webroot / "empty-dir" / "HEADER.txt").write_text("bienvenue")
        (self.webroot / "empty-dir" / "README.txt").write_text("lisez-moi")
        (self.webroot / "empty-dir" / "data.txt").write_text("x")
        request = _make_request("GET", "/empty-dir")
        response = serve_static_file(
            request, self.resolver, self.filesystem, self.security, index_files=("index.html",),
            dirlisting_zones=(Zone("/empty-dir", True),),
            dirlisting_settings=DirlistingSettings(show_header=True, show_readme=True),
        )
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertIn(b"bienvenue", response.body)
        self.assertIn(b"lisez-moi", response.body)
        self.assertIn(b"data.txt", response.body)
        self.assertNotIn(b'>HEADER.txt<', response.body)
        self.assertNotIn(b'>README.txt<', response.body)

    def test_directory_listing_marks_subdirectories_with_folder_icon(self):
        (self.webroot / "empty-dir").mkdir()
        (self.webroot / "empty-dir" / "sub").mkdir()
        (self.webroot / "empty-dir" / "data.txt").write_text("x")
        request = _make_request("GET", "/empty-dir")
        response = serve_static_file(
            request, self.resolver, self.filesystem, self.security, index_files=("index.html",),
            dirlisting_zones=(Zone("/empty-dir", True),),
        )
        self.assertEqual(response.status, HttpStatus.OK)
        self.assertIn(
            b'<li class="omega-dir"><a class="omega-listing-name" href="/empty-dir/sub">'
            b'<img class="omega-listing-icon" src="/.omega-serv-icons/folder.svg" alt="">sub/</a>',
            response.body,
        )
        self.assertIn(
            b'<li class="omega-file"><a class="omega-listing-name" href="/empty-dir/data.txt">'
            b'<img class="omega-listing-icon" src="/.omega-serv-icons/text-generic.svg" alt="">'
            b"data.txt</a>",
            response.body,
        )

    def test_directory_listing_show_header_without_file_does_not_crash(self):
        (self.webroot / "empty-dir").mkdir()
        request = _make_request("GET", "/empty-dir")
        response = serve_static_file(
            request, self.resolver, self.filesystem, self.security, index_files=("index.html",),
            dirlisting_zones=(Zone("/empty-dir", True),),
            dirlisting_settings=DirlistingSettings(show_header=True),
        )
        self.assertEqual(response.status, HttpStatus.OK)

    def test_cache_control_applied_when_policy_given(self):
        request = _make_request("GET", "/index.html")
        policy = CachePolicy(default="public, max-age=3600")
        response = serve_static_file(
            request, self.resolver, self.filesystem, self.security, index_files=("index.html",),
            cache_policy=policy,
        )
        self.assertEqual(response.headers["Cache-Control"], "public, max-age=3600")

    def test_no_cache_control_header_when_policy_not_given(self):
        response = self._serve("GET", "/index.html")
        self.assertNotIn("Cache-Control", response.headers)


if __name__ == "__main__":
    unittest.main()

"""Outils de l'editeur de listes de chemins (OMEGA-SERV_PLAN-DETAILLE_
SENSITIVE_PATHS.md, lots 4.5/4.6)."""
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.security.path_list_tools import (
    explain_path,
    reference_news,
    replay_successful_paths,
    retired_markers,
)
from omega_serv.domain.logging.access_log_parser import parse_combined_log_line
from omega_serv.infrastructure.filesystem.local_file_access import LocalFileAccess


def _log(path: str, status: int) -> str:
    return f'198.51.100.7 - - [18/Oct/2026:10:00:00 +0000] "GET {path} HTTP/1.1" {status} 10 "-" "ua"'


class TestReplaySuccessfulPaths(unittest.TestCase):
    def test_only_successful_requests_count(self):
        lines = [_log("/textfiles/a.log", 200), _log("/textfiles/a.log", 304), _log("/.env", 403), _log("/x.log", 404)]
        hits = replay_successful_paths("/.env\n/*.log\n", "any_segment", lines)
        self.assertEqual([(h.line, h.entry, h.hits) for h in hits], [(2, "/*.log", 2)])
        self.assertEqual(hits[0].examples, ("/textfiles/a.log",))

    def test_query_stripped_and_encoding_decoded(self):
        hits = replay_successful_paths("/.env\n", "any_segment", [_log("/%2eenv?x=1", 200)])
        self.assertEqual(hits[0].examples, ("/.env",))

    def test_exceptions_remove_paths(self):
        lines = [_log("/textfiles/a.log", 200)]
        self.assertEqual(replay_successful_paths("/*.log\n!/textfiles/\n", "any_segment", lines), ())

    def test_sorted_by_hits(self):
        lines = [_log("/a", 200)] + [_log("/b", 200)] * 3
        self.assertEqual([h.entry for h in replay_successful_paths("/a\n/b\n", "root", lines)], ["/b", "/a"])

    def test_unparseable_lines_ignored(self):
        self.assertEqual(replay_successful_paths("/a\n", "root", ["n'importe quoi", ""]), ())


class TestReferenceNews(unittest.TestCase):
    def test_missing_entries_proposed(self):
        self.assertEqual(reference_news("/a\n", "#t\n/a\n/b\n!/c\n"), ("/b", "!/c"))

    def test_case_insensitive_and_exceptions_count_as_known(self):
        self.assertEqual(reference_news("/A\n!/b\n", "/a\n/b\n"), ())

    def test_retired_entries_never_proposed_again(self):
        self.assertEqual(reference_news("/a\n#retire: /b\n", "/a\n/b\n"), ())


class TestRetiredMarkers(unittest.TestCase):
    def test_removed_reference_entry_is_marked(self):
        self.assertEqual(retired_markers("/a\n/b\n", "/a\n", "/a\n/b\n"), ("#retire: /b",))

    def test_removed_personal_entry_is_not_marked(self):
        self.assertEqual(retired_markers("/a\n/perso\n", "/a\n", "/a\n"), ())

    def test_entry_turned_into_exception_is_not_marked(self):
        self.assertEqual(retired_markers("/a\n/b\n", "/a\n!/b\n", "/a\n/b\n"), ())

    def test_already_marked_not_duplicated(self):
        self.assertEqual(retired_markers("/a\n/b\n", "/a\n#retire: /b\n", "/a\n/b\n"), ())


class TestExplainPath(unittest.TestCase):
    _TEXT = "/.env\n/api\n!/api/v1\n"

    def test_detected(self):
        self.assertIn("DÉTECTÉ par la ligne 1", explain_path(self._TEXT, "any_segment", "/blog/.env"))

    def test_exception_wins(self):
        self.assertIn("l'emporte sur la ligne 2", explain_path(self._TEXT, "root", "/api/v1/users"))

    def test_no_match(self):
        self.assertIn("aucune ligne", explain_path(self._TEXT, "root", "/index.html"))

    def test_encoded_value_normalized(self):
        self.assertIn("DÉTECTÉ", explain_path(self._TEXT, "any_segment", "/%2e%65nv"))

    def test_errors_block_the_test(self):
        self.assertIn("corrigez", explain_path("admin\n", "root", "/admin"))


class TestAccessLogParserPath(unittest.TestCase):
    def test_path_extracted(self):
        self.assertEqual(parse_combined_log_line(_log("/a?b=1", 200)).path, "/a?b=1")

    def test_garbled_request_line_gives_empty_path(self):
        line = '198.51.100.7 - - [18/Oct/2026:10:00:00 +0000] "-" 400 0 "-" "-"'
        self.assertEqual(parse_combined_log_line(line).path, "")


class TestReadTailLines(unittest.TestCase):
    def test_tail_drops_partial_first_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "access.log"
            log.write_text("".join(f"ligne-{i:03d}\n" for i in range(100)))
            lines = LocalFileAccess().read_tail_lines(log, 50)
            self.assertEqual(lines[-1], "ligne-099")
            self.assertTrue(all(line.startswith("ligne-") and len(line) == 9 for line in lines))

    def test_missing_file(self):
        self.assertEqual(LocalFileAccess().read_tail_lines(Path("/nexiste/pas.log"), 100), [])


if __name__ == "__main__":
    unittest.main()

"""Verification manuelle des mises a jour (2026-11-07) : lecture de download/sha.txt et comparaison."""
from __future__ import annotations

import unittest

from omega_serv.application.updates.check_updates import check_for_update
from omega_serv.domain.updates.release_check import (
    DOWNLOAD_BASE_URL,
    UpdateStatus,
    compare_with_published,
    published_versions,
    version_key,
)

_SHA = """Controle d integrite des archives OMEGA-SERV

version 2.5.0 :

c42d5f4d  omega-serv-2.5.0.tar.gz

version 2.0.1 :

c067c2c1  omega-serv-2.0.1.tar.gz

version 1.0.0 :

7e73ecfc  omega-serv-1.0.0.tar.gz
"""


class _Source:
    def __init__(self, content: str | None) -> None:
        self.content = content

    def fetch_sha_list(self) -> str | None:
        return self.content


class TestReleaseCheck(unittest.TestCase):
    def test_version_key(self):
        self.assertEqual(version_key("2.6.0"), (2, 6, 0))
        self.assertGreater(version_key("2.10.0"), version_key("2.9.1"))
        self.assertIsNone(version_key("2.6.0-dev"))
        self.assertIsNone(version_key(""))

    def test_published_versions_sorted_highest_first(self):
        self.assertEqual(published_versions(_SHA), ["2.5.0", "2.0.1", "1.0.0"])
        self.assertEqual(published_versions(_SHA + "aa  omega-serv-2.10.0.tar.gz\n")[0], "2.10.0")

    def test_update_available_gives_archive_and_notes_urls(self):
        check = compare_with_published("2.0.1", _SHA)
        self.assertIs(check.status, UpdateStatus.UPDATE_AVAILABLE)
        self.assertEqual(check.latest, "2.5.0")
        self.assertEqual(check.archive_url, DOWNLOAD_BASE_URL + "omega-serv-2.5.0.tar.gz")
        self.assertEqual(check.notes_url, DOWNLOAD_BASE_URL + "omega-serv-2.5.0-nouveautes.txt")

    def test_up_to_date_and_ahead(self):
        self.assertIs(compare_with_published("2.5.0", _SHA).status, UpdateStatus.UP_TO_DATE)
        ahead = compare_with_published("2.6.0", _SHA)
        self.assertIs(ahead.status, UpdateStatus.AHEAD)
        self.assertEqual(ahead.latest, "2.5.0")

    def test_unreachable_or_unreadable_is_unknown(self):
        self.assertIs(compare_with_published("2.6.0", None).status, UpdateStatus.UNKNOWN)
        self.assertIs(compare_with_published("2.6.0", "<html>erreur</html>").status, UpdateStatus.UNKNOWN)
        self.assertIs(compare_with_published("inconnue", _SHA).status, UpdateStatus.UNKNOWN)

    def test_use_case_reads_the_source(self):
        self.assertIs(check_for_update(_Source(_SHA), "1.0.0").status, UpdateStatus.UPDATE_AVAILABLE)
        self.assertIs(check_for_update(_Source(None), "1.0.0").status, UpdateStatus.UNKNOWN)


if __name__ == "__main__":
    unittest.main()

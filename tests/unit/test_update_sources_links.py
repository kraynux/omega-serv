# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Procedure de l'auteur (2026-11-22) : GitHub, puis le site kraynux, puis le site craftdark ; les liens d'archive
et de nouveautes sont ceux de la source qui a repondu."""
from omega_serv.application.updates.check_updates import check_for_update
from omega_serv.domain.updates.release_check import UpdateStatus

SHA = "abc  omega-serv-9.0.0.tar.gz\n"
CRAFTDARK = "https://craftdark.snake-mackarel.ts.net/omega-serv/download/"


class _Source:
    def __init__(self, base_url: str, from_github: bool) -> None:
        self.base_url, self.from_github = base_url, from_github

    def fetch_sha_list(self) -> str:
        return SHA


def test_liens_du_site_craftdark() -> None:
    check = check_for_update(_Source(CRAFTDARK, False), "1.0.0")
    assert check.status is UpdateStatus.UPDATE_AVAILABLE
    assert check.archive_url == CRAFTDARK + "omega-serv-9.0.0.tar.gz"
    assert check.notes_url == CRAFTDARK + "omega-serv-9.0.0-nouveautes.txt"


def test_liens_de_la_release_github() -> None:
    check = check_for_update(_Source("", True), "1.0.0")
    assert check.archive_url == "https://github.com/kraynux/omega-serv/releases/download/v9.0.0/omega-serv-9.0.0.tar.gz"
    assert check.notes_url == "https://github.com/kraynux/omega-serv/releases/tag/v9.0.0"


def test_ordre_des_sources() -> None:
    from omega_serv.infrastructure.updates.https_release_source import HttpsReleaseSource

    labels = [getattr(s, "label", "") for s in HttpsReleaseSource("1.0.0")._chain._sources]
    assert labels == ["GitHub", "https://kraynux.snake-mackarel.ts.net/", "https://craftdark.snake-mackarel.ts.net/"]

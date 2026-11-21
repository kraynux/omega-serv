# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""HttpResponse.force_security_headers (2026-11-19, ETUDE_PROXY_ET_MEMOIRE §12) : une passe, meme resultat que
force_security_header() appele pour chaque couple dans l'ordre - contenu ET ordre des en-tetes."""
from __future__ import annotations

import itertools

import pytest

from omega_serv.domain.http.response import HttpResponse

_NAMES = ["Content-Type", "content-type", "X-Frame-Options", "x-frame-options", "X-FRAME-OPTIONS", "Server",
          "K", "k", "K", "İ", "i̇"]  # signe kelvin et I point suscrit : minuscules non triviales


def _one_by_one(initial: list[str], items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    response = HttpResponse(status=200, headers={key: "amont" for key in initial})
    for name, value in items:
        response.force_security_header(name, value)
    return list(response.headers.items())


def _batch(initial: list[str], items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    response = HttpResponse(status=200, headers={key: "amont" for key in initial})
    response.force_security_headers(items)
    return list(response.headers.items())


@pytest.mark.parametrize("initial", [list(c) for n in range(4) for c in itertools.combinations(_NAMES, n)][::7])
def test_batch_matches_one_by_one(initial: list[str]) -> None:
    for items in ([], [("x-frame-options", "DENY")], [("X-Frame-Options", "DENY"), ("x-frame-options", "SAMEORIGIN")],
                  [("k", "1"), ("K", "2"), ("Server", "3")], [("i̇", "1"), ("İ", "2")],
                  [(name, str(i)) for i, name in enumerate(_NAMES)]):
        assert _batch(initial, items) == _one_by_one(initial, items)


def test_backend_case_variant_replaced_in_place() -> None:
    response = HttpResponse(status=200, headers={"x-frame-options": "ALLOWALL", "Content-Type": "text/html"})
    response.force_security_headers([("X-Frame-Options", "DENY")])
    assert response.headers == {"Content-Type": "text/html", "X-Frame-Options": "DENY"}

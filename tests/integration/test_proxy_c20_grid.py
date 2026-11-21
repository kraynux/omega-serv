# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Grille C20 (plan proxy natif v2, lot 0, etape 0.4) : options de securite facultatives, meme fonctionnement quelle
que soit la combinaison, et memes resultats dans les deux moteurs.

Pour chaque combinaison : un serveur moteur Python et un serveur moteur natif (sous son superviseur, avec
`waf.native_check_every = 1` quand le WAF est actif : chaque requete jugee propre par le natif est aussi jugee par
Python, qui journalise tout desaccord - S25). Le meme mini-corpus, sur une route proxifiee et sur une route statique,
doit donner les memes statuts et le meme nombre d'alertes WAF dans les deux moteurs, et zero desaccord.

Couper le WAF coupe aussi la liste de blocage et la limite de debit, dans les deux moteurs (§3.5, R3 : comportement
actuel, garde ici tel quel)."""
from __future__ import annotations

import copy
import unittest

from tests.integration.proxy_harness import BANNED_IP, NATIVE_BINARY, ProxyProject, ScriptedBackend

ATTACK = "?id=1%20union%20select%20password%20from%20users"
WAF_BLOCK = {"enabled": True, "mode": "block"}
COMBINATIONS: dict[str, dict] = {
    "aucune": {},
    "waf-block": {"waf": WAF_BLOCK},
    "waf-log-only": {"waf": {"enabled": True, "mode": "log-only"}},
    "waf-limite-de-debit": {"waf": {**WAF_BLOCK, "rate_limit": {"enabled": True,
                                                                "global": {"requests": 2, "window_seconds": 60}}}},
    "auth": {"auth": {"enabled": True}},
    "waf-et-auth": {"waf": WAF_BLOCK, "auth": {"enabled": True}},
}
# Statuts attendus : proxy propre, proxy attaque, adresse bannie, zone protegee, statique attaque, statique propre,
# puis trois requetes de la meme adresse.
EXPECTED: dict[str, tuple] = {
    "aucune": (200, 200, 200, 200, 200, 200, (200, 200, 200)),
    "waf-block": (200, 403, 451, 200, 403, 200, (200, 200, 200)),
    "waf-log-only": (200, 200, None, 200, 200, 200, (200, 200, 200)),  # None : ce que Python decide, compare seulement
    "waf-limite-de-debit": (200, 403, 451, 200, 403, 200, (200, 200, 429)),
    "auth": (200, 200, 200, 401, 200, 200, (200, 200, 200)),
    "waf-et-auth": (200, 403, 451, 401, 403, 200, (200, 200, 200)),
}


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestC20Grid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = ScriptedBackend()

    @classmethod
    def tearDownClass(cls):
        cls.backend.stop()

    def _observe(self, engine: str, options: dict, proxy: dict | None = None) -> tuple[tuple, int, list[str]]:
        options = copy.deepcopy(options)
        if engine == "native" and "waf" in options:
            options["waf"]["native_check_every"] = 1
        project = ProxyProject(engine, self.backend.port, options=options, proxy=proxy)
        try:
            project.start()
            self.assertEqual(project.effective_engine(), engine)
            offsets = project.log_offsets()
            same = project.next_address()
            statuses = (
                project.request("GET", "/api/ok")[0],
                project.request("GET", "/api/ok" + ATTACK)[0],
                project.request("GET", "/api/ok", address=BANNED_IP)[0],
                project.request("GET", "/api/prive")[0],
                project.request("GET", "/" + ATTACK)[0],
                project.request("GET", "/")[0],
                tuple(project.request("GET", "/api/ok", address=same)[0] for _ in range(3)),
            )
            alerts = len(project.new_lines("waf-alerts", offsets))
            errors = project.new_lines("error", offsets, wait=0)
        finally:
            project.stop()
        return statuses, alerts, errors

    def _check(self, name: str) -> None:
        python = self._observe("python", COMBINATIONS[name])
        native = self._observe("native", COMBINATIONS[name])
        expected = EXPECTED[name]
        for index, (want, got) in enumerate(zip(expected, python[0], strict=True)):
            if want is not None:
                self.assertEqual(got, want, f"{name} : requete {index}, moteur Python")
        # Plan proxy natif v2, lot 4 : la zone relayee par le natif (reverse_proxy.engine = native) aussi.
        relay = self._observe("native", COMBINATIONS[name], proxy={"engine": "native"})
        for label, observed in (("natif (zone confiee)", native), ("relais natif", relay)):
            self.assertEqual(observed[0], python[0], f"{name} : statuts differents, {label}")
            self.assertEqual(observed[1], python[1], f"{name} : nombre d'alertes WAF different, {label}")
            disagreements = [line for line in observed[2] if "desaccord" in line]
            self.assertEqual(disagreements, [], f"{name} : desaccord du filtre natif (S25), {label}")

    def test_no_security_option(self):
        self._check("aucune")

    def test_waf_block(self):
        self._check("waf-block")

    def test_waf_log_only(self):
        self._check("waf-log-only")

    def test_waf_with_rate_limit(self):
        self._check("waf-limite-de-debit")

    def test_auth_only(self):
        self._check("auth")

    def test_waf_and_auth(self):
        self._check("waf-et-auth")


if __name__ == "__main__":
    unittest.main()

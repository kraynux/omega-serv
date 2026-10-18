"""Le renouvellement Let's Encrypt (certbot --webroot) ne doit JAMAIS etre
bloque par le WAF livre (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.2,
lot 2.1) : `/.well-known/acme-challenge/` reste inspecte (aucune exclusion
globale, qui ouvrirait un contournement complet du WAF), donc on verifie
ici qu'aucun pack LIVRE ni aucune liste de reference ne produit de finding
sur une vraie requete de validation.

Les jetons ACME sont en base64url (RFC 8555 §8.3 : alphabet [A-Za-z0-9_-],
43 caracteres pour certbot) ; le User-Agent est celui des serveurs de
validation de Let's Encrypt."""
import json
import random
import string
import unittest
from pathlib import Path

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.entities import KeywordListDefinition
from omega_serv.domain.security.waf.keyword_list import (
    build_rule_pack_from_keyword_list,
    tokens_from_text,
)
from omega_serv.domain.security.waf.rule_validation import parse_rule_pack
from omega_serv.domain.security.waf.signature_engine import compile_rule_pack
from omega_serv.infrastructure.waf.python_waf_engine import PythonWafEngine

_ROOT = Path(__file__).resolve().parents[2]
_RULES_DIR = _ROOT / "secure" / "waf" / "rules"
_REFERENCES = _ROOT / "src" / "omega_serv" / "infrastructure" / "waf" / "keyword_references"
# custom.json n'est jamais livre (exclu par build-release.sh) : il contient
# les regles personnelles de l'operateur, pas le WAF par defaut.
_NOT_SHIPPED = {"custom.json"}
_BASE64URL = string.ascii_letters + string.digits + "-_"
_USER_AGENTS = (
    "Mozilla/5.0 (compatible; Let's Encrypt validation server; +https://www.letsencrypt.org)",
    "CertbotACMEClient/2.11.0 (certbot; Linux) Authenticator/webroot Installer/None",
)


def _shipped_engine() -> PythonWafEngine:
    packs = [
        compile_rule_pack(parse_rule_pack(json.loads(path.read_text(encoding="utf-8"))))
        for path in sorted(_RULES_DIR.glob("*.json")) if path.name not in _NOT_SHIPPED
    ]
    for name, anchor in (("sensitive-paths-hostile", "any_segment"), ("sensitive-paths-probe", "root")):
        definition = KeywordListDefinition(
            id=name, scope=("path",), file=f"{name}.txt", weight=6, match="path", anchor=anchor,
        )
        text = (_REFERENCES / f"{name}.txt").read_text(encoding="utf-8")
        packs.append(compile_rule_pack(build_rule_pack_from_keyword_list(definition, tokens_from_text(text))))
    return PythonWafEngine(tuple(packs), parse_waf_config({"mode": "block"}))


def _request(path: str, user_agent: str) -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method="GET",
        path=path, raw_path=path, query="", headers=HttpHeaders.from_pairs([("User-Agent", user_agent)]),
        body=None, content_length=None, is_tls=False,
    )


class TestAcmeChallengeNeverBlocked(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = _shipped_engine()

    def _assert_clean(self, token: str):
        for user_agent in _USER_AGENTS:
            decision = self.engine.inspect(_request(f"/.well-known/acme-challenge/{token}", user_agent))
            self.assertEqual(decision.findings, (), f"jeton {token!r} -> {[f.rule_id for f in decision.findings]}")

    def test_shipped_packs_are_loaded(self):
        self.assertGreaterEqual(len(self.engine._compiled_packs), 8)

    def test_random_certbot_tokens(self):
        rng = random.Random(20261018)
        for _ in range(3000):
            self._assert_clean("".join(rng.choice(_BASE64URL) for _ in range(43)))

    def test_list_words_inside_a_real_length_token(self):
        """Un vrai jeton (43 caracteres aleatoires) peut CONTENIR un mot de
        liste par hasard : les frontieres de segments l'empechent de matcher."""
        rng = random.Random(7)
        for word in ("admin", "wp-admin", "wp-login", "backup", "env", "git", "phpmyadmin", "xmlrpc",
                     "adminer", "config", "sql", "debug", "test", "actuator", "-_-_"):
            for position in ("start", "middle", "end"):
                filler = "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(43 - len(word)))
                token = {"start": word + filler, "middle": filler[:10] + word + filler[10:],
                         "end": filler + word}[position]
                with self.subTest(word=word, position=position):
                    self._assert_clean(token)

    def test_segment_exactly_equal_to_an_entry_is_detected_by_design(self):
        """`/.well-known/acme-challenge/wp-admin` n'est PAS un jeton certbot
        (43 caracteres aleatoires) mais une sonde : la detecter est voulu."""
        decision = self.engine.inspect(_request("/.well-known/acme-challenge/wp-admin", _USER_AGENTS[0]))
        self.assertTrue(decision.findings)


if __name__ == "__main__":
    unittest.main()

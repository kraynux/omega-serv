# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Banc differentiel du reverse proxy, lance par pytest (plan proxy natif v2, lot 0, etape 0.3).

Profil `proxy` de tools/differential/differential.py : meme corpus contre le moteur Python et contre le moteur natif
sous son vrai superviseur ; reponses (octets, sans `Date`), lignes d'access.log, waf-alerts et error.log doivent etre
IDENTIQUES quand le natif confie les zones a Python ; relais natif (lots 4 a 11) : seul le decoupage vers le client
differe. Lot 11 : `auto` (defaut) relaie par le natif."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BINARY = REPO / "native" / "omega-http-core" / "build-release" / "omega-http-core"


def _differential():
    spec = importlib.util.spec_from_file_location("differential", REPO / "tools" / "differential" / "differential.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _without_framing(case: dict) -> dict:
    """Lot 5 : le decoupage vers le client (chunked chez le natif en flux) est le seul ecart admis."""
    response = {key: value for key, value in case.get("response", {}).items() if key != "framing"}
    return {**case, "response": response}


@unittest.skipUnless(BINARY.is_file(), "binaire natif non construit")
class TestProxyDifferential(unittest.TestCase):
    def test_python_and_native_engines_answer_and_log_identically(self):
        # Zones confiees a Python sous le natif (reverse_proxy.engine = python) : tout doit etre identique, octet pour
        # octet. Avant le lot 11, c'etait le trajet de `auto`.
        differential = _differential()
        with tempfile.TemporaryDirectory(prefix="omega-diff-proxy-") as tmp:
            folder, python_out, native_out = Path(tmp) / "projet", Path(tmp) / "python.json", Path(tmp) / "native.json"
            differential.prepare(folder, "proxy")
            differential.run(folder, python_out, "python")
            differential.run(folder, native_out, "native-handoff", BINARY)
            python_cases = json.loads(python_out.read_text())["cases"]
            native_cases = json.loads(native_out.read_text())["cases"]
        self.assertEqual(len(python_cases), len(differential.proxy_corpus()))
        # Le corpus a bien servi : backend atteint, refus de securite journalises (un test vide serait identique).
        self.assertTrue(python_cases["proxy-ok"]["response"]["head"].startswith("HTTP/1.1 200 "))
        self.assertEqual(len(python_cases["proxy-waf-attack"]["waf_alerts"]), 1)
        self.assertTrue(python_cases["proxy-blocklist"]["response"]["head"].startswith("HTTP/1.1 451 "))
        different = sorted(name for name in python_cases if python_cases[name] != native_cases.get(name))
        self.assertEqual(different, [], "cas differents entre les moteurs (python.json / native.json)")

    def test_native_relay_answers_and_logs_like_python(self):
        # Plan proxy natif v2, lots 4 et 5 : zone relayee par le natif (reverse_proxy.engine = native). Reponses
        # chunked et delimitees par la fermeture relayees en flux : le banc compare le corps decode (le decoupage vers
        # le client, Content-Length chez Python et chunked chez le natif, est le seul ecart admis, voir differential).
        differential = _differential()
        with tempfile.TemporaryDirectory(prefix="omega-diff-relay-") as tmp:
            folder, python_out, relay_out = Path(tmp) / "projet", Path(tmp) / "python.json", Path(tmp) / "relay.json"
            differential.prepare(folder, "proxy")
            differential.run(folder, python_out, "python")
            differential.run(folder, relay_out, "native-relay", BINARY)
            python_cases = json.loads(python_out.read_text())["cases"]
            relay_cases = json.loads(relay_out.read_text())["cases"]
        for name in ("proxy-chunked", "proxy-close"):  # le corpus garde ses cas chunked et fermeture
            self.assertEqual(relay_cases[name]["response"]["framing"], "chunked", name)
            self.assertNotIn("framing", python_cases[name]["response"], name)
        different = sorted(name for name in python_cases if _without_framing(python_cases[name])
                           != _without_framing(relay_cases.get(name, {})))
        self.assertEqual(different, [], "cas differents entre le proxy Python et le relais natif")

    def test_default_auto_relays_like_python(self):
        # Lot 11 : AUTO_PENDING leve - le reglage par defaut relaie par le natif, avec le meme resultat que Python
        # (decoupage vers le client excepte).
        differential = _differential()
        with tempfile.TemporaryDirectory(prefix="omega-diff-auto-") as tmp:
            folder, python_out, auto_out = Path(tmp) / "projet", Path(tmp) / "python.json", Path(tmp) / "auto.json"
            differential.prepare(folder, "proxy")
            differential.run(folder, python_out, "python")
            differential.run(folder, auto_out, "native-serve", BINARY)
            python_cases = json.loads(python_out.read_text())["cases"]
            auto_cases = json.loads(auto_out.read_text())["cases"]
        self.assertEqual(auto_cases["proxy-chunked"]["response"]["framing"], "chunked")  # relaye par le natif
        different = sorted(name for name in python_cases if _without_framing(python_cases[name])
                           != _without_framing(auto_cases.get(name, {})))
        self.assertEqual(different, [], "cas differents entre le proxy Python et auto sous le natif")


if __name__ == "__main__":
    unittest.main()

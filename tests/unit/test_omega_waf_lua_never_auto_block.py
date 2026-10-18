"""Le VRAI omega-waf.lua (projet ~/DEV/WAF/omega-waf) execute via le pont
lighty.* d'omega-serv - OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md lot 11 :
reseaux jamais bannis automatiquement, motifs de chemins sensibles corriges.
Ignore si le projet omega-waf n'est pas present sur la machine."""
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.config import ReputationConfig, WafConfig
from omega_serv.infrastructure.waf.lua_waf_adapter import LuaWafAdapter

_SCRIPT = Path.home() / "DEV" / "WAF" / "omega-waf" / "omega-waf.lua"


def _request(ip: str, path: str) -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip=ip, peer_ip=ip, method="GET", path=path, raw_path=path, query="",
        headers=HttpHeaders.from_pairs([("User-Agent", "Mozilla/5.0")]), body=None, content_length=None,
        is_tls=False,
    )


@unittest.skipUnless(_SCRIPT.exists(), f"script absent : {_SCRIPT}")
class _OmegaWafCase(unittest.TestCase):
    networks: tuple[str, ...] | None = None  # None = valeurs par defaut d'omega-serv

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / "rules.d").mkdir()
        self.blocklist = root / "magnet-blocklist.txt"
        self.blocklist_log = root / "blocklist.log"
        paths = {
            "blocklist_file": str(self.blocklist), "rules_dir": str(root / "rules.d") + "/",
            "alerts_log": str(root / "alerts.log"), "blocklist_log": str(self.blocklist_log),
            "rate_store_file": str(root / "rate-store.lua"),
        }
        reputation = ReputationConfig() if self.networks is None else ReputationConfig(never_auto_block=self.networks)
        self.adapter = LuaWafAdapter(_SCRIPT.read_text(encoding="utf-8"), WafConfig(mode="block", reputation=reputation), paths)

    def tearDown(self):
        self._tmp.cleanup()

    def hammer(self, ip: str, path: str = "/.env", times: int = 4):
        return [self.adapter.inspect(_request(ip, path)) for _ in range(times)]

    def banned(self, ip: str) -> bool:
        return self.blocklist.exists() and ip in self.blocklist.read_text().split()


class TestNeverAutoBlock(_OmegaWafCase):
    def test_public_address_is_banned_after_recidive(self):
        decisions = self.hammer("198.51.100.7")
        self.assertTrue(self.banned("198.51.100.7"))
        self.assertEqual(decisions[-1].status_code, 451)
        self.assertIn("AJOUT BLOCKLIST ip=198.51.100.7", self.blocklist_log.read_text())

    def test_local_tailscale_and_lan_are_never_banned(self):
        for ip in ("127.0.0.1", "192.168.1.20", "100.106.10.47", "10.0.0.3", "fd7a:115c:a1e0::5", "::ffff:192.168.1.20"):
            with self.subTest(ip=ip):
                decisions = self.hammer(ip)
                self.assertFalse(self.banned(ip))
                self.assertTrue(all(d.status_code != 451 for d in decisions), "jamais d'escalade en 451")
                self.assertTrue(all(d.action != "allow" for d in decisions), "la requete reste refusee/journalisee")

    def test_public_tailscale_lookalike_is_banned(self):
        self.hammer("100.12.196.99")  # 100.0.0.0/8 contient des adresses PUBLIQUES
        self.assertTrue(self.banned("100.12.196.99"))


class TestInjectedListWins(_OmegaWafCase):
    networks = ("10.0.0.0/8",)

    def test_only_injected_networks_are_exempt(self):
        self.hammer("192.168.1.20")
        self.assertTrue(self.banned("192.168.1.20"), "192.168.x n'est plus exempte si omega-serv ne l'injecte pas")
        self.hammer("10.0.0.3")
        self.assertFalse(self.banned("10.0.0.3"))


class TestSensitivePatternsFixed(_OmegaWafCase):
    def test_variants_now_detected(self):
        for path in ("/phpmyadmin.bak", "/adminer.old", "/wp-admin.zip", "/wp-login.php.bak"):
            with self.subTest(path=path):
                self.assertNotEqual(self.adapter.inspect(_request("203.0.113.9", path)).action, "allow")

    def test_former_false_matches_are_gone(self):
        """Avant : %a/%w acceptaient n'importe quelle lettre en tete."""
        for path in ("/xdminer.old", "/1p-admin.zip", "/.hpmyadmin.x"):
            with self.subTest(path=path):
                self.assertEqual(self.adapter.inspect(_request("203.0.113.10", path)).action, "allow")


if __name__ == "__main__":
    unittest.main()

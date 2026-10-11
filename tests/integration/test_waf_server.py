"""Tests d'integration Phase 5 (WAF) : serveur reel, connexions TCP
reelles sur 127.0.0.1, aucun mock - meme discipline que
test_static_server.py."""
import asyncio
import http.client
import json
import tempfile
import time
import unittest
from pathlib import Path

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger

try:
    import lupa  # noqa: F401 - detection seulement, voir _MAGNET_AVAILABLE
    _MAGNET_AVAILABLE = True
except ImportError:
    _MAGNET_AVAILABLE = False

_SQLI_PACK = {
    "version": 1,
    "pack": "body-sqli",
    "enabled": True,
    "rules": [
        {"id": "SQLI-001", "description": "Union select", "scope": ["query"], "pattern": r"union\s+select", "weight": 5},
    ],
}

_REFERER_SPAM_PACK = {
    "version": 1,
    "pack": "referer-spam",
    "enabled": True,
    "rules": [
        {"id": "REFERER-001", "description": "Referer spammeur", "scope": ["referer"], "pattern": "casino", "weight": 5},
    ],
}


class _WafServerTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("hello world")

        rules_dir = self.root / "secure" / "waf" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "body-sqli.json").write_text(json.dumps(_SQLI_PACK))
        (rules_dir / "referer-spam.json").write_text(json.dumps(_REFERER_SPAM_PACK))

        keywords_dir = rules_dir / "keywords"
        keywords_dir.mkdir()
        (keywords_dir / "referer-spam.txt").write_text("# liste de test\ncasino\nviagra\n")

        scripts_dir = self.root / "secure" / "waf" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "block-magic.lua").write_text(
            "local env = lighty.env or {}\n"
            "local path = env['uri.path'] or ''\n"
            "local query = env['uri.query'] or ''\n"
            "if string.find(path .. ' ' .. query, 'magic%-word') then\n"
            "    return 403\n"
            "end\n"
            "return 0\n"
        )
        (scripts_dir / "slow.lua").write_text(
            "local t0 = os.clock()\n"
            "while os.clock() - t0 < 0.3 do end\n"
            "return 0\n"
        )

        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    async def _start(self, waf_settings: dict):
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0},
            "options": {"waf": {"enabled": True, **waf_settings}},
        })
        self.server = build_server(self.config, self.root, self.filesystem, self.logger)
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    def _request_sync(self, method, path, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, path, headers=headers or {})
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, dict(resp.getheaders()), data
        finally:
            conn.close()

    async def _request(self, method, path, headers=None):
        return await asyncio.to_thread(self._request_sync, method, path, headers)


class TestWafSignatureBlocking(_WafServerTestCase):
    async def test_clean_request_passes(self):
        await self._start({"mode": "block", "rules": {"paths": ["secure/waf/rules/body-sqli.json"]}})
        status, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)

    async def test_sqli_query_blocked_in_block_mode(self):
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 5},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
        })
        status, _, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(status, 403)

    async def test_sqli_query_only_logged_in_log_only_mode(self):
        await self._start({
            "mode": "log-only",
            "scoring": {"block_threshold": 5},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
        })
        status, _, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(status, 200)
        alert_log = self.root / "var" / "log" / "waf-alerts.log"
        self.assertTrue(alert_log.exists())
        record = json.loads(alert_log.read_text().splitlines()[-1])
        self.assertEqual(record["rules"], ["SQLI-001"])

    async def test_healthz_excluded_even_with_malicious_query(self):
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 1},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            "exclusions": {"path_prefixes": ["/healthz"]},
        })
        status, _, _ = await self._request("GET", "/healthz?q=union%20select%201")
        self.assertEqual(status, 200)


class TestWafRefererScope(_WafServerTestCase):
    async def test_clean_referer_passes(self):
        await self._start({"mode": "block", "rules": {"paths": ["secure/waf/rules/referer-spam.json"]}})
        status, _, _ = await self._request("GET", "/index.html", headers={"Referer": "https://example.org/"})
        self.assertEqual(status, 200)

    async def test_spam_referer_blocked(self):
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 5},
            "rules": {"paths": ["secure/waf/rules/referer-spam.json"]},
        })
        status, _, _ = await self._request(
            "GET", "/index.html", headers={"Referer": "https://evil-casino-spam.example/"},
        )
        self.assertEqual(status, 403)

    async def test_word_in_another_header_does_not_trigger_referer_rule(self):
        """Preuve que le scope referer n'inspecte QUE Referer - un autre
        en-tete contenant le meme mot ne doit jamais declencher la regle
        (contrairement a scope=headers, qui aurait matche)."""
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 5},
            "rules": {"paths": ["secure/waf/rules/referer-spam.json"]},
        })
        status, _, _ = await self._request(
            "GET", "/index.html",
            headers={"Referer": "https://example.org/", "X-Custom": "casino"},
        )
        self.assertEqual(status, 200)


class TestWafKeywordLists(_WafServerTestCase):
    async def test_clean_referer_passes(self):
        await self._start({
            "mode": "block",
            "rules": {"keyword_lists": [
                {"id": "REFERER-SPAM", "scope": ["referer"], "file": "secure/waf/rules/keywords/referer-spam.txt"},
            ]},
        })
        status, _, _ = await self._request("GET", "/index.html", headers={"Referer": "https://example.org/"})
        self.assertEqual(status, 200)

    async def test_keyword_from_file_is_blocked(self):
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 5},
            "rules": {"keyword_lists": [
                {"id": "REFERER-SPAM", "scope": ["referer"], "file": "secure/waf/rules/keywords/referer-spam.txt", "weight": 5},
            ]},
        })
        status, _, _ = await self._request(
            "GET", "/index.html", headers={"Referer": "https://evil-casino-spam.example/"},
        )
        self.assertEqual(status, 403)

    async def test_keyword_lists_and_json_rule_packs_both_apply(self):
        """Les deux mecanismes (RulePack JSON classique + keyword_lists)
        cohabitent et sont tous les deux evalues pour la meme requete."""
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 5},
            "rules": {
                "paths": ["secure/waf/rules/body-sqli.json"],
                "keyword_lists": [
                    {"id": "REFERER-SPAM", "scope": ["referer"], "file": "secure/waf/rules/keywords/referer-spam.txt", "weight": 5},
                ],
            },
        })
        sqli_status, _, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(sqli_status, 403)
        referer_status, _, _ = await self._request(
            "GET", "/index.html", headers={"Referer": "https://evil-viagra-spam.example/"},
        )
        self.assertEqual(referer_status, 403)
        clean_status, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(clean_status, 200)


@unittest.skipUnless(_MAGNET_AVAILABLE, "extra optionnel 'magnet' (lupa) non installe")
class TestWafMagnet(_WafServerTestCase):
    async def test_clean_request_passes(self):
        await self._start({
            "mode": "block",
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            "magnet": {"enabled": True, "script": "secure/waf/scripts/block-magic.lua"},
        })
        status, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)

    async def test_magnet_blocks_what_native_alone_would_miss(self):
        """Le mot 'magic-word' n'est connu d'AUCUN pack JSON natif - seul
        le script magnet le detecte, preuve qu'il s'agit bien d'un
        renfort complementaire, pas d'une simple redite du natif."""
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 5},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            "magnet": {"enabled": True, "script": "secure/waf/scripts/block-magic.lua"},
        })
        status, _, _ = await self._request("GET", "/index.html?q=magic-word")
        self.assertEqual(status, 403)

    async def test_native_and_magnet_both_applied(self):
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 5},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            "magnet": {"enabled": True, "script": "secure/waf/scripts/block-magic.lua"},
        })
        sqli_status, _, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(sqli_status, 403)
        magnet_status, _, _ = await self._request("GET", "/index.html?q=magic-word")
        self.assertEqual(magnet_status, 403)
        clean_status, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(clean_status, 200)

    async def test_magnet_never_lifts_a_native_block(self):
        """Etude §5.5 point 2 : le magnet est strictement additif,
        jamais soustractif - meme si son propre script dirait 'allow'
        sur cette requete (ce que fait block-magic.lua pour tout ce qui
        ne contient pas 'magic-word'), un blocage natif reste un
        blocage."""
        await self._start({
            "mode": "block",
            "scoring": {"block_threshold": 5},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            "magnet": {"enabled": True, "script": "secure/waf/scripts/block-magic.lua"},
        })
        status, _, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(status, 403)

    async def test_slow_magnet_script_never_blocks_unrelated_requests(self):
        """Lot E, decision D2 - preuve directe de non-blocage de la
        boucle asyncio, SANS confondre avec la parallelisme CPU du
        script Lua lui-meme (lupa ne libere pas necessairement le GIL
        pendant l'execution - deux scripts magnet concurrents peuvent
        donc se disputer le GIL entre eux, ce que D2 n'a jamais promis).
        Ce que D2 garantit reellement : UNE requete qui ne touche PAS le
        magnet (/healthz, exclu du WAF par defaut) reste rapide MEME SI
        une autre requete occupe un thread du pool magnet pendant ~300ms
        (slow.lua) - la boucle d'evenements elle-meme n'est jamais
        bloquee en attendant ce thread."""
        await self._start({
            "mode": "block",
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            "magnet": {"enabled": True, "script": "secure/waf/scripts/slow.lua", "timeout_ms": 5000},
        })

        async def _timed_request(path: str) -> tuple[int, float]:
            start = time.monotonic()
            status, _, _ = await self._request("GET", path)
            return status, time.monotonic() - start

        (slow_status, slow_duration), (fast_status, fast_duration) = await asyncio.gather(
            _timed_request("/index.html"),
            _timed_request("/healthz"),
        )
        self.assertEqual(slow_status, 200)
        self.assertEqual(fast_status, 200)
        self.assertGreaterEqual(slow_duration, 0.25)  # confirme que slow.lua a bien tourne pour de vrai
        self.assertLess(fast_duration, 0.15)  # jamais mise en attente derriere le thread magnet


class TestWafBlocklist(_WafServerTestCase):
    async def test_blocklisted_ip_gets_403(self):
        blocklist_path = self.root / "secure" / "waf" / "blocklist.json"
        blocklist_path.write_text(json.dumps({
            "version": 1,
            "entries": [{"network": "127.0.0.1/32", "reason": "test", "created_at": "2026-09-05T00:00:00+00:00", "source": "manual"}],
        }))
        await self._start({"rules": {"paths": ["secure/waf/rules/body-sqli.json"]}})
        status, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(status, 403)


class TestWafRateLimit(_WafServerTestCase):
    async def test_rate_limit_blocks_after_quota_exceeded(self):
        await self._start({
            "rate_limit": {"enabled": True, "global": {"requests": 1, "window_seconds": 60}},
            "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
        })
        status1, _, _ = await self._request("GET", "/index.html")
        self.assertEqual(status1, 200)
        status2, headers2, _ = await self._request("GET", "/index.html")
        self.assertEqual(status2, 429)
        self.assertIn("Retry-After", headers2)


if __name__ == "__main__":
    unittest.main()

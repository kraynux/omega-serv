"""plan_active_defense_omega_serv.md, Phase 1 - premier cablage reel
dans le pipeline HTTP (infrastructure/server/asyncio_server.py::
_observe_active_defense_threat) : serveur reel, connexions TCP reelles
sur 127.0.0.1, aucun mock - meme discipline que test_waf_server.py.
`ObserveThreatCommand` n'est jamais invoque directement ici (deja
couvert par test_observe_threat.py) - seul le CABLAGE est verifie :
la bonne decision WAF atteint-elle bien la bonne source_id, au bon
moment (jamais pour une requete "allow")."""
import asyncio
import http.client
import json
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.active_defense.entities import IncidentFilters
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_incident_repository import (
    SqliteIncidentRepository,
)
from omega_serv.infrastructure.persistence.sqlite_threat_state_repository import (
    SqliteThreatStateRepository,
)

_SQLI_PACK = {
    "version": 1,
    "pack": "body-sqli",
    "enabled": True,
    "rules": [
        {"id": "SQLI-001", "description": "Union select", "scope": ["query"], "pattern": r"union\s+select", "weight": 10},
    ],
}


class _ActiveDefenseServerTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("hello world")

        rules_dir = self.root / "secure" / "waf" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "body-sqli.json").write_text(json.dumps(_SQLI_PACK))

        self.filesystem = LocalFilesystem()
        self.logger = FileLineLogger()

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    async def _start(self, *, active_defense_settings: dict | None, waf_mode: str = "block"):
        options = {
            "waf": {
                "enabled": True, "mode": waf_mode, "scoring": {"block_threshold": 5},
                "rules": {"paths": ["secure/waf/rules/body-sqli.json"]},
            },
        }
        if active_defense_settings is not None:
            options["active_defense"] = {"enabled": True, **active_defense_settings}
        self.config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 0}, "options": options,
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
            return resp.status, data
        finally:
            conn.close()

    async def _request(self, method, path, headers=None):
        return await asyncio.to_thread(self._request_sync, method, path, headers)

    def _load_threat_states(self, database_relative_path: str):
        connection = open_active_defense_connection(self.root / database_relative_path)
        try:
            return SqliteThreatStateRepository(connection).list_all()
        finally:
            connection.close()

    def _load_incidents(self, database_relative_path: str):
        connection = open_active_defense_connection(self.root / database_relative_path)
        try:
            return SqliteIncidentRepository(connection).list_recent(IncidentFilters())
        finally:
            connection.close()


class TestActiveDefenseObservationWiring(_ActiveDefenseServerTestCase):
    async def test_no_database_file_created_when_option_disabled(self):
        await self._start(active_defense_settings=None)
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertFalse((self.root / "var" / "lib" / "active-defense.sqlite3").exists())

    async def test_no_observation_when_war_mode_disabled(self):
        await self._start(active_defense_settings={"war_mode": {"enabled": False}})
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(self._load_threat_states("var/lib/active-defense.sqlite3"), [])

    async def test_clean_request_creates_no_observation(self):
        await self._start(active_defense_settings={"war_mode": {"enabled": True}})
        status, _ = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(self._load_threat_states("var/lib/active-defense.sqlite3"), [])

    async def test_blocked_request_is_observed_with_a_real_score(self):
        await self._start(active_defense_settings={"war_mode": {"enabled": True}})
        status, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(status, 403)
        states = self._load_threat_states("var/lib/active-defense.sqlite3")
        self.assertEqual(len(states), 1)
        self.assertGreater(states[0].score, 0)

    async def test_log_only_waf_mode_still_observes_without_blocking(self):
        await self._start(active_defense_settings={"war_mode": {"enabled": True}}, waf_mode="log-only")
        status, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(status, 200)
        states = self._load_threat_states("var/lib/active-defense.sqlite3")
        self.assertEqual(len(states), 1)

    async def test_repeated_requests_from_the_same_subject_accumulate_score(self):
        await self._start(active_defense_settings={"war_mode": {"enabled": True}}, waf_mode="log-only")
        for _ in range(3):
            await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        states = self._load_threat_states("var/lib/active-defense.sqlite3")
        self.assertEqual(len(states), 1)  # meme IP + meme User-Agent -> meme subject_id
        self.assertGreater(states[0].score, 10)  # plus qu'une seule observation


class TestActiveDefenseIncidentWiring(_ActiveDefenseServerTestCase):
    """plan_active_defense_omega_serv.md, Phase 2 - un incident reel doit
    apparaitre une fois le score cumule au-dessus de incident_score,
    construit uniquement a partir d'evenements HTTP reels (jamais
    `create_or_update_incident` invoque directement ici, deja couvert
    par test_manage_incidents.py)."""

    async def test_no_incident_below_the_incident_score_threshold(self):
        await self._start(active_defense_settings={
            "war_mode": {"enabled": True, "thresholds": {"incident_score": 100}},
        })
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(self._load_incidents("var/lib/active-defense.sqlite3"), [])

    async def test_incident_opens_once_the_threshold_is_crossed(self):
        await self._start(active_defense_settings={
            "war_mode": {"enabled": True, "thresholds": {"incident_score": 10}},
        }, waf_mode="log-only")
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        incidents = self._load_incidents("var/lib/active-defense.sqlite3")
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].status, "open")
        self.assertEqual(len(incidents[0].observations), 1)
        self.assertEqual(len(incidents[0].events), 1)

    async def test_repeated_requests_merge_into_the_same_open_incident(self):
        await self._start(active_defense_settings={
            "war_mode": {"enabled": True, "thresholds": {"incident_score": 10}},
        }, waf_mode="log-only")
        for _ in range(3):
            await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        incidents = self._load_incidents("var/lib/active-defense.sqlite3")
        self.assertEqual(len(incidents), 1)  # jamais un second incident pour la meme source
        self.assertEqual(len(incidents[0].observations), 3)


class TestActiveDefenseDeceptionWiring(_ActiveDefenseServerTestCase):
    """plan_active_defense_omega_serv.md, Phase 3 - critere de sortie :
    une IP de test, declenchee par une observation synthetique, recoit
    la fixture `fake_admin` ; un client normal continue de voir la
    production. Seuil `hostile_score=10` choisi pour que la premiere
    requete SQLi (score_delta=10, WAF_FINDING_SCORE_DELTA) declenche deja
    le niveau "hostile" en un seul coup - jamais besoin d'un
    ObserveThreatCommand invoque directement ici (deja couvert par
    test_manage_deception.py), seul le CABLAGE HTTP est verifie."""

    _THRESHOLDS: ClassVar[dict[str, int]] = {"suspicious_score": 1, "hostile_score": 10, "incident_score": 1000}

    async def test_hostile_source_is_assigned_then_receives_the_decoy_on_any_path(self):
        await self._start(active_defense_settings={
            "mode": "enforce",
            "war_mode": {"enabled": True, "thresholds": self._THRESHOLDS},
            "deception": {
                "enabled": True, "fallback": "pass_through",
                "profiles": {"fake_admin": {"enabled": True, "match_attack_classes": ["sqli"]}},
            },
        })
        first_status, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(first_status, 403)  # decision WAF normale, pas encore de leurre pour CETTE requete

        status, body = await self._request("GET", "/dashboard")
        self.assertEqual(status, 200)
        self.assertIn(b"Connexion administrateur", body)

    async def test_monitor_mode_resolves_but_never_intercepts(self):
        await self._start(active_defense_settings={
            "mode": "monitor",
            "war_mode": {"enabled": True, "thresholds": self._THRESHOLDS},
            "deception": {
                "enabled": True, "fallback": "pass_through",
                "profiles": {"fake_admin": {"enabled": True, "match_attack_classes": ["sqli"]}},
            },
        })
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        status, body = await self._request("GET", "/dashboard")
        self.assertEqual(status, 404)  # production normale, jamais le leurre en mode monitor
        self.assertNotIn(b"Connexion administrateur", body)

    async def test_normal_client_never_gets_assigned(self):
        await self._start(active_defense_settings={
            "mode": "enforce",
            "war_mode": {"enabled": True, "thresholds": self._THRESHOLDS},
            "deception": {
                "enabled": True, "fallback": "pass_through",
                "profiles": {"fake_admin": {"enabled": True, "match_attack_classes": ["sqli"]}},
            },
        })
        status, body = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)
        self.assertIn(b"hello world", body)

    async def test_fallback_reject_when_dispatcher_has_no_matching_fixture(self):
        await self._start(active_defense_settings={
            "mode": "enforce",
            "war_mode": {"enabled": True, "thresholds": self._THRESHOLDS},
            "deception": {
                "enabled": True, "fallback": "reject",
                "profiles": {"mystery_profile": {"enabled": True, "match_attack_classes": ["sqli"]}},
            },
        })
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        status, _ = await self._request("GET", "/dashboard")
        self.assertEqual(status, 403)

    async def test_fallback_pass_through_when_dispatcher_has_no_matching_fixture(self):
        await self._start(active_defense_settings={
            "mode": "enforce",
            "war_mode": {"enabled": True, "thresholds": self._THRESHOLDS},
            "deception": {
                "enabled": True, "fallback": "pass_through",
                "profiles": {"mystery_profile": {"enabled": True, "match_attack_classes": ["sqli"]}},
            },
        })
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        status, _ = await self._request("GET", "/dashboard")
        self.assertEqual(status, 404)  # jamais de leurre disponible -> comportement normal


class TestActiveDefenseWarModeActionsWiring(_ActiveDefenseServerTestCase):
    """plan_active_defense_omega_serv.md, Phase 4 ("mode guerre") -
    critere de sortie : chaque action du DefensePlaybook est reellement
    declenchee (ou non) selon war_mode.actions et le niveau de la
    source, verifie via de vraies connexions TCP (jamais
    _apply_active_defense_war_mode_actions/_observe_active_defense_threat
    invoques directement)."""

    _MARKED_THRESHOLDS: ClassVar[dict[str, int]] = {
        "suspicious_score": 1, "hostile_score": 1000, "incident_score": 1000,
    }

    async def test_enrich_log_writes_a_redacted_line_for_a_marked_source(self):
        await self._start(active_defense_settings={
            "war_mode": {
                "enabled": True, "thresholds": self._MARKED_THRESHOLDS,
                "actions": ["enrich_log"],
            },
            "logging": {"capture_request_body": False},
        }, waf_mode="log-only")
        await self._request(
            "GET", "/index.html?q=1%20union%20select%20pwd%20from%20users",
            headers={"Authorization": "Bearer secret-token"},
        )
        log_path = self.root / "var" / "log" / "active-defense-enriched.jsonl"
        self.assertTrue(log_path.exists())
        lines = log_path.read_text().strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["level"], "suspicious")
        self.assertEqual(record["headers"]["authorization"], "***REDACTED***")

    async def test_no_enrich_log_when_action_absent_from_playbook(self):
        await self._start(active_defense_settings={
            "war_mode": {"enabled": True, "thresholds": self._MARKED_THRESHOLDS, "actions": ["create_incident"]},
        }, waf_mode="log-only")
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        log_path = self.root / "var" / "log" / "active-defense-enriched.jsonl"
        self.assertFalse(log_path.exists())

    async def test_delay_action_actually_slows_down_a_marked_source(self):
        await self._start(active_defense_settings={
            "war_mode": {
                "enabled": True, "thresholds": self._MARKED_THRESHOLDS, "actions": ["delay"],
                "slowdown": {"enabled": True, "minimum_ms": 300, "maximum_ms": 350, "jitter_ms": 50},
            },
        }, waf_mode="log-only")
        loop = asyncio.get_running_loop()
        start = loop.time()
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        elapsed_ms = (loop.time() - start) * 1000
        self.assertGreaterEqual(elapsed_ms, 300)

    async def test_no_delay_for_a_clean_request(self):
        await self._start(active_defense_settings={
            "war_mode": {
                "enabled": True, "thresholds": self._MARKED_THRESHOLDS, "actions": ["delay"],
                "slowdown": {"enabled": True, "minimum_ms": 300, "maximum_ms": 350, "jitter_ms": 50},
            },
        })
        loop = asyncio.get_running_loop()
        start = loop.time()
        status, _ = await self._request("GET", "/index.html")
        elapsed_ms = (loop.time() - start) * 1000
        self.assertEqual(status, 200)
        self.assertLess(elapsed_ms, 300)

    async def test_rate_limit_action_rejects_once_the_quota_is_exhausted(self):
        await self._start(active_defense_settings={
            "war_mode": {
                "enabled": True, "thresholds": self._MARKED_THRESHOLDS, "actions": ["rate_limit"],
                "rate_limit": {"requests": 1, "window_seconds": 60},
            },
        }, waf_mode="log-only")
        first_status, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        second_status, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertNotEqual(first_status, 429)
        self.assertEqual(second_status, 429)

    async def test_no_create_incident_when_action_absent_from_playbook(self):
        await self._start(active_defense_settings={
            "war_mode": {
                "enabled": True, "thresholds": {"incident_score": 1}, "actions": ["delay"],
            },
        }, waf_mode="log-only")
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(self._load_incidents("var/lib/active-defense.sqlite3"), [])


async def _fake_decoy_backend(raw_response: bytes) -> asyncio.AbstractServer:
    """Meme patron exact que test_reverse_proxy_server.py::_fake_upstream -
    un vrai socket TCP, tenant lieu de backend Niveau 2 REELLEMENT isole
    (plan §"Routage vers les leurres")."""
    async def handle(reader, writer):
        await reader.read(4096)
        writer.write(raw_response)
        await writer.drain()
        writer.close()

    return await asyncio.start_server(handle, "127.0.0.1", 0)


class TestActiveDefenseNiveau2ProxyWiring(_ActiveDefenseServerTestCase):
    """plan_active_defense_omega_serv.md, Phase 5 ("Niveau 2") - critere
    de sortie : un backend leurre reellement isole (process separe,
    ici un vrai socket TCP distinct du process de test) recoit le
    trafic derive via serve_proxy() - meme mecanisme deja livre/teste
    pour le reverse proxy sortant de production, jamais un second
    protocole de relai."""

    _THRESHOLDS: ClassVar[dict[str, int]] = {"suspicious_score": 1, "hostile_score": 10, "incident_score": 1000}

    async def asyncTearDown(self):
        if getattr(self, "_decoy_backend", None) is not None:
            self._decoy_backend.close()
            await self._decoy_backend.wait_closed()
        await super().asyncTearDown()

    async def _start_with_decoy_zone(self, *, fallback: str = "pass_through") -> None:
        self._decoy_backend = await _fake_decoy_backend(
            b"HTTP/1.1 200 OK\r\nContent-Length: 12\r\n\r\nDECOY REPLY\n"
        )
        decoy_port = self._decoy_backend.sockets[0].getsockname()[1]
        await self._start(active_defense_settings={
            "mode": "enforce",
            "war_mode": {"enabled": True, "thresholds": self._THRESHOLDS},
            "deception": {
                "enabled": True, "fallback": fallback,
                "profiles": {
                    "fake_admin": {
                        "enabled": True, "match_attack_classes": ["sqli"],
                        "isolation_level": "proxy", "reverse_proxy_zone_name": "decoy-1",
                    },
                },
                "decoy_zones": {"decoy-1": {"upstreams": [{"host": "127.0.0.1", "port": decoy_port}]}},
            },
        })

    async def test_hostile_source_is_relayed_to_the_real_isolated_backend(self):
        await self._start_with_decoy_zone()
        first_status, _ = await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        self.assertEqual(first_status, 403)  # decision WAF normale, affectation pas encore appliquee a CETTE requete

        status, body = await self._request("GET", "/dashboard")
        self.assertEqual(status, 200)
        self.assertIn(b"DECOY REPLY", body)

    async def test_normal_client_is_never_relayed_to_the_decoy_backend(self):
        await self._start_with_decoy_zone()
        status, body = await self._request("GET", "/index.html")
        self.assertEqual(status, 200)
        self.assertIn(b"hello world", body)

    async def test_missing_decoy_zone_falls_back_to_reject(self):
        await self._start(active_defense_settings={
            "mode": "enforce",
            "war_mode": {"enabled": True, "thresholds": self._THRESHOLDS},
            "deception": {
                "enabled": True, "fallback": "reject",
                "profiles": {
                    "fake_admin": {
                        "enabled": True, "match_attack_classes": ["sqli"],
                        "isolation_level": "proxy", "reverse_proxy_zone_name": "does-not-exist",
                    },
                },
            },
        })
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        status, _ = await self._request("GET", "/dashboard")
        self.assertEqual(status, 403)

    async def test_missing_decoy_zone_falls_back_to_pass_through(self):
        await self._start(active_defense_settings={
            "mode": "enforce",
            "war_mode": {"enabled": True, "thresholds": self._THRESHOLDS},
            "deception": {
                "enabled": True, "fallback": "pass_through",
                "profiles": {
                    "fake_admin": {
                        "enabled": True, "match_attack_classes": ["sqli"],
                        "isolation_level": "proxy", "reverse_proxy_zone_name": "does-not-exist",
                    },
                },
            },
        })
        await self._request("GET", "/index.html?q=1%20union%20select%20pwd%20from%20users")
        status, _ = await self._request("GET", "/dashboard")
        self.assertEqual(status, 404)  # comportement normal, jamais de leurre disponible


if __name__ == "__main__":
    unittest.main()

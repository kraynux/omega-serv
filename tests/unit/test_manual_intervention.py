"""INTERVENTION MANUELLE (Active Securite, decisions utilisateur 2026-11-06) : ban sans condition d'une seule adresse
IP dans la blocklist du WAF, leve seulement par ce menu, statut de tous les bans avec leur origine, export TXT au
format d'import d'omega-fire (une adresse par ligne, lignes « # » ignorees)."""
from __future__ import annotations

import ipaddress
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.security.manual_intervention import (
    ban_address,
    ban_rows_for_display,
    check_ban_request,
    collect_ban_rows,
    manual_bans,
    unban_address,
)
from omega_serv.domain.security.waf.blocklist import (
    is_stronger_entry,
    parse_blocklist,
    serialize_blocklist,
)
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.domain.security.waf.manual_intervention import (
    ORIGIN_INTERVENTION,
    ORIGIN_MAGNET,
    ORIGIN_MANUAL,
    ORIGIN_OMEGA_JAIL,
    ORIGIN_RIPOSTE,
    ORIGIN_WAF_LIST,
    ORIGIN_WAF_RULES,
    ban_rows_payload,
    build_ban_rows,
    check_single_address,
    classify_origin,
    parse_magnet_blocklist,
    render_injection_txt,
)
from omega_serv.domain.security.waf.reputation import DEFAULT_NEVER_AUTO_BLOCK
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.waf.blocklist_store import JsonBlocklistStore

NOW = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)


def _entry(network: str, reason: str = "x", source: str = "manual", origin: str | None = None,
           expires: timedelta | None = timedelta(hours=1)) -> BlocklistEntry:
    return BlocklistEntry(network=network, reason=reason, created_at=(NOW - timedelta(minutes=5)).isoformat(),
                          expires_at=None if expires is None else (NOW + expires).isoformat(),
                          source=source, origin=origin)  # type: ignore[arg-type]


def _omega_fire_import(text: str) -> set[str]:
    """Meme lecture que omega-fire (ban_ip_list_screen.py) : lignes « # » ignorees, adresses valides extraites."""
    found: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            found.add(str(ipaddress.ip_address(line)))
    return found


class TestSingleAddress(unittest.TestCase):
    def test_ipv4_and_ipv6_accepted(self):
        self.assertEqual(check_single_address(" 203.0.113.7 ").network, "203.0.113.7/32")
        self.assertEqual(check_single_address("2001:db8::7").network, "2001:db8::7/128")

    def test_any_network_notation_refused(self):
        for text in ("203.0.113.0/24", "203.0.113.7/32", "2001:db8::/64"):
            with self.subTest(text=text):
                self.assertEqual(check_single_address(text).error, "network")

    def test_empty_and_invalid(self):
        self.assertEqual(check_single_address("  ").error, "empty")
        self.assertEqual(check_single_address("pas-une-ip").error, "invalid")


class TestOrigin(unittest.TestCase):
    def test_every_origin_recognised(self):
        cases = (
            (_entry("1.1.1.1/32", origin="intervention"), (ORIGIN_INTERVENTION, "")),
            (_entry("1.1.1.2/32", "riposte:a1b2 scan-recidive #2", "riposte"), (ORIGIN_RIPOSTE, "scan-recidive")),
            (_entry("1.1.1.3/32", "récidive sensitive-paths-hostile : 2 détections", "auto"),
             (ORIGIN_WAF_LIST, "sensitive-paths-hostile")),
            (_entry("1.1.1.4/32", "14 detections suspectes dans la fenetre (seuil 3)", "auto"), (ORIGIN_WAF_RULES, "")),
            (_entry("1.1.1.5/32", "omega-jail:omega-serv-active-defense"), (ORIGIN_OMEGA_JAIL, "omega-serv-active-defense")),
            (_entry("1.1.1.6/32", "hebergeur abusif"), (ORIGIN_MANUAL, "")),
        )
        for entry, expected in cases:
            with self.subTest(reason=entry.reason):
                self.assertEqual(classify_origin(entry), expected)

    def test_magnet_list(self):
        text = "# 2026-11-02 13:02:30 - SENSITIVE-PATH:^/%.env/?$ (recidive x3)\n187.15.106.89\npas-une-ip\n"
        self.assertEqual(parse_magnet_blocklist(text),
                         [("187.15.106.89/32", "2026-11-02 13:02:30", "SENSITIVE-PATH:^/%.env/?$ (recidive x3)")])

    def test_rows_grouped_by_origin_then_newest_first(self):
        rows = build_ban_rows(
            [_entry("1.1.1.4/32", "seuil", "auto"), _entry("1.1.1.1/32", origin="intervention")],
            [("5.5.5.5/32", "", "")], NOW)
        self.assertEqual([r.origin for r in rows], [ORIGIN_INTERVENTION, ORIGIN_WAF_RULES, ORIGIN_MAGNET])
        self.assertEqual([r.removable for r in rows], [True, False, False])


class TestInjectionTxt(unittest.TestCase):
    def setUp(self):
        self.rows = build_ban_rows([
            _entry("198.51.100.23/32", origin="intervention"),
            _entry("2001:db8::7/128", "seuil", "auto"),
            _entry("187.13.23.119/32", "seuil", "auto", expires=timedelta(hours=-1)),
            _entry("203.0.113.0/24", "hebergeur", expires=None),
        ], [], NOW)

    def test_active_scope_is_importable_by_omega_fire(self):
        text = render_injection_txt(self.rows, "active", NOW)
        self.assertEqual(_omega_fire_import(text), {"198.51.100.23", "2001:db8::7"})

    def test_all_scope_includes_expired(self):
        self.assertIn("187.13.23.119", _omega_fire_import(render_injection_txt(self.rows, "all", NOW)))

    def test_network_only_as_comment_and_header_commented(self):
        lines = render_injection_txt(self.rows, "active", NOW).splitlines()
        self.assertTrue(lines[0].startswith("# omega-serv - active bans - exported 2026-11-06 09:00 UTC"))
        self.assertIn("# network not exported (addresses only): 203.0.113.0/24", lines)
        self.assertNotIn("203.0.113.0", _omega_fire_import("\n".join(lines)))

    def test_json_payload_keeps_stable_codes(self):
        payload = ban_rows_payload(self.rows, NOW)
        self.assertEqual(payload["bans"][0]["origin"], "intervention")
        self.assertEqual(len(payload["bans"]), 4)
        json.dumps(payload)


class TestBlocklistFormat(unittest.TestCase):
    def test_origin_written_only_when_present(self):
        data = serialize_blocklist([_entry("1.1.1.1/32"), _entry("1.1.1.2/32", origin="intervention")])
        self.assertNotIn("origin", data["entries"][0])
        self.assertEqual(data["entries"][1]["origin"], "intervention")
        self.assertEqual([e.origin for e in parse_blocklist(data)], [None, "intervention"])

    def test_auto_ban_never_replaces_a_manual_intervention(self):
        self.assertTrue(is_stronger_entry(_entry("1.1.1.1/32", origin="intervention"),
                                          _entry("1.1.1.1/32", "seuil", "auto", expires=timedelta(days=9)), NOW))


class _Clock:
    def now(self) -> datetime:
        return NOW


class TestUseCases(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.port = JsonBlocklistStore(LocalFilesystem(), self.root / "blocklist.json", _Clock())

    def tearDown(self):
        self._tmp.cleanup()

    def test_ban_writes_a_manual_entry_marked_intervention(self):
        result = ban_address(self.port, "203.0.113.7/32", "", 3600, NOW)
        self.assertTrue(result.success, result.message)
        (entry,) = self.port.list_entries()
        self.assertEqual((entry.source, entry.origin), ("manual", "intervention"))
        self.assertTrue(entry.reason)
        self.assertEqual(entry.expires_at, (NOW + timedelta(hours=1)).isoformat())
        self.assertIsNotNone(self.port.is_blocked("203.0.113.7"))

    def test_permanent_ban(self):
        ban_address(self.port, "203.0.113.7/32", "test", None, NOW)
        self.assertIsNone(self.port.list_entries()[0].expires_at)

    def test_unban_only_lifts_manual_interventions(self):
        self.port.add_entry(_entry("198.51.100.1/32", "omega-jail:x"))
        ban_address(self.port, "203.0.113.7/32", "test", 3600, NOW)
        self.assertEqual([e.network for e in manual_bans(self.port)], ["203.0.113.7/32"])
        refused = unban_address(self.port, "198.51.100.1/32")
        self.assertFalse(refused.success)
        self.assertEqual(len(self.port.list_entries()), 2)
        self.assertTrue(unban_address(self.port, "203.0.113.7/32").success)
        self.assertEqual([e.network for e in self.port.list_entries()], ["198.51.100.1/32"])

    def test_check_refuses_networks_and_warns(self):
        self.assertIn("WAF", check_ban_request(self.port, "203.0.113.0/24", False, DEFAULT_NEVER_AUTO_BLOCK, NOW).error)
        self.port.add_entry(_entry("203.0.113.7/32", "riposte:a1 p", "riposte"))
        check = check_ban_request(self.port, "203.0.113.7", True, DEFAULT_NEVER_AUTO_BLOCK, NOW)
        self.assertEqual(check.network, "203.0.113.7/32")
        self.assertEqual(len(check.warnings), 2)  # ban RIPOSTE remplace + permanent
        local = check_ban_request(self.port, "192.168.1.20", False, DEFAULT_NEVER_AUTO_BLOCK, NOW)
        self.assertEqual(len(local.warnings), 1)
        self.assertEqual(check_ban_request(self.port, "8.8.8.8", False, DEFAULT_NEVER_AUTO_BLOCK, NOW).warnings, ())

    def test_collect_reads_magnet_list_and_display_rows(self):
        magnet = self.root / "magnet-blocklist.txt"
        magnet.write_text("# 2026-11-02 13:02:30 - motif\n187.15.106.89\n", encoding="utf-8")
        ban_address(self.port, "203.0.113.7/32", "test", 3600, NOW)
        rows, warning = collect_ban_rows(self.port, LocalFilesystem(), magnet, NOW)
        self.assertEqual(warning, "")
        self.assertEqual([r.origin for r in rows], ["intervention", "magnet"])
        shown = ban_rows_for_display(rows)
        self.assertEqual(shown[0]["network"], "203.0.113.7")
        rows, _warning = collect_ban_rows(self.port, LocalFilesystem(), None, NOW)
        self.assertEqual(len(rows), 1)


class TestHtmlExport(unittest.TestCase):
    def test_every_row_and_origin_rendered(self):
        from omega_serv.infrastructure.exporters.html_exporter import export_bans_html

        rows = build_ban_rows([_entry("198.51.100.23/32", "scan <b>", origin="intervention"),
                               _entry("203.0.113.0/24", "hebergeur", expires=None)], [], NOW)
        html = export_bans_html(ban_rows_for_display(rows), 2)
        self.assertEqual(html.count("<tr>"), 3)
        self.assertIn("198.51.100.23", html)
        self.assertIn("203.0.113.0/24", html)
        self.assertIn("scan &lt;b&gt;", html)  # motif echappe


if __name__ == "__main__":
    unittest.main()

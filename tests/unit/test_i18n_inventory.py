"""Inventaire i18n tenu a jour (OMEGA-SERV_PLAN-DETAILLE_I18N.md §4.6, lot 1).

Echoue des qu'un texte de l'interface n'est pas classe (TRADUIRE / NE-PAS-TRADUIRE), qu'un
contrat machine ou un message du processus serveur (D18/D18b) partirait en traduction, ou que
le fichier de decisions de l'utilisateur devient incoherent. L'outil (tools/) et les decisions
(~/DEV/SERV/I18N_DECISIONS.md) ne sont jamais livres dans l'archive : test saute hors du depot
de developpement, comme test_omega_waf_lua_never_auto_block.py.

Ne modifie AUCUN fichier de l'utilisateur : releve en memoire, sorties dans un dossier temporaire.
"""
from __future__ import annotations

import csv
import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

_PROJECT = Path(__file__).resolve().parents[2]
_TOOL = _PROJECT / "tools" / "i18n_inventory.py"
_DECISIONS = _PROJECT.parent / "I18N_DECISIONS.md"
_LINE_DECISIONS = _PROJECT.parent / "i18n_inventaire.csv"


def _load_tool():
    spec = importlib.util.spec_from_file_location("i18n_inventory", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["i18n_inventory"] = module  # dataclass a besoin du module enregistre
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(_TOOL.exists() and _DECISIONS.exists(),
                     f"inventaire i18n absent (outil {_TOOL} ou decisions {_DECISIONS})")
class TestInventoryUpToDate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = _load_tool()
        entries, _skipped, missing = cls.tool.scan()
        cls.rules = cls.tool.load_rule_decisions(_DECISIONS)
        cls.lines = cls.tool.load_line_decisions(_LINE_DECISIONS)
        cls.tool.apply_decisions(entries, cls.rules, cls.lines)
        cls.entries = entries
        cls.missing = missing

    def _listing(self, entries, limit=25):
        shown = [f"  {e.source}/{e.file}:{e.line} [{e.reason}] {e.text[:80]!r}" for e in entries[:limit]]
        more = f"\n  ... et {len(entries) - limit} autre(s)" if len(entries) > limit else ""
        return "\n".join(shown) + more

    def test_sources_found(self):
        self.assertEqual(self.missing, [])
        self.assertGreater(len(self.entries), 10_000)

    def test_every_text_is_classified(self):
        pending = [e for e in self.entries if e.category not in (self.tool.TRADUIRE, self.tool.NE_PAS)]
        self.assertEqual(pending, [], (
            "Texte(s) de l'interface non classe(s). Decider par regle dans I18N_DECISIONS.md ou par "
            "ligne dans i18n_inventaire.csv, puis relancer tools/i18n_inventory.py :\n"
            + self._listing(pending)))

    def test_every_translatable_text_is_marked(self):
        # Lot 4 : tout texte classe TRADUIRE passe par _() / N_() / P_() / ngettext(), sinon il
        # resterait en francais dans toutes les langues. Modeles .j2 : {{ _("...") }}.
        unmarked = [e for e in self.entries if e.category == self.tool.TRADUIRE
                    and not e.reason.startswith(("marque pour traduction", "texte d'aide citant"))
                    and e.zone != "exports-html"]
        self.assertEqual(unmarked, [], (
            "Texte a traduire non marque : l'envelopper dans _(\"...\") (ou P_ pour une page "
            "servie aux visiteurs), ou le reclasser dans l'inventaire :\n" + self._listing(unmarked)))

    def test_export_templates_marked(self):
        raw = [e for e in self.entries if e.zone == "exports-html" and e.category == self.tool.TRADUIRE]
        self.assertEqual(raw, [], "Texte en dur dans un modele d'export : utiliser {{ _(\"...\") }}\n"
                         + self._listing(raw))

    def test_machine_contracts_never_translated(self):
        # Seule exception : une aide (guide / widget) qui CITE le marqueur, a traduire en le gardant.
        leaked = [
            e for e in self.entries
            for marker, _why in self.tool.MACHINE_CONTRACTS
            if marker in e.text and e.category == self.tool.TRADUIRE and "garder TEL QUEL" not in e.reason
        ]
        self.assertEqual(leaked, [], "Contrat machine classe a traduire :\n" + self._listing(leaked))

    def test_server_process_messages_stay_french(self):
        # D18/D18b : ce qu'ecrit `omega-serv serve` (journalctl) n'est jamais traduit.
        server = [
            e for e in self.entries
            if (e.scope.split(".")[0] in self.tool.SERVER_PROCESS_SCOPES or e.file in self.tool.SERVER_PROCESS_FILES)
            and e.category == self.tool.TRADUIRE
            and e.reason.startswith(("message", "sortie CLI", "print"))
        ]
        self.assertEqual(server, [], "Message du processus serveur classe a traduire :\n" + self._listing(server))

    def test_sql_and_http_header_values_never_translated(self):
        # Lot 3 (2026-10-21) : la colonne `detail` d'un schema SQL classe "texte humain" a ete
        # accentuee -> base Active Defense cassee. Jamais plus : SQL et valeurs d'en-tete = machine.
        sql = re.compile(r"\b(CREATE\s+TABLE|SELECT\s.+\sFROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)",
                         re.IGNORECASE | re.DOTALL)
        leaked = [e for e in self.entries if e.category == self.tool.TRADUIRE
                  and (sql.search(e.text) or re.fullmatch(r"(no-cache|no-store|public|private|max-age=\d+)(,\s*\S+)*", e.text))]
        self.assertEqual(leaked, [], "SQL / valeur d'en-tete classe a traduire :\n" + self._listing(leaked))

    def test_log_lines_never_translated(self):
        logs = [e for e in self.entries if e.reason.startswith("ligne de journal") and e.category != self.tool.NE_PAS]
        self.assertEqual(logs, [], "Ligne de journal classee a traduire :\n" + self._listing(logs))

    def test_decisions_file_is_consistent(self):
        # Une decision dont la regle a disparu reste documentee dans I18N_DECISIONS.md (section
        # dediee) : sans danger, car un texte reste sans decision fait echouer
        # test_every_text_is_classified. Seules les valeurs inconnues sont refusees ici.
        for (_auto, reason), (decision, _note) in self.rules.items():
            self.assertIn(decision, ("", *self.tool.CATEGORIES), f"decision inconnue pour {reason!r} : {decision!r}")


@unittest.skipUnless(_TOOL.exists(), f"outil absent : {_TOOL}")
class TestInventoryOutputs(unittest.TestCase):
    """Regressions du 2026-10-21 : rendu Markdown casse, decisions perdues a la regeneration."""

    @classmethod
    def setUpClass(cls):
        cls.tool = _load_tool()

    def test_md_code_neutralizes_markdown(self):
        for text in ("le joker '*' n'est accepte que sous la forme '/*.extension'",
                     '<!DOCTYPE html> <html lang="fr"> <head>', "__init__ et _prive_", "[lien](x)"):
            cell = self.tool._md_code(text)
            self.assertTrue(cell.startswith("`") and cell.endswith("`"), cell)
            self.assertNotIn("\n", cell)

    def test_md_code_keeps_backticks_and_pipes(self):
        cell = self.tool._md_code("a `b` | c")
        self.assertTrue(cell.startswith("`` ") and cell.endswith(" ``"), cell)
        self.assertIn("`b`", cell)
        self.assertIn("\\|", cell)

    def test_rule_and_line_decisions_survive_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decisions = root / "dec.md"
            decisions.write_text(
                "| Décision | Raison | Nombre | Pré-classement d'origine | Note |\n|---|---|---:|---|---|\n"
                "| NE-PAS-TRADUIRE | regle test \\* etoile | 0 | `A-DECIDER` | ma note |\n", encoding="utf-8")
            rules = self.tool.load_rule_decisions(decisions)
            self.assertEqual(rules[("A-DECIDER", "regle test * etoile")], ("NE-PAS-TRADUIRE", "ma note"))

            entry = self.tool.Entry("omega-serv", "domaine", "x.py", 3, "", "", "A-DECIDER", "regle test * etoile", "Texte")
            other = self.tool.Entry("omega-serv", "domaine", "y.py", 4, "", "", "A-DECIDER", "autre", "Autre texte")
            csv_path = root / "inv.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["id", "decision_utilisateur", "note"])
                writer.writerow([other.ident, "TRADUIRE et verifier", ""])
            lines = self.tool.load_line_decisions(csv_path)
            self.tool.apply_decisions([entry, other], rules, lines)
            self.assertEqual((entry.category, other.category), ("NE-PAS-TRADUIRE", "TRADUIRE"))
            self.assertEqual(other.note, "et verifier")

            self.tool.write_rule_decisions([entry, other], rules, decisions)
            self.assertEqual(self.tool.load_rule_decisions(decisions)[("A-DECIDER", "regle test * etoile")][0],
                             "NE-PAS-TRADUIRE")
            self.tool.write_csv([entry, other], csv_path)
            self.assertEqual(self.tool.load_line_decisions(csv_path)[other.ident][0], "TRADUIRE")

    def test_old_decisions_layout_still_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            decisions = Path(tmp) / "dec.md"
            decisions.write_text(
                "| Catégorie automatique | Raison | Nombre | Décision | Note |\n|---|---|---:|---|---|\n"
                "| `A-DECIDER` | print hors CLI | 4 | TRADUIRE | |\n", encoding="utf-8")
            self.assertEqual(self.tool.load_rule_decisions(decisions)[("A-DECIDER", "print hors CLI")][0], "TRADUIRE")

    def test_generated_markdown_has_no_raw_html_outside_code(self):
        entry = self.tool.Entry("omega-serv", "domaine", "x.py", 1, "", "expression", "A-DECIDER",
                                "raison", '<html lang="fr"><head> a * b _c_')
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "inv.md"
            self.tool.apply_decisions([entry], {}, {})
            self.tool.write_md([entry], 0, [], md, "inv.csv", "dec.md")
            for line in md.read_text(encoding="utf-8").splitlines():
                if line.startswith("|") and "x.py" not in line:
                    outside = re.sub(r"(`+).*?(?<!`)\1(?!`)", "", line)
                    self.assertNotRegex(outside, r"(?<!\\)<[a-zA-Z!/]", line)


if __name__ == "__main__":
    unittest.main()

"""Exports HTML echappes (2026-11-06) : les modeles s'appellent `*.html.j2`, que select_autoescape(["html"]) ne
reconnaissait pas - rien n'etait echappe. Un « <nom-archive> » du guide disparaissait dans le navigateur (pris pour
une balise), et un texte venu de l'exterieur aurait pu injecter du HTML."""
from __future__ import annotations

import unittest
from dataclasses import asdict

from omega_serv.core.capability import Capability, CapabilityStatus
from omega_serv.infrastructure.exporters.html_exporter import (
    export_capabilities_html,
    export_guide_html,
    export_log_archives_html,
)
from omega_serv.interfaces.tui.guide.menu_tree import GUIDE_MENU_ENTRIES
from omega_serv.interfaces.tui.guide.registry import ALL_FAQ_ENTRIES, SCREEN_GUIDES


class TestHtmlExportEscaping(unittest.TestCase):
    def test_log_archives_escaped(self):
        html = export_log_archives_html([{"name": "<script>x</script>.tar.gz", "size_bytes": 1, "modified_at": "t"}])
        self.assertIn("&lt;script&gt;x&lt;/script&gt;.tar.gz", html)
        self.assertNotIn("<script>", html)
        self.assertIn("color: #", html)  # palette dans <style> intacte

    def test_capabilities_escaped(self):
        capability = Capability(id="cap", category="cat", status=next(iter(CapabilityStatus)), reason="<b>raison</b>")
        html = export_capabilities_html([capability])
        self.assertIn("&lt;b&gt;raison&lt;/b&gt;", html)

    def test_guide_placeholders_stay_visible(self):
        guides = [asdict(SCREEN_GUIDES[e.screen_class_name]) for e in GUIDE_MENU_ENTRIES
                  if e.screen_class_name in SCREEN_GUIDES]
        html = export_guide_html(guides, [asdict(f) for f in ALL_FAQ_ENTRIES])
        self.assertIn("&lt;nom-archive&gt;", html)
        self.assertNotIn("<nom-archive>", html)


if __name__ == "__main__":
    unittest.main()

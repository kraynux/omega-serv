"""Vérifie une instance de démonstration générée par demo_instance.py : ouvre les écrans de la TUI en mode test
Textual (aucun terminal, aucun serveur lancé) et résume ce qu'ils affichent.

Usage (depuis n'importe où) :
    HOME=<dest>/home PYTHONPATH=<dest>/omega-serv/src .venv/bin/python tools/captures/verify_demo.py <dest> [--svg DIR]

L'application est construite exactement comme `python -m omega_serv` (omega_serv.__main__.main) : seule la boucle
`app.run()` est remplacée par `app.run_test(size=(213, 51))`. Aucun bouton qui agit (sudo, pare-feu, service) n'est
pressé : les écrans sont ouverts, lus, puis refermés.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

SIZE = (213, 51)


def _describe(screen) -> list[str]:  # type: ignore[no-untyped-def]
    from textual.widgets import Button, DataTable, Static

    lines: list[str] = []
    for table in screen.query(DataTable):
        if not table.display:
            continue
        lines.append(f"  tableau #{table.id}: {table.row_count} ligne(s), colonnes "
                     f"{[str(c.label) for c in table.columns.values()][:8]}")
        for index in range(min(table.row_count, 3)):
            row = [str(cell)[:40] for cell in table.get_row_at(index)][:6]
            lines.append(f"      {row}")
    shown = 0
    for static in screen.query(Static):
        if isinstance(static, Button) or not static.display or static.id == "label":
            continue
        text = " ".join(str(static.render()).split())
        if text and shown < 30:
            shown += 1
            lines.append(f"  #{static.id or type(static).__name__}: {text[:400]}")
    buttons = [str(b.label) for b in screen.query(Button) if b.display and not b.disabled]
    lines.append(f"  boutons actifs : {', '.join(buttons)[:400]}")
    return lines


async def _scenario(app, svg_dir: Path | None) -> list[str]:  # type: ignore[no-untyped-def]
    from omega_serv.interfaces.tui.screens.active_defense_status_screen import (
        ActiveDefenseStatusScreen,
    )
    from omega_serv.interfaces.tui.screens.admin_accounts_screen import AdminAccountsScreen
    from omega_serv.interfaces.tui.screens.admin_alerts_screen import AdminAlertsScreen
    from omega_serv.interfaces.tui.screens.admin_master_screen import AdminMasterScreen
    from omega_serv.interfaces.tui.screens.admin_sessions_screen import AdminSessionsScreen
    from omega_serv.interfaces.tui.screens.admin_web_screen import AdminWebScreen
    from omega_serv.interfaces.tui.screens.backup_screen import BackupScreen
    from omega_serv.interfaces.tui.screens.ban_status_screen import BanStatusScreen
    from omega_serv.interfaces.tui.screens.certificate_expiry_screen import CertificateExpiryScreen
    from omega_serv.interfaces.tui.screens.full_report_screen import FullReportScreen
    from omega_serv.interfaces.tui.screens.home import HomeScreen
    from omega_serv.interfaces.tui.screens.incidents_screen import IncidentsScreen
    from omega_serv.interfaces.tui.screens.instances_screen import InstancesScreen
    from omega_serv.interfaces.tui.screens.resource_status_screen import ResourceStatusScreen
    from omega_serv.interfaces.tui.screens.riposte_actions_screen import RiposteActionsScreen
    from omega_serv.interfaces.tui.screens.riposte_recidives_screen import RiposteRecidivesScreen
    from omega_serv.interfaces.tui.screens.riposte_status_screen import RiposteStatusScreen
    from omega_serv.interfaces.tui.screens.terminal_warning import TerminalWarningScreen
    from omega_serv.interfaces.tui.screens.threats_screen import ThreatsScreen

    report: list[str] = []
    container = app._container
    async with app.run_test(size=SIZE) as pilot:
        for _attempt in range(40):
            await pilot.pause(0.1)
            if isinstance(app.screen, TerminalWarningScreen):
                await pilot.click("#continue")
            elif not isinstance(app.screen, HomeScreen):
                await pilot.press("escape")
            else:
                break
        report.append(f"== Accueil ({type(app.screen).__name__}) titre={app.title!r}")
        report += _describe(app.screen)
        if svg_dir is not None:
            app.save_screenshot(str(svg_dir / "00-accueil.svg"))
        screens = (
            ("01-multi-instance", InstancesScreen), ("02-configuration-distante", AdminWebScreen),
            ("03-comptes", AdminAccountsScreen), ("04-alertes", AdminAlertsScreen),
            ("05-sessions", AdminSessionsScreen), ("06-maitre", AdminMasterScreen),
            ("07-echeances-certificats", CertificateExpiryScreen), ("08-etat-ressources", ResourceStatusScreen),
            ("09-rapport-complet", FullReportScreen), ("10-sauvegarde", BackupScreen),
            # Écrans de sécurité (hors liste demandée, pour contrôler les bases générées)
            ("11-active-defense", ActiveDefenseStatusScreen), ("12-menaces", ThreatsScreen),
            ("13-incidents", IncidentsScreen), ("14-statut-des-bans", BanStatusScreen),
            ("15-riposte-etat", RiposteStatusScreen), ("16-riposte-actions", RiposteActionsScreen),
            ("17-riposte-recidives", RiposteRecidivesScreen),
        )
        for name, screen_class in screens:
            await app.push_screen(screen_class(container=container))
            for _ in range(30):  # laisse finir les tâches de fond (workers, minuteries)
                await pilot.pause(0.1)
            report.append(f"== {name} ({type(app.screen).__name__})")
            report += _describe(app.screen)
            if svg_dir is not None:
                app.save_screenshot(str(svg_dir / f"{name}.svg"))
            app.pop_screen()
            await pilot.pause(0.2)
        report.append(f"notifications : {[(n.severity, n.message[:160]) for n in app._notifications]}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dest")
    parser.add_argument("--svg", default=None, help="dossier où enregistrer une capture SVG de chaque écran")
    args = parser.parse_args()
    dest = Path(args.dest).resolve()
    if Path(os.environ.get("HOME", "")).resolve() != dest / "home":
        sys.exit("HOME doit valoir <dest>/home")
    import omega_serv.__main__ as entry
    from omega_serv.bootstrap.paths import PROJECT_ROOT

    if PROJECT_ROOT.resolve() != (dest / "omega-serv").resolve():
        sys.exit(f"Mauvaise copie importée : {PROJECT_ROOT}")
    svg_dir = Path(args.svg).resolve() if args.svg else None
    if svg_dir is not None:
        svg_dir.mkdir(parents=True, exist_ok=True)
    collected: list[str] = []

    def run_headless(app) -> None:  # type: ignore[no-untyped-def]
        collected.extend(asyncio.run(_scenario(app, svg_dir)))

    entry._run_with_text_direction = run_headless
    entry.main([])
    print("\n".join(collected))
    freeze_dump = Path(f"/tmp/omega-serv-freeze-{os.getpid()}.txt")
    freeze_dump.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Captures de la TUI pour la galerie du site (html/screenshots/), depuis une instance de démonstration.

    .venv/bin/python tools/captures/capture_tui.py <demo> <sortie> [nom ...] [--size 140x50] [--width 1400]
        [--lang fr|en|pt_BR|zh_CN|ar...]

<demo> : dossier produit par tools/captures/demo_instance.py (<demo>/omega-serv = copie de l'application,
<demo>/home = HOME factice). Chaque capture tourne dans son propre processus (HOME et PYTHONPATH de la copie, jamais
l'instance de développement) : l'application démarre en mode test Textual à une taille fixe, le scénario ouvre
l'écran, Textual écrit un SVG, rsvg-convert le transforme en PNG (police JetBrains Mono locale, sans cadre de
fenêtre, aucune police chargée depuis Internet). Liste des captures : OMEGA-SERV_CAPTURES_3.0.0.md."""
from __future__ import annotations

import asyncio
import contextlib
import os
import re
import subprocess
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

Step = Callable[[Any], Awaitable[None]]


# --- briques des scénarios (exécutées dans le processus enfant) -----------------------------------------------------

async def settle(pilot: Any, seconds: float = 0.6) -> None:
    await pilot.pause(seconds)
    with contextlib.suppress(Exception):  # un worker en erreur se voit sur la capture
        await pilot.app.workers.wait_for_complete()
    await pilot.pause(0.3)


async def press(pilot: Any, widget_id: str, seconds: float = 0.8) -> None:
    from textual.widgets import Button

    button = pilot.app.screen.query_one(f"#{widget_id}", Button)
    if button.disabled:
        raise SystemExit(f"bouton #{widget_id} grisé sur {type(pilot.app.screen).__name__}")
    button.press()
    await settle(pilot, seconds)


async def row(pilot: Any, table_id: str, index: int, select: bool = True) -> None:
    from textual.widgets import DataTable

    table = pilot.app.screen.query_one(f"#{table_id}", DataTable)
    table.focus()
    table.move_cursor(row=index)
    await pilot.pause(0.2)
    if select:
        table.action_select_cursor()
    await settle(pilot, 0.4)


async def row_matching(pilot: Any, table_id: str, text: str, select: bool = True) -> None:
    from textual.widgets import DataTable

    table = pilot.app.screen.query_one(f"#{table_id}", DataTable)
    for index, key in enumerate(table.rows):
        if any(text in str(cell) for cell in table.get_row(key)):
            await row(pilot, table_id, index, select)
            return
    raise SystemExit(f"aucune ligne « {text} » dans #{table_id}")


async def expand_faq(pilot: Any, title_start: str) -> None:
    from textual.widgets import Collapsible

    for group in pilot.app.screen.query(Collapsible):
        if str(group.title).startswith(title_start):
            group.collapsed = False
            await settle(pilot, 0.4)
            return
    raise SystemExit(f"aucun thème « {title_start} » dans la FAQ")


def go(*ids: str) -> Step:
    async def step(pilot: Any) -> None:
        for widget_id in ids:
            await press(pilot, widget_id)
    return step


def chain(*steps: Step) -> Step:
    async def step(pilot: Any) -> None:
        for one in steps:
            await one(pilot)
    return step


def wait(seconds: float) -> Step:
    async def step(pilot: Any) -> None:
        await settle(pilot, seconds)
    return step


def on_row(table_id: str, text: str) -> Step:
    async def step(pilot: Any) -> None:
        await row_matching(pilot, table_id, text)
    return step


def on_first_row(table_id: str) -> Step:
    async def step(pilot: Any) -> None:
        await row(pilot, table_id, 0)
    return step


def faq(title_start: str) -> Step:
    async def step(pilot: Any) -> None:
        await expand_faq(pilot, title_start)
    return step


def fill(widget_id: str, value: str) -> Step:
    async def step(pilot: Any) -> None:
        from textual.widgets import Input

        field = pilot.app.screen.query_one(f"#{widget_id}", Input)
        field.focus()
        field.value = value
        await settle(pilot, 0.4)
    return step


def show(widget_id: str) -> Step:
    async def step(pilot: Any) -> None:
        pilot.app.screen.query_one(f"#{widget_id}").scroll_visible(animate=False)
        await settle(pilot, 0.4)
    return step


def scroll_end(widget_id: str, back_lines: int = 0) -> Step:
    async def step(pilot: Any) -> None:
        widget = pilot.app.screen.query_one(f"#{widget_id}")
        widget.scroll_end(animate=False)
        await pilot.pause(0.3)
        if back_lines:
            widget.scroll_to(y=max(widget.scroll_y - back_lines, 0), animate=False)
        await settle(pilot, 0.4)
    return step


SPLASH = "splash"

# nom du fichier -> scénario depuis le menu principal (SPLASH : capture de l'écran d'accueil animé)
SCENARIOS: dict[str, Any] = {
    # écrans modifiés (remplacent la capture existante, même nom)
    "A-splash.png": SPLASH,
    "B-menu-principal.png": wait(0.5),
    "C-dashboard.png": chain(go("resource-status"), wait(4.0)),
    "D-logs.png": chain(go("logs", "view-logs"), fill("selection-input", "1"), go("view-simple"), wait(3.0)),
    "1-registre-des-capacités.png": chain(go("capabilities"), wait(2.0)),
    "3-profils.png": chain(go("profiles"), on_row("profiles-table", "hardened")),
    "4-configuration-detaillé..png": go("server-config"),
    "4.14-fast-cgi-php-fm.png": chain(go("server-config", "fastcgi"), on_row("fastcgi-table", "/gestion/")),
    "4.15-authentification.png": chain(go("server-config", "auth"), on_row("zones-table", "/gestion/")),
    "4.17-reverse-proxy.png": chain(go("server-config", "reverse-proxy"), wait(1.5)),
    "4.19-tls.png": go("server-config", "tls"),
    "5-menu-active-securité.png": go("active-defense"),
    "5.8-waf-modules.png": go("active-defense", "waf-modules"),
    "6-etat-ressources-dashboard.png": chain(go("resource-status"), wait(4.0)),
    "6.2-etat-ressources-dashboard-reverse.png": chain(go("resource-status"), wait(4.0), scroll_end("frame-traffic", 24)),
    "8-service.png": chain(go("service"), wait(1.5)),
    "9-multi-instance.png": chain(go("instances"), wait(1.5)),
    "10-audit-securité.png": chain(go("audit"), wait(3.0)),
    "11-sauvegarde-restauration-configuration.png": chain(go("backup"), on_first_row("backups-table"),
                                                           show("backups-table")),
    "12-guide-complet-aide.png": go("help"),
    # écrans nouveaux
    "3.1-assistant-profil-personnalise.png": chain(go("profiles", "create-custom"), fill("name-input", "vitrine"),
                                                   fill("label-input", "Site vitrine durci"),
                                                   fill("description-input", "Pages publiques, aucun envoi de fichier"),
                                                   wait(1.0)),
    "4.17.1-reverse-proxy-reglages-communs.png": go("server-config", "reverse-proxy", "general-settings"),
    "4.19.8-echeances-certificats.png": chain(go("server-config", "tls", "expiry"), wait(2.0)),
    "9.2-configuration-distante-prete.png": chain(go("instances"), on_row("instances-table", "courante"),
                                                  go("remote-config"), wait(2.0)),
    "9.3-comptes-administration-web.png": chain(go("instances"), on_row("instances-table", "courante"),
                                                go("remote-config", "accounts"), on_row("accounts-table", "alice")),
    "9.3.1-activer-totp.png": chain(go("instances"), on_row("instances-table", "courante"),
                                    go("remote-config", "accounts"), on_row("accounts-table", "bruno"),
                                    go("totp-enable")),
    "9.3.2-codes-de-secours.png": chain(go("instances"), on_row("instances-table", "courante"),
                                        go("remote-config", "accounts"), on_row("accounts-table", "alice"),
                                        go("backup-codes", "confirm")),
    "9.3.3-sessions-ouvertes.png": chain(go("instances"), on_row("instances-table", "courante"),
                                         go("remote-config", "accounts", "sessions"), wait(1.0)),
    "9.4-maitre.png": chain(go("instances"), on_row("instances-table", "courante"), go("remote-config", "master")),
    "9.5-relier-au-maitre.png": chain(go("instances"), on_row("instances-table", "staging"), go("link-master")),
    "9.6-alertes-locales.png": chain(go("instances"), on_row("instances-table", "courante"),
                                     go("remote-config", "alerts")),
    "11.1-sauvegarde-exporter.png": chain(go("backup"), on_first_row("backups-table"), go("export"),
                                          fill("df-dest_dir", "/home/kraynux/sauvegardes")),
    "11.2-sauvegarde-importer.png": chain(go("backup", "import"),
                                          fill("df-archive", "/home/kraynux/sauvegardes/omega-serv-sauvegarde-20261117.tar.gz")),
    "11.bis-rapport-complet.png": chain(go("report"), wait(3.0)),
    "12.2-faq.png": chain(go("help", "faq"), faq("Reverse proxy")),
}
"""9.1 (Configuration distante « à régler ») et 6 (État & Ressources sans reverse proxy) demandent une autre
configuration de la démo, préparée avant la capture (voir VARIANTS)."""

VARIANTS: dict[str, tuple[str, str]] = {
    "9.1-configuration-distante-a-regler.png": ("admin-web-a-regler", "9.2-configuration-distante-prete.png"),
    "6-etat-ressources-dashboard.png": ("no-reverse-proxy", "6-etat-ressources-dashboard.png"),
}
"""nom -> (variante de la démo à préparer avant, scénario repris)"""


async def _run(app: Any, name: str, svg_dir: str) -> None:
    from omega_serv.interfaces.tui.screens.home import HomeScreen
    from omega_serv.interfaces.tui.screens.splash import SplashScreen

    scenario = SCENARIOS[VARIANTS[name][1] if name in VARIANTS else name]
    width, height = (int(v) for v in os.environ["OMEGA_CAPTURE_SIZE"].split("x"))
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause(1.2)
        if scenario == SPLASH:
            if not isinstance(app.screen, SplashScreen):
                raise SystemExit(f"splash attendu, écran {type(app.screen).__name__}")
            app.save_screenshot("capture.svg", svg_dir)
            return
        for _attempt in range(4):
            if isinstance(app.screen, HomeScreen):
                break
            await pilot.press("enter")
            await pilot.pause(0.6)
        if not isinstance(app.screen, HomeScreen):
            raise SystemExit(f"menu principal attendu, écran {type(app.screen).__name__}")
        await settle(pilot)
        await scenario(pilot)
        await settle(pilot, 0.5)
        print("écran :", type(app.screen).__name__)
        app.save_screenshot("capture.svg", svg_dir)


def child(name: str, svg_dir: str) -> None:
    from omega_lib.i18n.policies import text_direction

    import omega_serv.__main__ as entry

    if text_direction(os.environ.get("OMEGA_SERV_LANG", "fr").replace("_", "-")) == "rtl":
        # arabe : comme _run_with_text_direction, omega-serv ordonne lui-même le texte droite-à-gauche
        from omega_lib.i18n.terminal_bidi import install_visual_reordering

        install_visual_reordering()

    entry._run_with_text_direction = lambda app: asyncio.run(_run(app, name, svg_dir))
    entry.main([])


# --- processus parent : un enfant par capture, puis SVG -> PNG --------------------------------------------------------

def to_png(svg: Path, png: Path, width: int) -> None:
    text = svg.read_text(encoding="utf-8")
    text = re.sub(r"@font-face\s*\{[^}]*\}", "", text)  # jamais de police téléchargée
    text = text.replace("Fira Code, monospace", "JetBrains Mono, monospace")
    # Rich place chaque cellule a 0,61 em, JetBrains Mono avance de 0,6 em : sans ajustement, une longue ligne de
    # cadre finit presque une cellule trop tot (rsvg-convert ignore textLength)
    text = re.sub(r"(-matrix \{[^}]*font-size: )20px", r"\g<1>20.333px", text, count=1)
    clip = re.search(r'clip-terminal">\s*<rect x="0" y="0" width="([\d.]+)" height="([\d.]+)"', text)
    shift = re.search(r'<g transform="translate\((\d+), (\d+)\)" clip-path="url\(#terminal-\d+-clip-terminal\)"',
                      text)
    if clip is None or shift is None:
        raise SystemExit(f"{svg} : zone du terminal introuvable")
    w, h = float(clip.group(1)), float(clip.group(2))
    x, y = shift.group(1), shift.group(2)
    # sans le cadre de fenêtre : la vue commence au terminal lui-même
    text = re.sub(r'viewBox="[^"]*"', f'viewBox="{x} {y} {w} {h}"', text, count=1)
    text = text.replace("<svg ", '<svg xml:space="preserve" ', 1)  # espaces gardés (cadres, colonnes)
    svg.write_text(text, encoding="utf-8")
    subprocess.run(["rsvg-convert", "--width", str(width), "--keep-aspect-ratio", str(svg), "-o", str(png)],
                   check=True)


def parent(demo: Path, out: Path, names: list[str], size: str, width: int, language: str = "fr") -> int:
    demo, out = demo.resolve(), out.resolve()
    application = demo / "omega-serv"
    if not (application / "src" / "omega_serv").is_dir() or not (demo / "home").is_dir():
        raise SystemExit(f"{demo} n'est pas une instance de démonstration (demo_instance.py)")
    out.mkdir(parents=True, exist_ok=True)
    svg_dir = out / "svg"
    svg_dir.mkdir(exist_ok=True)
    columns, lines = size.split("x")
    env = dict(os.environ, HOME=str(demo / "home"), PYTHONPATH=f"{application / 'src'}:{demo / 'masque'}",
               OMEGA_SYNCHRO_DIR=str(demo / "synchro"), COLUMNS=columns,
               LINES=lines, OMEGA_CAPTURE_SIZE=size, OMEGA_SERV_LANG=language)
    failed = 0
    for name in names or [*SCENARIOS, *VARIANTS]:
        if name in VARIANTS:
            print(f"{name} : variante « {VARIANTS[name][0]} » à préparer avant (voir demo_instance.py)")
        svg = svg_dir / "capture.svg"
        svg.unlink(missing_ok=True)
        result = subprocess.run([sys.executable, __file__, "--child", name, str(svg_dir)], env=env,
                                cwd=application, capture_output=True, text=True, timeout=180, check=False)
        if result.returncode != 0 or not svg.exists():
            failed += 1
            print(f"ÉCHEC {name}\n{result.stdout[-1500:]}{result.stderr[-1500:]}")
            continue
        final_svg = svg_dir / (Path(name).stem + ".svg")
        svg.replace(final_svg)
        to_png(final_svg, out / name, width)
        print(f"ok {name} ({result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ''})")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["--child"]:
        child(argv[1], argv[2])
        return 0
    size, width, language, rest = "140x50", 1400, "fr", []
    iterator = iter(argv)
    for arg in iterator:
        if arg == "--size":
            size = next(iterator)
        elif arg == "--width":
            width = int(next(iterator))
        elif arg == "--lang":
            language = next(iterator)  # code des catalogues : en, pt_BR, zh_CN, ar...
        else:
            rest.append(arg)
    if len(rest) < 2:
        print(__doc__)
        return 2
    return parent(Path(rest[0]), Path(rest[1]), rest[2:], size, width, language)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

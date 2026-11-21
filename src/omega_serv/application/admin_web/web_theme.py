"""Theme du panneau web parmi les 10 themes omega de la TUI (plan tableau de bord web §9.7, decisions de l'auteur du
2026-11-17).

- Reglage `theme` de l'option admin_web : « tui » (defaut, suit le theme de la TUI de l'instance, var/settings.json)
  ou l'un des 10 themes ; chaque navigateur peut en choisir un autre (cookie de ce navigateur, jamais ecrit sur le
  serveur).
- Une feuille par theme, /static/theme/<nom>.css : un bloc :root qui redefinit les variables d'admin.css (la CSP
  interdit tout style en ligne). omega-base = la charte hpc + craftdark d'admin.css, telle quelle ; les 9 autres sont
  calculees depuis les palettes d'omega-lib (omega_lib.theme.policies.TUI_THEMES), source commune a la suite."""
from __future__ import annotations

from omega_lib.theme.policies import DEFAULT_TUI_THEME, TUI_THEMES, Palette

FOLLOW_TUI = "tui"
WEB_THEMES: tuple[str, ...] = tuple(TUI_THEMES)
THEME_COOKIE = "omega_admin_theme"

_ANSI = {"black": "#000000", "white": "#ffffff", "cyan": "#00cdcd", "green": "#00cd00", "yellow": "#cdcd00",
         "red": "#cd0000", "ansi_bright_black": "#7f7f7f"}
"""omega-mono et omega-minimal sont en noms ANSI (terminaux anciens) : equivalents hex pour le navigateur."""

_BASE = {
    "--bg-dark": "#050814", "--bg-panel-solid": "#0a1223", "--bg-raised": "#111c33", "--cyan": "#00e5ff",
    "--cyan-dim": "#00b8cc", "--border-color": "#1a2a40",
    "--text-title": "#ffffff", "--text-1": "#aab7c6", "--text-2": "#909fb1", "--text-3": "#78879a",
    "--text-4": "#606e81", "--error": "#ff5c7a", "--ok": "#3ddc97", "--warn": "#ffcc66", "--line-1": "#f59e0b",
    "--line-2": "#a78bfa", "--row-border": "#0f192b",
}
"""omega-base : la charte hpc + craftdark (reglage B du 2026-11-16), memes valeurs que le :root d'admin.css."""


def _hex(color: str) -> str:
    return _ANSI.get(color, color).lower()


def _rgb(color: str) -> tuple[int, int, int]:
    value = _hex(color)
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def _mix(first: str, second: str, share: float) -> str:
    """`share` de `second` dans `first`."""
    a, b = _rgb(first), _rgb(second)
    return "#" + "".join(f"{round(x + (y - x) * share):02x}" for x, y in zip(a, b, strict=True))


def _is_light(color: str) -> bool:
    r, g, b = _rgb(color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 140


def _luminance(color: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(first: str, second: str) -> float:
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _readable(color: str, background: str, minimum: float = 4.5) -> str:
    """Couleur ecrite en texte : eclaircie (fond sombre) ou foncee (fond clair) jusqu'au contraste WCAG AA, teinte
    gardee (omega-contrast : accent #004ff9 sur fond bleu nuit ; omega-light : jaune d'alerte sur blanc)."""
    target = "#000000" if _is_light(background) else "#ffffff"
    for step in range(21):
        candidate = _mix(color, target, step / 20)
        if contrast(candidate, background) >= minimum:
            return candidate
    return target


def _variables(palette: Palette) -> dict[str, str]:
    background, surface, foreground = _hex(palette.background), _hex(palette.surface), _hex(palette.foreground)
    panel = surface if surface != background else _mix(background, foreground, 0.05)
    raised = _mix(surface, foreground, 0.07)
    accent = _readable(_hex(palette.accent), raised)  # texte et liens sur les cadres, boutons compris
    r, g, b = _rgb(accent)
    light = _is_light(background)

    def text(color: str) -> str:
        return _readable(_hex(color), raised)

    return {
        "--bg-dark": background,
        "--bg-panel-solid": panel,
        "--bg-raised": raised,
        "--cyan": accent,
        "--cyan-dim": _mix(accent, background, 0.2),
        "--cyan-glow": f"rgba({r}, {g}, {b}, 0.4)",
        "--border-color": _mix(background, accent, 0.25 if light else 0.18),
        "--text-title": foreground,
        "--text-1": _mix(foreground, background, 0.2),
        "--text-2": _mix(foreground, background, 0.3),
        "--text-3": _readable(_mix(foreground, background, 0.4), raised),
        "--text-4": _readable(_mix(foreground, background, 0.48), raised, 3.0),  # indications discretes
        "--error": text(palette.error),
        "--ok": text(palette.success),
        "--warn": text(palette.warning),
        "--line-1": text(palette.warning),
        "--line-2": text(palette.secondary),
        "--row-border": _mix(background, foreground, 0.08),
    } | ({"--title-glow": "none"} if light else {})  # lueur des titres (admin.css) : jamais sur fond clair


def theme_css(name: str) -> str:
    """Feuille du theme `name` (un nom inconnu donne omega-base)."""
    if name == "omega-base" or name not in TUI_THEMES:
        r, g, b = _rgb(_BASE["--cyan"])
        variables, light = {**_BASE, "--cyan-glow": f"rgba({r}, {g}, {b}, 0.4)"}, False
    else:
        variables = _variables(TUI_THEMES[name].palette)
        light = _is_light(variables["--bg-dark"])
    body = "".join(f"    {key}: {value};\n" for key, value in variables.items())
    return f":root {{\n{body}    color-scheme: {'light' if light else 'dark'};\n}}\n"


def resolve_theme(setting: object, tui_theme: str | None, browser: str | None = None) -> str:
    """Theme d'une page : celui du navigateur s'il en a choisi un, sinon le reglage, sinon (« tui ») celui de la TUI."""
    for candidate in (browser, None if setting == FOLLOW_TUI else setting, tui_theme):
        if isinstance(candidate, str) and candidate in TUI_THEMES:
            return candidate
    return DEFAULT_TUI_THEME

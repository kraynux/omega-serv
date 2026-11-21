"""Routage et pages du processus d'administration web (tableau de bord web, lot 3).

Decision pure, sans reseau : le serveur (infrastructure/admin_web/server.py) lit la requete et ecrit la reponse.
Ordre fixe, pour toute requete :
1. adresse hors des reseaux permis -> 403, avant meme la page de connexion (Q6) ;
2. POST : en-tete Origin, s'il est present, du meme hote (sinon 403) ; corps de formulaire borne ; jeton CSRF de la
   session (sauf la connexion elle-meme, protegee par SameSite et Origin) ;
3. page demandee ; sans session valide -> page de connexion.

Pages lot 3 : connexion (choix du mode, decision Q2), nouvelle saisie pour passer en Administration, accueil avec les
deux onglets. Lot 4 : tableau de bord et API JSON en lecture. Lot 5 : page Administration et `POST /action` (role
administration, mode Administration, jeton CSRF, saisie de moins de 15 min, page de confirmation, journal d'audit)."""
from __future__ import annotations

import functools
import html
import inspect
import ipaddress
import json
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from omega_serv.application.admin_web.actions import ActionOutcome, AdminActions, state_to_dict
from omega_serv.application.admin_web.admin_page import (
    ACTION_FIELDS,
    ACTIONS,
    admin_page_body,
    confirmation_body,
)
from omega_serv.application.admin_web.alert_monitor import AlertMonitor
from omega_serv.application.admin_web.auth import AdminAuth, LoginResult, Session
from omega_serv.application.admin_web.certificate_watch import CertificateWatch
from omega_serv.application.admin_web.dashboard import DEFAULT_LINES, PANELS, DashboardData
from omega_serv.application.admin_web.fleet import FleetService
from omega_serv.application.admin_web.history import HistoryRecorder
from omega_serv.application.admin_web.master_link import MasterAccess, clean_name
from omega_serv.application.admin_web.responses import AdminResponse, security_headers
from omega_serv.application.admin_web.stats_aggregator import StatsAggregator
from omega_serv.application.admin_web.web_theme import (
    THEME_COOKIE,
    WEB_THEMES,
    resolve_theme,
    theme_css,
)
from omega_serv.application.status.formatting import bytes_to_human
from omega_serv.application.tls.certificate_inventory import state_text, tone
from omega_serv.core.i18n import _, interface_html_dir, interface_html_lang
from omega_serv.domain.admin_web.alerts import RULES_BY_KEY, Alert
from omega_serv.domain.admin_web.master import FollowedInstance
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.admin_web.traffic_stats import OTHERS, ROBOT_PREFIX, mask_ip
from omega_serv.domain.security.trusted_proxy import is_trusted_proxy

COOKIE_NAME = "omega_admin"
MASTER_REFUSED_AUDIT_SECONDS = 60.0
_REASONS = {200: "OK", 400: "Bad Request", 403: "Forbidden", 429: "Too Many Requests"}
MAX_FORM_BYTES = 8192


def _unbroken_name(title: str) -> str:
    """Titre echappe ou « omega-serv » ne se coupe jamais au tiret (essai de l'auteur du 2026-11-17 : « omega- » puis
    « serv » a la ligne) : le nom passe a la ligne en entier."""
    name = "omega-serv"
    return html.escape(title).replace(name, f'<span class="nobr">{name}</span>')


_CSS_PATH = "/static/admin.css"
_JS_PATH = "/static/admin.js"
_THEME_JS_PATH = "/static/theme.js"
_ASSETS = Path(__file__).parent / "assets"
_STATIC = {_CSS_PATH: ((_ASSETS / "admin.css").read_bytes(), "text/css; charset=utf-8"),
           _JS_PATH: ((_ASSETS / "admin.js").read_bytes(), "text/javascript; charset=utf-8"),
           _THEME_JS_PATH: ((_ASSETS / "theme.js").read_bytes(), "text/javascript; charset=utf-8"),
           **{f"/static/theme/{name}.css": (theme_css(name).encode(), "text/css; charset=utf-8")
              for name in WEB_THEMES}}
_PAGE_THEME: ContextVar[tuple[str, str]] = ContextVar("admin_page_theme", default=("omega-base", ""))
"""(theme de la page, choix du navigateur ou "") de la requete en cours : une tache asyncio par connexion, donc un
contexte par requete (plan §9.7)."""


@dataclass(frozen=True)
class AdminRequest:
    peer_ip: str
    method: str
    target: str
    headers: tuple[tuple[str, str], ...]
    body: bytes = b""

    def header(self, name: str) -> str | None:
        lowered = name.lower()
        return next((value for key, value in self.headers if key.lower() == lowered), None)

    @property
    def path(self) -> str:
        return urlsplit(self.target).path or "/"

    def cookie(self, name: str) -> str | None:
        for part in (self.header("cookie") or "").split(";"):
            key, _sep, value = part.strip().partition("=")
            if key == name:
                return value
        return None

    def form(self) -> dict[str, str]:
        try:
            parsed = parse_qs(self.body.decode("utf-8"), keep_blank_values=True, max_num_fields=20)
        except (UnicodeDecodeError, ValueError):
            return {}
        return {key: values[0] for key, values in parsed.items()}


def _int(text: str | None, default: int) -> int:
    return int(text) if text is not None and text.isascii() and text.isdigit() else default


class AdminWebApp:
    def __init__(self, settings: AdminWebSettings, auth: AdminAuth, instance_name: str,
                 dashboard: DashboardData | None = None, actions: AdminActions | None = None,
                 master_access: MasterAccess | None = None, fleet: FleetService | None = None,
                 history: HistoryRecorder | None = None,
                 tui_theme: Callable[[], str | None] | None = None,
                 certificates: CertificateWatch | None = None, alerts: AlertMonitor | None = None,
                 stats: StatsAggregator | None = None) -> None:
        self._settings = settings
        self._auth = auth
        self._tls = settings.tls != "none"
        self._instance = instance_name
        self._dashboard = dashboard
        self._actions = actions
        self._master_access = master_access
        self._fleet = fleet
        self._history = history
        """Graphes de 1 h a 30 jours (lots 7 et 9) ; None : option `history` a false."""
        self._refused_audit: dict[str, float] = {}
        self._tui_theme = tui_theme
        self._certificates = certificates
        self._alerts = alerts
        self._stats = stats
        """Statistiques de trafic (etude modules, module 2) ; None : Historique desactive, vue absente."""
        """Alertes locales (etude modules, module 1) ; None : vue absente."""
        """Echeances des certificats locaux (etude modules, module 3) ; None : vue absente."""
        """Theme de la TUI de l'instance (var/settings.json), relu a chaque page : reglage « tui » (plan §9.7)."""

    # ------------------------------------------------------------------ reponses
    def _response(self, status: int, reason: str, body: bytes = b"", content_type: str = "text/html; charset=utf-8",
                  extra: tuple[tuple[str, str], ...] = ()) -> AdminResponse:
        headers = (("Content-Type", content_type), *security_headers(tls=self._tls), *extra)
        return AdminResponse(status, reason, headers, body)

    def _redirect(self, location: str, extra: tuple[tuple[str, str], ...] = ()) -> AdminResponse:
        return self._response(303, "See Other", extra=(("Location", location), *extra))

    def _cookie(self, token: str, *, clear: bool = False) -> tuple[str, str]:
        attributes = "Path=/; HttpOnly; SameSite=Strict" + ("; Secure" if self._tls else "")
        value = f"{COOKIE_NAME}=; Max-Age=0; {attributes}" if clear else f"{COOKIE_NAME}={token}; {attributes}"
        return ("Set-Cookie", value)

    def _page(self, title: str, content: str, status: int = 200, reason: str = "OK",
              extra: tuple[tuple[str, str], ...] = ()) -> AdminResponse:
        body = (f'<!doctype html><html lang="{interface_html_lang()}" dir="{interface_html_dir()}"><head>'
                f'<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>{html.escape(title)}</title><link rel="stylesheet" href="{_CSS_PATH}">'
                f'<link rel="stylesheet" id="theme-css" href="/static/theme/{_PAGE_THEME.get()[0]}.css">'
                f'<script src="{_THEME_JS_PATH}" defer></script></head>'
                f"<body><main>{content}</main></body></html>").encode()
        return self._response(status, reason, body, extra=extra)

    # ------------------------------------------------------------------ entree
    async def handle(self, request: AdminRequest) -> AdminResponse:
        if not is_trusted_proxy(request.peer_ip, self._settings.allowed_networks):
            return self._page(_("Administration web omega-serv"), "<h1>403</h1><p>" + html.escape(_(
                "Accès refusé : cette adresse n'est pas dans les réseaux permis de l'administration web.")) + "</p>",
                403, "Forbidden")
        if request.method not in ("GET", "HEAD", "POST"):
            return self._response(405, "Method Not Allowed", extra=(("Allow", "GET, HEAD, POST"),))
        path = request.path
        if path.startswith(("/api/maitre/", "/api/appairage/")):
            return await self._master_api(request)  # jeton ou code d'appairage, jamais le cookie du navigateur
        if not self._host_allowed(request):
            return self._page(_("Administration web omega-serv"), "<h1>421</h1><p>" + html.escape(_(
                "Nom d'hôte refusé : sans TLS, ouvrez l'administration web par son adresse IP, « localhost » ou le "
                "nom de cette machine.")) + "</p>", 421, "Misdirected Request")
        if request.method == "POST" and not self._same_origin(request):
            return self._response(403, "Forbidden")
        if path in _STATIC and request.method in ("GET", "HEAD"):
            content, content_type = _STATIC[path]
            return self._response(200, "OK", content, content_type)
        session = self._auth.session(request.cookie(COOKIE_NAME))
        self._set_page_theme(request)
        if path.startswith(("/api/instances", "/api/distant/")) and request.method in ("GET", "HEAD"):
            return await self._fleet_api(path, session)
        if path.startswith("/api/") and request.method in ("GET", "HEAD"):
            return self._api(request, session)
        if path.startswith("/instances/") and path not in ("/instances/ajouter", "/instances/sonde",
                                                           "/instances/retirer"):
            return await self._instance_routes(request, session)
        routes: dict[tuple[str, str], Callable[[], AdminResponse | Awaitable[AdminResponse]]] = {
            ("GET", "/connexion"): lambda: self._login_page(session),
            ("POST", "/connexion"): lambda: self._login(request),
            ("GET", "/"): lambda: self._home(session),
            ("GET", "/journaux"): lambda: self._view_page(session, "journaux"),
            ("GET", "/securite"): lambda: self._view_page(session, "securite"),
            ("GET", "/historique"): lambda: self._view_page(session, "historique"),
            ("GET", "/certificats"): lambda: self._view_page(session, "certificats"),
            ("GET", "/alertes"): lambda: self._view_page(session, "alertes"),
            ("GET", "/sessions"): lambda: self._view_page(session, "sessions"),
            ("GET", "/trafic"): lambda: self._traffic_page(session, request),
            ("POST", "/sessions/fermer"): lambda: self._close_session(request, session),
            ("GET", "/audit"): lambda: self._view_page(session, "audit"),
            ("POST", "/mode"): lambda: self._switch_mode(request, session),
            ("GET", "/reconnexion"): lambda: self._reauth_page(session),
            ("POST", "/reconnexion"): lambda: self._reauth(request, session),
            ("POST", "/deconnexion"): lambda: self._logout(request, session),
            ("POST", "/action"): lambda: self._action(request, session),
            ("GET", "/confirmation"): lambda: self._pending_confirmation(session),
            ("GET", "/instances"): lambda: self._instances_page(session),
            ("POST", "/instances/ajouter"): lambda: self._fleet_pair(request, session),
            ("POST", "/instances/sonde"): lambda: self._fleet_probe(request, session),
            ("POST", "/instances/retirer"): lambda: self._fleet_remove(request, session),
        }
        method = "GET" if request.method == "HEAD" else request.method
        route = routes.get((method, path))
        if route is None:
            return self._page(_("Administration web omega-serv"), "<h1>404</h1>", 404, "Not Found")
        result: AdminResponse | Awaitable[AdminResponse] = route()
        return await result if inspect.isawaitable(result) else result

    def _set_page_theme(self, request: AdminRequest) -> None:
        browser = request.cookie(THEME_COOKIE) or ""
        browser = browser if browser in WEB_THEMES else ""
        tui = None
        if self._tui_theme is not None:
            try:
                tui = self._tui_theme()
            except Exception:  # noqa: BLE001 - var/settings.json illisible : theme par defaut
                tui = None
        _PAGE_THEME.set((resolve_theme(self._settings.theme, tui, browser), browser))

    def _host_allowed(self, request: AdminRequest) -> bool:
        """Scan de securite n° 2 (2026-11-20, F37) : sans TLS, une page Internet pouvait, par DNS rebinding (son nom
        re-resolu vers 127.0.0.1), joindre l'interface depuis le navigateur d'un utilisateur local - le filtre
        reseau voit 127.0.0.1 et l'Origin egale le Host recu. Sans TLS, seuls une adresse IP, « localhost » et les
        noms de cette machine sont acceptes. Avec TLS, le navigateur exige un certificat au nom demande : un nom
        d'attaquant echoue deja a la poignee de main."""
        if self._tls:
            return True
        hostname = (urlsplit("//" + (request.header("host") or "")).hostname or "").lower().rstrip(".")
        if not hostname:
            return True  # sans Host (client HTTP/1.0, outil) : jamais un navigateur victime de rebinding
        if hostname == "localhost" or hostname.endswith(".localhost"):
            return True
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            return hostname in _machine_names()
        return True

    def _same_origin(self, request: AdminRequest) -> bool:
        origin = request.header("origin")
        if origin is None:
            return True  # navigateur ancien : SameSite=Strict et le jeton CSRF protegent
        return urlsplit(origin).netloc.lower() == (request.header("host") or "").lower()

    def _csrf_ok(self, request: AdminRequest, session: Session | None) -> bool:
        return session is not None and self._auth.csrf_ok(session, request.form().get("csrf", ""))

    # ------------------------------------------------------------------ connexion
    def _login_form(self, error: str = "", username: str = "", mode: str = "tableau") -> str:
        def checked(value: str) -> str:
            return " checked" if mode == value else ""
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        return (
            f'<section class="panel login"><h1>{_unbroken_name(_("Administration web omega-serv"))}</h1>'
            f'<p class="hint">{html.escape(self._instance)}</p>'
            f'<form method="post" action="/connexion">'
            f'<label for="identifiant">{html.escape(_("Identifiant"))}</label>'
            f'<input type="text" id="identifiant" name="identifiant" value="{html.escape(username)}" '
            f'autocomplete="username" required autofocus>'
            f'<label for="mot_de_passe">{html.escape(_("Mot de passe"))}</label>'
            f'<input type="password" id="mot_de_passe" name="mot_de_passe" autocomplete="current-password" required>'
            f'<label for="code">{html.escape(_("Code TOTP ou code de secours (si activé)"))}</label>'
            f'<input type="text" id="code" name="code" inputmode="numeric" autocomplete="one-time-code">'
            f'<fieldset><legend class="hint">{html.escape(_("Arriver sur :"))}</legend>'
            f'<label><input type="radio" name="mode" value="tableau"{checked("tableau")}> '
            f'{html.escape(_("Tableau de bord"))}</label>'
            f'<label><input type="radio" name="mode" value="administration"{checked("administration")}> '
            f'{html.escape(_("Administration"))}</label></fieldset>'
            f'<button type="submit">{html.escape(_("Se connecter"))}</button>{error_html}</form></section>')

    def _login_page(self, session: Session | None) -> AdminResponse:
        if session is not None:
            return self._redirect("/")
        return self._page(_("Connexion"), self._login_form())

    @staticmethod
    def _login_error(result: LoginResult) -> str:
        if result.error == "locked":
            return _("Trop d'essais : réessayez dans {seconds} s.").format(seconds=result.retry_after)
        if result.error == "totp_setup_required":
            return _("Ce compte d'administration doit activer TOTP avant de se connecter depuis un autre appareil "
                     "(TUI : Instances -> Configuration distante -> Comptes).")
        return _("Identifiant, mot de passe ou code incorrect.")

    def _login(self, request: AdminRequest) -> AdminResponse:
        form = request.form()
        username, mode = form.get("identifiant", "").strip(), form.get("mode", "tableau")
        result = self._auth.login(request.peer_ip, username, form.get("mot_de_passe", ""), form.get("code", ""), mode)
        if result.session is None:
            status, reason = (429, "Too Many Requests") if result.error == "locked" else (401, "Unauthorized")
            return self._page(_("Connexion"), self._login_form(self._login_error(result), username, mode),
                              status, reason)
        if mode == "administration" and result.session.mode != "administration":
            result.session.notice = _(  # role lecture : on le dit au lieu d'arriver en silence sur le tableau de bord
                "Compte en lecture seule : connecté en Tableau de bord. Pour agir, donnez-lui le rôle administration "
                "dans la TUI (Instances -> Configuration distante -> Comptes -> Rôle).")
            result.session.notice_ok = False
        return self._redirect("/", (self._cookie(result.session.token),))

    def _logout(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        if session is not None and self._csrf_ok(request, session):
            self._auth.logout(session, request.peer_ip)
        return self._redirect("/connexion", (self._cookie("", clear=True),))

    # ------------------------------------------------------------------ accueil et modes
    def _nav(self, session: Session) -> str:
        account = self._auth.account_of(session)
        csrf = html.escape(session.csrf)
        tabs = [("tableau", _("Tableau de bord"))]
        if account is not None and account.can_administer:
            tabs.append(("administration", _("Administration")))
        active = ' class="active"'
        buttons = "".join(
            f'<form method="post" action="/mode"><input type="hidden" name="csrf" value="{csrf}">'
            f'<input type="hidden" name="mode" value="{value}"><button type="submit"'
            f'{active if session.mode == value else ""}>{html.escape(label)}</button></form>'
            for value, label in tabs)
        who = html.escape(_("{name} · {instance}").format(name=session.username, instance=self._instance))
        logout = (f'<form method="post" action="/deconnexion"><input type="hidden" name="csrf" value="{csrf}">'
                  f'<button type="submit">{html.escape(_("Déconnexion"))}</button></form>')
        return f'<nav class="top">{buttons}<span class="who">{who}</span>{self._theme_picker()}{logout}</nav>'

    @staticmethod
    def _theme_picker() -> str:
        """Choix du theme pour CE navigateur (cookie, jamais ecrit sur le serveur ; plan §9.7, decision QT2)."""
        current, browser = _PAGE_THEME.get()
        options = [("", _("Thème de l'instance"))] + [(name, name) for name in WEB_THEMES]
        items = "".join(f'<option value="{value}"{" selected" if value == browser else ""}>{html.escape(label)}'
                        f'</option>' for value, label in options)
        label = html.escape(_("Thème (ce navigateur)"))
        return (f'<select id="theme-select" class="theme-select" aria-label="{label}" title="{label}" '
                f'data-current="{current}">{items}</select>')

    def _subnav(self, session: Session, current: str) -> str:
        account = self._auth.account_of(session)
        links = [("etat", "/", _("État & Ressources")), ("journaux", "/journaux", _("Journaux")),
                 ("securite", "/securite", _("Sécurité"))]
        if self._history is not None:
            links.append(("historique", "/historique", _("Historique")))
        if self._stats is not None:
            links.append(("trafic", "/trafic", _("Trafic")))
        if self._certificates is not None:
            links.append(("certificats", "/certificats", _("Certificats")))
        if self._alerts is not None:
            count = len(self._alerts.book.active)
            label = _("Alertes ({count})").format(count=count) if count else _("Alertes")
            links.append(("alertes", "/alertes", label))
        if account is not None and account.can_administer:
            links.append(("audit", "/audit", _("Journal d'audit")))
        links.append(("sessions", "/sessions", _("Sessions")))
        if self._fleet is not None:
            links.append(("instances", "/instances", _("Instances")))
        active = ' class="active"'
        items = "".join(f'<a href="{href}"{active if key == current else ""}>{html.escape(label)}</a>'
                        for key, href, label in links)
        return f'<nav class="sub">{items}</nav>'

    async def _home(self, session: Session | None) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        if session.mode == "administration":
            return await self._admin_page(session)
        return self._view_page(session, "etat")

    def _view_page(self, session: Session | None, view: str) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        account = self._auth.account_of(session)
        if view == "audit" and (account is None or not account.can_administer):
            return self._page(_("Administration web omega-serv"), "<h1>403</h1>", 403, "Forbidden")
        loading = html.escape(_("Chargement..."))
        if view == "etat":
            body = "".join(f'<div class="column" data-api="/api/vue/{panel}" data-title="{html.escape(title)}">'
                           f'<p class="hint">{loading}</p></div>'
                           for panel, title in (("etat", _("ÉTAT DU SERVEUR")), ("flux", _("FLUX (LOG D'ACCÈS)")),
                                                ("ressources", _("RESSOURCES SYSTÈME"))))
            body = f'<div class="columns">{body}</div>'
            title = _("État & Ressources")
        elif view == "securite":
            body = f'<div data-api="/api/vue/securite"><p class="hint">{loading}</p></div>'
            title = _("Sécurité")
        elif view == "historique":
            if self._history is None:
                return self._page(_("Administration web omega-serv"), "<h1>404</h1>", 404, "Not Found")
            title = _("Historique")
            body = self._history_body()
        elif view == "sessions":
            title = _("Sessions")
            body = self._sessions_body(session)
        elif view == "alertes":
            if self._alerts is None:
                return self._page(_("Administration web omega-serv"), "<h1>404</h1>", 404, "Not Found")
            title = _("Alertes")
            body = self._alerts_body()
        elif view == "certificats":
            if self._certificates is None:
                return self._page(_("Administration web omega-serv"), "<h1>404</h1>", 404, "Not Found")
            title = _("Certificats")
            body = self._certificates_body()
        elif view == "audit":
            title = _("Journal d'audit")
            body = (f'<section class="panel"><h2>{html.escape(title)}</h2>'
                    f'<pre class="log" data-lines="/api/audit">{loading}</pre></section>')
        else:
            body = self._logs_body()
            title = _("Journaux")
        updated = f'<p class="hint updated" data-updated-label="{html.escape(_("Mis à jour à"))}"></p>'
        notice = ""
        if session.notice:  # affiche une fois (ex. : compte en lecture qui avait choisi Administration)
            tone = "tone-ok" if session.notice_ok else "tone-warn"
            notice = f'<p class="notice {tone}">{html.escape(session.notice)}</p>'
            session.notice = ""
        content = f'{self._nav(session)}{self._subnav(session, view)}{notice}{updated}{body}' \
                  f'<script src="{_JS_PATH}"></script>'
        return self._page(title, content)

    def _traffic_page(self, session: Session | None, request: AdminRequest) -> AdminResponse:
        """Trafic des sites (etude modules, module 2) : aujourd'hui, 7 ou 30 jours ; lecture seule, sans pays."""
        if session is None:
            return self._redirect("/connexion")
        if self._stats is None:
            return self._page(_("Administration web omega-serv"), "<h1>404</h1>", 404, "Not Found")
        query = parse_qs(urlsplit(request.target).query)
        period = query.get("periode", ["jour"])[0]
        period = period if period in ("jour", "7j", "30j") else "jour"
        summary = self._stats.summary(period)
        mask = self._settings.stats_mask_ip is True
        periods = (("jour", _("Aujourd'hui")), ("7j", _("7 jours")), ("30j", _("30 jours")))
        buttons = "".join(f'<a class="range{" active" if value == period else ""}" href="/trafic?periode={value}">'
                          f'{html.escape(label)}</a>' for value, label in periods)

        def table(title: str, rows: list[tuple[str, int]], head: str) -> str:
            if not rows:
                return (f'<section class="panel"><h2>{html.escape(title)}</h2>'
                        f'<p class="hint">{html.escape(_("Rien pour cette période."))}</p></section>')
            body = "".join(f"<tr><td>{html.escape(key)}</td><td>{count}</td></tr>" for key, count in rows)
            return (f'<section class="panel"><h2>{html.escape(title)}</h2><div class="table-wrap"><table><thead><tr>'
                    f'<th>{html.escape(head)}</th><th>{html.escape(_("Requêtes"))}</th></tr></thead><tbody>{body}'
                    f'</tbody></table></div></section>')

        ips = [(mask_ip(ip) if mask and ip != OTHERS else ip, count) for ip, count in summary.tops["ips"]]
        if mask:  # deux adresses du meme /24 deviennent une seule ligne
            merged: dict[str, int] = {}
            for ip, count in ips:
                merged[ip] = merged.get(ip, 0) + count
            ips = sorted(merged.items(), key=lambda item: -item[1])
        totals = [(_("Requêtes"), str(summary.requests)), (_("Données envoyées"), bytes_to_human(summary.bytes)),
                  (_("Erreurs 4xx"), str(summary.errors_4xx)), (_("Erreurs 5xx"), str(summary.errors_5xx))]
        totals_html = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>" for k, v in totals)
        hours = "".join(f"<td>{count}</td>" for count in summary.hours)
        hour_heads = "".join(f"<th>{hour:02d}</th>" for hour in range(24))
        hint = html.escape(_("Lu dans le journal d'accès au fil de l'eau depuis le démarrage de l'administration web "
                             "(rien n'est relu en arrière), jour par jour, 31 jours gardés dans var/lib/admin/stats/. "
                             "Pages sans la partie après « ? » ; référents : nom du site seulement. Pas de pays : aucune "
                             "base externe."))
        statuses = [(code, count) for code, count in summary.statuses.items()]

        def shown(key: str) -> str:
            """Cles techniques des fichiers du jour, traduites ici seulement."""
            if key == OTHERS:
                return _("(autres)")
            if key == "autre":
                return _("autre")
            if key.startswith(ROBOT_PREFIX):
                return _("robot : {name}").format(name=key[len(ROBOT_PREFIX):])
            return key

        agents = [(shown(key), count) for key, count in summary.tops["agents"]]
        ips = [(shown(key), count) for key, count in ips]
        content = (
            f'{self._nav(session)}{self._subnav(session, "trafic")}'
            f'<section class="panel history"><div class="ranges">{buttons}</div><p class="hint">{hint}</p>'
            f'<div class="table-wrap"><table><tbody>{totals_html}</tbody></table></div>'
            f'<h3>{html.escape(_("Requêtes par heure"))}</h3><div class="table-wrap"><table><thead><tr>{hour_heads}'
            f'</tr></thead><tbody><tr>{hours}</tr></tbody></table></div></section>'
            + table(_("Pages les plus demandées"), [(shown(k), c) for k, c in summary.tops["pages"]], _("Page"))
            + table(_("Pages introuvables (404)"), [(shown(k), c) for k, c in summary.tops["not_found"]], _("Page"))
            + table(_("Adresses IP les plus actives"), ips, _("Adresse IP"))
            + table(_("Statuts HTTP"), statuses, _("Statut"))
            + table(_("Référents"), [(shown(k), c) for k, c in summary.tops["referrers"]], _("Site d'origine"))
            + table(_("Navigateurs et robots"), agents, _("Famille")))
        return self._page(_("Trafic"), content)

    def _sessions_body(self, session: Session) -> str:
        """Sessions ouvertes (etude modules, module 5) : un compte administration voit et ferme toutes les sessions ;
        un compte lecture, les siennes seulement."""
        account = self._auth.account_of(session)
        everyone = account is not None and account.can_administer
        shown = [s for s in self._auth.open_sessions() if everyone or s.username == session.username]
        csrf = html.escape(session.csrf)

        def when(stamp: float) -> str:
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(stamp))

        modes = {"tableau": _("Tableau de bord"), "administration": _("Administration")}
        rows = []
        for item in shown:
            mine = item.token == session.token
            close = (f'<form method="post" action="/sessions/fermer"><input type="hidden" name="csrf" value="{csrf}">'
                     f'<input type="hidden" name="session" value="{item.public_id}">'
                     f'<button type="submit" class="danger">{html.escape(_("Fermer"))}</button></form>')
            rows.append(f'<tr><td>{html.escape(item.username)}</td><td>{html.escape(item.ip or "-")}</td>'
                        f'<td>{html.escape(modes.get(item.mode, item.mode))}</td><td>{when(item.created)}</td>'
                        f'<td>{when(item.last_seen)}</td>'
                        f'<td>{html.escape(_("(cette session)")) if mine else close}</td></tr>')
        heads = "".join(f"<th>{html.escape(h)}</th>" for h in (_("Compte"), _("Adresse"), _("Mode"), _("Ouverte"),
                                                                _("Dernière activité"), ""))
        hint = html.escape(_("Sessions du panneau web encore ouvertes (30 min sans activité ou 8 h au plus). Fermer "
                             "une session déconnecte ce navigateur tout de suite ; c'est noté dans le journal "
                             "d'audit. Un compte lecture ne voit que ses propres sessions.") if everyone else
                           _("Vos sessions encore ouvertes. Fermer une session déconnecte ce navigateur tout de "
                             "suite."))
        notice = ""
        if session.notice:
            notice = f'<p class="notice tone-{"ok" if session.notice_ok else "warn"}">{html.escape(session.notice)}</p>'
            session.notice = ""
        return (f'<section class="panel"><h2>{html.escape(_("Sessions ouvertes"))}</h2><p class="hint">{hint}</p>'
                f'{notice}<div class="table-wrap"><table><thead><tr>{heads}</tr></thead><tbody>{"".join(rows)}'
                f'</tbody></table></div></section>')

    def _close_session(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        if not self._csrf_ok(request, session):
            return self._response(403, "Forbidden")
        target_id = request.form().get("session", "")
        account = self._auth.account_of(session)
        target = next((s for s in self._auth.open_sessions() if s.public_id == target_id), None)
        allowed = target is not None and (target.username == session.username
                                          or (account is not None and account.can_administer))
        if target is None or not allowed:
            self._auth.audit(f"fermeture de session refusee compte={session.username} session={target_id[:12]!r} "
                             f"ip={request.peer_ip}")
            session.notice, session.notice_ok = _("Session introuvable ou déjà fermée."), False
            return self._redirect("/sessions")
        self._auth.close_session(target_id, session.username, request.peer_ip)
        session.notice, session.notice_ok = _("Session fermée."), True
        return self._redirect("/sessions")

    def _alerts_body(self) -> str:
        """Alertes locales (etude modules, module 1) : en cours et 30 derniers jours ; reglages dans la TUI."""
        monitor = self._alerts
        assert monitor is not None
        book = monitor.book

        def when(stamp: float | None) -> str:
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(stamp)) if stamp else "-"

        def value(alert: Alert, number: float | None) -> str:
            rule = RULES_BY_KEY.get(alert.rule)
            if number is None or rule is None:
                return "-"
            if rule.key in ("backend", "incident"):
                return ""
            if rule.key == "certificat":
                return _("{days} jours").format(days=int(number))
            return f"{number:.0f} {rule.unit}".strip()

        def label(alert: Alert) -> str:
            rule = RULES_BY_KEY.get(alert.rule)
            return _(rule.label) if rule is not None else alert.rule

        hint = html.escape(_("Alertes locales : rien n'est envoyé hors de cette machine. Seuils, maintenance et règles "
                             "coupées : TUI, Instances -> Configuration distante -> Alertes. Journal : "
                             "var/log/alertes.log."))
        parts = [f'<section class="panel"><h2>{html.escape(_("Alertes en cours"))}</h2><p class="hint">{hint}</p>']
        until = monitor.maintenance_until
        if until is not None:
            notice = _("Maintenance jusqu'à {date} : aucune nouvelle alerte.").format(date=when(until))
            parts.append(f'<p class="notice tone-warn">{html.escape(notice)}</p>')
        if self._history is None:
            off = _("Historique désactivé : pas d'alerte sur le disque, la mémoire, le processeur, la température ni "
                    "la batterie.")
            parts.append(f'<p class="hint">{html.escape(off)}</p>')
        active = sorted(book.active.values(), key=lambda a: a.opened_at, reverse=True)
        if active:
            heads = "".join(f"<th>{html.escape(h)}</th>" for h in (_("Alerte"), _("Sujet"), _("Depuis"), _("Valeur"),
                                                                    _("Seuil"), _("Pire")))
            rows = "".join(f'<tr><td class="tone-error">{html.escape(label(a))}</td><td>{html.escape(a.subject)}</td>'
                           f'<td>{when(a.opened_at)}</td><td>{html.escape(value(a, a.value))}</td>'
                           f'<td>{html.escape(value(a, a.threshold))}</td><td>{html.escape(value(a, a.worst))}</td></tr>'
                           for a in active)
            parts.append(f'<div class="table-wrap"><table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody>'
                         f'</table></div>')
        else:
            parts.append(f'<p class="tone-ok">{html.escape(_("Aucune alerte en cours."))}</p>')
        parts.append(f'</section><section class="panel"><h2>{html.escape(_("30 derniers jours"))}</h2>')
        closed = list(reversed(book.history))[:200]
        if closed:
            heads = "".join(f"<th>{html.escape(h)}</th>" for h in (_("Alerte"), _("Sujet"), _("Ouverte"), _("Fermée"),
                                                                    _("Pire")))
            rows = "".join(f'<tr><td>{html.escape(label(a))}</td><td>{html.escape(a.subject)}</td>'
                           f'<td>{when(a.opened_at)}</td><td>{when(a.closed_at)}</td>'
                           f'<td>{html.escape(value(a, a.worst))}</td></tr>' for a in closed)
            parts.append(f'<div class="table-wrap"><table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody>'
                         f'</table></div>')
        else:
            parts.append(f'<p class="hint">{html.escape(_("Aucune alerte fermée."))}</p>')
        parts.append("</section>")
        return "".join(parts)

    def _certificates_body(self) -> str:
        """Certificats locaux et leurs echeances (etude modules, module 3) : lecture seule, rien n'est renouvele ici."""
        watch = self._certificates
        assert watch is not None
        hint = html.escape(_("Certificats de cette instance (site, panneau web, secure/certificates/), relus toutes les "
                             "12 heures et à chaque rechargement. Alerte à 30, 14, 7 et 1 jour de l'échéance. Le "
                             "renouvellement se fait dans la TUI (TLS) ou par Certbot."))
        if watch.checked_at is None:
            content = f'<p class="hint">{html.escape(_("Lecture en cours..."))}</p>'
        elif not watch.lines:
            content = f'<p class="hint">{html.escape(_("Aucun certificat dans cette instance."))}</p>'
        else:
            rows = "".join(
                f'<tr><td>{html.escape(line.label)}</td><td>{html.escape(line.path)}</td>'
                f'<td>{html.escape(line.not_after or "-")}</td>'
                f'<td class="tone-{tone(line)}">{html.escape(state_text(line))}</td>'
                f'<td>{html.escape(", ".join(line.names[:4]) or line.subject)}</td></tr>'
                for line in watch.lines)
            heads = "".join(f"<th>{html.escape(h)}</th>" for h in (
                _("Certificat"), _("Fichier"), _("Fin de validité"), _("État"), _("Noms")))
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(watch.checked_at))
            content = (f'<div class="table-wrap"><table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody>'
                       f'</table></div><p class="hint">{html.escape(_("Relu le {date}.").format(date=stamp))}</p>')
        return (f'<section class="panel"><h2>{html.escape(_("Certificats"))}</h2><p class="hint">{hint}</p>'
                f'{content}</section>')

    def _history_body(self) -> str:
        """Graphes dessines par admin.js (SVG, aucun HTML venu du serveur) ; libelles traduits ici. Lot 9 (§9.5) : six
        plages, « Moyenne » ou « Max 1 min », graphes de la machine, d'omega-serv et des sites ; un graphe sans
        aucune valeur sur la plage (pas de capteur, pas de batterie...) est masque par la page."""
        charts = (
            ("cpu", _("Processeur"), "%", "", ""),
            ("mem", _("Mémoire"), "%", "", "memoire"),
            ("swap", _("Swap"), "%", "", "swap"),
            ("load1,load5,load15", _("Charge"), "num", _("1 min|5 min|15 min"), ""),
            ("site_out", _("Téléchargements (envoyé aux visiteurs)"), "bits", "", ""),
            ("site_in", _("Téléversement (reçu des visiteurs)"), "bits", "", ""),
            ("net_in,net_out", _("Réseau - débit (reçu / envoyé)"), "bytes", _("reçu|envoyé"), ""),
            ("rps", _("Réseau - requêtes par seconde"), "num", "", ""),
            ("tcp,sockets", _("Réseau - connexions et sockets"), "num", _("TCP en cours|sockets ouverts"), ""),
            ("disk_read,disk_write", _("Disque - E/S"), "bytes", _("lecture|écriture"), ""),
            ("disk_used", _("Disque - espace (partition de l'instance)"), "%", "", "disque"),
            ("procs", _("Processus (machine)"), "num", "", ""),
            ("serv_cpu", _("Processus d'omega-serv - processeur"), "%", "", "coeurs"),
            ("serv_mem", _("Processus d'omega-serv - mémoire"), "size", "", "memoire-octets"),
            ("temp", _("Température du processeur"), "celsius", "", ""),
            ("battery", _("Batterie"), "%", "", "batterie"),
        )
        # 5e champ (lot 9c, essai de l'auteur du 2026-11-17) : courbe remplie et « utilise / total · % » en haut a
        # droite, d'apres les tailles totales lues a l'affichage (capacites de /api/historique)
        figures = "".join(f'<figure class="chart" data-series="{chart[0]}" data-unit="{chart[2]}" '
                          f'data-legend="{html.escape(chart[3])}"'
                          + (f' data-detail="{chart[4]}"' if chart[4] else "") + '>'
                          f'<figcaption>{html.escape(chart[1])}</figcaption><div class="plot"></div></figure>'
                          for chart in charts)
        labels = {"now": _("maintenant"), "empty": _("Pas encore de mesure : un relevé toutes les 10 s, le premier "
                                                      "point après 20 s."),
                  "units": _("o/s|Ko/s|Mo/s|Go/s"), "units_bits": _("bit/s|kbit/s|Mbit/s|Gbit/s"),
                  "units_size": _("o|Ko|Mo|Go"), "of": _("{used} / {total} · {percent}"),
                  "cores": _("{used} / {total} cœurs · {percent}"), "plugged": _("sur secteur · {percent}"),
                  "left": _("{hours} h {minutes} min restantes · {percent}"), "same_max": _("Même courbe à cette échelle : chaque point dure une "
                                                                "minute ou moins.")}
        data = " ".join(f'data-label-{key.replace("_", "-")}="{html.escape(value)}"' for key, value in labels.items())
        ranges = (("1h", _("1 heure"), _("il y a 1 h")), ("3h", _("3 heures"), _("il y a 3 h")),
                  ("12h", _("12 heures"), _("il y a 12 h")), ("24h", _("24 heures"), _("il y a 24 h")),
                  ("7j", _("7 jours"), _("il y a 7 jours")), ("30j", _("30 jours"), _("il y a 30 jours")))
        buttons = "".join(f'<button type="button" data-range="{value}" data-ago="{html.escape(ago)}">'
                          f'{html.escape(label)}</button>' for value, label, ago in ranges)
        modes = "".join(f'<button type="button" data-mode="{value}">{html.escape(label)}</button>'
                        for value, label in (("avg", _("Moyenne")), ("max", _("Max 1 min"))))
        hint = html.escape(_("Machine entière, sauf « Processus d'omega-serv » (cette instance) et Téléchargements / "
                             "Téléversement (sites de cette instance). Requêtes : lignes ajoutées au journal d'accès. "
                             "Moyenne : chaque point est la moyenne de sa tranche ; Max 1 min : la minute la plus "
                             "chargée de la tranche (24 heures, 7 et 30 jours). Graphe masqué : aucune mesure sur la "
                             "plage (pas de capteur sur cette machine, ou pas encore de visiteur pour Téléchargements / "
                             "Téléversement)."))
        return (f'<section class="panel history" data-history="/api/historique" {data}>'
                f'<div class="ranges">{buttons}</div><div class="ranges modes">{modes}</div>'
                f'<p class="hint">{hint}</p><p class="hint mode-note" hidden></p>'
                f'<div class="charts">{figures}</div></section>')

    def _logs_body(self) -> str:
        hint = html.escape(_("Journaux de cette instance et de sa bibliothèque, lus par le service. Instantané : les "
                             "dernières lignes ; direct : les lignes ajoutées, toutes les 2 secondes."))
        return (
            f'<section class="panel logs"><h2>{html.escape(_("Journaux"))}</h2>'
            f'<p class="hint">{hint}</p>'
            f'<div class="controls"><label>{html.escape(_("Journal"))} <select id="log-select"></select></label>'
            f'<label>{html.escape(_("Lignes"))} <input type="text" id="log-lines" value="{DEFAULT_LINES}" '
            f'inputmode="numeric" size="5"></label>'
            f'<label>{html.escape(_("Filtre"))} <input type="text" id="log-filter" size="16"></label>'
            f'<button type="button" id="log-snapshot">{html.escape(_("Instantané"))}</button>'
            f'<button type="button" id="log-follow" data-on="{html.escape(_("Arrêter le direct"))}" '
            f'data-off="{html.escape(_("Direct"))}">{html.escape(_("Direct"))}</button></div>'
            f'<p class="hint" id="log-status"></p><pre class="log" id="log-output"></pre></section>')

    # ------------------------------------------------------------------ API JSON (lecture seule)
    def _json(self, payload: object, status: int = 200, reason: str = "OK") -> AdminResponse:
        return self._response(status, reason, json.dumps(payload, ensure_ascii=False).encode(),
                              "application/json; charset=utf-8")

    def _api(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        if session is None:
            return self._json({"error": "session"}, 401, "Unauthorized")
        query = {key: values[0] for key, values in parse_qs(urlsplit(request.target).query).items()}
        path = request.path
        if path == "/api/historique":
            series = self._history.series(query.get("plage", "1h"), query.get("mode", "avg")) \
                if self._history is not None else None
            return self._json(series) if series is not None else self._json({"error": "historique"}, 404,
                                                                             "Not Found")
        if self._dashboard is None:
            return self._json({"error": "indisponible"}, 503, "Service Unavailable")
        if path.startswith("/api/vue/"):
            payload = self._dashboard.panel(path[len("/api/vue/"):])
            return self._json(payload) if payload is not None else self._json({"error": "vue"}, 404, "Not Found")
        if path == "/api/journaux":
            return self._json({"logs": self._dashboard.log_list()})
        if path == "/api/journal":
            found = self._dashboard.log_snapshot(query.get("id", ""), _int(query.get("lignes"), DEFAULT_LINES),
                                                 query.get("filtre", "")[:200])
            return self._json(found) if found is not None else self._json({"error": "journal"}, 404, "Not Found")
        if path == "/api/journal/suite":
            found = self._dashboard.log_follow(query.get("id", ""), _int(query.get("curseur"), 0))
            return self._json(found) if found is not None else self._json({"error": "journal"}, 404, "Not Found")
        if path == "/api/audit":
            account = self._auth.account_of(session)
            if account is None or not account.can_administer:
                return self._json({"error": "role"}, 403, "Forbidden")
            return self._json(self._dashboard.audit(_int(query.get("lignes"), DEFAULT_LINES)))
        return self._json({"error": "route"}, 404, "Not Found")

    def _switch_mode(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        if not self._csrf_ok(request, session):
            return self._response(403, "Forbidden")
        outcome = self._auth.switch_mode(session, request.form().get("mode", ""), request.peer_ip)
        return self._redirect("/reconnexion" if outcome == "reauth" else "/")

    def _reauth_form(self, session: Session, error: str = "") -> str:
        error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
        hint = html.escape(_("Pour agir, confirmez votre identité (dernière saisie il y a plus de 15 minutes)."))
        return (
            f'{self._nav(session)}<section class="panel login"><h2>{html.escape(_("Administration"))}</h2>'
            f'<p class="hint">{hint}</p>'
            f'<form method="post" action="/reconnexion"><input type="hidden" name="csrf" '
            f'value="{html.escape(session.csrf)}">'
            f'<label for="mot_de_passe">{html.escape(_("Mot de passe"))}</label>'
            f'<input type="password" id="mot_de_passe" name="mot_de_passe" autocomplete="current-password" required '
            f'autofocus>'
            f'<label for="code">{html.escape(_("Code TOTP ou code de secours (si activé)"))}</label>'
            f'<input type="text" id="code" name="code" inputmode="numeric" autocomplete="one-time-code">'
            f'<button type="submit">{html.escape(_("Confirmer"))}</button>{error_html}</form></section>')

    def _reauth_page(self, session: Session | None) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        return self._page(_("Administration"), self._reauth_form(session))

    def _reauth(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        if not self._csrf_ok(request, session):
            return self._response(403, "Forbidden")
        form = request.form()
        result = self._auth.reauthenticate(session, form.get("mot_de_passe", ""), form.get("code", ""),
                                           request.peer_ip)
        if result.session is None:
            return self._page(_("Administration"), self._reauth_form(session, self._login_error(result)), 401,
                              "Unauthorized")
        return self._redirect("/confirmation" if session.pending else "/")

    # ------------------------------------------------------------------ Administration (lot 5)
    async def _admin_page(self, session: Session) -> AdminResponse:
        if self._actions is None:
            body = f'<p class="hint">{html.escape(_("Actions indisponibles dans cet environnement."))}</p>'
        else:
            state = await self._actions.state()
            body = admin_page_body(state, session.csrf, session.notice, session.notice_ok)
            session.notice = ""
        content = f'{self._nav(session)}<h1>{html.escape(_("Administration"))}</h1>{body}'
        return self._page(_("Administration"), content)

    def _forbidden(self, session: Session, request: AdminRequest, why: str) -> AdminResponse:
        self._auth.audit(f"action refusee ({why}) compte={session.username} ip={request.peer_ip}")
        return self._page(_("Administration web omega-serv"), "<h1>403</h1>", 403, "Forbidden")

    async def _action(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        if not self._csrf_ok(request, session):
            return self._response(403, "Forbidden")
        account = self._auth.account_of(session)
        if account is None or not account.can_administer:
            return self._forbidden(session, request, "role lecture")
        if self._actions is None:
            return self._page(_("Administration"), "<h1>503</h1>", 503, "Service Unavailable")
        form = request.form()
        params = {key: form[key][:300] for key in ACTION_FIELDS if key in form}
        if params.get("action") not in ACTIONS:
            return self._page(_("Administration"), "<h1>400</h1>", 400, "Bad Request")
        if self._auth.needs_reauth(session):
            session.pending = params  # proposee a la confirmation juste apres la nouvelle saisie
            return self._redirect("/reconnexion")
        if session.mode != "administration":
            return self._forbidden(session, request, "mode tableau de bord")
        if form.get("confirme") != "1":
            return self._confirmation(session, params)
        session.pending = None
        outcome = await self._run(params)
        details = " ".join(f"{key}={value!r}" for key, value in params.items() if key != "action")
        self._auth.audit(f"action {params['action']} {details} compte={session.username} ip={request.peer_ip} -> "
                         f"{'ok' if outcome.ok else 'echec'} : {outcome.message}".replace("\n", " "))
        session.notice, session.notice_ok = outcome.message, outcome.ok
        return self._redirect("/")

    def _confirmation(self, session: Session, params: dict[str, str]) -> AdminResponse:
        assert self._actions is not None
        warnings: tuple[str, ...] = ()
        if params["action"] == "bannir":
            network, error, warnings = self._actions.check_ban(params.get("adresse", ""), params.get("duree", ""))
            if network is None:
                session.notice, session.notice_ok = error, False
                return self._redirect("/")
        content = f'{self._nav(session)}' + confirmation_body(params, warnings, session.csrf, self._actions.log_name)
        return self._page(_("Confirmer l'action"), content)

    def _pending_confirmation(self, session: Session | None) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        if session.pending and "_instance" in session.pending and session.mode == "administration":
            item = self._fleet.find(session.pending["_instance"]) if self._fleet is not None else None
            if item is not None:
                params = {key: value for key, value in session.pending.items() if key != "_instance"}
                return self._remote_confirmation(session, item, params)
        if not session.pending or self._actions is None or session.mode != "administration":
            return self._redirect("/")
        return self._confirmation(session, session.pending)

    async def _run(self, params: dict[str, str]) -> ActionOutcome:
        assert self._actions is not None
        return await self._actions.run(params)

    # ------------------------------------------------------------------ appels d'un maitre (lot 6a, plan §7.4)
    def _master_refused(self, request: AdminRequest) -> AdminResponse:
        now = time.monotonic()
        if now - self._refused_audit.get(request.peer_ip, -MASTER_REFUSED_AUDIT_SECONDS) >= MASTER_REFUSED_AUDIT_SECONDS:
            if len(self._refused_audit) > 1000:
                self._refused_audit.clear()
            self._refused_audit[request.peer_ip] = now
            self._auth.audit(f"appel de maitre refuse (jeton absent ou faux) ip={request.peer_ip}")
        return self._json({"error": "jeton"}, 401, "Unauthorized")

    def _json_body(self, request: AdminRequest) -> object:
        try:
            return json.loads(request.body.decode("utf-8")) if request.body else None
        except (UnicodeDecodeError, ValueError):
            return None

    async def _master_api(self, request: AdminRequest) -> AdminResponse:
        access = self._master_access
        if access is None:
            return self._json({"error": "indisponible"}, 503, "Service Unavailable")
        path, method = request.path, request.method
        if path == "/api/appairage/defi" and method == "POST":
            reply = access.challenge()
            return self._json(reply.payload, reply.status, _REASONS.get(reply.status, ""))
        if path == "/api/appairage/preuve" and method == "POST":
            reply = await access.prove(self._json_body(request), request.peer_ip)
            return self._json(reply.payload, reply.status, _REASONS.get(reply.status, ""))
        master = access.authenticate(request.header("authorization"))
        if master is None:
            return self._master_refused(request)
        if self._dashboard is None:
            return self._json({"error": "indisponible"}, 503, "Service Unavailable")
        if method in ("GET", "HEAD"):
            if path == "/api/maitre/resume":
                return self._json({"instance": self._instance, "droits": master.rights, **self._dashboard.summary()})
            if path.startswith("/api/maitre/vue/"):
                payload = self._dashboard.panel(path[len("/api/maitre/vue/"):])
                return self._json(payload) if payload is not None else self._json({"error": "vue"}, 404, "Not Found")
            if path == "/api/maitre/administration":
                if not master.can_administer:
                    return self._json({"error": "droits"}, 403, "Forbidden")
                if self._actions is None:
                    return self._json({"error": "indisponible"}, 503, "Service Unavailable")
                return self._json(state_to_dict(await self._actions.state()))
        if path == "/api/maitre/action" and method == "POST":
            return await self._master_action(request, master.master_name, master.can_administer)
        return self._json({"error": "route"}, 404, "Not Found")

    async def _master_action(self, request: AdminRequest, master_name: str, allowed: bool) -> AdminResponse:
        body = self._json_body(request)
        raw = body.get("params") if isinstance(body, dict) else None
        account = clean_name(body.get("compte", "")) if isinstance(body, dict) else ""
        who = f"maitre={master_name!r} compte_maitre={account!r} ip={request.peer_ip}"
        if not allowed:
            self._auth.audit(f"action refusee (maitre en lecture seule) {who}")
            return self._json({"error": "droits"}, 403, "Forbidden")
        if not isinstance(raw, dict) or raw.get("action") not in ACTIONS or self._actions is None:
            return self._json({"error": "action"}, 400, "Bad Request")
        params = {key: str(raw[key])[:300] for key in ACTION_FIELDS if key in raw}
        outcome = await self._actions.run(params)
        details = " ".join(f"{key}={value!r}" for key, value in params.items() if key != "action")
        self._auth.audit(f"action {params['action']} {details} {who} -> {'ok' if outcome.ok else 'echec'} : "
                         f"{outcome.message}".replace("\n", " "))
        return self._json({"ok": outcome.ok, "message": outcome.message})

    # ------------------------------------------------------------------ instance maitre (lot 6c, plan §7)
    def _notice_html(self, session: Session) -> str:
        if not session.notice:
            return ""
        css = "tone-ok" if session.notice_ok else "error"
        text, session.notice = session.notice, ""
        return f'<p class="notice {css}">{html.escape(text)}</p>'

    def _admin_gate(self, request: AdminRequest, session: Session | None) -> AdminResponse | None:
        """Ajouter, retirer, agir a distance : role et mode Administration, CSRF, saisie de moins de 15 min."""
        if session is None:
            return self._redirect("/connexion")
        if not self._csrf_ok(request, session):
            return self._response(403, "Forbidden")
        account = self._auth.account_of(session)
        if account is None or not account.can_administer:
            return self._forbidden(session, request, "role lecture")
        if self._fleet is None:
            return self._page(_("Instances"), "<h1>503</h1>", 503, "Service Unavailable")
        if self._auth.needs_reauth(session):
            return self._redirect("/reconnexion")
        if session.mode != "administration":
            return self._forbidden(session, request, "mode tableau de bord")
        return None

    async def _fleet_api(self, path: str, session: Session | None) -> AdminResponse:
        if session is None:
            return self._json({"error": "session"}, 401, "Unauthorized")
        if self._fleet is None:
            return self._json({"error": "indisponible"}, 503, "Service Unavailable")
        if path == "/api/instances":
            return self._json(await self._fleet.overview())
        parts = path.split("/")  # ["", "api", "distant", id, "vue", panneau]
        if len(parts) == 6 and parts[4] == "vue" and parts[5] in PANELS:
            status, payload = await self._fleet.panel(parts[3], parts[5])
            return self._json(payload, status, "OK" if status == 200 else "Not Found")
        return self._json({"error": "route"}, 404, "Not Found")

    def _instances_page(self, session: Session | None) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        if self._fleet is None:
            return self._page(_("Instances"), "<h1>503</h1>", 503, "Service Unavailable")
        loading = html.escape(_("Chargement..."))
        updated = f'<p class="hint updated" data-updated-label="{html.escape(_("Mis à jour à"))}"></p>'
        hint = html.escape(_("État de chaque instance suivie par ce maître, toutes les 5 s. Cliquez sur un nom pour "
                             "ouvrir son tableau de bord."))
        listing = (f'<section class="panel"><h2>{html.escape(_("Instances suivies"))}</h2><p class="hint">{hint}</p>'
                   f'<div data-fleet="/api/instances"><p class="hint">{loading}</p></div></section>')
        content = (f"{self._nav(session)}{self._subnav(session, 'instances')}{updated}{self._notice_html(session)}"
                   f"{listing}{self._fleet_management(session)}<script src=\"{_JS_PATH}\"></script>")
        return self._page(_("Instances"), content)

    def _fleet_management(self, session: Session) -> str:
        assert self._fleet is not None
        account = self._auth.account_of(session)
        if account is None or not account.can_administer:
            return ""
        identity = self._fleet.identity()
        who = html.escape(_("Ce maître : {name} (identifiant {master_id}).").format(
            name=identity.name, master_id=identity.master_id))
        if session.mode != "administration":
            return (f'<section class="panel"><h2>{html.escape(_("Gérer les instances suivies"))}</h2>'
                    f'<p class="hint">{who}</p><p class="hint">'
                    f'{html.escape(_("Passez en mode Administration pour ajouter ou retirer une instance."))}'
                    f"</p></section>")
        csrf = html.escape(session.csrf)
        hidden = f'<input type="hidden" name="csrf" value="{csrf}">'
        pair_hint = html.escape(_("Sur l'instance à suivre : TUI -> Instances -> Configuration distante -> Maître -> "
                                  "« Accepter un maître (code) ». Le code vaut 10 minutes ; 3 essais faux ferment "
                                  "la fenêtre. L'adresse de ce maître doit être dans les réseaux permis de "
                                  "l'instance."))
        pair = (f'<h3>{html.escape(_("Ajouter à la main (code d’appairage)"))}</h3><p class="hint">{pair_hint}</p>'
                f'<form method="post" action="/instances/ajouter" class="row-form">{hidden}'
                f'<label>{html.escape(_("Nom (facultatif)"))} <input type="text" name="nom" size="16" '
                f'maxlength="80"></label>'
                f'<label>{html.escape(_("Adresse IP"))} <input type="text" name="adresse" required size="18"></label>'
                f'<label>{html.escape(_("Port"))} <input type="text" name="port" required size="6" '
                f'inputmode="numeric"></label>'
                f'<label>{html.escape(_("Code"))} <input type="text" name="code" required size="10" '
                f'autocomplete="off"></label>'
                f'<button type="submit">{html.escape(_("Relier"))}</button></form>')
        probe_hint = html.escape(_("Pour un backend qui n'est pas omega-serv : statut HTTP et temps de réponse "
                                   "seulement, sans jeton."))
        probe = (f'<h3>{html.escape(_("Ajouter une sonde HTTP"))}</h3><p class="hint">{probe_hint}</p>'
                 f'<form method="post" action="/instances/sonde" class="row-form">{hidden}'
                 f'<label>{html.escape(_("Nom (facultatif)"))} <input type="text" name="nom" size="16" '
                 f'maxlength="80"></label>'
                 f'<label>URL <input type="text" name="url" required size="32" placeholder="http://10.0.0.5:8080/">'
                 f'</label><button type="submit">{html.escape(_("Ajouter"))}</button></form>')
        rows = "".join(
            f"<tr><td>{html.escape(item.name)}</td><td>{html.escape(item.target)}</td><td>"
            f'<form method="post" action="/instances/retirer" class="inline">{hidden}'
            f'<input type="hidden" name="instance" value="{html.escape(item.instance_id)}">'
            f'<button type="submit" class="danger">{html.escape(_("Retirer..."))}</button></form></td></tr>'
            for item in self._fleet.fleet().instances)
        listing = (f'<div class="table-wrap"><table><tr><th>{html.escape(_("Instance"))}</th>'
                   f'<th>{html.escape(_("Adresse"))}</th><th></th></tr>{rows}</table></div>' if rows else "")
        return (f'<section class="panel"><h2>{html.escape(_("Gérer les instances suivies"))}</h2>'
                f'<p class="hint">{who}</p>{listing}{pair}{probe}</section>')

    async def _fleet_pair(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        refused = self._admin_gate(request, session)
        if refused is not None:
            return refused
        assert session is not None and self._fleet is not None
        form = request.form()
        port_text = form.get("port", "").strip()
        port = int(port_text) if port_text.isascii() and port_text.isdigit() and len(port_text) <= 5 else 0
        outcome = await self._fleet.pair(form.get("nom", ""), form.get("adresse", "").strip(), port,
                                         form.get("code", ""))
        if not outcome.ok:
            self._auth.audit(f"appairage echoue adresse={form.get('adresse', '')[:60]!r}:{port} "
                             f"compte={session.username} ip={request.peer_ip} : {outcome.message}")
        session.notice, session.notice_ok = outcome.message, outcome.ok
        return self._redirect("/instances")

    def _fleet_probe(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        refused = self._admin_gate(request, session)
        if refused is not None:
            return refused
        assert session is not None and self._fleet is not None
        form = request.form()
        outcome = self._fleet.add_probe(form.get("nom", ""), form.get("url", "").strip())
        session.notice, session.notice_ok = outcome.message, outcome.ok
        return self._redirect("/instances")

    def _fleet_remove(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        refused = self._admin_gate(request, session)
        if refused is not None:
            return refused
        assert session is not None and self._fleet is not None
        form = request.form()
        item = self._fleet.find(form.get("instance", ""))
        if item is None:
            session.notice, session.notice_ok = _("Instance inconnue."), False
            return self._redirect("/instances")
        if form.get("confirme") != "1":
            csrf = html.escape(session.csrf)
            text = html.escape(_("Retirer {name} ({target}) des instances suivies ? Son jeton est oublié ici : la "
                                 "suivre de nouveau demandera un nouvel appairage.").format(name=item.name,
                                                                                          target=item.target))
            content = (f'{self._nav(session)}<section class="panel login"><h2>'
                       f'{html.escape(_("Confirmer l’action"))}</h2><p>{text}</p>'
                       f'<form method="post" action="/instances/retirer"><input type="hidden" name="csrf" '
                       f'value="{csrf}"><input type="hidden" name="instance" value="{html.escape(item.instance_id)}">'
                       f'<input type="hidden" name="confirme" value="1"><button type="submit" class="danger">'
                       f'{html.escape(_("Confirmer"))}</button></form><p><a href="/instances">'
                       f'{html.escape(_("Annuler"))}</a></p></section>')
            return self._page(_("Confirmer l'action"), content)
        outcome = self._fleet.remove(item.instance_id)
        session.notice, session.notice_ok = outcome.message, outcome.ok
        return self._redirect("/instances")

    async def _instance_routes(self, request: AdminRequest, session: Session | None) -> AdminResponse:
        if session is None:
            return self._redirect("/connexion")
        parts = request.path.split("/")  # ["", "instances", id, (administration | action)]
        item = self._fleet.find(parts[2]) if self._fleet is not None and len(parts) in (3, 4) else None
        if item is None or item.kind != "omega-serv":
            return self._page(_("Instances"), "<h1>404</h1>", 404, "Not Found")
        method = "GET" if request.method == "HEAD" else request.method
        if len(parts) == 3 and method == "GET":
            return self._instance_view(session, item)
        if len(parts) == 4 and parts[3] == "administration" and method == "GET":
            return await self._remote_admin_page(session, item)
        if len(parts) == 4 and parts[3] == "action" and method == "POST":
            return await self._remote_action(request, session, item)
        return self._page(_("Instances"), "<h1>404</h1>", 404, "Not Found")

    def _instance_header(self, session: Session, item: FollowedInstance, current: str) -> str:
        account = self._auth.account_of(session)
        links = [("vue", f"/instances/{item.instance_id}", _("Tableau de bord"))]
        if account is not None and account.can_administer and session.mode == "administration":
            links.append(("admin", f"/instances/{item.instance_id}/administration", _("Administration")))
        active = ' class="active"'
        items = "".join(f'<a href="{href}"{active if key == current else ""}>{html.escape(label)}</a>'
                        for key, href, label in links)
        title = html.escape(_("Instance suivie : {name}").format(name=item.name))
        return (f'{self._nav(session)}{self._subnav(session, "instances")}<h1>{title}</h1>'
                f'<p class="hint">{html.escape(item.target)}</p><nav class="sub">{items}</nav>')

    def _instance_view(self, session: Session, item: FollowedInstance) -> AdminResponse:
        loading = html.escape(_("Chargement..."))
        base = f"/api/distant/{item.instance_id}/vue"
        columns = "".join(f'<div class="column" data-api="{base}/{panel}" data-title="{html.escape(title)}">'
                          f'<p class="hint">{loading}</p></div>'
                          for panel, title in (("etat", _("ÉTAT DU SERVEUR")), ("flux", _("FLUX (LOG D'ACCÈS)")),
                                               ("ressources", _("RESSOURCES SYSTÈME"))))
        updated = f'<p class="hint updated" data-updated-label="{html.escape(_("Mis à jour à"))}"></p>'
        content = (f'{self._instance_header(session, item, "vue")}{updated}<div class="columns">{columns}</div>'
                   f'<div data-api="{base}/securite"><p class="hint">{loading}</p></div>'
                   f'<script src="{_JS_PATH}"></script>')
        return self._page(item.name, content)

    @staticmethod
    def _retarget(body: str, item: FollowedInstance) -> str:
        """Les formulaires de la page Administration visent l'instance suivie. Les valeurs venues de l'instance sont
        echappees (html.escape) : la chaine exacte `action="/action"` ne peut venir que de nos gabarits."""
        return body.replace('action="/action"', f'action="/instances/{item.instance_id}/action"').replace(
            'href="/"', f'href="/instances/{item.instance_id}/administration"')

    async def _remote_admin_page(self, session: Session, item: FollowedInstance) -> AdminResponse:
        account = self._auth.account_of(session)
        if account is None or not account.can_administer or session.mode != "administration":
            return self._redirect(f"/instances/{item.instance_id}")
        assert self._fleet is not None
        state = await self._fleet.admin_state(item)
        notice = self._notice_html(session)
        if isinstance(state, str):
            body = f'{notice}<p class="error">{html.escape(state)}</p>'
        else:
            body = self._retarget(admin_page_body(state, session.csrf, "", True), item)
            body = notice + body
        return self._page(_("Administration"), self._instance_header(session, item, "admin") + body)

    def _remote_confirmation(self, session: Session, item: FollowedInstance, params: dict[str, str]) -> AdminResponse:
        where = html.escape(_("Instance suivie : {name}").format(name=item.name))
        content = (f'{self._nav(session)}<p class="hint">{where}</p>'
                   + self._retarget(confirmation_body(params, (), session.csrf), item))
        return self._page(_("Confirmer l'action"), content)

    async def _remote_action(self, request: AdminRequest, session: Session, item: FollowedInstance) -> AdminResponse:
        if not self._csrf_ok(request, session):
            return self._response(403, "Forbidden")
        account = self._auth.account_of(session)
        if account is None or not account.can_administer:
            return self._forbidden(session, request, "role lecture")
        assert self._fleet is not None
        form = request.form()
        params = {key: form[key][:300] for key in ACTION_FIELDS if key in form}
        if params.get("action") not in ACTIONS:
            return self._page(_("Administration"), "<h1>400</h1>", 400, "Bad Request")
        if self._auth.needs_reauth(session):
            session.pending = {**params, "_instance": item.instance_id}
            return self._redirect("/reconnexion")
        if session.mode != "administration":
            return self._forbidden(session, request, "mode tableau de bord")
        if form.get("confirme") != "1":
            return self._remote_confirmation(session, item, params)
        session.pending = None
        outcome = await self._fleet.action(item, params, session.username)
        details = " ".join(f"{key}={value!r}" for key, value in params.items() if key != "action")
        self._auth.audit(f"action {params['action']} {details} instance={item.name!r} compte={session.username} "
                         f"ip={request.peer_ip} -> {'ok' if outcome.ok else 'echec'} : {outcome.message}"
                         .replace("\n", " "))
        session.notice, session.notice_ok = outcome.message, outcome.ok
        return self._redirect(f"/instances/{item.instance_id}/administration")


@functools.cache
def _machine_names() -> frozenset[str]:
    """Noms de cette machine (nom court, nom complet, nom.local) acceptes sans TLS (F37)."""
    import socket

    names = {socket.gethostname().lower(), socket.getfqdn().lower()}
    names |= {f"{name.split('.')[0]}.local" for name in set(names)}
    return frozenset(name for name in names if name)

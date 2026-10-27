"""Page d'erreur HTML par defaut (retour utilisateur 2026-09-09 : "on
mettra des pages html d'erreur fournies de base"). Toujours utilisee
pour toute reponse d'erreur (statut >= 400) dont le corps est vide -
voir infrastructure/server/asyncio_server.py::_write_response, seul
point d'injection (jamais chaque gestionnaire individuellement) - et
seulement si l'option `error_pages` n'est pas activee/configuree pour
ce statut (sinon `resolve_error_page_body` sert le fichier personnalise
de l'utilisateur en priorite, voir application/server/resolve_error_page.py).

Generation en chaine pure, meme convention que
domain/routing/dirlisting.py : jinja2 est confine a
infrastructure.exporters.html_exporter par contrat import-linter, et
une page d'erreur (rendue a chaque requete, potentiellement sous
charge) n'a pas besoin d'un moteur de template pour un contenu aussi
simple.

`_CURATED_PAGES` (401/403/404/451, retour utilisateur 2026-09-19 ; 429
ajoutee le 2026-10-26 depuis le modele ~/DEV/SERV/errors/429.html - la
page generique, avec son <style> inline, restait sans aucun style sous
la CSP du profil durci) :
modeles fournis directement en constantes - jamais lues depuis un
fichier (aucune I/O ici, meme regle que le reste du module). Les autres
codes gardent la page generique minimaliste ci-dessous.

CSS servi en fichier EXTERNE reserve (retour utilisateur 2026-10-12 :
"le css ne s'applique pas sur le profil hardene") - meme patron que
`domain/routing/dirlisting.py::CSS_URL_PREFIX` : `style-src 'self'`
autorise une feuille de style de meme origine, jamais un `<style>`
inline sans `unsafe-inline`/nonce. `ERROR_CSS_URL_PREFIX`, servi par
application/server/serve_error_css.py, chemin reserve verifie tout en
haut de route_request() - jamais soumis aux regles du site (crucial
ici : une page d'erreur peut etre justement declenchee PAR une regle
d'acces qui bloquerait sinon le CSS lui-meme). Un seul theme necessaire
(pas de personnalisation utilisateur comme le dirlisting) : les 3
variantes de couleur (rouge/orange/cyan) vivent dans le meme fichier
via des classes (`theme-orange`, `theme-cyan`; le rouge est le defaut,
401 et 451 n'ont pas besoin de classe supplementaire)."""
from __future__ import annotations

from html import escape

from omega_serv.core.i18n import N_, P_, page_html_dir, page_html_lang
from omega_serv.domain.http.status_codes import reason_phrase_for

ERROR_CSS_URL_PREFIX = "/.omega-serv-error-css/"
ERROR_CSS_FILENAME = "error-pages.css"
ERROR_CSS_PATH = ERROR_CSS_URL_PREFIX + ERROR_CSS_FILENAME
"""Chemin URL reserve, meme statut que `dirlisting.CSS_URL_PREFIX` - vit
ici pour que ce module et `application/server/serve_error_css.py` (qui
genere la reponse reelle) partagent exactement la meme valeur sans
jamais diverger."""

_ERROR_PAGES_CSS = (
    "* { margin: 0; padding: 0; box-sizing: border-box; }\n"
    "body {\n"
    "    background: #0a0e1a;\n"
    "    color: #e0e0e0;\n"
    "    font-family: monospace;\n"
    "    min-height: 100vh;\n"
    "    display: flex;\n"
    "    justify-content: center;\n"
    "    align-items: center;\n"
    "    padding: 20px;\n"
    "}\n"
    ".container {\n"
    "    background: #0f1320;\n"
    "    border-radius: 12px;\n"
    "    padding: 40px;\n"
    "    text-align: center;\n"
    "    max-width: 500px;\n"
    "    box-shadow: 0 8px 32px rgba(0,0,0,0.4);\n"
    "    border: 1px solid rgba(255, 68, 68, 0.3);\n"
    "}\n"
    ".code {\n"
    "    font-size: 5rem;\n"
    "    color: #ff4444;\n"
    "    font-weight: bold;\n"
    "    text-shadow: 0 0 10px rgba(255, 68, 68, 0.3);\n"
    "}\n"
    ".title {\n"
    "    font-size: 1.5rem;\n"
    "    margin: 20px 0;\n"
    "    color: #ff6666;\n"
    "}\n"
    ".msg {\n"
    "    color: #9098a5;\n"
    "    margin-bottom: 30px;\n"
    "}\n"
    ".warning {\n"
    "    background: rgba(255, 68, 68, 0.1);\n"
    "    border-left: 3px solid #ff4444;\n"
    "    padding: 12px;\n"
    "    margin: 20px 0;\n"
    "    font-size: 0.85rem;\n"
    "    color: #ff8888;\n"
    "    text-align: left;\n"
    "}\n"
    "a {\n"
    "    color: #ff4444;\n"
    "    text-decoration: none;\n"
    "}\n"
    "a:hover {\n"
    "    text-decoration: underline;\n"
    "    color: #ff7777;\n"
    "}\n"
    "hr {\n"
    "    border: none;\n"
    "    height: 1px;\n"
    "    background: #2a2e3a;\n"
    "    margin: 20px 0;\n"
    "}\n"
    ".footer {\n"
    "    font-size: 0.7rem;\n"
    "    color: #606878;\n"
    "    margin-top: 20px;\n"
    "}\n"
    "\n"
    "/* Variante orange (403) */\n"
    ".container.theme-orange { border-color: rgba(255, 170, 68, 0.8); }\n"
    ".theme-orange .code { color: #ffaa44; text-shadow: 0 0 10px rgba(255, 170, 68, 0.3); }\n"
    ".theme-orange .title { color: #ffbb66; }\n"
    ".theme-orange .warning { background: rgba(255, 170, 68, 0.1); border-left-color: #ffaa44; color: #ffcc88; }\n"
    ".theme-orange a { color: #ffaa44; }\n"
    ".theme-orange a:hover { color: #ffcc88; }\n"
    "\n"
    "/* Variante cyan (404) */\n"
    ".container.theme-cyan { border-color: rgba(0, 212, 255, 0.9); }\n"
    ".theme-cyan .code { color: #00d4ff; text-shadow: none; }\n"
    ".theme-cyan .title { color: #e0e0e0; }\n"
    ".theme-cyan .warning { background: rgba(0, 212, 255, 0.08); border-left-color: #00d4ff; color: #9098a5; }\n"
    ".theme-cyan a { color: #00d4ff; }\n"
    ".theme-cyan a:hover { color: #00d4ff; }\n"
    "\n"
    "/* Variante jaune (429) */\n"
    ".container.theme-yellow { border-color: rgba(255, 255, 0, 0.8); }\n"
    ".theme-yellow .code { color: #e5de00; text-shadow: 0 0 10px rgba(255, 170, 68, 0.3); }\n"
    ".theme-yellow .title { color: #e5de00; }\n"
    ".theme-yellow .msg { color: #e5de00; }\n"
    ".theme-yellow .warning { background: rgba(255, 170, 68, 0.1); border-left-color: #e5de00; color: #e5de00; }\n"
    ".theme-yellow a { color: #e5de00; }\n"
    ".theme-yellow a:hover { color: #e5de00; }\n"
)


def error_pages_css() -> str:
    return _ERROR_PAGES_CSS


_CURATED_TEMPLATES: dict[int, tuple[str, tuple[str, ...]]] = {
    401: (
        (
        "<!DOCTYPE html>\n"
        '<html lang="{lang}" dir="{dir}">\n'
        "<head>\n"
        '    <meta charset="UTF-8">\n'
        "    <title>{t0}</title>\n"
        '    \t<link rel="icon" type="image/png" href="/favicon-96x96.png" sizes="96x96" />\n'
        '\t<link rel="icon" type="image/svg+xml" href="/favicon.svg" />\n'
        '\t<link rel="shortcut icon" href="/favicon.ico" />\n'
        '\t<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />\n'
        '\t<meta name="apple-mobile-web-app-title" content="Omega" />\n'
        '    <link rel="stylesheet" href="/.omega-serv-error-css/error-pages.css">\n'
        "</head>\n"
        "<body>\n"
        '    <div class="container">\n'
        '        <div class="code">401</div>\n'
        '        <div class="title">{t1}</div>\n'
        '        <div class="msg">{t2}</div>\n'
        '        <div class="warning">\n'
        "             {t3}<br>\n"
        "            {t4}\n"
        "        </div>\n"
        "        <hr>\n"
        '         <a href="/">{t5}</a>\n'
        '        <div class="footer">  {t6} <a href="https://github.com/kraynux/omega-serv">OMEGA-SERV</a></div>\n'
        "    </div>\n"
        "</body>\n"
        "</html>\n"
        ),
        (
            N_('401 - Non autorisé'),
            N_('⛔ Non autorisé'),
            N_('Authentification requise pour accéder à cette ressource.'),
            N_('✕ Identifiants invalides ou manquants.'),
            N_("Veuillez vérifier vos informations d'accès."),
            N_("← Retour à l'index"),
            N_('⚡ propulsé par'),
        ),
    ),
    403: (
        (
        "<!DOCTYPE html>\n"
        '<html lang="{lang}" dir="{dir}">\n'
        "<head>\n"
        '    <meta charset="UTF-8">\n'
        "    <title>{t0}</title>\n"
        '    \t<link rel="icon" type="image/png" href="/favicon-96x96.png" sizes="96x96" />\n'
        '\t<link rel="icon" type="image/svg+xml" href="/favicon.svg" />\n'
        '\t<link rel="shortcut icon" href="/favicon.ico" />\n'
        '\t<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />\n'
        '\t<meta name="apple-mobile-web-app-title" content="Omega" />\n'
        '    <link rel="stylesheet" href="/.omega-serv-error-css/error-pages.css">\n'
        "</head>\n"
        "<body>\n"
        '    <div class="container theme-orange">\n'
        '        <div class="code">403</div>\n'
        '        <div class="title">{t1}</div>\n'
        '        <div class="msg">{t2}</div>\n'
        '        <div class="warning">\n'
        "             \t        {t3}<br>\n"
        "            {t4}\n"
        "        </div>\n"
        "        <hr>\n"
        '        <a href="/">{t5}</a>\n'
        '        <div class="footer">  {t6} <a href="https://github.com/kraynux/omega-serv">OMEGA-SERV</a></div>\n'
        "    </div>\n"
        "</body>\n"
        "</html>\n"
        ),
        (
            N_('403 - Accès interdit'),
            N_('⛔ Accès interdit'),
            N_("Vous n'avez pas les droits nécessaires pour accéder à cette ressource."),
            N_('Permission refusée.'),
            N_("Vérifiez vos droits d'accès ou contactez l'administrateur."),
            N_("← Retour à l'index"),
            N_('⚡ propulsé par'),
        ),
    ),
    404: (
        (
        "<!DOCTYPE html>\n"
        '<html lang="{lang}" dir="{dir}">\n'
        "<head>\n"
        '    <meta charset="UTF-8">\n'
        "    <title>{t0}</title>\n"
        '    \t<link rel="icon" type="image/png" href="/favicon-96x96.png" sizes="96x96" />\n'
        '\t<link rel="icon" type="image/svg+xml" href="/favicon.svg" />\n'
        '\t<link rel="shortcut icon" href="/favicon.ico" />\n'
        '\t<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />\n'
        '\t<meta name="apple-mobile-web-app-title" content="Omega" />\n'
        '    <link rel="stylesheet" href="/.omega-serv-error-css/error-pages.css">\n'
        "</head>\n"
        "<body>\n"
        '    <div class="container theme-cyan">\n'
        '        <div class="code">404</div>\n'
        '        <div class="title">{t1}</div>\n'
        '        <div class="msg">{t2}</div>\n'
        '        <div class="warning">\n'
        "            {t3}<br>\n"
        "\n"
        "        </div>\n"
        "        <hr>\n"
        '        <a href="/">{t4}</a>\n'
        '        <div class="footer">  {t5} <a href="https://github.com/kraynux/omega-serv">OMEGA-SERV</a></div>\n'
        "    </div>\n"
        "</body>\n"
        "</html>\n"
        ),
        (
            N_('404 - Page non trouvée'),
            N_('✖   Page non trouvée'),
            N_("La ressource demandée n'existe pas ou a été déplacée"),
            N_("Vérifier l'adresse url dans la barre d'adresse."),
            N_("← Retour à l'index"),
            N_('⚡ propulsé par'),
        ),
    ),
    429: (
        (
        "<!DOCTYPE html>\n"
        '<html lang="{lang}" dir="{dir}">\n'
        "<head>\n"
        '    <meta charset="UTF-8">\n'
        "    <title>{t0}</title>\n"
        '    \t<link rel="icon" type="image/png" href="/favicon-96x96.png" sizes="96x96" />\n'
        '\t<link rel="icon" type="image/svg+xml" href="/favicon.svg" />\n'
        '\t<link rel="shortcut icon" href="/favicon.ico" />\n'
        '\t<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />\n'
        '\t<meta name="apple-mobile-web-app-title" content="Omega" />\n'
        '    <link rel="stylesheet" href="/.omega-serv-error-css/error-pages.css">\n'
        "</head>\n"
        "<body>\n"
        '    <div class="container theme-yellow">\n'
        '        <div class="code">429</div>\n'
        '        <div class="title">{t1}</div>\n'
        '        <div class="msg">{t2}</div>\n'
        '        <div class="warning">\n'
        "             \t        {t3}<br>\n"
        "            {t4}\n"
        "        </div>\n"
        "        <hr>\n"
        '        <a href="/">{t5}</a>\n'
        '        <div class="footer">  {t6} <a href="https://github.com/kraynux/omega-serv">OMEGA-SERV</a></div>\n'
        "    </div>\n"
        "</body>\n"
        "</html>\n"
        ),
        (
            N_('429 - Limite de requêtes'),
            N_('⛔ Accès limité'),
            N_('Le serveur a détecté un nombre élevé de requêtes.'),
            N_('Blocage temporaire.'),
            N_('Attendez un peu avant de recharger ou de naviguer.'),
            N_("← Retour à l'index"),
            N_('⚡ propulsé par'),
        ),
    ),
    451: (
        (
        "<!DOCTYPE html>\n"
        '<html lang="{lang}" dir="{dir}">\n'
        "<head>\n"
        '    <meta charset="UTF-8">\n'
        '    <link rel="icon" type="image/png" href="/favicon-96x96.png" sizes="96x96" />\n'
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg" />\n'
        '<link rel="shortcut icon" href="/favicon.ico" />\n'
        '<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />\n'
        '<meta name="apple-mobile-web-app-title" content="Omega" />\n'
        "    <title>{t0}</title>\n"
        '    <link rel="stylesheet" href="/.omega-serv-error-css/error-pages.css">\n'
        "</head>\n"
        "<body>\n"
        '    <div class="container">\n'
        '        <div class="code">451</div>\n'
        "\n"
        '        <div class="title">{t1}</div>\n'
        '        <p class="msg">{t2}</p>\n'
        "\n"
        '        <p class="warning">{t3}</p> <hr>\n'
        '        <p class="msg"><a href="https://www.google.com">{t4}</a></p>\n'
        '        <div class="footer">{t5} <a href="https://github.com/kraynux/omega-serv">OMEGA-SERV</a></div>\n'
        "    </div>\n"
        "</body>\n"
        "</html>\n"
        ),
        (
            N_('451 - Accès interdit'),
            N_('🕱 Votre IP a été bannie'),
            N_('Durée entre 1 minute et 1 année selon le type de requête que vous avez effectué !'),
            N_("● Si vous pensez qu'il s'agit d'une erreur, contactez l'administrateur du site"),
            N_('← Retourner sur Google en attendant :-) '),
            N_('⚡ propulsé par'),
        ),
    ),
}


def _curated_page(status: int) -> bytes | None:
    """Pages integrees, construites a chaque appel dans la langue des pages visiteurs (D19) :
    textes passes par P_() et echappes pour le HTML (une traduction contenant < ou & ne casse
    jamais la page), attribut lang= dans la meme langue."""
    entry = _CURATED_TEMPLATES.get(status)
    if entry is None:
        return None
    template, texts = entry
    values = {f"t{i}": escape(P_(text), quote=False) for i, text in enumerate(texts)}
    return template.format(lang=page_html_lang(), dir=page_html_dir(), **values).encode()


def render_default_error_page(status: int) -> bytes:
    curated = _curated_page(status)
    if curated is not None:
        return curated
    reason = reason_phrase_for(status) or P_("Erreur")
    title = escape(f"{status} {reason}")
    return (
        f"<!doctype html><html lang=\"{page_html_lang()}\" dir=\"{page_html_dir()}\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title>"
        "<style>"
        "body{font-family:ui-monospace,Consolas,monospace;background:#0a0e1a;"
        "color:#e0e0e0;display:flex;align-items:center;justify-content:center;"
        "height:100vh;margin:0}"
        ".box{text-align:center}"
        "h1{font-size:2.5rem;margin:0 0 .5rem;color:#00d4ff}"
        "p{color:#b4c2e0;margin:0}"
        "</style></head><body><div class=\"box\">"
        f"<h1>{status}</h1><p>{escape(reason)}</p>"
        "</div></body></html>"
    ).encode()

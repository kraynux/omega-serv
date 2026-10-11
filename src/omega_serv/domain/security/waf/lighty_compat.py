"""Compatibilite du pont `lighty.*` expose aux scripts WAF magnet
importes (OMEGA-SERV_ETUDE_INCLUDE_ET_MAGNET_LUA.md, revision "import
d'un WAF externe, pas une implementation de plus"). Fonctions pures
uniquement - aucune execution Lua ici (ca, c'est infrastructure/waf/
lua_waf_adapter.py).

Liste de reference etablie a partir d'un VRAI script `mod_magnet`
fourni par l'utilisateur (non generique, mais le seul terrain verifie
dont on dispose) - jamais une liste inventee depuis la documentation
Lighttpd seule. Toute cle non listee ici reste `nil` cote Lua : un
script qui l'utilise degrade (souvent via son propre fallback `or`,
deja une pratique courante dans les scripts mod_magnet bien ecrits),
jamais un crash cote omega-serv (voir magnet_fallback_decision)."""
from __future__ import annotations

import re

SUPPORTED_LIGHTY_MEMBERS: frozenset[str] = frozenset({"env", "header", "content", "stat"})
"""Membres de `lighty.*` reellement branches par LuaWafAdapter. `header`/
`content` sont acceptes en ecriture mais jamais relus (OMEGA-SERV_WAF_
LUA_DEPERSONNALISATION.md, decision a retenir #12 : "les reponses
d'erreur sont rendues par le serveur, jamais par le moteur WAF") - un
script peut les ecrire sans planter, leur contenu est simplement
ignore."""

SUPPORTED_ENV_KEYS: frozenset[str] = frozenset({
    "request.remote-addr",
    "request.remote-ip",
    "request.method",
    "request.uri",
    "uri.path",
    "uri.query",
    "request.user-agent",
    "request.body",
})
"""Cles de `lighty.env` alimentees avec de VRAIES donnees de la requete.
Deliberement absentes (toujours nil) :
- "request.body-path" : omega-serv capture le corps en memoire, jamais
  dans un fichier temporaire - un script qui lit "request.body" en
  repli (comme le script de reference) fonctionne quand meme.
- "physical.path" : pas encore resolu a l'etape WAF (avant le routage/
  la resolution de fichier statique) - sans impact sur la decision de
  blocage du script de reference (utilise uniquement pour un message
  informatif), mais a verifier au cas par cas pour un autre script."""

_LIGHTY_MEMBER_RE = re.compile(r"\blighty\.(\w+)")


def scan_lighty_member_references(source: str) -> frozenset[str]:
    """Scan STATIQUE, heuristique - trouve chaque acces direct
    `lighty.X` dans le texte du script. Ne detecte pas un acces fait
    via une variable deja alias (ex. `local e = lighty.env` puis
    `e[...]` plus loin) - sous-estime donc parfois l'usage reel, jamais
    une preuve absolue d'incompatibilite ou de compatibilite. Le smoke
    test dynamique (infrastructure/waf/lua_waf_adapter.py::dry_run)
    reste la verification qui compte vraiment."""
    return frozenset(_LIGHTY_MEMBER_RE.findall(source))


def unsupported_lighty_members(source: str) -> frozenset[str]:
    return scan_lighty_member_references(source) - SUPPORTED_LIGHTY_MEMBERS

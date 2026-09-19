"""Leurre `fake_cms` (plan_active_defense_omega_serv.md, §"Honeypots
V1"/Phase 5) - fixture STATIQUE et deterministe, Niveau 1 (in-process,
isolation faible assumee, voir "Routage vers les leurres"). Simule un
CMS minimal (page de connexion + liste de plugins factices) - ne lit
jamais de fichier reel, n'execute jamais de commande, ne verifie jamais
reellement des identifiants soumis."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus

_LOGIN_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head><title>Connexion</title></head>
<body>
<h1>Connexion</h1>
<form method="post" action="/wp-login.php">
  <label>Identifiant <input type="text" name="log"></label>
  <label>Mot de passe <input type="password" name="pwd"></label>
  <button type="submit">Se connecter</button>
</form>
{message}
</body>
</html>
"""

_ADMIN_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head><title>Tableau de bord</title></head>
<body>
<h1>Tableau de bord</h1>
<ul>
  <li>Plugin-Cache 1.4.2</li>
  <li>Plugin-Formulaires 3.0.1</li>
  <li>Plugin-SEO 2.7.0</li>
</ul>
</body>
</html>
"""


def handle_fake_cms(request: HttpRequest) -> HttpResponse:
    """Toujours 200 pour `/wp-login.php`/`/wp-admin` (jamais une
    redirection ni un vrai succes) : un POST sur la connexion affiche
    simplement un message d'echec generique. Tout autre chemin (faux
    assets scannes) recoit un 404 plausible mais statique."""
    if request.path.startswith("/wp-admin"):
        body = _ADMIN_PAGE.encode("utf-8")
    else:
        message = '<p style="color:red">Identifiants invalides.</p>' if request.method == "POST" else ""
        body = _LOGIN_PAGE.format(message=message).encode("utf-8")
    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", "text/html; charset=utf-8")
    response.set_header("Content-Length", str(len(body)))
    response.body = body
    return response

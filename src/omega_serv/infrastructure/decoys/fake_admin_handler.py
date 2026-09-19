"""Leurre `fake_admin` (plan_active_defense_omega_serv.md, §"Honeypots
V1") - fixture STATIQUE et deterministe, Niveau 1 (in-process, isolation
faible assumee, voir "Routage vers les leurres"). Ne lit jamais de
fichier reel, n'execute jamais de commande ni de requete SQL, ne
verifie jamais reellement des identifiants soumis - un POST recoit
toujours le meme message d'echec, quel que soit son contenu."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus

_LOGIN_FORM = """<!DOCTYPE html>
<html lang="fr">
<head><title>Administration</title></head>
<body>
<h1>Connexion administrateur</h1>
<form method="post" action="/admin">
  <label>Identifiant <input type="text" name="username"></label>
  <label>Mot de passe <input type="password" name="password"></label>
  <button type="submit">Se connecter</button>
</form>
{message}
</body>
</html>
"""


def handle_fake_admin(request: HttpRequest) -> HttpResponse:
    """Toujours 200 (jamais une redirection ni un vrai succes) : un POST
    affiche simplement un message d'echec generique, sans jamais
    inspecter `request.body` au-dela de sa capture pour le journal
    (deja faite en amont par Active Defense, pas ici)."""
    message = '<p style="color:red">Identifiants invalides.</p>' if request.method == "POST" else ""
    body = _LOGIN_FORM.format(message=message).encode("utf-8")
    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", "text/html; charset=utf-8")
    response.set_header("Content-Length", str(len(body)))
    response.body = body
    return response

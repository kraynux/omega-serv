"""Scenarios prets a charger (topo §6.5, OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.4, lot 3).

Donnees pures, comme le catalogue omega-jail ou les packs WAF : charger un scenario = pre-remplir le
formulaire de politique ; tout reste modifiable, et la politique enregistree ne garde qu'une trace de son
origine (`origin = "scenario:<id>"`). Ajouter un scenario = ajouter une entree ici, jamais du code.

Tous les scenarios restent dans les bornes « prudentes » (paliers globaux, IP seule, jamais le niveau
« suspicious », ban local seulement) : un scenario charge tel quel ne demande aucune confirmation de
risque. Le ban reseau (omega-jail) s'ajoute a la main dans le formulaire."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.core.i18n import _
from omega_serv.domain.security.riposte.config import DAY, RipostePolicy


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    for_whom: str
    what_it_does: str
    what_it_does_not: str
    policy: RipostePolicy


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="scan-recidive",
        name=_("Scanner récidiviste"),
        for_whom=_("Un site exposé qui voit revenir les mêmes robots d'exploration."),
        what_it_does=_("Au 3e épisode de scan d'une même IP en 7 jours, ban local de plus en plus long "
                       "(paliers : 1 h, 6 h, 24 h, 7 j)."),
        what_it_does_not=_("Ne réagit jamais à un premier passage : le WAF et son ban automatique s'en chargent."),
        policy=RipostePolicy(
            id="scan-recidive", name=_("Scanner récidiviste"), origin="scenario:scan-recidive",
            attack_classes=("scan",), returns=3, within_seconds=7 * DAY, action="local_ban",
        ),
    ),
    Scenario(
        id="force-brute",
        name=_("Force brute"),
        for_whom=_("Un site avec une page de connexion ou une zone protégée."),
        what_it_does=_("Au 2e épisode d'essais d'identifiants d'une même IP en 24 h, ban local progressif."),
        what_it_does_not=_("Ne voit que ce que le WAF classe en essais d'identifiants : les erreurs 401 seules "
                           "restent pour la jail omega-jail « auth-bruteforce »."),
        policy=RipostePolicy(
            id="force-brute", name=_("Force brute"), origin="scenario:force-brute",
            attack_classes=("credential_stuffing",), returns=2, within_seconds=DAY, action="local_ban",
        ),
    ),
    Scenario(
        id="injections-repetees",
        name=_("Injections répétées"),
        for_whom=_("Tout site : une injection (SQL, XSS, commandes) ou une traversée de chemin n'est jamais un accident."),
        what_it_does=_("Dès le 2e épisode d'injection d'une même IP en 24 h, ban local progressif."),
        what_it_does_not=_("Pas de ban réseau par défaut : l'ajouter dans le formulaire si omega-jail est installé."),
        policy=RipostePolicy(
            id="injections-repetees", name=_("Injections répétées"), origin="scenario:injections-repetees",
            attack_classes=("sqli", "xss", "path_traversal", "command_injection"), returns=2, within_seconds=DAY, action="local_ban",
        ),
    ),
    Scenario(
        id="explorateur-leurres",
        name=_("Explorateur de leurres"),
        for_whom=_("Un site qui utilise les leurres d'Active Defense."),
        what_it_does=_("Une IP qui a déjà visité 2 leurres pendant un épisode y reste 24 h."),
        what_it_does_not=_("Ne bannit pas : la source continue de voir le leurre, pas le vrai site."),
        policy=RipostePolicy(
            id="explorateur-leurres", name=_("Explorateur de leurres"), origin="scenario:explorateur-leurres",
            decoy_hits=2, returns=1, within_seconds=DAY, action="decoy", decoy_profile="fake_admin",
            decoy_duration_seconds=DAY,
        ),
    ),
    Scenario(
        id="sonde-upload-api",
        name=_("Sonde upload / API"),
        for_whom=_("Un site avec une API ou un envoi de fichiers."),
        what_it_does=_("Une IP qui sonde l'envoi de fichiers ou l'API est envoyée 24 h vers le leurre « fake_api »."),
        what_it_does_not=_("Ne bannit pas ; exige le profil de leurre « fake_api » activé dans Active Defense."),
        policy=RipostePolicy(
            id="sonde-upload-api", name=_("Sonde upload / API"), origin="scenario:sonde-upload-api",
            attack_classes=("upload_probe", "api_probe"), returns=1, within_seconds=DAY, action="decoy",
            decoy_profile="fake_api", decoy_duration_seconds=DAY,
        ),
    ),
)


def find_scenario(scenario_id: str) -> Scenario | None:
    return next((s for s in SCENARIOS if s.id == scenario_id), None)

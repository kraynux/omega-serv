"""Widget LogLibraryTable - table reutilisable pour afficher une liste
de `LogFile` (gestion des logs, refonte menu 2026-10-15) - meme
representation partout (Bibliotheque/Favoris/Voir les logs/Voir et
traiter IP), jamais une table reinventee par ecran."""
from __future__ import annotations

from typing import Any

from textual.widgets import DataTable

from omega_serv.core.i18n import _
from omega_serv.domain.logs.library import LogFile


class LogLibraryTable(DataTable):
    """Table Chemin/Service/Acces/Taille/Modifie/Etat pour une liste de
    LogFile. `Modifie` (retour utilisateur 2026-10-15, source distante
    SSH) : pour un log recupere via scp (access="ssh"), ce n'est PAS une
    consultation live - c'est une copie figee au moment du dernier clic
    sur "Recuperer maintenant" (`scp` sans `-p` fixe la date de
    modification du fichier local au moment de la copie, jamais celle du
    fichier distant - c'est volontaire : on veut savoir QUAND on a
    recupere notre propre copie, pas quand le fichier distant a ete
    ecrit sur son serveur). Affiche aussi pour un log local ordinaire
    (utile pour voir en un coup d'oeil si un service a cesse d'ecrire)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "row"

    def on_mount(self) -> None:
        self.add_columns(_("Chemin"), _("Service"), _("Accès"), _("Taille"), _("Modifié"), _("État"))

    def load(self, log_files: list[LogFile]) -> None:
        """Remplace le contenu de la table par `log_files`. Pas de `key=`
        explicite sur `add_row` : un meme chemin pourrait en theorie
        apparaitre deux fois dans une future extension (ex. corrige par
        un futur Registre), un `key` duplique leverait `DuplicateKey` et
        interromprait le chargement en plein milieu - laisser Textual
        generer ses propres cles internes evite cette collision."""
        self.clear()
        for log_file in log_files:
            size = f"{log_file.size_bytes} o" if log_file.size_bytes is not None else "?"
            modified = log_file.modified_at.strftime("%Y-%m-%d %H:%M") if log_file.modified_at else "-"
            state = _("SUSPECT (vide)") if log_file.is_stale else (_("ABSENT") if not log_file.exists else "OK")
            self.add_row(log_file.path, log_file.service_id or "-", log_file.access, size, modified, state)

"""Garde-fou « jamais de mélange des genres » (plan moteur C++ §16.5, exigence utilisateur 2026-11-02) : un
réglage enregistré depuis un autre écran (TLS, reverse proxy, FastCGI, envoi de fichiers...) qui empêcherait le
moteur natif DEMANDÉ de tourner n'est jamais enregistré en silence. Fenêtre de confirmation explicite : la cause,
et la conséquence (moteur Python au prochain redémarrage). Même décideur que le démarrage (`decide_engine`)."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from omega_serv.application.server.engine_selection import decide_engine, describe_reason
from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.interfaces.tui.screens._base import OmegaScreen


def native_loss_reasons(previous: OmegaServConfig, new: OmegaServConfig, binary_problem: str | None) -> tuple[str, ...]:
    """Raisons pour lesquelles `new` ferait perdre le moteur natif que `previous` permettait (vide sinon)."""
    if new.server.engine != "native":
        return ()
    if decide_engine(previous, binary_problem).effective != "native":
        return ()  # deja en repli : rien de neuf a signaler ici (ecran Etat, Configuration de base)
    after = decide_engine(new, binary_problem)
    return () if after.effective == "native" else after.reasons


def save_guarded(
    screen: OmegaScreen, container: DependencyContainer, previous: OmegaServConfig, new: OmegaServConfig,
    after_save: Callable[[], None],
) -> None:
    """Enregistre `new` puis appelle `after_save` ; si le natif demandé ne pourrait plus tourner, demande d'abord."""
    def save() -> None:
        container.configuration.save(container.config_file, new)
        after_save()

    reasons = native_loss_reasons(previous, new, container.native_binary_problem())
    if not reasons:
        save()
        return
    message = _(
        "Avec ce réglage, le moteur natif ne peut pas être utilisé :\n{reasons}\n\nAu prochain redémarrage, le "
        "serveur tournera sur le moteur Python. Enregistrer quand même ?"
    ).format(reasons="\n".join(f"  - {describe_reason(code)}" for code in reasons))

    def answered(confirmed: bool | None) -> None:
        if confirmed:
            save()

    screen.app.push_screen(ConfirmScreen(title=_("MOTEUR NATIF"), message=message), answered)

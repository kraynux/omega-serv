"""Export HTML hors du fil de l'interface. Quand la langue des exports
(Options) differe de celle de l'interface, le contenu est produit par un
processus enfant lance dans cette langue (`container.export_*_html`) :
quelques secondes, d'ou le worker - l'interface reste utilisable et
l'utilisateur est prevenu que l'export est en cours."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from omega_serv.core.i18n import _

if TYPE_CHECKING:
    from textual.screen import Screen

    from omega_serv.bootstrap.container import DependencyContainer


def run_html_export(
    screen: Screen,
    container: DependencyContainer,
    produce: Callable[[], str | None],
    on_content: Callable[[str], None],
    on_failure: Callable[[str], None],
) -> None:
    language_name = container.export_language_name
    if language_name is not None:
        screen.app.notify(_("Export en cours dans la langue « {name} »…").format(name=language_name))

    def work() -> None:
        content = produce()
        if content is not None:
            screen.app.call_from_thread(on_content, content)
            return
        reason = container.last_export_error or _("Export HTML indisponible dans cet environnement.")
        screen.app.call_from_thread(on_failure, reason)

    screen.run_worker(work, thread=True, group="html-export")

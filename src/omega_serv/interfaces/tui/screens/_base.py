# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Classe de base partagee par tous les ecrans navigables (retour clavier).
Portee verbatim depuis omega-check (plan interface §0/§3.1), a l'exception
de `_maybe_suspend` (ajoute en Phase II §3.6, generalise en Phase V
§3.4 : deuxieme besoin reel confirme - service_screen.py pour
sudo, lnav_screen.py pour rendre la main au vrai terminal - D-008) et de
`action_show_help` (plan guide d'aide §3.5, 2026-09-14 - SPECIFIQUE A
SERV, jamais a reporter verbatim vers les autres outils de la suite :
depend de `SCREEN_GUIDES`, concept propre a ce projet)."""
from __future__ import annotations

import termios
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, ClassVar

from textual.app import SuspendNotSupported
from textual.binding import Binding, BindingType
from textual.screen import Screen

if TYPE_CHECKING:
    from textual.app import App


_INPUT_THREAD_JOIN_TIMEOUT_SECONDS = 1.0
"""Preuve concrete (bug reel "sudo authentification systematiquement
refusee", capture de processus - /proc/<pid>/task/*/comm au moment
exact ou sudo demarre) : le thread interne de Textual qui lit le
clavier en continu (`LinuxDriver._key_thread`, nomme "textual-input")
reste VIVANT et SELECTIONNE ENCORE SUR LE MEME TTY apres que
`App.suspend()` (donc `_driver.suspend_application_mode()` ->
`stop_application_mode()` -> `disable_input()`) soit deja revenu -
`disable_input()` avale silencieusement toute exception
(`except Exception: pass`, textual/drivers/linux_driver.py) qui
surviendrait avant `self._key_thread.join()`, laissant alors l'ancien
thread tourner indefiniment SANS que l'appelant (nous) ne puisse le
savoir. Consequence directe et intégralement reproduite : ce thread ET
sudo lisent alors CONCURREMMENT les memes frappes clavier sur le meme
tty - le mot de passe tape est disperse entre les deux lecteurs (sudo
n'en recoit jamais une version complete/coherente, d'ou "conversation
failed"/"jeton d'authentification" cote PAM), et les frappes captees
par le thread Textual s'accumulent dans sa file de messages (le thread
principal etant bloque, lui, dans le `subprocess.run()` de sudo) pour
etre rejouees d'un coup au reveil - exactement le texte qui
"s'incruste dans l'ecran" rapporte."""


def _ensure_terminal_truly_released(app: App[None]) -> None:
    """Repli defensif AJOUTE PAR-DESSUS `App.suspend()` (jamais un
    correctif dans Textual lui-meme, hors de portee ici) : verifie/attend
    reellement que le thread d'entree du pilote soit mort avant de
    rendre la main a l'appelant (qui va lancer une commande interactive
    - sudo - sur ce meme terminal). `getattr` partout : purement
    best-effort, silencieux sur tout driver/version ou ces attributs
    prives n'existeraient pas (jamais une nouvelle dependance dure sur
    l'implementation interne de Textual)."""
    driver = getattr(app, "_driver", None)
    if driver is None:
        return
    key_thread = getattr(driver, "_key_thread", None)
    if key_thread is not None and key_thread.is_alive():
        # Ne PAS se contenter d'attendre (`join()` seul) : preuve
        # concrete (deuxieme capture, apres un premier essai de ce
        # correctif limite a un join passif) que le thread reste vivant
        # BIEN AU-DELA du timeout - `disable_input()` (linux_driver.py)
        # a du avaler une exception AVANT d'atteindre
        # `self.exit_event.set()`, le thread ne verra alors JAMAIS le
        # signal d'arret peu importe combien de temps on patiente.
        # Positionner `exit_event` nous-memes est idempotent (aucun
        # effet si Textual l'avait deja fait correctement) et garantit
        # que le thread sort de sa boucle `while not exit_event.is_set()`
        # (run_input_thread) au prochain `selector.select(0.1)`.
        exit_event = getattr(driver, "exit_event", None)
        if exit_event is not None:
            exit_event.set()
        key_thread.join(timeout=_INPUT_THREAD_JOIN_TIMEOUT_SECONDS)
        # CRITIQUE : `start_application_mode()` (linux_driver.py) demarre
        # un nouveau `_key_thread` SANS jamais re-verifier/reinitialiser
        # `exit_event` - le laisser positionne casserait TOUTE saisie
        # clavier au prochain reveil (la boucle `while not
        # exit_event.is_set()` du nouveau thread serait fausse des le
        # depart, le thread ressortirait aussitot sans jamais rien lire).
        # Meme remise a zero que fait `disable_input()` apres son propre
        # join reussi - on la reproduit ici puisqu'on vient d'agir a sa
        # place.
        if exit_event is not None:
            exit_event.clear()
    writer_thread = getattr(driver, "_writer_thread", None)
    if writer_thread is not None and writer_thread.is_alive():
        stop = getattr(writer_thread, "stop", None)
        if callable(stop):
            stop()
        else:
            writer_thread.join(timeout=_INPUT_THREAD_JOIN_TIMEOUT_SECONDS)
    # Meme raison que disable_input() (linux_driver.py) : vide tout ce
    # qui a pu s'accumuler dans la file d'entree du tty PENDANT que le
    # thread ci-dessus tournait encore en concurrence avec nous - sans
    # ca, un reste de frappes "polluees" (deja lues en mode brut par
    # Textual) pourrait encore trainer au moment ou sudo commence sa
    # propre lecture.
    fileno = getattr(driver, "fileno", None)
    if isinstance(fileno, int):
        try:
            termios.tcflush(fileno, termios.TCIFLUSH)
        except OSError:
            pass


def show_contextual_help(app: App[None], screen_class_name: str) -> None:
    """Aide contextuelle (F1, plan guide d'aide §3.5) - fonction libre
    plutot qu'une seule methode sur `OmegaScreen` : `HomeScreen` (racine
    de la pile, n'herite pas de `OmegaScreen` - `echap` y demande une
    confirmation de sortie plutot qu'un dismiss()) a le meme besoin
    reel, jamais une seconde logique divergente pour ce cas."""
    # Imports differes : evite un import circulaire (guide_detail_screen.py
    # et help_screen.py heritent tous deux de OmegaScreen, defini ici meme).
    from omega_serv.interfaces.tui.guide.registry import SCREEN_GUIDES
    from omega_serv.interfaces.tui.screens.guide_detail_screen import GuideDetailScreen
    from omega_serv.interfaces.tui.screens.help_screen import HelpScreen

    guide = SCREEN_GUIDES.get(screen_class_name)
    if guide is not None:
        app.push_screen(GuideDetailScreen(guide))
    else:
        # Pas encore documente (deploiement progressif, plan guide
        # d'aide §5) - jamais un ecran vide ou une exception, on
        # retombe sur la reference statique generale.
        app.push_screen(HelpScreen())


class OmegaScreen(Screen[None]):
    """Ecran navigable standard : ajoute `echap` -> retour, sans qu'aucun
    ecran n'ait a redeclarer son propre binding. `home.py` et
    `quit_confirm.py` n'en heritent pas (voir leurs propres fichiers)."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back", "Retour", show=True),
        Binding("up", "focus_previous_item", "Monter", show=False),
        Binding("down", "focus_next_item", "Descendre", show=False),
        Binding("f1", "show_help", "Aide de cet ecran", show=True),
    ]

    def action_back(self) -> None:
        self.dismiss()

    def action_focus_previous_item(self) -> None:
        self.focus_previous()

    def action_focus_next_item(self) -> None:
        self.focus_next()

    def action_show_help(self) -> None:
        show_contextual_help(self.app, type(self).__name__)

    @contextmanager
    def _maybe_suspend(self) -> Iterator[None]:
        # `App.suspend()` echoue avec SuspendNotSupported dans certains
        # environnements (pilote de test headless, Textual Web...) - la
        # commande interactive/privilegiee reste tentee quand meme
        # plutot que de planter l'ecran : sans suspension, le rendu
        # eventuel s'affichera deteriore, mais l'action aboutit.
        #
        # Retour utilisateur (audit "gel d'ecran") : ce repli reste
        # imparfait pour une commande sudo reelle (service_screen.py) -
        # sans terminal pour afficher/saisir le mot de passe, une
        # commande privilegiee (deliberement SANS timeout, voir
        # systemd_service_manager.py::_run_privileged) pourrait s'y
        # bloquer indefiniment. Correctif tente puis REVERTE ici (produire
        # un booleen pour que service_screen.py refuse l'action) : le
        # SEUL signal disponible a ce niveau ("suspend a echoue") est
        # aussi vrai en environnement de test headless avec un manager
        # FACTICE qui n'appelle jamais reellement sudo - refuser sur ce
        # seul signal cassait alors les tests existants (manager.calls
        # jamais rempli) sans jamais avoir ete un vrai probleme dans ce
        # cas precis. Corriger correctement exigerait de faire remonter
        # un signal distinct depuis ServiceManagerPort lui-meme ("cette
        # action va reellement invoquer sudo de facon interactive"),
        # hors perimetre d'un correctif ponctuel - laisse tel quel,
        # documente comme limitation connue plutot que "corrige" a moitie.
        # Retour utilisateur (bug reel, "sudo s'incruste dans l'ecran,
        # gele, notification d'erreur") : `App.suspend()` (textual/app.py)
        # n'entoure PAS son `yield` interne d'un try/finally - le code qui
        # restaure le terminal (`resume_application_mode()`) suit ce
        # `yield` en sequence normale, jamais dans un `finally`. Si le
        # bloc suspendu (ici : la commande sudo, potentiellement
        # n'importe quelle exception imprevue - OSError, etc. - pas
        # seulement les echecs metier deja convertis en ManageServiceResult
        # par manage_service.py) leve quoi que ce soit, cette exception
        # traverse le `with self.app.suspend():` SANS jamais atteindre le
        # code de restauration : le terminal reste dans l'etat suspendu
        # (mode cooked, hors ecran alternatif) alors que Textual continue
        # de croire tourner normalement - tout rendu ulterieur (y compris
        # la notification d'erreur affichant l'exception elle-meme)
        # s'affiche alors detériore/mélangé, exactement le symptome
        # rapporte. Capturee ICI, A L'INTERIEUR du bloc `with`, pour que
        # `app.suspend()` atteigne bien sa restauration avant que
        # l'exception ne soit repropagee.
        caught: BaseException | None = None
        try:
            with self.app.suspend():
                _ensure_terminal_truly_released(self.app)
                try:
                    yield
                except BaseException as exc:  # noqa: BLE001 - repropagee plus bas, jamais avalee
                    caught = exc
        except SuspendNotSupported:
            yield
            return
        if caught is not None:
            raise caught

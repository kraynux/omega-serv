"""Assistant de creation de regle WAF Custom (retour utilisateur
2026-09-14 : "il faut rajouter une indication pour l'utilisateur car
c'est flou... le but c'est qu'un utilisateur qui ne sait pas coder
puisse utiliser [cet ecran]"). Remplace le formulaire brut (regex +
scope a ecrire a la main, DynamicFormScreen generique) par un
questionnaire en langage clair pour les 4 scenarios les plus courants -
la regex reelle est CONSTRUITE par le code (`build_path_segment_pattern`/
`build_keyword_pattern`, domain/security/waf/rule_validation.py,
`re.escape` systematique : un caractere special tape sans le savoir
n'est jamais interprete comme une regex) a partir d'une valeur saisie EN
CLAIR. Un mode "Avance" reste disponible pour qui veut ecrire sa propre
regex/scope directement - jamais retire, seulement plus un choix
explicite qu'un point de depart impose a tout le monde."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from omega_serv.application.security.editable_list_file import KEYWORDS_DIR
from omega_serv.application.security.load_keyword_list import (
    ListLoadRequest,
    sanitize_list_file_name,
)
from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.keyword_list import tokens_from_text
from omega_serv.domain.security.waf.rule_validation import (
    build_keyword_pattern,
    build_path_segment_pattern,
)
from omega_serv.interfaces.tui.screens._waf_list_choices import (
    ANCHORS,
    BAN_DURATIONS,
    GRAVITY_LEVELS,
    KEYWORD_SCOPES,
    NEW_FILE,
    RECIDIVE_COUNTS,
    RECIDIVE_WINDOWS,
)
from omega_serv.interfaces.tui.screens.path_list_editor_screen import PathListEditorScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_DETECTION_TYPES: tuple[tuple[str, str], ...] = (
    (_("Un chemin précis visite (ex: /admin)"), "path_exact"),
    (_("Un mot-clé dans l'adresse ou les paramètres"), "keyword_url"),
    (_("Un mot-clé envoyé dans un formulaire (POST)"), "keyword_body"),
    (_("Un outil de scan connu (User-Agent)"), "user_agent"),
    (_("Avance : j'écris moi-même une expression régulière"), "advanced"),
)

_TYPE_HINTS: dict[str, str] = {
    "path_exact": (
        _("Tapez le chemin SANS le '/' de tête. Exemple : 'admin' détecte /admin et /admin/xxx, "
        "mais jamais /administrator.")
    ),
    "keyword_url": (
        _("Tapez le mot recherche tel quel. Exemple : 'union select' - détecte ce mot n'importe où "
        "dans l'adresse ou les paramètres de la requête.")
    ),
    "keyword_body": (
        _("Tapez le mot recherche tel quel. Détecte ce mot dans les données envoyées par un "
        "formulaire (méthode POST).")
    ),
    "user_agent": (
        _("Tapez le nom de l'outil recherche tel quel. Exemple : 'sqlmap' - détecte les requêtes "
        "envoyées par cet outil.")
    ),
    "advanced": (
        _("Écrivez vous-même le motif (expression régulière Python) et la portée "
        "(path, query, body, headers, user_agent, referer - séparés par des virgules).")
    ),
}

# Chargement d'une LISTE (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md lot 6) -
# action explicite et distincte des 5 types "une regle" ci-dessus (A5).
_LIST_TYPES: tuple[tuple[str, str], ...] = (
    (_("CHARGER une liste de chemins (fichier)"), "list_path"),
    (_("CHARGER une liste de mots-clés (fichier)"), "list_keyword"),
)
_LIST_TYPE_HINTS: dict[str, str] = {
    "list_path": (
        _("Un chemin par ligne, '#' = commentaire. /admin -> /admin et /admin/xxx (jamais /administrator) ; "
        "/.git/ -> tout ce qui est sous /.git/ ; /*.bak -> fichiers finissant par .bak ; "
        "!/api/v1 -> exception, toujours prioritaire. Rien n'est actif avant d'avoir clique sur Charger.")
    ),
    "list_keyword": (
        _("Un mot-clé par ligne, recherche n'importe où dans la partie choisie de la requête (casse ignorée). "
        "Écrivez le texte tel quel, jamais une expression régulière.")
    ),
}
# Reglages proposes pour les references livrees (plan §3.3/§3.12, Q9).
_REFERENCE_PRESETS: dict[str, dict[str, str]] = {
    "sensitive-paths-hostile.txt": {
        "anchor": "any_segment", "weight": "6", "count": "2", "window": "600", "duration": "86400",
        "label": _("Chemins sensibles - bloquer"),
    },
    "sensitive-paths-probe.txt": {
        "anchor": "root", "weight": "3", "count": "5", "window": "600", "duration": "3600",
        "label": _("Chemins sensibles - surveiller"),
    },
}

_SEVERITY_LEVELS: tuple[tuple[str, str], ...] = (
    (_("Faible"), "1"),
    (_("Moyen"), "3"),
    (_("Élevé"), "6"),
    (_("Critique"), "9"),
)


class WafCustomRuleWizardScreen(ModalScreen[dict[str, Any] | None]):
    """Retourne un dict `{description, scope, pattern, weight}` (jamais
    `id` - genere par l'appelant, qui connait deja les regles
    existantes) pret a etre valide/ecrit tel quel par WafCustomRuleScreen,
    ou None si annule. Pour un type "CHARGER une liste" (seulement si un
    `container` est fourni : il faut lire les fichiers et pouvoir ouvrir
    l'editeur), retourne `{"kind": "keyword_list", "request": ListLoadRequest}`."""

    def __init__(self, container: DependencyContainer | None = None) -> None:
        super().__init__()
        self._container = container
        self._detection_types = _DETECTION_TYPES + (_LIST_TYPES if container is not None else ())
        self._preset_weight = "3"

    def compose(self) -> ComposeResult:
        with Center(), VerticalScroll(classes="omega-dynamic-form-box"):
            yield Static(_("AJOUTER UNE RÈGLE - ASSISTANT"), classes="omega-title")
            yield Static(
                _("Une règle repère un texte dans une partie de la requête (le chemin visite, "
                "un paramètre, le logiciel utilise...). Choisissez ci-dessous ce que vous voulez "
                "détecter - aucune connaissance des expressions régulières n'est nécessaire, sauf "
                "en mode Avance."),
                classes="omega-hint",
            )
            yield Static(_("Que voulez-vous détecter ?"), classes="omega-subtitle")
            yield Select(self._detection_types, value="path_exact", allow_blank=False, id="detection-type-select")
            yield Static(_TYPE_HINTS["path_exact"], id="type-hint", classes="omega-hint")

            yield Static(_("Valeur à détecter (mode simple)"), id="value-label", classes="omega-subtitle")
            yield Input(placeholder=_("ex: admin"), id="value-input")

            with Container(id="advanced-fields"):
                yield Static(_("Portée (path, query, body, headers, user_agent, referer - séparés par des virgules)"), classes="omega-subtitle")
                yield Input(value="path", id="scope-input")
                yield Static(_("Motif (expression régulière Python)"), classes="omega-subtitle")
                yield Input(id="pattern-input")

            with Container(id="list-fields"):
                yield Static(_("Fichier de liste"), classes="omega-subtitle")
                yield Select(self._file_options(), allow_blank=False, id="list-file-select")
                yield Input(placeholder=_("nom du nouveau fichier (ex: mes-chemins)"), id="list-new-name")
                yield Static(_("Où chercher"), id="list-anchor-label", classes="omega-subtitle")
                yield Select(ANCHORS, value="any_segment", allow_blank=False, id="list-anchor")
                yield Static(_("Dans quelle partie de la requête"), id="list-scope-label", classes="omega-subtitle")
                yield Select(KEYWORD_SCOPES, value="path,query", allow_blank=False, id="list-scope")
                yield Static(_("Gravité"), classes="omega-subtitle")
                yield Select(GRAVITY_LEVELS, value="observe", allow_blank=False, id="list-gravity")
                yield Static(_("Récidive : bannir après ... accès en ... pendant ..."), classes="omega-subtitle")
                yield Select(RECIDIVE_COUNTS, value="0", allow_blank=False, id="list-recidive-count")
                yield Select(RECIDIVE_WINDOWS, value="600", allow_blank=False, id="list-recidive-window")
                yield Select(BAN_DURATIONS, value="3600", allow_blank=False, id="list-recidive-duration")
                yield Static(_("Nom affiché"), classes="omega-subtitle")
                yield Input(placeholder=_("ex: Chemins sensibles - bloquer"), id="list-label")
                with Horizontal(classes="omega-confirm-buttons"), Container(classes="omega-btn-frame"):
                    yield Button(_("Ouvrir l'éditeur"), id="list-open-editor")

            yield Static(_("Description (facultatif)"), id="description-label", classes="omega-subtitle")
            yield Input(id="description-input")
            yield Static(_("Gravité"), id="severity-label", classes="omega-subtitle")
            yield Select(_SEVERITY_LEVELS, value="3", allow_blank=False, id="severity-select")

            with Horizontal(classes="omega-confirm-buttons"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ajouter"), id="confirm", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Annuler"), id="cancel")

    def on_mount(self) -> None:
        self._apply_mode("path_exact")

    # ---- fichiers de liste -------------------------------------------------
    def _file_options(self) -> list[tuple[str, str]]:
        """Fichiers .txt locaux (jamais les .example), references livrees pas
        encore copiees, puis "Nouveau fichier..."."""
        if self._container is None:
            return [(_("Nouveau fichier..."), NEW_FILE)]
        keywords_dir = self._container.project_root / KEYWORDS_DIR
        filesystem = self._container.filesystem
        local: list[str] = []
        if filesystem.is_dir(keywords_dir):
            local = sorted(n for n in filesystem.list_directory_entries(keywords_dir) if n.endswith(".txt"))
        options: list[tuple[str, str]] = []
        for name in local:
            count = len(tokens_from_text(filesystem.read_text(keywords_dir / name)))
            options.append((_("{name} ({count} entrées)").format(name=name, count=count), f"local:{name}"))
        for name in self._container.keyword_references.names():
            if name not in local:
                text = self._container.keyword_references.read(name) or ""
                options.append((_("{name} (référence livrée, {count} entrées)").format(name=name, count=len(tokens_from_text(text))), f"ref:{name}"))
        options.append((_("Nouveau fichier..."), NEW_FILE))
        return options

    def _selected_file(self) -> tuple[str | None, str | None]:
        """(nom du fichier local, reference a copier s'il n'existe pas encore)."""
        value = str(self.query_one("#list-file-select", Select).value)
        if value.startswith("local:"):
            name = value.removeprefix("local:")
            return name, name if name in _REFERENCE_PRESETS else None
        if value.startswith("ref:"):
            name = value.removeprefix("ref:")
            return name, name
        return sanitize_list_file_name(self.query_one("#list-new-name", Input).value), None

    def _apply_file_presets(self) -> None:
        name, _ = self._selected_file()
        is_new = str(self.query_one("#list-file-select", Select).value) == NEW_FILE
        self.query_one("#list-new-name", Input).display = is_new
        preset = _REFERENCE_PRESETS.get(name or "")
        if preset is None:
            return
        self.query_one("#list-anchor", Select).value = preset["anchor"]
        self.query_one("#list-gravity", Select).value = "observe"
        self.query_one("#list-recidive-count", Select).value = preset["count"]
        self.query_one("#list-recidive-window", Select).value = preset["window"]
        self.query_one("#list-recidive-duration", Select).value = preset["duration"]
        self.query_one("#list-label", Input).value = preset["label"]
        self._preset_weight = preset["weight"]

    def _apply_recidive_state(self) -> None:
        observe = str(self.query_one("#list-gravity", Select).value) == "observe"
        own_counter = str(self.query_one("#list-recidive-count", Select).value) != "0"
        self.query_one("#list-recidive-count", Select).disabled = observe
        for select_id in ("#list-recidive-window", "#list-recidive-duration"):
            self.query_one(select_id, Select).disabled = observe or not own_counter

    # ---- modes -------------------------------------------------------------
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "detection-type-select":
            self._apply_mode(str(event.value))
        elif event.select.id == "list-file-select":
            self._apply_file_presets()
            self._apply_recidive_state()
        elif event.select.id in ("list-gravity", "list-recidive-count"):
            self._apply_recidive_state()

    def _apply_mode(self, detection_type: str) -> None:
        is_list = detection_type in _LIST_TYPE_HINTS
        hint = _LIST_TYPE_HINTS[detection_type] if is_list else _TYPE_HINTS[detection_type]
        self.query_one("#type-hint", Static).update(hint)
        advanced = detection_type == "advanced"
        self.query_one("#advanced-fields", Container).display = advanced
        self.query_one("#value-label", Static).display = not advanced and not is_list
        self.query_one("#value-input", Input).display = not advanced and not is_list
        self.query_one("#list-fields", Container).display = is_list
        for widget_id in ("#description-label", "#description-input", "#severity-label", "#severity-select"):
            self.query_one(widget_id).display = not is_list
        if is_list:
            path_mode = detection_type == "list_path"
            self.query_one("#list-anchor-label", Static).display = path_mode
            self.query_one("#list-anchor", Select).display = path_mode
            self.query_one("#list-scope-label", Static).display = not path_mode
            self.query_one("#list-scope", Select).display = not path_mode
            self._apply_file_presets()
            self._apply_recidive_state()
        self.query_one("#confirm", Button).label = _("Charger") if is_list else _("Ajouter")

    # ---- actions -------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "list-open-editor":
            self._open_editor()
            return
        if event.button.id == "confirm":
            result = self._build_result()
            if result is not None:
                self.dismiss(result)

    def _open_editor(self) -> None:
        if self._container is None:
            return
        name, reference = self._selected_file()
        if name is None:
            self.app.notify(_("Donnez d'abord un nom au nouveau fichier."), severity="warning")
            return
        list_path = str(self.query_one("#detection-type-select", Select).value) == "list_path"
        self.app.push_screen(
            PathListEditorScreen(
                container=self._container, relative_path=f"{KEYWORDS_DIR}/{name}",
                anchor=str(self.query_one("#list-anchor", Select).value) if list_path else "any_segment",
                title=_("ÉDITION - {name}").format(name=name), reference_name=reference,
                match="path" if list_path else "substring",
            ),
            self._after_editor,
        )

    def _after_editor(self, _result: None) -> None:
        """Les nombres d'entrees affiches ont pu changer : on recharge la liste
        des fichiers en gardant la selection."""
        select = self.query_one("#list-file-select", Select)
        current = select.value
        options = self._file_options()
        select.set_options(options)
        name, _ = self._selected_file() if current != NEW_FILE else (None, None)
        values = [value for _, value in options]
        if current in values:
            select.value = current
        elif name is not None and f"local:{name}" in values:
            select.value = f"local:{name}"

    def _build_list_request(self, detection_type: str) -> ListLoadRequest | None:
        name, reference = self._selected_file()
        if name is None:
            self.app.notify(_("Nom de fichier manquant ou invalide (lettres, chiffres, '-')."), severity="error")
            return None
        gravity = str(self.query_one("#list-gravity", Select).value)
        observe = gravity == "observe"
        count = int(str(self.query_one("#list-recidive-count", Select).value))
        list_path = detection_type == "list_path"
        scope = ("path",) if list_path else tuple(str(self.query_one("#list-scope", Select).value).split(","))
        return ListLoadRequest(
            file_name=name,
            match="path" if list_path else "substring",
            scope=scope,
            anchor=str(self.query_one("#list-anchor", Select).value) if list_path else "any_segment",
            weight=int(self._preset_weight if observe else gravity),
            observe_only=observe,
            escalation_threshold=0 if observe else count,
            escalation_window_seconds=int(str(self.query_one("#list-recidive-window", Select).value)),
            auto_block_duration_seconds=(
                int(str(self.query_one("#list-recidive-duration", Select).value)) if count and not observe else None
            ),
            label=self.query_one("#list-label", Input).value.strip(),
            reference_name=reference,
        )

    def _build_result(self) -> dict[str, Any] | None:
        detection_type = str(self.query_one("#detection-type-select", Select).value)
        if detection_type in _LIST_TYPE_HINTS:
            request = self._build_list_request(detection_type)
            return None if request is None else {"kind": "keyword_list", "request": request}
        description = self.query_one("#description-input", Input).value.strip()
        weight = str(self.query_one("#severity-select", Select).value)

        if detection_type == "advanced":
            scope = self.query_one("#scope-input", Input).value
            pattern = self.query_one("#pattern-input", Input).value
        else:
            value = self.query_one("#value-input", Input).value
            if detection_type == "path_exact":
                scope, pattern = "path", build_path_segment_pattern(value)
            elif detection_type == "keyword_url":
                scope, pattern = "path,query", build_keyword_pattern(value)
            elif detection_type == "keyword_body":
                scope, pattern = "body", build_keyword_pattern(value)
            else:  # user_agent
                scope, pattern = "user_agent", build_keyword_pattern(value)

        return {
            "description": description, "scope": scope, "pattern": pattern,
            "weight": weight, "case_insensitive": "oui", "enabled": "oui",
        }

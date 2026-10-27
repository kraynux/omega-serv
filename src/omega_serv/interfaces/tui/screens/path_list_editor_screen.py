"""Editeur d'une liste de chemins (keyword_lists, match="path") -
OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.6, lots 4.2 a 4.6.

Branche l'editeur generique sur :
- le validateur UNIQUE (`analyze_path_list_text`) pour les diagnostics en
  direct - un texte en erreur ne peut jamais etre enregistre ;
- `explain_path` pour "Tester" (texte EN COURS, avant enregistrement) ;
- `save_list_file` (lot 3 : emplacement, liens symboliques, lecture seule,
  modification exterieure, droits conserves, lisibilite par le service) ;
- un rechargement HONNETE (§3.8) : validation d'environnement de la liste
  avant de declencher le SIGHUP, jamais "recharge" annonce a tort ;
- "Corriger les droits" (R4), "Verifier contre mes logs" (§3.10-4),
  "Nouveautes de la reference" (§3.11)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omega_serv.application.config.load_config import load_config
from omega_serv.application.security.editable_list_file import (
    ListFileStatus,
    apply_read_fixes,
    inspect_list_file,
    save_list_file,
)
from omega_serv.application.security.path_list_tools import (
    explain_path,
    reference_news,
    replay_successful_paths,
    retired_markers,
)
from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_account,
)
from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.keyword_list import (
    NEW_KEYWORD_LIST_TEMPLATE,
    NEW_PATH_LIST_TEMPLATE,
    analyze_path_list_text,
    tokens_from_text,
)
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.path_list_editor_dialogs import (
    LogHitAction,
    LogHitsScreen,
    ReferenceNewsScreen,
)
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required
from omega_serv.interfaces.tui.screens.text_file_editor_screen import (
    EditorAnalysis,
    EditorDiagnostic,
    TextFileEditorScreen,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

ACCESS_LOG_TAIL_BYTES = 20 * 1024 * 1024  # dernieres ~100 000 lignes d'un journal combine typique



class PathListEditorScreen(TextFileEditorScreen):
    def __init__(
        self,
        *,
        container: DependencyContainer,
        relative_path: str,
        anchor: str,
        title: str,
        reference_name: str | None = None,
        match: str = "path",
    ) -> None:
        """`match="substring"` : liste de MOTS-CLEFS (meme ecriture sure, meme
        rechargement honnete) - sans testeur de chemins, sans rejeu des logs,
        sans reference (ces outils n'ont de sens que pour des chemins)."""
        self._container = container
        self._match = match
        self._relative_path = relative_path
        self._anchor = anchor
        self._reference_text = container.keyword_references.read(reference_name) if reference_name else None
        self._service_account = resolve_current_service_account(
            container.instance_registry, container.filesystem, container.settings_store,
            container.project_root, container.systemd_unit_dir,
        )
        self._status = self._inspect()
        self._path = container.project_root / relative_path
        text = self._initial_content()
        # Texte AFFICHE a l'ouverture (la reference au premier chargement) : c'est
        # par rapport a lui qu'une ligne supprimee est marquee `#retire:`.
        self._opened_text = text
        self._fingerprint = container.file_access.fingerprint(self._path) if self._status.location_error is None else None
        read_only = self._status.location_error or (
            None if self._status.writable else _("fichier ou dossier non modifiable par votre compte (jamais via sudo)")
        )
        super().__init__(title=title, text=text, read_only_reason=read_only)

    # ---- ouverture -----------------------------------------------------------
    def _inspect(self) -> ListFileStatus:
        return inspect_list_file(
            self._container.file_access, self._container.project_root, self._relative_path, self._service_account,
        )

    def _initial_content(self) -> str:
        if self._status.location_error is None and self._status.exists:
            return self._container.filesystem.read_text(self._path)
        if self._reference_text is not None:
            return self._reference_text  # premier chargement : copie de la reference (§3.11)
        return NEW_PATH_LIST_TEMPLATE if self._match == "path" else NEW_KEYWORD_LIST_TEMPLATE

    # ---- points d'extension --------------------------------------------------
    def analyze(self, text: str) -> EditorAnalysis:
        if self._match != "path":
            return EditorAnalysis(summary=_("{count} mot(s)-clef(s)").format(count=len(tokens_from_text(text))))
        analysis = analyze_path_list_text(text, self._anchor)
        summary = (
            _("{count} entrée(s) · {count2} exception(s) · {count3} erreur(s) · {count4} avertissement(s)").format(count=len(analysis.entries), count2=len(analysis.exceptions), count3=len(analysis.errors), count4=len(analysis.warnings))
        )
        return EditorAnalysis(
            summary=summary,
            diagnostics=tuple(EditorDiagnostic(d.line, d.severity, d.message) for d in analysis.diagnostics),
        )

    def supports_test(self) -> bool:
        return self._match == "path"

    def test_value(self, text: str, value: str) -> str:
        return explain_path(text, self._anchor, value)

    def extra_tools(self) -> tuple[tuple[str, str], ...]:
        tools = [("tool-check-logs", _("Vérifier contre mes logs"))] if self._match == "path" else []
        if self._reference_text is not None and self._match == "path":
            tools.append(("tool-reference-news", _("Nouveautés de la référence")))
        tools.append(("tool-fix-rights", _("Corriger les droits")))
        return tuple(tools)

    def status_text(self) -> str:
        message = self._status.service_message()
        if self._status.service_check == "unreadable":
            return _("ATTENTION : {message} - le serveur ne pourra pas charger cette liste (bouton Corriger les droits)").format(message=message)
        return message

    def handle_extra_tool(self, tool_id: str) -> None:
        if tool_id == "tool-check-logs":
            self._check_logs()
        elif tool_id == "tool-reference-news":
            self._reference_news()
        elif tool_id == "tool-fix-rights":
            self._fix_rights()

    # ---- enregistrement ----------------------------------------------------
    def save(self, text: str) -> tuple[bool, str]:
        markers = list(retired_markers(self._opened_text, text, self._reference_text)) if self._reference_text else []
        final_text = text if not markers else text + ("" if text.endswith("\n") else "\n") + "\n".join(markers) + "\n"
        result = save_list_file(
            self._container.file_access, self._container.project_root, self._relative_path,
            final_text, self._service_account, self._fingerprint,
        )
        self._status = result.status
        if not result.saved:
            return False, _("Enregistrement refusé : {refused_reason}").format(refused_reason=result.refused_reason)
        if markers:
            self.append_lines(markers)  # visible et annulable dans l'editeur, comme sur disque
        self._fingerprint = self._container.file_access.fingerprint(self._path)
        self._opened_text = final_text
        self.mark_saved(self.text_area.text)

        messages = [_("Liste enregistrée.")]
        if result.outcome is not None and not result.outcome.group_preserved:
            messages.append(_("Groupe d'origine du fichier non conservé (vous n'en êtes pas membre)."))
        if self._status.service_check == "unreadable":
            messages.append(_("ATTENTION : {value} (bouton Corriger les droits).").format(value=self._status.service_message()))
            return True, " ".join(messages)
        messages.append(self._apply_to_server())
        return True, " ".join(m for m in messages if m)

    def _referencing_list_ids(self, waf_settings: dict[str, Any]) -> list[str]:
        lists = waf_settings.get("rules", {}).get("keyword_lists", [])
        return [str(item.get("id")) for item in lists
                if item.get("file") == self._relative_path and item.get("enabled", True)]

    def _apply_to_server(self) -> str:
        """Ne declenche le rechargement QUE si la liste est chargee dans le WAF
        ET passe la validation d'environnement (§3.8)."""
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return _("Configuration illisible : aucun rechargement tenté.")
        config = load_result.config
        waf_option = config.options.get("waf")
        list_ids = self._referencing_list_ids(waf_option.settings) if waf_option is not None else []
        if not list_ids:
            return _("Cette liste n'est pas encore chargée dans le WAF (assistant WAF Custom).")
        runner = self._container.config_check_runner
        if runner is not None:
            errors = runner(config, self._container.filesystem, self._container.project_root, False, False)
            relevant = [e for e in errors if any(f"keyword_lists[{list_id!r}]" in e for list_id in list_ids)]
            if relevant:
                return _("Rechargement NON effectué : {value}").format(value=relevant[0])
        notify_reload_required(self, self._container, _("Liste {value} enregistrée.").format(value=', '.join(list_ids)))
        return ""

    # ---- outils --------------------------------------------------------------
    def _fix_rights(self) -> None:
        self._status = self._inspect()
        self.refresh_status()
        if self._status.service_check != "unreadable":
            self.notify_message(_("Rien à corriger : {value}.").format(value=self._status.service_message()))
            return
        if not self._status.fixes:
            blocked = ", ".join(node.path for node in self._status.not_fixable)
            self.notify_message(
                _("Correction impossible depuis votre compte (éléments qui ne vous appartiennent pas : {blocked}). Demandez à l'administrateur de la machine.").format(blocked=blocked), error=True,
            )
            return
        details = "\n".join(f"{fix.path} : {fix.current_mode:o} -> {fix.new_mode:o}" for fix in self._status.fixes)
        self.app.push_screen(
            ConfirmScreen(title=_("CORRIGER LES DROITS"), message=_("Appliquer ces changements de droits ?\n{details}").format(details=details)),
            self._apply_fixes_if_confirmed,
        )

    def _apply_fixes_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        apply_read_fixes(self._container.file_access, self._status.fixes)
        self._status = self._inspect()
        self.refresh_status()
        self.notify_message(_("Droits corrigés : {value}.").format(value=self._status.service_message()))

    def _check_logs(self) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.notify_message(_("Configuration illisible : journal d'accès introuvable."), error=True)
            return
        access_log = self._container.project_root / load_result.config.logs.access
        lines = self._container.file_access.read_tail_lines(access_log, ACCESS_LOG_TAIL_BYTES)
        if not lines:
            self.notify_message(_("Journal d'accès vide ou absent : {access_log}").format(access_log=access_log))
            return
        hits = replay_successful_paths(self.text_area.text, self._anchor, lines)
        if not hits:
            self.notify_message(_("Aucune ligne n'a touché de requête réussie ({count} lignes de journal analysées).").format(count=len(lines)))
            return
        self.app.push_screen(LogHitsScreen(hits, len(lines)), self._apply_log_hit_action)

    def _apply_log_hit_action(self, action: LogHitAction | None) -> None:
        if action is None:
            return
        kind, value = action
        if kind == "exception":
            self.append_lines([f"!{value}"])
        elif kind == "delete":
            self.delete_line(int(value))
        self.text_area.focus()

    def _reference_news(self) -> None:
        if self._reference_text is None:
            return
        news = reference_news(self.text_area.text, self._reference_text)
        if not news:
            self.notify_message(_("Aucune nouveauté : votre liste contient déjà toute la référence."))
            return
        self.app.push_screen(ReferenceNewsScreen(news), self._add_reference_news)

    def _add_reference_news(self, chosen: list[str] | None) -> None:
        if chosen:
            self.append_lines([_("#Ajouts depuis la référence"), *chosen])
        self.text_area.focus()

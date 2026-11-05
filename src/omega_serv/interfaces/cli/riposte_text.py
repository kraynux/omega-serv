"""Textes RIPOSTE pour l'humain (CLI, et TUI au lot 5) : le domaine ne produit que des codes
(domain/security/riposte/decide.py::Reason) ; les phrases, traduites, sont ici - un seul endroit."""
from __future__ import annotations

from omega_serv.application.riposte.get_status import RiposteStatus
from omega_serv.application.riposte.measure import MeasureResult
from omega_serv.core.i18n import _
from omega_serv.domain.security.riposte.config import RiposteConfig, RipostePolicy
from omega_serv.domain.security.riposte.decide import Decision, Reason
from omega_serv.domain.security.riposte.network_ban import jail_for, jail_name

_MINUTE = 60
_HOUR = 3600
_DAY = 86400


def format_duration(seconds: int) -> str:
    if seconds % _DAY == 0:
        return _("{n} j").format(n=seconds // _DAY)
    if seconds % _HOUR == 0:
        return _("{n} h").format(n=seconds // _HOUR)
    if seconds % _MINUTE == 0:
        return _("{n} min").format(n=seconds // _MINUTE)
    return _("{n} s").format(n=seconds)


def action_label(action: str | None) -> str:
    return {
        "local_ban": _("ban local (blocklist)"),
        "local_and_network_ban": _("ban local + ban réseau (omega-jail)"),
        "decoy": _("leurre"),
    }.get(action or "", action or "-")


def action_short_label(action: str | None) -> str:
    """Forme courte pour les colonnes de tableau."""
    return {
        "local_ban": _("ban local"),
        "local_and_network_ban": _("ban local + réseau"),
        "decoy": _("leurre"),
    }.get(action or "", action or "-")


def status_label(status: str) -> str:
    return {
        "matched": _("action décidée"),
        "rejected_by_safety": _("refusée par les garde-fous"),
        "stopped": _("arrêt d'urgence"),
        "observed": _("aucune action"),
    }.get(status, status)


def _p(reason: Reason, key: str) -> str:
    value = reason.param(key)
    return "-" if value is None else str(value)


def _d(reason: Reason, key: str) -> str:
    value = reason.param(key)
    return format_duration(value) if isinstance(value, int) else "-"


def format_reason(reason: Reason) -> str:
    code = reason.code
    if code == "event":
        return _("Événement : {kind} de {ip}").format(kind=_p(reason, "kind"), ip=_p(reason, "ip"))
    if code == "not_a_deciding_event":
        return _("Cet événement ne déclenche jamais de décision (refus de blocklist, limite de débit...).")
    if code == "emergency_stop":
        return _("Arrêt d'urgence actif : aucune nouvelle action.")
    if code == "exempt_network":
        return _("Source exclue : réseau {network} (exclusions du WAF ou de RIPOSTE).").format(network=_p(reason, "network"))
    if code == "exemptions_checked":
        return _("Exclusions vérifiées : {count} réseau(x), aucun ne correspond.").format(count=_p(reason, "count"))
    if code == "no_episode":
        return _("Aucun épisode en cours pour cette source.")
    if code == "already_acted_this_episode":
        return _("Une action a déjà été décidée pendant cet épisode (une seule par épisode).")
    if code == "policy_disabled":
        return _("Politique {policy} : désactivée.").format(policy=_p(reason, "policy"))
    if code == "unmet_returns":
        return _("Politique {policy} : {have} épisode(s) en {within}, il en faut {need}.").format(
            policy=_p(reason, "policy"), have=_p(reason, "have"), need=_p(reason, "need"),
            within=_d(reason, "within_seconds"))
    if code == "unmet_attack_class":
        return _("Politique {policy} : classes attendues {need}, vues {have}.").format(
            policy=_p(reason, "policy"), need=_p(reason, "need"), have=_p(reason, "have"))
    if code == "unmet_level":
        return _("Politique {policy} : niveau Active Defense attendu {need}, atteint {have}.").format(
            policy=_p(reason, "policy"), need=_p(reason, "need"), have=_p(reason, "have"))
    if code == "unmet_decoy_hits":
        return _("Politique {policy} : {have} visite(s) de leurre, il en faut {need}.").format(
            policy=_p(reason, "policy"), have=_p(reason, "have"), need=_p(reason, "need"))
    if code == "no_policy_matched":
        return _("Aucune politique ne correspond ({policies} examinée(s)).").format(policies=_p(reason, "policies"))
    if code == "policy_matched":
        return _("Politique retenue : {policy}.").format(policy=_p(reason, "policy"))
    if code == "source_already_has_action":
        return _("Refusée : la source a déjà {current} action(s) en cours (limite {limit}).").format(
            current=_p(reason, "current"), limit=_p(reason, "limit"))
    if code == "max_active_bans_reached":
        return _("Refusée : {current} bans RIPOSTE déjà en cours (limite {limit}).").format(
            current=_p(reason, "current"), limit=_p(reason, "limit"))
    if code == "tier":
        return _("Palier {index} sur {of} : {duration}.").format(
            index=_p(reason, "index"), of=_p(reason, "of"), duration=_d(reason, "duration"))
    if code == "decoy":
        return _("Leurre {profile} pendant {duration}.").format(profile=_p(reason, "profile"), duration=_d(reason, "duration"))
    return code


def format_decision(decision: Decision) -> list[str]:
    head = _("Décision : {status}").format(status=status_label(decision.status))
    if decision.status == "matched":
        head += " - " + _("{action} pendant {duration}").format(
            action=action_label(decision.action),
            duration=format_duration(decision.duration_seconds) if decision.duration_seconds else "-",
        )
    return [head, *("  - " + format_reason(r) for r in decision.reasons)]


def policy_lines(policy: RipostePolicy, config: RiposteConfig, service_name: str | None = None) -> list[str]:
    """Description d'une politique (CLI `policies show`, ecran Politiques)."""
    tiers = policy.tiers_seconds or config.tiers_seconds
    lines = [
        _("{id} - {name} ({state})").format(id=policy.id, name=policy.name,
                                            state=_("active") if policy.enabled else _("désactivée")),
        "  " + _("Quand : {returns} épisode(s) en {within}").format(
            returns=policy.returns, within=format_duration(policy.within_seconds)),
    ]
    if policy.attack_classes:
        lines.append("  " + _("Classes d'attaque : {classes}").format(classes=", ".join(policy.attack_classes)))
    if policy.min_ad_level:
        lines.append("  " + _("Niveau Active Defense minimal : {level}").format(level=policy.min_ad_level))
    if policy.decoy_hits:
        lines.append("  " + _("Visites de leurre minimales : {n}").format(n=policy.decoy_hits))
    lines.append("  " + _("Alors : {action}").format(action=action_label(policy.action)))
    if policy.action == "decoy":
        lines.append("  " + _("Leurre {profile} pendant {duration}").format(
            profile=policy.decoy_profile or "-", duration=format_duration(policy.decoy_duration_seconds)))
    else:
        lines.append("  " + _("Paliers : {tiers}").format(tiers=" / ".join(format_duration(t) for t in tiers)))
    if policy.action == "local_and_network_ban" and service_name:
        lines.append("  " + _("Ban réseau : {jails}").format(jails=network_jails_text(service_name, tiers)))
    return lines


def network_jails_text(service_name: str, tiers: tuple[int, ...]) -> str:
    """« palier 2 h -> jail omega-serv-riposte-1h » pour chaque palier (jails a duree fixe, decision 2026-11-02)."""
    return ", ".join(_("palier {tier} -> jail {jail}").format(tier=format_duration(t), jail=jail_name(service_name, t))
                     for t in tiers)


def network_ban_notice(service_name: str, duration_seconds: int) -> str:
    """Ce qu'une levee ne touche pas : le ban reseau (omega-serv n'a pas les droits sur fail2ban)."""
    return _("Ban réseau : jail {jail} ({duration}) - à lever dans omega-jail ou fail2ban, omega-serv n'en a pas "
             "les droits.").format(jail=jail_name(service_name, duration_seconds),
                                   duration=format_duration(jail_for(duration_seconds)[0]))


def format_measure(result: MeasureResult) -> list[str]:
    """Resultat de « Mesurer » (CLI et formulaire de la TUI) : periode REELLEMENT couverte, toujours dite."""
    if result.first_event_at is None or result.last_event_at is None:
        return [_("Aucun événement dans les journaux disponibles : rien à mesurer.")]
    covered = result.last_event_at - result.first_event_at
    lines = [_("Mesuré sur {days} j de journaux ({events} événements, du {first} au {last}).").format(
        days=round(covered.total_seconds() / 86400, 1), events=result.events,
        first=result.first_event_at.date().isoformat(), last=result.last_event_at.date().isoformat())]
    if result.truncated:
        lines.append(_("Attention : trop d'événements, seuls les plus récents ont été rejoués."))
    lines.append(_("Aurait pris {actions} action(s) sur {sources} source(s) - {rejected} refusée(s) par les garde-fous.").format(
        actions=result.actions, sources=len(result.sources_acted), rejected=result.rejected_by_safety))
    if result.max_cumulative_ban_seconds:
        lines.append(_("Ban cumulé le plus long pour une source : {duration}.").format(
            duration=format_duration(result.max_cumulative_ban_seconds)))
    return lines


# --- Lot 4 : actions et commandes ---------------------------------------------------------------


def action_state_label(state: str) -> str:
    return {
        "pending": _("en cours d'application"),
        "applied": _("en cours"),
        "unknown": _("état inconnu (vérification impossible)"),
        "failed": _("non appliquée"),
        "expired": _("terminée (échéance)"),
        "revoked": _("levée"),
    }.get(state, state)


def finished_by_label(finished_by: str) -> str:
    return {
        "expiry": _("échéance"),
        "user": _("levée par l'utilisateur"),
        "policy": _("règle désactivée"),
        "emergency": _("arrêt d'urgence"),
        "outside": _("retirée hors RIPOSTE"),
    }.get(finished_by, finished_by or "-")


def action_detail_label(detail: str) -> str:
    if detail.startswith("error:"):
        return _("erreur : {error}").format(error=detail.partition(":")[2])
    return {
        "": "",
        "waf_inactive": _("WAF inactif : activer le WAF pour les actions de ban."),
        "active_defense_inactive": _("Leurres inactifs : activer Active Defense et ses leurres."),
        "no_subject": _("Aucun identifiant Active Defense connu pour cette IP : leurre impossible."),
        "decoy_already_assigned": _("La source est déjà affectée à un autre leurre ou plus longtemps."),
        "stronger_ban_present": _("Déjà bannie (ban manuel, permanent ou plus long) : rien n'a été écrit."),
        "invalid_network": _("Adresse invalide pour la blocklist."),
        "interrupted": _("Application interrompue (arrêt brutal) et absente au redémarrage."),
        "removed_outside": _("Retirée hors RIPOSTE (blocklist ou leurre modifié à la main)."),
        "check_failed": _("Vérification impossible (blocklist ou base illisible) : nouvel essai dans 60 s."),
    }.get(detail, detail)


def command_result_text(result: str, params: dict[str, object]) -> str:
    def p(key: str) -> str:
        value = params.get(key)
        return "-" if value is None else str(value)

    return {
        "revoked": _("Action {action_id} levée.").format(action_id=p("action_id")),
        "already_finished": _("Action {action_id} déjà terminée.").format(action_id=p("action_id")),
        "not_recidive": _("Action {action_id} : ne compte plus dans la récidive.").format(action_id=p("action_id")),
        "revoked_count": _("{count} action(s) levée(s).").format(count=p("count")),
        "source_forgotten": _("Mémoire de {ip} effacée.").format(ip=p("ip")),
        "source_has_action": _("{ip} a une action en cours : la lever d'abord.").format(ip=p("ip")),
        "unknown_source": _("Source inconnue de RIPOSTE : {ip}").format(ip=p("ip")),
        "exemption_removed": _("Exemption {network} retirée.").format(network=p("network")),
        "unknown_exemption": _("Aucune exemption pour {network}.").format(network=p("network")),
        "reloaded": _("Configuration relue par RIPOSTE."),
        "reload_refused": _("Configuration refusée par RIPOSTE ({reason}) : les règles précédentes restent actives.").format(
            reason=p("reason")),
        "unknown_action": _("Action inconnue : {action_id}").format(action_id=p("action_id")),
        "invalid_exempt": _("Durée d'exemption invalide : {exempt}").format(exempt=p("exempt")),
        "unknown_command": _("Commande inconnue : {kind}").format(kind=p("kind")),
        "error": _("Erreur : {error}").format(error=p("error")),
    }.get(result, result)


def format_status(status: RiposteStatus, in_progress: int, bans: int) -> list[str]:
    """Etat du processus (CLI `riposte status` et ecran Etat de la TUI), heures locales."""
    lines = [_("Processus : {state}").format(
        state=_("actif (PID {pid})").format(pid=status.pid) if status.running else _("arrêté"))]
    if status.running and status.started_at is not None:
        lines.append(_("Démarré le {when}").format(when=status.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")))
    if status.emergency_stop:
        lines.append(_("Arrêt d'urgence : ACTIF"))
    lines.append(_("Actions en cours : {count} (dont {bans} ban(s) local(aux))").format(count=in_progress, bans=bans))
    if status.heartbeat_at is not None:
        lines.append(_("Dernier signe de vie : {when}").format(when=status.heartbeat_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")))
    lines.append(_("Lignes lues : {lines} - événements nouveaux : {events} - doublons écartés : {duplicates}").format(
        lines=status.lines_read, events=status.new_events, duplicates=status.duplicates))
    if status.rejected:
        rejected = ", ".join(f"{reason} {count}" for reason, count in sorted(status.rejected.items()))
        lines.append(_("Lignes ignorées : {rejected}").format(rejected=rejected))
    for journal, when in sorted(status.last_event_at.items()):
        lines.append(_("Dernier événement {journal} : {when}").format(journal=journal, when=when.astimezone().strftime("%Y-%m-%d %H:%M:%S")))
    if status.decisions:
        decisions = ", ".join(f"{status_label(name)} {count}" for name, count in sorted(status.decisions.items()))
        lines.append(_("Décisions depuis le démarrage : {decisions}").format(decisions=decisions))
    return lines

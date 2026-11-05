"""Execution des commandes deposees par la TUI / la CLI (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.7, lot 4).

La TUI et la CLI ne touchent jamais au registre des actions : elles deposent une commande, executee ici
par le processus RIPOSTE (seul ecrivain) au tour suivant (<= 1 s). Le resultat est un CODE + parametres,
traduit par l'interface. Une commande en erreur n'arrete jamais la boucle : elle est marquee `failed`.

Ce qui n'a pas besoin du processus est fait directement par l'interface : l'arret d'urgence (drapeau
d'etat, persistant, respecte meme si le processus est arrete) et la desactivation d'une regle (fichier
de configuration, puis commande `reload`)."""
from __future__ import annotations

import ipaddress
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from omega_serv.application.riposte.actuator import RiposteActuator
from omega_serv.domain.security.riposte.actions import (
    EXEMPT_DURATIONS,
    Exemption,
    RiposteAction,
    RiposteCommand,
)
from omega_serv.domain.security.riposte.history import end_action, exclude_from_recidive
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.riposte_store_port import RiposteStorePort

COMMANDS_PER_TICK = 50
COMMANDS_RETENTION = timedelta(days=30)
_ALL = 100_000

Outcome = tuple[str, str, dict[str, Any]]
"""(etat `done` | `failed`, code de resultat, parametres)."""


class RiposteCommandRunner:
    def __init__(
        self,
        store: RiposteStorePort,
        actuator: RiposteActuator,
        clock: ClockPort,
        *,
        reload: Callable[[], str | None],
    ) -> None:
        """`reload` relit la configuration ; retourne None si elle est appliquee, sinon un code de refus."""
        self._store = store
        self._actuator = actuator
        self._clock = clock
        self._reload = reload

    def run_pending(self) -> int:
        commands = self._store.pending_commands(COMMANDS_PER_TICK)
        for command in commands:
            try:
                state, result, params = self._execute(command)
            except OSError as error:
                state, result, params = "failed", "error", {"error": f"{type(error).__name__}: {error}"}
            self._store.finish_command(command.id, state=state, result=result, result_params=params,
                                       done_at=self._clock.now())
            self._store.append_audit(self._clock.now(), f"command:{command.kind}", f"{result} {params}")
        return len(commands)

    def _execute(self, command: RiposteCommand) -> Outcome:
        params = command.params
        if command.kind == "revoke":
            return self._revoke_one(str(params.get("action_id", "")), exempt=params.get("exempt"),
                                    not_recidive=bool(params.get("not_recidive", False)))
        if command.kind == "not_recidive":
            return self._not_recidive(str(params.get("action_id", "")))
        if command.kind == "revoke_policy":
            policy_id = str(params.get("policy_id", ""))
            actions = self._store.list_actions(in_progress=True, limit=_ALL, policy_id=policy_id)
            return "done", "revoked_count", {"count": self._revoke_many(actions, by="policy")}
        if command.kind == "revoke_all":
            actions = self._store.list_actions(in_progress=True, limit=_ALL)
            return "done", "revoked_count", {"count": self._revoke_many(actions, by="emergency")}
        if command.kind == "forget_source":
            ip = str(params.get("ip", ""))
            if self._store.list_actions(in_progress=True, limit=1, ip=ip):
                return "failed", "source_has_action", {"ip": ip}
            return ("done", "source_forgotten", {"ip": ip}) if self._store.forget_source(ip) else \
                ("failed", "unknown_source", {"ip": ip})
        if command.kind == "remove_exemption":
            network = str(params.get("network", ""))
            return ("done", "exemption_removed", {"network": network}) if self._store.remove_exemption(network) else \
                ("failed", "unknown_exemption", {"network": network})
        if command.kind == "reload":
            refused = self._reload()
            return ("done", "reloaded", {}) if refused is None else ("failed", "reload_refused", {"reason": refused})
        return "failed", "unknown_command", {"kind": command.kind}

    def _revoke_one(self, action_id: str, *, exempt: object, not_recidive: bool) -> Outcome:
        action = self._store.get_action(action_id)
        if action is None:
            return "failed", "unknown_action", {"action_id": action_id}
        if exempt is not None and exempt not in EXEMPT_DURATIONS:
            return "failed", "invalid_exempt", {"exempt": str(exempt)}
        now = self._clock.now()
        was_in_progress = action.in_progress
        if was_in_progress:
            action = self._actuator.revoke(action, by="user", now=now)
            self._update_history(action, now, not_recidive=not_recidive)
        elif not_recidive:
            self._update_history(action, None, not_recidive=True)
        if not_recidive and action.counts_for_recidive:
            self._store.save_action(replace(action, counts_for_recidive=False))
        if exempt is not None:
            seconds = EXEMPT_DURATIONS[str(exempt)]
            network = str(ipaddress.ip_network(action.ip))
            self._store.add_exemption(Exemption(
                network=network, created_at=now, until=None if seconds is None else now + timedelta(seconds=seconds),
                origin_action_id=action.id,
            ))
        result = "revoked" if was_in_progress else "already_finished"
        return "done", result, {"action_id": action.id, "exempt": exempt, "not_recidive": not_recidive}

    def _not_recidive(self, action_id: str) -> Outcome:
        action = self._store.get_action(action_id)
        if action is None:
            return "failed", "unknown_action", {"action_id": action_id}
        self._update_history(action, None, not_recidive=True)
        self._store.save_action(replace(action, counts_for_recidive=False))
        return "done", "not_recidive", {"action_id": action.id}

    def _revoke_many(self, actions: list[RiposteAction], *, by: str) -> int:
        now = self._clock.now()
        count = 0
        for action in actions:
            revoked = self._actuator.revoke(action, by=by, now=now)
            self._update_history(revoked, now, not_recidive=False)
            count += 1
        return count

    def _update_history(self, action: RiposteAction, ended_at: datetime | None, *, not_recidive: bool) -> None:
        history = self._store.get_source(action.ip)
        if history is None:
            return
        if ended_at is not None:
            history = end_action(history, action.id, ended_at)
        if not_recidive:
            history = exclude_from_recidive(history, action.id)
        self._store.save_source(history, self._clock.now())

    def maintenance(self, now: datetime) -> None:
        self._store.purge_commands(now - COMMANDS_RETENTION, 10_000)

"""Alertes locales du panneau web (etude OMEGA-SERV_ETUDE_MODULES_ADMIN_WEB.md, module 1 ; decisions de l'auteur du
2026-11-17 : locales seulement, aucun envoi vers l'exterieur, evaluees dans le processus d'administration).

Une regle = une mesure, un seuil, une duree (« pendant N minutes ») et un retour a la normale plus bas que le seuil
(hysteresis : une alerte ne clignote pas autour du seuil). Cycle : en attente -> ouverte -> fermee ; une alerte par
episode. Les certificats donnent une alerte par fichier, aggravee aux paliers 30, 14, 7 et 1 jours. Pendant une
maintenance (reglee dans la TUI), aucune alerte ne s'ouvre ; celles deja ouvertes se ferment normalement."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

from omega_serv.core.i18n import N_

Direction = Literal["above", "below"]


@dataclass(frozen=True)
class AlertRule:
    key: str
    label: str
    """Libelle a traduire a l'affichage (N_)."""
    unit: str
    default: float
    clear_gap: float
    """Fermeture quand la mesure revient a seuil - ecart (ou + ecart pour « below »)."""
    hold_seconds: int
    direction: Direction = "above"
    low: float = 0.0
    high: float = 100.0
    """Seuils permis dans le reglage."""


RULES: tuple[AlertRule, ...] = (
    AlertRule("disque", N_("Disque (partition de l'instance) plein"), "%", 90, 5, 300, low=50, high=99),
    AlertRule("memoire", N_("Mémoire saturée"), "%", 90, 5, 600, low=50, high=99),
    AlertRule("swap", N_("Swap très utilisé"), "%", 80, 10, 600, low=10, high=99),
    AlertRule("processeur", N_("Processeur saturé"), "%", 95, 10, 600, low=50, high=100),
    AlertRule("temperature", N_("Processeur trop chaud"), "°C", 85, 5, 300, low=50, high=110),
    AlertRule("batterie", N_("Batterie faible"), "%", 15, 5, 120, direction="below", low=5, high=50),
    AlertRule("erreurs_5xx", N_("Erreurs 5xx du site"), "%", 5, 3, 0, low=1, high=50),
    AlertRule("backend", N_("Backend hors service"), "", 1, 0, 120, low=1, high=1),
    AlertRule("incident", N_("Incident Active Defense ouvert"), "", 1, 0, 0, low=1, high=1),
    AlertRule("certificat", N_("Certificat bientôt expiré"), "j", 30, 0, 0, direction="below", low=1, high=90),
)
RULES_BY_KEY = {rule.key: rule for rule in RULES}
CERTIFICATE_STEPS = (30, 14, 7, 1)
HISTORY_LIMIT = 500
HISTORY_SECONDS = 30 * 86400


def thresholds_from_settings(raw: object) -> dict[str, float | None]:
    """Reglage `alerts` de l'option admin_web : {regle: seuil ou false}. Absent : seuil par defaut ; false : regle
    coupee ; valeur hors bornes : seuil par defaut (validate_admin_web le signale a l'enregistrement)."""
    values = raw if isinstance(raw, dict) else {}
    result: dict[str, float | None] = {}
    for rule in RULES:
        value = values.get(rule.key, rule.default)
        if value is False:
            result[rule.key] = None
        elif isinstance(value, int | float) and not isinstance(value, bool) and rule.low <= value <= rule.high:
            result[rule.key] = float(value)
        else:
            result[rule.key] = float(rule.default)
    return result


def threshold_errors(raw: object) -> list[tuple[str, AlertRule]]:
    """Regles dont le reglage est invalide (ni false, ni un nombre dans les bornes)."""
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return [("", RULES[0])]
    wrong = []
    for key, value in raw.items():
        rule = RULES_BY_KEY.get(key)
        if rule is None:
            wrong.append((key, RULES[0]))
        elif value is not False and not (isinstance(value, int | float) and not isinstance(value, bool)
                                         and rule.low <= value <= rule.high):
            wrong.append((key, rule))
    return wrong


@dataclass(frozen=True)
class Alert:
    key: str
    """Regle, ou « certificat:<fichier> », « backend:<zone>/<nom> »..."""
    rule: str
    subject: str
    """Ce qui est en cause (fichier, backend, incident) ; vide pour une mesure de la machine."""
    opened_at: float
    value: float | None
    threshold: float | None
    worst: float | None
    level: str = ""
    """Palier des certificats (« 14 »...) ; vide sinon."""
    closed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "rule": self.rule, "subject": self.subject, "opened_at": self.opened_at,
                "value": self.value, "threshold": self.threshold, "worst": self.worst, "level": self.level,
                "closed_at": self.closed_at}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Alert | None:
        try:
            return cls(str(data["key"]), str(data["rule"]), str(data.get("subject", "")), float(data["opened_at"]),
                       _number(data.get("value")), _number(data.get("threshold")), _number(data.get("worst")),
                       str(data.get("level", "")), _number(data.get("closed_at")))
        except (KeyError, TypeError, ValueError):
            return None


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


@dataclass(frozen=True)
class AlertEvent:
    kind: Literal["opened", "worse", "closed"]
    alert: Alert


@dataclass(frozen=True)
class Reading:
    """Une mesure a juger : regle, sujet (vide pour la machine) et valeur (None : pas de mesure, rien ne change)."""
    rule: str
    value: float | None
    subject: str = ""


@dataclass
class AlertBook:
    """Alertes ouvertes, en attente (seuil depasse depuis...) et historique (30 jours, 500 au plus)."""
    active: dict[str, Alert] = field(default_factory=dict)
    pending: dict[str, float] = field(default_factory=dict)
    history: list[Alert] = field(default_factory=list)

    def evaluate(self, readings: list[Reading], thresholds: dict[str, float | None], now: float, *,
                 maintenance: bool = False, complete_rules: frozenset[str] = frozenset()) -> list[AlertEvent]:
        """`complete_rules` : regles dont `readings` donne TOUS les sujets (backends, incidents, certificats) ; une
        alerte ouverte de ces regles dont le sujet n'apparait plus se ferme (backend retire, incident ferme)."""
        events: list[AlertEvent] = []
        seen: set[str] = set()
        for reading in readings:
            rule = RULES_BY_KEY.get(reading.rule)
            threshold = thresholds.get(reading.rule)
            key = f"{reading.rule}:{reading.subject}" if reading.subject else reading.rule
            seen.add(key)
            if rule is None or reading.value is None:
                continue
            if threshold is None:
                self.pending.pop(key, None)
                if key in self.active:
                    events.append(self._close(key, now))
                continue
            events += self._judge(rule, key, reading, threshold, now, maintenance)
        for key in [k for k, alert in self.active.items() if alert.rule in complete_rules and k not in seen]:
            events.append(self._close(key, now))
        for key in [k for k in self.pending if k.split(":", 1)[0] in complete_rules and k not in seen]:
            del self.pending[key]
        self._trim(now)
        return events

    def _judge(self, rule: AlertRule, key: str, reading: Reading, threshold: float, now: float,
               maintenance: bool) -> list[AlertEvent]:
        value = float(reading.value)  # type: ignore[arg-type]
        above = rule.direction == "above"
        breached = value >= threshold if above else value <= threshold
        clear = threshold - rule.clear_gap if above else threshold + rule.clear_gap
        cleared = (value < clear if above else value > clear) if rule.clear_gap else not breached
        current = self.active.get(key)
        if current is not None:
            if cleared:
                return [self._close(key, now)]
            worst = current.worst if current.worst is not None else value
            worst = max(worst, value) if above else min(worst, value)
            level = _certificate_level(value) if rule.key == "certificat" else ""
            updated = replace(current, value=value, worst=worst, level=level or current.level)
            self.active[key] = updated
            if level and level != current.level:
                return [AlertEvent("worse", updated)]
            return []
        if not breached:
            self.pending.pop(key, None)
            return []
        since = self.pending.setdefault(key, now)
        if now - since < rule.hold_seconds or maintenance:
            return []
        del self.pending[key]
        level = _certificate_level(value) if rule.key == "certificat" else ""
        alert = Alert(key, rule.key, reading.subject, now, value, threshold, value, level)
        self.active[key] = alert
        return [AlertEvent("opened", alert)]

    def _close(self, key: str, now: float) -> AlertEvent:
        closed = replace(self.active.pop(key), closed_at=now)
        self.history.append(closed)
        return AlertEvent("closed", closed)

    def _trim(self, now: float) -> None:
        self.history = [a for a in self.history if (a.closed_at or now) >= now - HISTORY_SECONDS][-HISTORY_LIMIT:]

    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "active": [a.to_dict() for a in self.active.values()],
                "history": [a.to_dict() for a in self.history]}

    @classmethod
    def from_dict(cls, data: object) -> AlertBook:
        book = cls()
        if not isinstance(data, dict):
            return book
        for raw in data.get("active", []) if isinstance(data.get("active"), list) else []:
            alert = Alert.from_dict(raw) if isinstance(raw, dict) else None
            if alert is not None:
                book.active[alert.key] = alert
        for raw in data.get("history", []) if isinstance(data.get("history"), list) else []:
            alert = Alert.from_dict(raw) if isinstance(raw, dict) else None
            if alert is not None:
                book.history.append(alert)
        return book


def _certificate_level(days: float) -> str:
    """Plus petit palier franchi : 30, 14, 7 ou 1 jour(s) ; « 0 » expire."""
    if days < 0:
        return "0"
    return str(min(step for step in CERTIFICATE_STEPS if days <= step)) if days <= CERTIFICATE_STEPS[0] else ""

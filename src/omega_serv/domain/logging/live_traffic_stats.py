"""Statistiques de flux en direct (retour utilisateur 2026-09-09, ecran
"Etat & Ressources") - transpose depuis omega-fire
(interfaces/cli/renderers/logs_live.py::LogBuffer.get_stats(), meme
calcul de debit "cumule depuis le debut du suivi" plutot qu'une
fenetre glissante - fidele a la reference plutot qu'invente) mais
adapte a la source reelle de SERV : `ParsedAccessLogEntry`
(domain/logging/access_log_parser.py, format combine propre a SERV)
plutot que le parseur multi-format devinant heuristiquement chez fire
(fire tire des logs de serveurs web TIERS dont il ne controle pas le
format ; SERV connait deja le sien, un vrai parseur suffit).

Latence absente deliberement : le format combine de SERV n'enregistre
aucun temps de reponse (domain/logging/access_log_format.py), contrairement
au parseur generique de fire qui invente une valeur par defaut (25ms)
faute de mieux - ne jamais inventer une mesure absente ici.

Pur (aucune I/O, aucune lecture d'horloge murale directe) : `now` est
toujours fourni par l'appelant, meme convention que
domain/logs/rotation.py::plan_rotation."""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime

from omega_serv.domain.logging.access_log_parser import ParsedAccessLogEntry

DEFAULT_BUFFER_SIZE = 500

_MAX_TRACKED_IPS = 10_000
"""Retour utilisateur (audit performance/securite, constat "Compteur
d'IP du dashboard non borne") : `_ip_counts` grandissait avec chaque IP
unique vue depuis l'ouverture de l'ecran, sans jamais etre purge -
negligeable pour un dashboard consulte quelques minutes, mais une
fuite reelle si un operateur le laisse ouvert en continu des jours
durant sous fort trafic (des IP jamais revues s'accumulent pour
toujours). Piste de l'audit retenue : taille max avec eviction LRU
(pas de fenetre glissante a decroissance temporelle - romprait le
choix deliberement documente ci-dessous, "cumule depuis le debut", et
`now` n'est de toute facon jamais lu ici, voir le commentaire de
purete du module). 10 000 IP simultanement suivies est tres largement
au-dessus de tout usage reel d'un dashboard interactif - la purge ne
joue donc qu'en repli, jamais en usage normal."""


@dataclass(frozen=True)
class LiveTrafficStats:
    total: int
    success_2xx: int
    redirect_3xx: int
    errors_4xx: int
    errors_5xx: int
    unique_ips: int
    top_ip: str
    error_rate: float
    rps: float
    bps: float
    bytes_total: int
    avg_size: float
    buffer_size: int


class LiveTrafficBuffer:
    """Compteurs cumules depuis `started_at` (jamais une fenetre
    glissante - meme choix que la reference). `max_size` borne
    uniquement le tampon des entrees recentes conservees (`buffer_size`
    dans les stats) - les compteurs numeriques (total, 2xx/3xx/4xx/5xx,
    octets) portent eux sur tout l'historique suivi depuis la
    construction, sans aucune borne (ce sont de simples entiers, cout
    memoire constant). Seul `_ip_counts` (une entree par IP source
    unique) a besoin d'une borne explicite (`_MAX_TRACKED_IPS`,
    eviction LRU) - lui seul grandit avec la diversite du trafic plutot
    qu'avec sa seule duree."""

    def __init__(self, started_at: datetime, max_size: int = DEFAULT_BUFFER_SIZE) -> None:
        self._started_at = started_at
        self._buffer: deque[ParsedAccessLogEntry] = deque(maxlen=max_size)
        self._total = 0
        self._success_2xx = 0
        self._redirect_3xx = 0
        self._errors_4xx = 0
        self._errors_5xx = 0
        self._bytes_total = 0
        self._ip_counts: OrderedDict[str, int] = OrderedDict()

    def add(self, entry: ParsedAccessLogEntry) -> None:
        self._buffer.append(entry)
        self._total += 1
        if 200 <= entry.status_code < 300:
            self._success_2xx += 1
        elif 300 <= entry.status_code < 400:
            self._redirect_3xx += 1
        elif 400 <= entry.status_code < 500:
            self._errors_4xx += 1
        elif 500 <= entry.status_code < 600:
            self._errors_5xx += 1
        self._bytes_total += entry.response_size
        if entry.ip in self._ip_counts:
            self._ip_counts[entry.ip] += 1
            self._ip_counts.move_to_end(entry.ip)
        else:
            if len(self._ip_counts) >= _MAX_TRACKED_IPS:
                self._ip_counts.popitem(last=False)
            self._ip_counts[entry.ip] = 1

    def get_stats(self, now: datetime) -> LiveTrafficStats:
        elapsed = max(0.1, (now - self._started_at).total_seconds())
        total_errors = self._errors_4xx + self._errors_5xx
        top_ip = max(self._ip_counts, key=lambda ip: self._ip_counts[ip]) if self._ip_counts else "N/A"
        return LiveTrafficStats(
            total=self._total,
            success_2xx=self._success_2xx,
            redirect_3xx=self._redirect_3xx,
            errors_4xx=self._errors_4xx,
            errors_5xx=self._errors_5xx,
            unique_ips=len(self._ip_counts),
            top_ip=top_ip,
            error_rate=(total_errors / self._total * 100) if self._total else 0.0,
            rps=self._total / elapsed,
            bps=self._bytes_total / elapsed,
            bytes_total=self._bytes_total,
            avg_size=(self._bytes_total / self._total) if self._total else 0.0,
            buffer_size=len(self._buffer),
        )

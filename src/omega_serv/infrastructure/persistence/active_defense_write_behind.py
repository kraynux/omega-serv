"""Ecriture differee d'Active Defense (OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md §3.6,
correctif valide par l'utilisateur le 2026-10-26).

Mesures qui l'ont justifie (tools/bench/active_defense_load.py, §3.5) :
- une ecriture SQLite par requete suspecte, faite sur la boucle asyncio, coutait 18 % de debit
  aux visiteurs legitimes sous un botnet (adresse nouvelle a chaque requete) ;
- une base verrouillee par un autre programme (purge, sauvegarde) figeait TOUT le serveur 5 s
  (delai par defaut de sqlite3), puis chaque requete suspecte echouait sur « database is
  locked », exception non rattrapee : connexion coupee sans reponse, rien dans error.log ;
- la purge n'etant que manuelle, la base grossissait sans limite sous un botnet.

D'ou :
- `SqliteActiveDefenseWriter` : UN fil d'ecriture, SA connexion (ouverte dans le fil, delai de
  verrou court), une file BORNEE (au-dela : travail abandonne et compte, jamais d'attente sur la
  boucle), nouvel essai du meme travail apres une erreur (un verrou bref ne perd rien), une
  seule ligne au journal par serie d'erreurs, purge automatique des etats expires ;
- `WriteBehindThreatStateRepository` / `WriteBehindDeceptionAssignmentRepository` : ce que la
  boucle utilise. Une ecriture devient « en attente » (visible tout de suite par les lectures
  suivantes de CE processus) et part dans la file ; une lecture compare l'en-attente et la base
  et garde la plus recente ; une erreur de lecture vaut « rien de connu », jamais une exception
  vers la requete.

Mode boost : chaque worker a son propre ecrivain et ses propres « en attente » (cree apres le
fork, dans build_server). Les ecritures de plusieurs workers sur un meme sujet restent « la
derniere gagne », exactement comme avant ce correctif."""
from __future__ import annotations

import queue
import sqlite3
import threading
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypeVar, cast

from omega_serv.domain.security.active_defense.entities import DeceptionAssignment, ThreatState
from omega_serv.domain.security.active_defense.policies import (
    AUDIT_MAX_ROWS,
    AUDIT_RETENTION_DAYS,
    INCIDENT_HISTORY_KEEP_FIRST,
    INCIDENT_HISTORY_KEEP_LAST,
    MAX_TRACKED_SUBJECTS,
)
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_deception_assignment_repository import (
    SqliteDeceptionAssignmentRepository,
)
from omega_serv.infrastructure.persistence.sqlite_incident_repository import (
    SqliteIncidentRepository,
)
from omega_serv.infrastructure.persistence.sqlite_threat_state_repository import (
    SqliteThreatStateRepository,
)
from omega_serv.ports.active_defense_writer_port import ActiveDefenseJob, ActiveDefenseRepositories
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.deception_assignment_repository_port import DeceptionAssignmentRepositoryPort
from omega_serv.ports.threat_state_repository_port import ThreatStateRepositoryPort

ErrorReporter = Callable[[str], None]
_T = TypeVar("_T")

MAX_PENDING_JOBS = 10_000
"""Borne de la file : ~10 000 observations en attente au plus (quelques Mo). Au-dela, la base
est indisponible ou trop lente depuis longtemps : on abandonne plutot que de grossir."""
WRITER_LOCK_TIMEOUT_SECONDS = 1.0
"""Attente maximale d'un verrou par le FIL d'ecriture (jamais la boucle) avant de reessayer."""
READER_LOCK_TIMEOUT_SECONDS = 0.05
"""Lectures faites sur la boucle : en mode WAL elles n'attendent normalement jamais ; borne
basse quand meme, une lecture impossible vaut « rien de connu »."""
RETRY_PAUSE_SECONDS = 0.5
BATCH_SIZE = 200
BATCH_WINDOW_SECONDS = 0.05
"""Apres le premier travail recu, le fil attend au plus 50 ms d'en accumuler d'autres avant
d'ecrire (« validation groupee »). Mesure (2026-10-26) : sous un botnet, les observations
arrivent une a une (~400/s) ; sans cette fenetre, chaque lot ne contenait qu'un travail, donc
une validation et un passage de GIL par observation : 15 fois le cout d'un lot plein. Sans
effet sur les decisions : les lectures voient deja les etats en attente."""
"""Travaux ecrits dans UNE transaction. Mesure (2026-10-26) : valider apres chaque ecriture
coutait 205 µs de processeur par ecriture, valider une fois pour 100 en coute 72 - or le fil
d'ecriture partage le processeur (et le GIL) avec la boucle qui sert les visiteurs."""
PURGE_INTERVAL_SECONDS = 600.0


def purge_interval_for(state_ttl_seconds: int) -> float:
    """Purge au plus toutes les 10 min, et au moins deux fois par duree de vie d'un etat (jamais
    plus d'une fois toutes les 10 s) : la base reste proportionnelle au trafic recent."""
    return max(10.0, min(PURGE_INTERVAL_SECONDS, state_ttl_seconds / 2))


def _ignore(_message: str) -> None:
    return None


class _DeferredCommitConnection:
    """Connexion donnee aux repositories du fil d'ecriture : leur `commit()` ne fait rien, le fil
    valide lui-meme une fois par lot (BATCH_SIZE). Tout le reste est la vraie connexion."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def __getattr__(self, name: str) -> object:
        return getattr(self._connection, name)

    def commit(self) -> None:
        return None


class SqliteActiveDefenseWriter:
    """Implemente ports.active_defense_writer_port.ActiveDefenseWriterPort."""

    def __init__(
        self,
        database_path: Path,
        clock: ClockPort,
        *,
        max_pending: int = MAX_PENDING_JOBS,
        lock_timeout_seconds: float = WRITER_LOCK_TIMEOUT_SECONDS,
        retry_pause_seconds: float = RETRY_PAUSE_SECONDS,
        purge_interval_seconds: float = PURGE_INTERVAL_SECONDS,
        batch_window_seconds: float = BATCH_WINDOW_SECONDS,
    ) -> None:
        self._database_path = database_path
        self._clock = clock
        self._queue: queue.Queue[ActiveDefenseJob] = queue.Queue(maxsize=max_pending)
        self._lock_timeout_seconds = lock_timeout_seconds
        self._retry_pause_seconds = retry_pause_seconds
        self._purge_interval_seconds = purge_interval_seconds
        self._batch_window_seconds = batch_window_seconds
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._dropped = 0
        self._failing = False
        self._overflowing = False
        self._report: ErrorReporter = _ignore
        self._after_commit: list[Callable[[], None]] = []

    def set_error_reporter(self, report: ErrorReporter) -> None:
        """Le serveur branche ici son journal d'erreurs (appele depuis le fil d'ecriture :
        FileLineLogger est protege par un verrou)."""
        self._report = report

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def capacity(self) -> int:
        """Borne commune : travaux dans la file, et etats dans le tampon d'un repository."""
        return self._queue.maxsize

    def report(self, message: str) -> None:
        self._report(message)

    def count_dropped(self, count: int) -> None:
        """Travaux refuses ailleurs (tampon d'etats plein) : comptes et signales comme la file pleine."""
        self._dropped += count
        if not self._overflowing:
            self._overflowing = True
            self._log_error(
                "Active Defense : file d'écriture pleine, observations abandonnées "
                "(base indisponible ou trop lente) - le service continue normalement"
            )

    def after_commit(self, callback: Callable[[], None]) -> None:
        """Appele PAR UN TRAVAIL (fil d'ecriture) : `callback` ne s'execute qu'apres la validation
        du lot, jamais si le lot est annule. Sert a retirer un etat « en attente » seulement quand
        la base le contient vraiment (sinon une lecture entre les deux verrait l'ancien etat)."""
        self._after_commit.append(callback)

    def _log_error(self, message: str) -> None:
        """Ligne du journal d'erreurs du serveur (D18 : reste en francais, jamais traduite)."""
        self._report(message)

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="omega-serv-active-defense-writer", daemon=True)
            self._thread.start()

    def submit(self, job: ActiveDefenseJob) -> bool:
        if self._stopping.is_set():
            return False
        try:
            self._queue.put_nowait(job)
        except queue.Full:
            self._dropped += 1
            if not self._overflowing:
                self._overflowing = True
                self._log_error(
                    "Active Defense : file d'écriture pleine, observations abandonnées "
                    "(base indisponible ou trop lente) - le service continue normalement"
                )
            return False
        if self._overflowing and self._queue.qsize() < self._queue.maxsize // 2:
            self._overflowing = False
            self._log_error(f"Active Defense : file d'écriture rétablie ({self._dropped} observation(s) abandonnée(s) depuis le démarrage)")
        return True

    def flush(self, timeout: float) -> bool:
        done = threading.Event()
        # signale APRES la validation du lot qui le contient (file FIFO : tout ce qui precede est en base)
        if not self.submit(lambda _repositories: self.after_commit(done.set)):
            return False
        return done.wait(timeout)

    def stop(self, timeout: float) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout)

    # --- fil d'ecriture -------------------------------------------------------------------------

    def _run(self) -> None:
        connection: sqlite3.Connection | None = None
        repositories: ActiveDefenseRepositories | None = None
        next_purge = time.monotonic() + self._purge_interval_seconds
        while True:
            if repositories is None or connection is None:
                connection, repositories = self._open()
                if repositories is None or connection is None:
                    if self._stopping.wait(self._retry_pause_seconds * 4):
                        return
                    continue
            try:
                batch = [self._queue.get(timeout=0.5)]
            except queue.Empty:
                if self._stopping.is_set():
                    break
                batch = []
            window_end = time.monotonic() + self._batch_window_seconds
            while batch and len(batch) < BATCH_SIZE:
                remaining = window_end - time.monotonic()
                if remaining <= 0 or self._stopping.is_set():
                    break
                try:
                    batch.append(self._queue.get(timeout=remaining))
                except queue.Empty:
                    break
            if batch:
                self._execute(batch, connection, repositories)
            if time.monotonic() >= next_purge:
                next_purge = time.monotonic() + self._purge_interval_seconds
                self._execute([self._purge_job], connection, repositories)
        if connection is not None:
            connection.close()

    def _open(self) -> tuple[sqlite3.Connection | None, ActiveDefenseRepositories | None]:
        try:
            connection = open_active_defense_connection(self._database_path, lock_timeout=self._lock_timeout_seconds)
        except OSError as error:
            self._failed(error)
            return None, None
        deferred = cast("sqlite3.Connection", _DeferredCommitConnection(connection))
        repositories = ActiveDefenseRepositories(
            threat_states=SqliteThreatStateRepository(deferred),
            incidents=SqliteIncidentRepository(deferred),
            deception_assignments=SqliteDeceptionAssignmentRepository(deferred),
        )
        return connection, repositories

    def _purge_job(self, repositories: ActiveDefenseRepositories) -> None:
        """Etats de menace expires et journal d'audit (duree + plafond). La fermeture des
        incidents (et leur export automatique) reste a `active-defense purge`, inchangee."""
        now = self._clock.now()
        repositories.threat_states.expire_before(now)
        repositories.threat_states.cap_tracked_subjects(MAX_TRACKED_SUBJECTS)
        repositories.threat_states.prune_audit_log(now - timedelta(days=AUDIT_RETENTION_DAYS), AUDIT_MAX_ROWS)
        repositories.incidents.prune_history(INCIDENT_HISTORY_KEEP_FIRST, INCIDENT_HISTORY_KEEP_LAST)

    def _execute(
        self, batch: list[ActiveDefenseJob], connection: sqlite3.Connection, repositories: ActiveDefenseRepositories,
    ) -> None:
        """Un lot = une transaction. Erreur SQLite : tout le lot est annule puis rejoue (un verrou
        bref ne perd rien) ; a l'arret, il est abandonne et compte. Un travail defectueux (autre
        erreur) est ecarte seul, sans faire echouer les autres."""
        while True:
            self._after_commit.clear()
            try:
                for job in batch:
                    try:
                        job(repositories)
                    except (sqlite3.Error, OSError):
                        raise
                    except Exception as error:  # noqa: BLE001 - un travail defectueux ne doit jamais tuer le fil d'ecriture
                        self._log_error(f"Active Defense : écriture abandonnée (erreur inattendue : {error!r})")
                        self._dropped += 1
                connection.commit()
                for callback in self._after_commit:
                    callback()
            except (sqlite3.Error, OSError) as error:
                self._failed(error)
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
                if self._stopping.wait(self._retry_pause_seconds):
                    self._dropped += len(batch)
                    return
                continue
            if self._failing:
                self._failing = False
                self._log_error("Active Defense : écriture en base rétablie")
            return

    def _failed(self, error: BaseException) -> None:
        if not self._failing:
            self._failing = True
            self._log_error(
                f"Active Defense : écriture en base impossible ({error}) - nouvel essai automatique, "
                "le service continue normalement"
            )


def _newest_state(first: ThreatState | None, second: ThreatState | None) -> ThreatState | None:
    if first is None:
        return second
    if second is None:
        return first
    return first if first.updated_at >= second.updated_at else second


class _GuardedReads:
    """Une lecture qui echoue vaut « rien de connu » ; une ligne au journal par serie d'echecs."""

    def __init__(self, report: ErrorReporter) -> None:
        self._log_error = report
        self._failing = False

    def read(self, fetch: Callable[[], _T], default: _T) -> _T:
        try:
            value = fetch()
        except (sqlite3.Error, OSError) as error:
            if not self._failing:
                self._failing = True
                self._log_error(f"Active Defense : lecture en base impossible ({error}) - requêtes traitées sans historique")
            return default
        if self._failing:
            self._failing = False
            self._log_error("Active Defense : lecture en base rétablie")
        return value


class WriteBehindThreatStateRepository:
    """Implemente ThreatStateRepositoryPort pour la boucle : lectures gardees, ecritures differees.

    Les etats a ecrire s'accumulent dans un tampon (borne, MAX_PENDING_JOBS) ; UN seul travail
    est depose dans la file tant que le precedent n'a pas pris le tampon, et il ecrit tout d'un
    coup (`save_many`). Sous un botnet, chaque requete est un nouvel etat : un travail Python par
    etat coutait autant de temps de GIL a la boucle (mesure du 2026-10-26)."""

    def __init__(self, reader: ThreatStateRepositoryPort, writer: SqliteActiveDefenseWriter) -> None:
        self._reader = reader
        self._writer = writer
        self._pending: dict[str, ThreatState] = {}
        self._unsaved: list[ThreatState] = []
        self._flush_submitted = False
        self._lock = threading.Lock()
        self._reads = _GuardedReads(writer.report)

    def get(self, subject_id: str) -> ThreatState | None:
        with self._lock:
            pending = self._pending.get(subject_id)
        stored = self._reads.read(lambda: self._reader.get(subject_id), None)
        return _newest_state(pending, stored)

    def save(self, state: ThreatState) -> None:
        self.save_many((state,))

    def save_many(self, states: Sequence[ThreatState]) -> None:
        with self._lock:
            room = max(0, self._writer.capacity - len(self._unsaved))
            accepted, refused = list(states[:room]), len(states) - room
            for state in accepted:
                self._pending[state.subject_id] = state
            self._unsaved.extend(accepted)
            submit = bool(accepted) and not self._flush_submitted
            if submit:
                self._flush_submitted = True
        if refused > 0:
            self._writer.count_dropped(refused)
        if submit and not self._writer.submit(self._flush_job()):
            with self._lock:
                dropped, self._unsaved, self._flush_submitted = self._unsaved, [], False
                for state in dropped:
                    if self._pending.get(state.subject_id) is state:
                        del self._pending[state.subject_id]

    def _flush_job(self) -> ActiveDefenseJob:
        taken: list[ThreatState] | None = None

        def job(repositories: ActiveDefenseRepositories) -> None:
            nonlocal taken
            if taken is None:  # premier passage : prend le tampon ; un lot rejoue reecrit les memes etats
                with self._lock:
                    taken, self._unsaved, self._flush_submitted = self._unsaved, [], False
            repositories.threat_states.save_many(taken)
            batch = taken
            self._writer.after_commit(lambda: self._forget_all(batch))

        return job

    def _forget_all(self, states: list[ThreatState]) -> None:
        with self._lock:
            for state in states:
                if self._pending.get(state.subject_id) is state:
                    del self._pending[state.subject_id]

    def expire_before(self, instant: datetime) -> int:
        return self._reads.read(lambda: self._reader.expire_before(instant), 0)

    def prune_audit_log(self, older_than: datetime, max_rows: int) -> int:
        return self._reads.read(lambda: self._reader.prune_audit_log(older_than, max_rows), 0)

    def cap_tracked_subjects(self, max_subjects: int) -> int:
        return self._reads.read(lambda: self._reader.cap_tracked_subjects(max_subjects), 0)

    def list_all(self) -> list[ThreatState]:
        return self._reads.read(self._reader.list_all, [])


_RELEASED = object()


class WriteBehindDeceptionAssignmentRepository:
    """Implemente DeceptionAssignmentRepositoryPort pour la boucle (meme principe)."""

    def __init__(self, reader: DeceptionAssignmentRepositoryPort, writer: SqliteActiveDefenseWriter) -> None:
        self._reader = reader
        self._writer = writer
        self._pending: dict[str, object] = {}
        self._lock = threading.Lock()
        self._reads = _GuardedReads(writer.report)

    def get(self, subject_id: str) -> DeceptionAssignment | None:
        with self._lock:
            pending = self._pending.get(subject_id)
        if pending is _RELEASED:
            return None
        if isinstance(pending, DeceptionAssignment):
            return pending
        return self._reads.read(lambda: self._reader.get(subject_id), None)

    def save(self, assignment: DeceptionAssignment) -> None:
        self._defer(assignment.subject_id, assignment, lambda repositories: repositories.deception_assignments.save(assignment))

    def release(self, subject_id: str) -> None:
        self._defer(subject_id, _RELEASED, lambda repositories: repositories.deception_assignments.release(subject_id))

    def list_active(self) -> list[DeceptionAssignment]:
        return self._reads.read(self._reader.list_active, [])

    def _defer(self, subject_id: str, marker: object, write: ActiveDefenseJob) -> None:
        with self._lock:
            self._pending[subject_id] = marker

        def job(repositories: ActiveDefenseRepositories) -> None:
            write(repositories)
            self._writer.after_commit(lambda: self._forget(subject_id, marker))

        if not self._writer.submit(job):
            self._forget(subject_id, marker)

    def _forget(self, subject_id: str, marker: object) -> None:
        with self._lock:
            if self._pending.get(subject_id) is marker:
                del self._pending[subject_id]

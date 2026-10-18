"""Adaptateur WafPort pour un script WAF EXTERNE importe en mode
"magnet" (OMEGA-SERV_ETUDE_INCLUDE_ET_MAGNET_LUA.md §5,
OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md). Le but n'est PAS d'implementer
un WAF de plus : c'est de faire tourner, sans le reecrire, un script
`mod_magnet` Lighttpd deja existant, ecrit par l'operateur pour un AUTRE
site - jamais un contrat invente par omega-serv (l'ancien contrat
`inspect(req)` de ce fichier a ete abandonne pour cette raison exacte).
Seul point du projet qui depend de `lupa` (extra optionnel "magnet",
voir pyproject.toml) - import local a cette classe, jamais au niveau
module d'un fichier charge sans condition.

Modele d'execution (reverse-engineering d'un vrai script fourni par
l'utilisateur, `~/DEV/SERV/waf.lua` - jamais devine depuis la seule
documentation Lighttpd) :
- le script est un CHUNK Lua plat (pas de fonction wrapper), compile
  UNE SEULE FOIS au demarrage (`runtime.compile(source)`) puis RAPPELE
  tel quel a chaque requete - les GLOBALES Lua (`rate_store = rate_store
  or {}`, `function add_to_blocklist(...) ... end`) survivent donc d'un
  appel a l'autre (verifie empiriquement : appeler le meme objet compile
  plusieurs fois conserve les globales entre appels tout en
  reinitialisant les `local`s a chaque fois) - c'est le SEUL modele
  d'execution qui respecte la persistance d'etat (rate limiting,
  blocklist progressive) que ce genre de script attend.
- le script lit l'etat de la requete via la table `lighty.env[...]`
  (cles a plat, cf. `lighty_compat.SUPPORTED_ENV_KEYS`) et peut ecrire
  `lighty.header[...]`/`lighty.content` (acceptees en ecriture, jamais
  relues - "le WAF retourne une decision, le serveur rend une page
  generique", decision deja actee avant cette revision) et appeler
  `lighty.stat(path)`.
- convention de retour mod_magnet : `0`/`nil` = laisser passer, un
  nombre >= 100 = code de statut HTTP final (bloque avec ce code).

Compatibilite d'un script TIERS, inconnu a l'avance (le script fourni
par l'utilisateur n'est qu'un PREMIER exemple concret, pas le seul
script jamais importe) :
- `unsupported_members`/`last_error` (attributs publics, remplis a la
  construction et a chaque appel) donnent la matiere du controle de
  compatibilite statique+dynamique integre a `waf test`/`config check`
  (application/security/simulate_waf_request.py,
  application/config/validate_config.py) - jamais une verification
  cachee qui laisserait un script silencieusement inoperant.
- toute reference `lighty.X` hors de `lighty_compat.
  SUPPORTED_LIGHTY_MEMBERS` reste `nil` cote Lua (jamais une exception
  de construction) - un script bien ecrit degrade via son propre
  fallback `or` (pratique courante mod_magnet), un script qui ne degrade
  pas remonte une erreur a l'execution, capturee par `inspect()` comme
  n'importe quelle autre erreur de script (voir `on_error` ci-dessous).

Modele de confiance (etude §5.3, inchange par cette revision) : le
script est ecrit par l'operateur avance de CE serveur, jamais celui d'un
contenu soumis par un visiteur. Les protections ci-dessous visent la
FIABILITE (un bug ne doit jamais faire planter le serveur), pas la
malveillance :
- `register_eval=False`/`register_builtins=False` : le script ne peut
  pas rappeler Python arbitrairement.
- `max_memory` borne : une fuite memoire dans le script ne peut pas
  degrader tout le processus serveur.
- Toute exception/sortie malformee devient une `WafDecision` de repli
  (`combine_decisions.magnet_fallback_decision`, politique `on_error`),
  JAMAIS une exception qui remonte - `inspect()` ne doit jamais faire
  planter l'appelant.
- Un script hors de delai (timeout) n'est PAS detectable depuis cette
  classe elle-meme (`lupa` n'expose aucun mecanisme d'interruption en
  cours d'execution) : le respect de `options.waf.magnet.timeout_ms`
  est entierement a la charge de l'APPELANT
  (application/security/evaluate_waf_request.py, via
  `asyncio.wait_for(loop.run_in_executor(...))`).
- Constate EMPIRIQUEMENT (tests d'integration, lot E) : `lupa` ne
  libere pas necessairement le GIL pendant l'execution d'un script Lua
  CPU-bound. Ce que `run_in_executor` garantit reellement : la BOUCLE
  ASYNCIO ELLE-MEME ne bloque jamais en attendant un appel magnet - deux
  appels magnet VRAIMENT CONCURRENTS peuvent en revanche se disputer le
  GIL entre eux, meme chacun sur son propre thread du pool."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.combine_decisions import magnet_fallback_decision
from omega_serv.domain.security.waf.config import WafConfig
from omega_serv.domain.security.waf.entities import Severity, WafDecision, WafFinding
from omega_serv.domain.security.waf.exceptions import WafError
from omega_serv.domain.security.waf.lighty_compat import unsupported_lighty_members
from omega_serv.ports.filesystem_port import FilesystemPort

_MAX_LUA_MEMORY_BYTES = 64 * 1024 * 1024


class WafMagnetScriptError(WafError):
    """Le script magnet est syntaxiquement invalide."""


def _severity_for_status(status_code: int) -> tuple[Severity, int]:
    """Convention mod_magnet : le script ne donne qu'un code de statut
    HTTP, jamais de severite explicite - deduite ici du code, memes
    paliers que les reponses natives (403/451 = tentative deliberee,
    429/413/414 = abus de volume, 5xx = le script lui-meme signale une
    erreur interne, tout le reste = faible confiance)."""
    if status_code >= 500:
        return Severity.CRITICAL, 9
    if status_code in (403, 451):
        return Severity.HIGH, 5
    if status_code in (429, 413, 414):
        return Severity.MEDIUM, 2
    return Severity.LOW, 1


class LuaWafAdapter:
    def __init__(self, script_source: str, config: WafConfig, paths: dict[str, str]):
        import lupa  # import local - voir note de tete de module

        self._config = config
        self.unsupported_members: frozenset[str] = unsupported_lighty_members(script_source)
        self.last_error: str | None = None

        self._runtime = lupa.LuaRuntime(
            unpack_returned_tuples=True,
            register_eval=False,
            register_builtins=False,
            max_memory=_MAX_LUA_MEMORY_BYTES,
        )
        self._env_table = self._runtime.table()
        lighty = self._runtime.table()
        lighty["env"] = self._env_table
        lighty["header"] = self._runtime.table()
        lighty["content"] = self._runtime.table()
        lighty["stat"] = self._lua_stat
        self._runtime.globals()["lighty"] = lighty
        self._runtime.globals()["omega_magnet_paths"] = self._runtime.table_from(paths)
        # Reseaux jamais bannis automatiquement (OMEGA-SERV_PLAN-DETAILLE_
        # SENSITIVE_PATHS.md lot 11) : la liste EFFECTIVE du WAF natif (deja
        # calculee par build_waf_collaborators, garde-fou du proxy de confiance
        # compris) - un script qui la lit (omega-waf.lua) n'auto-bannit jamais
        # ces adresses, exactement comme le WAF natif. Un script qui l'ignore
        # garde son comportement : jamais une obligation pour un script importe.
        self._runtime.globals()["omega_never_auto_block"] = self._runtime.table_from(
            list(config.reputation.never_auto_block)
        )

        try:
            self._compiled = self._runtime.compile(script_source)
        except Exception as e:
            raise WafMagnetScriptError(f"erreur de syntaxe du script magnet : {e}") from e

    def _lua_stat(self, path: Any) -> bool | None:
        """`lighty.stat(path)`/`lighty.c.stat(path)` reel : verification
        best-effort, en lecture seule, avec les permissions du processus
        serveur - jamais de levee d'exception cote Lua (le script
        enveloppe deja ses propres appels dans un `pcall`, inutile de
        dupliquer)."""
        if not path:
            return None
        try:
            return True if Path(str(path)).exists() else None
        except OSError:
            return None

    def inspect(self, request: HttpRequest) -> WafDecision:
        """Synchrone, comme l'exige `WafPort` - le dispatch hors du
        thread de la boucle asyncio est la responsabilite de
        l'APPELANT (voir note de tete de module)."""
        try:
            self._update_env(request)
            result = self._compiled()
            self.last_error = None
            return self._decision_from_return_code(result)
        except Exception as e:  # noqa: BLE001 - toute erreur de script devient une decision de repli, jamais une exception qui remonte
            self.last_error = str(e)
            return magnet_fallback_decision(self._config.magnet.on_error, self._config.mode)

    def dry_run(self, request: HttpRequest) -> str | None:
        """Execution REELLE du script (sans filet de repli) a des fins de
        diagnostic UNIQUEMENT (`waf test`/controle de compatibilite a
        l'import) - jamais appelee pour une vraie decision WAF, qui
        passe toujours par `inspect()`. Retourne le message d'erreur si
        le script a leve une exception, None sinon.

        Note : n'appelle PAS `inspect()` en interne pour eviter de faire
        tourner le script deux fois (un script avec etat - compteurs de
        taux, blocklist progressive - ne doit jamais etre execute deux
        fois pour une seule requete simulee)."""
        try:
            self._update_env(request)
            self._compiled()
            return None
        except Exception as e:  # noqa: BLE001
            return str(e)

    def _update_env(self, request: HttpRequest) -> None:
        user_agent = request.header("user-agent")
        body_text = request.body.decode("utf-8", errors="replace") if request.body else None
        self._env_table["request.remote-addr"] = request.remote_ip
        self._env_table["request.remote-ip"] = request.remote_ip
        self._env_table["request.method"] = request.method
        self._env_table["request.uri"] = request.raw_path
        self._env_table["uri.path"] = request.path
        self._env_table["uri.query"] = request.query
        self._env_table["request.user-agent"] = user_agent
        self._env_table["request.body"] = body_text
        # Deliberement absents (toujours nil) - voir lighty_compat.py :
        # "request.body-path" (corps capture en memoire, jamais sur
        # disque) et "physical.path" (pas encore resolu a cette etape).
        self._env_table["request.body-path"] = None
        self._env_table["physical.path"] = None

    def _decision_from_return_code(self, result: Any) -> WafDecision:
        code = int(result) if result else 0
        if code <= 0:
            return WafDecision(action="allow", status_code=None, score=0, log_level="debug")

        severity, weight = _severity_for_status(code)
        action: str = "block"
        status_code: int | None = code
        if self._config.mode != "block":
            # log-only ne bloque JAMAIS (decision a retenir #14) - meme
            # invariant applique au magnet qu'au moteur natif.
            action, status_code = "log", None

        finding = WafFinding(
            rule_id="magnet-external",
            pack="magnet",
            description=f"Script magnet externe : code de retour {code}",
            severity=severity,
            weight=weight,
            scope="path",
        )
        return WafDecision(
            action=action,  # type: ignore[arg-type]
            status_code=status_code,
            score=weight,
            findings=(finding,),
            log_level="warning",
        )


def load_lua_waf_adapter(
    filesystem: FilesystemPort,
    path: Path,
    config: WafConfig,
    resolved_paths: dict[str, str],
) -> LuaWafAdapter:
    """I/O reelle (lecture du fichier) + construction - meme repartition
    que infrastructure/waf/rule_pack_loader.py::load_rule_pack (I/O ici,
    compilation deleguee a `LuaWafAdapter.__init__`). `resolved_paths` :
    chemins ABSOLUS deja resolus par l'appelant (application/server/
    start_server.py, qui connait `project_root`) - cette fonction ne
    resout jamais de chemin relatif elle-meme."""
    if not filesystem.exists(path):
        raise WafMagnetScriptError(f"script magnet introuvable : {path}")
    try:
        source = filesystem.read_text(path)
    except OSError as e:
        raise WafMagnetScriptError(f"impossible de lire {path} : {e}") from e
    return LuaWafAdapter(source, config, resolved_paths)

-- ======================================================================
-- Exemple MINIMAL de script WAF complementaire "magnet" (OMEGA-SERV)
-- ======================================================================
-- Script generique de depart, SANS logique propre a un site particulier
-- (contrairement a un vrai script mod_magnet importe, qui porterait
-- forcement les specificites de son site d'origine - routes dediees,
-- exceptions whitelist, etc., jamais generalisables a l'avance pour
-- n'importe quel autre site). Objectif de ce fichier : montrer la
-- STRUCTURE attendue par le pont `lighty.*` d'omega-serv
-- (infrastructure/waf/lua_waf_adapter.py), pas fournir une protection
-- toute faite.
--
-- Chemin par defaut de `options.waf.magnet.script`
-- (domain/config/entities.py::PathsConfig.waf_script) - remplacez ce
-- fichier par votre propre script importe, ou pointez
-- `options.waf.magnet.script` vers un autre chemin.
--
-- Modele d'execution reel (voir OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md
-- pour l'analyse complete) :
--   - ce fichier est un chunk Lua PLAT (pas de fonction englobante),
--     compile une seule fois puis rappele a chaque requete - toute
--     variable GLOBALE (sans `local`) survit donc entre les appels,
--     utile pour un compteur de rate-limiting ou une liste en memoire.
--   - `lighty.env[...]` expose les attributs de la requete en lecture
--     (cles reellement alimentees par ce pont : voir
--     domain/security/waf/lighty_compat.py::SUPPORTED_ENV_KEYS).
--   - `lighty.header`/`lighty.content` peuvent etre ecrits sans faire
--     planter le script, mais ne sont JAMAIS relus ni renvoyes au
--     visiteur : omega-serv rend toujours sa propre page d'erreur
--     generique, jamais une page fournie par le script.
--   - valeur de retour : `0` (ou `nil`) laisse passer la requete ;
--     un nombre >= 100 devient le code de statut HTTP final (requete
--     bloquee avec ce code).

local lighty_env = lighty.env or {}

-- Chemins personnels DISSOCIES (options.waf.magnet.paths, ecran
-- Active Securite -> WAF -> Magnet) : injectes ici comme table globale
-- `omega_magnet_paths`, avec repli sur un chemin par defaut si absente -
-- c'est la METHODE a reprendre pour adapter un VRAI script importe
-- (seuls les noms de chemins changent d'un script a l'autre).
local omega_paths = omega_magnet_paths or {}
local alerts_log = omega_paths.alerts_log or "var/log/waf-magnet-alerts.log"

-- Exemple de lecture des attributs de requete les plus courants.
local remote_ip = lighty_env["request.remote-addr"] or lighty_env["request.remote-ip"] or "0.0.0.0"
local uri_path  = lighty_env["uri.path"] or "/"
local method    = lighty_env["request.method"] or "GET"

-- Petit utilitaire d'ecriture de log, protege par pcall (une erreur
-- d'ecriture - dossier absent, permissions - ne doit jamais faire
-- planter le script).
local function log_line(line)
  local ok, f = pcall(io.open, alerts_log, "a")
  if not ok or not f then return end
  pcall(function() f:write(os.date("%Y-%m-%d %H:%M:%S") .. " " .. line .. "\n") end)
  pcall(function() f:close() end)
end

-- Toute la logique reelle vit dans un pcall global : une erreur Lua
-- inattendue ne doit jamais faire planter omega-serv, seulement ce
-- script magnet (deja protege cote appelant par `on_error`, mais une
-- erreur capturee ICI reste la plus facile a diagnostiquer).
local ok_main, ret = pcall(function()
  -- Exemple illustratif, a adapter ou retirer : bloque une requete qui
  -- viserait explicitement ce chemin de demonstration.
  if uri_path == "/exemple-waf-magnet-bloque" then
    log_line("EXEMPLE-BLOQUE ip=" .. tostring(remote_ip) .. " method=" .. tostring(method))
    return 403
  end

  -- Aucun blocage par defaut : remplacez ce qui precede par votre
  -- propre logique, ou importez un script existant (voir le guide
  -- d'aide, ecran WAF - Magnet, bouton "Verifier la compatibilite").
  return 0
end)

if not ok_main then
  log_line("LUA-ERROR " .. tostring(ret))
  return 500
end

return ret or 0

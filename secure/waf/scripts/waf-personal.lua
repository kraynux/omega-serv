-- ======================================================================
-- WAF Lighttpd mod_magnet (attract-physical-path-to)
-- Compatible SearXNG (>/, /search) derrière Tailscale
-- Optimisé pour persistance, sécurité Lua, et anti-DoS
-- Version durcie: pcall, load(), tolérance corruption, anti-crash
-- Version corrigée et verifiée mode DEFINITIF (v2, patterns nettoyés):
--  - détection insensible à la casse gérée côté Lua
--
-- COPIE ADAPTEE pour omega-serv (import "magnet", OMEGA-SERV_WAF_LUA_
-- DEPERSONNALISATION.md) - script original intact a ~/DEV/SERV/waf.lua,
-- JAMAIS modifie. La SEULE difference avec l'original : les 5 chemins
-- de la section CONFIGURATION ci-dessous lisent maintenant la table
-- globale `omega_magnet_paths` (injectee par infrastructure/waf/
-- lua_waf_adapter.py depuis options.waf.magnet.paths), avec repli sur
-- les memes valeurs en dur si cette table est absente - toute la
-- logique metier (signatures, rate limiting, escalade, blocklist) est
-- reprise VERBATIM, non reecrite.
-- ======================================================================

-- lighty.env : interface  pour lire les attributs de requête.
-- Ici on la récupère de façon sûre, avec fallback sur table vide,
-- pour éviter un crash si l'environnement n'est pas présent.
local lighty_env = lighty.env or {}

-- =========================
-- CONFIGURATION
-- =========================
local omega_paths = omega_magnet_paths or {}
-- Fichier texte des IP bannies définitivement.
local blocklist_file         = omega_paths.blocklist_file or "/etc/blocklist.txt"
-- Dossier des règles externes, ici utilisé pour whitelist dynamique.
local waf_rules_dir          = omega_paths.rules_dir or "/etc/lighttpd/waf-rules.d/"
-- Journal des alertes WAF (détections, refus, dépassements, etc.).
local alerts_log             = omega_paths.alerts_log or "/var/log/lighttpd/waf-alerts.log"
-- Journal dédié aux ajouts dans la blocklist.
local blocklist_log          = omega_paths.blocklist_log or "/var/log/lighttpd/waf-blocklist.log"
-- Fichier de persistance des compteurs en mémoire (rate limit / récidive).
local rate_store_file        = omega_paths.rate_store_file or "/var/lib/lighttpd/rate_store.lua"  -- Persistance
-- Active l'inspection du corps POST.
local enable_body_inspection = true
-- Active le rate limiting.
local enable_rate_limit      = true
-- Autorise l'ajout automatique à la blocklist.
local enable_auto_block      = true
-- Bascule entre logs texte simples et logs JSON.
local use_json_logs          = false
-- Score minimum pour qu'une requête POST soit bloquée.
local waf_score_threshold    = 5
-- 64 Ko max pour inspection :
-- Limite dure de taille inspectée, évite les abus mémoire/CPU.
local body_max_inspect       = 65536
-- 8 Ko pour lecture par morceaux (anti-DoS mémoire) :
-- Taille de chunk pour lire le body sans tout charger d'un coup.
local chunk_size             = 8192

-- Rate Limiting
-- Limite globale par IP, toutes routes confondues.
local global_rate_max_req    = 60
local global_rate_window     = 60
-- Limite spécifique aux routes SearXNG.
local searx_rate_max_req     = 40
local searx_rate_window      = 60
-- Garde-fou sur la taille max de la query-string.
local searx_max_query_len    = 4096

-- Escalade progressive (récidive)
-- nb de hits avant blocklist définitive
-- Nombre de comportements suspects avant ban définitif.
local suspicious_threshold   = 3
-- fenêtre glissante en secondes
-- Fenêtre de temps sur laquelle on compte les récidives.
local suspicious_window      = 300

-- Intervalles de rafraîchissement des caches fichiers.
-- Évite d'aller relire le fichier de blocklist à chaque requête
local blocklist_refresh_interval = 5   -- secondes
-- Évite d'aller relire la whitelist à chaque appel.
local whitelist_refresh_interval = 15  -- secondes

-- =========================
-- VARIABLES REQUÊTE
-- =========================
-- On extrait les infos utiles de la requête dès le départ.
-- Les fallback successifs rendent le script plus robuste selon les versions
-- ou le contexte d'exécution.
local remote_ip = lighty_env["request.remote-addr"] or lighty_env["request.remote-ip"] or "0.0.0.0"
local uri_path  = lighty_env["uri.path"] or lighty_env["request.uri"] or "/"
local uri_raw   = lighty_env["request.uri"] or uri_path
local method    = lighty_env["request.method"] or "GET"
local query     = lighty_env["uri.query"] or ""
local ua        = lighty_env["request.user-agent"] or "-"

-- =========================
-- OUTILS
-- =========================
-- Supprime les espaces début/fin.
-- Sert au nettoyage des lignes lues depuis les fichiers de règles.
local function trim(s)
  return (s and s:match("^%s*(.-)%s*$")) or ""
end

-- Ouvre un fichier en lecture.
-- Petit wrapper pour centraliser la lecture ligne par ligne.
local function file_lines(path)
  return io.open(path, "r")
end

-- Ajoute une ligne/chaîne en fin de fichier.
-- pcall() sert ici à empêcher qu'une erreur I/O fasse tomber tout le WAF,
-- ce qui est important car Lua tourne dans le process du serveur.
local function append_file(path, line)
  local ok, f = pcall(io.open, path, "a")
  if not ok or not f then return false end
  local okw = pcall(function() f:write(line) end)
  pcall(function() f:close() end)
  return okw
end

-- IMPORTANT: log_line doit être déclaré ICI, AVANT add_to_blocklist qui l'utilise
-- Helper simple pour écrire une ligne de log avec retour à la ligne.
local function log_line(path, line)
  append_file(path, line .. "\n")
end

-- Timestamp lisible pour les logs.
local function now_str()
  return os.date("%Y-%m-%d %H:%M:%S")
end

-- Tronque une chaîne pour les logs et neutralise les retours ligne.
-- Évite de polluer les fichiers log avec des payloads énormes.
local function safe_sub(s, n)
  if not s then return "-" end
  s = tostring(s):gsub("\n", "\\n"):gsub("\r", "\\r")
  if #s <= n then return s end
  return s:sub(1, n) .. "..."
end

-- Wrapper de compatibilité :
-- certaines versions exposent lighty.stat(), d'autres gardent aussi
-- l'ancienne API lighty.c.stat(). On essaye les deux sans changer
-- la logique métier du script.
local function safe_stat(path)
  if not path or path == "" then return nil end
  if type(lighty) == "table" and type(lighty.stat) == "function" then
    return lighty.stat(path)
  end
  if type(lighty) == "table" and type(lighty.c) == "table" and type(lighty.c.stat) == "function" then
    return lighty.c.stat(path)
  end
  return nil
end

-- =========================
-- RECURSIVE URL DECODE (SÉCURISÉ)
-- =========================
-- Décode récursivement les %xx pour attraper les payloads doublement
-- ou triplement encodés.
-- La profondeur est limitée pour éviter boucle, coût CPU, ou crash.
local function recursive_url_decode(str, depth)
  if not str or str == "" then return "" end
  depth = depth or 5  -- Limite à 5 niveaux (anti-crash)
  if depth <= 0 then return str end
  local decoded = str:gsub("%%(%x%x)", function(hex)
    return string.char(tonumber(hex, 16))
  end)
  if decoded == str then return str end
  return recursive_url_decode(decoded, depth - 1)
end

-- Détecte la présence d'un octet NUL, soit encodé (%00), soit brut.
-- Très utile contre les payloads de contournement / confusion parseur.
local function has_nul_byte(s)
  if not s then return false end
  return s:find("%%00", 1, true) ~= nil or s:find("\0", 1, true) ~= nil
end

-- NOTE: pas de : get_file_mtime() .
-- Sa risque de fork "stat -c %Y" via io.popen() à CHAQUE requête pour
-- invalider le cache blocklist. Remplacée par un cache temporel
-- (blocklist_refresh_interval) dans load_blocklist() plus bas.
-- Zéro fork résiduel.

-- =========================
-- LOGGING
-- =========================
-- Enregistre une alerte WAF.
-- Deux formats:
--  - JSON pour ingestion machine / SIEM
--  - texte lisible pour debug humain
-- Les champs sont bornés et échappés pour éviter de casser les logs.
local function pattern_to_str(p)
  if type(p) == "table" then
    return tostring(p.pat or "<pattern-table>")
  end
  return tostring(p or "<pattern>")
end

local function log_alert(ip, score, rules, payload)
  if use_json_logs then
    local rules_str = table.concat(rules or {}, '","')
    local log_entry = string.format(
      '{"timestamp":"%s","ip":"%s","method":"%s","path":"%s","score":%d,"rules":["%s"],"user_agent":"%s","payload":"%s"}\n',
      now_str(),
      tostring(ip or "-"),
      tostring(method or "-"),
      tostring(uri_raw or "-"):gsub('"', '\\"'):gsub("/", "\\/"),
      tonumber(score or 0),
      rules_str,
      tostring(ua or "-"):gsub('"', '\\"'):gsub("\n", "\\n"),
      tostring(payload or ""):gsub('"', '\\"'):gsub("\n", "\\n"):sub(1, 200)
    )
    append_file(alerts_log, log_entry)
  else
    append_file(alerts_log, string.format(
      "[%s] ip=%s method=%s path=%s score=%s ua=%s rules=%s payload=%s\n",
      now_str(),
      tostring(ip or "-"),
      tostring(method or "-"),
      tostring(uri_raw or "-"),
      tostring(score or 0),
      safe_sub(ua, 120),
      table.concat(rules or {}, ","),
      safe_sub(payload, 200)
    ))
  end
end

-- =========================
-- PERSISTENCE RATE STORE
-- =========================
-- last_save = date du dernier flush disque du store.
local last_save = 0
-- last_cleanup est laissé global/réutilisable si déjà présent.
-- Cela évite de perdre l'état entre exécutions si le contexte Lua persiste.
last_cleanup = last_cleanup or 0
-- rate_store est la table mémoire centrale pour:
--  - rate limiting
--  - compteur de récidive
rate_store = rate_store or {}

-- Charge les compteurs depuis le fichier disque.
-- Le fichier stocke du Lua de type "return { ... }", relu via load().
-- pcall + validations protègent contre corruption ou contenu invalide.
local function load_rate_store()
  local f = io.open(rate_store_file, "r")
  if not f then return {} end
  local data = f:read("*a") or ""
  pcall(function() f:close() end)
  if data == "" then return {} end

  local ok, result = pcall(function()
    -- data commence déjà par "return { ... }"
    local func, err = load(data)
    if not func then
      error(err or "load() failed")
    end
    local out = func()
    if type(out) ~= "table" then
      error("rate_store invalid")
    end
    return out
  end)

  if not ok or type(result) ~= "table" then
    return {}
  end
  return result
end

-- On initialise correctement rate_store avec le contenu disque (ou table vide)
rate_store = rate_store or load_rate_store() or {}

-- Sauvegarde les compteurs sur disque sous forme de table Lua.
-- Intérêt:
--  - simple à recharger
--  - pas besoin de parser du JSON
-- On normalise les types pour éviter d'écrire des données incohérentes
local function save_rate_store()
  local ok, f = pcall(io.open, rate_store_file, "w")
  if not ok or not f then return end
  pcall(function() f:write("return {\n") end)
  for k, v in pairs(rate_store) do
    local key = tostring(k):gsub('"', '\\"')
    local count = tonumber(v and v.count or 0) or 0
    local first = tonumber(v and v.first or 0) or 0
    pcall(function()
      f:write(string.format('  ["%s"] = { count = %d, first = %d },\n', key, count, first))
    end)
  end
  pcall(function() f:write("}\n") end)
  pcall(function() f:close() end)
end

-- Nettoyage périodique du store:
--  - supprime les entrées trop anciennes
--  - déclenche au plus toutes les 5 min
--  - profite de ce moment pour persister sur disque, au lieu de le faire
--    à chaque requête
local function cleanup_rate_store()
  local now = os.time()
  if now - last_cleanup < 300 then return end
  last_cleanup = now
  for k, v in pairs(rate_store) do
    if type(v) == "table" and v.first and (now - v.first > 600) then
      rate_store[k] = nil
    end
  end
  if now - (last_save or 0) > 300 then
    save_rate_store()
    last_save = now
  end
end

-- Vérifie si une clé a dépassé sa limite dans une fenêtre donnée.
-- Mécanique:
--  - si la clé n'existe pas, on l'initialise
--  - si la fenêtre est expirée, on repart à 1
--  - sinon on incrémente
-- Retourne true si le quota est dépassé.
local function check_rate_limit(key, max_req, window)
  local now = os.time()
  if not rate_store[key] then
    rate_store[key] = { count = 1, first = now }
    return false
  end
  local e = rate_store[key]
  if type(e) ~= "table" then
    rate_store[key] = { count = 1, first = now }
    return false
  end
  if now - (e.first or now) > window then
    e.count = 1
    e.first = now
    return false
  end
  e.count = (tonumber(e.count) or 0) + 1
  return e.count > max_req
end

-- Enregistre un "hit" suspect pour une IP.
-- C'est une logique d'escalade douce:
--  - 1 hit: alerte / blocage ponctuel
--  - plusieurs hits dans la fenêtre: ban définitif
-- Cela évite de bannir instantanément sur un seul faux positif léger.
local function record_suspicious_hit(ip, reason)
  local key = "susp:" .. tostring(ip or "0.0.0.0")
  local now = os.time()
  if not rate_store[key] then
    rate_store[key] = { count = 1, first = now }
  else
    local e = rate_store[key]
    if type(e) ~= "table" then
      rate_store[key] = { count = 1, first = now }
    elseif now - (e.first or now) > suspicious_window then
      e.count = 1
      e.first = now
    else
      e.count = (tonumber(e.count) or 0) + 1
    end
  end
  if rate_store[key].count >= suspicious_threshold then
    add_to_blocklist(ip, reason .. " (recidive x" .. tostring(rate_store[key].count) .. ")")
    return true
  end
  return false
end

-- =========================
-- BLOCKLIST CACHE (pas de fork stat)
-- =========================
-- Cache mémoire des IP bannies.
-- loaded_at = timestamp du dernier chargement
-- entries   = table set { ["ip"]=true }
local blocklist_cache = { loaded_at = 0, entries = {} }

-- Recharge la blocklist au plus toutes les N secondes.
-- But:
--  - éviter I/O disque et fork shell par requête
--  - garder un effet quasi temps réel
local function load_blocklist()
  local now = os.time()
  if now - blocklist_cache.loaded_at < blocklist_refresh_interval then
    return blocklist_cache.entries
  end
  local blocked = {}
  local f = file_lines(blocklist_file)
  if f then
    for line in f:lines() do
      local ip = trim(line)
      if ip ~= "" and not ip:match("^#") then
        blocked[ip] = true
      end
    end
    pcall(function() f:close() end)
  end
  blocklist_cache.entries = blocked
  blocklist_cache.loaded_at = now
  return blocked
end

-- Ajoute une IP à la blocklist persistante.
-- Fonction globale volontairement, car utilisée depuis plusieurs endroits.
-- Le cache mémoire est mis à jour immédiatement pour que le ban soit actif
-- sans attendre le prochain refresh du fichier.
function add_to_blocklist(ip, reason)
  if not enable_auto_block or not ip or ip == "" then return end
  local blocked = load_blocklist()
  if blocked[ip] then return end
  append_file(blocklist_file, string.format("# %s - %s\n%s\n", now_str(), tostring(reason or ""), tostring(ip)))
  blocked[ip] = true
  -- Mise à jour immédiate du cache en mémoire : un ban déclenché par le
  -- WAF lui-même reste effectif sans attendre le refresh temporel.
  blocklist_cache.entries[ip] = true
  log_line(blocklist_log, string.format("[%s] AJOUT BLOCKLIST ip=%s reason=%s", now_str(), tostring(ip), tostring(reason or "")))
end

-- =========================
-- WHITELIST CACHE (cache temporel, pas de io.open à chaque appel)
-- =========================
-- Cache des regex/patterns de chemins autorisés.
local whitelist_cache = { loaded_at = 0, patterns = {} }

-- Recharge les patterns de whitelist depuis un fichier.
-- Même logique d'optimisation que la blocklist: éviter l'ouverture disque
-- à chaque requête.
local function load_whitelist_patterns()
  local now = os.time()
  if now - whitelist_cache.loaded_at < whitelist_refresh_interval then
    return whitelist_cache.patterns
  end
  local patterns = {}
  local f = file_lines(waf_rules_dir .. "whitelist_paths.txt")
  if f then
    for line in f:lines() do
      local cleaned = trim(line)
      if cleaned ~= "" and not cleaned:match("^#") then
        table.insert(patterns, cleaned)
      end
    end
    pcall(function() f:close() end)
  end
  whitelist_cache.patterns = patterns
  whitelist_cache.loaded_at = now
  return patterns
end

-- Vérifie si un chemin est explicitement autorisé.
-- Il y a:
--  - des exceptions codées en dur
--  - des patterns externes depuis le fichier
-- Le pcall protège d'un pattern invalide côté admin.
local function is_whitelisted_path(path)
  if not path then return false end
  if path:match("^/%.assets/.*/403%.css$") then return true end
  if path:match("^/js%-gallery$") then return true end
  for _, cleaned in ipairs(load_whitelist_patterns()) do
    local ok, matched = pcall(function() return path:match(cleaned) end)
    if ok and matched then
      return true
    end
  end
  return false
end

-- Détermine si l'URL fait partie des endpoints SearXNG à ménager.
-- L'intérêt est d'appliquer une politique spécifique plus permissive
-- sur les recherches légitimes.
local function is_searxng_path(path)
  return path == "/" or
         path == "/search" or
         path == "/search-textfiles" or
         path == "/search-textfiles/" or
         path == "/search-madchat" or
         path == "/search-madchat/" or
         path == "/preferences"
end

-- Extrait un paramètre de query-string sans parser complet.
-- Le décodage est limité à 2 niveaux, suffisant pour beaucoup de cas
-- de double encodage sans coût excessif.
local function get_query_param(name)
  if not query or query == "" then return nil end
  for k, v in query:gmatch("([^&=]+)=?([^&]*)") do
    if k == name then
      return recursive_url_decode(v, 2):gsub("+", " ")
    end
  end
  return nil
end

-- =========================
-- BODY ACCESS (SÉCURISÉ)
-- =========================
-- Récupère le body de la requête de façon défensive.
-- Si le serveur fournit un fichier temporaire (request.body-path), on le lit.
-- Sinon fallback éventuel sur request.body.
-- Lecture par morceaux pour limiter l'impact mémoire d'un gros POST.
local function get_request_body()
  local body_file = lighty_env["request.body-path"]
  if not body_file then
    return lighty_env["request.body"] or "", "body_unavailable"
  end
  local ok, f = pcall(io.open, body_file, "r")
  if not ok or not f then
    return "", "body_unavailable"
  end
  --  Lecture par morceaux
  local body = ""
  while true do
    local chunk = f:read(chunk_size)
    if not chunk then break end
    body = body .. chunk
    if #body > body_max_inspect then
      pcall(function() f:close() end)
      return body, "body_too_large"
    end
  end
  pcall(function() f:close() end)
  return body, nil
end

-- =========================
-- SIGNATURES
-- =========================
-- Base de signatures.
-- Chaque sous-table correspond à une famille d'attaque:
--  - sqli_body        : injections SQL
--  - xss_body         : JavaScript / HTML injecté
--  - cmdi_body        : injection de commandes système
--  - path_traversal   : accès fichiers / chemins sensibles
-- On n'utilise pas de  pseudo-PCRE (?i) ici.
-- L'insensibilité à la casse est gérée via un flag "ci = true" dans les tables.
local patterns = {
  sqli_body = {
    { pat = "union%s+select",                 ci = true },
    { pat = "select%s+.-%s+from",             ci = true },
    { pat = "insert%s+into",                  ci = true },
    { pat = "drop%s+table",                   ci = true },
    { pat = "or%s+%d+%s*=%s*%d+",             ci = true },
    { pat = ";%s*drop%f[%A]",                 ci = true },
    { pat = ";%s*alter%f[%A]",                ci = true },
    { pat = ";%s*exec%f[%A]",                 ci = true },
    { pat = ";%s*shutdown%f[%A]",             ci = true },
    { pat = "or%s+1=1",                       ci = true },
    { pat = "'%s*or%s+'1'='1",                ci = true },
    { pat = "sleep%s*%(",                     ci = true },
    { pat = "benchmark%s*%(",                 ci = true }
  },
  xss_body = {
    { pat = "<script[^>]*>",   ci = true },
    { pat = "javascript%s*:",  ci = true },
    { pat = "on%w+%s*=",       ci = true },
    { pat = "<iframe",         ci = true },
    { pat = "eval%s*%(",       ci = true },
    { pat = "document%.cookie",ci = true },
    { pat = "onerror%s*=",     ci = true },
    { pat = "onload%s*=",      ci = true },
    { pat = "svg/onload",      ci = true }
  },
  cmdi_body = {
    { pat = ";%s*ls%f[%W]",       ci = true },
    { pat = ";%s*id%f[%W]",       ci = true },
    { pat = ";%s*whoami%f[%W]",   ci = true },
    { pat = ";%s*cat%f[%W]",      ci = true },
    { pat = ";%s*wget%f[%W]",     ci = true },
    { pat = ";%s*curl%f[%W]",     ci = true },
    { pat = ";%s*nc%f[%W]",       ci = true },
    { pat = ";%s*netcat%f[%W]",   ci = true },
    { pat = ";%s*bash%f[%W]",     ci = true },
    { pat = ";%s*sh%f[%W]",       ci = true },
    { pat = ";%s*python%f[%W]",   ci = true },

    { pat = "|%s*ls%f[%W]",       ci = true },
    { pat = "|%s*id%f[%W]",       ci = true },
    { pat = "|%s*whoami%f[%W]",   ci = true },
    { pat = "|%s*cat%f[%W]",      ci = true },

    -- backticks et $(...)
    { pat = "`[^`]+`",            ci = false },
    { pat = "%$%([^)]+%)",        ci = false },

    -- balise PHP et fonctions d'exec
    { pat = "<%?php",             ci = true },
    { pat = "system%s*%(",        ci = true },
    { pat = "exec%s*%(",          ci = true },
    { pat = "passthru%s*%(",      ci = true }
  },
  path_traversal = {
    { pat = "%.%.%/",        ci = false },
    { pat = "%.%.\\",        ci = false },
    { pat = "/proc/self/",   ci = true  },
    { pat = "etc/passwd",    ci = true  },
    { pat = "etc/shadow",    ci = true  },
    { pat = "file://",       ci = true  },
    { pat = "php://filter",  ci = true  }
  }
}

-- Signatures spécifiques User-Agent.
-- Le but ici est de filtrer les outils de scan, scrapers et bots non souhaités
-- très tôt dans le pipeline, sans attendre une payload malveillante.
local patterns_scanner_ua = {
  { pat = "masscan",             ci = true },
  { pat = "sqlmap",              ci = true },
  { pat = "nmap",                ci = true },
  { pat = "python%-requests",    ci = true },
  { pat = "nikto",               ci = true },
  { pat = "dirbuster",           ci = true },
  { pat = "wfuzz",               ci = true },
  { pat = "zgrab",               ci = true },
  { pat = "morfeus",             ci = true },
  { pat = "libwww",              ci = true },
  { pat = "go%-http%-client",    ci = true },
  { pat = "ahrefsbot",           ci = true },
  { pat = "mj12bot",             ci = true },
  { pat = "semrushbot",          ci = true },
  { pat = "blexbot",             ci = true },
  { pat = "dotbot",              ci = true },
  { pat = "spbot",               ci = true },
  { pat = "yandexbot",           ci = true },
  { pat = "sogoubot",            ci = true },
  { pat = "spider",              ci = true },
  { pat = "crawler",             ci = true },
  { pat = "bot",                 ci = true },
  { pat = "scraper",             ci = true },
  { pat = "facebookexternalhit", ci = true },
  { pat = "lwp::simple",         ci = true }
}

-- =========================
-- PATHS SENSIBLES SURVEILLÉS
-- =========================
local sensitive_path_patterns = {
  "^/%.env/?$",
  "^/%.env%..+",
  "^/%.git/?",
  "^/%.git%..+",
  "^/%.git%-config/?",
  "^/%.git%-config%..+",
  "^/%.svn/?",
  "^/%.hg/?",
  "^/%.bzr/?",
  "^/composer%.json$",
  "^/composer%.lock$",
  "^/vendor/?",
  "^/phpunit/?",
  "^/phpmyadmin/?",
  "^/%phpmyadmin%..+",
  "^/pma/?",
  "^/adminer%.php$",
  "^/%adminer%..+",
  "^/wp%-admin/?",
  "^/%wp%-admin%..+",
  "^/wp%-login%.php$",
  "^/%wp%-login%.php%..+",
  "^/server%-status/?$",
  "^/%.DS_Store$"
}

local function is_sensitive_path(path)
  if not path or path == "" then return false, nil end
  local decoded = recursive_url_decode(path, 2)
  for _, pat in ipairs(sensitive_path_patterns) do
    local ok, matched = pcall(function() return decoded:match(pat) end)
    if ok and matched then
      return true, pat
    end
  end
  return false, nil
end

-- Génération de la page HTML en cas d'acces en premier avertissemnt avant BAN
local function respond_sensitive_warning(path, exists)
  local exists_txt = exists and "oui" or "non"
  lighty.header["Content-Type"] = "text/html; charset=utf-8"
  lighty.content = { string.format([[
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="/.assets/css/403.css">
    <title>403 - Accès refusé</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0a0e1a;
            color: #e0e0e0;
            font-family: monospace;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: #0f1320;
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            max-width: 560px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }
        .code { font-size: 5rem; color: #00d4ff; font-weight: bold; }
        .title { font-size: 1.5rem; margin: 20px 0; }
        .msg { color: #9098a5; margin-bottom: 18px; }
        .path {
            color: #c7d0dd;
            background: #0a0e1a;
            border: 1px solid #2a2e3a;
            border-radius: 8px;
            padding: 10px 12px;
            margin: 14px 0;
            word-break: break-all;
        }
        .meta {
            color: #7f8896;
            font-size: 0.9rem;
            margin-bottom: 24px;
        }
        a { color: #00d4ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        hr { border: none; height: 1px; background: #2a2e3a; margin: 20px 0; }
        .footer { font-size: 0.7rem; color: #606878; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="code">403</div>
        <div class="title">Accès refusé</div>
        <div class="msg">? Accès non autorisé à ce chemin ou ressource</div>
        <div class="msg">Cette page apparait pour avertissement ! </div>
        <div class="msg">? Soyez plus prudent avant le <span style="color: red;">BAN</span></div>
        <div class="path">%s</div>
        <div class="meta">Présence physique détectée : %s</div>
        <hr>
        <a href="/">?  Retour à l'index</a>
        <div class="footer">Lighttpd · OMEGA-Serveur</div>
    </div>
</body>
</html>
  ]], tostring(path or "-"), exists_txt) }
  return 403
end

-- detect_patterns: détection générique avec option insensible à la casse.
-- On NE modifie PAS les patterns Lua (pas de :lower() dessus) pour
-- ne pas casser les classes (%w, %W, %u, %U, etc.) ni les %f[].
-- Chaque entrée de pattern_list est:
--   - soit une string (match sensible à la casse)
--   - soit une table { pat = "motif", ci = true } pour case-insensitive.
local function detect_patterns(content, pattern_list)
  if not content or content == "" or not pattern_list then
    return false, nil
  end

  local s = tostring(content)
  local s_lower = s:lower()

  for _, entry in ipairs(pattern_list) do
    local pat, ci

    if type(entry) == "string" then
      pat = entry
      ci  = false
    elseif type(entry) == "table" then
      pat = entry.pat
      ci  = not not entry.ci
    else
      goto continue
    end

    if type(pat) ~= "string" or pat == "" then
      goto continue
    end

    local search_s = ci and s_lower or s

    local ok, matched = pcall(function()
      return search_s:match(pat)
    end)

    if ok and matched then
      return true, entry
    end

    ::continue::
  end

  return false, nil
end

-- =========================
-- LOGIQUE PRINCIPALE
-- =========================
-- Le coeur du WAF est encapsulé dans un pcall global.
-- Si n'importe quel bloc plante, on log l'erreur et on renvoie 500
-- au lieu de faire tomber le serveur ou laisser le script casser le flux.
-- mod_magnet considère 0 comme "continuer" et >=200 comme statut final HTTP.
local ok_main, ret = pcall(function()
  -- 1. blocklist
  -- Vérification prioritaire: si IP bannie, on coupe très tôt.
  local blocked = load_blocklist()
  -- Cas particulier: une IP bannie peut encore accéder à un chemin whitelisté.
  -- C'est utile pour servir une ressource précise, page d'erreur, CSS, etc.
  if blocked[remote_ip] and is_whitelisted_path(uri_path) then
    return 0
  end

  -- IP bannie et pas whitelistée: refus immédiat.
  if blocked[remote_ip] then
    log_alert(remote_ip, 10, {"BLOCKLIST-HIT"}, "")
    return 451
  end

  -- 1bis. paths sensibles surveillés
  do
    local found, pat = is_sensitive_path(uri_path)
    if found then
      local physical = lighty_env["physical.path"]
      local exists = false

      if physical and physical ~= "" then
        local ok, st = pcall(function() return safe_stat(physical) end)
        exists = ok and st and true or false
      end

      local escalated = record_suspicious_hit(
        remote_ip,
        "SENSITIVE-PATH:" .. tostring(pat) .. " exists=" .. tostring(exists)
      )

      log_alert(
        remote_ip,
        escalated and 10 or 4,
        { "SENSITIVE-PATH:" .. tostring(pat), "EXISTS:" .. tostring(exists) },
        uri_path
      )

      if escalated then
        return 451
      end

      return respond_sensitive_warning(uri_path, exists)
    end
  end

  -- 1ter. scanners / bots (User-Agent) avec escalade progressive
  -- Filtrage précoce des User-Agent connus comme scanners/bots.
  -- Première détection: 403
  -- Récidive: ban + 451
  do
    local found, pat = detect_patterns(ua, patterns_scanner_ua)
    if found then
      local rule = "SCANNER-UA:" .. pattern_to_str(pat)
      local escalated = record_suspicious_hit(remote_ip, rule)
      log_alert(remote_ip, escalated and 10 or 3, { rule }, ua)
      if escalated then
        return 451
      end
      return 403
    end
  end

  -- 2. rate limit global
  -- Limiteur global, indépendant du type de route.
  -- cleanup_rate_store() est appelé ici pour mutualiser le ménage périodique.
  if enable_rate_limit then
    cleanup_rate_store()
    if check_rate_limit("g:" .. remote_ip, global_rate_max_req, global_rate_window) then
      log_alert(remote_ip, 3, {"RATE-LIMIT-GLOBAL"}, "")
      return 429
    end
  end

  -- 3. politique dédiée SearXNG
  -- Les routes SearXNG sont traitées à part pour éviter les faux positifs.
  -- Une recherche utilisateur peut contenir des mots ou motifs "dangereux"
  -- sans intention malveillante.
  if is_searxng_path(uri_path) then
    local q = get_query_param("q") or ""
    -- Rate limit spécifique SearXNG, distinct du global.
    if enable_rate_limit then
      if check_rate_limit("sx:" .. remote_ip, searx_rate_max_req, searx_rate_window) then
        log_alert(remote_ip, 2, {"RATE-LIMIT-SEARXNG"}, q)
        return 429
      end
    end

    -- Garde-fou sur query-string trop grosse.
    if #query > searx_max_query_len then
      log_alert(remote_ip, 2, {"SEARXNG-QUERY-TOO-LARGE"}, query)
      return 414
    end

    -- Rejet des octets NUL, souvent utilisés pour obfuscation/contournement.
    if has_nul_byte(query) or has_nul_byte(q) then
      log_alert(remote_ip, 4, {"SEARXNG-NUL-BYTE"}, query)
      return 451
    end

    -- Important: sortie immédiate pour les routes SearXNG.
    -- Donc les tests agressifs plus bas sur path/query n'impacteront pas
    -- les recherches légitimes.
    return 0
  end

  -- 3bis. protection du path lui-même (SQLi/XSS/Traversal dans l'URL)
  -- Placé APRÈS l'étape 3 pour ne jamais impacter les recherches SearXNG légitimes.
  -- On ne fait PAS de CMDI sur le path (évite les faux positifs *.php).
  do
    local decoded_path = recursive_url_decode(uri_path, 2)

    -- SQLi dans le path
    local found, pat = detect_patterns(decoded_path, patterns.sqli_body)
    if found then
      local rule = "PATH-SQLI:" .. pattern_to_str(pat)
      log_alert(remote_ip, 5, { rule }, uri_path)
      record_suspicious_hit(remote_ip, rule)
      return 451
    end

    -- XSS dans le path
    found, pat = detect_patterns(decoded_path, patterns.xss_body)
    if found then
      local rule = "PATH-XSS:" .. pattern_to_str(pat)
      log_alert(remote_ip, 5, { rule }, uri_path)
      record_suspicious_hit(remote_ip, rule)
      return 451
    end

    -- PAS de CMDI sur le path, pour éviter de prendre "*.php" comme "<?php"

    -- Traversal dans le path
    found, pat = detect_patterns(decoded_path, patterns.path_traversal)
    if found then
      local rule = "PATH-TRAVERSAL:" .. pattern_to_str(pat)
      log_alert(remote_ip, 4, { rule }, uri_path)
      record_suspicious_hit(remote_ip, rule)
      return 451
    end
  end

  -- 4. protection légère query-string
  -- Inspection plus légère de la query-string hors SearXNG.
  -- Ici le script cherche surtout traversal et NUL byte,
  -- moins risqués en faux positifs que SQLi/XSS sur un moteur de recherche.
  if query and query ~= "" then
    local decoded = recursive_url_decode(query, 2)
    local found, pat = detect_patterns(decoded, patterns.path_traversal)
    if found then
      local rule = "QUERY-PATH-TRAVERSAL:" .. pattern_to_str(pat)
      log_alert(remote_ip, 4, { rule }, query)
      return 451
    end
    if has_nul_byte(decoded) then
      log_alert(remote_ip, 4, {"QUERY-NUL-BYTE"}, query)
      return 451
    end
  end

  -- 5. inspection POST
  -- Inspection du corps HTTP uniquement sur POST.
  -- On ne lit pas systématiquement tous les bodies pour limiter le coût.
  if enable_body_inspection and method == "POST" then
    local body, err = get_request_body()
    -- Body trop volumineux pour inspection: refus direct.
    -- Ici la logique privilégie la sécurité et la protection ressource.
    if err == "body_too_large" then
      log_alert(remote_ip, 2, {"BODY-TOO-LARGE"}, "")
      return 413
    end
    -- Si le body est indisponible, on ne casse pas la requête.
    if err == "body_unavailable" then
      return 0
    end

    if body and #body > 0 then
      -- Score cumulé WAF.
      -- Chaque famille d'attaque ajoute un poids.
      local waf_score = 0
      local triggered = {}

      local found, pat = detect_patterns(body, patterns.sqli_body)
      if found then
        waf_score = waf_score + 5
        table.insert(triggered, "SQLI:" .. pattern_to_str(pat))
      end

      found, pat = detect_patterns(body, patterns.xss_body)
      if found then
        waf_score = waf_score + 5
        table.insert(triggered, "XSS:" .. pattern_to_str(pat))
      end

      found, pat = detect_patterns(body, patterns.cmdi_body)
      if found then
        waf_score = waf_score + 5
        table.insert(triggered, "CMDI:" .. pattern_to_str(pat))
      end

      found, pat = detect_patterns(body, patterns.path_traversal)
      if found then
        waf_score = waf_score + 3
        table.insert(triggered, "TRAVERSAL:" .. pattern_to_str(pat))
      end

      -- Décision basée sur score.
      -- Intérêt du scoring:
      --  - plusieurs petits signaux peuvent suffire
      --  - permet une réponse graduée
      if waf_score >= waf_score_threshold then
        log_alert(remote_ip, waf_score, triggered, body)
        -- Si score élevé, ban immédiat.
        -- Sinon seulement hit suspect pour escalade progressive.
        if waf_score >= 8 then
          add_to_blocklist(remote_ip, "WAF score " .. tostring(waf_score))
        else
          record_suspicious_hit(remote_ip, "WAF score " .. tostring(waf_score))
        end
        return 451
      end
    end
  end

  -- pas d'appel "save_rate_store()" sinon Il réécrit tout le fichier rate_store.lua à CHAQUE
  -- requête non bloquée, doublon du throttle déjà géré par
  -- cleanup_rate_store() (appelé à l'étape 2, save toutes les 300s max).
  -- La persistance reste assurée par cleanup_rate_store() uniquement.
  -- Aucun blocage: continue le traitement normal.
  return 0
end)

-- Si une erreur Lua non prévue survient, sa log puis renvoie 500.
-- Cela évite qu'un bug du WAF se transforme en comportement silencieux.
if not ok_main then
  log_line(alerts_log, string.format("[%s] LUA-ERROR %s", now_str(), tostring(ret)))
  return 500
end

-- Retour final :
--  - 0 => continuer le pipeline
--  - code HTTP => réponse finale immédiate
return ret or 0

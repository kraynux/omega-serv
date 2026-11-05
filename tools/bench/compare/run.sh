#!/bin/bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Mesure UNE configuration (docs/comparatif-serveurs-web.md) - outil de developpement.
#   tools/bench/compare/run.sh DOSSIER <nginx-N|lighttpd-N|caddy-N|apache-N|omega-vX-N-WAF[-native]>
#   ex. omega-v2-2-1 = omega-serv 2.0, 2 workers, WAF actif ; N = processus (Caddy : GOMAXPROCS)
#   suffixe -native : moteur natif C++ (N = processus de securite Python), sinon moteur Python
# Serveur epingle sur SRV_CPUS, client oha sur CLI_CPUS (par defaut : un cœur physique chacun,
# a adapter a la topologie : lscpu -e). Affiche req/s, Mo/s, p50, p99 (ms), puis la memoire PSS.
W=$(readlink -f "$1"); name=$2
SERV=$(readlink -f "$(dirname "$(readlink -f "$0")")/../../.."); PY=${OMEGA_PY:-$SERV/.venv/bin/python}
SRV="taskset -c ${SRV_CPUS:-0,2}"; CLI="taskset -c ${CLI_CPUS:-1,3}"
omega_cfg() { # version workers waf [native]
  local extra="" waf='{}'
  [ "$1" != v1 ] && extra=", \"workers\": $2"  # toute version sauf v1 (2026-11-02 : sinon boost auto, workers orphelins)
  [ "${4:-}" = native ] && extra="$extra, \"engine\": \"native\""
  # WAF : 0 = coupe, 1 = actif sans rate limit (campagne du 26/10), 2 = actif AVEC rate limit (lot 0 du plan
  # moteur C++, 2026-11-02) : limite de 10^9 req/min, jamais atteinte - mesure le seul cout du comptage.
  local rl='{"enabled": false}'
  [ "$3" = 2 ] && rl='{"enabled": true, "global": {"requests": 1000000000, "window_seconds": 60}}'
  [ "$3" != 0 ] && waf="{\"waf\": {\"enabled\": true, \"mode\": \"block\", \"rules\": {\"paths\": [$(cd "$W/omega-$1" && ls secure/waf/rules/*.json | sed 's/.*/"&"/' | paste -sd,)]}, \"rate_limit\": $rl}}"
  echo "{\"version\": 1, \"profile\": \"standard\", \"server\": {\"bind\": \"127.0.0.1\", \"port\": 18954, \"max_connections\": 1024, \"max_keepalive_requests\": 100000$extra}, \"options\": $waf}" > "$W/omega-$1/config/omega-serve.json"
  # OMEGA_EXTRA_OPTIONS=fichier.json : options fusionnees (routage realiste, lot 0 du plan moteur C++)
  [ -n "${OMEGA_EXTRA_OPTIONS:-}" ] && python3 - "$W/omega-$1/config/omega-serve.json" "$OMEGA_EXTRA_OPTIONS" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1])); cfg["options"].update(json.load(open(sys.argv[2])))
json.dump(cfg, open(sys.argv[1], "w"))
PY
}
case $name in
  nginx-*) sed "s/WORKERS/${name#nginx-}/" "$W/nginx.conf" > "$W/nginx/run.conf"
     $SRV nginx -p "$W/nginx" -c "$W/nginx/run.conf" -e "$W/logs/nginx-error.log" -g "daemon off;" & pid=$!; port=18951;;
  lighttpd-*) sed "s/MAXWORKER/${name#lighttpd-}/" "$W/lighttpd.conf" > "$W/lighttpd.run.conf"
     $SRV lighttpd -D -f "$W/lighttpd.run.conf" & pid=$!; port=18952;;
  caddy-*) HOME=$W GOMAXPROCS=${name#caddy-} $SRV caddy run --config "$W/Caddyfile" --adapter caddyfile > "$W/logs/caddy.out" 2>&1 & pid=$!; port=18953;;
  apache-*) n=${name#apache-}; sed -e "s/MAXRW/$((n * 64))/g" -e "s/WORKERS/$n/g" "$W/apache.conf" > "$W/apache.run.conf"
     $SRV httpd -DFOREGROUND -f "$W/apache.run.conf" > "$W/logs/apache.out" 2>&1 & pid=$!; port=18955;;
  omega-*) IFS=- read -r _ v w waf eng <<< "$name"; omega_cfg "$v" "$w" "$waf" "$eng"
     pp=$W/omega-$v/src; [ -e "$W/omega-$v/omega-lib" ] && pp=$W/omega-$v/omega-lib:$pp
     (cd "$W/omega-$v" && PYTHONPATH=$pp exec $SRV "$PY" -m omega_serv --config config/omega-serve.json serve > "$W/logs/omega.out" 2>&1) & pid=$!; port=18954;;
  *) echo "configuration inconnue : $name" >&2; exit 2;;
esac
for _ in $(seq 100); do curl -s -o /dev/null "http://127.0.0.1:$port/small.html" && break; sleep 0.2; done
sleep 2
pss() { local total=0 p; for p in $(pstree -p -T "$1" | grep -o '([0-9]*)' | tr -d '()'); do total=$((total + $(awk '/^Pss:/{print $2}' "/proc/$p/smaps_rollup" 2>/dev/null || echo 0))); done; echo $((total / 1024)); }
idle=$(pss $pid)
for f in small.html:32 medium.png:32 large.bin:8; do
  path=${f%:*}; conc=${f#*:}
  $CLI oha -z "${DUR:-10}s" -c "$conc" --no-tui --output-format json "http://127.0.0.1:$port/$path" > "$W/oha.json" 2>/dev/null
  python3 - "$name" "$path" "$W/oha.json" <<'PY'
import json, sys
name, path, f = sys.argv[1:]
d = json.load(open(f)); s = d["summary"]; p = d["latencyPercentiles"]
bad = sum(v for k, v in d.get("statusCodeDistribution", {}).items() if k != "200")
print(f"{name:<22} {path:<12}{s['requestsPerSec']:>9.0f}{s['sizePerSec']/1e6:>9.1f}{p['p50']*1000:>8.1f}{p['p99']*1000:>8.1f}{bad:>7}")
PY
done
echo "$name PSS_Mo repos=$idle apres_charge=$(pss $pid)"
kill -TERM $pid 2>/dev/null; wait $pid 2>/dev/null; sleep 2

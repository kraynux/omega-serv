#!/bin/bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Mesure UNE configuration de reverse proxy (plan proxy natif v2, lot 11) - outil de developpement.
#   tools/bench/proxy/run.sh DOSSIER <nginx-N|lighttpd-N|caddy-N|apache-N|traefik-N|omega-py-N-WAF|omega-nat-N-WAF>[-tls]
#   omega-py-2-0 = moteur Python, 2 processus, WAF coupe ; omega-nat-1-1 = moteur natif, 1 processus de securite, WAF
#   actif (toutes les regles livrees, sans limite de debit) ; suffixe -tls : HTTPS cote client (backend toujours en
#   HTTP). Le backend (campaign.sh) doit deja tourner sur 127.0.0.1:18960.
# Proxy epingle sur SRV_CPUS, client oha sur CLI_CPUS (le backend partage les coeurs du client : decision de
# l'auteur du 2026-11-14). OMEGA_PY : interpreteur (defaut : .venv du depot) ; OMEGA_EXTRA_PATH : chemins Python
# ajoutes devant (ex. omega-lib/src d'une machine de banc). Affiche req/s, Mo/s, p50, p99 (ms), reponses non 200, puis la memoire PSS du proxy.
W=$(readlink -f "$1"); name=$2
SERV=$(readlink -f "$(dirname "$(readlink -f "$0")")/../../.."); PY=${OMEGA_PY:-$SERV/.venv/bin/python}
SRV="taskset -c ${SRV_CPUS:-0,2}"; CLI="taskset -c ${CLI_CPUS:-1,3}"
base=${name%-tls}; tls=0; [ "$base" != "$name" ] && tls=1
scheme=http; [ $tls = 1 ] && scheme=https
omega_cfg() { # moteur workers waf
  local engine=python; [ "$1" = nat ] && engine=native
  local waf='"waf": {"enabled": false}'
  [ "$3" = 1 ] && waf="\"waf\": {\"enabled\": true, \"mode\": \"block\", \"rules\": {\"paths\": [$(cd "$W/omega" && ls secure/waf/rules/*.json | sed 's/.*/"&"/' | paste -sd,)]}, \"rate_limit\": {\"enabled\": false}}"
  local tlscfg='"tls": {"enabled": false}'
  [ $tls = 1 ] && tlscfg='"tls": {"enabled": true, "mode": "direct", "certificate": {"certificate_path": "secure/certs/cert.pem", "private_key_path": "secure/certs/key.pem"}}'
  cat > "$W/omega/config/omega-serve.json" <<JSON
{"version": 1, "profile": "standard",
 "server": {"bind": "127.0.0.1", "port": 18954, "max_connections": 1024, "max_keepalive_requests": 100000,
            "workers": $2, "engine": "$engine"},
 $tlscfg,
 "options": {$waf, "reverse_proxy": {"enabled": true, "zones": [
   {"url_prefix": "/", "upstreams": [{"host": "127.0.0.1", "port": 18960}]}]}}}
JSON
}
case $base in
  nginx-*) listen="listen 127.0.0.1:18951;"; [ $tls = 1 ] && listen="listen 127.0.0.1:18951 ssl;"
     sed -e "s/WORKERS/${base#nginx-}/" -e "s/LISTEN/$listen/" "$W/nginx.conf" > "$W/nginx/run.conf"
     $SRV nginx -p "$W/nginx" -c "$W/nginx/run.conf" -e "$W/logs/nginx-error.log" -g "daemon off;" & pid=$!; port=18951;;
  lighttpd-*) eng=disable; [ $tls = 1 ] && eng=enable
     sed -e "s/MAXWORKER/${base#lighttpd-}/" -e "s/PORT/18952/" -e "s/\"TLS\"/\"$eng\"/" "$W/lighttpd.conf" > "$W/lighttpd.run.conf"
     $SRV lighttpd -D -f "$W/lighttpd.run.conf" & pid=$!; port=18952;;
  caddy-*) site="http://127.0.0.1:18953"; line=""
     [ $tls = 1 ] && site="https://127.0.0.1:18953" && line="tls $W/tls/cert.pem $W/tls/key.pem"
     sed -e "s#SITE#$site#" -e "s#TLSLINE#$line#" "$W/Caddyfile" > "$W/Caddyfile.run"
     HOME=$W GOMAXPROCS=${base#caddy-} $SRV caddy run --config "$W/Caddyfile.run" --adapter caddyfile > "$W/logs/caddy.out" 2>&1 & pid=$!; port=18953;;
  apache-*) n=${base#apache-}; ssl=off; [ $tls = 1 ] && ssl=on
     sed -e "s/MAXRW/$((n * 64))/g" -e "s/WORKERS/$n/g" -e "s/PORT/18955/" -e "s/SSLSWITCH/$ssl/" "$W/apache.conf" > "$W/apache.run.conf"
     $SRV httpd -DFOREGROUND -f "$W/apache.run.conf" > "$W/logs/apache.out" 2>&1 & pid=$!; port=18955;;
  traefik-*) block=""; [ $tls = 1 ] && block="[http.routers.all.tls]"
     sed -e "s/TLSBLOCK/$block/" "$W/traefik-dyn.toml" > "$W/traefik-dyn.run.toml"
     sed -e "s/PORT/18956/" "$W/traefik.toml" > "$W/traefik.run.toml"
     GOMAXPROCS=${base#traefik-} $SRV "$W/traefik" --configFile="$W/traefik.run.toml" > "$W/logs/traefik.out" 2>&1 & pid=$!; port=18956;;
  omega-*) IFS=- read -r _ eng w waf <<< "$base"; omega_cfg "$eng" "$w" "$waf"
     (cd "$W/omega" && PYTHONPATH=${OMEGA_EXTRA_PATH:+$OMEGA_EXTRA_PATH:}$W/omega/src exec $SRV "$PY" -m omega_serv --config config/omega-serve.json serve > "$W/logs/omega.out" 2>&1) & pid=$!; port=18954;;
  *) echo "configuration inconnue : $name" >&2; exit 2;;
esac
url="$scheme://127.0.0.1:$port"
for _ in $(seq 150); do [ "$(curl -sk -o /dev/null -w '%{http_code}' "$url/small.html")" = 200 ] && break; sleep 0.2; done
sleep 2
curl -sk -D - -o /dev/null "$url/small.html" | grep -qi '^x-backend: 1' || echo "$name ATTENTION : reponse sans X-Backend (pas relayee ?)"
pss() { local total=0 p; for p in $(pstree -p -T "$1" | grep -o '([0-9]*)' | tr -d '()'); do total=$((total + $(awk '/^Pss:/{print $2}' "/proc/$p/smaps_rollup" 2>/dev/null || echo 0))); done; echo $((total / 1024)); }
idle=$(pss $pid)
for f in small.html:32 medium.png:32; do
  path=${f%:*}; conc=${f#*:}
  $CLI oha -z "${DUR:-10}s" -c "$conc" --insecure --no-tui --output-format json "$url/$path" > "$W/oha.json" 2>/dev/null
  python3 - "$name" "$path" "$W/oha.json" <<'PY'
import json, sys
name, path, f = sys.argv[1:]
d = json.load(open(f)); s = d["summary"]; p = d["latencyPercentiles"]
bad = sum(v for k, v in d.get("statusCodeDistribution", {}).items() if k != "200")
bad += sum(v for k, v in d.get("errorDistribution", {}).items() if "deadline" not in k)  # erreurs de connexion
print(f"{name:<22} {path:<12}{s['requestsPerSec']:>9.0f}{s['sizePerSec']/1e6:>9.1f}{(p['p50'] or 0)*1000:>8.1f}{(p['p99'] or 0)*1000:>8.1f}{bad:>7}")
PY
done
echo "$name PSS_Mo repos=$idle apres_charge=$(pss $pid)"
kill -TERM $pid 2>/dev/null; wait $pid 2>/dev/null; sleep 2

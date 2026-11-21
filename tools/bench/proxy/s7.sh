#!/bin/bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Mesure du §7 du plan proxy natif v2 (lot 11, decision de l'auteur du 2026-11-14 : « on mesure tout ») - outil de
# developpement. Dossier deja prepare par setup.sh (meme machine, memes coeurs que campaign.sh).
#   SRV_CPUS=0,2 CLI_CPUS=1,3 tools/bench/proxy/s7.sh DOSSIER > s7-resultats.txt
# Pour chaque proxy (natif, natif + WAF, moteur Python, nginx) : debit seul et CPU par requete (natif et Python
# separes) ; clients lents (lecture, tete, corps) avec et sans trafic normal ; reponses chunked longues (rapides et
# lentes, corps verifie) ; envois de fichiers de 1 et 8 Mo ; keep-alive qui melange statique et proxy ; descripteurs
# et connexions avant et apres (fuite, connexion bloquee) ; CPU pendant l'attente seule (boucle a vide).
W=$(readlink -f "$1")
HERE=$(dirname "$(readlink -f "$0")"); SERV=$(readlink -f "$HERE/../../.."); PY=${OMEGA_PY:-$SERV/.venv/bin/python}
SRV="taskset -c ${SRV_CPUS:-0,2}"; CLI="taskset -c ${CLI_CPUS:-1,3}"
C="$CLI python3 $HERE/s7_clients.py"
PORT=18957

# ---------------------------------------------------------------- fichiers et backend
[ -f "$W/www/big10.bin" ] || head -c 10000000 /dev/urandom > "$W/www/big10.bin"
[ -f "$W/www/big100.bin" ] || head -c 100000000 /dev/urandom > "$W/www/big100.bin"
[ -f "$W/up1.bin" ] || head -c 1000000 /dev/urandom > "$W/up1.bin"
[ -f "$W/up8.bin" ] || head -c 8000000 /dev/urandom > "$W/up8.bin"
# lot 11 (F2) : meme taille, signature PNG en tete (un vrai fichier image, pour le WAF)
[ -f "$W/upimg1.bin" ] || { printf '\x89PNG\r\n\x1a\n' > "$W/upimg1.bin"; head -c 999992 /dev/urandom >> "$W/upimg1.bin"; }
[ -f "$W/upimg8.bin" ] || { printf '\x89PNG\r\n\x1a\n' > "$W/upimg8.bin"; head -c 7999992 /dev/urandom >> "$W/upimg8.bin"; }
mkdir -p "$W/omega/webroot-mixed" && cp "$W/www/small.html" "$W/omega/webroot-mixed/"
mkdir -p "$W/nginx-s7/tmp" "$W/nginx-s7/html" && cp "$W/www/small.html" "$W/nginx-s7/html/"
SHA10=$(sha256sum "$W/www/big10.bin" | cut -d' ' -f1); SHA100=$(sha256sum "$W/www/big100.bin" | cut -d' ' -f1)
cat > "$W/backend-s7.conf" <<CONF
worker_processes 2;
pid $W/backend/nginx.pid;
error_log $W/logs/backend-error.log;
events { worker_connections 4096; }
http {
  include /etc/nginx/mime.types;
  sendfile on; tcp_nopush on; keepalive_requests 1000000; keepalive_timeout 120s; access_log off;
  client_body_temp_path $W/backend/tmp; proxy_temp_path $W/backend/tmp; fastcgi_temp_path $W/backend/tmp; uwsgi_temp_path $W/backend/tmp; scgi_temp_path $W/backend/tmp;
  server { listen 127.0.0.1:18960; root $W/www; add_header X-Backend 1 always; client_max_body_size 200m;
    location /api/ { alias $W/www/; }
    # sub_filter retire Content-Length : la reponse part en chunked, octets inchanges (motif absent du fichier)
    location /chunked/ { alias $W/www/; sub_filter_types *; sub_filter 'QZQZQZQZ' 'R'; }
    location = /upload { client_body_buffer_size 16m; return 200 "ok\n"; }
  }
}
CONF
taskset -c "${BACK_CPUS:-${CLI_CPUS:-1,3}}" nginx -p "$W/backend" -c "$W/backend-s7.conf" -e "$W/logs/backend-error.log" -g "daemon off;" &
backend=$!
trap 'kill -TERM $backend 2>/dev/null; wait $backend 2>/dev/null' EXIT
for _ in $(seq 50); do curl -s -o /dev/null http://127.0.0.1:18960/small.html && break; sleep 0.2; done

# ---------------------------------------------------------------- serveurs mesures
omega_start() { # moteur workers waf zone(/ ou /api/)
  local engine=python; [ "$1" = nat ] && engine=native
  local waf='"waf": {"enabled": false}' webroot=webroot
  [ "$3" = 1 ] && waf="\"waf\": {\"enabled\": true, \"mode\": \"block\", \"rules\": {\"paths\": [$(cd "$W/omega" && ls secure/waf/rules/*.json | sed 's/.*/"&"/' | paste -sd,)]}, \"rate_limit\": {\"enabled\": false}}"
  [ "$4" = /api/ ] && webroot=webroot-mixed
  cat > "$W/omega/config/omega-s7.json" <<JSON
{"version": 1, "profile": "standard", "paths": {"webroot": "$webroot"},
 "security": {"allowed_methods": ["GET", "HEAD", "POST"]},
 "server": {"bind": "127.0.0.1", "port": $PORT, "max_connections": 1024, "max_keepalive_requests": 100000,
            "max_request_size": 16777216, "workers": $2, "engine": "$engine"},
 "tls": {"enabled": false},
 "options": {$waf, "reverse_proxy": {"enabled": true, "zones": [
   {"url_prefix": "$4", "upstreams": [{"host": "127.0.0.1", "port": 18960}]}]}}}
JSON
  (cd "$W/omega" && PYTHONPATH=${OMEGA_EXTRA_PATH:+$OMEGA_EXTRA_PATH:}$W/omega/src exec $SRV "$PY" -m omega_serv --config config/omega-s7.json serve > "$W/logs/omega-s7.out" 2>&1) &
  pid=$!
}
nginx_start() { # zone
  local loc="location / { proxy_pass http://backend; proxy_http_version 1.1; proxy_set_header Connection \"\"; }"
  [ "$1" = /api/ ] && loc="root $W/nginx-s7/html; location /api/ { proxy_pass http://backend; proxy_http_version 1.1; proxy_set_header Connection \"\"; }"
  cat > "$W/nginx-s7/run.conf" <<CONF
worker_processes 2;
pid $W/nginx-s7/nginx.pid;
error_log $W/logs/nginx-s7-error.log;
events { worker_connections 4096; }
http {
  keepalive_requests 100000; access_log $W/logs/nginx-s7-access.log; client_max_body_size 16m;
  client_body_temp_path $W/nginx-s7/tmp; proxy_temp_path $W/nginx-s7/tmp; fastcgi_temp_path $W/nginx-s7/tmp; uwsgi_temp_path $W/nginx-s7/tmp; scgi_temp_path $W/nginx-s7/tmp;
  upstream backend { server 127.0.0.1:18960; keepalive 64; }
  server { listen 127.0.0.1:$PORT; $loc }
}
CONF
  $SRV nginx -p "$W/nginx-s7" -c "$W/nginx-s7/run.conf" -e "$W/logs/nginx-s7-error.log" -g "daemon off;" & pid=$!
}
start() { # nom zone
  case $1 in
    nginx-2) nginx_start "$2";;
    omega-*) IFS=- read -r _ eng w waf <<< "$1"; omega_start "$eng" "$w" "$waf" "$2";;
  esac
  for _ in $(seq 150); do [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/small.html")" = 200 ] && break; sleep 0.2; done
  sleep 2
}
stop() { kill -TERM $pid 2>/dev/null; wait $pid 2>/dev/null; sleep 2; }

# ---------------------------------------------------------------- relevés
procs() { pstree -p -T "$pid" | grep -o '([0-9]*)' | tr -d '()'; }
pss() { local t=0 p; for p in $(procs); do t=$((t + $(awk '/^Pss:/{print $2}' "/proc/$p/smaps_rollup" 2>/dev/null || echo 0))); done; echo $((t / 1024)); }
fds() { local t=0 p; for p in $(procs); do t=$((t + $(ls "/proc/$p/fd" 2>/dev/null | wc -l))); done; echo $t; }
conns() { ss -Htn state established "( sport = :$PORT )" | wc -l; }
upconns() { ss -Htn state established "( dport = :18960 )" | wc -l; }
cpu() { # ticks natif python (utime+stime, 100 par seconde)
  local nat=0 py=0 p v
  for p in $(procs); do
    v=$(awk '{print $14 + $15}' "/proc/$p/stat" 2>/dev/null || echo 0)
    if grep -q omega-http-core "/proc/$p/comm" 2>/dev/null; then nat=$((nat + v)); else py=$((py + v)); fi
  done
  echo "$nat $py"
}
peak_pss() { # echantillonne la memoire jusqu'a la fin du processus $1 ; ecrit le maximum dans $W/peak
  local max=0 m; while kill -0 "$1" 2>/dev/null; do m=$(pss); [ "$m" -gt "$max" ] && max=$m; sleep 1; done; echo $max > "$W/peak"
}
oha_run() { # url [options...] -> "req/s Mo/s p99_ms non200"
  local url=$1; shift
  $CLI oha -z "${DUR:-10}s" --no-tui --output-format json "$@" "$url" > "$W/oha-s7.json" 2>/dev/null
  python3 - "$W/oha-s7.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); s = d["summary"]; p = d["latencyPercentiles"]
bad = sum(v for k, v in d.get("statusCodeDistribution", {}).items() if k != "200")
bad += sum(v for k, v in d.get("errorDistribution", {}).items() if "deadline" not in k)
print(f"{s['requestsPerSec']:.0f} req/s {s['sizePerSec']/1e6:.1f} Mo/s p99={(p['p99'] or 0)*1000:.1f}ms non200={bad}")
PY
}

U="http://127.0.0.1:$PORT"
for name in ${CONFIGS:-omega-nat-1-0 omega-nat-1-1 omega-py-2-0 nginx-2}; do
  echo "=== $name $(date +%T) charge: $(cut -d' ' -f1-3 /proc/loadavg)"
  start "$name" /
  echo "repos : PSS=$(pss)Mo descripteurs=$(fds) connexions_client=$(conns) connexions_backend=$(upconns)"
  fd0=$(fds)

  # 1. debit seul et CPU par requete, natif et Python separes
  read -r n0 p0 <<< "$(cpu)"
  line=$(oha_run "$U/small.html" -c 32); read -r n1 p1 <<< "$(cpu)"
  reqs=$(python3 -c "import json; print(json.load(open('$W/oha-s7.json'))['summary']['requestsPerSec'] * ${DUR:-10})")
  echo "1Ko seul : $line ; CPU par requete : natif $(python3 -c "print(f'{($n1-$n0)*1e4/$reqs:.1f}')") us, Python $(python3 -c "print(f'{($p1-$p0)*1e4/$reqs:.1f}')") us"

  # 2. 500 lecteurs lents (100 Ko a 10 Ko/s) pendant le trafic normal
  $C slowread $PORT /medium.png 500 10000 > "$W/s7-slow.txt" & slow=$!
  peak_pss $slow & peak=$!; sleep 2
  echo "1Ko avec 500 lecteurs lents : $(oha_run "$U/small.html" -c 32)"
  wait $slow; wait $peak; echo "  $(cat "$W/s7-slow.txt") ; PSS max=$(cat "$W/peak")Mo"

  # 3. 100 lecteurs tres lents (100 Ko a 2 Ko/s, ~50 s) seuls : CPU pendant l'attente (boucle a vide ?)
  $C slowread $PORT /medium.png 100 2000 > "$W/s7-slow.txt" & slow=$!
  sleep 5; read -r n0 p0 <<< "$(cpu)"; sleep 20; read -r n1 p1 <<< "$(cpu)"
  echo "attente de 100 lecteurs tres lents : CPU natif $(( (n1 - n0) * 100 / 20 / 100 )).$(( (n1 - n0) * 100 / 20 % 100 ))% Python $(( (p1 - p0) * 100 / 20 / 100 )).$(( (p1 - p0) * 100 / 20 % 100 ))% (sur 20 s)"
  wait $slow; echo "  $(cat "$W/s7-slow.txt")"

  # 4. tetes au compte-gouttes (200) et corps au compte-gouttes (50 x 100 Ko a 5 Ko/s)
  echo "  $($C slowhead $PORT 200)"
  echo "  $($C slowbody $PORT /upload 50 100000 5000)"

  # 5. chunked longues : 4 x 100 Mo rapides (et la meme taille avec longueur), 5 x 10 Mo lus a 1 Mo/s
  $C fetch $PORT /chunked/big100.bin 4 "$SHA100" > "$W/s7-f.txt" & f=$!; peak_pss $f; wait $f
  echo "chunked 4 x 100 Mo : $(cat "$W/s7-f.txt") ; PSS max=$(cat "$W/peak")Mo"
  echo "longueur 4 x 100 Mo : $($C fetch $PORT /big100.bin 4 "$SHA100")"
  $C slowread $PORT /chunked/big10.bin 5 1000000 > "$W/s7-slow.txt" & slow=$!; peak_pss $slow; wait $slow
  echo "chunked 5 x 10 Mo lus a 1 Mo/s : $(cat "$W/s7-slow.txt") ; PSS max=$(cat "$W/peak")Mo"

  # 6. envois de fichiers
  echo "POST 1 Mo x8 : $(oha_run "$U/upload" -c 8 -m POST -D "$W/up1.bin" -T application/octet-stream)"
  echo "POST 8 Mo x4 : $(oha_run "$U/upload" -c 4 -m POST -D "$W/up8.bin" -T application/octet-stream)"
  echo "POST image 1 Mo x8 : $(oha_run "$U/upload" -c 8 -m POST -D "$W/upimg1.bin" -T image/png)"
  echo "POST image 8 Mo x4 : $(oha_run "$U/upload" -c 4 -m POST -D "$W/upimg8.bin" -T image/png)"

  # 7. fuite, connexion bloquee
  sleep 12
  echo "apres : PSS=$(pss)Mo descripteurs=$(fds) (repos $fd0) connexions_client=$(conns) connexions_backend=$(upconns) vivant=$(kill -0 $pid 2>/dev/null && echo oui || echo NON)"
  stop

  # 8. keep-alive mixte : statique servi par le proxy lui-meme, /api/ relaye
  [ "$name" = omega-nat-1-1 ] && continue
  start "$name" /api/
  printf '%s\n%s\n' "$U/small.html" "$U/api/small.html" > "$W/s7-urls.txt"
  echo "mixte (oha, 32 connexions) : $(oha_run "$W/s7-urls.txt" -c 32 --urls-from-file)"
  echo "  $($C mixed $PORT 20000)"
  stop
done
echo FIN

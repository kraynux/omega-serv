#!/bin/bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Campagne du reverse proxy (plan proxy natif v2, lot 11), 3 repetitions entrelacees - outil de developpement.
#   SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/proxy/campaign.sh DOSSIER > resultats.txt ; puis summarize.py resultats.txt
# Le backend commun (nginx statique) tourne pendant toute la campagne, epingle sur BACK_CPUS (defaut : CLI_CPUS ;
# machine C : SRV_CPUS=0-3 BACK_CPUS=4,5 CLI_CPUS=6-9, decision de l'auteur du 2026-11-14).
HERE=$(dirname "$(readlink -f "$0")"); W=$(readlink -f "$1")
taskset -c "${BACK_CPUS:-${CLI_CPUS:-1,3}}" nginx -p "$W/backend" -c "$W/backend.conf" -e "$W/logs/backend-error.log" -g "daemon off;" &
backend=$!
trap 'kill -TERM $backend 2>/dev/null; wait $backend 2>/dev/null' EXIT
for _ in $(seq 50); do curl -s -o /dev/null http://127.0.0.1:18960/small.html && break; sleep 0.2; done
DEFAULT="nginx-2 lighttpd-2 apache-2 caddy-2 traefik-2 omega-py-2-0 omega-nat-1-0 omega-nat-1-1"
for rep in $(seq ${REPS:-3}); do
  echo "=== repetition $rep $(date +%T) charge: $(cut -d' ' -f1-3 /proc/loadavg)"
  for n in ${CONFIGS:-$DEFAULT}; do
    for suffix in "" -tls; do
      timeout 120 "$HERE/run.sh" "$W" "$n$suffix" 2>/dev/null
    done
  done
done

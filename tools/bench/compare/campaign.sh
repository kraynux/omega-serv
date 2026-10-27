#!/bin/bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Les 12 configurations du comparatif, 3 repetitions entrelacees - outil de developpement.
#   tools/bench/compare/campaign.sh DOSSIER > resultats.txt ; puis summarize.py resultats.txt
HERE=$(dirname "$(readlink -f "$0")")
for rep in 1 2 3; do
  echo "=== repetition $rep $(date +%T) charge: $(cut -d' ' -f1-3 /proc/loadavg)"
  for n in nginx-1 nginx-2 lighttpd-1 lighttpd-2 caddy-1 caddy-2 omega-v1-1-0 omega-v2-1-0 omega-v2-2-0 omega-v1-1-1 omega-v2-1-1 omega-v2-2-1; do
    timeout 120 "$HERE/run.sh" "$1" "$n" 2>/dev/null
  done
done

#!/bin/bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Les 21 configurations du comparatif (campagne du 2026-11-04), 3 repetitions entrelacees - outil de developpement.
#   setup.sh doit avoir recu les archives 1.0.0 et 2.0.0 ; SRV_CPUS / CLI_CPUS selon la machine (voir run.sh).
#   tools/bench/compare/campaign.sh DOSSIER > resultats.txt ; puis summarize.py resultats.txt
HERE=$(dirname "$(readlink -f "$0")")
for rep in $(seq ${REPS:-3}); do
  echo "=== repetition $rep $(date +%T) charge: $(cut -d' ' -f1-3 /proc/loadavg)"
  # CONFIGS="..." : autre liste (ex. 4 processus : nginx-4 ... omega-v2-4-1-native)
  for n in ${CONFIGS:-nginx-1 nginx-2 lighttpd-1 lighttpd-2 caddy-1 caddy-2 apache-1 apache-2 omega-v2-1-0 omega-v2-1-1 omega-v2-2-0 omega-v2-2-1 omega-v2-1-0-native omega-v2-1-1-native omega-v2-2-1-native omega-v1-1-0 omega-v1-1-1 omega-v20-1-0 omega-v20-1-1 omega-v20-2-0 omega-v20-2-1}; do
    timeout 120 "$HERE/run.sh" "$1" "$n" 2>/dev/null
  done
done

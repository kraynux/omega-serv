#!/bin/bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Remesure d'omega-serv 3.0.0 pour le comparatif (memoire, OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §11, 2026-11-19) -
# outil de developpement. Meme protocole que docs/comparatif-serveurs-web.md (compare/, proxy/, bigfile.py) ; nginx
# est remesure dans la meme session comme reference (rapports et comparaison avec les campagnes precedentes).
#   MACHINE=a SRV_CPUS=0,2 CLI_CPUS=1,3 [BACK_CPUS=..] [CPUS4=1] [OMEGA_PY=..] [OMEGA_LIB=dossier/src] [TRAEFIK=..] \
#     tools/bench/memoire-3.0.0.sh DOSSIER > resultats.txt
#   CPUS4=1 : en plus, passe a 4 processus (machine C) ; PROXY_CONFIGS : autre liste pour le proxy (machine C :
#   "nginx-4 omega-nat-1-0 omega-nat-1-1", avec BACK_CPUS=4,5 et PROXY_CLI_CPUS=6-9).
set -u
HERE=$(dirname "$(readlink -f "$0")"); SERV=$(readlink -f "$HERE/../.."); W=$(readlink -f "$1")
export OMEGA_PY=${OMEGA_PY:-$SERV/.venv/bin/python} SRV_CPUS CLI_CPUS
echo "# omega-serv 3.0.0, machine ${MACHINE:-?}, $(date '+%F %T'), coeurs serveur $SRV_CPUS client $CLI_CPUS"
echo "# Python $($OMEGA_PY -c 'import platform; print(platform.python_version())'), $(nginx -v 2>&1), $(oha --version)"
mkdir -p "$W"
bash "$HERE/compare/setup.sh" "$W/fichiers" > /dev/null
[ -n "${OMEGA_LIB:-}" ] && ln -sfn "$OMEGA_LIB" "$W/fichiers/omega-v2/omega-lib"
echo "## fichiers (compare/run.sh)"
CONFIGS="nginx-2 omega-v2-1-0 omega-v2-1-1 omega-v2-2-0 omega-v2-2-1 omega-v2-1-0-native omega-v2-1-1-native omega-v2-2-1-native" \
  bash "$HERE/compare/campaign.sh" "$W/fichiers"
if [ -n "${CPUS4:-}" ]; then
  echo "## 4 processus"
  CONFIGS="nginx-4 omega-v2-1-0-native omega-v2-4-0-native omega-v2-4-0" \
    bash "$HERE/compare/campaign.sh" "$W/fichiers"
fi
echo "## gros telechargements (bigfile.py, RSS)"
for pass in 1 2; do
  echo "--- 3.0.0 Python passage $pass"
  (cd "$SERV" && BENCH_PY=$OMEGA_PY BENCH_EXTRA_PATH=${OMEGA_LIB:-} "$OMEGA_PY" tools/bench/bigfile.py)
  echo "--- 3.0.0 natif passage $pass"
  (cd "$SERV" && BENCH_PY=$OMEGA_PY BENCH_EXTRA_PATH=${OMEGA_LIB:-} BENCH_ENGINE=native "$OMEGA_PY" tools/bench/bigfile.py)
done
echo "## reverse proxy (proxy/run.sh)"
bash "$HERE/proxy/setup.sh" "$W/proxy" ${TRAEFIK:-} > /dev/null
CLI_CPUS=${PROXY_CLI_CPUS:-$CLI_CPUS} OMEGA_EXTRA_PATH=${OMEGA_LIB:-} CONFIGS=${PROXY_CONFIGS:-"nginx-2 omega-py-2-0 omega-nat-1-0 omega-nat-1-1"} \
  bash "$HERE/proxy/campaign.sh" "$W/proxy"
echo "FIN $(date +%T)"

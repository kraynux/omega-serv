#!/bin/bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Prepare un dossier de comparaison (docs/comparatif-serveurs-web.md) - outil de developpement.
#   tools/bench/compare/setup.sh DOSSIER [omega-serv-1.0.0.tar.gz [omega-serv-2.0.0.tar.gz]]
# Cree : DOSSIER/www (fichiers de test communs), les configurations nginx/lighttpd/Caddy pointant
# sur ce webroot, DOSSIER/omega-v2 (code courant) et, si les archives sont donnees, DOSSIER/omega-v1 et
# DOSSIER/omega-v20 (run.sh : omega-v1-..., omega-v20-...).
set -eu
W=$(readlink -f "$1"); V1=${2:-}; V20=${3:-}
HERE=$(dirname "$(readlink -f "$0")"); SERV=$(readlink -f "$HERE/../../..")
mkdir -p "$W/logs" "$W/nginx/tmp"
python3 "$SERV/tools/bench/bench_any.py" --make-files "$W/www"
sed "s#@W@#$W#g" "$HERE/nginx.conf.in" > "$W/nginx.conf"
sed "s#@W@#$W#g" "$HERE/lighttpd.conf.in" > "$W/lighttpd.conf"
sed "s#@W@#$W#g" "$HERE/Caddyfile.in" > "$W/Caddyfile"
sed "s#@W@#$W#g" "$HERE/apache.conf.in" > "$W/apache.conf"
prepare_omega() { # dossier-cible dossier-source
  mkdir -p "$1/config" "$1/secure/waf/rules"
  rm -rf "$1/src"; cp -r "$2/src" "$1/src"
  cp "$2"/secure/waf/rules/*.json "$1/secure/waf/rules/"
  ln -sfn "$W/www" "$1/webroot"
  # moteur natif (suffixe -native de run.sh) : binaire compile dans native/omega-http-core/build-release
  [ -x "$2/native/omega-http-core/build-release/omega-http-core" ] && mkdir -p "$1/bin" && ln -sfn "$2/native/omega-http-core/build-release/omega-http-core" "$1/bin/omega-http-core"
  return 0
}
prepare_omega "$W/omega-v2" "$SERV"
if [ -n "$V1" ]; then
  rm -rf "$W/v1-archive"; mkdir -p "$W/v1-archive"; tar xzf "$V1" -C "$W/v1-archive"
  prepare_omega "$W/omega-v1" "$W/v1-archive/omega-serv"
  ln -sfn "$W/v1-archive/omega-serv/vendor/omega-lib/src" "$W/omega-v1/omega-lib"
fi
if [ -n "$V20" ]; then
  rm -rf "$W/v20-archive"; mkdir -p "$W/v20-archive"; tar xzf "$V20" -C "$W/v20-archive"
  prepare_omega "$W/omega-v20" "$W/v20-archive/omega-serv"
  ln -sfn "$W/v20-archive/omega-serv/vendor/omega-lib/src" "$W/omega-v20/omega-lib"
fi
echo "pret : $W"

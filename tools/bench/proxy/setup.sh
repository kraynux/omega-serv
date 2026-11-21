#!/bin/bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# Prepare un dossier de mesure du REVERSE PROXY (plan proxy natif v2, lot 11) - outil de developpement.
#   tools/bench/proxy/setup.sh DOSSIER [TRAEFIK]
# Meme protocole que tools/bench/compare (docs/comparatif-serveurs-web.md) : memes fichiers (1 Ko, 100 Ko), journal
# d'acces actif partout, keep-alive, 3 repetitions entrelacees. Ici chaque serveur est un reverse proxy devant le
# MEME backend : nginx statique (decision de l'auteur du 2026-11-14), epingle avec le client.
# Cree : DOSSIER/www, un certificat auto-signe (HTTPS), le backend, les configurations des proxys (nginx, lighttpd
# mod_proxy, Apache mod_proxy + mod_proxy_http, Caddy reverse_proxy, Traefik) et DOSSIER/omega (code courant).
# TRAEFIK : chemin du binaire traefik (sinon `traefik` dans le PATH, sinon DOSSIER/traefik).
set -eu
W=$(readlink -f "$1"); TRAEFIK=${2:-}
HERE=$(dirname "$(readlink -f "$0")"); SERV=$(readlink -f "$HERE/../../..")
mkdir -p "$W/logs" "$W/nginx/tmp" "$W/backend/tmp" "$W/tls"
python3 "$SERV/tools/bench/bench_any.py" --make-files "$W/www"
[ -f "$W/tls/cert.pem" ] || openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout "$W/tls/key.pem" -out "$W/tls/cert.pem" -days 30 -subj /CN=localhost \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null  # Caddy choisit le certificat par l'adresse
chmod 600 "$W/tls/key.pem"; cat "$W/tls/cert.pem" "$W/tls/key.pem" > "$W/tls/both.pem"; chmod 600 "$W/tls/both.pem"
for f in backend.conf nginx.conf lighttpd.conf apache.conf Caddyfile traefik.toml traefik-dyn.toml; do
  sed "s#@W@#$W#g" "$HERE/$f.in" > "$W/$f"
done
if [ -n "$TRAEFIK" ]; then ln -sfn "$(readlink -f "$TRAEFIK")" "$W/traefik"
elif command -v traefik > /dev/null; then ln -sfn "$(command -v traefik)" "$W/traefik"; fi
mkdir -p "$W/omega/config" "$W/omega/secure/waf/rules" "$W/omega/secure/certs"
rm -rf "$W/omega/src"; cp -r "$SERV/src" "$W/omega/src"
cp "$SERV"/secure/waf/rules/*.json "$W/omega/secure/waf/rules/"
cp "$W/tls/cert.pem" "$W/tls/key.pem" "$W/omega/secure/certs/"; chmod 600 "$W/omega/secure/certs/key.pem"
mkdir -p "$W/omega/webroot"  # webroot vide : toute requete va au proxy (zone /)
if [ -x "$SERV/native/omega-http-core/build-release/omega-http-core" ]; then
  mkdir -p "$W/omega/bin"; cp "$SERV/native/omega-http-core/build-release/omega-http-core" "$W/omega/bin/"
fi
echo "pret : $W"

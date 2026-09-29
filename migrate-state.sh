#!/usr/bin/env bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# ==============================================================================
# Copie l'etat vivant (config/secrets/webroot/var) d'une ANCIENNE installation
# omega-serv vers CETTE installation-ci.
#
# Jamais invoque interactivement par l'utilisateur en temps normal : appele
# AUTOMATIQUEMENT par install.sh quand il detecte une extraction fraiche
# (config/omega-serve.json absent ici) a cote d'une ancienne installation
# sans ambiguite (voir install.sh, meme raison) - --yes systematique dans ce
# cas, le seul "consentement" necessaire est celui d'avoir lance
# ./install.sh lui-meme. Reste utilisable a la main (sans --yes, demande
# alors une confirmation ecrite) pour une recuperation manuelle ciblee.
#
# Usage : ./migrate-state.sh <ancien-dossier-omega-serv> [--yes]
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLD_DIR=""
ASSUME_YES="false"
for arg in "$@"; do
    case "$arg" in
        --yes|-y) ASSUME_YES="true" ;;
        *) OLD_DIR="$arg" ;;
    esac
done

if [ -z "$OLD_DIR" ]; then
    err "Usage : $0 <ancien-dossier-omega-serv> [--yes]"
    echo "Exemple : $0 ~/omega-serv.old-20260928"
    exit 1
fi

OLD_DIR="$(cd "$OLD_DIR" 2>/dev/null && pwd || true)"
if [ -z "$OLD_DIR" ] || [ ! -d "$OLD_DIR" ]; then
    err "Dossier introuvable : ${1}"
    exit 1
fi

if [ "$OLD_DIR" = "$SCRIPT_DIR" ]; then
    err "L'ancien dossier ne peut pas etre le meme que celui-ci ($SCRIPT_DIR)."
    exit 1
fi

if [ "$ASSUME_YES" != "true" ]; then
    echo ""
    warn "Cette action va ECRASER dans :"
    echo "    $SCRIPT_DIR"
    warn "les fichiers d'etat (config, secrets, webroot, var/) copies depuis :"
    echo "    $OLD_DIR"
    echo ""
    read -r -p "Tapez CONFIRMER pour continuer : " confirmation
    if [ "$confirmation" != "CONFIRMER" ]; then
        err "Annule."
        exit 1
    fi
fi

info "Recuperation de l'etat depuis $OLD_DIR..."

_copy() {
    local rel="$1"
    if [ -e "$OLD_DIR/$rel" ]; then
        mkdir -p "$(dirname "$SCRIPT_DIR/$rel")"
        rsync -a "$OLD_DIR/$rel" "$SCRIPT_DIR/$rel"
        ok "Recupere : $rel"
    fi
}

_copy_dir_contents() {
    local rel="$1"
    if [ -d "$OLD_DIR/$rel" ]; then
        mkdir -p "$SCRIPT_DIR/$rel"
        rsync -a "$OLD_DIR/$rel/" "$SCRIPT_DIR/$rel/"
        ok "Recupere : $rel/"
    fi
}

# Meme liste que build-release.sh (section "exclude"), a l'exception de
# var/log/*, var/cache/*, var/run/* : etat transitoire, jamais reporte
# d'une installation a l'autre, se regenere tout seul.
# secure/waf/ copie fichier par fichier : les autres packs de regles
# (scanner-ua.json...) sont du contenu LIVRE par la release, jamais de
# l'etat utilisateur - seuls blocklist/allowlist/rules/custom.json le
# sont (meme distinction que build-release.sh).
_copy "config/omega-serve.json"
_copy_dir_contents "secure/auth"
_copy_dir_contents "secure/certificates"
_copy_dir_contents "secure/secrets"
_copy "secure/waf/blocklist.json"
_copy "secure/waf/allowlist.json"
_copy "secure/waf/rules/custom.json"
_copy_dir_contents "webroot"
_copy "var/settings.json"
_copy_dir_contents "var/lib"
_copy_dir_contents "var/uploads"
_copy_dir_contents "var/backups"
_copy_dir_contents "var/exports"
_copy_dir_contents "var/screenshots"

if command -v getent >/dev/null 2>&1 && getent group omega-serv >/dev/null 2>&1; then
    if [ "$(id -u)" = "0" ]; then
        chown -R omega-serv:omega-serv "$SCRIPT_DIR/var" "$SCRIPT_DIR/secure" 2>/dev/null || true
        ok "Proprietaire var/ et secure/ restaure a omega-serv:omega-serv."
    fi
fi

ok "Etat recupere depuis l'ancienne installation."

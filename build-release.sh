#!/usr/bin/env bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# ==============================================================================
# Construit l'archive distribuable omega-serv.tar.gz : copie le projet
# (sans artefacts dev/runtime/secrets), vendore omega-lib (dependance
# obligatoire non publiee sur PyPI depuis l'interface interactive, plan
# interface §3.2), archive le tout dans ../dist/ (a l'exterieur du
# sous-dossier omega-serv/, meme convention que CHECK/TRACK depuis la
# restructuration de l'arborescence en ~/DEV/SERV/omega-serv/).
# Outil de maintenance, jamais lui-meme inclus dans l'archive generee.
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMEGA_LIB_SRC="${OMEGA_LIB_SRC:-$HOME/DEV/LIB/omega-lib}"
DIST_DIR="${DIST_DIR:-$PROJECT_ROOT/../dist}"
ARCHIVE_NAME="omega-serv.tar.gz"

if [ ! -d "$OMEGA_LIB_SRC" ]; then
    err "omega-lib introuvable : $OMEGA_LIB_SRC (definissez OMEGA_LIB_SRC si le chemin differe)."
    exit 1
fi

STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGING_DIR"' EXIT
DEST="$STAGING_DIR/omega-serv"
mkdir -p "$DEST"

info "Copie du projet omega-serv..."
rsync -a \
    --exclude='.venv/' --exclude='venv/' \
    --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.egg-info/' \
    --exclude='.pytest_cache/' --exclude='.mypy_cache/' --exclude='.ruff_cache/' \
    --exclude='.import_linter_cache/' --exclude='.hypothesis/' \
    --exclude='.git/' --exclude='.claude/' \
    --exclude='var/log/*' --exclude='var/cache/*' --exclude='var/run/*' \
    --exclude='var/uploads/*' --exclude='var/backups/*' \
    --exclude='secure/auth/users.json' --exclude='secure/auth/zones.json' \
    --exclude='secure/certificates/**/*.key' --exclude='secure/certificates/**/*.pem' \
    --exclude='secure/certificates/**/*.crt' --exclude='secure/certificates/**/*.csr' \
    --exclude='secure/certificates/**/*.p12' --exclude='secure/certificates/**/*.pfx' \
    --exclude='secure/certificates/**/*.der' --exclude='secure/certificates/**/serial.txt' \
    --exclude='secure/certificates/**/index.txt' --exclude='secure/certificates/acme/**' \
    --exclude='secure/secrets/*' --exclude='secure/waf/blocklist.json' --exclude='secure/waf/allowlist.json' \
    --exclude='config/omega-serve.json' \
    --exclude='*~' --exclude='*.bak' --exclude='*.swp' \
    --exclude='.coverage' --exclude='htmlcov/' \
    --exclude='build-release.sh' --exclude='omega-serv.tar.gz' --exclude='dist/' \
    "$PROJECT_ROOT/" "$DEST/"

info "Vendoring d'omega-lib (dependance obligatoire, non publiee sur PyPI)..."
mkdir -p "$DEST/vendor/omega-lib"
rsync -a \
    --exclude='.venv/' --exclude='__pycache__/' --exclude='*.pyc' \
    --exclude='.pytest_cache/' --exclude='.mypy_cache/' --exclude='.ruff_cache/' \
    --exclude='*.egg-info/' --exclude='.git/' --exclude='tests/' \
    "$OMEGA_LIB_SRC/" "$DEST/vendor/omega-lib/"

info "Archivage..."
mkdir -p "$DIST_DIR"
tar -C "$STAGING_DIR" -czf "$DIST_DIR/$ARCHIVE_NAME" omega-serv

ok "Archive generee : $DIST_DIR/$ARCHIVE_NAME"
echo "sha256sum :"
sha256sum "$DIST_DIR/$ARCHIVE_NAME"

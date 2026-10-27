#!/usr/bin/env bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# ==============================================================================
# Construit l'archive distribuable omega-serv-<version>.tar.gz : copie le
# projet (sans artefacts dev/runtime/secrets), vendore omega-lib (dependance
# obligatoire non publiee sur PyPI depuis l'interface interactive, plan
# interface §3.2), archive le tout dans ../html/download/ (dossier publie
# du site, /omega-serv/download/ - remplace ../dist/ depuis la 2.0.0) et
# ajoute son empreinte a sha.txt (format sha256sum, une ligne par version).
# Version = pyproject.toml, seule source.
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
# Fichier maitre des chemins sensibles (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_
# PATHS.md §3.11) - meme convention que OMEGA_LIB_SRC. Absent (machine sans
# ~/DEV/JAIL) : les references deja presentes dans src/ sont livrees telles
# quelles, jamais une erreur.
SENSITIVE_PATHS_MASTER="${SENSITIVE_PATHS_MASTER:-$HOME/DEV/JAIL/sensitive-path.txt}"
DIST_DIR="${DIST_DIR:-$PROJECT_ROOT/../html/download}"
VERSION="$(sed -n 's/^version = "\(.*\)"$/\1/p' "$PROJECT_ROOT/pyproject.toml" | head -n1)"
if [ -z "$VERSION" ]; then
    err "Version introuvable dans pyproject.toml."
    exit 1
fi
ARCHIVE_NAME="omega-serv-$VERSION.tar.gz"
SHA_FILE="$DIST_DIR/sha.txt"

if [ ! -d "$OMEGA_LIB_SRC" ]; then
    err "omega-lib introuvable : $OMEGA_LIB_SRC (definissez OMEGA_LIB_SRC si le chemin differe)."
    exit 1
fi

if [ -f "$SENSITIVE_PATHS_MASTER" ]; then
    info "Regeneration des listes de reference depuis $SENSITIVE_PATHS_MASTER..."
    # Echec = arret du build (set -e) : jamais une reference invalide livree.
    # omega-lib aussi : omega_serv.core.i18n l'importe depuis la traduction de l'application.
    PYTHONPATH="$PROJECT_ROOT/src:$OMEGA_LIB_SRC/src" python3 -m omega_serv.infrastructure.waf.keyword_reference_generator \
        "$SENSITIVE_PATHS_MASTER" "$PROJECT_ROOT/src/omega_serv/infrastructure/waf/keyword_references"
else
    info "Fichier maitre des chemins sensibles absent ($SENSITIVE_PATHS_MASTER) : references existantes livrees telles quelles."
fi

STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGING_DIR"' EXIT
DEST="$STAGING_DIR/omega-serv"
mkdir -p "$DEST"

info "Copie du projet omega-serv..."
# webroot/* exclu ci-dessous : racine servie par defaut
# (domain/config/entities.py::webroot="webroot", aucun profil ne la
# surcharge) - contenu reel d'un deploiement en place (retour
# utilisateur 2026-09-27), jamais du contenu du depot a expedier. Absent
# des excludes jusqu'ici par oubli (aucun risque constate jusqu'a present
# car ce webroot/ de dev est reste vide) - meme principe que var/*,
# secure/* et config/omega-serve.json ci-dessous : une mise a jour par
# extraction par-dessus une installation existante ne doit JAMAIS ecraser
# le site reellement servi.
# var/lib/*, var/exports/*, var/screenshots/*, var/settings.json exclus
# (2026-09-28, retour utilisateur : "verifie que la configuration totale
# reste... service, sauvegarde, regles, options activees... seul le code
# doit etre modifie") : meme oubli, meme risque que webroot/* ci-dessus,
# et plus grave pour var/lib/active-defense.sqlite3 - base Active Defense
# (incidents/menaces/deception) - qui aurait ete EXPEDIEE DANS L'ARCHIVE
# (jamais exclue jusqu'ici) : une reinstallation par extraction par-dessus
# une instance existante aurait alors ECRASE l'historique Active Defense
# reel par un instantane fige au moment du build. var/settings.json
# (theme/repertoires d'export-capture/nom de service) aurait eu le meme
# sort, avec un degat supplementaire : les chemins qu'il contient
# (exports_dir_override/screenshots_dir_override) sont des chemins
# ABSOLUS propres a LA MACHINE OU build-release.sh a ete execute -
# livrer ce fichier tel quel a une autre installation y aurait pointe
# vers un repertoire inexistant chez elle. Sans risque de perte au
# demarrage suivant : chaque emplacement se recree lui-meme au besoin
# (infrastructure/config/json_settings_store.py, infrastructure/
# persistence/sqlite_active_defense_connection.py) - jamais suppose deja
# present par le reste du code.
# var/favorites.json, var/library.json, var/remote-log-sources.json
# exclus (2026-10-15, retour utilisateur : "l'ancienne archive avait
# garde des configurations de la machine de dev, notamment les chemins
# de logs") : meme categorie que var/settings.json ci-dessus - ces 3
# fichiers de la Bibliotheque de logs (refonte menu 2026-10-15)
# contiennent des chemins ABSOLUS propres a la machine de dev (ex.
# /home/<utilisateur>/log-test/access.log) et des noms de favoris
# personnels, jamais des donnees generiques a expedier. Oublis au
# moment de l'ajout de la fonctionnalite, pas une exclusion
# deliberement differee. Se recreent vides au besoin
# (infrastructure/logging/json_log_*_repository.py,
# json_remote_log_source_repository.py), jamais supposes deja presents.
# secure/waf/scripts/waf-personal.lua exclu (retour utilisateur
# 2026-10-11, "le script Lua est-il bien depersonnalise, peut-il etre
# distribue pour tous ?") : seuls les 5 chemins avaient ete dissocies
# (consigne d'origine), pas la logique propre au site de l'auteur
# (routes SearXNG, exceptions whitelist, texte de la page d'erreur) -
# jamais distribuable tel quel. secure/waf/scripts/waf.lua (SANS ce
# suffixe, jamais exclu) est desormais un exemple minimal et
# generique, sans aucune logique propre a un site particulier.
# var/ et secure/auth/ : jamais livres, meme vides (2026-10-18) - une entree
# de dossier dans l'archive remet ses droits a l'extraction par-dessus une
# installation existante et casse le partage avec le compte du service.
# install.sh les cree s'ils manquent, sans jamais toucher aux existants.
rsync -a \
    --exclude='.venv/' --exclude='venv/' \
    --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.egg-info/' \
    --exclude='.pytest_cache/' --exclude='.mypy_cache/' --exclude='.ruff_cache/' \
    --exclude='.import_linter_cache/' --exclude='.hypothesis/' \
    --exclude='.git/' --exclude='.claude/' \
    --exclude='docs/assets/' \
    --exclude='/var/' --exclude='/secure/auth/' \
    --exclude='var/log/*' --exclude='var/cache/*' --exclude='var/run/*' \
    --exclude='var/uploads/*' --exclude='var/backups/*' \
    --exclude='var/lib/*' --exclude='var/exports/*' --exclude='var/screenshots/*' \
    --exclude='var/settings.json' \
    --exclude='var/favorites.json' --exclude='var/library.json' --exclude='var/remote-log-sources.json' \
    --exclude='webroot/*' \
    --exclude='secure/auth/users.json' --exclude='secure/auth/zones.json' \
    --exclude='secure/certificates/**/*.key' --exclude='secure/certificates/**/*.pem' \
    --exclude='secure/certificates/**/*.crt' --exclude='secure/certificates/**/*.csr' \
    --exclude='secure/certificates/**/*.p12' --exclude='secure/certificates/**/*.pfx' \
    --exclude='secure/certificates/**/*.der' --exclude='secure/certificates/**/serial.txt' \
    --exclude='secure/certificates/**/index.txt' --exclude='secure/certificates/letsencrypt/**' \
    --exclude='secure/secrets/*' --exclude='secure/waf/blocklist.json' --exclude='secure/waf/allowlist.json' \
    --exclude='secure/waf/rules/custom.json' --exclude='secure/waf/scripts/waf-personal.lua' \
    --exclude='secure/waf/rules/keywords/*.txt' \
    --exclude='config/omega-serve.json' \
    --exclude='*~' --exclude='*.bak' --exclude='*.swp' \
    --exclude='.coverage' --exclude='htmlcov/' \
    --exclude='build-release.sh' --exclude='omega-serv*.tar.gz' --exclude='dist/' \
    --exclude='/tools/' \
    "$PROJECT_ROOT/" "$DEST/"

# Traductions (OMEGA-SERV_PLAN-DETAILLE_I18N.md, lot 4) : les .mo sont compiles ICI,
# jamais a l'execution (aucune dependance gettext chez l'utilisateur). Un .po present
# sans msgfmt = arret du build : jamais une archive dont une langue proposee resterait
# en francais faute de catalogue compile. msgfmt --check : {variables} identiques
# entre la phrase source et sa traduction, sinon arret.
PO_FILES=$(find "$DEST/src/omega_serv/locale" -name '*.po' 2>/dev/null || true)
if [ -n "$PO_FILES" ]; then
    if ! command -v msgfmt >/dev/null 2>&1; then
        err "msgfmt introuvable (paquet gettext) : impossible de compiler les traductions."
        exit 1
    fi
    info "Compilation des traductions..."
    for po in $PO_FILES; do
        msgfmt --check -o "${po%.po}.mo" "$po"
        echo "   $(basename "$(dirname "$(dirname "$po")")") : $(msgfmt --statistics -o /dev/null "$po" 2>&1)"
    done
fi
# Sources de traduction (.po/.pot) jamais livrees (decision utilisateur 2026-10-24) :
# l'application ne lit que les .mo compiles ci-dessus ; les sources ne servent qu'a
# traduire et pesaient plus de la moitie de l'archive.
find "$DEST/src/omega_serv/locale" \( -name '*.po' -o -name '*.pot' \) -delete 2>/dev/null || true

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

# sha.txt (mise en page de l'utilisateur, 2026-10-24) : un titre encadre de lignes "=",
# puis une section par version, la plus recente en tete :
#   version X.Y.Z :
#   <ligne vide>
#   <empreinte>  omega-serv-X.Y.Z.tar.gz
#   <ligne vide>
#   ===...
# Version reconstruite : sa ligne est remplacee sur place (jamais deux empreintes pour le
# meme nom). Nouvelle version : nouvelle section inseree avant la premiere section
# existante. Reste lisible par `sha256sum -c --ignore-missing` (lignes de mise en page
# signalees comme non formatees, sans effet sur la verification).
SHA_LINE="$(cd "$DIST_DIR" && sha256sum "$ARCHIVE_NAME")"
SHA_LINE="$SHA_LINE" ARCHIVE_NAME="$ARCHIVE_NAME" VERSION="$VERSION" python3 - "$SHA_FILE" <<'PY'
import os, sys
path = sys.argv[1]
line, name, version = os.environ["SHA_LINE"], os.environ["ARCHIVE_NAME"], os.environ["VERSION"]
sep = "=" * 89
lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
if not any(l.strip() for l in lines):
    lines = ["", sep, "Controle d integrite des archives OMEGA-SERV", "", sep, ""]
if any(l.endswith("  " + name) for l in lines):
    lines = [line if l.endswith("  " + name) else l for l in lines]
elif f"version {version} :" in lines:
    i = lines.index(f"version {version} :")
    lines[i + 1:i + 1] = ["", line]
else:
    first = next((i for i, l in enumerate(lines) if l.startswith("version ")), len(lines))
    lines[first:first] = [f"version {version} :", "", line, "", sep, ""]
open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY

ok "Archive generee : $DIST_DIR/$ARCHIVE_NAME"
echo "sha256sum (ajoute a $SHA_FILE) :"
echo "$SHA_LINE"

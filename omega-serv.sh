#!/usr/bin/env bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# ==============================================================================
# Script de lancement - OMEGA-SERV
# Aucun privilege particulier requis pour lancer ce script - l'application
# elle-meme refuse de demarrer en tant que root (voir plan de developpement
# §6), et la gestion du service systeme eleve desormais ses propres
# privileges ponctuellement, au moment de l'action (plan interface §3.6),
# jamais en exigeant que l'application entiere soit lancee en root.
# Dispatch TUI (aucun argument) / CLI (au moins un argument) gere par
# __main__.py (plan interface §4, Phase I) - meme patron que le reste de
# la suite omega- depuis ce chantier. Pas de OMEGA_SERV_VAR_DIR a
# exporter : la racine du projet est deduite de l'emplacement reel du
# fichier source (bootstrap/paths.py::PROJECT_ROOT), jamais du
# repertoire courant du shell appelant - contrairement au reste de la
# suite omega-, ceci reste inchange par l'ajout de la TUI.
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
WHITE='\033[1;37m'
NC='\033[0m'

# `synchro jeton|fiche` (contrats d'interconnexion, 2026-11-10) : sortie JSON lue par omega-connect,
# donc sans bannière.
if [ "${1:-}" != "synchro" ]; then
echo -e "${WHITE}${NC}"
echo -e "${WHITE}DÉMARRAGE DE L'APPLICATION${NC}"
echo -e "${WHITE}${NC}"
echo -e "${WHITE}    ░▒▓█████████████████████▓▒░${NC}"
echo -e "${WHITE}    ░▒▓ Ω M E G A - S E R V ▓▒░${NC}"
echo -e "${WHITE}    ░▒▓█████████████████████▓▒░${NC}"
echo -e "${WHITE}${NC}"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ Environnement virtuel introuvable : $VENV_DIR${NC}"
    echo ""
    echo "Lancez d'abord : $SCRIPT_DIR/install.sh"
    exit 1
fi

if ! "$VENV_DIR/bin/python" -c "import omega_serv" 2>/dev/null; then
    # Jamais de `pip install` en root (2026-11-10, comme omega-jail.sh) : omega-connect lance certaines
    # commandes avec sudo, et pip ecrirait alors en root dans le dossier de l'utilisateur.
    if [ "$(id -u)" -eq 0 ]; then
        echo -e "${RED}❌ Environnement virtuel incomplet : $VENV_DIR${NC}" >&2
        echo "Relancez sans sudo : $SCRIPT_DIR/install.sh" >&2
        exit 1
    fi
    echo "⚠️  Le venv semble incomplet, reinstallation..." >&2
    if [ -d "$SCRIPT_DIR/vendor/omega-lib" ]; then
        "$VENV_DIR/bin/pip" install -q -e "$SCRIPT_DIR/vendor/omega-lib"
    fi
    "$VENV_DIR/bin/pip" install -q -e "$SCRIPT_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
exec omega-serv "$@"

#!/usr/bin/env bash
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
# ==============================================================================
# Script d'installation - OMEGA-SERV
# À lancer depuis le dossier extrait de l'archive : cd omega-serv && ./install.sh
# Résilient : peut être relancé sans erreur si une étape a déjà été faite.
# Aucune étape ici ne nécessite les privilèges root : omega-serv refuse
# lui-même de démarrer en tant que root (voir plan de développement §6),
# et l'installation d'un service système reste une étape séparée et
# explicite (`omega-serv service install`, voir README.md §10).
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
WHITE='\033[1;37m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { echo -e "${CYAN}ℹ️  $1${NC}"; }
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }
tip()  { echo -e "${WHITE}💡 $1${NC}"; }

echo -e "${WHITE}    ░▒▓████████████████████████████████████████████▓▒░${NC}"
echo -e "${WHITE}    ░▒▓ Ω M E G A - SERV — I N S T A L L A T I O N ▓▒░${NC}"
echo -e "${WHITE}    ░▒▓████████████████████████████████████████████▓▒░${NC}"
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# -------------------------------------------------------------------------
# 1. Environnement virtuel Python
# -------------------------------------------------------------------------
if [ -d ".venv" ]; then
    info ".venv existe déjà, création ignorée."
else
    if ! python3 -m venv .venv 2>/tmp/omega-serv-venv-err.log; then
        err "Échec de la création de l'environnement virtuel."
        warn "Sur Debian/Ubuntu (et dérivées), le module venv n'est pas toujours inclus avec python3 de base."
        tip "Installez-le puis relancez ce script : sudo apt install python3-venv"
        cat /tmp/omega-serv-venv-err.log >&2
        rm -f /tmp/omega-serv-venv-err.log
        exit 1
    fi
    rm -f /tmp/omega-serv-venv-err.log
    ok "Environnement virtuel créé (.venv)."
fi

# -------------------------------------------------------------------------
# 2. Dépendances — pyproject.toml reste l'unique source de verite.
#    omega-lib (interface interactive, plan interface §3.2) n'est pas
#    publiee sur PyPI : l'archive distribuable la vendore dans
#    vendor/omega-lib/ (meme convention que CHECK/DEEP/FOLD/FUZZ/TRACK/
#    SCAN) - installee ICI, avant omega-serv lui-meme, pour que pip la
#    trouve deja satisfaite dans le venv. Absente en clone de
#    developpement (omega-lib vient alors du monorepo local
#    ~/DEV/LIB/omega-lib, deja installee a part) : etape silencieusement
#    ignoree si vendor/omega-lib/ n'existe pas.
# -------------------------------------------------------------------------
source .venv/bin/activate
pip install -q --upgrade pip
if [ -d "$SCRIPT_DIR/vendor/omega-lib" ]; then
    pip install -q -e "$SCRIPT_DIR/vendor/omega-lib"
    ok "Dépendance vendorée omega-lib installée."
fi
pip install -q -e .
ok "Dépendances installées."

# -------------------------------------------------------------------------
# 3. Scripts exécutables
# -------------------------------------------------------------------------
chmod +x omega-serv.sh
chmod +x "$SCRIPT_DIR/install.sh"
ok "Scripts rendus exécutables."

# -------------------------------------------------------------------------
# 3b. Dossiers d'etat (var/, secure/auth/) - crees ICI, plus livres dans
#     l'archive (2026-10-18, incident craftdark : extraire une mise a jour
#     par-dessus l'installation remettait les droits de ces dossiers a ceux
#     de l'archive et effacait le partage avec le compte du service, qui
#     tombait en PermissionError jusqu'au bouton "Reappliquer les
#     permissions"). Un dossier deja present n'est JAMAIS modifie (ni mode,
#     ni groupe) : seuls les manquants sont crees.
# -------------------------------------------------------------------------
_state_dir() {
    [ -d "$SCRIPT_DIR/$1" ] || mkdir -m "$2" "$SCRIPT_DIR/$1"
}
_state_dir "var" 0755
for sub in log cache run uploads backups exports screenshots; do
    _state_dir "var/$sub" 0755
done
_state_dir "var/lib" 0750
_state_dir "secure" 0755
_state_dir "secure/auth" 0750
ok "Dossiers d'état présents (var/, secure/auth/) - les existants sont laissés tels quels."

# -------------------------------------------------------------------------
# 3c. Moteur HTTP natif (bin/omega-http-core, plan moteur C++ lot 9) : le
#     binaire fourni est essaye ; s'il ne demarre pas sur cette machine
#     (glibc trop ancienne, OpenSSL 3 absent), compilation locale si cmake
#     et un compilateur C++ sont presents - jamais une question. Sans lui,
#     omega-serv fonctionne normalement avec le moteur Python et le choix
#     du natif reste grise, avec la raison.
# -------------------------------------------------------------------------
NATIVE_BIN="$SCRIPT_DIR/bin/omega-http-core"
native_ok() { [ -x "$NATIVE_BIN" ] && "$NATIVE_BIN" --version >/dev/null 2>&1; }
if native_ok; then
    ok "Moteur natif disponible ($("$NATIVE_BIN" --version))."
else
    if [ -f "$NATIVE_BIN" ]; then
        warn "Le moteur natif fourni ne démarre pas sur cette machine (glibc trop ancienne ou OpenSSL 3 absent)."
    else
        warn "Moteur natif absent (bin/omega-http-core)."
    fi
    if command -v cmake >/dev/null 2>&1 && command -v c++ >/dev/null 2>&1 && [ -d "$SCRIPT_DIR/native/omega-http-core" ]; then
        info "Compilation locale du moteur natif (une à deux minutes)..."
        NATIVE_LOG="$(mktemp)"
        LOCAL_BUILD="$SCRIPT_DIR/native/omega-http-core/build-local"
        if cmake -S "$SCRIPT_DIR/native/omega-http-core" -B "$LOCAL_BUILD" -DCMAKE_BUILD_TYPE=Release >"$NATIVE_LOG" 2>&1 \
            && cmake --build "$LOCAL_BUILD" -j "$(nproc)" >>"$NATIVE_LOG" 2>&1 \
            && "$LOCAL_BUILD/omega_tests" >>"$NATIVE_LOG" 2>&1; then
            mkdir -p "$SCRIPT_DIR/bin"
            install -m 0755 "$LOCAL_BUILD/omega-http-core" "$NATIVE_BIN"
        fi
        if native_ok; then
            ok "Moteur natif compilé sur cette machine ($("$NATIVE_BIN" --version))."
            if grep -q "PCRE2 introuvable" "$NATIVE_LOG"; then
                warn "PCRE2 absent : avec le WAF, le moteur natif fait inspecter chaque requête par Python (plus lent)."
                tip "Installez PCRE2 (ex. apt install libpcre2-dev, pacman -S pcre2) puis relancez ce script."
            fi
            rm -f "$NATIVE_LOG"
        else
            warn "Échec de la compilation locale du moteur natif (détails : $NATIVE_LOG)."
            tip "Il faut cmake, un compilateur C++20 et les en-têtes OpenSSL 3, PCRE2 conseillé (ex. apt install cmake g++ libssl-dev libpcre2-dev)."
        fi
    fi
    if ! native_ok; then
        tip "omega-serv fonctionne normalement avec le moteur Python ; le moteur natif reste indisponible, raison affichée dans Configuration de base."
    fi
fi

# -------------------------------------------------------------------------
# 4. Verification de la presence d'openssl (necessaire pour tout ce qui
#    touche aux certificats TLS - le reste du serveur fonctionne sans).
# -------------------------------------------------------------------------
if command -v openssl >/dev/null 2>&1; then
    ok "openssl détecté ($(openssl version))."
else
    warn "openssl introuvable : les commandes 'certs *' (TLS auto-signe, CA locale) ne fonctionneront pas."
    tip "Le reste d'omega-serv (statique, WAF, auth, FastCGI) fonctionne normalement sans openssl."
fi

# -------------------------------------------------------------------------
# 5. Verification de la presence de certbot (necessaire uniquement pour
#    l'assistant Let's Encrypt/ACME et son renouvellement automatique -
#    le reste du serveur, TLS auto-signe/CA locale inclus, fonctionne
#    sans). Jamais installe ici : binaire systeme (paquet de la
#    distribution ou pipx), pas une dependance Python du projet.
# -------------------------------------------------------------------------
if command -v certbot >/dev/null 2>&1; then
    ok "certbot détecté ($(certbot --version 2>&1 | head -n1))."
else
    warn "certbot introuvable : l'assistant Let's Encrypt (TLS -> Assistant Let's Encrypt) ne fonctionnera pas."
    tip "Installez-le via le gestionnaire de paquets de votre distribution (ex: pacman -S certbot, apt install certbot) si vous prevoyez un certificat public auto-hebergé."
fi

# -------------------------------------------------------------------------
# 6. Alias (optionnel) — bash et zsh, quel que soit celui réellement utilisé.
#    Pas de sudo ici : l'installation elle-meme ne requiert aucun privilege
#    root (voir l'installation d'un service systeme, une etape separee).
# -------------------------------------------------------------------------
ALIAS_LINE="alias serv=\"${SCRIPT_DIR}/omega-serv.sh\""

for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    rc_name="$(basename "$rc")"
    if grep -qxF "$ALIAS_LINE" "$rc" 2>/dev/null; then
        info "Alias déjà présent dans $rc_name."
    elif echo "$ALIAS_LINE" >> "$rc" 2>/dev/null; then
        ok "Alias ajouté à $rc_name."
    else
        warn "Impossible d'ajouter l'alias à $rc_name."
    fi
done

# -------------------------------------------------------------------------
# 6b. Page de manuel (man omega-serv) — dossier de l'utilisateur, pas de
#     sudo. `man` le lit des que ~/.local/bin est dans le PATH (man-db
#     associe <dossier>/bin a <dossier>/share/man) ; sinon, lecture directe
#     du fichier fourni dans docs/.
# -------------------------------------------------------------------------
MAN_DIR="$HOME/.local/share/man/man1"
if mkdir -p "$MAN_DIR" 2>/dev/null && cp "$SCRIPT_DIR/docs/omega-serv.1" "$MAN_DIR/omega-serv.1" 2>/dev/null; then
    ok "Page de manuel installée : man omega-serv"
else
    warn "Page de manuel non installée - lisible directement : man $SCRIPT_DIR/docs/omega-serv.1"
fi

# -------------------------------------------------------------------------
# 7. Recuperation automatique d'une ancienne installation, SANS AUCUNE
#    QUESTION (2026-09-28, retour utilisateur : "il faut penser
#    multi-machines et multi-utilisateur, une mise a jour a pour principe
#    d'upgrader donc il doit recuperer ce qui est deja existant" +
#    "jamais vu une mise a jour ou l'installateur demande une
#    restauration de dossier apres avoir execute" - donc jamais de
#    prompt interactif, une detection et une action automatiques ou
#    rien). Ne se declenche QUE si config/omega-serve.json est absent
#    ICI (extraction dans un dossier neuf plutot que par-dessus
#    l'existant - une extraction par-dessus laisse deja ce fichier en
#    place, cette etape entiere est alors silencieusement sautee, voir
#    section "Mise a jour" du README) ET qu'un seul dossier voisin
#    ressemble sans ambiguite a une ancienne installation (config/
#    omega-serve.json y est present) - jamais d'action sur un signal
#    ambigu (plusieurs candidats, ou aucun) : dans ces cas, rien n'est
#    fait, aucun message d'erreur, l'installation reste une simple
#    premiere installation normale.
# -------------------------------------------------------------------------
if [ ! -f "$SCRIPT_DIR/config/omega-serve.json" ]; then
    CANDIDATES=()
    for dir in "$SCRIPT_DIR"/../*omega-serv*/; do
        dir="${dir%/}"
        if [ "$dir" != "$SCRIPT_DIR" ] && [ -f "$dir/config/omega-serve.json" ]; then
            CANDIDATES+=("$dir")
        fi
    done
    if [ "${#CANDIDATES[@]}" -eq 1 ]; then
        info "Ancienne installation detectee : ${CANDIDATES[0]}"
        "$SCRIPT_DIR/migrate-state.sh" "${CANDIDATES[0]}" --yes
    elif [ "${#CANDIDATES[@]}" -gt 1 ]; then
        warn "Plusieurs anciennes installations voisines detectees, aucune recuperee automatiquement (ambigu) :"
        for c in "${CANDIDATES[@]}"; do echo "    $c"; done
        tip "Recuperez manuellement : ${SCRIPT_DIR}/migrate-state.sh <dossier>"
    fi
fi

# -------------------------------------------------------------------------
# 8. Jeton d'installation (var/omega-jeton.json, contrats d'interconnexion
#    2026-11-10) : lu par omega-connect, sans rien executer, pour savoir
#    quel outil est la, ou, sous quel compte. Jamais en root (refuse par la
#    commande elle-meme) ; un echec ne bloque jamais l'installation.
# -------------------------------------------------------------------------
if "$SCRIPT_DIR/.venv/bin/python" -m omega_serv synchro jeton >/dev/null 2>&1; then
    ok "Jeton d'installation à jour (var/omega-jeton.json)."
else
    warn "Jeton d'installation non écrit : omega-connect ne verra pas cette installation tant qu'il manque."
    tip "Il sera créé à la prochaine ouverture d'omega-serv, ou avec : ${SCRIPT_DIR}/omega-serv.sh synchro jeton"
fi

echo ""
ok "Installation terminée."
tip "Lancez Omega-Serv avec : ${SCRIPT_DIR}/omega-serv.sh serve (ou 'serv serve' dans un nouveau terminal si l'alias vient d'être ajouté)."
if [ ! -f "$SCRIPT_DIR/config/omega-serve.json" ]; then
    tip "Commencez par : ${SCRIPT_DIR}/omega-serv.sh config init"
fi

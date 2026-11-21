"""Deuxième temps de demo_instance.py : exécuté dans un processus relancé avec HOME=<dest>/home et
PYTHONPATH=<dest>/omega-serv/src, il importe la COPIE d'omega-serv et écrit les données de démonstration avec les
dépôts, fonctions de hachage et services de l'application (formats exacts, jamais réécrits à la main quand une
fonction publique existe).

Toutes les adresses sont des adresses de documentation : 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24 (RFC 5737),
2001:db8::/32 (RFC 3849) ; 127.0.0.1 pour le local. Les noms de domaine sont en exemple.org.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import socket
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SERVER_PORT = 18080
STAGING_PORT = 18081
DOCS_PORT = 18082
ADMIN_PORT = 19643
BACKEND_PORTS = (18101, 18102, 18103)
SERVICE_NAME = "omega-serv-demo"
SERVER_NAME = "exemple.org"

RNG = random.Random(20261118)  # données reproductibles d'un passage à l'autre (sauf horodatages « maintenant »)
NOW = datetime.now(UTC).replace(microsecond=0)

# Adresses de documentation uniquement.
HOSTILE_IPS = ("203.0.113.66", "203.0.113.77", "198.51.100.23", "198.51.100.200", "203.0.113.150",
               "2001:db8:bad::17", "198.51.100.41", "203.0.113.9")
VISITOR_IPS = tuple([f"192.0.2.{n}" for n in (10, 14, 27, 33, 45, 58, 61, 72, 88, 91, 104, 117, 125, 138, 142, 156,
                                               163, 177, 189, 201, 214, 228, 233, 247)]
                    + [f"198.51.100.{n}" for n in (5, 12, 19, 64, 81, 99, 130, 177)]
                    + ["2001:db8:1::25", "2001:db8:2::4a", "2001:db8:3::101", "2001:db8:42::7"])
BOT_IPS = ("198.51.100.150", "198.51.100.151", "203.0.113.200", "2001:db8:b07::1")
ADMIN_CLIENT_IPS = ("127.0.0.1", "192.0.2.10", "2001:db8:1::25")


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, data: Any, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


# ---------------------------------------------------------------------------------------------------------------------
# Certificats (openssl, autosignés, CN/SAN en exemple.org)


def _openssl_self_signed(cert: Path, key: Path, common_name: str, sans: tuple[str, ...],
                         not_before: datetime, not_after: datetime, organization: str = "Exemple SARL") -> None:
    """Certificat autosigné avec une période de validité choisie (le premier essai garde des dates réalistes :
    émis il y a quelques semaines ; repli sur -days si l'openssl local ne connaît pas -not_before)."""
    cert.parent.mkdir(parents=True, exist_ok=True)
    san = "subjectAltName=" + ",".join(f"DNS:{name}" for name in sans)
    base = ["openssl", "req", "-x509", "-sha256", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
            "-nodes", "-keyout", str(key), "-out", str(cert),
            "-subj", f"/O={organization}/CN={common_name}", "-addext", san]
    dated = base + ["-not_before", not_before.strftime("%Y%m%d%H%M%SZ"),
                    "-not_after", not_after.strftime("%Y%m%d%H%M%SZ")]
    result = subprocess.run(dated, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        days = max(1, (not_after - NOW).days)
        subprocess.run(base + ["-days", str(days)], capture_output=True, text=True, check=True)
    key.chmod(0o600)
    cert.chmod(0o644)


def make_certificates(root: Path) -> None:
    certs = root / "secure" / "certificates"
    # Site (TLS direct) : 90 jours, émis il y a 80 jours -> expire dans ~10 jours (alerte certificat).
    _openssl_self_signed(certs / "server" / "server.pem", certs / "server" / "server.key", SERVER_NAME,
                         (SERVER_NAME, f"www.{SERVER_NAME}", f"boutique.{SERVER_NAME}", f"app.{SERVER_NAME}"),
                         NOW - timedelta(days=80), NOW + timedelta(days=10, hours=6))
    # Administration web (tls own) : ~200 jours restants.
    _openssl_self_signed(certs / "admin" / "admin.pem", certs / "admin" / "admin.key", f"admin.{SERVER_NAME}",
                         (f"admin.{SERVER_NAME}",), NOW - timedelta(days=165), NOW + timedelta(days=200))
    # Certificat d'un autre site gardé sous secure/certificates (échéance intermédiaire).
    _openssl_self_signed(certs / "docs" / "docs.pem", certs / "docs" / "docs.key", f"docs.{SERVER_NAME}",
                         (f"docs.{SERVER_NAME}",), NOW - timedelta(days=30), NOW + timedelta(days=60))


# ---------------------------------------------------------------------------------------------------------------------
# Configuration (base : config/omega-serve.json du projet, chemins relatifs, puis remplie)


def build_config(root: Path, native_available: bool) -> dict[str, Any]:
    base_path = root / "config" / "omega-serve.base.json"
    data = json.loads(base_path.read_text(encoding="utf-8"))
    base_path.unlink()
    data["profile"] = "hardened"
    data["server"].update({
        "bind": "127.0.0.1", "port": SERVER_PORT, "server_name": SERVER_NAME,
        "index_files": ["index.html", "index.php"],
        "engine": "native" if native_available else "python", "workers": 1,
        "max_request_size": 20 * 1024 * 1024,
    })
    data["security"].update({
        "allowed_methods": ["GET", "HEAD", "POST", "PUT", "DELETE"],
        "hsts_enabled": True, "hsts_max_age": 31536000,
        "csp_zones": [{"path_prefix": "/boutique/",
                       "policy": "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'"}],
    })
    data["tls"] = {
        "enabled": True, "mode": "direct",
        "certificate": {"certificate_path": "secure/certificates/server/server.pem",
                        "private_key_path": "secure/certificates/server/server.key",
                        "chain_path": "", "private_key_passphrase_env": ""},
        "protocols": {"min_version": "TLS1.2", "max_version": "TLS1.3"},
    }
    options = data["options"]
    waf = options["waf"]
    waf.update({
        "enabled": True, "mode": "block", "on_internal_error": "fail-closed",
        "scoring": {"block_threshold": 5, "high_score_threshold": 8, "response_status": 403},
        "rate_limit": {
            "enabled": True,
            "global": {"key": "client_ip", "requests": 120, "window_seconds": 60, "response_status": 429},
            "path_policies": [{"prefix": "/api/", "requests": 60, "window_seconds": 60},
                              {"prefix": "/membres/", "requests": 20, "window_seconds": 60}],
            "source_policies": [{"network": "192.0.2.0/28", "requests": 600, "window_seconds": 60,
                                 "trusted": True}],
        },
        "reputation": {"enabled": True, "suspicious_threshold": 3, "window_seconds": 300, "auto_block": True,
                       "auto_block_duration_seconds": 3600, "auto_block_max_entries": 200},
        "blocklist": {"enabled": True, "path": "var/lib/waf/blocklist.json", "allow_temporary_entries": True},
        "exclusions": {"extensions": [".css", ".js", ".woff2"], "path_prefixes": ["/healthz"]},
    })
    options["auth"] = {"enabled": True}
    options["dirlisting"].update({"enabled": True, "zone_prefixes": ["/docs/telechargements/"]})
    options["fastcgi"] = {
        "enabled": True,
        "zones": [
            {"url_prefix": "/boutique/", "script_root": "apps/boutique", "socket_path": "var/run/php-fpm-boutique.sock",
             "connect_timeout_seconds": 5.0, "read_timeout_seconds": 30.0, "allowed_extensions": [".php"],
             "index_files": ["index.php"], "allowed_scripts": ["index.php", "panier.php", "commande.php"],
             "enabled": True},
            {"url_prefix": "/gestion/", "script_root": "apps/gestion", "socket_path": "var/run/php-fpm-gestion.sock",
             "connect_timeout_seconds": 5.0, "read_timeout_seconds": 120.0, "allowed_extensions": [".php"],
             "index_files": ["index.php"], "allowed_scripts": [], "enabled": True,
             "max_request_size": 64 * 1024 * 1024},
            {"url_prefix": "/wiki/", "script_root": "apps/wiki", "socket_path": "var/run/php-fpm-wiki.sock",
             "connect_timeout_seconds": 5.0, "read_timeout_seconds": 30.0, "allowed_extensions": [".php"],
             "index_files": ["index.php"], "allowed_scripts": [], "enabled": False},
        ],
    }
    options["cache"] = {"enabled": True, "zones": [
        {"path_prefix": "/blog/images/", "cache_control": "public, max-age=604800, immutable"},
        {"path_prefix": "/docs/", "cache_control": "public, max-age=3600"},
    ]}
    options["upload"] = {
        "enabled": True,
        "zones": [{"url_prefix": "/depot/", "storage_path": "var/uploads/depot",
                   "policy": {"max_file_size_bytes": 8 * 1024 * 1024,
                              "allowed_extensions": [".pdf", ".png", ".jpg", ".zip"],
                              "allowed_content_types": ["application/pdf", "image/png", "image/jpeg",
                                                        "application/zip"],
                              "max_files_per_zone": 500, "max_total_bytes_per_zone": 2 * 1024 ** 3}}],
    }
    options["aliases"] = {"enabled": True, "list": [
        {"url_prefix": "/docs/v2/", "target_path": "webroot/docs/version-2"},
        {"url_prefix": "/medias/", "target_path": "webroot/blog/images"},
    ]}
    options["rewrites"] = {"enabled": True, "list": [
        {"match_prefix": "/blog/articles/", "replacement_prefix": "/blog/"},
        {"match_prefix": "/aide/", "replacement_prefix": "/docs/"},
    ]}
    options["redirects"] = {"enabled": True, "list": [
        {"url_prefix": "/ancien-blog/", "destination": "/blog/", "status_code": 301},
        {"url_prefix": "/promo", "destination": f"https://boutique.{SERVER_NAME}/soldes", "status_code": 302},
        {"url_prefix": "/contact.html", "destination": "/docs/contact.html", "status_code": 308},
    ]}
    options["access_control"] = {"enabled": True, "list": [
        {"path_prefix": "/docs/brouillons/", "verdict": "deny"},
        {"path_prefix": "/blog/", "verdict": "deny", "extensions": [".md", ".yml"]},
        {"path_prefix": "/docs/publics/", "verdict": "allow"},
    ]}
    options["trusted_proxy"] = {"enabled": True, "trusted_networks": ["127.0.0.1/32", "::1/128"]}  # appels internes de la TUI (BACKENDS)
    options["error_pages"] = {"enabled": True, "custom_dir": "webroot/.errors/"}
    active_defense = options["active_defense"]
    active_defense.update({"enabled": True, "mode": "enforce"})
    active_defense["ioc"]["enabled"] = True
    active_defense["logging"]["enhanced_capture"] = True
    riposte = options["riposte"]
    riposte["enabled"] = True
    riposte["exemptions"] = ["192.0.2.0/28", "2001:db8:1::/64"]
    for policy in riposte["policies"]:
        policy["enabled"] = True
    options["reverse_proxy"] = {
        "enabled": True,
        "cache_max_size_mb": 256,
        "zones": [
            {"url_prefix": "/api/",
             "upstreams": [{"host": "127.0.0.1", "port": BACKEND_PORTS[0], "weight": 2},
                           {"host": "127.0.0.1", "port": BACKEND_PORTS[1], "weight": 1}],
             "connect_timeout_seconds": 3.0, "read_timeout_seconds": 30.0, "preserve_host_header": True,
             "load_balancing": "round_robin", "unhealthy_after": 3, "healthy_after": 2,
             "cache_enabled": True, "cache_default_ttl_seconds": 30.0},
            {"url_prefix": "/app/",
             "upstreams": [{"host": "127.0.0.1", "port": BACKEND_PORTS[2]}],
             "connect_timeout_seconds": 5.0, "read_timeout_seconds": 60.0, "preserve_host_header": True,
             "websocket_enabled": True, "websocket_idle_timeout_seconds": 900.0},
        ],
    }
    options["admin_web"] = {
        "enabled": True, "bind": "127.0.0.1", "port": ADMIN_PORT, "tls": "own",
        "certificate_path": "secure/certificates/admin/admin.pem",
        "private_key_path": "secure/certificates/admin/admin.key",
        "allowed_networks": ["127.0.0.0/8", "::1/128", "192.0.2.0/24", "2001:db8:1::/48"],
        "history": True,
        "theme": "tui",
        "alerts": {"disque": 85, "memoire": 90, "processeur": 95, "erreurs_5xx": 5, "certificat": 30,
                   "temperature": 85, "batterie": False},
        "stats_mask_ip": False,
    }
    return data


# ---------------------------------------------------------------------------------------------------------------------
# Webroot (3 petits sites) et applications FastCGI (hors webroot)

_PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>{title}</title>
<link rel="stylesheet" href="/assets/site.css"></head>
<body><header><h1>{title}</h1></header><main>{body}</main>
<footer>exemple.org - site de démonstration</footer></body></html>
"""


def _page(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_PAGE.format(title=title, body=body), encoding="utf-8")


def make_webroot(root: Path) -> None:
    web = root / "webroot"
    (web / "assets").mkdir(parents=True, exist_ok=True)
    (web / "assets" / "site.css").write_text(
        "body{font-family:sans-serif;max-width:48rem;margin:auto;color:#222}header{border-bottom:1px solid #ccc}\n",
        encoding="utf-8")
    _page(web / "index.html", "Exemple.org", "<p>Bienvenue. <a href='/blog/'>Blog</a> · "
          "<a href='/boutique/'>Boutique</a> · <a href='/docs/'>Documentation</a></p>")
    # Blog
    _page(web / "blog" / "index.html", "Le blog d'exemple.org",
          "<ul><li><a href='/blog/2026/11/migration-tls.html'>Migration TLS</a></li>"
          "<li><a href='/blog/2026/10/sauvegardes.html'>Nos sauvegardes</a></li></ul>")
    _page(web / "blog" / "2026" / "11" / "migration-tls.html", "Migration TLS", "<p>Article de démonstration.</p>")
    _page(web / "blog" / "2026" / "10" / "sauvegardes.html", "Nos sauvegardes", "<p>Article de démonstration.</p>")
    (web / "blog" / "images").mkdir(parents=True, exist_ok=True)
    (web / "blog" / "images" / "logo.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><circle cx='32' cy='32' r='30'/></svg>\n",
        encoding="utf-8")
    (web / "blog" / "feed.xml").write_text("<?xml version='1.0'?><rss version='2.0'><channel>"
                                           "<title>exemple.org</title></channel></rss>\n", encoding="utf-8")
    # Boutique : seulement les fichiers statiques ; le PHP vit hors webroot (apps/boutique, zone FastCGI /boutique/).
    (web / "boutique" / "static").mkdir(parents=True, exist_ok=True)
    (web / "boutique" / "static" / "boutique.css").write_text(".produit{border:1px solid #ddd}\n", encoding="utf-8")
    # Documentation (+ dossier listé, + version 2 servie par alias)
    _page(web / "docs" / "index.html", "Documentation", "<p><a href='/docs/installation.html'>Installation</a></p>")
    _page(web / "docs" / "installation.html", "Installation", "<pre>tar xzf exemple-1.4.tar.gz</pre>")
    _page(web / "docs" / "contact.html", "Contact", "<p>contact@exemple.org</p>")
    _page(web / "docs" / "version-2" / "index.html", "Documentation v2", "<p>Version 2.</p>")
    downloads = web / "docs" / "telechargements"
    downloads.mkdir(parents=True, exist_ok=True)
    for name, size in (("exemple-1.4.tar.gz", 48_213), ("exemple-1.3.tar.gz", 46_870), ("notes-1.4.txt", 2_310)):
        (downloads / name).write_bytes(bytes(RNG.getrandbits(8) for _ in range(size)))
    (downloads / "README.txt").write_text("Archives publiées de l'application d'exemple.\n", encoding="utf-8")
    (web / "robots.txt").write_text("User-agent: *\nDisallow: /gestion/\n", encoding="utf-8")
    (web / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    # Fichiers oubliés dans le webroot, pour l'écran Audit (fichiers sensibles nommés, contenu réel ; fictifs)
    (web / "blog" / ".env").write_text("DB_HOST=127.0.0.1\nDB_USER=blog\nDB_PASSWORD=exemple-a-changer\n",
                                       encoding="utf-8")
    (web / "boutique" / "sauvegarde.sql").write_text("", encoding="utf-8")
    git_dir = web / "docs" / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    # Applications PHP (FastCGI), hors webroot
    for app, files in (("boutique", ("index.php", "panier.php", "commande.php")),
                       ("gestion", ("index.php", "export.php")), ("wiki", ("index.php",))):
        for name in files:
            target = root / "apps" / app / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"<?php\n// {app}/{name} - application de démonstration\necho 'exemple.org';\n",
                              encoding="utf-8")
    # Sockets PHP-FPM des zones actives : de vrais fichiers socket Unix (jamais écoutés, aucune surface réseau),
    # pour que la vérification de configuration trouve le chemin attendu.
    run = root / "var" / "run"
    run.mkdir(parents=True, exist_ok=True)
    previous_cwd = Path.cwd()
    os.chdir(run)  # chemin relatif : la limite de 108 octets des sockets Unix ne dépend plus de <dest>
    try:
        for name in ("php-fpm-boutique.sock", "php-fpm-gestion.sock"):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as unix_socket:
                unix_socket.bind(name)
    finally:
        os.chdir(previous_cwd)
    (root / "var" / "uploads" / "depot").mkdir(parents=True, exist_ok=True)
    for name, size in (("facture-2026-10.pdf", 81_920), ("photo-vitrine.jpg", 245_760)):
        (root / "var" / "uploads" / "depot" / name).write_bytes(b"\0" * size)


# ---------------------------------------------------------------------------------------------------------------------
# Authentification du site (utilisateurs + zones), via les dépôts de l'application


def make_site_auth(root: Path) -> None:
    from omega_serv.domain.security.auth.entities import AuthZone, UserAccount
    from omega_serv.domain.security.auth.password_hashing import hash_password
    from omega_serv.infrastructure.auth.auth_zones_repository import JsonAuthZonesRepository
    from omega_serv.infrastructure.auth.users_repository import JsonUsersRepository
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

    filesystem = LocalFilesystem()
    users = tuple(UserAccount(name, hash_password(f"demo-{name}-2026")) for name in
                  ("claire", "damien", "emma", "redaction"))
    JsonUsersRepository(filesystem, root / "secure" / "auth" / "users.json").save(users)
    zones = (
        AuthZone("/membres/", "Espace membres", ("claire", "damien", "emma")),
        # Zone « à modifier » : écriture permise (POST/PUT/DELETE) pour l'équipe de rédaction seulement.
        AuthZone("/gestion/", "Gestion de la boutique", ("claire", "redaction"),
                 ("GET", "HEAD", "POST", "PUT", "DELETE")),
    )
    JsonAuthZonesRepository(filesystem, root / "secure" / "auth" / "zones.json").save(zones)


# ---------------------------------------------------------------------------------------------------------------------
# Vérification de la configuration avec les chargeurs de l'application (copie importée)


def check_config(root: Path) -> list[str]:
    from omega_serv.application.config.load_config import load_config
    from omega_serv.application.config.validate_config import validate_config_environment
    from omega_serv.bootstrap import paths
    from omega_serv.bootstrap.container import DependencyContainer

    if paths.PROJECT_ROOT.resolve() != root.resolve():
        raise SystemExit(f"La copie importée n'est pas celle de la démo : PROJECT_ROOT={paths.PROJECT_ROOT}")
    container = DependencyContainer(project_root=root)
    result = load_config(container.configuration, root / "config" / "omega-serve.json")
    if result.config is None:
        return [f"structure : {error}" for error in result.errors]
    return [f"environnement : {error}" for error in
            validate_config_environment(result.config, container.filesystem, root)]


# ---------------------------------------------------------------------------------------------------------------------
# Administration web : comptes, alertes, sessions, historique, statistiques, état, maître, flotte, pare-feu


def make_admin_accounts(root: Path) -> None:
    """« alice » (administration, TOTP actif, 7 codes de secours restants sur 10) et « bruno » (lecture), par les
    fonctions de l'application (hachage scrypt, confirmation TOTP avec un code juste)."""
    import time

    from omega_serv.application.admin_web import manage_accounts
    from omega_serv.domain.admin_web import totp
    from omega_serv.infrastructure.admin_web.accounts_repository import JsonAdminAccountsRepository
    from omega_serv.infrastructure.admin_web.used_backup_codes import (
        USED_BACKUP_CODES_RELATIVE_PATH,
        UsedBackupCodes,
    )
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

    filesystem = LocalFilesystem()
    store = JsonAdminAccountsRepository(filesystem, root / "secure" / "auth" / "admin-web.json")
    for username, password, role in (("alice", "Demo-Alice-2026!", "administration"),
                                     ("bruno", "Demo-Bruno-2026!", "lecture")):
        result = manage_accounts.add_account(store, username, password, role)
        assert result.success, result.message
    secret = manage_accounts.new_totp_secret()
    now = time.time()
    confirmed = manage_accounts.confirm_totp(store, "alice", secret, totp.code_at(secret, totp.step_of(now)))
    assert confirmed.success, confirmed.message
    alice = next(account for account in store.load() if account.username == "alice")
    used = UsedBackupCodes(filesystem, root / USED_BACKUP_CODES_RELATIVE_PATH)
    for code_hash in alice.backup_code_hashes[:3]:
        used.add(code_hash)


def _alert(key: str, rule: str, subject: str, opened: datetime, value: float | None, threshold: float | None,
           worst: float | None, level: str = "", closed: datetime | None = None) -> dict[str, Any]:
    from omega_serv.domain.admin_web.alerts import Alert

    return Alert(key, rule, subject, opened.timestamp(), value, threshold, worst, level,
                 closed.timestamp() if closed else None).to_dict()


def make_admin_alerts(root: Path) -> None:
    from omega_serv.infrastructure.admin_web.alert_store import AlertStore
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

    cert = "secure/certificates/server/server.pem"
    active = [
        _alert(f"certificat:{cert}", "certificat", cert, NOW - timedelta(days=4, hours=3), 10.0, 30.0, 10.0, "14"),
        _alert("disque", "disque", "", NOW - timedelta(hours=2, minutes=17), 87.4, 85.0, 88.1),
    ]
    history_specs = [
        ("memoire", "memoire", "", 27, 0.6, 91.8, 90.0, 94.2, ""),
        ("processeur", "processeur", "", 24, 0.2, 97.5, 95.0, 99.1, ""),
        ("backend:/api/127.0.0.1:18102", "backend", "/api/127.0.0.1:18102", 21, 0.05, 1.0, 1.0, 1.0, ""),
        ("erreurs_5xx", "erreurs_5xx", "", 18, 0.3, 7.4, 5.0, 11.2, ""),
        (f"incident:{INCIDENT_IDS[6]}", "incident", INCIDENT_IDS[6], 13, 1.5, 1.0, 1.0, 1.0, ""),
        ("memoire", "memoire", "", 9, 0.4, 90.6, 90.0, 92.0, ""),
        ("backend:/app/127.0.0.1:18103", "backend", "/app/127.0.0.1:18103", 5, 0.1, 1.0, 1.0, 1.0, ""),
        (f"certificat:{cert}", "certificat", cert, 16, 12.0, 30.0, 30.0, 30.0, "30"),
    ]
    history = []
    for key, rule, subject, days_ago, duration_hours, value, threshold, worst, level in history_specs:
        opened = NOW - timedelta(days=days_ago, hours=RNG.randint(0, 20))
        history.append(_alert(key, rule, subject, opened, value, threshold, worst, level,
                              opened + timedelta(hours=duration_hours)))
    history.sort(key=lambda item: item["opened_at"])
    store = AlertStore(LocalFilesystem(), root)
    store.save({"version": 1, "active": active, "history": history})
    # Journal des événements d'alerte (ordre chronologique).
    events: list[tuple[float, str]] = []
    for item in history + active:
        subject = f" sujet={item['subject']}" if item["subject"] else ""
        level = f" palier={item['level']}" if item["level"] else ""
        events.append((item["opened_at"], (f"ouverte {item['rule']}{subject} valeur={item['value']:g} "
                                          f"seuil={item['threshold']:g}{level}")))
        if item["closed_at"]:
            events.append((item["closed_at"], f"fermee {item['rule']}{subject}"))
    events.append((active[0]["opened_at"] + 86400 * 3, (f"aggravee certificat sujet={cert} valeur=10 seuil=30 "
                                                       "palier=14")))
    with (root / "var" / "log" / "alertes.log").open("w", encoding="utf-8") as log:
        for at, text in sorted(events):
            log.write(f"{datetime.fromtimestamp(at, UTC).strftime('%Y-%m-%dT%H:%M:%SZ')} {text}\n")


def make_admin_sessions(root: Path) -> None:
    import hashlib

    from omega_serv.infrastructure.admin_web.session_files import SessionFiles
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

    sessions = []
    for token, account, address, mode, opened_minutes, idle_seconds in (
            ("demo-session-1", "alice", "192.0.2.10", "administration", 42, 8),
            ("demo-session-2", "bruno", "2001:db8:1::25", "tableau", 125, 64),
            ("demo-session-3", "alice", "127.0.0.1", "tableau", 7, 2)):
        sessions.append({"id": hashlib.sha256(token.encode()).hexdigest()[:12], "compte": account,
                         "adresse": address, "mode": mode,
                         "ouverte": int((NOW - timedelta(minutes=opened_minutes)).timestamp()),
                         "activite": int((NOW - timedelta(seconds=idle_seconds)).timestamp())})
    SessionFiles(LocalFilesystem(), root, clock=lambda: NOW.timestamp()).publish(sessions)


def _history_value(series: str, t: float) -> float | None:
    """Courbes plausibles : cycle de la journée (pic en fin d'après-midi), un peu de bruit."""
    import math

    hour = (t / 3600) % 24
    day_cycle = 0.5 + 0.5 * math.sin((hour - 10) / 24 * 2 * math.pi)  # 0 vers 4 h, 1 vers 16 h
    noise = RNG.random()
    days_left = (NOW.timestamp() - t) / 86400
    values = {
        "cpu": 6 + 28 * day_cycle + 8 * noise, "mem": 38 + 14 * day_cycle + 3 * noise, "swap": 4 + noise,
        "load1": 0.3 + 1.6 * day_cycle + 0.4 * noise, "load5": 0.3 + 1.3 * day_cycle + 0.2 * noise,
        "load15": 0.3 + 1.1 * day_cycle + 0.1 * noise,
        "net_in": 40_000 + 420_000 * day_cycle * (0.7 + 0.6 * noise),
        "net_out": 120_000 + 1_900_000 * day_cycle * (0.7 + 0.6 * noise),
        "rps": 0.4 + 9 * day_cycle * (0.6 + 0.8 * noise),
        "site_in": 15_000 + 160_000 * day_cycle * (0.7 + 0.6 * noise),
        "site_out": 90_000 + 1_500_000 * day_cycle * (0.7 + 0.6 * noise),
        "tcp": 18 + 140 * day_cycle + 20 * noise, "sockets": 210 + 160 * day_cycle + 30 * noise,
        "disk_read": 20_000 + 300_000 * noise * day_cycle, "disk_write": 60_000 + 500_000 * noise * day_cycle,
        "disk_used": 87.4 - days_left * 0.08 + 0.05 * noise, "procs": 240 + 30 * day_cycle + 6 * noise,
        "serv_cpu": 0.8 + 9 * day_cycle * (0.6 + 0.8 * noise), "serv_mem": 31_000_000 + 9_000_000 * day_cycle,
        "temp": 41 + 17 * day_cycle + 4 * noise, "battery": None,
    }
    return values[series]


def make_admin_history(root: Path) -> None:
    """Paliers du format 2 remplis directement (une moyenne et un maximum par tranche), fin de tranche <= maintenant."""
    from omega_serv.domain.admin_web.history import SERIES, TIERS, HistoryRings, _round
    from omega_serv.infrastructure.admin_web.history_store import HistoryStore
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

    rings = HistoryRings()
    now = int(NOW.timestamp())
    for tier in TIERS:
        ring = rings.rings[tier.name]
        last_end = (now // tier.step) * tier.step
        for index in range(tier.size - 1, -1, -1):
            end = last_end - index * tier.step
            point: dict[str, Any] = {"t": end}
            for series in SERIES:
                value = _history_value(series, end - tier.step / 2)
                point[series] = _round(value)
                if tier.keeps_max:
                    point[series + "_max"] = None if value is None else _round(value * (1.15 + 0.3 * RNG.random()))
            ring.points.append(point)
    HistoryStore(LocalFilesystem(), root).save(rings.to_dict())


def make_admin_state(root: Path, admin_bind: str) -> None:
    from omega_serv.domain.admin_web.run_state import AdminRunState
    from omega_serv.infrastructure.admin_web.run_state_store import AdminRunStateStore
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

    # PID 1 : toujours vivant (le fichier est ignoré si le PID est mort) ; réécrit par le vrai processus
    # d'administration dès qu'il démarre.
    AdminRunStateStore(LocalFilesystem(), root).save(AdminRunState(1, True, admin_bind, ADMIN_PORT, "", ""))


def make_admin_master_and_fleet(root: Path) -> None:
    from omega_serv.application.admin_web.firewall_setup import FirewallRecord
    from omega_serv.domain.admin_web.master import AcceptedMaster, Fleet, FollowedInstance
    from omega_serv.domain.security.auth.password_hashing import hash_password
    from omega_serv.infrastructure.admin_web.firewall_record_store import FirewallRecordStore
    from omega_serv.infrastructure.admin_web.master_store import FleetStore, MasterStore
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

    filesystem = LocalFilesystem()
    iso = "%Y-%m-%dT%H:%M:%SZ"
    MasterStore(filesystem, root).save_master(AcceptedMaster(
        "5e0d1c2b3a4f5e6d7c8b9a0f1e2d3c4b", "console@poste-admin", hash_password("jeton-de-demonstration"),
        "administration", (NOW - timedelta(days=12, hours=5)).strftime(iso),
        (NOW - timedelta(minutes=3)).strftime(iso)))
    fleet = FleetStore(filesystem, root)
    fleet.identity(lambda: "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d", "omega-serv@exemple.org")
    fleet.save(Fleet((
        FollowedInstance("a1b2c3d4e5f6", "staging", "omega-serv", address="127.0.0.1", port=19644,
                         token="jeton-demo-staging", fingerprint="",
                         added=(NOW - timedelta(days=9)).strftime(iso)),
        FollowedInstance("0f1e2d3c4b5a", "api-sante", "sonde", url=f"http://127.0.0.1:{BACKEND_PORTS[0]}/sante",
                         added=(NOW - timedelta(days=6)).strftime(iso)),
    )))
    # Ouverture partielle faite il y a 12 jours (seulement 192.0.2.0/24) : le réseau 2001:db8:1::/48 ajouté depuis
    # n'est pas couvert, le bilan propose donc « Ouvrir le port » (quand l'administration web n'écoute pas en
    # boucle locale et que omega-fire est inscrit dans la zone omega-connect).
    FirewallRecordStore(filesystem, root).save(FirewallRecord(
        ADMIN_PORT, ("192.0.2.0/24",), (NOW - timedelta(days=12)).isoformat(timespec="seconds")))


# ---------------------------------------------------------------------------------------------------------------------
# Multi-instance : registre du HOME factice, deux instances fictives légères, zone omega-connect factice


def _light_instance(dest: Path, name: str, port: int, admin_port: int | None, root: Path) -> Path:
    """Dossier minimal accepté par l'écran Instances : configuration valide (bind/port, accès distant), version."""
    target = dest / name
    for sub in ("config", "var/log", "var/run", "webroot"):
        (target / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "pyproject.toml", target / "pyproject.toml")
    data = json.loads((root / "config" / "omega-serve.json").read_text(encoding="utf-8"))
    data["server"].update({"port": port, "server_name": f"{name}.{SERVER_NAME}", "engine": "python"})
    data["tls"]["enabled"] = False
    data["security"]["hsts_enabled"] = False
    for option in ("fastcgi", "upload", "reverse_proxy", "auth", "riposte", "active_defense"):
        data["options"][option] = {"enabled": False}
    if admin_port is None:
        data["options"]["admin_web"] = {"enabled": False}
    else:
        data["options"]["admin_web"].update({"port": admin_port, "tls": "none"})
    _write_json(target / "config" / "omega-serve.json", data)
    _write_json(target / "var" / "settings.json", {"theme": "omega-base", "service_name": f"omega-serv-{name}",
                                                   "language": "", "page_language": ""})
    (target / "webroot" / "index.html").write_text(f"<h1>{name}.{SERVER_NAME}</h1>\n", encoding="utf-8")
    return target.resolve()


def make_instances(dest: Path, root: Path) -> None:
    from omega_serv.bootstrap.paths import INSTANCE_REGISTRY_PATH
    from omega_serv.domain.instances.entities import InstanceEntry
    from omega_serv.infrastructure.instances.json_instance_registry import JsonInstanceRegistry

    assert dest.resolve() / "home" in INSTANCE_REGISTRY_PATH.parents, INSTANCE_REGISTRY_PATH
    staging = _light_instance(dest, "staging", STAGING_PORT, ADMIN_PORT + 1, root)
    docs = _light_instance(dest, "docs", DOCS_PORT, None, root)
    entries = [
        InstanceEntry("principale", root.resolve(), "127.0.0.1", SERVER_PORT, SERVICE_NAME,
                      NOW - timedelta(days=41, hours=3)),
        InstanceEntry("staging", staging, "127.0.0.1", STAGING_PORT, "omega-serv-staging",
                      NOW - timedelta(days=17, hours=8)),
        InstanceEntry("docs", docs, "127.0.0.1", DOCS_PORT, "omega-serv-docs", NOW - timedelta(days=6, hours=2)),
    ]
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

    JsonInstanceRegistry(LocalFilesystem(), INSTANCE_REGISTRY_PATH).save(entries)


def make_synchro_zone(dest: Path, root: Path) -> Path:
    """Zone omega-connect factice (lue seulement si la TUI est lancée avec OMEGA_SYNCHRO_DIR=<dest>/synchro) :
    omega-serv (la démo) et omega-fire y sont inscrits. omega-fire.sh est un bouchon inoffensif qui refuse tout."""
    zone = dest / "synchro"
    zone.mkdir()
    fire = dest / "omega-fire"
    fire.mkdir()
    launcher = fire / "omega-fire.sh"
    launcher.write_text("#!/bin/sh\n# Bouchon de démonstration : n'ouvre rien, ne touche à aucun pare-feu.\n"
                        "echo '{\"ok\": false, \"error\": \"omega-fire de démonstration : aucune action\"}'\n"
                        "exit 1\n", encoding="utf-8")
    launcher.chmod(0o755)
    stamp = (NOW - timedelta(days=12)).isoformat(timespec="seconds")
    registry = {
        "format": "omega-registre", "schema_version": 1, "zone": str(zone.resolve()), "state": "active",
        "updated_at": stamp, "created": [],
        "installations": [
            {"installation_id": "3c4d5e6f708192a3b4c5d6e7f8091a2b", "tool": "omega-serv", "instance": "principale",
             "root": str(root.resolve()), "owner": "demo", "version": "3.0.0", "linked_at": stamp,
             "has_sheet": False},
            {"installation_id": "8f7e6d5c4b3a29181716151413121110", "tool": "omega-fire", "instance": "omega-fire",
             "root": str(fire.resolve()), "owner": "demo", "version": "3.6", "linked_at": stamp,
             "has_sheet": False},
        ],
    }
    from omega_lib.synchro.registry import registry_from_dict

    registry_from_dict(registry)  # même validation que la lecture par omega-serv
    _write_json(zone / "registre.json", registry)
    return zone


def make_settings(root: Path) -> None:
    _write_json(root / "var" / "settings.json", {
        "theme": "omega-base", "exports_dir_override": "var/exports", "screenshots_dir_override": "var/screenshots",
        "service_name": SERVICE_NAME, "render_profile_override": "complete", "language": "", "page_language": "",
    })
    for sub in ("exports", "screenshots", "cache"):
        (root / "var" / sub).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------------------------------------------------
# Trafic sur 30 jours : access.log, waf-alerts.log, error.log, active-defense-enriched.jsonl, statistiques du panneau

BROWSERS = (
    (("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 "
     "Safari/537.36"), 34),
    ("Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0", 22),
    (("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 "
     "Safari/605.1.15"), 12),
    (("Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
     "Version/18.1 Mobile/15E148 Safari/604.1"), 14),
    (("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 "
     "Safari/537.36 Edg/131.0.0.0"), 9),
    (("Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/26.0 "
     "Chrome/122.0.0.0 Mobile Safari/537.36"), 5),
    (("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 "
     "Safari/537.36 OPR/115.0.0.0"), 4),
)
ROBOTS = (
    ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", 40),
    ("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", 25),
    ("Mozilla/5.0 (compatible; DuckDuckBot-Https/1.1; https://duckduckgo.com/duckduckbot)", 15),
    ("Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)", 12),
    ("UptimeRobot/2.0 (+http://www.uptimerobot.com/)", 8),
)
PAGES = (
    ("/", 18, 9_412), ("/blog/", 14, 7_208), ("/blog/2026/11/migration-tls.html", 9, 12_844),
    ("/blog/2026/10/sauvegardes.html", 6, 10_377), ("/boutique/", 12, 15_620), ("/boutique/panier.php", 4, 6_904),
    ("/boutique/commande.php", 2, 5_118), ("/docs/", 8, 6_330), ("/docs/installation.html", 7, 9_871),
    ("/docs/v2/", 3, 5_402), ("/docs/telechargements/", 3, 3_208), ("/docs/telechargements/exemple-1.4.tar.gz", 2,
                                                                        48_213),
    ("/assets/site.css", 10, 1_204), ("/blog/images/logo.svg", 6, 312), ("/boutique/static/boutique.css", 5, 980),
    ("/app/", 4, 22_014), ("/blog/feed.xml", 3, 2_960),
)
MISSING = ("/favicon.png", "/blog/2025/01/ancien-article.html", "/apple-touch-icon.png", "/docs/v1/",
           "/boutique/produit-42", "/sitemap.xml")
REFERERS = (("-", 45), ("https://www.google.com/", 20), ("https://duckduckgo.com/", 8),
            ("https://www.bing.com/", 5), ("https://exemple.org/", 14), ("https://forum.exemple.net/sujet/1287", 4),
            ("https://news.exemple.com/", 4))
API_CALLS = (("GET", "/api/v1/produits", 200, 3_412), ("GET", "/api/v1/produits/42", 200, 912),
             ("POST", "/api/v1/panier", 201, 288), ("GET", "/api/v1/stock?ref=A42", 200, 140),
             ("DELETE", "/api/v1/panier/7", 204, 0), ("GET", "/api/v1/sante", 200, 17))
# (méthode, cible, user-agent, règles [(id, pack, poids)], classe d'attaque)
ATTACKS = (
    ("GET", "/.env", "Mozilla/5.0 zgrab/0.x", [("SENS-001", "sensitive-paths", 6)], "scan"),
    ("GET", "/.git/config", "Go-http-client/1.1", [("SENS-002", "sensitive-paths", 6)], "scan"),
    ("GET", "/wp-login.php", "Mozilla/5.0 (Windows NT 6.1; rv:60.0) Gecko/20100101 Firefox/60.0",
     [("WP-001", "wordpress-probes", 3), ("CUSTOM-001", "custom", 3)], "scan"),
    ("POST", "/xmlrpc.php", "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1)",
     [("WP-002", "wordpress-probes", 4), ("WP-001", "wordpress-probes", 3)], "credential_stuffing"),
    ("GET", "/wp-config.php.bak", "curl/8.4.0", [("WP-003", "wordpress-probes", 6)], "scan"),
    ("GET", "/boutique/index.php?id=1%27%20OR%201=1--", "sqlmap/1.8.4#stable (https://sqlmap.org)",
     [("UA-001", "scanner-ua", 6), ("SQLI-005", "body-sqli", 5)], "sqli"),
    ("GET", "/api/v1/produits?ref=1%20UNION%20SELECT%20password%20FROM%20users", "python-requests/2.32.3",
     [("SQLI-001", "body-sqli", 6)], "sqli"),
    ("GET", "/docs/?q=%3Cscript%3Ealert(1)%3C/script%3E", "Mozilla/5.0 (X11; Linux x86_64)",
     [("XSS-001", "body-xss", 6)], "xss"),
    ("GET", "/cgi-bin/status?cmd=$(cat%20/etc/passwd)", "Mozilla/5.0 (compatible; Nmap Scripting Engine)",
     [("CMDI-001", "body-cmdi", 6), ("CMDI-004", "body-cmdi", 7)], "command_injection"),
    ("GET", "/", "Mozilla/5.00 (Nikto/2.5.0) (Evasions:None) (Test:Port Check)",
     [("UA-002", "scanner-ua", 6)], "scan"),
    ("GET", "/adminer.php", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", [("CUSTOM-003", "custom", 3),
                                                                           ("CUSTOM-002", "custom", 5)], "scan"),
)


def _weighted(choices: tuple[tuple[Any, int], ...]) -> Any:
    return RNG.choices([c[0] for c in choices], weights=[c[1] for c in choices])[0]


def _day_weight(moment: datetime) -> float:
    hour = moment.astimezone().hour
    return (0.15, 0.1, 0.08, 0.06, 0.06, 0.1, 0.25, 0.5, 0.8, 0.95, 1.0, 1.0, 0.9, 0.95, 1.0, 1.0, 0.95, 0.9, 0.95,
            1.0, 0.9, 0.7, 0.45, 0.25)[hour]


def _random_moment(start: datetime, end: datetime) -> datetime:
    span = (end - start).total_seconds()
    while True:
        moment = start + timedelta(seconds=RNG.random() * span)
        if RNG.random() < _day_weight(moment):
            return moment.replace(microsecond=RNG.randrange(1_000_000))


def _request_id() -> str:
    return f"{RNG.getrandbits(64):016x}"


class Hit:
    """Une requête du trafic simulé (et ce qu'elle a laissé dans les autres journaux)."""

    def __init__(self, at: datetime, ip: str, method: str, target: str, status: int, size: int,
                 referer: str | None, agent: str | None) -> None:
        self.at, self.ip, self.method, self.target = at, ip, method, target
        self.status, self.size, self.referer, self.agent = status, size, referer, agent
        self.request_id = _request_id()
        self.waf: tuple[str, list[tuple[str, str, int]], int] | None = None  # (étape, règles, score)
        self.attack_class = ""
        self.error = ""


def simulate_traffic(start: datetime, end: datetime, count: int) -> list[Hit]:
    hits: list[Hit] = []
    for _ in range(count):
        at = _random_moment(start, end)
        kind = RNG.random()
        if kind < 0.70:  # visiteurs
            ip = RNG.choice(VISITOR_IPS)
            agent = _weighted(BROWSERS)
            referer = _weighted(REFERERS)
            if RNG.random() < 0.06:
                hits.append(Hit(at, ip, "GET", RNG.choice(MISSING), 404, 1_142, referer, agent))
                continue
            path, _weight, size = RNG.choices(PAGES, weights=[p[1] for p in PAGES])[0]
            status = 304 if RNG.random() < 0.12 and not path.endswith(".php") else 200
            hits.append(Hit(at, ip, "GET", path, status, 0 if status == 304 else size, referer, agent))
        elif kind < 0.82:  # robots
            ip = RNG.choice(BOT_IPS)
            agent = _weighted(ROBOTS)
            path = RNG.choice(("/robots.txt", "/sitemap.xml", "/blog/feed.xml", "/", "/blog/", "/docs/"))
            status = 404 if path == "/sitemap.xml" else 200
            hits.append(Hit(at, ip, "GET", path, status, 1_142 if status == 404 else 2_400, "-", agent))
        elif kind < 0.93:  # API (reverse proxy /api/)
            ip = RNG.choice(VISITOR_IPS[:12])
            method, path, status, size = RNG.choice(API_CALLS)
            hit = Hit(at, ip, method, path, status, size, "https://exemple.org/boutique/",
                      _weighted(BROWSERS))
            hits.append(hit)
        else:  # hostiles
            ip = RNG.choice(HOSTILE_IPS)
            method, target, agent, rules, attack_class = RNG.choice(ATTACKS)
            hit = Hit(at, ip, method, target, 403, 1_142, "-", agent)
            score = sum(weight for _rule, _pack, weight in rules)
            hit.waf = ("inspection", rules, score)
            hit.attack_class = attack_class
            if score < 5:  # sous le seuil : journalisé seulement, la requête passe (404 du site)
                hit.status = 404
            hits.append(hit)
    # Épisodes particuliers, cohérents avec les alertes et les bans :
    # rafale limitée en débit (429) il y a 3 jours ;
    burst_start = NOW - timedelta(days=3, hours=5, minutes=12)
    for index in range(46):
        hit = Hit(burst_start + timedelta(seconds=index * 0.7), "198.51.100.23", "GET", "/api/v1/produits",
                  200 if index < 14 else 429, 3_412 if index < 14 else 221, "-", "python-requests/2.32.3")
        if index >= 14:
            hit.waf = ("rate_limit", [], 0)
        hits.append(hit)
    # sources bannies qui reviennent (451) ;
    for ip, days in (("203.0.113.66", 1.2), ("2001:db8:bad::17", 0.4), ("203.0.113.77", 2.1)):
        for index in range(RNG.randint(6, 12)):
            hit = Hit(NOW - timedelta(days=days, minutes=-index * 7), ip, "GET",
                      RNG.choice(("/.env", "/wp-login.php", "/", "/.git/HEAD")), 451, 1_388, "-",
                      "Mozilla/5.0 zgrab/0.x")
            hit.waf = ("blocklist", [], 0)
            hits.append(hit)
    # backends hors service (502 / 504), mêmes moments que les alertes « backend » de l'historique.
    for days_ago, status, count_ in ((21, 502, 9), (5, 504, 6), (0.2, 502, 2)):
        moment = NOW - timedelta(days=days_ago, hours=1)
        for index in range(count_):
            hit = Hit(moment + timedelta(seconds=index * 20), RNG.choice(VISITOR_IPS), "GET",
                      "/api/v1/produits" if status == 502 else "/app/", status, 559, "https://exemple.org/",
                      _weighted(BROWSERS))
            hit.error = ("proxy : backend 127.0.0.1:18102 injoignable (connexion refusée)" if status == 502
                         else "proxy : délai de lecture dépassé (60 s) vers 127.0.0.1:18103")
            hits.append(hit)
    # Trafic des 15 dernières minutes (l'écran État & Ressources relit ce quart d'heure à l'ouverture).
    for _ in range(75 if end >= NOW else 0):
        moment = NOW - timedelta(seconds=RNG.random() * 900)
        path, _weight, size = RNG.choices(PAGES, weights=[p[1] for p in PAGES])[0]
        status = RNG.choices((200, 304, 404, 502), weights=(86, 9, 4, 1))[0]
        hits.append(Hit(moment, RNG.choice(VISITOR_IPS), "GET", path, status, 0 if status == 304 else size,
                        _weighted(REFERERS), _weighted(BROWSERS)))
    hits = [hit for hit in hits if hit.at <= NOW]
    hits.sort(key=lambda hit: hit.at)
    return hits


def write_traffic_logs(root: Path, hits: list[Hit], waf_logging: Any, ad_logging: Any) -> None:
    import hashlib

    from omega_serv.domain.logging.access_log_format import (
        AccessLogEntry,
        format_combined_log_line,
        format_error_log_line,
    )
    from omega_serv.domain.logging.active_defense_enriched_log_format import (
        EnrichedLogEntry,
        format_enriched_log_line,
    )
    from omega_serv.domain.logging.waf_alert_format import WafAlertEntry, format_waf_alert_line
    from omega_serv.domain.security.waf.entities import Severity, WafDecision, WafFinding

    logs = root / "var" / "log"
    logs.mkdir(parents=True, exist_ok=True)
    access_lines, waf_lines, error_lines, enriched_lines = [], [], [], []
    for hit in hits:
        access_lines.append(format_combined_log_line(AccessLogEntry(
            hit.ip, hit.at, hit.method, hit.target, "HTTP/1.1", hit.status, hit.size,
            None if hit.referer in (None, "-") else hit.referer, hit.agent, hit.request_id)))
        if hit.waf is not None:
            stage, rules, score = hit.waf
            findings = tuple(WafFinding(rule_id, pack, rule_id, Severity.HIGH if weight >= 6 else Severity.MEDIUM,
                                        weight, "path") for rule_id, pack, weight in rules)
            if stage == "blocklist":
                decision = WafDecision("block", 451, 0, (), "warning", stage="blocklist")
            elif stage == "rate_limit":
                decision = WafDecision("block", 429, 0, (), "warning", throttle_only=True, stage="rate_limit")
            elif score >= 5:
                decision = WafDecision("block", 403, score, findings, "critical" if score >= 8 else "warning")
            else:
                decision = WafDecision("log", None, score, findings, "info")
            waf_lines.append(format_waf_alert_line(WafAlertEntry(
                hit.request_id, hit.at, hit.ip, hit.method, hit.target.split("?", 1)[0], hit.agent, decision,
                round(0.18 + RNG.random() * 0.6, 3)), waf_logging))
            if hit.attack_class:
                level = "hostile" if score >= 6 else "suspicious"
                subject = f"{hit.ip}:{hashlib.sha256((hit.agent or '').encode()).hexdigest()}"
                enriched_lines.append(format_enriched_log_line(EnrichedLogEntry(
                    hit.at, subject, hit.ip, hit.method, hit.target.split("?", 1)[0], hit.agent,
                    min(100, 40 + score * 5), level, hit.attack_class,
                    {"host": SERVER_NAME, "user-agent": hit.agent or "", "accept": "*/*"}), ad_logging))
        if hit.error:
            error_lines.append(format_error_log_line(hit.at, hit.error, hit.request_id))
    # Quelques erreurs de parsing (requêtes malformées des scanners), sans ligne d'accès complète.
    for _ in range(14):
        moment = _random_moment(NOW - timedelta(days=30), NOW)
        error_lines.append(format_error_log_line(moment, "erreur de parsing : ligne de requête invalide",
                                                 _request_id()))
    for _ in range(5):
        moment = _random_moment(NOW - timedelta(days=30), NOW)
        error_lines.append(format_error_log_line(moment, "Host invalide : '198.51.100.200:443'", _request_id()))
    error_lines.append(format_error_log_line(NOW - timedelta(days=12, hours=3),
                                             "arret force de 1 connexion(s) encore actives apres le delai de "
                                             "grace de 10s"))
    error_lines.sort(key=lambda line: line[1:20])
    (logs / "access.log").write_text("\n".join(access_lines) + "\n", encoding="utf-8")
    (logs / "waf-alerts.log").write_text("\n".join(waf_lines) + "\n", encoding="utf-8")
    (logs / "error.log").write_text("\n".join(error_lines) + "\n", encoding="utf-8")
    (logs / "active-defense-enriched.jsonl").write_text("\n".join(enriched_lines) + "\n", encoding="utf-8")
    for name in ("access.log", "waf-alerts.log", "error.log", "active-defense-enriched.jsonl"):
        (logs / name).chmod(0o664)


def write_traffic_stats(root: Path, hits: list[Hit]) -> None:
    """Statistiques du panneau (une par jour, date locale) recalculées par StatsDay.add depuis les mêmes lignes."""
    from omega_serv.domain.admin_web.traffic_stats import StatsDay
    from omega_serv.domain.logging.access_log_format import AccessLogEntry, format_combined_log_line
    from omega_serv.infrastructure.admin_web.stats_store import StatsStore
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

    days: dict[str, StatsDay] = {}
    for hit in hits:
        local = hit.at.astimezone()
        day = local.strftime("%Y-%m-%d")
        line = format_combined_log_line(AccessLogEntry(
            hit.ip, hit.at, hit.method, hit.target, "HTTP/1.1", hit.status, hit.size,
            None if hit.referer in (None, "-") else hit.referer, hit.agent, hit.request_id))
        days.setdefault(day, StatsDay(day)).add(line.encode("utf-8"), local.hour)
    store = StatsStore(LocalFilesystem(), root)
    for day, stats in sorted(days.items())[-31:]:
        store.save(day, stats.to_dict())


def write_other_logs(root: Path) -> None:
    """admin-audit.log, uploads.log, breakage.log (vide : aucun écrivain dans l'application)."""
    from omega_serv.domain.logging.upload_log_format import format_upload_log_line
    from omega_serv.domain.upload.entities import UploadResult

    logs = root / "var" / "log"
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    audit: list[tuple[datetime, str]] = [
        (NOW - timedelta(days=12, hours=5), ("maitre accepte (code) nom='console@poste-admin' "
                                            "id=5e0d1c2b3a4f5e6d7c8b9a0f1e2d3c4b droits=administration")),
        (NOW - timedelta(days=12, hours=5, minutes=4), "fenetre d'appairage ouverte droits=administration (10 min)"),
    ]
    for days_ago in range(29, -1, -1):
        base = NOW - timedelta(days=days_ago)
        if days_ago % 2 == 0:
            moment = base.replace(hour=8, minute=RNG.randint(2, 50))
            audit.append((moment, "connexion compte=alice role=administration mode=tableau ip=192.0.2.10"))
            if RNG.random() < 0.5:
                audit.append((moment + timedelta(minutes=3), "mode administration compte=alice ip=192.0.2.10"))
            audit.append((moment + timedelta(minutes=RNG.randint(20, 90)), "deconnexion compte=alice ip=192.0.2.10"))
        if days_ago % 3 == 1:
            moment = base.replace(hour=14, minute=RNG.randint(0, 59))
            audit.append((moment, "connexion compte=bruno role=lecture mode=tableau ip=2001:db8:1::25"))
    for days_ago, ip in ((17, "203.0.113.150"), (17, "203.0.113.150"), (17, "203.0.113.150"), (8, "198.51.100.41")):
        moment = NOW - timedelta(days=days_ago, hours=RNG.randint(0, 3), minutes=RNG.randint(0, 59))
        audit.append((moment, f"echec de connexion compte='admin' ip={ip}"))
    audit.append((NOW - timedelta(days=17, hours=4), ("connexion refusee (attente 60 s) compte='admin' "
                                                     "ip=203.0.113.150")))
    audit.append((NOW - timedelta(days=6, hours=2), "code de secours utilise compte=alice"))
    audit.append((NOW - timedelta(days=4, hours=7), ("session fermee par TUI compte=bruno session=6b1f0e9a2c44 "
                                                    "ip=local")))
    audit.append((NOW - timedelta(minutes=42), ("connexion compte=alice role=administration mode=tableau "
                                               "ip=192.0.2.10")))
    audit.append((NOW - timedelta(minutes=40), "mode administration compte=alice ip=192.0.2.10"))
    audit.append((NOW - timedelta(minutes=125), ("connexion compte=bruno role=lecture mode=tableau "
                                                "ip=2001:db8:1::25")))
    audit.sort()
    (logs / "admin-audit.log").write_text("".join(f"{at.strftime(stamp)} {text}\n" for at, text in audit),
                                          encoding="utf-8")
    uploads = []
    for days_ago, accepted, name, size, reason in (
            (19, True, "facture-2026-10.pdf", 81_920, None), (11, True, "photo-vitrine.jpg", 245_760, None),
            (9, False, "shell.php", 3_201, ("extension non autorisée : '.php' (attendu : ['.pdf', '.png', '.jpg', "
                                           "'.zip'])")),
            (3, False, "catalogue-complet.zip", 12_582_912, "fichier trop volumineux (12582912 > 8388608)")):
        stored = f"{RNG.getrandbits(128):032x}{Path(name).suffix}" if accepted else None
        uploads.append(format_upload_log_line(UploadResult(
            accepted, "/depot/", "192.0.2.10" if accepted else "203.0.113.9", name, stored,
            f"var/uploads/depot/{stored}" if stored else None, size, reason,
            NOW - timedelta(days=days_ago, hours=2))))
    (logs / "uploads.log").write_text("\n".join(uploads) + "\n", encoding="utf-8")
    (logs / "breakage.log").write_text("", encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------------------
# Active Defense (menaces + incidents), RIPOSTE (sources, actions, décisions), liste de blocage WAF

_IDS = random.Random(7)
INCIDENT_IDS = [str(__import__("uuid").UUID(int=_IDS.getrandbits(128), version=4)) for _ in range(9)]
ACTION_IDS = [f"{_IDS.getrandbits(48):012x}" for _ in range(10)]


class FixedClock:
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment


def _subject(ip: str, agent: str) -> str:
    import hashlib

    return f"{ip}:{hashlib.sha256(agent.encode()).hexdigest()}"


# (ip, user-agent, score, niveau, jours depuis la dernière activité, classe, incident ouvert ?)
THREATS = (
    ("203.0.113.66", "Mozilla/5.0 zgrab/0.x", 92, "contained", 0.05, "scan", True),
    ("2001:db8:bad::17", "Mozilla/5.0 zgrab/0.x", 84, "contained", 0.3, "scan", True),
    ("198.51.100.23", "python-requests/2.32.3", 71, "hostile", 3.2, "sqli", False),
    ("203.0.113.77", "sqlmap/1.8.4#stable (https://sqlmap.org)", 66, "hostile", 2.0, "sqli", False),
    ("198.51.100.200", "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1)", 48, "suspicious", 0.8,
     "credential_stuffing", False),
    ("203.0.113.150", "Mozilla/5.0 (compatible; Nmap Scripting Engine)", 38, "suspicious", 6.0,
     "command_injection", False),
    ("198.51.100.41", "Mozilla/5.0 (X11; Linux x86_64)", 34, "suspicious", 9.0, "xss", False),
    ("203.0.113.9", "curl/8.4.0", 12, "normal", 14.0, "scan", False),
)


def make_active_defense(root: Path) -> None:
    from omega_serv.domain.security.active_defense.entities import (
        IncidentEvent,
        ThreatObservation,
        ThreatState,
    )
    from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
        open_active_defense_connection,
    )
    from omega_serv.infrastructure.persistence.sqlite_incident_repository import (
        SqliteIncidentRepository,
    )
    from omega_serv.infrastructure.persistence.sqlite_threat_state_repository import (
        SqliteThreatStateRepository,
    )

    connection = open_active_defense_connection(root / "var" / "lib" / "active-defense.sqlite3")
    try:
        threats = SqliteThreatStateRepository(connection)
        incidents = SqliteIncidentRepository(connection)
        for ip, agent, score, level, days, _attack, open_incident in THREATS:
            updated = NOW - timedelta(days=days)
            # Sources avec un incident ouvert : état prolongé (sinon le balayage fermerait l'incident).
            expires = NOW + timedelta(hours=6) if open_incident else updated + timedelta(seconds=7200)
            actions = ("enrich_log", "delay", "create_incident") if level in ("hostile", "contained") else (
                ("enrich_log",) if level == "suspicious" else ())
            threats.save(ThreatState(_subject(ip, agent), score, level, updated, expires, actions))
        # 9 incidents : 2 ouverts (sources contenues), 7 fermés sur le mois.
        closed_specs = (("198.51.100.23", "python-requests/2.32.3", 3.3, 0.6, "sqli"),
                        ("203.0.113.77", "sqlmap/1.8.4#stable (https://sqlmap.org)", 2.1, 0.4, "sqli"),
                        ("203.0.113.150", "Mozilla/5.0 (compatible; Nmap Scripting Engine)", 6.1, 1.0,
                         "command_injection"),
                        ("198.51.100.41", "Mozilla/5.0 (X11; Linux x86_64)", 9.2, 0.3, "xss"),
                        ("203.0.113.66", "Mozilla/5.0 zgrab/0.x", 13.0, 2.0, "scan"),
                        ("198.51.100.200", "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1)", 18.4, 0.8,
                         "credential_stuffing"),
                        ("203.0.113.9", "curl/8.4.0", 26.0, 1.5, "scan"))
        specs = [(ip, agent, days, None, attack) for ip, agent, _s, _l, days, attack, is_open in THREATS if is_open]
        specs += [(ip, agent, days, duration, attack) for ip, agent, days, duration, attack in closed_specs]
        for incident_id, (ip, agent, days, duration_days, attack) in zip(INCIDENT_IDS, specs, strict=True):
            subject = _subject(ip, agent)
            opened = NOW - timedelta(days=days + 0.2)
            incidents.create(incident_id, subject, opened)
            moment = opened - timedelta(minutes=25)
            for step in range(RNG.randint(3, 6)):
                moment += timedelta(minutes=RNG.randint(2, 9))
                rules = {"scan": "SENS-001", "sqli": "SQLI-001", "xss": "XSS-001",
                         "command_injection": "CMDI-004", "credential_stuffing": "WP-002"}[attack]
                incidents.add_observation(incident_id, ThreatObservation(
                    subject, moment, "waf_decision", attack, 10, f"WAF block (score=6, regles={rules})"))
                incidents.add_event(incident_id, IncidentEvent(moment, "waf_decision",
                                                               f"WAF block (score=6, regles={rules})"))
                if step == 1:
                    incidents.add_event(incident_id, IncidentEvent(moment, "threat_escalated",
                                                                   "suspicious -> hostile (score 64)"))
            incidents.add_event(incident_id, IncidentEvent(opened, "incident_opened", "score 72 >= seuil 70"))
            if duration_days is not None:
                closed = opened + timedelta(days=duration_days)
                incidents.add_event(incident_id, IncidentEvent(closed, "incident_closed",
                                                               "source revenue au niveau normal"))
                incidents.close(incident_id, closed)
    finally:
        connection.close()


def make_riposte(root: Path) -> list[Any]:
    """Base RIPOSTE ; rend les actions en cours (leurs bans vont aussi dans la liste de blocage)."""
    from omega_serv.domain.security.riposte.actions import Exemption, RiposteAction
    from omega_serv.domain.security.riposte.decide import Decision, Reason
    from omega_serv.domain.security.riposte.history import Episode, PastAction, SourceHistory
    from omega_serv.infrastructure.persistence.sqlite_riposte_connection import (
        open_riposte_connection,
    )
    from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore

    connection = open_riposte_connection(root / "var" / "lib" / "riposte.sqlite3")
    store = SqliteRiposteStore(connection)
    tiers = (3600, 21600, 86400, 604800)
    # (ip, politique, palier, jours depuis la décision, état, fini par)
    plan = (
        ("203.0.113.66", "scan-recidive", 3, 0.05, "applied", ""),
        ("2001:db8:bad::17", "scan-recidive", 2, 0.3, "applied", ""),
        ("203.0.113.77", "injections-repetees", 2, 0.2, "applied", ""),
        ("198.51.100.23", "injections-repetees", 1, 3.2, "expired", "expiry"),
        ("203.0.113.66", "scan-recidive", 2, 4.5, "expired", "expiry"),
        ("203.0.113.66", "scan-recidive", 1, 12.0, "expired", "expiry"),
        ("198.51.100.200", "force-brute", 0, 0.8, "revoked", "user"),
        ("203.0.113.150", "injections-repetees", 0, 6.1, "expired", "expiry"),
        ("2001:db8:bad::17", "scan-recidive", 0, 8.0, "expired", "expiry"),
        ("198.51.100.41", "injections-repetees", 0, 9.2, "expired", "expiry"),
    )
    in_progress = []
    histories: dict[str, SourceHistory] = {}
    agents = {ip: agent for ip, agent, *_rest in THREATS}
    classes = {"scan-recidive": ("scan",), "injections-repetees": ("sqli", "xss"), "force-brute":
               ("credential_stuffing",)}
    for action_id, (ip, policy, tier, days, state, finished_by) in zip(ACTION_IDS, plan, strict=True):
        created = NOW - timedelta(days=days)
        ends = created + timedelta(seconds=tiers[tier])
        finished = None
        if state == "expired":
            finished = ends
        elif state == "revoked":
            finished = created + timedelta(minutes=35)
        kind = "local_and_network_ban" if tier >= 2 else "local_ban"
        action = RiposteAction(action_id, ip, kind, policy, created, ends, state, tier, None,
                               (_subject(ip, agents[ip]),), "", finished, finished_by, True,
                               f"{RNG.getrandbits(128):032x}")
        store.save_action(action)
        if state == "applied":
            in_progress.append(action)
        event_id = action.event_id
        store.append_decision(Decision("matched", ip, event_id, created, policy, kind, tier, tiers[tier], None, (
            Reason("event", (("ip", ip), ("kind", "waf_alert"))),
            Reason("exemptions_checked", (("count", 2),)),
            Reason("policy_matched", (("policy", policy),)),
            Reason("tier", (("index", tier + 1), ("of", len(tiers)))),
        )), True)
        history = histories.get(ip, SourceHistory(ip, (), (), (_subject(ip, agents[ip]),)))
        episode = Episode(created - timedelta(minutes=40), created, RNG.randint(4, 30), classes[policy],
                          "hostile" if tier < 2 else "contained", 0, RNG.randint(0, 9), True)
        histories[ip] = SourceHistory(ip, (*history.episodes, episode),
                                      (*history.actions, PastAction(created, ends, policy, tier, True, action_id)),
                                      history.subject_ids)
    # Décisions sans action : réseau exempté, aucune politique.
    for days, ip, status, reasons in (
            (1.4, "192.0.2.5", "rejected_by_safety", (Reason("exempt_network", (("network", "192.0.2.0/28"),)),)),
            (2.6, "198.51.100.150", "observed", (Reason("no_policy_matched", (("policies", 3),)),)),
            (5.1, "203.0.113.9", "observed", (Reason("already_acted_this_episode"),))):
        store.append_decision(Decision(status, ip, f"{RNG.getrandbits(128):032x}", NOW - timedelta(days=days),
                                       reasons=reasons), False)
    for ip, history in histories.items():
        ordered = SourceHistory(ip, tuple(sorted(history.episodes, key=lambda e: e.started_at)),
                                tuple(sorted(history.actions, key=lambda a: a.taken_at)), history.subject_ids)
        store.save_source(ordered, max(e.last_seen_at for e in ordered.episodes))
    store.add_exemption(Exemption("198.51.100.150/32", NOW - timedelta(days=2), NOW + timedelta(days=5)))
    store.set_state("started_at", (NOW - timedelta(days=4, hours=6)).isoformat())
    store.set_state("heartbeat_at", (NOW - timedelta(minutes=20)).isoformat())
    store.set_state("emergency_stop", "0")
    store.set_state("stats", json.dumps({
        "duplicates": 12, "historical": 0, "lines_read": 4_812, "new_events": 1_204, "rejected": {},
        "last_event_at": {"waf-alerts": (NOW - timedelta(minutes=21)).isoformat(),
                          "security-events": (NOW - timedelta(hours=2)).isoformat()}}))
    for days, kind, detail in ((4.25, "start", "RIPOSTE démarré"), (0.05, "action", "ban local 203.0.113.66 #4")):
        store.append_audit(NOW - timedelta(days=days), kind, detail)
    store.close()
    return in_progress


def make_blocklist(root: Path, riposte_actions: list[Any]) -> None:
    from omega_serv.domain.security.riposte.actions import blocklist_reason
    from omega_serv.domain.security.waf.entities import BlocklistEntry
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
    from omega_serv.infrastructure.waf.blocklist_store import JsonBlocklistStore

    (root / "var" / "lib" / "waf").mkdir(parents=True, exist_ok=True)
    store = JsonBlocklistStore(LocalFilesystem(), root / "var" / "lib" / "waf" / "blocklist.json", FixedClock(NOW))

    def network(ip: str) -> str:
        return f"{ip}/128" if ":" in ip else f"{ip}/32"

    entries = [
        BlocklistEntry(network(action.ip), blocklist_reason(action), action.created_at.isoformat(),
                       action.ends_at.isoformat(), "riposte") for action in riposte_actions
    ]
    entries += [
        BlocklistEntry("198.51.100.200/32", "5 détections suspectes dans la fenêtre (seuil 3)",
                       (NOW - timedelta(minutes=38)).isoformat(), (NOW + timedelta(minutes=22)).isoformat(), "auto"),
        BlocklistEntry("203.0.113.9/32", "4 détections suspectes dans la fenêtre (seuil 3)",
                       (NOW - timedelta(days=2, hours=3)).isoformat(), (NOW - timedelta(days=2, hours=2)).isoformat(),
                       "auto"),
        BlocklistEntry("198.51.100.0/27", "Plage d'un hébergeur à l'origine de scans répétés",
                       (NOW - timedelta(days=20)).isoformat(), None, "manual", "intervention"),
        BlocklistEntry("203.0.113.150/32", "Tentatives répétées sur /gestion/ (vu dans l'audit)",
                       (NOW - timedelta(days=17)).isoformat(), (NOW + timedelta(days=13)).isoformat(), "manual",
                       "intervention"),
        BlocklistEntry("2001:db8:dead::/48", "omega-jail : omega-serv-404 (recidive)",
                       (NOW - timedelta(days=1, hours=4)).isoformat(), (NOW + timedelta(days=6)).isoformat(),
                       "manual"),
        BlocklistEntry("198.51.100.41/32", "Robot d'indexation agressif",
                       (NOW - timedelta(days=9)).isoformat(), (NOW - timedelta(days=8)).isoformat(), "manual"),
    ]
    for entry in entries:
        store.add_entry(entry)


# ---------------------------------------------------------------------------------------------------------------------
# Sauvegardes (service de l'application, horloge antidatée), archives de journaux, bibliothèque des journaux


def make_backups(root: Path) -> None:
    from omega_serv.application.config.load_config import load_config
    from omega_serv.application.persistence.create_backup import create_backup
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.persistence.backup import BackupRequest

    container = DependencyContainer(project_root=root)
    config = load_config(container.configuration, container.config_file).config
    assert config is not None
    backups_dir = root / "var" / "backups" / "config-snapshots"
    archive_store = container.build_archive_store(backups_dir)
    metadata_store = container.build_backup_metadata_store(backups_dir)
    manifest = container._backup_manifest(config)
    for days, request in (
            (24, BackupRequest(include_waf_rules=True, description="Avant activation du reverse proxy")),
            (11, BackupRequest(include_waf_rules=True, include_auth_zones=True, include_certificates=True,
                               description="Avant migration TLS direct")),
            (4, BackupRequest.everything("Sauvegarde complète hebdomadaire")),
            (0.3, BackupRequest(include_waf_rules=True, include_active_defense=True, include_riposte=True,
                                description="Avant mise à jour 3.0.0"))):
        moment = (NOW - timedelta(days=days)).replace(hour=RNG.randint(7, 22), minute=RNG.randint(0, 59))
        moment = min(moment, NOW - timedelta(minutes=30))
        result = create_backup(request, config, root, container.config_file, archive_store, metadata_store,
                               FixedClock(moment), manifest=manifest, exports_dir=root / "var" / "exports")
        assert result.success, result.message
    for path in backups_dir.iterdir():  # dates des fichiers alignées sur leur sauvegarde
        stamp = path.name.split("_")[1:3]
        if len(stamp) == 2 and stamp[0].isdigit():
            moment = datetime.strptime("_".join(stamp)[:15], "%Y%m%d_%H%M%S").replace(tzinfo=UTC).timestamp()
            os.utime(path, (moment, moment))


def make_log_archives(root: Path, hits_before: list[Hit]) -> None:
    """Deux archives de rotation : access.log et error.log plus anciens que les 30 jours du journal courant."""
    import tempfile

    from omega_serv.domain.logging.access_log_format import (
        AccessLogEntry,
        format_combined_log_line,
        format_error_log_line,
    )
    from omega_serv.domain.logs.rotation import generate_archive_name
    from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore

    archives = root / "var" / "backups" / "logs"
    archives.mkdir(parents=True, exist_ok=True)
    store = ArchiveStore(archives)
    rotated_at = NOW - timedelta(days=30, minutes=5)
    with tempfile.TemporaryDirectory() as work:
        access = Path(work) / "access.log"
        access.write_text("".join(format_combined_log_line(AccessLogEntry(
            hit.ip, hit.at, hit.method, hit.target, "HTTP/1.1", hit.status, hit.size,
            None if hit.referer in (None, "-") else hit.referer, hit.agent, hit.request_id)) + "\n"
                                  for hit in hits_before), encoding="utf-8")
        error = Path(work) / "error.log"
        error.write_text("".join(format_error_log_line(hit.at, "erreur de parsing : ligne de requête invalide",
                                                       hit.request_id) + "\n" for hit in hits_before[::40]),
                         encoding="utf-8")
        for source in (access, error):
            name = generate_archive_name(source, rotated_at)
            path = store.create_archive(name, [source])
            os.utime(path, (rotated_at.timestamp(), rotated_at.timestamp()))


def make_log_library(root: Path) -> None:
    from omega_serv.domain.logs.favorite import Favorite
    from omega_serv.domain.logs.library import LibraryRecord
    from omega_serv.domain.logs.viewer_type import ViewerType
    from omega_serv.infrastructure.logging.json_log_favorite_repository import (
        JsonLogFavoriteRepository,
    )
    from omega_serv.infrastructure.logging.json_log_library_repository import (
        JsonLogLibraryRepository,
    )

    logs = root / "var" / "log"
    library = JsonLogLibraryRepository(root / "var" / "library.json")
    for name in ("access.log", "error.log", "waf-alerts.log", "active-defense-enriched.jsonl", "admin-audit.log",
                 "alertes.log", "uploads.log"):
        library.add(LibraryRecord(str((logs / name).resolve()), "file", SERVICE_NAME))
    favorites = JsonLogFavoriteRepository(root / "var" / "favorites.json")
    favorites.add(Favorite("Accès du site", (str((logs / "access.log").resolve()),), ViewerType.SIMPLE))
    favorites.add(Favorite("Sécurité (WAF + Active Defense)", (str((logs / "waf-alerts.log").resolve()),
                                                              str((logs / "active-defense-enriched.jsonl").resolve())),
                           ViewerType.LNAV))
    favorites.add(Favorite("Erreurs", (str((logs / "error.log").resolve()),), ViewerType.CLASSIC))


# ---------------------------------------------------------------------------------------------------------------------
# Masque d'affichage : nom de machine et adresses réseau fictifs (captures sans aucune donnée de la vraie machine)

SITECUSTOMIZE = '''"""Masque de la démo omega-serv (généré par tools/captures/demo_instance.py), chargé automatiquement par Python
quand <dest>/masque est dans PYTHONPATH. Ne change que ce que les écrans AFFICHENT de la machine : son nom
(socket.gethostname) et les adresses de ses interfaces (psutil.net_if_addrs), remplacés par des valeurs de
documentation. Désactivable avec OMEGA_DEMO_MASQUE=0."""
import os
import socket

if os.environ.get("OMEGA_DEMO_MASQUE", "1") != "0":
    socket.gethostname = lambda: "srv-exemple"
    try:
        import psutil
    except ImportError:  # pragma: no cover
        psutil = None
    if psutil is not None:
        _real_net_if_addrs = psutil.net_if_addrs

        def _demo_net_if_addrs():
            counters = {"v4": 0, "v6": 0, "mac": 0}
            result = {}
            for name, entries in _real_net_if_addrs().items():
                kept = []
                for entry in entries:
                    address = entry.address.split("%", 1)[0]
                    if entry.family == socket.AF_INET and not address.startswith("127."):
                        counters["v4"] += 1
                        entry = entry._replace(address=f"192.0.2.{counters['v4']}", broadcast=None)
                    elif entry.family == socket.AF_INET6 and address != "::1":
                        if address.lower().startswith("fe80"):
                            continue
                        counters["v6"] += 1
                        entry = entry._replace(address=f"2001:db8::{counters['v6']}")
                    elif entry.family not in (socket.AF_INET, socket.AF_INET6) and name != "lo":
                        counters["mac"] += 1
                        entry = entry._replace(address=f"02:00:00:00:00:{counters['mac']:02x}", broadcast=None)
                    kept.append(entry)
                result[name] = kept
            return result

        psutil.net_if_addrs = _demo_net_if_addrs
        _real_users = psutil.users
        psutil.users = lambda: [u._replace(name="demo", host="") for u in _real_users()]

    # Cadre RÉSEAU (TUI et tableau de bord web) : adresse sortante, passerelle et DNS lus directement par
    # infrastructure/probe/system_stats.py ; remplacés dès que ce module est importé.
    import importlib.abc
    import importlib.util
    import sys
    from pathlib import Path

    _PROBE = "omega_serv.infrastructure.probe.system_stats"

    class _DemoProbeFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name != _PROBE:
                return None
            sys.meta_path.remove(self)
            try:
                spec = importlib.util.find_spec(name)
            finally:
                sys.meta_path.insert(0, self)
            if spec is None or spec.loader is None:
                return spec
            real_exec = spec.loader.exec_module

            def exec_module(module):
                real_exec(module)
                module._detect_outbound_ip = lambda: "192.0.2.1"
                module._detect_default_gateway = lambda: "192.0.2.254"
                module._RESOLV_CONF = Path(__file__).with_name("resolv.conf")

            spec.loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, _DemoProbeFinder())
'''


def make_mask(dest: Path) -> None:
    (dest / "masque").mkdir()
    (dest / "masque" / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    (dest / "masque" / "resolv.conf").write_text("nameserver 192.0.2.53\nnameserver 2001:db8::53\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------------------
# Point d'entrée du processus relancé


def populate(dest: Path, real_project_root: Path, admin_bind: str = "127.0.0.1",
             tls_mode: str = "direct") -> None:
    root = dest / "omega-serv"
    assert Path(os.environ["HOME"]).resolve() == (dest / "home").resolve(), "HOME factice attendu"
    assert real_project_root.resolve() != root.resolve()
    native_available = (root / "bin" / "omega-http-core").is_file()
    print("Certificats, sites, comptes du site ...")
    make_certificates(root)
    make_webroot(root)
    make_site_auth(root)
    make_settings(root)
    print("Configuration ...")
    config = build_config(root, native_available)
    config["options"]["admin_web"]["bind"] = admin_bind
    config["tls"]["mode"] = tls_mode
    if tls_mode != "direct":
        config["security"]["hsts_enabled"] = False
    _write_json(root / "config" / "omega-serve.json", config)
    errors = check_config(root)
    if errors:
        raise SystemExit("Configuration de démonstration refusée :\n  " + "\n  ".join(errors))
    print("  configuration valide (chargeur + validation d'environnement de l'application).")
    print("Multi-instance, zone omega-connect, masque ...")
    make_instances(dest, root)
    make_synchro_zone(dest, root)
    make_mask(dest)
    print("Trafic sur 30 jours ...")
    hits = simulate_traffic(NOW - timedelta(days=30), NOW, 6200)
    older = simulate_traffic(NOW - timedelta(days=38), NOW - timedelta(days=30, minutes=10), 1300)
    older = [hit for hit in older if hit.at < NOW - timedelta(days=30, minutes=10)]
    from omega_serv.domain.security.active_defense.config import ActiveDefenseLoggingConfig
    from omega_serv.domain.security.waf.config import WafLoggingConfig

    write_traffic_logs(root, hits, WafLoggingConfig(), ActiveDefenseLoggingConfig(enhanced_capture=True))
    write_traffic_stats(root, hits)
    write_other_logs(root)
    print(f"  {len(hits)} requêtes ({sum(1 for h in hits if h.waf)} alertes WAF).")
    print("Active Defense, RIPOSTE, liste de blocage ...")
    make_active_defense(root)
    actions = make_riposte(root)
    make_blocklist(root, actions)
    print("Administration web ...")
    make_admin_accounts(root)
    make_admin_alerts(root)
    make_admin_sessions(root)
    make_admin_history(root)
    make_admin_state(root, admin_bind)
    make_admin_master_and_fleet(root)
    make_log_library(root)
    print("Sauvegardes ...")
    make_log_archives(root, older)
    make_backups(root)

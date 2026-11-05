#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Banc differentiel des moteurs HTTP (plan moteur C++, lot 1, 2026-11-02) - outil de developpement.

Rejoue un corpus de requetes BRUTES contre un serveur et enregistre, pour chaque requete :
  - les octets de la reponse (en-tete `Date` retire, tout le reste tel quel) ;
  - la ou les lignes ajoutees au journal d'acces (horodatage et identifiant de requete neutralises) ;
  - la ou les alertes WAF ajoutees (horodatage, identifiant et duree neutralises).
Deux executions (moteur Python, moteur natif) doivent donner EXACTEMENT le meme fichier : meme octets, meme
ligne de journal (lue par les failregex d'omega-jail, lnav, le parseur), meme decision de securite.

  python3 tools/differential/differential.py prepare DOSSIER [--profile full|static]
  python3 tools/differential/differential.py run DOSSIER --out python.json [--engine python|native]
  python3 tools/differential/differential.py compare python.json native.json

Profil `static` (lot 2 du moteur natif) : meme projet, sans WAF, auth, upload ni listing - ce que le natif sait
deja servir seul. Profil `static-tls` (lot 3b) : le meme en TLS direct (certificat auto-signe genere ici), le
corpus passe par un client TLS, plus des cas propres a TLS (HTTP en clair sur le port TLS, versions, suites). Moteur `native` : instantane construit par infrastructure/server/native_snapshot.py dans le
projet de test, puis binaire omega-http-core (par defaut la version ASan/UBSan du depot).

`prepare` cree un projet de test FIGE (dates des fichiers fixes, ETag/Last-Modified stables), avec une copie
de src/ (le serveur ecrit dans le var/ du projet dont il est lance, jamais dans le vrai depot).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PORT = 18970
FIXED_MTIME = 1_700_000_000
HOST = f"127.0.0.1:{PORT}"
# Client simule derriere le proxy de confiance (127.0.0.1) : chaque cas a sa propre adresse, aucun etat
# (compteurs, reputation) ne passe d'un cas a l'autre.
BANNED_IP = "203.0.113.66"
USER, PASSWORD = "bob", "secret-de-test"


# --------------------------------------------------------------------------------------------- projet de test
def prepare(folder: Path, profile: str = "full") -> None:
    folder = folder.resolve()
    if folder.exists():
        shutil.rmtree(folder)
    (folder / "config").mkdir(parents=True)
    shutil.copytree(REPO / "src", folder / "src", ignore=shutil.ignore_patterns("__pycache__", "*.bak"))
    rules = folder / "secure" / "waf" / "rules"
    rules.mkdir(parents=True)
    for pack in sorted((REPO / "secure" / "waf" / "rules").glob("*.json")):
        if pack.name != "custom.json":
            shutil.copy(pack, rules / pack.name)

    web = folder / "webroot"
    files = {
        "index.html": b"<!doctype html><title>accueil</title>\n",
        "page.html": b"<html><body>" + b"p" * 900 + b"</body></html>\n",
        "style.css": b"body{color:#123}\n" * 40,
        "img.png": bytes(range(256)) * 8,
        "docs/a.txt": b"fichier a\n",
        "docs/b.txt": b"fichier b plus long\n" * 3,
        "private/secret.txt": b"jamais servi\n",
        "admin/index.html": b"<p>zone protegee</p>\n",
        "big.bin": bytes(range(256)) * 400,
        "huge.bin": bytes(range(256)) * 1200,  # > 256 Kio : envoye par sendfile
        "café.txt": "fichier au nom accentué\n".encode(),
        ".assets/app.css": b"a{color:blue}\n",
        ".errors/404.html": b"<!doctype html><style>body{color:red}</style><STYLE type=x>p{}</style ><p>introuvable</p>\n",
        ".errors/403.html": b"<!doctype html><p>interdit</p>\n",
    }
    for name, content in files.items():
        path = web / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    import gzip

    (web / "style.css.gz").write_bytes(gzip.compress(files["style.css"], mtime=0))
    (web / "lien-docs").symlink_to("docs")                  # lien interne : servi
    (web / "lien-sortie").symlink_to("../config")           # lien qui sort du webroot : 403
    (web / "docs" / "lien-boucle").symlink_to("lien-boucle")  # boucle de liens
    for path in web.rglob("*"):
        stamp = FIXED_MTIME + (10 if path.suffix == ".gz" else 0)
        os.utime(path, (stamp, stamp), follow_symlinks=False)

    auth = folder / "secure" / "auth"
    auth.mkdir(parents=True)
    sys.path.insert(0, str(folder / "src"))
    from omega_serv.domain.security.auth.password_hashing import hash_password

    (auth / "users.json").write_text(json.dumps(
        {"version": 1, "users": [{"username": USER, "password_hash": hash_password(PASSWORD)}]}))
    (auth / "zones.json").write_text(json.dumps(
        {"version": 1, "zones": [{"path_prefix": "/admin", "realm": "Admin", "allowed_users": [USER]}]}))

    waf_state = folder / "var" / "lib" / "waf"
    waf_state.mkdir(parents=True)
    (waf_state / "blocklist.json").write_text(json.dumps({"version": 1, "entries": [{
        "network": f"{BANNED_IP}/32", "reason": "banc differentiel", "created_at": "2026-11-02T00:00:00+00:00",
        "expires_at": None, "source": "manual"}]}))

    config = {
        "version": 1, "profile": "standard",
        # delais courts : les cas « lent » restent rapides a rejouer
        "server": {"bind": "127.0.0.1", "port": PORT, "workers": 1, "read_timeout_seconds": 2,
                   "keepalive_timeout_seconds": 1},
        "security": {"allowed_methods": ["GET", "HEAD", "POST"],
                     "csp_zones": [{"path_prefix": "/docs", "policy": "default-src 'self'; style-src 'self' 'unsafe-inline'"}]},
        "options": {
            "waf": {"enabled": True, "mode": "block",
                    "rules": {"paths": [f"secure/waf/rules/{p.name}" for p in sorted(rules.glob("*.json"))]},
                    "rate_limit": {"enabled": False}},
            "trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1", "::1"],
                              "header_preference": ["X-Forwarded-For"]},
            "redirects": {"enabled": True, "list": [{"url_prefix": "/old", "destination": "/page.html", "status_code": 301},
                                                    {"url_prefix": "/vieux/", "destination": "/page.html", "status_code": 308}]},
            "rewrites": {"enabled": True, "list": [{"match_prefix": "/rw", "replacement_prefix": "/docs"},
                                                   {"match_prefix": "/loop-a", "replacement_prefix": "/loop-b"},
                                                   {"match_prefix": "/loop-b", "replacement_prefix": "/loop-a"}]},
            "aliases": {"enabled": True, "list": [{"url_prefix": "/al", "target_path": "webroot/docs"}]},
            "access_control": {"enabled": True, "list": [{"path_prefix": "/private", "verdict": "deny"},
                                                         {"path_prefix": "/.assets", "verdict": "allow"}]},
            "error_pages": {"enabled": True, "custom_dir": "webroot/.errors"},
            "cache": {"enabled": True},
            "dirlisting": {"enabled": True, "zone_prefixes": ["/docs"]},
            "auth": {"enabled": True},
            # zone d'upload : autorise le POST sur /upload, pour exercer les vrais controles du corps
            # (Transfer-Encoding, Content-Length, limite de taille) au lieu d'un 405 qui les masque
            "upload": {"enabled": True, "zones": [{"url_prefix": "/upload", "storage_path": "var/uploads"}]},
        },
    }
    if profile in ("static", "static-tls"):
        for name in ("waf", "auth", "upload", "dirlisting"):
            del config["options"][name]
    if profile == "secure":  # lots 4-5 : WAF, Auth, blocklist, listing (route deleguee) ; sans upload (lot 6)
        del config["options"]["upload"]
        config["options"]["waf"]["rate_limit"] = {"enabled": True, "path_policies": [
            {"prefix": "/limite", "requests": 3, "window_seconds": 60}]}
        config["options"]["active_defense"] = {"enabled": True}
    if profile == "static-tls":
        certs = folder / "secure" / "certificates" / "server"
        certs.mkdir(parents=True)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                        "-nodes", "-keyout", str(certs / "server.key"), "-out", str(certs / "server.pem"), "-days", "30",
                        "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
                       check=True, capture_output=True)
        config["tls"] = {"enabled": True, "mode": "direct", "certificate": {
            "certificate_path": "secure/certificates/server/server.pem",
            "private_key_path": "secure/certificates/server/server.key", "chain_path": "",
            "private_key_passphrase_env": ""}, "protocols": {"min_version": "TLS1.2", "max_version": "TLS1.3"}}
    (folder / "config" / "omega-serve.json").write_text(json.dumps(config, indent=2))
    print(f"projet de test pret : {folder}")


# ------------------------------------------------------------------------------------------------- le corpus
def _req(line: str, headers: list[str] | None = None, body: bytes = b"", ip: str | None = None) -> bytes:
    lines = [line, *(headers if headers is not None else [f"Host: {HOST}"])]
    if ip:
        lines.append(f"X-Forwarded-For: {ip}")
    lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body


def _basic(user: str, password: str) -> str:
    return "Authorization: Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def corpus() -> list[tuple[str, list[bytes | float]]]:
    """(nom, requetes envoyees sur UNE connexion). Chaque cas a sa propre adresse client (X-Forwarded-For)."""
    h = f"Host: {HOST}"
    cases: list[tuple[str, list[bytes]]] = []

    def add(name: str, *requests: bytes | float) -> None:  # un nombre = pause (secondes) avant la suite
        cases.append((name, list(requests)))

    ip = iter(f"198.51.100.{i}" for i in range(1, 250))
    # statique
    add("get-index", _req("GET / HTTP/1.1", ip=next(ip)))
    add("get-page", _req("GET /page.html HTTP/1.1", ip=next(ip)))
    add("head-page", _req("HEAD /page.html HTTP/1.1", ip=next(ip)))
    add("get-css", _req("GET /style.css HTTP/1.1", ip=next(ip)))
    add("get-css-gzip", _req("GET /style.css HTTP/1.1", [h, "Accept-Encoding: gzip"], ip=next(ip)))
    add("get-css-br-absent", _req("GET /style.css HTTP/1.1", [h, "Accept-Encoding: br"], ip=next(ip)))
    add("get-png", _req("GET /img.png HTTP/1.1", ip=next(ip)))
    add("get-big", _req("GET /big.bin HTTP/1.1", ip=next(ip)))
    add("get-missing", _req("GET /absent.html HTTP/1.1", ip=next(ip)))
    add("get-query", _req("GET /page.html?a=1&b=2 HTTP/1.1", ip=next(ip)))
    add("get-encoded", _req("GET /p%61ge.html HTTP/1.1", ip=next(ip)))
    add("if-modified-since", _req("GET /page.html HTTP/1.1", [h, "If-Modified-Since: Wed, 15 Nov 2023 00:00:00 GMT"], ip=next(ip)))
    add("if-modified-since-old", _req("GET /page.html HTTP/1.1", [h, "If-Modified-Since: Mon, 01 Jan 2001 00:00:00 GMT"], ip=next(ip)))
    add("range", _req("GET /big.bin HTTP/1.1", [h, "Range: bytes=0-9"], ip=next(ip)))
    add("range-suffix", _req("GET /big.bin HTTP/1.1", [h, "Range: bytes=-16"], ip=next(ip)))
    add("range-unsatisfiable", _req("GET /page.html HTTP/1.1", [h, "Range: bytes=99999-100000"], ip=next(ip)))
    add("healthz", _req("GET /healthz HTTP/1.1", ip=next(ip)))
    # repertoires, redirections, reecritures, alias, acces
    add("dirlisting", _req("GET /docs/ HTTP/1.1", ip=next(ip)))
    add("dirlisting-sorted", _req("GET /docs/?sort=size&order=desc HTTP/1.1", ip=next(ip)))
    add("dirlisting-head", _req("HEAD /docs/ HTTP/1.1", ip=next(ip)))
    add("admin-cache-stats", _req("GET /.omega-serv-admin/cache-stats HTTP/1.1", ip=next(ip)))
    add("load-probe", _req("GET /.omega-serv-load/ HTTP/1.1", ip=next(ip)))
    add("dir-no-slash", _req("GET /docs HTTP/1.1", ip=next(ip)))
    add("redirect", _req("GET /old/x HTTP/1.1", ip=next(ip)))
    add("rewrite", _req("GET /rw/a.txt HTTP/1.1", ip=next(ip)))
    add("alias", _req("GET /al/b.txt HTTP/1.1", ip=next(ip)))
    add("access-denied", _req("GET /private/secret.txt HTTP/1.1", ip=next(ip)))
    # authentification
    add("auth-missing", _req("GET /admin/ HTTP/1.1", ip=next(ip)))
    add("auth-bad", _req("GET /admin/ HTTP/1.1", [h, _basic(USER, "mauvais")], ip=next(ip)))
    add("auth-ok", _req("GET /admin/ HTTP/1.1", [h, _basic(USER, PASSWORD)], ip=next(ip)))
    # securite (WAF, blocklist, chemins)
    add("waf-env", _req("GET /.env HTTP/1.1", ip=next(ip)))
    add("waf-git", _req("GET /.git/config HTTP/1.1", ip=next(ip)))
    add("waf-sqli", _req("GET /?id=1%20UNION%20SELECT%201 HTTP/1.1", ip=next(ip)))
    add("waf-xss", _req("GET /?q=%3Cscript%3Ealert(1)%3C/script%3E HTTP/1.1", ip=next(ip)))
    add("waf-traversal", _req("GET /..%2f..%2fetc/passwd HTTP/1.1", ip=next(ip)))
    add("waf-scanner-ua", _req("GET / HTTP/1.1", [h, "User-Agent: sqlmap/1.7"], ip=next(ip)))
    add("blocklisted", _req("GET /page.html HTTP/1.1", ip=BANNED_IP))
    add("traversal-raw", _req("GET /../etc/passwd HTTP/1.1", ip=next(ip)))
    # methodes et versions
    add("options", _req("OPTIONS / HTTP/1.1", ip=next(ip)))
    add("delete", _req("DELETE /page.html HTTP/1.1", ip=next(ip)))
    add("trace", _req("TRACE / HTTP/1.1", ip=next(ip)))
    add("post-static", _req("POST /page.html HTTP/1.1", [h, "Content-Length: 3"], b"abc", ip=next(ip)))
    add("http10-no-host", _req("GET /page.html HTTP/1.0", [], ip=next(ip)))
    add("http11-no-host", _req("GET /page.html HTTP/1.1", [], ip=next(ip)))
    add("absolute-form", _req(f"GET http://{HOST}/page.html HTTP/1.1", ip=next(ip)))
    # requetes malformees (smuggling, limites)
    add("te-chunked", _req("POST /page.html HTTP/1.1", [h, "Transfer-Encoding: chunked"], b"3\r\nabc\r\n0\r\n\r\n", ip=next(ip)))
    add("cl-and-te", _req("POST /page.html HTTP/1.1", [h, "Content-Length: 3", "Transfer-Encoding: chunked"], b"abc", ip=next(ip)))
    add("cl-duplicate-differ", _req("POST /page.html HTTP/1.1", [h, "Content-Length: 3", "Content-Length: 4"], b"abcd", ip=next(ip)))
    add("cl-negative", _req("POST /page.html HTTP/1.1", [h, "Content-Length: -1"], ip=next(ip)))
    add("body-too-large", _req("POST /page.html HTTP/1.1", [h, "Content-Length: 20000000"], ip=next(ip)))
    add("header-too-large", _req("GET / HTTP/1.1", [h, "X-Big: " + "a" * 20000], ip=next(ip)))
    add("bad-request-line", b"GARBAGE\r\n\r\n")
    add("lowercase-method", _req("get / HTTP/1.1", ip=next(ip)))
    add("bad-version", _req("GET / HTTP/9.9", ip=next(ip)))
    add("obs-fold", _req("GET / HTTP/1.1", [h, "X-A: 1", " suite"], ip=next(ip)))
    add("space-before-colon", _req("GET / HTTP/1.1", [h, "X-A : 1"], ip=next(ip)))
    add("nul-in-path", b"GET /page.html%00.txt HTTP/1.1\r\nHost: " + HOST.encode() + b"\r\nConnection: close\r\n\r\n")
    add("expect-continue", _req("POST /page.html HTTP/1.1", [h, "Content-Length: 3", "Expect: 100-continue"], b"abc", ip=next(ip)))
    # controles du corps sur une route qui accepte le POST (zone d'upload) et en GET
    add("get-te-chunked", _req("GET / HTTP/1.1", [h, "Transfer-Encoding: chunked"], b"0\r\n\r\n", ip=next(ip)))
    add("get-cl-and-te", _req("GET / HTTP/1.1", [h, "Content-Length: 5", "Transfer-Encoding: chunked"], b"0\r\n\r\n", ip=next(ip)))
    add("upload-te-chunked", _req("POST /upload HTTP/1.1", [h, "Transfer-Encoding: chunked"], b"3\r\nabc\r\n0\r\n\r\n", ip=next(ip)))
    add("upload-cl-and-te", _req("POST /upload HTTP/1.1", [h, "Content-Length: 3", "Transfer-Encoding: chunked"], b"abc", ip=next(ip)))
    add("upload-cl-duplicate", _req("POST /upload HTTP/1.1", [h, "Content-Length: 3", "Content-Length: 4"], b"abcd", ip=next(ip)))
    add("upload-cl-negative", _req("POST /upload HTTP/1.1", [h, "Content-Length: -1"], ip=next(ip)))
    add("upload-cl-not-number", _req("POST /upload HTTP/1.1", [h, "Content-Length: 12abc"], ip=next(ip)))
    add("upload-too-large", _req("POST /upload HTTP/1.1", [h, "Content-Length: 20000000"], ip=next(ip)))
    add("upload-no-length", _req("POST /upload HTTP/1.1", [h], ip=next(ip)))
    add("upload-bad-body", _req("POST /upload HTTP/1.1", [h, "Content-Type: text/plain", "Content-Length: 3"], b"abc", ip=next(ip)))
    # keep-alive : deux requetes sur une connexion
    keep_ip = next(ip)
    first = f"GET /page.html HTTP/1.1\r\n{h}\r\nX-Forwarded-For: {keep_ip}\r\n\r\n".encode()
    second = _req("GET /style.css HTTP/1.1", ip=keep_ip)
    add("keep-alive-two", first, second)

    # --- elargi pour le moteur natif (lot 2, 2026-11-02)
    def keep(line: str, extra: list[str] | None = None, addr: str | None = None) -> bytes:
        lines = [line, h, *(extra or [])]
        if addr:
            lines.append(f"X-Forwarded-For: {addr}")
        return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")

    add("cl-plus", _req("POST /page.html HTTP/1.1", [h, "Content-Length: +3"], b"abc", ip=next(ip)))
    add("cl-underscore", _req("POST /page.html HTTP/1.1", [h, "Content-Length: 0_3"], b"abc", ip=next(ip)))
    add("head-missing", _req("HEAD /absent.html HTTP/1.1", ip=next(ip)))
    add("if-none-match", _req("GET /page.html HTTP/1.1", [h, 'If-None-Match: "6553f100-3a0"'], ip=next(ip)))
    add("if-none-match-star", _req("GET /page.html HTTP/1.1", [h, "If-None-Match: *"], ip=next(ip)))
    add("if-range-etag", _req("GET /big.bin HTTP/1.1", [h, "Range: bytes=5-9", 'If-Range: "nope"'], ip=next(ip)))
    add("range-mid", _req("GET /big.bin HTTP/1.1", [h, "Range: bytes=1000-70000"], ip=next(ip)))
    add("huge", _req("GET /huge.bin HTTP/1.1", ip=next(ip)))
    add("huge-range", _req("GET /huge.bin HTTP/1.1", [h, "Range: bytes=262000-262143"], ip=next(ip)))
    add("huge-head", _req("HEAD /huge.bin HTTP/1.1", ip=next(ip)))
    add("referer-repeated", _req("GET /page.html HTTP/1.1", [h, "Referer: http://a/", "Referer: http://b/"], ip=next(ip)))
    add("ua-latin1", _req("GET /page.html HTTP/1.1", [h, "User-Agent: caf\xe9 \xff"], ip=next(ip)))
    add("utf8-file", _req("GET /caf%C3%A9.txt HTTP/1.1", ip=next(ip)))
    add("latin1-raw-path", _req("GET /caf\xe9.txt HTTP/1.1", ip=next(ip)))
    add("bad-utf8-escape", _req("GET /caf%E9.txt HTTP/1.1", ip=next(ip)))
    add("symlink-in", _req("GET /lien-docs/a.txt HTTP/1.1", ip=next(ip)))
    add("symlink-out", _req("GET /lien-sortie/omega-serve.json HTTP/1.1", ip=next(ip)))
    add("symlink-loop", _req("GET /docs/lien-boucle HTTP/1.1", ip=next(ip)))
    add("hidden-allowed", _req("GET /.assets/app.css HTTP/1.1", ip=next(ip)))
    add("hidden-denied", _req("GET /.errors/404.html HTTP/1.1", ip=next(ip)))
    add("error-page-zone-csp", _req("GET /docs/absent.txt HTTP/1.1", ip=next(ip)))
    add("rewrite-loop", _req("GET /loop-a HTTP/1.1", ip=next(ip)))
    add("redirect-slash", _req("GET /vieux HTTP/1.1", ip=next(ip)))
    add("redirect-sub", _req("GET /vieux/x?y=1 HTTP/1.1", ip=next(ip)))
    add("dot-segments", _req("GET /docs/../page.html HTTP/1.1", ip=next(ip)))
    add("double-encoded", _req("GET /%252e%252e/page.html HTTP/1.1", ip=next(ip)))
    add("backslash", _req("GET /docs\\a.txt HTTP/1.1", ip=next(ip)))
    add("query-latin1", _req("GET /page.html?q=%C3%A9&r=\xe9 HTTP/1.1", ip=next(ip)))
    add("uri-too-long", _req("GET /" + "a" * 9000 + " HTTP/1.1", ip=next(ip)))
    add("too-many-headers", _req("GET / HTTP/1.1", [h] + [f"X-H{i}: v" for i in range(101)], ip=next(ip)))
    add("host-duplicate", _req("GET / HTTP/1.1", [h, h], ip=next(ip)))
    add("host-empty", _req("GET / HTTP/1.1", ["Host:"], ip=next(ip)))
    add("host-tab", _req("GET / HTTP/1.1", ["Host: a\tb"], ip=next(ip)))
    add("put", _req("PUT /page.html HTTP/1.1", [h, "Content-Length: 0"], ip=next(ip)))
    add("post-healthz", _req("POST /healthz HTTP/1.1", [h, "Content-Length: 0"], ip=next(ip)))
    add("head-healthz", _req("HEAD /healthz HTTP/1.1", ip=next(ip)))
    add("icon", _req("GET /.omega-serv-icons/audio.svg HTTP/1.1", ip=next(ip)))
    add("icon-head", _req("HEAD /.omega-serv-icons/audio.svg HTTP/1.1", ip=next(ip)))
    add("icon-unknown", _req("GET /.omega-serv-icons/nope.svg HTTP/1.1", ip=next(ip)))
    add("dirlisting-css-unknown", _req("GET /.omega-serv-dirlisting-css/inconnu.css HTTP/1.1", ip=next(ip)))
    add("error-css", _req("GET /.omega-serv-error-css/error-pages.css HTTP/1.1", ip=next(ip)))
    add("error-css-post", _req("POST /.omega-serv-error-css/error-pages.css HTTP/1.1", [h, "Content-Length: 0"], ip=next(ip)))
    add("error-css-wrong", _req("POST /.omega-serv-error-css/x.css HTTP/1.1", [h, "Content-Length: 0"], ip=next(ip)))
    add("xff-chain", _req("GET /page.html HTTP/1.1", [h, "X-Forwarded-For: 1.2.3.4, 10.0.0.1"]))
    add("xff-mapped", _req("GET /page.html HTTP/1.1", [h, "X-Forwarded-For: ::ffff:192.0.2.7"]))
    add("connection-close-upper", _req("GET /page.html HTTP/1.1", [h, "Connection: CLOSE"], ip=next(ip)))
    add("http10-with-host", _req("GET /page.html HTTP/1.0", ip=next(ip)))
    pipe_ip = next(ip)
    add("pipelined", keep("GET /page.html HTTP/1.1", addr=pipe_ip) + _req("GET /img.png HTTP/1.1", ip=pipe_ip))
    many_ip = next(ip)
    add("keepalive-limit", b"".join(keep(f"GET /docs/a.txt?n={i} HTTP/1.1", addr=many_ip) for i in range(31)))
    slow_ip = next(ip)
    add("slow-body", _req("POST /page.html HTTP/1.1", [h, "Content-Length: 10"], b"abc", ip=slow_ip), 2.6)
    add("slow-head", f"GET /page.html HTTP/1.1\r\n{h}\r\n".encode(), 2.6)
    idle_ip = next(ip)
    add("keepalive-idle", keep("GET /page.html HTTP/1.1", addr=idle_ip), 1.6, _req("GET /style.css HTTP/1.1", ip=idle_ip))
    add("truncated-head", f"GET /page.html HTTP/1.1\r\n{h}\r\nX-A: 1".encode())
    add("truncated-body", _req("POST /page.html HTTP/1.1", [h, "Content-Length: 50"], b"abc", ip=next(ip)))
    # plan §14 (2026-11-02) : version stricte, forme absolue, erreurs d'analyse dans access.log
    add("version-1-7", _req("GET /page.html HTTP/1.7", ip=next(ip)))
    add("version-2", _req("GET /page.html HTTP/2.0", ip=next(ip)))
    add("version-text", _req("GET /page.html HTTP/abc", ip=next(ip)))
    add("version-long", _req("GET /page.html HTTP/1.10", ip=next(ip)))
    add("absolute-https-upper", _req(f"GET HTTPS://{HOST}/docs/a.txt?x=1 HTTP/1.1", ip=next(ip)))
    add("absolute-no-path", _req(f"GET http://{HOST} HTTP/1.1", ip=next(ip)))
    add("absolute-query-only", _req(f"GET http://{HOST}?q=1 HTTP/1.1", ip=next(ip)))
    add("absolute-empty-host", _req("GET http:///page.html HTTP/1.1", ip=next(ip)))
    add("absolute-userinfo", _req(f"GET http://u@{HOST}/page.html HTTP/1.1", ip=next(ip)))
    add("absolute-hidden", _req(f"GET http://{HOST}/.secret HTTP/1.1", ip=next(ip)))
    add("absolute-no-host-header", _req(f"GET http://{HOST}/page.html HTTP/1.1", [], ip=next(ip)))
    add("absolute-ftp", _req(f"GET ftp://{HOST}/page.html HTTP/1.1", ip=next(ip)))
    add("parse-error-xff-ua", _req("GET /p HTTP/1.1", [h, "X-Forwarded-For: 203.0.113.50", "User-Agent: ua\xe9",
                                                     "Referer: http://r/", "X-A : 1"]))
    add("parse-error-latin1-line", b"GET /\xe9\x01\"x HTTP/7.1\r\nHost: h\r\n\r\n")
    add("eof-after-request-line", b"GET /page.html HTTP/1.1\r\n")
    add("eof-after-host", f"GET /page.html HTTP/1.1\r\n{h}\r\n".encode())
    burst_ip = next(ip)
    add("rate-limit-burst", b"".join(keep(f"GET /limite?n={i} HTTP/1.1", addr=burst_ip) for i in range(5)))
    sqli_body = b"q=1' UNION SELECT password FROM users--"
    add("waf-body-sqli", _req("POST /page.html HTTP/1.1", [h, "Content-Type: application/x-www-form-urlencoded",
                                                          f"Content-Length: {len(sqli_body)}"], sqli_body, ip=next(ip)))
    clean_body = b"nom=marie&ville=lyon"
    add("waf-body-clean", _req("POST /page.html HTTP/1.1", [h, "Content-Type: application/x-www-form-urlencoded",
                                                           f"Content-Length: {len(clean_body)}"], clean_body, ip=next(ip)))
    add("quotes-in-log", _req('GET /page.html?q="1" HTTP/1.1', [h, 'User-Agent: a"b', 'Referer: http://r/"x'], ip=next(ip)))
    return cases


def tls_corpus() -> list[tuple[str, list]]:
    """Cas propres a TLS (profil static-tls) : meme reponse, meme journal, et meme refus de poignee de main."""
    page = _req("GET /page.html HTTP/1.1", ip="198.51.100.240")
    return [
        ("tls-plain-http", [TLS_PLAIN, page]),
        ("tls-1.2-only", [TLS_ONLY_12, page]),
        ("tls-1.3-only", [TLS_ONLY_13, page]),
        ("tls-cipher-refused", [TLS_CIPHER_RSA_ONLY, page]),
    ]


# ------------------------------------------------------------------------------------------------ execution
def _wait_port(timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise SystemExit("le serveur n'a pas ouvert son port")


# Cas propres a TLS : premier element du cas = directive pour le client.
TLS_PLAIN = "@clair"            # HTTP en clair sur le port TLS
TLS_ONLY_12 = "@tls1.2"
TLS_ONLY_13 = "@tls1.3"
TLS_CIPHER_RSA_ONLY = "@suite-refusee"  # TLS 1.2 avec une suite absente de _MODERN_CIPHER_SUITES


def _tls_client(directive: str | None) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # certificat auto-signe du projet de test
    if directive == TLS_ONLY_12 or directive == TLS_CIPHER_RSA_ONLY:
        context.maximum_version = ssl.TLSVersion.TLSv1_2
    if directive == TLS_ONLY_13:
        context.minimum_version = ssl.TLSVersion.TLSv1_3
    if directive == TLS_CIPHER_RSA_ONLY:
        context.set_ciphers("AES128-SHA")
    return context


def _exchange(requests: list, tls: bool = False) -> bytes:
    directive = requests[0] if requests and isinstance(requests[0], str) else None
    if directive is not None:
        requests = requests[1:]
    with socket.create_connection(("127.0.0.1", PORT), timeout=5) as raw_sock:
        sock = raw_sock
        if tls and directive != TLS_PLAIN:
            try:
                sock = _tls_client(directive).wrap_socket(raw_sock)
            except (ssl.SSLError, OSError) as e:
                return f"<poignee de main refusee : {type(e).__name__}>".encode()
            negotiated = f"<{sock.version()} {sock.cipher()[0]}>".encode()
        else:
            negotiated = b""
        for request in requests:
            if isinstance(request, float):
                time.sleep(request)
                continue
            try:
                sock.sendall(request)
            except OSError:
                break  # connexion deja fermee par le serveur (delai depasse)
            time.sleep(0.05)
        if sock is raw_sock:  # en TLS, pas de demi-fermeture : la lecture s'arrete a la fin ou au delai
            try:
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
        chunks = [negotiated]
        sock.settimeout(3)
        while True:
            try:
                data = sock.recv(65536)
            except (TimeoutError, ConnectionResetError, ssl.SSLError):
                break
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks)


_DATE = re.compile(rb"^Date: [^\r\n]*\r\n", re.MULTILINE | re.IGNORECASE)
_LOG_TS = re.compile(r"\[\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}\]")


_LIVE_LOAD = re.compile(rb'("(?:cpu_percent|load_average_1m|memory_percent)": )[0-9.eE+-]+')


def _normalize_response(raw: bytes) -> dict:
    cleaned = _DATE.sub(b"", raw)
    head, _, body = cleaned.partition(b"\r\n\r\n")
    body = _LIVE_LOAD.sub(rb"\1N", body)  # /.omega-serv-load/ : mesures systeme en direct, jamais deux fois egales
    head = re.sub(r"Content-Length: \d+", "Content-Length: L", head.decode("latin-1")).encode("latin-1") \
        if body.startswith(b'{"cpu_percent"') else head
    return {"head": head.decode("latin-1"), "body_sha256": hashlib.sha256(body).hexdigest(), "body_len": len(body),
            "body_start": body[:160].decode("latin-1")}


def _normalize_access(line: str) -> str:
    line = _LOG_TS.sub("[TS]", line)
    if "/.omega-serv-load/" in line:  # taille du JSON de mesures en direct
        line = re.sub(r'" 200 \d+ "', '" 200 L "', line)
    return re.sub(r" \S+$", " RID", line)


_ERROR_TS = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] ")
_ERROR_RID = re.compile(r" \[[0-9a-f]{16}\]$")


def _normalize_error(line: str) -> str:
    return _ERROR_RID.sub(" [RID]", _ERROR_TS.sub("[TS] ", line))


def _normalize_alert(line: str) -> dict:
    try:
        data = json.loads(line)
    except ValueError:
        return {"raw": line}
    for key in ("timestamp", "request_id", "duration_ms", "elapsed_ms"):
        data.pop(key, None)
    return data


def _new_lines(path: Path, offset: int) -> tuple[list[str], int]:
    if not path.exists():
        return [], offset
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
    return [line for line in data.decode("utf-8", "replace").splitlines() if line.strip()], offset + len(data)


NATIVE_BINARY = REPO / "native" / "omega-http-core" / "build-asan" / "omega-http-core"
_SNAPSHOT_SCRIPT = """
import os, sys
from pathlib import Path
root = Path.cwd()
from omega_serv.bootstrap.early_language import install_page_language_early
install_page_language_early(os.environ, root)
from omega_serv.application.config.load_config import load_config
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.infrastructure.server.native_snapshot import native_unsupported_features, write_native_snapshot
result = load_config(DependencyContainer(project_root=root).configuration, Path("config/omega-serve.json"))
if not result.success:
    raise SystemExit("configuration refusee : " + "; ".join(result.errors))
missing = native_unsupported_features(result.config)
if missing:
    raise SystemExit("non pris en charge par le moteur natif : " + ", ".join(missing))
write_native_snapshot(result.config, root, 1, Path(sys.argv[1]))
"""


def _native_command(folder: Path, env: dict[str, str], binary: Path, threads: int) -> list[str]:
    snapshot = folder / "var" / "run" / "native-snapshot.json"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-c", _SNAPSHOT_SCRIPT, str(snapshot)], cwd=folder, env=env, check=True)
    return [str(binary), "--config", str(snapshot), "--threads", str(threads)]


def run(folder: Path, out: Path, engine: str, binary: Path = NATIVE_BINARY, threads: int = 2) -> None:
    folder = folder.resolve()
    env = {**os.environ, "PYTHONPATH": str(folder / "src")}
    config_file = folder / "config" / "omega-serve.json"
    original_config = config_file.read_text()
    if engine == "python":
        command = [sys.executable, "-m", "omega_serv", "--config", "config/omega-serve.json", "serve"]
    elif engine == "native":
        command = _native_command(folder, env, binary, threads)
    elif engine == "native-serve":
        # Lot 4 : le natif sous son vrai superviseur (processus de securite, canaux), server.engine = native le temps
        # de ce passage ; nombre de fils = coeurs utilisables (le superviseur le fixe lui-meme).
        config = json.loads(original_config)
        config.setdefault("server", {})["engine"] = "native"
        config_file.write_text(json.dumps(config, indent=2))
        (folder / "bin").mkdir(exist_ok=True)
        link = folder / "bin" / "omega-http-core"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(binary.resolve())
        command = [sys.executable, "-m", "omega_serv", "--config", "config/omega-serve.json", "serve"]
    else:
        raise SystemExit(f"moteur inconnu : {engine!r}")
    access = folder / "var" / "log" / "access.log"
    alerts = folder / "var" / "log" / "waf-alerts.log"
    errors = folder / "var" / "log" / "error.log"
    server = subprocess.Popen(command, cwd=folder, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_port()
        time.sleep(0.5)
        access_offset = access.stat().st_size if access.exists() else 0
        alerts_offset = alerts.stat().st_size if alerts.exists() else 0
        errors_offset = errors.stat().st_size if errors.exists() else 0
        results = {}
        tls = json.loads((folder / "config" / "omega-serve.json").read_text()).get("tls", {}).get("enabled", False)
        cases = corpus() + (tls_corpus() if tls else [])
        for name, requests in cases:
            raw = _exchange(requests, tls)
            time.sleep(0.15)  # journal ecrit apres la reponse
            access_lines, access_offset = _new_lines(access, access_offset)
            alert_lines, alerts_offset = _new_lines(alerts, alerts_offset)
            error_lines, errors_offset = _new_lines(errors, errors_offset)
            results[name] = {
                "response": _normalize_response(raw),
                "access_log": [_normalize_access(line) for line in access_lines],
                "waf_alerts": [_normalize_alert(line) for line in alert_lines],
                "error_log": [_normalize_error(line) for line in error_lines],
            }
    finally:
        server.terminate()
        try:
            server.wait(15)
        except subprocess.TimeoutExpired:
            server.kill()
        config_file.write_text(original_config)  # le projet de test reste celui du moteur Python
    out.write_text(json.dumps({"engine": engine, "cases": results}, indent=1, ensure_ascii=False))
    print(f"{len(results)} cas -> {out}")


def compare(first: Path, second: Path) -> int:
    a = json.loads(first.read_text())["cases"]
    b = json.loads(second.read_text())["cases"]
    differences = 0
    for name in sorted(set(a) | set(b)):
        if a.get(name) != b.get(name):
            differences += 1
            print(f"DIFFERENT : {name}")
            for part in ("response", "access_log", "waf_alerts", "error_log"):
                if (a.get(name) or {}).get(part) != (b.get(name) or {}).get(part):
                    print(f"  {part}:\n    {json.dumps((a.get(name) or {}).get(part), ensure_ascii=False)[:400]}"
                          f"\n    {json.dumps((b.get(name) or {}).get(part), ensure_ascii=False)[:400]}")
    print(f"{len(a)} cas, {differences} different(s)")
    return 1 if differences else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare"); p.add_argument("folder", type=Path)
    p.add_argument("--profile", choices=("full", "static", "static-tls", "secure"), default="full")
    r = sub.add_parser("run"); r.add_argument("folder", type=Path); r.add_argument("--out", type=Path, required=True)
    r.add_argument("--engine", choices=("python", "native", "native-serve"), default="python")
    r.add_argument("--native-bin", type=Path, default=NATIVE_BINARY)
    r.add_argument("--threads", type=int, default=2)
    c = sub.add_parser("compare"); c.add_argument("first", type=Path); c.add_argument("second", type=Path)
    args = parser.parse_args()
    if args.cmd == "prepare":
        prepare(args.folder, args.profile)
        return 0
    if args.cmd == "run":
        run(args.folder, args.out, args.engine, args.native_bin, args.threads)
        return 0
    return compare(args.first, args.second)


if __name__ == "__main__":
    raise SystemExit(main())

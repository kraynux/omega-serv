"""Captures du tableau de bord web (administration web) de l'instance de démonstration, pour la galerie.

    python3 tools/captures/capture_web.py <demo> <sortie> [--url https://127.0.0.1:19643]

Prérequis : la démo tourne (`serve`, qui lance l'administration web sur 127.0.0.1). Chromium est lancé sans
fenêtre, sur un profil jetable, avec son port de débogage sur 127.0.0.1 seulement, et piloté par le protocole
DevTools (module `websocket` du système). La connexion passe par le vrai formulaire : compte « alice » de la démo,
code TOTP calculé depuis son secret (fichier de la démo, jamais un vrai compte). Aucune requête hors de la machine :
Chromium tourne sans réseau d'arrière-plan, et le certificat autosigné de la démo est accepté pour cette session
seulement."""
from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket  # websocket-client (paquet du système)

DEBUG_PORT = 9333
PASSWORD = "Demo-Alice-2026!"  # mot de passe de démo fixé par demo_populate.py


def totp_now(secret: str) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", int(time.time()) // 30), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


class Browser:
    def __init__(self) -> None:
        self._profile = Path(tempfile.mkdtemp(prefix="omega-capture-web-"))
        self._process = subprocess.Popen(
            ["chromium", "--headless=new", f"--remote-debugging-port={DEBUG_PORT}",
             "--remote-debugging-address=127.0.0.1", f"--user-data-dir={self._profile}",
             "--ignore-certificate-errors", "--no-first-run", "--no-default-browser-check",
             "--disable-background-networking", "--disable-sync", "--disable-component-update",
             "--disable-domain-reliability", "--disable-features=Translate,MediaRouter,OptimizationHints",
             "--hide-scrollbars", "--font-render-hinting=none", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        target = None
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=1) as reply:
                    pages = [t for t in json.load(reply) if t.get("type") == "page"]
                if pages:
                    target = pages[0]
                    break
            except OSError:
                pass
            time.sleep(0.2)
        if target is None:
            self.close()
            raise SystemExit("Chromium ne répond pas sur son port de débogage")
        self._ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
        self._id = 0
        self.call("Page.enable")
        self.call("Runtime.enable")

    def call(self, method: str, **params: object) -> dict:
        self._id += 1
        self._ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            message = json.loads(self._ws.recv())
            if message.get("id") == self._id:
                if "error" in message:
                    raise RuntimeError(f"{method} : {message['error']}")
                return message.get("result", {})

    def viewport(self, width: int, height: int, mobile: bool = False) -> None:
        self.call("Emulation.setDeviceMetricsOverride", width=width, height=height,
                  deviceScaleFactor=2 if mobile else 1, mobile=mobile)

    def js(self, expression: str) -> object:
        result = self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        return result.get("result", {}).get("value")

    def open(self, url: str, wait: float = 3.5) -> None:
        self.call("Page.navigate", url=url)
        self.settle(wait)

    def settle(self, wait: float = 3.5) -> None:
        for _ in range(100):
            if self.js("document.readyState") == "complete":
                break
            time.sleep(0.1)
        time.sleep(wait)  # vues rafraîchies toutes les 2 s : au moins un rafraîchissement
        for _ in range(60):  # données arrivées (plus de « Chargement... » à l'écran)
            if not self.js("document.body.innerText.includes('Chargement')"):
                break
            time.sleep(0.25)
        time.sleep(0.5)

    def shot(self, path: Path) -> None:
        data = self.call("Page.captureScreenshot", format="png")["data"]
        path.write_bytes(base64.b64decode(data))
        print("ok", path.name, "-", self.js("location.pathname"))

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._ws.close()
        self._process.terminate()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
        shutil.rmtree(self._profile, ignore_errors=True)


def logout(browser: Browser) -> None:
    browser.js("(() => { const b = document.querySelector('form[action=\"/deconnexion\"] button');"
               " if (b) b.click(); })()")
    browser.settle(1.0)


def login(browser: Browser, base: str, secret: str, mode: str, fill_only: bool = False) -> None:
    browser.open(f"{base}/connexion", wait=0.8)
    browser.js(f"""(() => {{
        document.getElementById('identifiant').value = 'alice';
        document.getElementById('mot_de_passe').value = {json.dumps(PASSWORD)};
        document.getElementById('code').value = {json.dumps(totp_now(secret))};
        document.querySelector('input[name=mode][value={mode}]').checked = true;
    }})()""")
    if fill_only:
        return
    browser.js("document.querySelector('form').submit()")
    browser.settle(3.5)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    demo, out = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    base = argv[argv.index("--url") + 1] if "--url" in argv else "https://127.0.0.1:19643"
    if not base.startswith(("https://127.0.0.1:", "http://127.0.0.1:")):
        raise SystemExit("adresse refusée : captures en boucle locale seulement")
    accounts = json.loads((demo / "omega-serv" / "secure" / "auth" / "admin-web.json").read_text(encoding="utf-8"))
    secret = next(a["totp_secret"] for a in accounts["accounts"] if a["username"] == "alice")
    out.mkdir(parents=True, exist_ok=True)
    browser = Browser()
    try:
        browser.viewport(1400, 1000)
        login(browser, base, secret, "tableau", fill_only=True)  # formulaire rempli, mot de passe masqué
        browser.shot(out / "9.7-admin-web-connexion.png")
        login(browser, base, secret, "tableau")
        browser.shot(out / "9.7.2-admin-web-tableau-de-bord.png")
        # noms de la galerie : 9.7 = Multi-instance -> Configuration distante -> panneau web (décision 2026-11-18)
        for path, name in (("/journaux", "9.7.4-admin-web-journaux"), ("/securite", "9.7.5-admin-web-securite"),
                           ("/historique", "9.7.6-admin-web-historique"), ("/trafic", "9.7.7-admin-web-trafic"),
                           ("/certificats", "9.7.8-admin-web-certificats"), ("/alertes", "9.7.9-admin-web-alertes"),
                           ("/sessions", "9.7.10-admin-web-sessions"), ("/audit", "9.7.11-admin-web-journal-audit"),
                           ("/instances", "9.7.12-admin-web-instances")):
            browser.open(f"{base}{path}", wait=4.5 if path in ("/historique", "/journaux", "/instances") else 3.5)
            if path == "/journaux":  # un journal chargé plutôt qu'un cadre vide
                browser.js("(() => { const b = [...document.querySelectorAll('button')]"
                           ".find(x => /Instantan/.test(x.textContent)); if (b) b.click(); })()")
                browser.settle(2.5)
            browser.shot(out / f"{name}.png")
        browser.open(f"{base}/reconnexion", wait=1.0)
        browser.shot(out / "9.7.1-admin-web-nouvelle-saisie.png")
        logout(browser)
        login(browser, base, secret, "administration")
        browser.shot(out / "9.7.13-admin-web-administration.png")
        # téléphone : même tableau de bord en largeur mobile
        logout(browser)
        login(browser, base, secret, "tableau")
        browser.viewport(390, 844, mobile=True)
        browser.open(f"{base}/", wait=4.0)
        browser.shot(out / "9.7.3-admin-web-telephone.png")
    finally:
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

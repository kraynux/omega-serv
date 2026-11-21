"""`ssl` charge seulement quand le processus en a besoin (memoire, 2026-11-19, OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §11).

asyncio importe `ssl` d'office (base_events, selector_events, sslproto), meme pour un serveur sans TLS : 1,6 Mo par
processus Python (mesure : asyncio seul 11,8 Mo avec, 10,2 Mo sans). `defer_ssl_import`, appele avant le premier import
d'asyncio, charge asyncio comme sur un Python sans `ssl` (cas prevu par asyncio : `ssl = None`), puis remet `ssl`
importable. Le premier vrai `import ssl` du processus (TLS direct, backend HTTPS, envoi de la declaration...) est
intercepte une fois : le module est charge normalement, puis rebranche dans ces trois modules d'asyncio (et la
constante `SSLAgainErrors` de sslproto, calculee a l'import). Aucun appelant n'a a s'en soucier.

Garde : tests/unit/test_lazy_ssl.py (serveur et client TLS asyncio apres un `ssl` charge tard ; liste des references
module de `ssl` dans asyncio, pour une version de Python qui en ajouterait)."""
from __future__ import annotations

import sys

ASYNCIO_SSL_USERS = ("asyncio.base_events", "asyncio.selector_events", "asyncio.sslproto")

TYPE_CHECKING = False
if TYPE_CHECKING:
    from importlib.machinery import ModuleSpec
    from types import ModuleType


def defer_ssl_import() -> bool:
    """Vrai si applique ; rien si asyncio ou ssl sont deja charges."""
    if "ssl" in sys.modules or "asyncio" in sys.modules:
        return False
    sys.modules["ssl"] = None  # type: ignore[assignment]  # import ssl -> ImportError, prevu par asyncio
    try:
        import asyncio  # noqa: F401
    finally:
        del sys.modules["ssl"]
    sys.meta_path.insert(0, _AttachSslToAsyncio())
    return True


class _AttachSslToAsyncio:
    """Chercheur d'import qui ne fait qu'observer le premier `import ssl`, puis se retire."""

    def find_spec(self, name: str, path: object = None, target: object = None) -> ModuleSpec | None:
        if name != "ssl":
            return None
        sys.meta_path.remove(self)
        from importlib.machinery import PathFinder
        spec = PathFinder.find_spec(name)
        if spec is None or spec.loader is None:
            return spec
        exec_module = spec.loader.exec_module

        def exec_then_attach(module: ModuleType) -> None:
            exec_module(module)
            attach_ssl_to_asyncio(module)

        spec.loader.exec_module = exec_then_attach  # type: ignore[method-assign]
        return spec


def attach_ssl_to_asyncio(ssl_module: ModuleType) -> None:
    for name in ASYNCIO_SSL_USERS:
        module = sys.modules.get(name)
        if module is not None and getattr(module, "ssl", ssl_module) is None:
            module.ssl = ssl_module  # type: ignore[attr-defined]
    sslproto = sys.modules.get("asyncio.sslproto")
    if sslproto is not None and not hasattr(sslproto, "SSLAgainErrors"):
        sslproto.SSLAgainErrors = (ssl_module.SSLWantReadError, ssl_module.SSLSyscallError)  # type: ignore[attr-defined]

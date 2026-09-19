"""Entites de configuration OMEGA-SERV.

Forme fixee par OMEGA-SERV_SPECIFICATION.md §5.2 (exemple de
configuration generique). Ces dataclasses ne font aucune I/O : le
chargement du fichier JSON est delegue a
infrastructure/config/json_config_repository.py, la validation
structurelle a domain/config/validation.py, la resolution des chemins
relatifs en chemins absolus a infrastructure/filesystem/ (spec §4.1 :
"Le serveur resout ces chemins en chemins absolus au demarrage").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from omega_serv.domain.config.option import Option


@dataclass(frozen=True)
class PathsConfig:
    """Chemins relatifs a la racine du projet (spec §4.1) - jamais de
    chemin absolu personnel en dur."""
    webroot: str = "webroot"
    logs: str = "var/log"
    uploads: str = "var/uploads"
    secure: str = "secure"
    auth_file: str = "secure/auth/users.json"
    auth_zones: str = "secure/auth/zones.json"
    waf_script: str = "secure/waf/scripts/waf.lua"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PathsConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_dict(self) -> dict[str, Any]:
        return {
            "webroot": self.webroot,
            "logs": self.logs,
            "uploads": self.uploads,
            "secure": self.secure,
            "auth_file": self.auth_file,
            "auth_zones": self.auth_zones,
            "waf_script": self.waf_script,
        }


@dataclass(frozen=True)
class RotationConfig:
    enabled: bool = True
    max_bytes: int = 10_485_760
    keep: int = 7
    compress: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RotationConfig:
        return cls(
            enabled=bool(data.get("enabled", True)),
            max_bytes=int(data.get("max_bytes", 10_485_760)),
            keep=int(data.get("keep", 7)),
            compress=bool(data.get("compress", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_bytes": self.max_bytes,
            "keep": self.keep,
            "compress": self.compress,
        }


@dataclass(frozen=True)
class LogsConfig:
    access: str = "var/log/access.log"
    error: str = "var/log/error.log"
    waf_alerts: str = "var/log/waf-alerts.log"
    breakage: str = "var/log/breakage.log"
    uploads: str = "var/log/uploads.log"
    access_format: str = "combined"
    rotation: RotationConfig = field(default_factory=RotationConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LogsConfig:
        rotation = RotationConfig.from_dict(data.get("rotation", {}))
        return cls(
            access=data.get("access", cls.access),
            error=data.get("error", cls.error),
            waf_alerts=data.get("waf_alerts", cls.waf_alerts),
            breakage=data.get("breakage", cls.breakage),
            uploads=data.get("uploads", cls.uploads),
            access_format=data.get("access_format", cls.access_format),
            rotation=rotation,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "access": self.access,
            "error": self.error,
            "waf_alerts": self.waf_alerts,
            "breakage": self.breakage,
            "uploads": self.uploads,
            "access_format": self.access_format,
            "rotation": self.rotation.to_dict(),
        }


@dataclass(frozen=True)
class ServerConfig:
    bind: str = "127.0.0.1"
    port: int = 8080
    server_name: str = ""
    index_files: tuple[str, ...] = ("index.html",)
    max_connections: int = 256
    max_request_size: int = 10_485_760
    max_header_size: int = 16_384
    max_request_line_size: int = 8_192
    read_timeout_seconds: int = 10
    write_timeout_seconds: int = 15
    keepalive_timeout_seconds: int = 5
    max_keepalive_requests: int = 30
    listen_backlog: int = 128
    shutdown_grace_period_seconds: int = 10

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerConfig:
        defaults = cls()
        index_files = tuple(data.get("index_files", defaults.index_files))
        return cls(
            bind=data.get("bind", defaults.bind),
            port=int(data.get("port", defaults.port)),
            server_name=data.get("server_name", defaults.server_name),
            index_files=index_files,
            max_connections=int(data.get("max_connections", defaults.max_connections)),
            max_request_size=int(data.get("max_request_size", defaults.max_request_size)),
            max_header_size=int(data.get("max_header_size", defaults.max_header_size)),
            max_request_line_size=int(data.get("max_request_line_size", defaults.max_request_line_size)),
            read_timeout_seconds=int(data.get("read_timeout_seconds", defaults.read_timeout_seconds)),
            write_timeout_seconds=int(data.get("write_timeout_seconds", defaults.write_timeout_seconds)),
            keepalive_timeout_seconds=int(data.get("keepalive_timeout_seconds", defaults.keepalive_timeout_seconds)),
            max_keepalive_requests=int(data.get("max_keepalive_requests", defaults.max_keepalive_requests)),
            listen_backlog=int(data.get("listen_backlog", defaults.listen_backlog)),
            shutdown_grace_period_seconds=int(data.get("shutdown_grace_period_seconds", defaults.shutdown_grace_period_seconds)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bind": self.bind,
            "port": self.port,
            "server_name": self.server_name,
            "index_files": list(self.index_files),
            "max_connections": self.max_connections,
            "max_request_size": self.max_request_size,
            "max_header_size": self.max_header_size,
            "max_request_line_size": self.max_request_line_size,
            "read_timeout_seconds": self.read_timeout_seconds,
            "write_timeout_seconds": self.write_timeout_seconds,
            "keepalive_timeout_seconds": self.keepalive_timeout_seconds,
            "max_keepalive_requests": self.max_keepalive_requests,
            "listen_backlog": self.listen_backlog,
            "shutdown_grace_period_seconds": self.shutdown_grace_period_seconds,
        }


@dataclass(frozen=True)
class SecurityConfig:
    allowed_methods: tuple[str, ...] = ("GET", "HEAD")
    deny_hidden_files: bool = True
    deny_sensitive_extensions: tuple[str, ...] = (
        ".env", ".ini", ".conf", ".cfg", ".key", ".pem", ".crt", ".bak", ".orig", ".sql",
    )
    deny_patterns: tuple[str, ...] = ("~", ".htaccess", ".htpasswd")
    reject_path_traversal: bool = True
    normalize_url: bool = True
    require_valid_host: bool = True
    security_headers_enabled: bool = True
    csp_mode: str = "enforce"
    hsts_enabled: bool = False
    hsts_max_age: int = 31536000
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecurityConfig:
        defaults = cls()
        return cls(
            allowed_methods=tuple(data.get("allowed_methods", defaults.allowed_methods)),
            deny_hidden_files=bool(data.get("deny_hidden_files", defaults.deny_hidden_files)),
            deny_sensitive_extensions=tuple(data.get("deny_sensitive_extensions", defaults.deny_sensitive_extensions)),
            deny_patterns=tuple(data.get("deny_patterns", defaults.deny_patterns)),
            reject_path_traversal=bool(data.get("reject_path_traversal", defaults.reject_path_traversal)),
            normalize_url=bool(data.get("normalize_url", defaults.normalize_url)),
            require_valid_host=bool(data.get("require_valid_host", defaults.require_valid_host)),
            security_headers_enabled=bool(data.get("security_headers_enabled", defaults.security_headers_enabled)),
            csp_mode=data.get("csp_mode", defaults.csp_mode),
            hsts_enabled=bool(data.get("hsts_enabled", defaults.hsts_enabled)),
            hsts_max_age=int(data.get("hsts_max_age", defaults.hsts_max_age)),
            hsts_include_subdomains=bool(data.get("hsts_include_subdomains", defaults.hsts_include_subdomains)),
            hsts_preload=bool(data.get("hsts_preload", defaults.hsts_preload)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_methods": list(self.allowed_methods),
            "deny_hidden_files": self.deny_hidden_files,
            "deny_sensitive_extensions": list(self.deny_sensitive_extensions),
            "deny_patterns": list(self.deny_patterns),
            "reject_path_traversal": self.reject_path_traversal,
            "normalize_url": self.normalize_url,
            "require_valid_host": self.require_valid_host,
            "security_headers_enabled": self.security_headers_enabled,
            "csp_mode": self.csp_mode,
            "hsts_enabled": self.hsts_enabled,
            "hsts_max_age": self.hsts_max_age,
            "hsts_include_subdomains": self.hsts_include_subdomains,
            "hsts_preload": self.hsts_preload,
        }


@dataclass(frozen=True)
class TlsConfig:
    """Configuration TLS direct (doc TLS §12.1). Perimetre 6a
    verrouille : un seul listener, mode "direct" (ssl.SSLContext local)
    ou "behind_proxy" (TLS termine en amont, ce serveur reste en HTTP
    simple) - pas de mode hybride/double listener en V1."""
    enabled: bool = False
    mode: str = "behind_proxy"
    certificate_path: str = "secure/certificates/server/server.pem"
    private_key_path: str = "secure/certificates/server/server.key"
    chain_path: str = ""
    min_version: str = "TLS1.2"
    max_version: str = "TLS1.3"
    private_key_passphrase_env: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TlsConfig:
        defaults = cls()
        certificate = data.get("certificate", {})
        protocols = data.get("protocols", {})
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            mode=data.get("mode", defaults.mode),
            certificate_path=certificate.get("certificate_path", defaults.certificate_path),
            private_key_path=certificate.get("private_key_path", defaults.private_key_path),
            chain_path=certificate.get("chain_path", defaults.chain_path),
            min_version=protocols.get("min_version", defaults.min_version),
            max_version=protocols.get("max_version", defaults.max_version),
            private_key_passphrase_env=certificate.get("private_key_passphrase_env", defaults.private_key_passphrase_env),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "certificate": {
                "certificate_path": self.certificate_path,
                "private_key_path": self.private_key_path,
                "chain_path": self.chain_path,
                "private_key_passphrase_env": self.private_key_passphrase_env,
            },
            "protocols": {
                "min_version": self.min_version,
                "max_version": self.max_version,
            },
        }


@dataclass(frozen=True)
class OmegaServConfig:
    """Configuration complete OMEGA-SERV - forme du fichier
    config/omega-serve.json (spec §5.2)."""
    version: int = 1
    profile: str = "standard"
    paths: PathsConfig = field(default_factory=PathsConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    logs: LogsConfig = field(default_factory=LogsConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    tls: TlsConfig = field(default_factory=TlsConfig)
    options: dict[str, Option] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OmegaServConfig:
        options_data = data.get("options", {})
        options = {
            name: Option.from_dict(name, opt_data)
            for name, opt_data in options_data.items()
        }
        return cls(
            version=int(data.get("version", 1)),
            profile=data.get("profile", "standard"),
            paths=PathsConfig.from_dict(data.get("paths", {})),
            server=ServerConfig.from_dict(data.get("server", {})),
            logs=LogsConfig.from_dict(data.get("logs", {})),
            security=SecurityConfig.from_dict(data.get("security", {})),
            tls=TlsConfig.from_dict(data.get("tls", {})),
            options=options,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "profile": self.profile,
            "paths": self.paths.to_dict(),
            "server": self.server.to_dict(),
            "logs": self.logs.to_dict(),
            "security": self.security.to_dict(),
            "tls": self.tls.to_dict(),
            "options": {name: opt.to_dict() for name, opt in self.options.items()},
        }

    def option_enabled(self, name: str) -> bool:
        option = self.options.get(name)
        return option is not None and option.enabled

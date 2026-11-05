// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Instantane de configuration (contrat IPC §4) : construit et VALIDE par Python
// (src/omega_serv/infrastructure/server/native_snapshot.py), une seule source de verite. Le natif ne fait
// qu'un controle de structure : un champ manquant ou mal type -> instantane refuse (l'ancienne generation
// reste active, ou repli moteur Python au demarrage), jamais une valeur par defaut devinee ici.
#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "http_parser.hpp"
#include "ip.hpp"
#include "static_rules.hpp"

namespace omega {

class WafFilter;  // waf_filter.hpp

inline constexpr int kSnapshotFormat = 1;

struct ServerSettings {
    std::string bind;
    int port = 0;
    int listen_backlog = 128;
    std::size_t max_connections = 256;
    std::uint64_t max_request_size = 10485760;
    std::size_t max_header_size = 16384;
    std::size_t max_request_line_size = 8192;
    double read_timeout_seconds = 10;
    double keepalive_timeout_seconds = 5;
    int max_keepalive_requests = 30;
    double shutdown_grace_period_seconds = 10;
    std::vector<std::string> index_files;
    std::string webroot;  // chemin reel, resolu une fois par Python (comme SafePathResolver au demarrage)
};

struct SecurityHeaders {
    // apply_security_headers(path=None) cote Python, dans l'ordre exact ; seule la valeur de `csp_header`
    // change selon le chemin (zones csp_zones, plus long prefixe).
    std::vector<std::pair<std::string, std::string>> ordered;
    std::string csp_header;
    std::vector<std::string> csp_zone_prefixes;
    std::vector<std::string> csp_zone_policies;
};

struct AccessRule {
    std::string prefix;
    bool allow = true;
    std::vector<std::string> extensions;
};

struct RedirectRule {
    std::string prefix;
    std::string destination;
    int status = 302;
};

struct RewriteRule {
    std::string match_prefix;
    std::string replacement_prefix;
};

struct AliasRule {
    std::string prefix;
    std::string root;  // project_root / target_path, NON resolu (Python le resout a chaque requete)
};

struct InternalAssets {
    std::string icon_prefix;
    std::map<std::string, std::string> icons;  // nom -> SVG
    std::string dirlisting_css_prefix;
    std::map<std::string, std::string> dirlisting_css;  // theme -> CSS
    std::string dirlisting_css_fallback;
    std::string error_css_prefix;
    std::string error_css_name;
    std::string error_css;
    std::string load_prefix;   // /.omega-serv-load/ (Python seul, reseaux de confiance)
    std::string admin_prefix;  // /.omega-serv-admin/
};

// TLS direct (lot 3b) : tout vient de Python (ssl_context_builder.py), rien n'est devine ici.
struct TlsSettings {
    std::string certificate;     // chemin absolu (chaine complete, comme load_cert_chain)
    std::string private_key;     // chemin absolu
    std::string passphrase_env;  // nom de la variable d'environnement de la phrase de passe, vide = aucune
    std::string min_version;     // "TLS1.2" | "TLS1.3"
    std::string max_version;
    std::string ciphers;         // _MODERN_CIPHER_SUITES (TLS 1.2 ; TLS 1.3 : suites par defaut d'OpenSSL)
};

// Securite via Python (lot 4) : apres la lecture du corps, chaque requete est soumise (INSPECT) au processus Python
// de securite (leurres, WAF, Active Defense, mode guerre, Auth) ; son VERDICT dit de continuer ou quoi repondre.
struct InspectSettings {
    std::vector<std::string> body_methods;  // waf.inspect.body_methods : corps capture pour ces methodes seulement
    std::uint64_t body_bytes = 0;            // waf.inspect.body_max_inspect_bytes (0 : jamais de corps)
    int timeout_ms = 0;                      // au-dela : on_error
    bool fail_closed = false;                // on_error : 503 (true) ou requete servie sans controle (false)
    // Lot 6 : prefixes des routes applicatives (reverse proxy, FastCGI ; envoi de fichiers pour POST). Un chemin
    // (d'origine ou reecrit) qui en commence un : la connexion est confiee a Python, qui la traite jusqu'au bout.
    std::optional<std::string> blocklist_path;  // WAF + blocklist actifs : bannis refuses (451) meme en fail-open
    std::vector<std::string> handoff_any;
    std::vector<std::string> handoff_post;
    bool security_stage = false;             // leurre / WAF / AD / Auth actifs : INSPECT pour chaque requete ; sinon
                                             // le processus Python ne sert qu'aux routes deleguees (lot 5)
};

struct Snapshot {
    std::uint32_t generation = 0;
    ServerSettings server;
    ParserLimits parser_limits;

    // security
    bool require_valid_host = true;
    std::vector<std::string> allowed_methods;
    DenyRules deny;
    std::optional<SecurityHeaders> security_headers;  // absent : security_headers_enabled = false

    std::optional<std::vector<IpNetwork>> trusted_networks;  // option trusted_proxy active
    std::vector<IpNetwork> trusted_networks_for_internal;   // routes /load et /admin (vide si option inactive)
    std::vector<std::string> header_preference;

    std::optional<std::vector<AccessRule>> access_rules;
    std::optional<std::vector<RedirectRule>> redirects;
    std::optional<std::vector<RewriteRule>> rewrites;
    std::optional<std::vector<AliasRule>> aliases;
    std::optional<CachePolicy> cache;
    std::vector<std::string> dirlisting_zones;  // non portees en lot 2 : la requete part vers Python

    // pages d'erreur
    std::optional<std::string> error_custom_dir;  // absent : option error_pages inactive
    std::string page_lang;                        // core.i18n.page_html_lang()
    std::map<int, std::string> default_error_pages;
    std::map<int, std::string> reason_phrases;

    InternalAssets internal;

    std::string access_log;
    std::string error_log;

    std::optional<TlsSettings> tls;  // null : TLS desactive ou termine en amont (behind_proxy)
    std::optional<InspectSettings> inspect;  // null : aucune fonction de securite Python active
    // Filtre WAF (plan WAF natif, lot 1) : null sans WAF. Ne sert qu'a reconnaitre une requete propre.
    std::shared_ptr<const WafFilter> waf_filter;
};

// nullptr + `error` rempli si l'instantane est mal forme.
std::shared_ptr<const Snapshot> parse_snapshot(std::string_view json_text, std::string* error);

}  // namespace omega

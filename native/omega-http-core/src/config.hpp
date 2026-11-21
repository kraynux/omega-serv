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

#include "util.hpp"
#include "http_parser.hpp"
#include "ip.hpp"
#include "static_rules.hpp"
#include "waf_alert.hpp"

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
    double write_timeout_seconds = 15;  // lot A (D31) : delai SANS PROGRES de l'envoi d'une reponse
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
    // Lot 2 : corps plus grand que cette taille refuse (413), pour body_methods (waf.inspect.body_over_limit = reject).
    std::optional<std::uint64_t> body_reject_over;
    // Lot 1N (D36) : journal waf-alerts des refus que le natif decide seul (absent sans WAF).
    std::optional<WafAlertSettings> waf_alerts;
    bool security_stage = false;             // leurre / WAF / AD / Auth actifs : INSPECT pour chaque requete ; sinon
                                             // le processus Python ne sert qu'aux routes deleguees (lot 5)
    // Plan proxy natif v2, lot 3 (P6) : processus de securite ; le fil i est servi par le processus i % N, et
    // /.omega-serv-admin/ est toujours confie au n° 0 (seul responsable de la sante des backends).
    std::size_t security_processes = 1;
};

// Plan proxy natif v2, lot 3 : instantane `proxy` (zones, backends, regles, delais, budgets, INSPECT par zone). Lu et
// verifie ; aucune zone n'est relayee par le natif avant le lot 4 (elles restent dans inspect.handoff_any).
struct ProxyUpstream {
    std::string key;          // upstream_key : "hote:port", identite stable (regles, cookie collant, sante)
    std::string host;
    int port = 0;
    std::string host_header;  // host_header_value (IPv6 entre crochets, D28)
    std::optional<std::string> address;  // IP litterale canonique ; nom DNS : resolu par Python (lot 4, C18)
    bool tls = false;
    int weight = 1;
    std::optional<std::int64_t> max_concurrent;  // null : illimite
    std::string load_source;  // none | native | declarative
    // Plan proxy natif v2, lot 6 : un backend par adresse (nom DNS resolu par Python, C18). `key` : identite de la
    // sante et du pool (« hote:port », ou « nom (adresse):port ») ; `name` : upstream_key de la configuration, cible
    // des regles par en-tete et des etats manuels ; `cookie` : valeur du cookie collant (sticky_cookie_value_for_key).
    std::string name;
    std::string cookie;
    bool active_check = false;      // sonde active (processus n° 0) : pas d'essai passif a demi ouvert
    std::optional<std::string> unusable;  // "dns" (nom non resolu) | "boucle" : jamais choisi
};

struct ProxyRoutingRule {
    std::string header;
    std::string pattern;   // egalite, ou prefixe si termine par « * »
    std::string upstream;  // ProxyUpstream::key, present dans la zone
};

struct ProxySticky {
    std::string cookie_name;
    std::int64_t max_age_seconds = 0;
};

enum class ZoneInspect { never, filter, always };

struct ProxyZoneSettings {
    std::string prefix;
    bool native = false;               // false : connexion confiee a Python
    std::vector<std::string> reasons;  // pourquoi la zone est confiee (vide si native)
    ZoneInspect inspect = ZoneInspect::always;
    std::int64_t connect_timeout_ms = 0;
    std::int64_t read_timeout_ms = 0;
    bool preserve_host = false;
    bool verify_tls = true;
    bool websocket = false;
    std::int64_t websocket_idle_timeout_ms = 3600000;  // lot 10 (Q11) : tunnel sans octet -> 1001 ; 0 = aucun delai
    std::string load_balancing;
    std::optional<ProxySticky> sticky;
    std::vector<ProxyRoutingRule> routing_rules;
    int unhealthy_after = 3;
    int healthy_after = 2;
    std::int64_t load_sample_max_age_ms = 60000;  // real_load : score perime au-dela (lot 6)
    std::vector<ProxyUpstream> upstreams;
};

struct ProxyBudgets {  // C2 : globaux, tous fils confondus ; epuise -> 503 immediat
    std::uint64_t pending_body_bytes = 0;
    std::size_t inspections = 0;
    std::size_t upstream_connections = 0;
};

struct ProxySettings {
    std::string engine;  // auto | native | python (options.reverse_proxy.engine, P8)
    ProxyBudgets budgets;
    std::uint64_t max_response_body_bytes = 0;
    std::vector<ProxyZoneSettings> zones;
};

// Section `proxy` seule (lot 6, outil de test --simulate-balance) ; nullopt + `error` si mal formee.
std::optional<ProxySettings> parse_proxy_section(const Json& proxy, std::string* error);

// Meme forme que native_snapshot.proxy_section (cles et valeurs) : test differentiel Python / natif.
std::string dump_proxy_json(const ProxySettings& proxy);

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
    std::optional<ProxySettings> proxy;      // null : reverse proxy inactif (lot 3)
    // Filtre WAF (plan WAF natif, lot 1) : null sans WAF. Ne sert qu'a reconnaitre une requete propre.
    std::shared_ptr<const WafFilter> waf_filter;
};

// nullptr + `error` rempli si l'instantane est mal forme.
std::shared_ptr<const Snapshot> parse_snapshot(std::string_view json_text, std::string* error);

}  // namespace omega

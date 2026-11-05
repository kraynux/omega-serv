// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "config.hpp"

#include <cmath>
#include <stdexcept>

#include "util.hpp"
#include "waf_filter.hpp"

namespace omega {

namespace {

struct SnapshotError : std::runtime_error {
    using std::runtime_error::runtime_error;
};

const Json& need(const Json& object, std::string_view key) {
    if (!object.is_object()) throw SnapshotError("objet attendu avant « " + std::string(key) + " »");
    const Json* value = object.get(key);
    if (value == nullptr) throw SnapshotError("champ manquant : " + std::string(key));
    return *value;
}

const std::string& need_string(const Json& object, std::string_view key) {
    const Json& value = need(object, key);
    if (!value.is_string()) throw SnapshotError("texte attendu : " + std::string(key));
    return value.as_string();
}

double need_number(const Json& object, std::string_view key) {
    const Json& value = need(object, key);
    if (!std::holds_alternative<double>(value.value)) throw SnapshotError("nombre attendu : " + std::string(key));
    return std::get<double>(value.value);
}

std::int64_t need_integer(const Json& object, std::string_view key, std::int64_t min, std::int64_t max) {
    const double value = need_number(object, key);
    if (std::floor(value) != value || value < static_cast<double>(min) || value > static_cast<double>(max)) {
        throw SnapshotError("entier hors bornes : " + std::string(key));
    }
    return static_cast<std::int64_t>(value);
}

bool need_bool(const Json& object, std::string_view key) {
    const Json& value = need(object, key);
    if (!std::holds_alternative<bool>(value.value)) throw SnapshotError("booleen attendu : " + std::string(key));
    return std::get<bool>(value.value);
}

const JsonArray& need_array(const Json& object, std::string_view key) {
    const Json& value = need(object, key);
    if (!value.is_array()) throw SnapshotError("liste attendue : " + std::string(key));
    return *std::get<std::shared_ptr<JsonArray>>(value.value);
}

// null -> absent (option inactive)
const Json* optional_value(const Json& object, std::string_view key) {
    const Json& value = need(object, key);
    return value.is_null() ? nullptr : &value;
}

std::vector<std::string> string_list(const Json& object, std::string_view key) {
    std::vector<std::string> out;
    for (const Json& item : need_array(object, key)) {
        if (!item.is_string()) throw SnapshotError("liste de textes attendue : " + std::string(key));
        out.push_back(item.as_string());
    }
    return out;
}

std::map<std::string, std::string> string_map(const Json& object, std::string_view key) {
    const Json& value = need(object, key);
    if (!value.is_object()) throw SnapshotError("objet attendu : " + std::string(key));
    std::map<std::string, std::string> out;
    for (const auto& [name, item] : value.object()) {
        if (!item.is_string()) throw SnapshotError("objet de textes attendu : " + std::string(key));
        out[name] = item.as_string();
    }
    return out;
}

std::vector<std::pair<std::string, std::string>> pair_list(const Json& object, std::string_view key) {
    std::vector<std::pair<std::string, std::string>> out;
    for (const Json& item : need_array(object, key)) {
        if (!item.is_array()) throw SnapshotError("liste de paires attendue : " + std::string(key));
        const JsonArray& pair = *std::get<std::shared_ptr<JsonArray>>(item.value);
        if (pair.size() != 2 || !pair[0].is_string() || !pair[1].is_string()) {
            throw SnapshotError("paire [texte, texte] attendue : " + std::string(key));
        }
        out.emplace_back(pair[0].as_string(), pair[1].as_string());
    }
    return out;
}

std::map<int, std::string> status_map(const Json& object, std::string_view key) {
    std::map<int, std::string> out;
    for (const auto& [code, text] : string_map(object, key)) {
        int value = 0;
        for (char c : code) {
            if (c < '0' || c > '9' || value > 999) throw SnapshotError("code HTTP invalide dans " + std::string(key));
            value = value * 10 + (c - '0');
        }
        if (value < 100 || value > 599) throw SnapshotError("code HTTP invalide dans " + std::string(key));
        out[value] = text;
    }
    return out;
}

std::vector<IpNetwork> networks(const std::vector<std::string>& texts) { return parse_trusted_networks(texts); }

void parse_server(const Json& root, Snapshot& s) {
    const Json& server = need(root, "server");
    ServerSettings& out = s.server;
    out.bind = need_string(server, "bind");
    out.port = static_cast<int>(need_integer(server, "port", 0, 65535));
    out.listen_backlog = static_cast<int>(need_integer(server, "listen_backlog", 1, 65535));
    out.max_connections = static_cast<std::size_t>(need_integer(server, "max_connections", 1, 1000000));
    out.max_request_size = static_cast<std::uint64_t>(need_integer(server, "max_request_size", 0, INT64_C(1) << 50));
    out.max_header_size = static_cast<std::size_t>(need_integer(server, "max_header_size", 1, 1 << 24));
    out.max_request_line_size = static_cast<std::size_t>(need_integer(server, "max_request_line_size", 1, 1 << 24));
    out.read_timeout_seconds = need_number(server, "read_timeout_seconds");
    out.keepalive_timeout_seconds = need_number(server, "keepalive_timeout_seconds");
    out.max_keepalive_requests = static_cast<int>(need_integer(server, "max_keepalive_requests", 0, 1000000));
    out.shutdown_grace_period_seconds = need_number(server, "shutdown_grace_period_seconds");
    out.index_files = string_list(server, "index_files");
    out.webroot = need_string(server, "webroot");
    if (out.webroot.empty() || out.webroot[0] != '/') throw SnapshotError("webroot doit etre un chemin absolu");
    s.parser_limits.max_request_line_size = out.max_request_line_size;
    s.parser_limits.max_header_size = out.max_header_size;
}

void parse_security(const Json& root, Snapshot& s) {
    const Json& security = need(root, "security");
    s.require_valid_host = need_bool(security, "require_valid_host");
    s.allowed_methods = string_list(security, "allowed_methods");
    s.deny.deny_hidden_files = need_bool(security, "deny_hidden_files");
    s.deny.deny_sensitive_extensions = string_list(security, "deny_sensitive_extensions");
    s.deny.deny_patterns = string_list(security, "deny_patterns");
    if (const Json* headers = optional_value(security, "headers")) {
        SecurityHeaders out;
        out.ordered = pair_list(*headers, "ordered");
        out.csp_header = need_string(*headers, "csp_header");
        for (auto& [prefix, policy] : pair_list(*headers, "csp_zones")) {
            out.csp_zone_prefixes.push_back(prefix);
            out.csp_zone_policies.push_back(policy);
        }
        s.security_headers = std::move(out);
    }
}

void parse_routes(const Json& root, Snapshot& s) {
    const Json& routes = need(root, "routes");
    if (const Json* proxy = optional_value(routes, "trusted_proxy")) {
        s.trusted_networks = networks(string_list(*proxy, "networks"));
        s.trusted_networks_for_internal = *s.trusted_networks;
        s.header_preference = string_list(*proxy, "header_preference");
    }
    if (const Json* list = optional_value(routes, "access_rules")) {
        std::vector<AccessRule> rules;
        for (const Json& item : need_array(*list, "list")) {
            AccessRule rule;
            rule.prefix = need_string(item, "path_prefix");
            const std::string& verdict = need_string(item, "verdict");
            if (verdict != "allow" && verdict != "deny") throw SnapshotError("verdict d'acces invalide");
            rule.allow = verdict == "allow";
            rule.extensions = string_list(item, "extensions");
            rules.push_back(std::move(rule));
        }
        s.access_rules = std::move(rules);
    }
    if (const Json* list = optional_value(routes, "redirects")) {
        std::vector<RedirectRule> rules;
        for (const Json& item : need_array(*list, "list")) {
            RedirectRule rule;
            rule.prefix = need_string(item, "url_prefix");
            rule.destination = need_string(item, "destination");
            rule.status = static_cast<int>(need_integer(item, "status_code", 100, 599));
            rules.push_back(std::move(rule));
        }
        s.redirects = std::move(rules);
    }
    if (const Json* list = optional_value(routes, "rewrites")) {
        std::vector<RewriteRule> rules;
        for (const Json& item : need_array(*list, "list")) {
            rules.push_back({need_string(item, "match_prefix"), need_string(item, "replacement_prefix")});
        }
        s.rewrites = std::move(rules);
    }
    if (const Json* list = optional_value(routes, "aliases")) {
        std::vector<AliasRule> rules;
        for (const Json& item : need_array(*list, "list")) {
            rules.push_back({need_string(item, "url_prefix"), need_string(item, "root")});
        }
        s.aliases = std::move(rules);
    }
    if (const Json* cache = optional_value(routes, "cache")) {
        CachePolicy policy;
        policy.default_value = need_string(*cache, "default");
        policy.zones = pair_list(*cache, "zones");
        policy.extensions = pair_list(*cache, "extensions");
        s.cache = std::move(policy);
    }
    if (const Json* dirlisting = optional_value(routes, "dirlisting")) {
        s.dirlisting_zones = string_list(*dirlisting, "zone_prefixes");
    }
}

void parse_error_pages(const Json& root, Snapshot& s) {
    const Json& pages = need(root, "error_pages");
    if (const Json* custom = optional_value(pages, "custom_dir")) {
        if (!custom->is_string()) throw SnapshotError("texte attendu : custom_dir");
        s.error_custom_dir = custom->as_string();
    }
    s.page_lang = need_string(pages, "page_lang");
    s.default_error_pages = status_map(pages, "defaults");
    s.reason_phrases = status_map(pages, "reason_phrases");
}

void parse_internal(const Json& root, Snapshot& s) {
    const Json& internal = need(root, "internal");
    InternalAssets& out = s.internal;
    out.icon_prefix = need_string(internal, "icon_prefix");
    out.icons = string_map(internal, "icons");
    out.dirlisting_css_prefix = need_string(internal, "dirlisting_css_prefix");
    out.dirlisting_css = string_map(internal, "dirlisting_css");
    out.dirlisting_css_fallback = need_string(internal, "dirlisting_css_fallback");
    out.error_css_prefix = need_string(internal, "error_css_prefix");
    out.error_css_name = need_string(internal, "error_css_name");
    out.error_css = need_string(internal, "error_css");
    out.load_prefix = need_string(internal, "load_prefix");
    out.admin_prefix = need_string(internal, "admin_prefix");
}

}  // namespace

std::shared_ptr<const Snapshot> parse_snapshot(std::string_view json_text, std::string* error) {
    std::string json_error;
    const auto root = parse_json(json_text, &json_error);
    if (!root) {
        if (error) *error = "JSON invalide : " + json_error;
        return nullptr;
    }
    try {
        if (need_integer(*root, "format", 0, 1000) != kSnapshotFormat) throw SnapshotError("format d'instantane inconnu");
        auto snapshot = std::make_shared<Snapshot>();
        snapshot->generation = static_cast<std::uint32_t>(need_integer(*root, "generation", 0, UINT32_MAX));
        parse_server(*root, *snapshot);
        parse_security(*root, *snapshot);
        parse_routes(*root, *snapshot);
        parse_error_pages(*root, *snapshot);
        parse_internal(*root, *snapshot);
        const Json& logs = need(*root, "logs");
        snapshot->access_log = need_string(logs, "access");
        snapshot->error_log = need_string(logs, "error");
        if (const Json* inspect = optional_value(*root, "inspect")) {
            InspectSettings settings;
            settings.body_methods = string_list(*inspect, "body_methods");
            settings.body_bytes = static_cast<std::uint64_t>(need_integer(*inspect, "body_bytes", 0, INT64_C(1) << 40));
            settings.timeout_ms = static_cast<int>(need_integer(*inspect, "timeout_ms", 1, 3600 * 1000));
            const std::string& on_error = need_string(*inspect, "on_error");
            if (on_error != "fail-open" && on_error != "fail-closed") throw SnapshotError("inspect.on_error inconnu : " + on_error);
            settings.fail_closed = on_error == "fail-closed";
            settings.security_stage = need_bool(*inspect, "security_stage");
            if (const Json* blocklist = optional_value(*inspect, "blocklist")) {
                if (!blocklist->is_string() || blocklist->as_string().empty() || blocklist->as_string()[0] != '/')
                    throw SnapshotError("inspect.blocklist : chemin absolu attendu");
                settings.blocklist_path = blocklist->as_string();
            }
            settings.handoff_any = string_list(*inspect, "handoff_any");
            settings.handoff_post = string_list(*inspect, "handoff_post");
            snapshot->inspect = std::move(settings);
        }
        // Plan WAF natif (lot 1) : absent ou null = aucun filtre (toute requete inspectee par Python, comme avant).
        if (const Json* waf_filter = root->get("waf_filter"); waf_filter != nullptr && !waf_filter->is_null()) {
            try {
                snapshot->waf_filter = WafFilter::from_json(*waf_filter);
            } catch (const SnapshotError&) {
                throw;
            } catch (const std::runtime_error& e) {
                throw SnapshotError(e.what());
            }
        }
        if (const Json* tls = optional_value(*root, "tls")) {
            TlsSettings settings;
            settings.certificate = need_string(*tls, "certificate");
            settings.private_key = need_string(*tls, "private_key");
            settings.passphrase_env = need_string(*tls, "passphrase_env");
            settings.min_version = need_string(*tls, "min_version");
            settings.max_version = need_string(*tls, "max_version");
            settings.ciphers = need_string(*tls, "ciphers");
            for (const std::string* version : {&settings.min_version, &settings.max_version}) {
                if (*version != "TLS1.2" && *version != "TLS1.3") throw SnapshotError("version TLS inconnue : " + *version);
            }
            if (settings.certificate.empty() || settings.certificate[0] != '/' || settings.private_key.empty() ||
                settings.private_key[0] != '/')
                throw SnapshotError("chemins TLS absolus attendus");
            snapshot->tls = std::move(settings);
        }
        return snapshot;
    } catch (const SnapshotError& e) {
        if (error) *error = e.what();
        return nullptr;
    }
}

}  // namespace omega

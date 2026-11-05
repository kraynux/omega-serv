// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "engine.hpp"

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <map>
#include <set>
#include <unordered_map>

#include "ip.hpp"
#include "static_rules.hpp"
#include "text.hpp"
#include "util.hpp"

namespace omega {

// ============================================================================== ResponseHeaders
void ResponseHeaders::set(std::string_view name, std::string value) {
    for (auto& item : items_) {
        if (item.first == name) {
            item.second = std::move(value);
            return;
        }
    }
    items_.emplace_back(std::string(name), std::move(value));
}

void ResponseHeaders::set_default(std::string_view name, std::string value) {
    if (find(name) == nullptr) items_.emplace_back(std::string(name), std::move(value));
}

const std::string* ResponseHeaders::find(std::string_view name) const {
    for (const auto& item : items_) {
        if (item.first == name) return &item.second;
    }
    return nullptr;
}

void ResponseHeaders::erase(std::string_view name) {
    items_.erase(std::remove_if(items_.begin(), items_.end(), [&](const auto& item) { return item.first == name; }),
                 items_.end());
}

namespace {

bool ascii_iequals(std::string_view a, std::string_view b) {
    if (a.size() != b.size()) return false;
    for (std::size_t i = 0; i < a.size(); ++i) {
        char x = a[i], y = b[i];
        if (x >= 'A' && x <= 'Z') x = static_cast<char>(x - 'A' + 'a');
        if (y >= 'A' && y <= 'Z') y = static_cast<char>(y - 'A' + 'a');
        if (x != y) return false;
    }
    return true;
}

// HttpHeaders.from_pairs : dict par nom en minuscules -> la DERNIERE valeur gagne (≠ ParsedRequestHead.header).
const std::string* last_header(const RequestHead& head, std::string_view name) {
    for (auto it = head.headers.rbegin(); it != head.headers.rend(); ++it) {
        if (ascii_iequals(it->first, name)) return &it->second;
    }
    return nullptr;
}

std::string join(const std::vector<std::string>& items, std::string_view sep) {
    std::string out;
    for (std::size_t i = 0; i < items.size(); ++i) {
        if (i) out += sep;
        out += items[i];
    }
    return out;
}

Response method_not_allowed(std::string allow) {
    Response response;
    response.status = 405;
    response.headers.set("Allow", std::move(allow));
    return response;
}

Response empty_response(int status) {
    Response response;
    response.status = status;
    return response;
}

// zone_resolver.resolve_zone sur une liste de prefixes : indice, -1 si aucune.
int zone_index(std::string_view path, const std::vector<std::string>& prefixes) { return resolve_zone_index(path, prefixes); }

// access_rule.py : regles candidates (extensions) puis plus long prefixe ; nullptr = aucune.
const AccessRule* matching_access_rule(std::string_view path, const std::vector<AccessRule>& rules) {
    if (rules.empty()) return nullptr;
    const std::string lower_path = py_lower(path);
    std::vector<const AccessRule*> applicable;
    std::vector<std::string> prefixes;
    for (const AccessRule& rule : rules) {
        bool candidate = rule.extensions.empty();
        for (const std::string& ext : rule.extensions) {
            const std::string lower_ext = py_lower(ext);
            if (lower_path.size() >= lower_ext.size() &&
                lower_path.compare(lower_path.size() - lower_ext.size(), lower_ext.size(), lower_ext) == 0) {
                candidate = true;
                break;
            }
        }
        if (candidate) {
            applicable.push_back(&rule);
            prefixes.push_back(rule.prefix);
        }
    }
    const int index = zone_index(path, prefixes);
    return index < 0 ? nullptr : applicable[static_cast<std::size_t>(index)];
}

bool explicit_allow(const Snapshot& snapshot, std::string_view path) {
    if (!snapshot.access_rules) return false;
    const AccessRule* rule = matching_access_rule(path, *snapshot.access_rules);
    return rule != nullptr && rule->allow;
}

// ---------------------------------------------------------------------------------- systeme de fichiers
struct PathInfo {
    bool is_file = false;
    bool is_dir = false;
    std::uint64_t size = 0;
    double mtime = 0;  // st_mtime de Python : sec + nsec * 1e-9 (double)
};

std::optional<PathInfo> path_info(const std::string& path) {
    struct stat st {};
    if (::stat(path.c_str(), &st) != 0) return std::nullopt;
    PathInfo info;
    info.is_file = S_ISREG(st.st_mode);
    info.is_dir = S_ISDIR(st.st_mode);
    info.size = static_cast<std::uint64_t>(st.st_size);
    info.mtime = static_cast<double>(st.st_mtim.tv_sec) + static_cast<double>(st.st_mtim.tv_nsec) * 1e-9;
    return info;
}

std::int64_t int_mtime(double mtime) { return static_cast<std::int64_t>(mtime); }  // int(float) : vers zero

bool read_file(const std::string& path, std::string& out) {
    const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (fd < 0) return false;
    out.clear();
    char buffer[65536];
    while (true) {
        const ssize_t n = ::read(fd, buffer, sizeof buffer);
        if (n < 0) {
            if (errno == EINTR) continue;
            ::close(fd);
            return false;
        }
        if (n == 0) break;
        out.append(buffer, static_cast<std::size_t>(n));
    }
    ::close(fd);
    return true;
}

bool is_regular_file(const std::string& path) {
    const auto info = path_info(path);
    return info && info->is_file;
}

std::string path_join(std::string_view base, std::string_view name) {
    if (!base.empty() && base.back() == '/') return std::string(base) + std::string(name);
    return std::string(base) + "/" + std::string(name);
}

std::string_view path_name(std::string_view path) {
    const std::size_t slash = path.rfind('/');
    return slash == std::string_view::npos ? path : path.substr(slash + 1);
}

std::string path_parent(std::string_view path) {
    const std::size_t slash = path.rfind('/');
    if (slash == std::string_view::npos) return ".";
    if (slash == 0) return "/";
    return std::string(path.substr(0, slash));
}

// ------------------------------------------------------------------------- variantes .br / .gz absentes
// serve_static_file.py::_absent_variants : absences retenues 2 s, 4 096 entrees au plus (par fil ici,
// par processus en Python : seul le delai d'apparition d'un nouveau fichier en depend).
struct AbsentVariants {
    std::unordered_map<std::string, std::chrono::steady_clock::time_point> until;

    bool known_absent(const std::string& candidate, std::chrono::steady_clock::time_point now) {
        auto it = until.find(candidate);
        if (it == until.end()) return false;
        if (now < it->second) return true;
        until.erase(it);
        return false;
    }
    void remember(const std::string& candidate, std::chrono::steady_clock::time_point now) {
        if (until.size() >= 4096) until.clear();
        until[candidate] = now + std::chrono::seconds(2);
    }
};
thread_local AbsentVariants absent_variants;

struct Variant {
    std::string encoding;
    std::string path;
    PathInfo info;
};

std::optional<Variant> precompressed_variant(const Request& request, const std::string& original, double original_mtime) {
    const auto now = std::chrono::steady_clock::now();
    for (const auto& [encoding, suffix] : preferred_encodings(request.header("accept-encoding"))) {
        const std::string candidate = original + suffix;
        if (absent_variants.known_absent(candidate, now)) continue;
        const auto info = path_info(candidate);
        if (!info || !info->is_file) {
            absent_variants.remember(candidate, now);
            continue;
        }
        if (path_parent(real_path(candidate)) != path_parent(original)) continue;
        if (info->mtime < original_mtime) continue;
        return Variant{encoding, candidate, *info};
    }
    return std::nullopt;
}

constexpr std::uint64_t kStreamThreshold = 256 * 1024;  // STREAM_THRESHOLD_BYTES

Response serve_static_file(const Snapshot& snapshot, const Request& request, std::string_view path,
                           const std::string& real_root, bool access_override, std::string_view display_path) {
    const std::string& method = request.head->method;
    if (method != "GET" && method != "HEAD") return method_not_allowed("GET, HEAD");

    const PathDecision decision = normalize_uri_path_utf8(path);
    if (decision.status != 0) return empty_response(decision.status);
    std::string target = resolve_real_path_under(real_root, decision.segments);
    {
        // safe_path_resolver.py : real != root and not real.startswith(root.rstrip("/") + "/")
        std::string root_slash = real_root;
        while (!root_slash.empty() && root_slash.back() == '/') root_slash.pop_back();
        root_slash += '/';
        if (target != real_root && target.compare(0, root_slash.size(), root_slash) != 0) return empty_response(403);
    }
    if (!access_override && is_denied_path(decision.segments, snapshot.deny)) return empty_response(403);

    auto info = path_info(target);
    if (info && info->is_dir) {
        bool found = false;
        for (const std::string& index_name : snapshot.server.index_files) {
            const std::string candidate = path_join(target, index_name);
            const auto candidate_info = path_info(candidate);
            if (candidate_info && candidate_info->is_file) {
                target = candidate;
                info = candidate_info;
                found = true;
                break;
            }
        }
        if (!found) {
            if (zone_index(display_path, snapshot.dirlisting_zones) >= 0) {
                Response response;
                response.needs_python = true;  // listing de repertoire : lot 5
                return response;
            }
            return empty_response(404);
        }
    }
    if (!info || !info->is_file) return empty_response(404);

    Response response;
    response.status = 200;
    const std::string name(path_name(target));
    response.headers.set("Content-Type", guess_mime_type(name));
    if (snapshot.cache) response.headers.set("Cache-Control", resolve_cache_control(display_path, name, *snapshot.cache));

    std::uint64_t size = info->size;
    double mtime = info->mtime;
    std::string etag = make_etag(size, int_mtime(mtime));
    if (is_compressible(name)) {
        response.headers.set("Vary", "Accept-Encoding");
        if (auto variant = precompressed_variant(request, target, mtime)) {
            target = variant->path;
            size = variant->info.size;
            mtime = variant->info.mtime;
            etag = make_etag(size, int_mtime(mtime));
            etag.pop_back();
            etag += "-" + variant->encoding + "\"";
            response.headers.set("Content-Encoding", variant->encoding);
        }
    }
    response.headers.set("ETag", etag);
    response.headers.set("Last-Modified", http_date(int_mtime(mtime)));
    response.headers.set("Accept-Ranges", "bytes");

    if (is_not_modified(request.header("if-none-match"), request.header("if-modified-since"), etag, int_mtime(mtime))) {
        response.status = 304;
        return response;
    }
    if (method == "HEAD") {
        response.headers.set("Content-Length", std::to_string(size));
        return response;
    }
    const RangeDecision range = resolve_range(request.header("range"), request.header("if-range"), size, etag, int_mtime(mtime));
    if (range.unsatisfiable) {
        response.status = 416;
        response.headers.set("Content-Range", "bytes */" + std::to_string(size));
        return response;
    }
    std::uint64_t start = 0, length = size;
    if (range.partial) {
        start = range.start;
        length = range.end - range.start + 1;
        response.status = 206;
        response.headers.set("Content-Range",
                             "bytes " + std::to_string(start) + "-" + std::to_string(range.end) + "/" + std::to_string(size));
    }
    if (size > kStreamThreshold) {
        response.body_file = target;
        response.body_file_offset = start;
        response.body_file_length = length;
    } else {
        std::string content;
        if (!read_file(target, content)) {
            Response abort;
            abort.abort_connection = true;  // OSError non rattrapee cote Python
            return abort;
        }
        if (start < content.size()) response.body = content.substr(static_cast<std::size_t>(start), static_cast<std::size_t>(length));
    }
    response.headers.set("Content-Length", std::to_string(length));
    return response;
}

Response fixed_asset(const std::string& method, const std::string& content_type, const std::string& body) {
    if (method != "GET" && method != "HEAD") return method_not_allowed("GET, HEAD");
    Response response;
    response.headers.set("Content-Type", content_type);
    response.headers.set("Cache-Control", "public, max-age=86400");
    response.headers.set("Content-Length", std::to_string(body.size()));
    if (method == "GET") response.body = body;
    return response;
}

bool starts_with(std::string_view text, std::string_view prefix) { return text.substr(0, prefix.size()) == prefix; }

struct RewriteOutcome {
    std::string path;
    bool loop = false;
};

// rewrite.py::apply_rewrites
RewriteOutcome apply_rewrites(const std::string& path, const std::vector<RewriteRule>& rules) {
    std::string current = path;
    std::set<std::string> seen{current};
    for (int i = 0; i < 10; ++i) {  // MAX_REWRITE_ITERATIONS
        const RewriteRule* matched = nullptr;
        for (const RewriteRule& rule : rules) {
            if (path_matches_prefix(current, rule.match_prefix)) {
                matched = &rule;
                break;
            }
        }
        if (matched == nullptr) return {current, false};
        current = matched->replacement_prefix + std::string(utf8_skip(current, utf8_length(matched->match_prefix)));
        if (seen.count(current)) return {path, true};
        seen.insert(current);
    }
    return {path, true};
}

}  // namespace

// ================================================================================ requete
const std::string* Request::header(std::string_view name) const { return last_header(*head, name); }

AbsoluteForm absolute_form_parts(std::string_view target) {
    AbsoluteForm result;
    std::size_t scheme = 0;
    if (target.size() >= 7 && ascii_iequals(target.substr(0, 7), "http://")) scheme = 7;
    else if (target.size() >= 8 && ascii_iequals(target.substr(0, 8), "https://")) scheme = 8;
    else return result;
    const std::string_view rest = target.substr(scheme);
    const std::size_t end = std::min(rest.find_first_of("/?"), rest.size());
    const std::string_view host = rest.substr(0, end);
    const bool bad_char = std::any_of(host.begin(), host.end(), [](char ch) {
        const auto c = static_cast<unsigned char>(ch);
        return c == '@' || c <= 0x20 || c == 0x7F;
    });
    if (host.empty() || bad_char) {
        result.kind = AbsoluteForm::invalid;
        return result;
    }
    result.kind = AbsoluteForm::valid;
    result.host.assign(host);
    const std::string_view origin = rest.substr(end);
    result.origin = (origin.empty() || origin.front() != '/') ? "/" + std::string(origin) : std::string(origin);
    return result;
}

void fill_request_target(Request& request) {
    const std::string& target = request.head->target;
    const AbsoluteForm absolute = absolute_form_parts(target);
    request.absolute_target_invalid = absolute.kind == AbsoluteForm::invalid;
    const std::string_view effective = absolute.kind == AbsoluteForm::valid ? std::string_view(absolute.origin) : std::string_view(target);
    const std::size_t question = effective.find('?');
    request.path_text = latin1_to_utf8(effective.substr(0, question));
    request.query_text = question == std::string_view::npos ? std::string() : latin1_to_utf8(effective.substr(question + 1));
    request.target_text = latin1_to_utf8(target);
}

std::string resolve_remote_ip(const Snapshot& snapshot, std::string_view peer_ip, const RequestHead& head) {
    if (!snapshot.trusted_networks) return normalize_ip(peer_ip);
    std::vector<std::string> converted;  // valeurs en texte (latin-1 -> UTF-8), stables pendant l'appel
    converted.reserve(head.headers.size());
    auto lookup = [&](const std::string& name) -> const std::string* {
        const std::string* raw = last_header(head, name);
        if (raw == nullptr) return nullptr;
        converted.push_back(latin1_to_utf8(*raw));
        return &converted.back();
    };
    return resolve_client_ip(peer_ip, lookup, *snapshot.trusted_networks, snapshot.header_preference);
}

std::optional<EarlyOutcome> check_before_body(const Snapshot& snapshot, const Request& request) {
    const RequestHead& head = *request.head;
    if (snapshot.require_valid_host) {
        std::vector<const std::string*> hosts;
        for (const auto& [name, value] : head.headers) {
            if (ascii_iequals(name, "host")) hosts.push_back(&value);
        }
        std::string reason;
        if (hosts.empty()) {
            reason = "Host manquant";
        } else if (hosts.size() > 1) {
            reason = "Host dupliqué (ambigu)";
        } else if (hosts[0]->empty()) {
            reason = "Host vide";
        } else if (std::any_of(hosts[0]->begin(), hosts[0]->end(),
                               [](char c) { return is_control_character(static_cast<unsigned char>(c)); })) {
            reason = "Host contient un caractère de contrôle";
        }
        if (!reason.empty()) {
            EarlyOutcome outcome;
            outcome.response = error_response(400);
            outcome.is_error_response = true;
            outcome.error_log_message = "Host invalide : " + reason;
            return outcome;
        }
    }
    if (request.absolute_target_invalid) {
        EarlyOutcome outcome;
        outcome.response = error_response(400);
        outcome.is_error_response = true;
        outcome.error_log_message = "cible de requête absolue invalide";
        return outcome;
    }
    if (std::find(snapshot.allowed_methods.begin(), snapshot.allowed_methods.end(), latin1_to_utf8(head.method)) ==
        snapshot.allowed_methods.end()) {
        EarlyOutcome outcome;
        outcome.response = method_not_allowed(join(snapshot.allowed_methods, ", "));
        return outcome;
    }
    if (snapshot.access_rules) {
        const AccessRule* rule = matching_access_rule(request.path_text, *snapshot.access_rules);
        if (rule != nullptr && !rule->allow) {
            EarlyOutcome outcome;
            outcome.response = empty_response(403);
            apply_security_headers(outcome.response, snapshot, request.path_text);
            return outcome;
        }
    }
    return std::nullopt;
}

bool wants_handoff(const Snapshot& snapshot, const Request& request) {
    if (!snapshot.inspect) return false;
    const InspectSettings& settings = *snapshot.inspect;
    if (settings.handoff_any.empty() && settings.handoff_post.empty()) return false;
    std::vector<std::string> paths{request.path_text};
    if (snapshot.rewrites) paths.push_back(apply_rewrites(request.path_text, *snapshot.rewrites).path);
    const bool is_post = request.head->method == "POST";
    for (const std::string& path : paths) {
        for (const std::string& prefix : settings.handoff_any) {
            if (starts_with(path, prefix)) return true;
        }
        if (is_post) {
            for (const std::string& prefix : settings.handoff_post) {
                if (starts_with(path, prefix)) return true;
            }
        }
    }
    return false;
}

Response route_request(const Snapshot& snapshot, const Request& request) {
    const std::string& path = request.path_text;
    const std::string& method = request.head->method;
    const InternalAssets& internal = snapshot.internal;

    if (path == "/healthz") {
        if (method != "GET" && method != "HEAD") return method_not_allowed("GET, HEAD");
        Response response;
        response.headers.set("Content-Type", "text/plain; charset=utf-8");
        response.headers.set("Content-Length", "2");
        if (method == "GET") response.body = "OK";
        return response;
    }
    if (starts_with(path, internal.icon_prefix)) {
        if (method != "GET" && method != "HEAD") return method_not_allowed("GET, HEAD");
        const auto it = internal.icons.find(path.substr(internal.icon_prefix.size()));
        if (it == internal.icons.end()) return empty_response(404);
        Response response;
        response.headers.set("Content-Type", "image/svg+xml");
        response.headers.set("Cache-Control", "public, max-age=86400");
        if (method == "GET") response.body = it->second;
        response.headers.set("Content-Length", std::to_string(it->second.size()));
        return response;
    }
    if (starts_with(path, internal.dirlisting_css_prefix)) {
        std::string theme = path.substr(internal.dirlisting_css_prefix.size());
        if (theme.size() >= 4 && theme.compare(theme.size() - 4, 4, ".css") == 0) theme.resize(theme.size() - 4);
        const auto it = internal.dirlisting_css.find(theme);
        return fixed_asset(method, "text/css; charset=utf-8",
                           it == internal.dirlisting_css.end() ? internal.dirlisting_css_fallback : it->second);
    }
    if (starts_with(path, internal.error_css_prefix)) {
        if (path.substr(internal.error_css_prefix.size()) != internal.error_css_name) return empty_response(404);
        return fixed_asset(method, "text/css; charset=utf-8", internal.error_css);
    }
    if (starts_with(path, internal.load_prefix) || starts_with(path, internal.admin_prefix)) {
        if (!is_trusted_proxy(request.peer_ip, snapshot.trusted_networks_for_internal)) return empty_response(403);
        Response response;
        response.needs_python = true;
        return response;
    }
    if (snapshot.redirects) {
        std::vector<std::string> prefixes;
        for (const RedirectRule& rule : *snapshot.redirects) prefixes.push_back(rule.prefix);
        const int index = zone_index(path, prefixes);
        if (index >= 0) {
            const RedirectRule& rule = (*snapshot.redirects)[static_cast<std::size_t>(index)];
            Response response = empty_response(rule.status);
            response.headers.set("Location", rule.destination);
            return response;
        }
    }
    std::string effective_path = path;
    if (snapshot.rewrites) {
        const RewriteOutcome outcome = apply_rewrites(effective_path, *snapshot.rewrites);
        if (outcome.loop) return empty_response(500);
        effective_path = outcome.path;
    }
    if (snapshot.aliases) {
        std::vector<std::string> prefixes;
        for (const AliasRule& rule : *snapshot.aliases) prefixes.push_back(rule.prefix);
        const int index = zone_index(effective_path, prefixes);
        if (index >= 0) {
            const AliasRule& rule = (*snapshot.aliases)[static_cast<std::size_t>(index)];
            std::string_view remaining = utf8_skip(effective_path, utf8_length(rule.prefix));
            while (!remaining.empty() && remaining.front() == '/') remaining.remove_prefix(1);
            const std::string alias_path = "/" + std::string(remaining);
            return serve_static_file(snapshot, request, alias_path, real_path(rule.root),
                                     explicit_allow(snapshot, effective_path), effective_path);
        }
    }
    return serve_static_file(snapshot, request, effective_path, snapshot.server.webroot,
                             explicit_allow(snapshot, effective_path), effective_path);
}

void apply_security_headers(Response& response, const Snapshot& snapshot, std::string_view path_text) {
    if (!snapshot.security_headers) return;
    const SecurityHeaders& headers = *snapshot.security_headers;
    for (const auto& [name, value] : headers.ordered) {
        if (name == headers.csp_header && !headers.csp_zone_prefixes.empty()) {
            const int index = zone_index(path_text, headers.csp_zone_prefixes);
            response.headers.set(name, index >= 0 ? headers.csp_zone_policies[static_cast<std::size_t>(index)] : value);
        } else {
            response.headers.set(name, value);
        }
    }
}

Response error_response(int status) { return empty_response(status); }

namespace {

std::string error_page_body(const Snapshot& snapshot, int status) {
    if (snapshot.error_custom_dir) {
        const std::string code = std::to_string(status);
        for (const std::string& name : {code + "-" + snapshot.page_lang + ".html", code + ".html"}) {
            const std::string candidate = path_join(*snapshot.error_custom_dir, name);
            std::string content;
            if (is_regular_file(candidate) && read_file(candidate, content)) return content;
        }
    }
    const auto it = snapshot.default_error_pages.find(status);
    return it == snapshot.default_error_pages.end() ? std::string() : it->second;
}

}  // namespace

std::optional<std::string> finalize_response(const Snapshot& snapshot, Response& response, bool keep_alive) {
    if (response.body.empty() && response.status >= 400) {
        response.body = error_page_body(snapshot, response.status);
        response.headers.set_default("Content-Type", "text/html; charset=utf-8");
        for (const char* csp_name : {"Content-Security-Policy", "Content-Security-Policy-Report-Only"}) {
            if (const std::string* policy = response.headers.find(csp_name)) {
                response.headers.set(csp_name, allow_inline_styles_by_hash(*policy, response.body));
            }
        }
    }
    response.headers.set_default("Connection", keep_alive ? "keep-alive" : "close");
    if (response.status == 304) {
        response.headers.erase("Content-Length");
        response.body.clear();
    } else {
        response.headers.set_default("Content-Length", std::to_string(response.content_length()));
    }
    const auto reason = snapshot.reason_phrases.find(response.status);
    std::string head = "HTTP/1.1 " + std::to_string(response.status) + " " +
                       (reason == snapshot.reason_phrases.end() ? std::string() : reason->second) + "\r\n";
    for (const auto& [name, value] : response.headers.items()) head += name + ": " + value + "\r\n";
    head += "\r\n";
    return utf8_to_latin1(head);
}

// ================================================================================== journaux
namespace {

std::string apache_timestamp(std::int64_t unix_seconds) {
    static constexpr const char* months[] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
    const std::time_t t = static_cast<std::time_t>(unix_seconds);
    std::tm tm{};
    gmtime_r(&t, &tm);
    char buffer[64];
    std::snprintf(buffer, sizeof buffer, "%02d/%s/%04d:%02d:%02d:%02d +0000", tm.tm_mday, months[tm.tm_mon],
                  tm.tm_year + 1900, tm.tm_hour, tm.tm_min, tm.tm_sec);
    return buffer;
}

}  // namespace

namespace {
// access_log_format.py::_quoted_field : guillemet d'un champ client -> \x22 (comme nginx), apres assainissement.
std::string quoted_field(std::string value) {
    std::string out;
    out.reserve(value.size());
    for (char ch : value) {
        if (ch == '"') out += "\\x22";
        else out.push_back(ch);
    }
    return out;
}
}  // namespace

std::string format_access_line(const Request& request, const Response& response, std::int64_t unix_seconds) {
    const std::string request_line = request.unparsed ? request.raw_request_line_text
                                                      : latin1_to_utf8(request.head->method) + " " + request.target_text + " HTTP/1.1";
    const std::string* referer = request.header("referer");
    const std::string* user_agent = request.header("user-agent");
    const std::uint64_t size = response.content_length();
    std::string line;
    line += sanitize_log_field(request.remote_ip, 64);
    line += " - - [" + apache_timestamp(unix_seconds) + "] \"";
    line += quoted_field(sanitize_log_field(request_line, 2048));
    line += "\" " + std::to_string(response.status) + " " + (size ? std::to_string(size) : std::string("-")) + " \"";
    line += quoted_field(sanitize_log_field(referer && !referer->empty() ? latin1_to_utf8(*referer) : std::string("-"), 512));
    line += "\" \"";
    line += quoted_field(sanitize_log_field(user_agent && !user_agent->empty() ? latin1_to_utf8(*user_agent) : std::string("-"), 256));
    line += "\" " + sanitize_log_field(request.request_id, 64);
    return line;
}

std::string format_error_line(std::string_view message, std::string_view request_id, std::int64_t unix_seconds) {
    const std::time_t t = static_cast<std::time_t>(unix_seconds);
    std::tm tm{};
    gmtime_r(&t, &tm);
    char stamp[64];
    std::snprintf(stamp, sizeof stamp, "%04d-%02d-%02d %02d:%02d:%02d", tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday,
                  tm.tm_hour, tm.tm_min, tm.tm_sec);
    std::string line = "[" + std::string(stamp) + "] " + sanitize_log_field(message, 2048);
    if (!request_id.empty()) line += " [" + sanitize_log_field(request_id, 64) + "]";
    return line;
}

// ===================================================================================== CSP
namespace {

bool is_word_byte(unsigned char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_'; }
bool is_regex_space(unsigned char c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v'; }

bool iequals_at(std::string_view text, std::size_t pos, std::string_view word) {
    if (pos + word.size() > text.size()) return false;
    return ascii_iequals(text.substr(pos, word.size()), word);
}

// re.findall(rb"<style\b[^>]*>(.*?)</style\s*>", html, re.IGNORECASE | re.DOTALL)
std::vector<std::string_view> inline_style_blocks(std::string_view html) {
    std::vector<std::string_view> blocks;
    std::size_t pos = 0;
    while (pos < html.size()) {
        if (!iequals_at(html, pos, "<style")) {
            ++pos;
            continue;
        }
        const std::size_t after = pos + 6;
        if (after < html.size() && is_word_byte(static_cast<unsigned char>(html[after]))) {
            ++pos;
            continue;
        }
        const std::size_t close_angle = html.find('>', after);
        if (close_angle == std::string_view::npos) {
            ++pos;  // [^>]* sans '>' : aucune correspondance a cette position
            continue;
        }
        const std::size_t content_start = close_angle + 1;
        std::size_t end_tag = std::string_view::npos, match_end = 0;
        for (std::size_t j = content_start; j < html.size(); ++j) {
            if (!iequals_at(html, j, "</style")) continue;
            std::size_t k = j + 7;
            while (k < html.size() && is_regex_space(static_cast<unsigned char>(html[k]))) ++k;
            if (k < html.size() && html[k] == '>') {
                end_tag = j;
                match_end = k + 1;
                break;
            }
        }
        if (end_tag == std::string_view::npos) {
            ++pos;
            continue;
        }
        blocks.push_back(html.substr(content_start, end_tag - content_start));
        pos = match_end;
    }
    return blocks;
}

}  // namespace

std::string allow_inline_styles_by_hash(std::string_view policy, std::string_view html) {
    const auto blocks = inline_style_blocks(html);
    if (blocks.empty()) return std::string(policy);
    // parse_csp_directives : dict (ordre d'insertion ; une directive repetee garde sa premiere place)
    std::vector<std::pair<std::string, std::string>> directives;
    std::size_t start = 0;
    while (start <= policy.size()) {
        std::size_t end = policy.find(';', start);
        if (end == std::string_view::npos) end = policy.size();
        const std::string_view directive = py_strip(policy.substr(start, end - start));
        start = end + 1;
        if (!directive.empty()) {
            const std::size_t space = directive.find(' ');
            const std::string name(directive.substr(0, space));
            const std::string values(space == std::string_view::npos ? std::string_view{} : py_strip(directive.substr(space + 1)));
            auto it = std::find_if(directives.begin(), directives.end(), [&](const auto& d) { return d.first == name; });
            if (it == directives.end()) directives.emplace_back(name, values);
            else it->second = values;
        }
        if (end == policy.size()) break;
    }
    auto find = [&](std::string_view name) {
        return std::find_if(directives.begin(), directives.end(), [&](const auto& d) { return d.first == name; });
    };
    const std::string_view name = find("style-src") != directives.end() ? "style-src" : "default-src";
    const auto source = find(name);
    if (source == directives.end()) return std::string(policy);
    std::vector<std::string> tokens;
    for (std::string_view token : py_split_whitespace(source->second)) tokens.emplace_back(token);
    if (std::find(tokens.begin(), tokens.end(), "'none'") != tokens.end() ||
        std::find(tokens.begin(), tokens.end(), "'unsafe-inline'") != tokens.end()) {
        return std::string(policy);
    }
    for (std::string_view block : blocks) {
        const auto digest = sha256(block);
        const std::string token = "'sha256-" + base64_encode(digest.data(), digest.size()) + "'";
        if (std::find(tokens.begin(), tokens.end(), token) == tokens.end()) tokens.push_back(token);
    }
    std::string joined;
    for (std::size_t i = 0; i < tokens.size(); ++i) joined += (i ? " " : "") + tokens[i];
    if (auto style = find("style-src"); style != directives.end()) style->second = joined;
    else directives.emplace_back("style-src", joined);
    std::string out;
    for (std::size_t i = 0; i < directives.size(); ++i) {
        if (i) out += "; ";
        out += std::string(py_strip(directives[i].first + " " + directives[i].second));
    }
    return out;
}

// =============================================================================== chemins reels
std::string real_path(std::string_view filename) {
    // posixpath.realpath(strict=False), Python 3.14
    struct Part {
        std::string name;
        bool marker = false;  // None : cible d'un lien resolue, le chemin du lien suit
    };
    std::vector<Part> rest;
    auto push_reversed = [&](std::string_view text) -> std::size_t {
        std::vector<std::string> parts;
        std::size_t start = 0;
        while (true) {
            const std::size_t slash = text.find('/', start);
            parts.emplace_back(text.substr(start, slash == std::string_view::npos ? std::string_view::npos : slash - start));
            if (slash == std::string_view::npos) break;
            start = slash + 1;
        }
        for (auto it = parts.rbegin(); it != parts.rend(); ++it) rest.push_back({*it, false});
        return parts.size();
    };
    std::size_t part_count = push_reversed(filename);
    std::string path;
    if (!filename.empty() && filename[0] == '/') {
        path = "/";
    } else {
        char cwd[4096];
        path = ::getcwd(cwd, sizeof cwd) ? cwd : "/";
    }
    std::map<std::string, std::optional<std::string>> seen;
    while (part_count > 0) {
        Part part = std::move(rest.back());
        rest.pop_back();
        if (part.marker) {
            Part link = std::move(rest.back());
            rest.pop_back();
            seen[link.name] = path;
            continue;
        }
        --part_count;
        const std::string& name = part.name;
        if (name.empty() || name == ".") continue;
        if (name == "..") {
            const std::size_t slash = path.rfind('/');
            path = slash == 0 || slash == std::string::npos ? "/" : path.substr(0, slash);
            continue;
        }
        const std::string newpath = path == "/" ? path + name : path + "/" + name;
        struct stat st {};
        if (::lstat(newpath.c_str(), &st) != 0) {
            path = newpath;  // OSError ignoree (non strict)
            continue;
        }
        if (!S_ISLNK(st.st_mode)) {
            path = newpath;
            continue;
        }
        if (auto it = seen.find(newpath); it != seen.end()) {
            if (it->second) {
                path = *it->second;
                continue;
            }
            path = newpath;  // boucle de liens (non strict)
            continue;
        }
        char target_buffer[4096];
        const ssize_t length = ::readlink(newpath.c_str(), target_buffer, sizeof target_buffer);
        if (length < 0) {
            path = newpath;
            continue;
        }
        const std::string target(target_buffer, static_cast<std::size_t>(length));
        if (!target.empty() && target[0] == '/') path = "/";
        seen[newpath] = std::nullopt;
        rest.push_back({newpath, false});
        rest.push_back({std::string(), true});
        part_count += push_reversed(target);
    }
    return path;
}

std::string resolve_real_path_under(const std::string& real_root, const std::vector<std::string>& segments) {
    std::string current = real_root;
    auto joined_all = [&]() {
        std::string full = real_root;
        for (const std::string& segment : segments) full = path_join(full, segment);
        return full;
    };
    for (std::size_t index = 0; index < segments.size(); ++index) {
        current = path_join(current, segments[index]);
        struct stat st {};
        if (::lstat(current.c_str(), &st) != 0) {
            if (errno == ENOENT) {
                for (std::size_t rest = index + 1; rest < segments.size(); ++rest) current = path_join(current, segments[rest]);
                return current;
            }
            return real_path(joined_all());
        }
        if (S_ISLNK(st.st_mode)) return real_path(joined_all());
    }
    return current;
}

}  // namespace omega

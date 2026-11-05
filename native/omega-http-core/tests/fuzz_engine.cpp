// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Fuzzing du pipeline complet d'une requete (libFuzzer + ASan/UBSan) : parseur, IP client, Host / methode /
// regles d'acces, cadrage du corps, routage (redirections, reecritures en boucle, alias, statique, liens
// symboliques), en-tetes de securite, page d'erreur avec empreinte CSP, ligne de journal.
// Webroot de test cree une fois dans un dossier temporaire.
#include <sys/stat.h>
#include <unistd.h>

#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <memory>
#include <string>

#include "config.hpp"
#include "engine.hpp"
#include "http_parser.hpp"

namespace {

std::string make_webroot() {
    char pattern[] = "/tmp/omega-fuzz-XXXXXX";
    const char* dir = ::mkdtemp(pattern);
    if (dir == nullptr) std::abort();
    const std::string root = dir;
    ::mkdir((root + "/web").c_str(), 0755);
    ::mkdir((root + "/web/docs").c_str(), 0755);
    ::mkdir((root + "/web/.errors").c_str(), 0755);
    std::ofstream(root + "/web/index.html") << "<p>accueil</p>";
    std::ofstream(root + "/web/docs/a.txt") << "a";
    std::ofstream(root + "/web/style.css") << "b{}";
    std::ofstream(root + "/web/style.css.gz") << "gz";
    std::ofstream(root + "/web/.errors/404.html") << "<style>x{}</style>";
    (void)::symlink("docs", (root + "/web/lien").c_str());
    (void)::symlink("../..", (root + "/web/sortie").c_str());
    (void)::symlink("boucle", (root + "/web/boucle").c_str());
    return root;
}

std::shared_ptr<const omega::Snapshot> snapshot() {
    static std::shared_ptr<const omega::Snapshot> cached = [] {
        const std::string root = make_webroot();
        const std::string json = R"({"format":1,"generation":1,
"server":{"bind":"127.0.0.1","port":1,"listen_backlog":8,"max_connections":8,"max_request_size":1000,
 "max_header_size":4096,"max_request_line_size":2048,"read_timeout_seconds":1,"keepalive_timeout_seconds":1,
 "max_keepalive_requests":3,"shutdown_grace_period_seconds":1,"index_files":["index.html"],"webroot":")" + root + R"(/web"},
"security":{"require_valid_host":true,"allowed_methods":["GET","HEAD","POST"],"deny_hidden_files":true,
 "deny_sensitive_extensions":[".bak"],"deny_patterns":["~"],
 "headers":{"ordered":[["X-Content-Type-Options","nosniff"],["Content-Security-Policy","default-src 'none'; style-src 'self'"]],
  "csp_header":"Content-Security-Policy","csp_zones":[["/docs","style-src 'unsafe-inline'"]]}},
"routes":{"trusted_proxy":{"networks":["127.0.0.1","10.0.0.0/8","::1"],"header_preference":["Forwarded","X-Forwarded-For"]},
 "access_rules":{"list":[{"path_prefix":"/private","verdict":"deny","extensions":[]},{"path_prefix":"/.ok","verdict":"allow","extensions":[".css"]}]},
 "redirects":{"list":[{"url_prefix":"/old/","destination":"/né","status_code":301},{"url_prefix":"/x","destination":"/日","status_code":302}]},
 "rewrites":{"list":[{"match_prefix":"/a","replacement_prefix":"/b"},{"match_prefix":"/b","replacement_prefix":"/a"},
  {"match_prefix":"/ré","replacement_prefix":"/docs/日"}]},
 "aliases":{"list":[{"url_prefix":"/al//","root":")" + root + R"(/web/docs"}]},
 "cache":{"default":"no-cache","zones":[["/docs","max-age=1"]],"extensions":[[".css","max-age=2"]]},
 "dirlisting":{"zone_prefixes":["/docs"]}},
"error_pages":{"custom_dir":")" + root + R"(/web/.errors","page_lang":"fr","defaults":{"400":"<style>e</style>","404":"n"},
 "reason_phrases":{"200":"OK","400":"Bad Request","404":"Not Found"}},
"internal":{"icon_prefix":"/.i/","icons":{"a.svg":"<svg/>"},"dirlisting_css_prefix":"/.c/","dirlisting_css":{"t":"c"},
 "dirlisting_css_fallback":"f","error_css_prefix":"/.e/","error_css_name":"e.css","error_css":"e",
 "load_prefix":"/.l/","admin_prefix":"/.adm/"},
"logs":{"access":")" + root + R"(/access.log","error":")" + root + R"(/error.log"},
"inspect":null,"tls":null,"waf_filter":null})";
        std::string error;
        auto parsed = omega::parse_snapshot(json, &error);
        if (!parsed) {
            std::fprintf(stderr, "instantane de fuzzing refuse : %s\n", error.c_str());
            std::abort();
        }
        return parsed;
    }();
    return cached;
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
    const auto snap = snapshot();
    const std::string_view input(reinterpret_cast<const char*>(data), size);
    // premier octet : adresse du pair (confiance ou non), le reste : la requete
    const std::string peer = size > 0 && (data[0] & 1) ? "127.0.0.1" : "203.0.113.9";
    const std::string_view wire = size > 0 ? input.substr(1) : input;
    omega::ParseResult parsed = omega::parse_request_head(wire, snap->parser_limits, (size & 2) != 0);
    if (parsed.state != omega::ParseState::complete) {
        if (parsed.state == omega::ParseState::error) {
            omega::Response response = omega::error_response(parsed.status);
            (void)omega::finalize_response(*snap, response, false);
        }
        return 0;
    }
    omega::Request request;
    request.request_id = "0123456789abcdef";
    request.peer_ip = peer;
    request.head = &parsed.head;
    omega::fill_request_target(request);
    request.remote_ip = omega::resolve_remote_ip(*snap, peer, parsed.head);
    if (auto early = omega::check_before_body(*snap, request)) {
        (void)omega::finalize_response(*snap, early->response, false);
        (void)omega::format_access_line(request, early->response, 0);
        return 0;
    }
    const omega::BodyFraming framing = omega::body_framing(parsed.head, snap->server.max_request_size);
    if (framing.status != 0) return 0;
    omega::Response response = omega::route_request(*snap, request);
    omega::apply_security_headers(response, *snap, request.path_text);
    (void)omega::finalize_response(*snap, response, true);
    (void)omega::format_access_line(request, response, 1700000000);
    return 0;
}

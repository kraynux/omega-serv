// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Plan proxy natif v2, lot 3 : lecture de l'instantane `proxy` (zones, backends, regles, delais, budgets, INSPECT par
// zone) et de inspect.security_processes. Le test differentiel avec Python (cles et valeurs) est cote pytest :
// tests/integration/test_native_proxy_snapshot.py.
#include <doctest.h>

#include <string>

#include "config.hpp"

namespace {

std::string snapshot_json(const std::string& proxy, const std::string& inspect = "null") {
    return R"({"format":1,"generation":1,
"server":{"bind":"127.0.0.1","port":1,"listen_backlog":8,"max_connections":8,"max_request_size":1000,
 "max_header_size":4096,"max_request_line_size":2048,"read_timeout_seconds":1,"keepalive_timeout_seconds":1,
 "write_timeout_seconds":1,"max_keepalive_requests":3,"shutdown_grace_period_seconds":1,"index_files":["index.html"],"webroot":"/tmp"},
"security":{"require_valid_host":true,"allowed_methods":["GET"],"deny_hidden_files":true,
 "deny_sensitive_extensions":[],"deny_patterns":[],"headers":null},
"routes":{"trusted_proxy":null,"access_rules":null,"redirects":null,"rewrites":null,"aliases":null,"cache":null,
 "dirlisting":null},
"error_pages":{"custom_dir":null,"page_lang":"fr","defaults":{},"reason_phrases":{"200":"OK"}},
"internal":{"icon_prefix":"/.i/","icons":{},"dirlisting_css_prefix":"/.c/","dirlisting_css":{},
 "dirlisting_css_fallback":"f","error_css_prefix":"/.e/","error_css_name":"e.css","error_css":"e",
 "load_prefix":"/.l/","admin_prefix":"/.adm/"},
"logs":{"access":"/tmp/a.log","error":"/tmp/e.log"},
"inspect":)" + inspect + R"(,"tls":null,"waf_filter":null,"proxy":)" + proxy + "}";
}

const std::string kUpstreamA =
    R"({"key":"10.0.0.1:8080","host":"10.0.0.1","port":8080,"host_header":"10.0.0.1:8080","address":"10.0.0.1",)"
    R"("tls":false,"weight":3,"max_concurrent":50,"load_source":"native",)"
    R"("name":"10.0.0.1:8080","cookie":"0123456789abcdef","active_check":true,"unusable":null})";
const std::string kUpstreamB =
    R"({"key":"api.example:443","host":"api.example","port":443,"host_header":"api.example:443","address":null,)"
    R"("tls":true,"weight":1,"max_concurrent":null,"load_source":"none",)"
    R"("name":"api.example:443","cookie":"fedcba9876543210","active_check":false,"unusable":"dns"})";

std::string zone(const std::string& engine, const std::string& reasons, const std::string& rules = "[]",
                 const std::string& upstreams = "[" + kUpstreamA + "," + kUpstreamB + "]",
                 const std::string& inspect = "filter") {
    return R"({"prefix":"/app/","engine":")" + engine + R"(","reasons":)" + reasons + R"(,"inspect":")" + inspect +
           R"(","connect_timeout_ms":5000,"read_timeout_ms":30000,"preserve_host":false,"verify_tls":true,)"
           R"("websocket":false,"websocket_idle_timeout_ms":3600000,"load_balancing":"weighted_round_robin",)"
           R"("sticky":{"cookie_name":"omega_proxy_sticky","max_age_seconds":7200},"routing_rules":)" + rules +
           R"(,"unhealthy_after":3,"healthy_after":2,"load_sample_max_age_ms":60000,"upstreams":)" + upstreams + "}";
}

std::string proxy(const std::string& zones, const std::string& engine = "auto") {
    return R"({"engine":")" + engine + R"(","budgets":{"pending_body_bytes":134217728,"inspections":64,)"
           R"("upstream_connections":512},"max_response_body_bytes":268435456,"zones":[)" + zones + "]}";
}

std::shared_ptr<const omega::Snapshot> parse(const std::string& json, std::string* error = nullptr) {
    std::string ignored;
    return omega::parse_snapshot(json, error != nullptr ? error : &ignored);
}

}  // namespace

TEST_CASE("instantane proxy : zones, backends, regles, delais et budgets lus tels quels") {
    const auto snapshot = parse(snapshot_json(proxy(zone("python", R"(["relay_unavailable","cache"])",
                                                         R"([{"header":"X-Tenant","pattern":"a*","upstream":"10.0.0.1:8080"}])"))));
    REQUIRE(snapshot != nullptr);
    REQUIRE(snapshot->proxy.has_value());
    const omega::ProxySettings& settings = *snapshot->proxy;
    CHECK(settings.engine == "auto");
    CHECK(settings.budgets.pending_body_bytes == 134217728u);
    CHECK(settings.budgets.inspections == 64u);
    CHECK(settings.budgets.upstream_connections == 512u);
    CHECK(settings.max_response_body_bytes == 268435456u);
    REQUIRE(settings.zones.size() == 1);
    const omega::ProxyZoneSettings& z = settings.zones[0];
    CHECK(z.prefix == "/app/");
    CHECK_FALSE(z.native);
    CHECK(z.reasons.size() == 2);
    CHECK(z.inspect == omega::ZoneInspect::filter);
    CHECK(z.connect_timeout_ms == 5000);
    CHECK(z.read_timeout_ms == 30000);
    CHECK(z.load_balancing == "weighted_round_robin");
    REQUIRE(z.sticky.has_value());
    CHECK(z.sticky->max_age_seconds == 7200);
    REQUIRE(z.routing_rules.size() == 1);
    CHECK(z.routing_rules[0].upstream == "10.0.0.1:8080");
    REQUIRE(z.upstreams.size() == 2);
    CHECK(z.upstreams[0].weight == 3);
    CHECK(z.upstreams[0].max_concurrent == 50);
    CHECK(z.upstreams[0].address == "10.0.0.1");
    CHECK_FALSE(z.upstreams[1].address.has_value());  // nom DNS : resolu par Python quand la zone sera native
    CHECK_FALSE(z.upstreams[1].max_concurrent.has_value());
    CHECK(z.upstreams[1].tls);
}

TEST_CASE("instantane proxy : null ou absent = reverse proxy inactif") {
    const auto with_null = parse(snapshot_json("null"));
    REQUIRE(with_null != nullptr);
    CHECK_FALSE(with_null->proxy.has_value());
    std::string old = snapshot_json("null");
    old.erase(old.find(R"(,"proxy":null)"), std::string(R"(,"proxy":null)").size());  // instantane d'avant le lot 3
    const auto without = parse(old);
    REQUIRE(without != nullptr);
    CHECK_FALSE(without->proxy.has_value());
}

TEST_CASE("instantane proxy : incoherences refusees, jamais une valeur devinee") {
    std::string error;
    // zone native avec des raisons, ou confiee sans raison
    CHECK(parse(snapshot_json(proxy(zone("native", R"(["cache"])"))), &error) == nullptr);
    CHECK(error.find("raisons") != std::string::npos);
    CHECK(parse(snapshot_json(proxy(zone("python", "[]")))) == nullptr);
    // regle vers un backend absent de la zone
    CHECK(parse(snapshot_json(proxy(zone("native", "[]", R"([{"header":"H","pattern":"x","upstream":"autre:1"}])"))),
                &error) == nullptr);
    CHECK(error.find("backend absent") != std::string::npos);
    // zone sans backend, INSPECT inconnu, moteur inconnu
    CHECK(parse(snapshot_json(proxy(zone("native", "[]", "[]", "[]")))) == nullptr);
    CHECK(parse(snapshot_json(proxy(zone("native", "[]", "[]", "[" + kUpstreamA + "]", "parfois")))) == nullptr);
    CHECK(parse(snapshot_json(proxy(zone("native", "[]"), "turbo"))) == nullptr);
    // budget nul
    std::string zero = proxy(zone("native", "[]"));
    zero.replace(zero.find("\"inspections\":64"), std::string("\"inspections\":64").size(), "\"inspections\":0");
    CHECK(parse(snapshot_json(zero)) == nullptr);
}

TEST_CASE("instantane proxy : sortie --dump-proxy relisible et stable") {
    const auto snapshot = parse(snapshot_json(proxy(zone("native", "[]"))));
    REQUIRE(snapshot != nullptr);
    const std::string dumped = omega::dump_proxy_json(*snapshot->proxy);
    const auto again = parse(snapshot_json(dumped));
    REQUIRE(again != nullptr);
    CHECK(omega::dump_proxy_json(*again->proxy) == dumped);
    CHECK(dumped.find(R"("engine": "native", "reasons": [])") != std::string::npos);
}

TEST_CASE("inspect.security_processes : lu, un seul processus s'il est absent (P6)") {
    const std::string base = R"({"body_methods":[],"body_bytes":0,"timeout_ms":1000,"on_error":"fail-open",)"
                             R"("security_stage":false,"blocklist":null,"handoff_any":["/app/"],"handoff_post":[])";
    const auto absent = parse(snapshot_json("null", base + "}"));
    REQUIRE(absent != nullptr);
    CHECK(absent->inspect->security_processes == 1u);
    const auto two = parse(snapshot_json("null", base + R"(,"security_processes":2})"));
    REQUIRE(two != nullptr);
    CHECK(two->inspect->security_processes == 2u);
    CHECK(parse(snapshot_json("null", base + R"(,"security_processes":0})")) == nullptr);
}

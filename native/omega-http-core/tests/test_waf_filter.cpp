// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Filtre WAF (plan WAF natif, lot 1) : decodage borne, preparation des textes, evaluation. Les vecteurs
// (tools/differential/make_waf_vectors.py) rejouent les VRAIES fonctions Python sur les regles livrees.
#include "doctest.h"

#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "engine.hpp"
#include "http_parser.hpp"
#include "util.hpp"
#include "waf_filter.hpp"

namespace {

std::shared_ptr<const omega::WafFilter> filter_from(const std::string& json) {
    std::string error;
    const auto parsed = omega::parse_json(json, &error);
    REQUIRE_MESSAGE(parsed.has_value(), error);
    return omega::WafFilter::from_json(*parsed);
}

omega::WafScopeTexts texts_with(omega::WafScope scope, const std::string& text) {
    omega::WafScopeTexts texts;
    texts[static_cast<std::size_t>(scope)] = text;
    return texts;
}

const char* kOneRule = R"({"available":true,"decode_depth":2,"inspect_path":true,"inspect_query":true,
"inspect_headers":false,"native_decides":true,"native_decides_with_watch":true,"python_reason":null,"auth_prefixes":[],"unexported":[],
"rules":[{"id":"R1","pack":"p","scopes":["query","body"],"pattern":"\\x{65}\\x{76}\\x{69}\\x{6c}","exclude":null,"lowered":true}]})";

}  // namespace

TEST_CASE("decodage borne : meme resultat que Python sur l'ASCII, doute sinon") {
    using omega::decode_ascii_for_inspection;
    CHECK(decode_ascii_for_inspection("/a/b", 2) == std::optional<std::string>("/a/b"));
    CHECK(decode_ascii_for_inspection("%3Cscript%3E", 2) == std::optional<std::string>("<script>"));
    CHECK(decode_ascii_for_inspection("%253C", 2) == std::optional<std::string>("<"));
    CHECK(decode_ascii_for_inspection("%25253C", 2) == std::optional<std::string>("%3C"));  // 2 passes au plus
    CHECK(decode_ascii_for_inspection("%2", 2) == std::optional<std::string>("%2"));
    CHECK(decode_ascii_for_inspection("%zz%4", 2) == std::optional<std::string>("%zz%4"));
    CHECK(decode_ascii_for_inspection("%41", 0) == std::optional<std::string>("A"));  // max(1, passes)
    CHECK_FALSE(decode_ascii_for_inspection("%C3%A9", 2).has_value());  // non ASCII apres decodage
    CHECK_FALSE(decode_ascii_for_inspection("\xc3\xa9", 2).has_value());  // non ASCII au depart
}

#ifdef OMEGA_HAS_PCRE2
TEST_CASE("evaluation : propre, correspondance, regle Python seulement") {
    const auto filter = filter_from(kOneRule);
    CHECK(filter->available());
    CHECK(filter->exported_count() == 1);
    CHECK(filter->evaluate(texts_with(omega::WafScope::query, "q=hello")) == omega::WafFilterOutcome::clean);
    CHECK(filter->evaluate(texts_with(omega::WafScope::query, "q=EVIL")) == omega::WafFilterOutcome::match);
    CHECK(filter->evaluate(texts_with(omega::WafScope::path, "/evil")) == omega::WafFilterOutcome::clean);  // scope non lu

    const auto python_only = filter_from(R"({"available":true,"decode_depth":2,"inspect_path":true,"inspect_query":true,
"inspect_headers":false,"native_decides":true,"native_decides_with_watch":true,"python_reason":null,"auth_prefixes":[],"rules":[],"unexported":[{"id":"X","pack":"p","scopes":["user_agent"],"reason":"r"}]})");
    CHECK(python_only->evaluate(texts_with(omega::WafScope::query, "a")) == omega::WafFilterOutcome::clean);
    CHECK(python_only->evaluate(texts_with(omega::WafScope::user_agent, "ua")) == omega::WafFilterOutcome::doubt);
}

TEST_CASE("decision seule et zones protegees (lot 2)") {
    const auto filter = filter_from(R"({"available":true,"decode_depth":2,"inspect_path":true,"inspect_query":true,
"inspect_headers":false,"native_decides":true,"native_decides_with_watch":true,"python_reason":null,"auth_prefixes":["/admin/","/a%62c","/x"],
"unexported":[],"rules":[]})");
    CHECK(filter->decides_alone());
    CHECK(filter->in_protected_zone("/admin"));
    CHECK(filter->in_protected_zone("/admin/page"));
    CHECK_FALSE(filter->in_protected_zone("/administrateur"));  // frontiere de segment, comme zone_resolver
    CHECK(filter->in_protected_zone("/%61dmin/page"));  // sur-ensemble : chemin decode
    CHECK(filter->in_protected_zone("/a%62c"));
    CHECK(filter->in_protected_zone("/\xc3\xa9"));  // non decodable en ASCII : Python tranche
    CHECK_FALSE(filter->in_protected_zone("/public/x"));
    const auto everything = filter_from(R"({"available":true,"decode_depth":2,"inspect_path":true,"inspect_query":true,
"inspect_headers":false,"native_decides":true,"native_decides_with_watch":true,"python_reason":null,"auth_prefixes":["/"],"unexported":[],"rules":[]})");
    CHECK(everything->in_protected_zone("/n-importe-ou"));
    const auto magnet = filter_from(R"({"available":true,"decode_depth":2,"inspect_path":true,"inspect_query":true,
"inspect_headers":false,"native_decides":false,"native_decides_with_watch":false,"python_reason":"magnet","auth_prefixes":[],"unexported":[],"rules":[]})");
    CHECK_FALSE(magnet->decides_alone());
    const auto decoys = filter_from(R"({"available":true,"decode_depth":2,"inspect_path":true,"inspect_query":true,
"inspect_headers":false,"native_decides":false,"native_decides_with_watch":true,"python_reason":"deception",
"auth_prefixes":[],"unexported":[],"rules":[]})");
    CHECK(decoys->decides_alone());  // lot 3 : avec la table des sources suivies
    CHECK(magnet->python_reason() == "magnet");
}

TEST_CASE("controles au chargement (lot 4) : un desaccord confie la regle a Python") {
    const char* base = R"({"available":true,"decode_depth":2,"inspect_path":true,"inspect_query":true,
"inspect_headers":false,"native_decides":true,"native_decides_with_watch":true,"python_reason":null,"auth_prefixes":[],
"check_every":7,"unexported":[{"id":"U","pack":"p","scopes":["referer"],"reason":"reference arriere"}],
"rules":[{"id":"R1","pack":"p","scopes":["query"],"pattern":"\\x{65}\\x{76}\\x{69}\\x{6c}","exclude":null,"lowered":true,
"controls":CONTROLS}]})";
    auto with_controls = [&](const std::string& controls) {
        std::string json = base;
        json.replace(json.find("CONTROLS"), 8, controls);
        return filter_from(json);
    };
    const auto agree = with_controls(R"([["EVIL x",true],["good",false],["é",true]])");  // non ASCII : ignore
    CHECK(agree->exported_count() == 1);
    CHECK(agree->check_every() == 7);
    REQUIRE(agree->python_only_reasons().size() == 1);
    CHECK(agree->python_only_reasons()[0] == "U : non traduite (reference arriere)");
    const auto disagree = with_controls(R"([["good",true]])");
    CHECK(disagree->exported_count() == 0);
    CHECK(disagree->python_only_reasons()[0] == "R1 : controle en desaccord avec Python");
    CHECK(disagree->evaluate(texts_with(omega::WafScope::query, "good")) == omega::WafFilterOutcome::doubt);
}

TEST_CASE("motif refuse par PCRE2 : regle confiee a Python, jamais ignoree") {
    const auto filter = filter_from(R"({"available":true,"decode_depth":2,"inspect_path":true,"inspect_query":true,
"inspect_headers":false,"native_decides":true,"native_decides_with_watch":true,"python_reason":null,"auth_prefixes":[],"unexported":[],"rules":[{"id":"BAD","pack":"p","scopes":["path"],"pattern":"(","exclude":null,"lowered":false}]})");
    CHECK(filter->exported_count() == 0);
    CHECK(filter->compile_errors().size() == 1);
    CHECK(filter->evaluate(texts_with(omega::WafScope::path, "/x")) == omega::WafFilterOutcome::doubt);
}

TEST_CASE("vecteurs Python : textes inspectes et regles, regles livrees") {
    std::ifstream rules_file(std::string(OMEGA_WAF_VECTORS_DIR) + "/waf_filter.json");
    REQUIRE(rules_file.good());
    std::stringstream rules_json;
    rules_json << rules_file.rdbuf();
    const auto filter = filter_from(rules_json.str());
    REQUIRE(filter->compile_errors().empty());
    REQUIRE(filter->python_only_count() == 0);

    std::ifstream file(std::string(OMEGA_WAF_VECTORS_DIR) + "/waf_requests.tsv");
    REQUIRE(file.good());
    auto unhex = [](const std::string& hex) {
        std::string out;
        for (std::size_t i = 0; i + 1 < hex.size(); i += 2) out.push_back(static_cast<char>(std::stoi(hex.substr(i, 2), nullptr, 16)));
        return out;
    };
    int cases = 0, decided = 0, matches = 0, cleans = 0;
    std::string line;
    while (std::getline(file, line)) {
        std::vector<std::string> f;
        std::stringstream fields(line);
        for (std::string field; std::getline(fields, field, '\t');) f.push_back(field);
        REQUIRE(f.size() == 2 + omega::kWafScopeCount + 2);
        omega::RequestHead head;
        head.method = "GET";
        head.target = unhex(f[0]);
        head.http_version = "HTTP/1.1";
        std::stringstream header_lines(unhex(f[1]));
        for (std::string header; std::getline(header_lines, header, '\n');) {
            const auto nul = header.find('\0');
            head.headers.emplace_back(header.substr(0, nul), header.substr(nul + 1));
        }
        omega::Request request;
        request.head = &head;
        omega::fill_request_target(request);
        const bool must_decide = f.back() == "1";
        const std::string expected_ids = f[2 + omega::kWafScopeCount] == "-" ? "" : unhex(f[2 + omega::kWafScopeCount]);
        ++cases;
        const auto texts = filter->prepare(request, false);
        if (!texts) {
            CHECK_MESSAGE(!must_decide, "doute inattendu : " << head.target);
            continue;
        }
        for (std::size_t s = 0; s < omega::kWafScopeCount; ++s) {
            const std::string& expected = f[2 + s];
            const auto& got = (*texts)[s];
            if (expected == "-") CHECK_MESSAGE(!got.has_value(), "scope " << s << " en trop : " << head.target);
            else CHECK_MESSAGE((got.has_value() && *got == unhex(expected)), "scope " << s << " different : " << head.target);
        }
        const auto ids = filter->matching_rules(*texts);
        REQUIRE(ids.has_value());
        std::string joined;
        for (const auto& id : *ids) joined += (joined.empty() ? "" : ",") + id;
        CHECK_MESSAGE(joined == expected_ids, "regles differentes pour " << head.target << " : " << joined << " / " << expected_ids);
        const auto outcome = filter->evaluate(*texts);
        CHECK(outcome == (expected_ids.empty() ? omega::WafFilterOutcome::clean : omega::WafFilterOutcome::match));
        ++decided;
        (expected_ids.empty() ? cleans : matches)++;
    }
    MESSAGE("requetes " << cases << ", decidees " << decided << " (propres " << cleans << ", correspondances " << matches << ")");
    CHECK(cases > 8000);
    CHECK(cleans > 2000);
}
#endif  // OMEGA_HAS_PCRE2 ; sans PCRE2, le filtre est toujours indisponible (test ci-dessous)

TEST_CASE("indisponible : toujours un doute") {
    const auto filter = filter_from(R"({"available":false,"reason":"pack illisible"})");
    CHECK_FALSE(filter->available());
    CHECK(filter->evaluate(omega::WafScopeTexts{}) == omega::WafFilterOutcome::doubt);
}

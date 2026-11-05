// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Limite de debit comptee par le natif (plan WAF natif, lot 6) : vecteurs produits par les VRAIES fonctions Python
// (tools/differential/make_rate_vectors.py) - regle retenue et suite de verdicts du seau a jetons.
#include "doctest.h"

#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "rate_limiter.hpp"
#include "util.hpp"

namespace {

std::vector<std::string> split(const std::string& line, char separator) {
    std::vector<std::string> out;
    std::stringstream stream(line);
    for (std::string field; std::getline(stream, field, separator);) out.push_back(field);
    return out;
}

std::shared_ptr<const omega::RatePolicy> vector_policy() {
    std::ifstream file(std::string(OMEGA_WAF_VECTORS_DIR) + "/rate_policy.json");
    REQUIRE(file.good());
    std::stringstream json;
    json << file.rdbuf();
    std::string error;
    const auto parsed = omega::parse_json(json.str(), &error);
    REQUIRE_MESSAGE(parsed.has_value(), error);
    return omega::RatePolicy::from_json(*parsed);
}

}  // namespace

TEST_CASE("limite de debit : regle retenue identique a select_rate_limit") {
    const auto policy = vector_policy();
    std::ifstream file(std::string(OMEGA_WAF_VECTORS_DIR) + "/rate_select.tsv");
    REQUIRE(file.good());
    int cases = 0;
    for (std::string line; std::getline(file, line);) {
        const auto f = split(line, '\t');
        REQUIRE(f.size() == 5);
        std::string path;
        if (f[0] != "-") {
            for (std::size_t i = 0; i + 1 < f[0].size(); i += 2) path.push_back(static_cast<char>(std::stoi(f[0].substr(i, 2), nullptr, 16)));
        }
        const auto selected = policy->select(path, f[1]);
        CHECK_MESSAGE(selected.key == f[2], path << " " << f[1] << " : " << selected.key << " / " << f[2]);
        CHECK(selected.requests == std::stoll(f[3]));
        CHECK(selected.window_seconds == std::stoll(f[4]));
        ++cases;
    }
    CHECK(cases > 100);
    CHECK(policy->exempt("GET", "/.omega-serv-error-css/error-pages.css"));
    CHECK(policy->exempt("HEAD", "/.omega-serv-error-css/error-pages.css"));
    CHECK_FALSE(policy->exempt("POST", "/.omega-serv-error-css/error-pages.css"));
    CHECK_FALSE(policy->exempt("GET", "/.omega-serv-error-css/autre.css"));
}

TEST_CASE("limite de debit : meme suite de verdicts que le seau Python") {
    std::ifstream file(std::string(OMEGA_WAF_VECTORS_DIR) + "/rate_buckets.tsv");
    REQUIRE(file.good());
    int steps = 0, refused = 0;
    std::uint64_t series = 0;
    for (std::string line; std::getline(file, line);) {
        const auto f = split(line, '\t');
        REQUIRE(f.size() > 2);
        omega::RateLimiter::instance().clear_for_tests();
        const omega::SelectedRate rate{"serie-" + std::to_string(series++), std::stoll(f[0]), std::stoll(f[1])};
        for (std::size_t i = 2; i < f.size(); ++i) {
            const auto colon = f[i].find(':');
            const double now = std::stod(f[i].substr(0, colon));
            const std::uint32_t expected = static_cast<std::uint32_t>(std::stoul(f[i].substr(colon + 1)));
            const auto got = omega::RateLimiter::instance().check(rate, now);
            CHECK_MESSAGE(got.value_or(0) == expected, "seau " << f[0] << "/" << f[1] << " a t=" << now);
            ++steps;
            refused += expected > 0;
        }
    }
    CHECK(steps > 2000);
    CHECK(refused > 100);
}

TEST_CASE("limite de debit : section invalide refusee") {
    std::string error;
    const auto parsed = omega::parse_json(R"({"path_policies":[],"source_policies":[]})", &error);
    REQUIRE(parsed.has_value());
    CHECK_THROWS(omega::RatePolicy::from_json(*parsed));
}

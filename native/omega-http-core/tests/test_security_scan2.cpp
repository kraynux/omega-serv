// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Scan de securite n° 2 (2026-11-20) : cible sans « / » initial (F1-F3), « ..; » (F15), cookies de
// l'administration web (F16), champs de journal (F29), relais qui n'est pas une adresse (F40/F44).
// Memes cas que tests/unit/test_security_scan2_rules.py cote Python.
#include "doctest.h"

#include "http_parser.hpp"
#include "ip.hpp"
#include "static_rules.hpp"
#include "text.hpp"
#include "upstream.hpp"

namespace {

int status_of(std::string_view target) {
    const std::string raw = "GET " + std::string(target) + " HTTP/1.1\r\nHost: x\r\n\r\n";
    const omega::ParseResult r = omega::parse_request_head(raw, omega::ParserLimits{}, false);
    return r.state == omega::ParseState::error ? r.status : 0;
}

}  // namespace

TEST_CASE("scan 2 : seules la forme origine, la forme absolue et « * » sont acceptees") {
    CHECK(status_of("/private/x") == 0);
    CHECK(status_of("*") == 0);
    CHECK(status_of("http://h/x") == 0);
    CHECK(status_of("private/x") == 400);
    CHECK(status_of("%2Fprivate/x") == 400);
    CHECK(status_of("\\private\\x") == 400);
    CHECK(!omega::canonical_path_utf8("private/x"));
    CHECK(*omega::canonical_path_utf8("*") == "*");
}

TEST_CASE("scan 2 : « ..; » est un segment « .. »") {
    CHECK(status_of("/api/..;x/admin") == 400);
    CHECK(status_of("/api/%2e%2e;x/admin") == 400);
    CHECK(status_of("/a/b;x=1") == 0);
}

TEST_CASE("scan 2 : cookies de l'administration web jamais relayes") {
    CHECK(omega::without_admin_cookies("a=1; omega_admin=tok; omega_admin_theme=dark; b=2") == "a=1; b=2");
    CHECK(omega::without_admin_cookies("omega_admin=tok").empty());
    CHECK(omega::without_admin_cookies("PHPSESSID=1") == "PHPSESSID=1");
}

TEST_CASE("scan 2 : NEL, U+2028 et DEL neutralises dans les champs de journal") {
    CHECK(omega::sanitize_log_field("a\xC2\x85" "b\xE2\x80\xA8" "c\x7F" "d\xC2\x9B" "e", 512) == "a b c d e");
    CHECK(omega::sanitize_log_field("\xC3\xA9t\xC3\xA9", 512) == "\xC3\xA9t\xC3\xA9");
}

TEST_CASE("scan 2 : un relais qui n'est pas une adresse garde le pair TCP") {
    const auto trusted = omega::parse_trusted_networks({"127.0.0.1/32"});
    CHECK(omega::rightmost_untrusted({"=HYPERLINK(1)"}, trusted).empty());
    CHECK(omega::rightmost_untrusted({"203.0.113.7"}, trusted) == "203.0.113.7");
}

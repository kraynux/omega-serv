// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Scan de securite n° 1 (2026-11-20) : chemin canonique (cause A), « .. » doublement encode (cause B), parseur IPv6
// (F31). Memes cas que tests/unit/test_security_scan1_rules.py cote Python.
#include "doctest.h"

#include "http_parser.hpp"
#include "ip.hpp"
#include "static_rules.hpp"

namespace {

int status_of(std::string_view target) {
    const std::string raw = "GET " + std::string(target) + " HTTP/1.1\r\nHost: x\r\n\r\n";
    const omega::ParseResult r = omega::parse_request_head(raw, omega::ParserLimits{}, false);
    return r.state == omega::ParseState::error ? r.status : 0;
}

}  // namespace

TEST_CASE("scan 1 : chemin canonique des decisions de securite") {
    using omega::canonical_path_utf8;
    CHECK(*canonical_path_utf8("/private/doc.txt") == "/private/doc.txt");
    CHECK(*canonical_path_utf8("//private/doc.txt") == "/private/doc.txt");
    CHECK(*canonical_path_utf8("/%70rivate/doc.txt") == "/private/doc.txt");
    CHECK(*canonical_path_utf8("/%2570rivate/doc.txt") == "/private/doc.txt");
    CHECK(*canonical_path_utf8("/private%2fdoc.txt") == "/private/doc.txt");
    CHECK(*canonical_path_utf8("/private\\doc.txt") == "/private/doc.txt");
    CHECK(*canonical_path_utf8("/./private/") == "/private/");
    CHECK(*canonical_path_utf8("/a%20b") == "/a b");
    CHECK(*canonical_path_utf8("/") == "/");
    CHECK(*canonical_path_utf8("//") == "/");
    CHECK(*canonical_path_utf8("*") == "*");
    CHECK(!canonical_path_utf8("/%FF"));
    CHECK(!canonical_path_utf8("/a%00b"));
    CHECK(!canonical_path_utf8("/a/%2e%2e/b"));
}

TEST_CASE("scan 1 : « .. » encode une ou deux fois refuse par le parseur") {
    CHECK(status_of("/pub/%2e%2e/.env") == 400);
    CHECK(status_of("/pub/%252e%252e/.env") == 400);
    CHECK(status_of("/pub/%252E%252E%252F.env") == 400);
    CHECK(status_of("/pub/%25252e%25252e/x") == 0);  // trois encodages : jamais decode au-dela de deux passes
    CHECK(status_of("/pub/a.txt") == 0);
    CHECK(status_of("/a%2525b") == 0);
}

TEST_CASE("scan 1 : « % » jamais pris pour un marqueur interne de parse_ipv6") {
    CHECK(!omega::parse_ip_network("2001:db8::%v4hi/128"));
    CHECK(!omega::parse_ip_network("%v4hi:1::/64"));
    CHECK(omega::parse_ip_network("2001:db8::1.2.3.4/128"));
    CHECK(omega::parse_ip_address("fe80::1%eth0"));
}

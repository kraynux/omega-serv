// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Memes cas que le parseur Python (tests/unit/test_http_parser*.py) et que le corpus differentiel.
#include "doctest.h"

#include "http_parser.hpp"

using omega::ParseResult;
using omega::ParserLimits;
using omega::ParseState;
using omega::parse_request_head;

namespace {

ParseResult parse(std::string_view raw, bool eof = false) { return parse_request_head(raw, ParserLimits{}, eof); }

int status_of(std::string_view raw) {
    const ParseResult r = parse(raw);
    return r.state == ParseState::error ? r.status : (r.state == ParseState::complete ? 0 : -1);
}

}  // namespace

TEST_CASE("requete simple complete") {
    const ParseResult r = parse("GET /page.html?a=1 HTTP/1.1\r\nHost: x\r\nUser-Agent: test\r\n\r\nreste");
    REQUIRE(r.state == ParseState::complete);
    CHECK(r.head.method == "GET");
    CHECK(r.head.target == "/page.html?a=1");
    CHECK(r.head.http_version == "HTTP/1.1");
    REQUIRE(r.head.headers.size() == 2);
    CHECK(*r.head.header("host") == "x");
    CHECK(r.consumed == std::string_view("GET /page.html?a=1 HTTP/1.1\r\nHost: x\r\nUser-Agent: test\r\n\r\n").size());
}

TEST_CASE("tete incomplete : attendre, puis fermeture") {
    CHECK(parse("GET / HTTP/1.1\r\nHost: x\r\n").state == ParseState::need_more);
    CHECK(parse("").state == ParseState::need_more);
    CHECK(parse("", true).status == 0);                       // fermeture propre
    CHECK(parse("GET / HTTP/1.1\r\nHo", true).status == 400);  // fermeture au milieu
}

TEST_CASE("ligne de requete malformee") {
    CHECK(status_of("GARBAGE\r\n\r\n") == 400);
    CHECK(status_of("GET / HTTP/1.1 extra\r\n\r\n") == 400);
    CHECK(status_of("GET  / HTTP/1.1\r\n\r\n") == 400);
    CHECK(status_of("GET / FTP/1.1\r\n\r\n") == 400);
    CHECK(status_of("get / HTTP/1.1\r\nHost: x\r\n\r\n") == 0);   // methode refusee plus loin (405)
    // Version stricte (plan §14, 2026-11-02) : majeure autre que 1 -> 505, mal ecrite -> 400.
    CHECK(status_of("GET / HTTP/9.9\r\nHost: x\r\n\r\n") == 505);
    CHECK(status_of("GET / HTTP/abc\r\nHost: x\r\n\r\n") == 400);
    CHECK(status_of("GET / HTTP/1.7\r\nHost: x\r\n\r\n") == 0);
}

TEST_CASE("limites") {
    const std::string long_target(9000, 'a');
    CHECK(status_of("GET /" + long_target + " HTTP/1.1\r\n\r\n") == 414);
    CHECK(status_of("GET / HTTP/1.1\r\nX-Big: " + std::string(20000, 'a') + "\r\n\r\n") == 431);
    std::string many = "GET / HTTP/1.1\r\n";
    for (int i = 0; i < 101; ++i) many += "X-" + std::to_string(i) + ": v\r\n";
    CHECK(status_of(many + "\r\n") == 431);
    std::string total = "GET / HTTP/1.1\r\n";
    for (int i = 0; i < 20; ++i) total += "X-" + std::to_string(i) + ": " + std::string(900, 'v') + "\r\n";
    CHECK(status_of(total + "\r\n") == 431);
    // une ligne interminable sans CRLF est coupee des qu'elle depasse la limite
    CHECK(status_of("GET / HTTP/1.1\r\nX: " + std::string(17000, 'a')) == 431);
}

TEST_CASE("en-tetes malformes") {
    CHECK(status_of("GET / HTTP/1.1\r\nHost: x\r\n suite\r\n\r\n") == 400);      // repliage
    CHECK(status_of("GET / HTTP/1.1\r\nSansDeuxPoints\r\n\r\n") == 400);
    CHECK(status_of("GET / HTTP/1.1\r\n: valeur\r\n\r\n") == 400);              // nom vide
    CHECK(status_of("GET / HTTP/1.1\r\nX-A: a\x01" "b\r\n\r\n") == 400);         // caractere de controle
    CHECK(status_of("GET / HTTP/1.1\r\nX-A: a\tb\r\n\r\n") == 0);                // tabulation toleree
}

TEST_CASE("durcissement : espace dans le nom d'en-tete (RFC 9112 §5.1)") {
    CHECK(status_of("GET / HTTP/1.1\r\nX-A : 1\r\n\r\n") == 400);
    CHECK(status_of("GET / HTTP/1.1\r\nX A: 1\r\n\r\n") == 400);
    CHECK(status_of("GET / HTTP/1.1\r\nX-A\t: 1\r\n\r\n") == 400);
}

TEST_CASE("valeurs nettoyees comme str.strip() de Python") {
    const ParseResult r = parse("GET / HTTP/1.1\r\nX-A:  \xa0" "valeur\x85  \r\n\r\n");
    REQUIRE(r.state == ParseState::complete);
    CHECK(*r.head.header("x-a") == "valeur");
}

TEST_CASE("Content-Length duplique et Expect") {
    CHECK(status_of("POST / HTTP/1.1\r\nContent-Length: 3\r\nContent-Length: 3\r\n\r\n") == 400);
    CHECK(status_of("POST / HTTP/1.1\r\nContent-Length: 3\r\nExpect: 100-continue\r\n\r\n") == 417);
}

TEST_CASE("cadrage du corps") {
    auto framing = [](std::string_view raw) {
        return omega::body_framing(parse(raw).head, 10 * 1024 * 1024);
    };
    CHECK(framing("GET / HTTP/1.1\r\nHost: x\r\n\r\n").status == 0);
    CHECK(framing("POST / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n").status == 400);
    CHECK(framing("POST / HTTP/1.1\r\nContent-Length: 3\r\nTransfer-Encoding: chunked\r\n\r\n").status == 400);
    CHECK(framing("POST / HTTP/1.1\r\nContent-Length: -1\r\n\r\n").status == 400);
    CHECK(framing("POST / HTTP/1.1\r\nContent-Length: 12abc\r\n\r\n").status == 400);
    CHECK(framing("POST / HTTP/1.1\r\nContent-Length: +5\r\n\r\n").status == 400);        // durcissement
    CHECK(framing("POST / HTTP/1.1\r\nContent-Length: 1_000\r\n\r\n").status == 400);     // durcissement
    CHECK(framing("POST / HTTP/1.1\r\nContent-Length: 20000000\r\n\r\n").status == 413);
    CHECK(framing("POST / HTTP/1.1\r\nContent-Length: 99999999999999999999999\r\n\r\n").status == 413);
    const auto ok = framing("POST / HTTP/1.1\r\nContent-Length: 42\r\n\r\n");
    CHECK(ok.status == 0);
    CHECK(ok.content_length == 42);
}

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Plan proxy natif v2, lot 4 : requete vers le backend (build_outgoing_headers) et lecture stricte de sa reponse
// (_read_final_head, _body_framing). La comparaison avec les vraies fonctions Python est faite cote pytest
// (tests/integration/test_native_proxy_relay.py) ; ici, les regles une par une.
#include <doctest.h>

#include <string>

#include "upstream.hpp"

namespace {

struct Fixture {
    omega::RequestHead head;
    omega::Request request;
    omega::ProxyZoneSettings zone;
    omega::ProxyUpstream upstream;
    std::vector<omega::IpNetwork> trusted;

    Fixture() {
        head.method = "POST";
        head.target = "/api/x?a=1";
        head.http_version = "HTTP/1.1";
        request.head = &head;
        request.path_text = "/api/x";
        request.query_text = "a=1";
        request.remote_ip = "203.0.113.7";
        request.peer_ip = "127.0.0.1";
        upstream.host = "::1";
        upstream.port = 9000;
        upstream.host_header = "[::1]:9000";
        upstream.address = "::1";
    }

    std::string build(std::string_view body = "", bool tls = false) {
        omega::UpstreamRequestContext context;
        context.zone = &zone;
        context.upstream = &upstream;
        context.effective_path = request.path_text;
        context.client_tls = tls;
        context.listen_port = 8080;
        context.trusted_networks = &trusted;
        const auto built = omega::build_upstream_request(request, context, body);
        REQUIRE(built.has_value());
        return *built;
    }
};

}  // namespace

TEST_CASE("requete vers le backend : en-tetes reecrits comme build_outgoing_headers") {
    Fixture f;
    f.head.headers = {{"Host", "site.example"}, {"Content-Length", "2"}, {"X-Real-IP", "6.6.6.6"},
                      {"Forwarded", "for=6.6.6.6"}, {"Connection", "keep-alive, X-Secret"}, {"X-Secret", "s"},
                      {"Accept", "a"}, {"ACCEPT", "b"}, {"X-Forwarded-For", "9.9.9.9"}, {"X-Omega-Proxy-Hops", " 2 "}};
    const std::string out = f.build("ok");
    CHECK(out == "POST /api/x?a=1 HTTP/1.1\r\n"
                 "accept: b\r\n"  // en double : position de la premiere occurrence, valeur de la derniere
                 "Content-Length: 2\r\n"  // scan de securite n° 1 (F8) : recalculee sur le corps transmis
                 "Host: [::1]:9000\r\n"
                 "X-Forwarded-For: 203.0.113.7\r\n"
                 "X-Real-IP: 203.0.113.7\r\n"
                 "X-Forwarded-Proto: http\r\n"
                 "X-Forwarded-Port: 8080\r\n"
                 "X-Forwarded-Host: site.example\r\n"
                 "X-Omega-Proxy-Hops: 3\r\n\r\nok");
}

TEST_CASE("requete vers le backend : Host garde, relais de confiance, cible non latin-1") {
    Fixture f;
    f.zone.preserve_host = true;
    f.head.headers = {{"Host", "site.example"}, {"X-Forwarded-Proto", " HTTPS "}, {"X-Forwarded-Port", "0443"}};
    std::string out = f.build();
    CHECK(out.find("Host: site.example\r\n") != std::string::npos);
    CHECK(out.find("X-Forwarded-Proto: http\r\n") != std::string::npos);  // pair hors relais de confiance
    CHECK(out.find("X-Forwarded-Port: 8080\r\n") != std::string::npos);
    f.trusted = omega::parse_trusted_networks({"127.0.0.1/32"});
    out = f.build();
    CHECK(out.find("X-Forwarded-Proto: https\r\n") != std::string::npos);
    CHECK(out.find("X-Forwarded-Port: 443\r\n") != std::string::npos);
    CHECK(f.build("", true).find("X-Forwarded-Proto: https\r\n") != std::string::npos);

    f.request.path_text = "/api/\xe6\x97\xa5";  // UTF-8 hors latin-1 (apres une reecriture) : 502 cote Python
    omega::UpstreamRequestContext context;
    context.zone = &f.zone;
    context.upstream = &f.upstream;
    context.effective_path = f.request.path_text;
    context.trusted_networks = &f.trusted;
    CHECK_FALSE(omega::build_upstream_request(f.request, context, "").has_value());
}

TEST_CASE("compteur de sauts : int() de Python, jamais negatif") {
    Fixture f;
    for (const auto& [raw, expected] : std::vector<std::pair<std::string, int>>{
             {"4", 4}, {" +4 ", 4}, {"1_0", 10}, {"-3", 0}, {"x", 0}, {"1__0", 0}, {"_1", 0}, {"", 0}}) {
        f.head.headers = {{"X-Omega-Proxy-Hops", raw}};
        CHECK_MESSAGE(omega::incoming_proxy_hop_count(f.request) == expected, raw);
    }
}

TEST_CASE("reponse du backend : tete stricte et cadrage du corps") {
    using State = omega::UpstreamHead::State;
    auto parse = [](std::string_view data, std::string_view method = "GET", bool eof = false) {
        return omega::parse_upstream_head(data, method, eof);
    };
    auto ok = parse("HTTP/1.1 200 OK\r\nContent-Length: 5\r\nX: y\r\n\r\nhello");
    REQUIRE(ok.state == State::complete);
    CHECK(ok.framing == omega::UpstreamFraming::length);
    CHECK(ok.content_length == 5);
    CHECK(ok.consumed == std::string("HTTP/1.1 200 OK\r\nContent-Length: 5\r\nX: y\r\n\r\n").size());

    CHECK(parse("HTTP/1.1 200 OK\r\nContent-Le").state == State::need_more);
    CHECK(parse("HTTP/1.1 200 OK\r\nContent-Le", "GET", true).state == State::error);
    CHECK(parse("", "GET", true).reason == "upstream a fermé la connexion sans réponse");
    CHECK(parse("HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 204 No Content\r\n\r\n").status == 204);  // 1xx ignorees
    CHECK(parse("HTTP/1.1 101 Switching\r\n\r\n").state == State::error);
    std::string interim;
    for (int i = 0; i < 9; ++i) interim += "HTTP/1.1 103 Early\r\n\r\n";
    CHECK(parse(interim + "HTTP/1.1 200 OK\r\n\r\n").reason == "trop de reponses 1xx");

    // S7, S8
    CHECK(parse("HTTP/1.1 600 X\r\n\r\n").state == State::error);
    CHECK(parse("HTTP/2 200 OK\r\n\r\n").state == State::error);
    CHECK(parse("HTTP/1.1 200\n\n").state == State::complete);  // LF seul accepte, phrase facultative
    CHECK(parse("HTTP/1.1 200 OK\r\n folded\r\n\r\n").state == State::error);
    CHECK(parse("HTTP/1.1 200 OK\r\nBad Name: x\r\n\r\n").state == State::error);
    CHECK(parse("HTTP/1.1 200 OK\r\nX: a\x01" "b\r\n\r\n").state == State::error);
    CHECK(parse("HTTP/1.1 200 OK\r\nX: a\tb\r\n\r\n").state == State::complete);
    std::string many = "HTTP/1.1 200 OK\r\n";
    for (int i = 0; i < 101; ++i) many += "X-" + std::to_string(i) + ": v\r\n";
    CHECK(parse(many + "\r\n").state == State::error);

    // D1, D2 : sans corps ; S9, S10, D21
    CHECK(parse("HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n", "HEAD").framing == omega::UpstreamFraming::none);
    CHECK(parse("HTTP/1.1 304 NM\r\nContent-Length: 5\r\n\r\n").framing == omega::UpstreamFraming::none);
    CHECK(parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n").framing == omega::UpstreamFraming::chunked);
    CHECK(parse("HTTP/1.1 200 OK\r\n\r\n").framing == omega::UpstreamFraming::close);
    CHECK(parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip, chunked\r\n\r\n").state == State::error);
    CHECK(parse("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Length: 3\r\n\r\n").state == State::error);
    CHECK(parse("HTTP/1.1 200 OK\r\nContent-Length: 3\r\nContent-Length: 3\r\n\r\n").content_length == 3);
    CHECK(parse("HTTP/1.1 200 OK\r\nContent-Length: 3\r\nContent-Length: 4\r\n\r\n").state == State::error);
    CHECK(parse("HTTP/1.1 200 OK\r\nContent-Length: 3, 3\r\n\r\n").state == State::error);
    CHECK(parse("HTTP/1.1 200 OK\r\nContent-Length: +3\r\n\r\n").state == State::error);
}

TEST_CASE("reponse relayee : en-tetes de saut retires, Set-Cookie multiples, longueur recalculee") {
    const auto head = omega::parse_upstream_head(
        "HTTP/1.1 200 OK\r\nConnection: keep-alive\r\nContent-Length: 2\r\nSet-Cookie: a=1\r\nset-cookie: b=2\r\n"
        "x-frame-options: DENY\r\nX-Frame-Options: SAMEORIGIN\r\nKeep-Alive: timeout=5\r\nServer: amont\r\n\r\nok",
        "GET", false);
    const omega::Response response = omega::relayed_response(head, "ok", "GET");
    CHECK(response.status == 200);
    CHECK(response.body == "ok");
    CHECK(response.headers.find("Content-Length") == nullptr);  // calculee par le serveur a l'envoi
    CHECK(response.headers.find("Connection") == nullptr);
    CHECK(response.headers.find("x-frame-options") == nullptr);  // variante de casse remplacee (D27)
    REQUIRE(response.headers.find("X-Frame-Options") != nullptr);
    CHECK(*response.headers.find("X-Frame-Options") == "SAMEORIGIN");
    REQUIRE(response.headers.repeated().size() == 2);
    CHECK(response.headers.repeated()[1].second == "b=2");

    const auto head_response = omega::parse_upstream_head("HTTP/1.1 200 OK\r\nContent-Length: 1234\r\n\r\n", "HEAD", false);
    const omega::Response for_head = omega::relayed_response(head_response, "", "HEAD");
    REQUIRE(for_head.headers.find("Content-Length") != nullptr);
    CHECK(*for_head.headers.find("Content-Length") == "1234");  // D1 : longueur de la ressource
}

// ---------------------------------------------------------------------------------------------- lot 5 : chunked (S11)
namespace {

struct Decoded {
    std::string body;
    bool done = false;
    bool failed = false;
    std::string rest;  // octets non consommes (ligne inachevee)
};

// Tout d'un bloc, ou octet par octet (`step` = 1) : le resultat doit etre le meme (decodage au fil de l'eau).
Decoded decode(std::string_view input, std::size_t step = 0, bool eof = false) {
    omega::ChunkedDecoder decoder;
    Decoded out;
    std::string pending;
    std::size_t pos = 0;
    while (pos < input.size() && !decoder.done() && !decoder.failed()) {
        const std::size_t take = step == 0 ? input.size() - pos : std::min(step, input.size() - pos);
        pending.append(input.substr(pos, take));
        pos += take;
        pending.erase(0, decoder.feed(pending, out.body));
    }
    if (eof) decoder.finish_at_eof();
    out.done = decoder.done();
    out.failed = decoder.failed();
    out.rest = pending + std::string(input.substr(pos));
    return out;
}

}  // namespace

TEST_CASE("chunked : decode au fil de l'eau, extensions et trailers retires") {
    const std::string wire = "5\r\nhello\r\n6;nom=valeur\r\n world\r\n0\r\nX-Trailer: 1\r\nX-Autre: deux\r\n\r\nSUITE";
    for (std::size_t step : {0u, 1u, 3u, 7u}) {
        const Decoded result = decode(wire, step);
        CHECK(result.done);
        CHECK(result.body == "hello world");
        CHECK(result.rest == "SUITE");  // octets apres la reponse : jamais consommes (D22)
    }
    CHECK(decode("A\r\n0123456789\r\n0\r\n\r\n").body == "0123456789");
    CHECK(decode("a \t\r\n0123456789\r\n0\r\n\r\n").done);  // rstrip(" \t") de Python
    CHECK(decode("000000000000000a\r\n0123456789\r\n0\r\n\r\n").done);  // 16 chiffres : permis
}

TEST_CASE("chunked : refus stricts, comme _read_chunked") {
    CHECK(decode("00000000000000000a\r\n0123456789\r\n0\r\n\r\n").failed);  // plus de 16 chiffres
    CHECK(decode("-5\r\nhello\r\n0\r\n\r\n").failed);
    CHECK(decode("+5\r\nhello\r\n0\r\n\r\n").failed);
    CHECK(decode(" 5\r\nhello\r\n0\r\n\r\n").failed);
    CHECK(decode("0x5\r\nhello\r\n0\r\n\r\n").failed);
    CHECK(decode("\r\nhello\r\n0\r\n\r\n").failed);
    CHECK(decode("5\nhello\r\n0\r\n\r\n").failed);         // LF seul apres la taille
    CHECK(decode("5\r\nhelloXY0\r\n\r\n").failed);         // pas de CRLF apres les donnees
    CHECK(decode("5\r\nhello\n0\r\n\r\n", 1).failed);
    CHECK(decode("0\r\nX-T: 1\n\r\n").failed);             // trailer sans CRLF
    CHECK(decode("0\r\n bad: fold\r\n\r\n").failed);       // trailer replie
    CHECK(decode("0\r\nnom invalide: 1\r\n\r\n").failed);  // nom hors tchar
    CHECK(decode("0\r\n\n").failed);
    // Ligne de taille : 4096 octets CRLF compris au plus (extensions comprises).
    CHECK(decode("5;" + std::string(4092, 'e') + "\r\nhello\r\n0\r\n\r\n").done);
    CHECK(decode("5;" + std::string(4093, 'e') + "\r\nhello\r\n0\r\n\r\n").failed);
    CHECK(decode(std::string(5000, '1'), 1).failed);  // jamais de ligne sans fin gardee en memoire
    // Trailers : 32 lignes et 16 Kio au plus.
    std::string trailers;
    for (int i = 0; i < 32; ++i) trailers += "X-T" + std::to_string(i) + ": v\r\n";
    CHECK(decode("0\r\n" + trailers + "\r\n").done);
    CHECK(decode("0\r\n" + trailers + "X-De-Trop: v\r\n\r\n").failed);
    // « X-T: » + valeur + CRLF : 16384 octets tout juste permis, un de plus refuse (total > MAX_TRAILER_BYTES).
    CHECK(decode("0\r\nX-T: " + std::string(16384 - 7, 'v') + "\r\n\r\n").done);
    CHECK(decode("0\r\nX-T: " + std::string(16384 - 6, 'v') + "\r\n\r\n").failed);
    CHECK(decode("0\r\nX-T: " + std::string(20000, 'v'), 1).failed);
}

TEST_CASE("chunked : fin de flux avant la fin du corps = erreur, taille maximale sans depassement") {
    CHECK(decode("5\r\nhel", 0, true).failed);
    CHECK(decode("5\r\nhello\r\n", 0, true).failed);
    CHECK(decode("5\r\nhello\r\n0\r\n", 0, true).failed);
    const Decoded partial = decode("5\r\nhello\r\n", 0, false);
    CHECK_FALSE(partial.done);
    CHECK_FALSE(partial.failed);
    CHECK(partial.body == "hello");
    // Taille 2^64-1 : acceptee par la ligne (comme int(..., 16)), puis corps simplement attendu.
    omega::ChunkedDecoder decoder;
    std::string out;
    CHECK(decoder.feed("ffffffffffffffff\r\nabc", out) == 21);
    CHECK(out == "abc");
    CHECK(decoder.state() == omega::ChunkedDecoder::State::data);
}

TEST_CASE("asks_close : jetons de Connection, casse ignoree") {
    using omega::parse_upstream_head;
    CHECK(omega::asks_close(parse_upstream_head("HTTP/1.1 200 OK\r\nConnection: keep-alive, Close\r\n\r\n", "GET", false)));
    CHECK_FALSE(omega::asks_close(parse_upstream_head("HTTP/1.1 200 OK\r\nConnection: closed\r\n\r\n", "GET", false)));
    CHECK_FALSE(omega::asks_close(parse_upstream_head("HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n", "GET", false)));
}

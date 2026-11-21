// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Plan proxy natif v2, lot 10 (C17) : detection de la mise a niveau, reperage des trames, trames 1001, requete vers le
// backend (build_outgoing_headers(preserve_upgrade=True)), tete du backend et tete ecrite au client
// (_write_status_line_and_headers). Le meme comportement de bout en bout est compare aux deux moteurs par pytest
// (tests/integration/test_native_proxy_websocket.py).
#include <doctest.h>

#include <string>

#include "upstream.hpp"
#include "websocket.hpp"

namespace {

omega::Request upgrade_request(omega::RequestHead& head) {
    head.method = "GET";
    head.target = "/ws/chat";
    head.http_version = "HTTP/1.1";
    omega::Request request;
    request.head = &head;
    request.path_text = "/ws/chat";
    request.remote_ip = "203.0.113.7";
    request.peer_ip = "127.0.0.1";
    return request;
}

std::string frame(unsigned char first, std::string_view payload, bool masked) {
    std::string out(1, static_cast<char>(first));
    const unsigned char mask_bit = masked ? 0x80 : 0;
    if (payload.size() < 126) {
        out.push_back(static_cast<char>(mask_bit | payload.size()));
    } else if (payload.size() < 65536) {
        out.push_back(static_cast<char>(mask_bit | 126));
        out.push_back(static_cast<char>(payload.size() >> 8));
        out.push_back(static_cast<char>(payload.size() & 0xFF));
    } else {
        out.push_back(static_cast<char>(mask_bit | 127));
        for (int shift = 56; shift >= 0; shift -= 8) out.push_back(static_cast<char>((payload.size() >> shift) & 0xFF));
    }
    if (masked) out += std::string("\x01\x02\x03\x04", 4);
    out += payload;  // contenu jamais lu : peu importe qu'il soit masque
    return out;
}

}  // namespace

TEST_CASE("mise a niveau : GET, jeton upgrade dans Connection, Upgrade: websocket") {
    omega::RequestHead head;
    head.headers = {{"Connection", "keep-alive, Upgrade"}, {"Upgrade", " WebSocket "}};
    omega::Request request = upgrade_request(head);
    CHECK(omega::is_websocket_upgrade(request));
    head.headers = {{"Connection", "upgradex"}, {"Upgrade", "websocket"}};
    CHECK_FALSE(omega::is_websocket_upgrade(request));
    head.headers = {{"Connection", "Upgrade"}, {"Upgrade", "h2c"}};
    CHECK_FALSE(omega::is_websocket_upgrade(request));
    head.headers = {{"Connection", "Upgrade"}, {"Upgrade", "websocket"}};
    head.method = "POST";
    CHECK_FALSE(omega::is_websocket_upgrade(request));
    head.method = "GET";
    head.headers = {{"Connection", "Upgrade"}, {"Upgrade", "websocket"}, {"Upgrade", "h2c"}};  // derniere valeur
    CHECK_FALSE(omega::is_websocket_upgrade(request));
}

TEST_CASE("reperage des trames : en-tetes seulement, longueurs 7, 16 et 64 bits, masque") {
    omega::WebSocketFrameTracker tracker;
    CHECK(tracker.at_boundary());
    const std::string all = frame(0x81, "salut", true) + frame(0x82, std::string(300, 'x'), false) +
                            frame(0x82, std::string(70000, 'y'), true) + frame(0x89, "", false);
    for (std::size_t i = 0; i < all.size(); ++i) {  // un octet a la fois : jamais de fin de trame au milieu
        tracker.feed(std::string_view(all).substr(i, 1));
        const bool expected_boundary = i + 1 == all.size() || i + 1 == frame(0x81, "salut", true).size();
        if (expected_boundary) CHECK(tracker.at_boundary());
    }
    CHECK(tracker.at_boundary());
    CHECK(tracker.can_send_close());
    tracker.feed(all.substr(0, 3));
    CHECK_FALSE(tracker.at_boundary());
    CHECK_FALSE(tracker.can_send_close());
}

TEST_CASE("reperage des trames : une fermeture deja passee interdit la 1001") {
    omega::WebSocketFrameTracker tracker;
    tracker.feed(frame(0x88, "\x03\xe8", false));
    CHECK(tracker.at_boundary());
    CHECK(tracker.close_seen());
    CHECK_FALSE(tracker.can_send_close());
}

TEST_CASE("trames 1001 : vers le client sans masque, vers le backend masquee") {
    CHECK(omega::close_frame_to_client() == std::string("\x88\x02\x03\xe9", 4));
    const std::string masked = omega::close_frame_to_server({0x10, 0x20, 0x30, 0x40});
    CHECK(masked == std::string("\x88\x82\x10\x20\x30\x40", 6) + std::string(1, static_cast<char>(0x03 ^ 0x10)) +
                        std::string(1, static_cast<char>(0xe9 ^ 0x20)));
}

TEST_CASE("requete de mise a niveau : Connection et Upgrade relayes, autres en-tetes de saut retires") {
    omega::RequestHead head;
    head.headers = {{"Host", "site.example"}, {"Connection", "Upgrade, X-Secret"}, {"Upgrade", "websocket"},
                    {"X-Secret", "s"}, {"Keep-Alive", "5"}, {"Sec-WebSocket-Key", "k"}};
    omega::Request request = upgrade_request(head);
    omega::ProxyZoneSettings zone;
    omega::ProxyUpstream upstream;
    upstream.host_header = "127.0.0.1:9000";
    std::vector<omega::IpNetwork> trusted;
    omega::UpstreamRequestContext context;
    context.zone = &zone;
    context.upstream = &upstream;
    context.effective_path = "/ws/chat";
    context.listen_port = 8080;
    context.trusted_networks = &trusted;
    context.preserve_upgrade = true;
    const auto built = omega::build_upstream_request(request, context, "");
    REQUIRE(built.has_value());
    CHECK(*built == "GET /ws/chat HTTP/1.1\r\n"
                    "connection: Upgrade, X-Secret\r\n"
                    "upgrade: websocket\r\n"
                    "sec-websocket-key: k\r\n"
                    "Host: 127.0.0.1:9000\r\n"
                    "X-Forwarded-For: 203.0.113.7\r\n"
                    "X-Real-IP: 203.0.113.7\r\n"
                    "X-Forwarded-Proto: http\r\n"
                    "X-Forwarded-Port: 8080\r\n"
                    "X-Forwarded-Host: site.example\r\n"
                    "X-Omega-Proxy-Hops: 1\r\n\r\n");
    context.preserve_upgrade = false;  // relais ordinaire : inchange
    const auto plain = omega::build_upstream_request(request, context, "");
    REQUIRE(plain.has_value());
    CHECK(plain->find("upgrade") == std::string::npos);
    CHECK(plain->find("connection") == std::string::npos);
}

TEST_CASE("tete du backend a la mise a niveau : une seule tete, 101 acceptee, rien lu comme un corps") {
    const std::string answer = "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n";
    const auto head = omega::parse_upstream_head(answer + "\x81\x02hi", "GET", false, true);
    REQUIRE(head.state == omega::UpstreamHead::State::complete);
    CHECK(head.status == 101);
    CHECK(head.consumed == answer.size());
    CHECK(head.framing == omega::UpstreamFraming::none);
    const auto interim = omega::parse_upstream_head("HTTP/1.1 100 Continue\r\n\r\n", "GET", false, true);
    CHECK(interim.status == 100);  // _read_status_and_headers : aucune 1xx sautee
    CHECK(omega::parse_upstream_head("HTTP/1.1 101 Switching Protocols\r\nUpg", "GET", false, true).state ==
          omega::UpstreamHead::State::need_more);
    CHECK(omega::parse_upstream_head("HTTP/1.1 101 Switching Protocols\r\nUpg", "GET", true, true).state ==
          omega::UpstreamHead::State::error);
    CHECK(omega::parse_upstream_head(answer, "GET", false).state == omega::UpstreamHead::State::error);  // hors WebSocket
}

TEST_CASE("tete ecrite au client : 101 avec Connection/Upgrade, refus sans corps") {
    const std::vector<std::pair<std::string, std::string>> headers = {
        {"Upgrade", "websocket"}, {"Connection", "Upgrade"}, {"Keep-Alive", "5"}, {"Sec-WebSocket-Accept", "a"},
        {"Content-Length", "6"}};
    const std::string cookie = "s=b; Max-Age=60";
    CHECK(omega::upgrade_response_head(101, "Switching Protocols", headers, &cookie) ==
          "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: a\r\n"
          "Content-Length: 6\r\nSet-Cookie: s=b; Max-Age=60\r\n\r\n");
    CHECK(omega::upgrade_response_head(403, "Forbidden", headers) ==
          "HTTP/1.1 403 Forbidden\r\nUpgrade: websocket\r\nSec-WebSocket-Accept: a\r\nContent-Length: 0\r\n"
          "Connection: close\r\n\r\n");
    CHECK(omega::upgrade_response_head(502, "Bad Gateway", {}) ==
          "HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
}

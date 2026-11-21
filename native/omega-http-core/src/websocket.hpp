// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Plan proxy natif v2, lot 10 (C17) : tunnel WebSocket natif. Copies du moteur Python :
// - is_websocket_upgrade = domain/http/websocket.is_websocket_upgrade_request ;
// - WebSocketFrameTracker = domain/http/websocket.WebSocketFrameTracker (en-tetes de trame seulement, jamais le
//   contenu) : sait si une trame de fermeture peut s'inserer entre deux trames (C14, delai d'inactivite) ;
// - close_frame_to_client / close_frame_to_server : trame 1001 (decision de l'auteur du 2026-11-14).
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

#include "engine.hpp"

namespace omega {

inline constexpr std::uint16_t kGoingAway = 1001;  // RFC 6455 §7.4.1

// RFC 6455 §4.1 : GET, jeton `upgrade` dans Connection (liste, casse ignoree), `Upgrade: websocket`.
bool is_websocket_upgrade(const Request& request);

class WebSocketFrameTracker {
public:
    void feed(std::string_view data);
    [[nodiscard]] bool at_boundary() const { return header_size_ == 0 && remaining_ == 0; }
    [[nodiscard]] bool close_seen() const { return close_seen_; }
    [[nodiscard]] bool can_send_close() const { return at_boundary() && !close_seen_; }

private:
    std::array<unsigned char, 14> header_{};
    std::size_t header_size_ = 0;
    std::uint64_t remaining_ = 0;
    bool close_seen_ = false;
    [[nodiscard]] std::size_t header_needed() const;
    void end_of_header();
};

// Serveur vers client : jamais masquee (RFC 6455 §5.1).
std::string close_frame_to_client(std::uint16_t code = kGoingAway);
// Client vers serveur (le backend) : toujours masquee (§5.3), cle imprevisible de 4 octets.
std::string close_frame_to_server(const std::array<unsigned char, 4>& mask, std::uint16_t code = kGoingAway);

}  // namespace omega

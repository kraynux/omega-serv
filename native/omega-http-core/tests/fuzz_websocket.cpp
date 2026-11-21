// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Plan proxy natif v2, lot 11 (campagne finale) : fuzzing du reperage des trames WebSocket (lot 10).
// Proprietes verifiees : aucun plantage ni comportement indefini (ASan, UBSan) ; l'etat (frontiere de trame,
// fermeture vue) ne depend pas du decoupage des octets recus ; jamais de fermeture inseree hors frontiere ; une
// trame de fermeture suivie de quoi que ce soit garde `close_seen`.
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <string_view>

#include "websocket.hpp"

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
    if (size == 0) return 0;
    const std::string_view input(reinterpret_cast<const char*>(data) + 1, size - 1);
    omega::WebSocketFrameTracker whole;
    whole.feed(input);
    omega::WebSocketFrameTracker split;
    const std::size_t step = 1 + data[0] % 23;
    bool closed = false;
    for (std::size_t pos = 0; pos < input.size(); pos += step) {
        split.feed(input.substr(pos, step));
        if (closed && !split.close_seen()) std::abort();  // une fermeture vue ne s'oublie jamais
        closed = split.close_seen();
        if (split.can_send_close() && !split.at_boundary()) std::abort();
    }
    if (whole.at_boundary() != split.at_boundary() || whole.close_seen() != split.close_seen()) std::abort();
    if (whole.can_send_close() != split.can_send_close()) std::abort();
    return 0;
}

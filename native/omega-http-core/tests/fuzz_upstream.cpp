// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Plan proxy natif v2, lot 5 (C19) : fuzzing de l'analyseur de reponse du backend et du decodeur chunked.
// Proprietes verifiees : aucun plantage ni comportement indefini (ASan, UBSan) ; le decodage au fil de l'eau donne
// le meme resultat quel que soit le decoupage des octets recus ; aucune ligne inachevee gardee au-dela des plafonds.
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <string>
#include <string_view>

#include "upstream.hpp"

namespace {

struct Outcome {
    std::string body;
    omega::ChunkedDecoder::State state;
    std::size_t consumed;
};

Outcome decode_in_steps(std::string_view input, std::size_t step) {
    omega::ChunkedDecoder decoder;
    Outcome out{};
    std::string pending;
    std::size_t pos = 0;
    std::size_t consumed = 0;
    while (pos < input.size() && !decoder.done() && !decoder.failed()) {
        const std::size_t take = std::min(step, input.size() - pos);
        pending.append(input.substr(pos, take));
        pos += take;
        const std::size_t used = decoder.feed(pending, out.body);
        consumed += used;
        pending.erase(0, used);
        // C19 : une ligne inachevee reste bornee (taille de bloc ou trailers).
        if (pending.size() > omega::kMaxTrailerBytes + omega::kMaxChunkLineBytes + 4096) std::abort();
    }
    out.state = decoder.state();
    out.consumed = consumed;
    return out;
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
    if (size == 0) return 0;
    const std::string_view input(reinterpret_cast<const char*>(data) + 1, size - 1);
    const std::string_view method = (data[0] & 1) ? "HEAD" : "GET";
    for (const bool eof : {false, true}) {
        const omega::UpstreamHead head = omega::parse_upstream_head(input, method, eof);
        if (head.state == omega::UpstreamHead::State::complete && head.consumed > input.size()) std::abort();
        // Lot 11 : tete d'une reponse a une mise a niveau WebSocket (lot 10, une seule tete, 101 accepte).
        const omega::UpstreamHead upgrade = omega::parse_upstream_head(input, "GET", eof, true);
        if (upgrade.state == omega::UpstreamHead::State::complete && upgrade.consumed > input.size()) std::abort();
    }
    (void)omega::decode_upstream_response(input, method);

    const Outcome whole = decode_in_steps(input, input.size() == 0 ? 1 : input.size());
    const std::size_t step = 1 + (data[0] >> 1) % 17;
    const Outcome split = decode_in_steps(input, step);
    // Meme etat final et meme corps, sauf « en attente » (le decoupage ne change que le moment de la decision).
    const bool settled = whole.state == omega::ChunkedDecoder::State::done || whole.state == omega::ChunkedDecoder::State::failed;
    if (settled && whole.state != split.state) std::abort();
    if (whole.state == omega::ChunkedDecoder::State::done && (whole.body != split.body || whole.consumed != split.consumed))
        std::abort();
    return 0;
}

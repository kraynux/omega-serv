// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Fuzzing du filtre WAF (plan WAF natif, lot 1) : cible et User-Agent arbitraires, regles livrees (vecteurs).
// Aucune entree ne doit planter ; un texte prepare est toujours ASCII ; le decodage borne reste coherent.
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <string>
#include <string_view>

#include "engine.hpp"
#include "http_parser.hpp"
#include "util.hpp"
#include "waf_filter.hpp"

namespace {

std::shared_ptr<const omega::WafFilter> shipped_filter() {
    static const auto filter = [] {
        std::ifstream file(OMEGA_WAF_VECTORS_DIR "/waf_filter.json");
        std::stringstream text;
        text << file.rdbuf();
        const auto json = omega::parse_json(text.str());
        if (!json) __builtin_trap();
        return omega::WafFilter::from_json(*json);
    }();
    return filter;
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
    const std::string_view input(reinterpret_cast<const char*>(data), size);
    const std::size_t split = input.find('\n');
    omega::RequestHead head;
    head.method = "GET";
    head.target = std::string(input.substr(0, split));
    head.http_version = "HTTP/1.1";
    if (split != std::string_view::npos) head.headers.emplace_back("User-Agent", std::string(input.substr(split + 1)));
    omega::Request request;
    request.head = &head;
    omega::fill_request_target(request);
    const auto filter = shipped_filter();
    if (const auto texts = filter->prepare(request, false)) {
        for (const auto& text : *texts) {
            if (!text) continue;
            for (const char c : *text) {
                if (static_cast<unsigned char>(c) >= 0x80) __builtin_trap();  // le natif ne juge que de l'ASCII
            }
        }
        (void)filter->evaluate(*texts);
    }
    if (const auto once = omega::decode_ascii_for_inspection(head.target, 1)) {
        // une passe de plus ne peut que poursuivre le decodage de ce resultat
        const auto twice = omega::decode_ascii_for_inspection(head.target, 2);
        if (twice && *twice != *once && omega::decode_ascii_for_inspection(*once, 1) != twice) __builtin_trap();
    }
    return 0;
}

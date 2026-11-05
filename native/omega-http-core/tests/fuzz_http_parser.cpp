// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Fuzzing du parseur (plan §6) : aucune entree ne doit planter, deborder ou boucler.
//   cmake -S . -B build-fuzz -G Ninja -DCMAKE_CXX_COMPILER=clang++ -DOMEGA_FUZZ=ON && cmake --build build-fuzz
//   build-fuzz/fuzz_http_parser -max_total_time=300
#include <cstddef>
#include <cstdint>
#include <string_view>

#include "http_parser.hpp"

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
    const std::string_view input(reinterpret_cast<const char*>(data), size);
    omega::ParserLimits limits;
    limits.max_header_size = 4096;
    limits.max_request_line_size = 2048;
    for (bool eof : {false, true}) {
        const omega::ParseResult result = omega::parse_request_head(input, limits, eof);
        if (result.state == omega::ParseState::complete) {
            if (result.consumed > input.size()) __builtin_trap();
            (void)omega::body_framing(result.head, 1024);
        }
    }
    return 0;
}

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Fuzzing du decodeur de trames IPC (contrat §7) : aucune entree ne doit planter ni lire hors des bornes.
#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

#include "ipc.hpp"

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size) {
    omega::ipc::Frame frame;
    std::string error;
    if (omega::ipc::decode(std::string_view(reinterpret_cast<const char*>(data), size), frame, &error)) {
        // ce qui est accepte doit se re-encoder a l'identique
        const std::string again = omega::ipc::encode(frame);
        if (again != std::string_view(reinterpret_cast<const char*>(data), size)) __builtin_trap();
        (void)frame.unsigned_field(1);
    }
    return 0;
}

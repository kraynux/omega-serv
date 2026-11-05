// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Mode pilote par le superviseur (plan moteur C++ lot 3, contrat IPC §1-6) : canal `control` herite
// (--control-fd), poignee de main, configuration par generation (memfd scelle), sante, arret.
#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "config.hpp"
#include "server.hpp"

namespace omega {

// Capacites annoncees dans HELLO (contrat §3.1) : ce que ce binaire sait faire SANS Python.
std::vector<std::string> native_capabilities();

// Lit l'instantane d'une trame CONFIG : memfd recu (ferme ici dans tous les cas), taille et SHA-256 annonces,
// generation de l'en-tete egale a celle du JSON. nullptr + raison sinon.
std::shared_ptr<const Snapshot> snapshot_from_config_frame(std::uint32_t frame_generation, const std::string* size_field,
                                                           const std::string* sha_field, int memfd, std::string* error);

// Deroule toute la vie du processus en mode pilote. Code de sortie : 0 arret normal, 1 ecoute impossible,
// 2 configuration refusee au demarrage, 3 poignee de main refusee / absente.
int run_controlled(int control_fd, ServerOptions options, const char* binary_version);

}  // namespace omega

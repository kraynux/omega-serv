// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// omega-http-core : moteur HTTP natif d'omega-serv. Jamais lance a la main en production : le superviseur
// Python (omega-serv serve) le demarre, lui passe la configuration et le surveille (plan moteur C++ §2).
//
// Lot 3 - mode pilote (production) : omega-http-core --control-fd FD --listen-fd FD [--threads N]
//   poignee de main, configuration par generation, sante et arret par le canal de controle (control.cpp).
//
// Lot 2 - mode autonome (tests differentiels, mesures) :
//   omega-http-core --config instantane.json [--threads N] [--listen-fd FD]...
//   omega-http-core --check-config instantane.json      (structure seulement, code 0 / 2)
//   omega-http-core --version
// SIGTERM / SIGINT : arret propre (drainage borne) ; SIGHUP : relecture de l'instantane (nouvelle generation).
#include <signal.h>
#include <unistd.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "config.hpp"
#include "control.hpp"
#include "server.hpp"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr int kContractVersion = 1;

void usage() {
    std::fprintf(stderr,
                 "usage : omega-http-core --control-fd FD --listen-fd FD... [--threads N] [--data-fd FD...]\n"
                 "        omega-http-core --config FICHIER [--threads N] [--listen-fd FD]...\n"
                 "        omega-http-core --check-config FICHIER\n"
                 "        omega-http-core --version\n");
}

bool read_text_file(const std::string& path, std::string& out) {
    std::ifstream file(path, std::ios::binary);
    if (!file) return false;
    std::ostringstream buffer;
    buffer << file.rdbuf();
    out = buffer.str();
    return true;
}

std::shared_ptr<const omega::Snapshot> load_snapshot(const std::string& path, std::string* error) {
    std::string text;
    if (!read_text_file(path, text)) {
        *error = "lecture impossible : " + path;
        return nullptr;
    }
    return omega::parse_snapshot(text, error);
}

bool parse_int(const char* text, int& out) {
    char* end = nullptr;
    const long value = std::strtol(text, &end, 10);
    if (end == text || *end != '\0' || value < 0 || value > 1 << 20) return false;
    out = static_cast<int>(value);
    return true;
}

}  // namespace

int main(int argc, char** argv) {
    std::string config_path;
    bool check_only = false;
    int control_fd = -1;
    omega::ServerOptions options;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--version") {
            std::printf("omega-http-core %s (contrat IPC %d)\n", kVersion, kContractVersion);
            return 0;
        }
        if ((arg == "--config" || arg == "--check-config") && i + 1 < argc) {
            config_path = argv[++i];
            check_only = arg == "--check-config";
        } else if (arg == "--control-fd" && i + 1 < argc) {
            if (!parse_int(argv[++i], control_fd)) {
                usage();
                return 2;
            }
        } else if (arg == "--data-fd" && i + 1 < argc) {
            int fd = -1;
            if (!parse_int(argv[++i], fd)) {
                usage();
                return 2;
            }
            options.data_fds.push_back(fd);
        } else if (arg == "--threads" && i + 1 < argc) {
            if (!parse_int(argv[++i], options.threads)) {
                usage();
                return 2;
            }
        } else if (arg == "--listen-fd" && i + 1 < argc) {
            int fd = -1;
            if (!parse_int(argv[++i], fd)) {
                usage();
                return 2;
            }
            options.listen_fds.push_back(fd);
        } else {
            usage();
            return 2;
        }
    }
    if (control_fd >= 0) {
        if (!config_path.empty() || options.listen_fds.empty()) {  // pilote : socket toujours ouverte par le superviseur
            usage();
            return 2;
        }
        return omega::run_controlled(control_fd, options, kVersion);
    }
    if (config_path.empty()) {
        usage();
        return 2;
    }

    std::string error;
    auto snapshot = load_snapshot(config_path, &error);
    if (!snapshot) {
        std::fprintf(stderr, "omega-http-core : instantane refuse : %s\n", error.c_str());
        return 2;
    }
    if (check_only) return 0;

    // Signaux traites par un fil dedie (sigwait) : jamais de code non reentrant dans un gestionnaire.
    sigset_t signals;
    sigemptyset(&signals);
    sigaddset(&signals, SIGTERM);
    sigaddset(&signals, SIGINT);
    sigaddset(&signals, SIGHUP);
    pthread_sigmask(SIG_BLOCK, &signals, nullptr);
    signal(SIGPIPE, SIG_IGN);

    omega::Server server(snapshot, options);
    if (!server.listen(&error)) {
        std::fprintf(stderr, "omega-http-core : %s\n", error.c_str());
        return 1;
    }
    std::thread signal_thread([&] {
        while (true) {
            int received = 0;
            if (sigwait(&signals, &received) != 0) continue;
            if (received == SIGHUP) {
                std::string reload_error;
                if (auto next = load_snapshot(config_path, &reload_error)) {
                    server.install_snapshot(std::move(next));
                } else {
                    std::fprintf(stderr, "omega-http-core : rechargement refuse, generation conservee : %s\n",
                                 reload_error.c_str());
                }
                continue;
            }
            server.stop();
            return;
        }
    });
    const int forced = server.run();
    if (forced < 0) ::kill(::getpid(), SIGTERM);  // demarrage des fils rate : libere le fil des signaux
    signal_thread.join();
    return forced < 0 ? 1 : 0;
}

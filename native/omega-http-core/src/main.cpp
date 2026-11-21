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
//   omega-http-core --dump-proxy instantane.json        (section proxy telle que lue, JSON ; lot 3 du proxy natif)
//   omega-http-core --decode-responses                  (tests, lot 5 du proxy natif : reponses du backend lues
//                                                        sur l'entree, une par ligne « METHODE<TAB>HEX »)
//   omega-http-core --simulate-balance                  (tests, lot 6 : scenario JSON de choix de backend sur l'entree)
//   omega-http-core --version
// SIGTERM / SIGINT : arret propre (drainage borne) ; SIGHUP : relecture de l'instantane (nouvelle generation).
#include <signal.h>
#include <unistd.h>

#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstring>
#include <unordered_set>
#include <fstream>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "config.hpp"
#include "control.hpp"
#include "server.hpp"
#include "balance.hpp"
#include "upstream.hpp"
#include "util.hpp"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr int kContractVersion = 1;

void usage() {
    std::fprintf(stderr,
                 "usage : omega-http-core --control-fd FD --listen-fd FD... [--threads N] [--data-fd FD...]\n"
                 "        omega-http-core --config FICHIER [--threads N] [--listen-fd FD]...\n"
                 "        omega-http-core --check-config FICHIER\n"
                 "        omega-http-core --dump-proxy FICHIER   (section proxy lue, en JSON)\n"
                 "        omega-http-core --decode-responses     (tests : METHODE<TAB>HEX par ligne sur l'entree)\n"
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

std::string unhex(const std::string& hex) {
    std::string out;
    for (std::size_t i = 0; i + 1 < hex.size(); i += 2) out.push_back(static_cast<char>(std::stoi(hex.substr(i, 2), nullptr, 16)));
    return out;
}

std::string hex(std::string_view bytes) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string out;
    for (const char raw : bytes) {
        const auto ch = static_cast<unsigned char>(raw);
        out.push_back(digits[ch >> 4]);
        out.push_back(digits[ch & 15]);
    }
    return out;
}

// Plan proxy natif v2, lot 5 : « ok<TAB>statut<TAB>decoupage<TAB>corps hex<TAB>reste » ou « error ».
int decode_responses() {
    static constexpr const char* framings[] = {"none", "length", "chunked", "close"};
    std::string line;
    char buffer[1 << 16];
    std::string pending;
    while (true) {
        const std::size_t n = std::fread(buffer, 1, sizeof buffer, stdin);
        pending.append(buffer, n);
        if (n == 0) break;
    }
    std::istringstream input(pending);
    while (std::getline(input, line)) {
        const std::size_t tab = line.find('\t');
        if (tab == std::string::npos) continue;
        const auto result = omega::decode_upstream_response(unhex(line.substr(tab + 1)), line.substr(0, tab));
        if (!result.ok) {
            std::printf("error\n");
            continue;
        }
        std::printf("ok\t%d\t%s\t%s\t%zu\n", result.status, framings[static_cast<int>(result.framing)],
                    hex(result.body).c_str(), result.rest);
    }
    return 0;
}

// Plan proxy natif v2, lot 6 : {"proxy": section, "zone": prefixe, "steps": [...]} lu sur l'entree ; une ligne par
// « select » (cle du backend choisi, « capacity » ou « none »). Horloge virtuelle (« advance »). Compare au vrai
// resolve_upstream de Python par pytest.
int simulate_balance() {
    std::string text;
    char buffer[1 << 16];
    while (true) {
        const std::size_t n = std::fread(buffer, 1, sizeof buffer, stdin);
        if (n == 0) break;
        text.append(buffer, n);
    }
    std::string error;
    const auto root = omega::parse_json(text, &error);
    const omega::Json* section = root ? root->get("proxy") : nullptr;
    const auto proxy = section ? omega::parse_proxy_section(*section, &error) : std::nullopt;
    if (!proxy) {
        std::fprintf(stderr, "scenario refuse : %s\n", error.c_str());
        return 2;
    }
    const std::string prefix = root->str("zone");
    const omega::ProxyZoneSettings* zone = nullptr;
    for (const auto& candidate : proxy->zones) {
        if (candidate.prefix == prefix) zone = &candidate;
    }
    if (zone == nullptr) return 2;
    omega::BalanceRegistry registry;
    const auto balance = registry.zone(prefix);
    auto now = omega::BalanceClock::time_point{} + std::chrono::hours(1);
    for (const omega::Json& step : root->array("steps")) {
        const std::string op = step.str("op");
        const std::string key = step.str("key");
        if (op == "select") {
            omega::BalanceRequest request;
            request.client_ip = step.str("ip", "127.0.0.1");
            const omega::Json* headers = step.get("headers");
            request.header = [headers](std::string_view name) -> std::optional<std::string> {
                if (headers == nullptr || !headers->is_object()) return std::nullopt;
                for (const auto& [header, value] : headers->object()) {
                    if (header.size() == name.size() &&
                        std::equal(header.begin(), header.end(), name.begin(), [](char a, char b) {
                            return std::tolower(static_cast<unsigned char>(a)) == std::tolower(static_cast<unsigned char>(b));
                        }))
                        return value.as_string();
                }
                return std::nullopt;
            };
            std::unordered_set<std::string> exclude;
            if (const omega::Json* excluded = step.get("exclude"); excluded != nullptr && excluded->is_array()) {
                for (const omega::Json& item : step.array("exclude")) exclude.insert(item.as_string());
            }
            const auto selection = omega::select_backend(*balance, *zone, request, exclude, now);
            if (selection.result == omega::Selection::Result::chosen) {
                std::printf("%s\n", zone->upstreams[selection.index].key.c_str());
            } else {
                std::printf("%s\n", selection.result == omega::Selection::Result::at_capacity ? "capacity" : "none");
            }
        } else if (op == "release") {
            omega::release_backend(*balance->backend(key));
        } else if (op == "success") {
            omega::record_backend_success(*balance->backend(key), zone->healthy_after);
        } else if (op == "failure") {
            omega::record_backend_failure(*balance->backend(key), zone->unhealthy_after, now);
        } else if (op == "time") {
            omega::record_response_time(*balance->backend(key), step.num("seconds"));
        } else if (op == "advance") {
            now += std::chrono::duration_cast<omega::BalanceClock::duration>(std::chrono::duration<double>(step.num("seconds")));
        } else if (op == "event") {
            omega::apply_backend_event(registry, *proxy, prefix, step.str("name"), step.str("kind"), step.str("value"), now);
        }
    }
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    std::string config_path;
    bool check_only = false;
    bool dump_proxy = false;  // plan proxy natif v2, lot 3 : section proxy telle que lue (test differentiel)
    int control_fd = -1;
    omega::ServerOptions options;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--decode-responses") return decode_responses();
        if (arg == "--simulate-balance") return simulate_balance();
        if (arg == "--version") {
            std::printf("omega-http-core %s (contrat IPC %d)\n", kVersion, kContractVersion);
            return 0;
        }
        if ((arg == "--config" || arg == "--check-config" || arg == "--dump-proxy") && i + 1 < argc) {
            config_path = argv[++i];
            check_only = arg != "--config";
            dump_proxy = arg == "--dump-proxy";
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
    if (dump_proxy) {
        std::printf("%s\n", snapshot->proxy ? omega::dump_proxy_json(*snapshot->proxy).c_str() : "null");
        return 0;
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

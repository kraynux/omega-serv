// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Serveur epoll : T fils, une boucle epoll par fil, sockets d'ecoute partagees (EPOLLEXCLUSIVE : un seul fil
// reveille par connexion entrante). Une connexion vit dans le fil qui l'a acceptee, avec la generation de
// configuration active a son acceptation (contrat IPC §4 : les connexions en cours finissent avec la leur).
// Deroulement d'une connexion = asyncio_server.py::_handle_connection, etape par etape.
#pragma once

#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "config.hpp"

typedef struct ssl_ctx_st SSL_CTX;

namespace omega {

struct ServerOptions {
    int threads = 0;                 // 0 = coeurs disponibles
    std::vector<int> listen_fds;     // sockets deja ouvertes par le superviseur (sinon bind/port de la config)
    std::vector<int> data_fds;       // lot 4 : un canal INSPECT/VERDICT par fil (rang = rang du fil), vide = aucun
};

class Server {
public:
    Server(std::shared_ptr<const Snapshot> snapshot, ServerOptions options);
    ~Server();
    Server(const Server&) = delete;
    Server& operator=(const Server&) = delete;

    // Ouvre les sockets (si besoin) ; false + message si impossible.
    bool listen(std::string* error);
    // Boucle jusqu'a stop() puis drainage borne par shutdown_grace_period_seconds. Rend le nombre de
    // connexions fermees de force.
    int run();
    void stop();  // sur signal (async-signal-safe : ecrit dans un eventfd)
    void install_snapshot(std::shared_ptr<const Snapshot> snapshot);  // nouvelle generation
    void set_grace_period(double seconds) { grace_period_seconds_.store(seconds); }  // SHUTDOWN (avant stop())
    // DATA_ATTACH : nouveau canal de donnees pour le fil `index` (processus de securite relance). Adopte par le fil
    // a son prochain tour de boucle ; l'ancien est ferme, ses inspections en attente suivent on_error.
    void attach_data_channel(std::size_t index, int fd);

    // Compteurs du message HEALTH (contrat IPC §6).
    [[nodiscard]] std::size_t open_connections() const { return active_connections_.load(); }
    [[nodiscard]] std::uint64_t requests_served() const { return requests_served_.load(); }
    [[nodiscard]] std::uint64_t rejected_over_capacity() const { return rejected_over_capacity_.load(); }

    [[nodiscard]] std::shared_ptr<const Snapshot> snapshot() const { return snapshot_.load(); }

private:
    struct Worker;
    friend struct Worker;

    std::atomic<std::shared_ptr<const Snapshot>> snapshot_;
    ServerOptions options_;
    std::vector<int> listen_fds_;
    int stop_event_fd_ = -1;
    std::atomic<std::size_t> active_connections_{0};
    std::atomic<bool> stopping_{false};
    std::atomic<double> grace_period_seconds_{10};
    std::atomic<long long> force_deadline_{0};  // steady_clock, en ticks
    std::atomic<std::size_t> forced_closures_{0};
    std::atomic<std::uint64_t> requests_served_{0};
    std::atomic<std::uint64_t> rejected_over_capacity_{0};
    std::once_flag listen_shutdown_once_;
    std::shared_ptr<SSL_CTX> tls_context_;
    std::mutex data_mutex_;
    std::vector<int> pending_data_fds_;  // par fil : nouveau canal a adopter (-1 : rien)  // TLS direct : construit une fois au demarrage (change = redemarrage)
};

}  // namespace omega

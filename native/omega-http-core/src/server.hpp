// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Serveur epoll : T fils, une boucle epoll par fil, sockets d'ecoute partagees (EPOLLEXCLUSIVE : un seul fil
// reveille par connexion entrante). Une connexion vit dans le fil qui l'a acceptee, avec la generation de
// configuration active a son acceptation (contrat IPC §4 : les connexions en cours finissent avec la leur).
// Deroulement d'une connexion = asyncio_server.py::_handle_connection, etape par etape.
#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "balance.hpp"
#include "config.hpp"

typedef struct ssl_ctx_st SSL_CTX;
typedef struct ssl_st SSL;

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
    // Plan proxy natif v2, lot 4 (C2, S16, S19) : budgets du relais natif en cours d'usage, tous fils confondus. Chaque
    // reservation est rendue sur tous les chemins : au repos, ces compteurs reviennent a zero (verifie par les tests).
    [[nodiscard]] std::uint64_t proxy_pending_body() const { return proxy_pending_body_.load(); }
    [[nodiscard]] std::uint64_t proxy_inspections() const { return proxy_inspections_.load(); }
    [[nodiscard]] std::uint64_t upstream_connections() const { return upstream_connections_.load(); }
    [[nodiscard]] std::uint64_t proxy_relayed() const { return proxy_relayed_.load(); }
    // Plan tableau de bord web §9.5, lot 9b : octets recus des visiteurs et envoyes (cumuls, TLS compris)
    [[nodiscard]] std::uint64_t bytes_in() const { return bytes_in_.load(std::memory_order_relaxed); }
    [[nodiscard]] std::uint64_t bytes_out() const { return bytes_out_.load(std::memory_order_relaxed); }
    // Lot 5 (C8, S14, S19) : nouveaux essais (cumul) et connexions inactives du pool (comptees aussi dans
    // upstream_connections).
    [[nodiscard]] std::uint64_t upstream_retries() const { return upstream_retries_.load(); }
    [[nodiscard]] std::uint64_t upstream_idle() const { return upstream_idle_.load(); }

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
    std::atomic<std::uint64_t> proxy_pending_body_{0};
    std::atomic<std::uint64_t> proxy_inspections_{0};
    std::atomic<std::uint64_t> upstream_connections_{0};
    std::atomic<std::uint64_t> proxy_relayed_{0};
    std::atomic<std::uint64_t> bytes_in_{0};
    std::atomic<std::uint64_t> bytes_out_{0};
    std::atomic<std::uint64_t> upstream_retries_{0};
    std::atomic<std::uint64_t> upstream_retries_in_flight_{0};
    std::atomic<std::uint64_t> upstream_idle_{0};
    std::atomic<std::size_t> thread_count_{1};  // lot 5 : partage du plafond du pool entre les fils
    BalanceRegistry balance_registry_;  // lot 6 (C9) : sante et charge des backends, communes aux fils et aux generations
    std::once_flag listen_shutdown_once_;
    std::shared_ptr<SSL_CTX> tls_context_;
    // Plan proxy natif v2, lot 8 (C15) : contextes TLS vers les backends (0 : non verifie, 1 : verifie), construits une
    // fois, a la premiere generation qui en a besoin ; dernieres lignes « certificat refuse » par backend (une par
    // minute au plus, tous fils confondus).
    struct UpstreamTls {
        bool tried = false;
        std::shared_ptr<SSL_CTX> context;
        std::string error;
    };
    std::mutex upstream_tls_mutex_;
    UpstreamTls upstream_tls_[2];
    std::unordered_map<std::string, std::chrono::steady_clock::time_point> tls_failure_logged_;
    void prepare_upstream_tls(const Snapshot& snapshot);
    SSL_CTX* upstream_tls_context(bool verify, std::string* error);
    bool tls_failure_due(const std::string& key, std::chrono::steady_clock::time_point now);
    std::mutex data_mutex_;
    // Plan proxy natif v2, lot 3 (P6) : connexions confiees au fil 0 (dont le processus de securite est le n° 0)
    // pour /.omega-serv-admin/. Le fil qui les a acceptees les retire de son epoll, le fil 0 les reprend. Lot 9 : en
    // TLS direct aussi - la session OpenSSL suit la connexion (meme processus, jamais utilisee par deux fils a la fois).
    struct Transfer {
        int fd = -1;
        SSL* ssl = nullptr;  // lot 9 : session TLS directe, poignee de main faite (nullptr en clair)
        std::string peer_ip;
        std::string pending;  // octets deja lus (tete comprise), reanalyses par le fil 0
        int requests_served = 0;
        bool eof = false;
        std::shared_ptr<const Snapshot> snapshot;  // instantane de l'acceptation (contrat IPC §4)
    };
    std::mutex transfer_mutex_;
    std::vector<Transfer> transfers_;
    int transfer_event_fd_ = -1;
    std::vector<int> pending_data_fds_;  // par fil : nouveau canal a adopter (-1 : rien)  // TLS direct : construit une fois au demarrage (change = redemarrage)
};

}  // namespace omega

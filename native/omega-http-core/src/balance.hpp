// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Plan proxy natif v2, lot 6 : choix du backend et etat de sante du relais natif, copies exactes du proxy Python
// (reference : application/server/serve_proxy.py::resolve_upstream, domain/routing/proxy_zone.py::
// ProxyLoadBalancerState, domain/routing/proxy_health.py::ProxyHealthState).
//
// Etat COMMUN a tous les fils (C9) : capacite par backend, compteurs de least_connections, temps de reponse, sante et
// coupe-circuit, tenus dans un registre du serveur qui survit aux rechargements (cle : prefixe de zone + identite du
// backend, jamais sa position - meme regle que Python, §27.1). Le choix d'une zone se fait sous son verrou, reservation
// comprise : les plafonds (max_concurrent) sont exacts sur tous les fils, et une seule requete d'essai a demi ouverte
// part pour l'ensemble des fils (Q10, S19).
#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "config.hpp"

namespace omega {

using BalanceClock = std::chrono::steady_clock;

inline constexpr auto kPassiveRetry = std::chrono::seconds(10);  // proxy_health.PASSIVE_RETRY_SECONDS

enum class BackendManual { none, draining, maintenance };

struct BackendState {
    std::mutex mutex;  // sante, temps de reponse, score de charge
    int consecutive_failures = 0;
    int consecutive_successes = 0;
    bool down = false;
    BalanceClock::time_point down_since{};
    std::optional<BalanceClock::time_point> trial_started;
    BackendManual manual = BackendManual::none;
    std::optional<double> response_avg_seconds;
    std::optional<double> load_score;  // score lisse pousse par le processus n° 0 (Q5)
    BalanceClock::time_point load_at{};
    std::atomic<std::int64_t> active{0};  // requetes en cours (least_connections, capacite)
    // Tableau de bord par type d'instance (2026-11-16) : tentatives envoyees, echecs 502 et 504, depuis le demarrage.
    std::atomic<std::uint64_t> requests{0};
    std::atomic<std::uint64_t> errors_502{0};
    std::atomic<std::uint64_t> errors_504{0};

    [[nodiscard]] const char* status() const;  // up | down | draining | maintenance (appelant : mutex tenu)
};

struct ZoneBalance {
    std::mutex mutex;  // choix : round-robin, poids courants, capacite (verification et reservation ensemble)
    std::size_t round_robin_next = 0;
    std::unordered_map<std::string, std::int64_t> weighted_current;
    std::unordered_map<std::string, std::shared_ptr<BackendState>> backends;

    std::shared_ptr<BackendState> backend(const std::string& key);  // cree a la premiere demande (mutex tenu ou non)
    void retain(const std::unordered_set<std::string>& keys);         // lot 7 : backends retires oublies

private:
    std::mutex backends_mutex_;
};

class BalanceRegistry {
public:
    std::shared_ptr<ZoneBalance> zone(const std::string& prefix);
    // Lot 6 : etats des zones et backends de l'instantane, pour la remontee vers le processus n° 0 (administration).
    struct Report {
        std::string zone;
        std::string key;
        std::string name;
        std::string status;
        std::int64_t active = 0;
        std::uint64_t requests = 0;
        std::uint64_t errors_502 = 0;
        std::uint64_t errors_504 = 0;
        std::int64_t avg_us = -1;  // temps de reponse moyen en microsecondes, -1 : jamais sollicite
    };
    std::vector<Report> report(const ProxySettings& proxy);
    // Lot 7 (C13) : ne garde que les zones natives et les backends de `proxy` (nullptr : plus aucun).
    void retain(const ProxySettings* proxy);

private:
    std::mutex mutex_;
    std::unordered_map<std::string, std::shared_ptr<ZoneBalance>> zones_;
};

// Requete telle que le choix la voit : en-tetes (HttpHeaders.get : derniere valeur, texte UTF-8) et adresse cliente.
struct BalanceRequest {
    std::function<std::optional<std::string>(std::string_view)> header;
    std::string client_ip;
};

struct Selection {
    enum class Result { chosen, at_capacity, none } result = Result::none;
    std::size_t index = 0;  // dans zone.upstreams
    std::shared_ptr<BackendState> state;  // reserve (active + 1) quand chosen : rendu par release_backend
};

// resolve_upstream : regle d'en-tete > cookie collant > essai a demi ouvert > strategie parmi les sains, chaque etape
// filtree par eligibilite et capacite. `exclude` : identites deja tentees (nouvel essai, §18.4). at_capacity : au moins
// un sain, aucun avec de la place (503). none : aucun backend utilisable (noms non resolus, boucle) - 502.
Selection select_backend(ZoneBalance& balance, const ProxyZoneSettings& zone, const BalanceRequest& request,
                         const std::unordered_set<std::string>& exclude, BalanceClock::time_point now);

void release_backend(BackendState& state);

// _attempt_forward : succes (reponse lue), echec (connexion, delai, reponse invalide), temps de reponse.
void record_backend_success(BackendState& state, int healthy_after);
void record_backend_failure(BackendState& state, int unhealthy_after, BalanceClock::time_point now);
void record_response_time(BackendState& state, double seconds);

// Evenements du processus n° 0 (P6) : sonde active, score de charge, etat manuel - appliques a chaque adresse du nom.
// Rend false si le texte est inconnu.
bool apply_backend_event(BalanceRegistry& registry, const ProxySettings& proxy, std::string_view zone,
                         std::string_view name, std::string_view kind, std::string_view value,
                         BalanceClock::time_point now);

std::uint32_t crc32(std::string_view data);  // zlib.crc32

// parse_cookie_header(...).get(name) : derniere occurrence, valeur non nettoyee.
std::optional<std::string> cookie_value(std::string_view header, std::string_view name);

}  // namespace omega

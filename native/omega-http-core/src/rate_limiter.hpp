// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Limite de debit comptee par le moteur natif (OMEGA-SERV_PLAN-DETAILLE_WAF_NATIF.md, lot 6). Le natif voit toutes
// les requetes : il compte chacune (propre ou non) avec le MEME seau a jetons que Python
// (domain/security/waf/rate_limit.py::consume_token) et les MEMES regles (rate_limit_policy.py::select_rate_limit :
// dossier le plus long > IP/reseau le plus precis > global ; `requests == 0` = illimite). Il ne repond jamais 429
// lui-meme : un depassement part au processus Python (INSPECT, etiquette 11 = delai Retry-After), qui rejette et
// journalise comme aujourd'hui. Chaque requete envoyee a Python porte l'etiquette (0 = comptee, autorisee) :
// Python ne compte alors plus rien.
//
// Compteurs communs a tous les fils, gardes d'une generation de configuration a l'autre (cle = adresse + regle,
// comme Python) ; un seau inactif depuis plus d'une heure est retire (rate_limit_store.py, meme effet nul).
#pragma once

#include <array>
#include <cstdint>
#include <list>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "ip.hpp"
#include "util.hpp"

namespace omega {

struct SelectedRate {
    std::string key;
    std::int64_t requests = 0;
    std::int64_t window_seconds = 60;
};

// Section `waf_filter.rate_limit` de l'instantane (deja validee par Python ; regles IP/reseau deja filtrees par
// effective_source_policies). Structure invalide -> exception (instantane refuse).
class RatePolicy {
public:
    static std::shared_ptr<const RatePolicy> from_json(const Json& section);

    // select_rate_limit(path, ip, config) ; `path` = request.path (texte du chemin).
    [[nodiscard]] SelectedRate select(std::string_view path, std::string_view ip) const;
    // Feuille de style des pages d'erreur (GET/HEAD) : jamais comptee (evaluate_waf_request).
    [[nodiscard]] bool exempt(std::string_view method, std::string_view path) const;
    // Lot 1N : statut du refus (rate_limit.global.response_status) et source sure (alerte « throttle »).
    [[nodiscard]] int response_status() const { return response_status_; }
    [[nodiscard]] bool trusted_source(std::string_view ip) const;

private:
    struct PathRule { std::string prefix; std::int64_t requests; std::int64_t window; };
    struct SourceRule { std::string network_text; std::optional<IpNetwork> network; std::int64_t requests; std::int64_t window; };
    std::vector<PathRule> paths_;
    std::vector<std::string> path_prefixes_;
    std::vector<SourceRule> sources_;
    std::int64_t global_requests_ = 0;
    std::int64_t global_window_ = 60;
    std::string error_css_path_;
    int response_status_ = 429;
    std::vector<IpNetwork> trusted_;
};

class RateLimiter {
public:
    static RateLimiter& instance();
    // consume_token ; nullopt = autorisee, sinon delai Retry-After (int(retry) + 1, comme rate_limit_store.py).
    // `now` en secondes (horloge monotone).
    std::optional<std::uint32_t> check(const SelectedRate& rate, double now);
    void clear_for_tests();
    [[nodiscard]] std::size_t tracked_for_tests();

private:
    // Lot A (D33) : ordre d'usage par tranche (debut = la moins recente) pour remplacer la bonne adresse quand la
    // table est pleine. La liste pointe vers les cles de la table (noeuds stables) : aucune copie de la cle.
    using Order = std::list<const std::string*>;
    struct Bucket { double tokens; double last_refill; Order::iterator order; };
    struct Shard {
        std::mutex mutex;
        std::unordered_map<std::string, Bucket> buckets;
        Order order;
        double last_sweep = 0.0;
    };
    static constexpr std::size_t kShards = 64;
    std::array<Shard, kShards> shards_;
};

}  // namespace omega

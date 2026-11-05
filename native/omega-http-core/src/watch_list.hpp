// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Sources suivies (OMEGA-SERV_PLAN-DETAILLE_WAF_NATIF.md, lot 3) : adresses dont TOUTES les requetes vont au
// processus Python de securite jusqu'a une echeance (etat Active Defense, leurre affecte). Envoyees par Python (trame
// WATCH), ajoutees ou prolongees seulement : l'echeance seule les retire. Commune a tous les fils du moteur, gardee
// d'une generation de configuration a l'autre. Bornee : table pleine -> doute pour toutes les requetes (Python juge)
// tant qu'aucune place ne se libere.
#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_map>

namespace omega {

class WatchList {
public:
    static constexpr std::size_t kMaxEntries = 65536;

    static WatchList& instance();

    // `until` et `now` en secondes Unix. Faux si la table est pleine (entree refusee : doute pour tous).
    bool add(std::string ip, std::int64_t until, std::int64_t now);
    // Vrai : cette requete doit aller a Python (adresse suivie, ou table pleine).
    bool requires_python(std::string_view ip, std::int64_t now);
    std::size_t size();
    void clear_for_tests();

private:
    void purge_locked(std::int64_t now);

    std::mutex mutex_;
    std::unordered_map<std::string, std::int64_t> entries_;
    std::atomic<std::size_t> count_{0};  // lecture sans verrou du cas courant : table vide
    std::atomic<bool> overflow_{false};
};

}  // namespace omega

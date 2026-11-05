// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Blocklist du WAF lue par le natif (decision utilisateur 2026-11-02) : quand le controle de securite Python est
// indisponible et que la politique est fail-open, une adresse deja bannie reste refusee (451) au lieu de passer
// sans controle. En fonctionnement normal, c'est toujours le WAF Python qui decide (et ecrit ses alertes).
//
// Meme regle que domain/security/waf/blocklist.py::BlocklistIndex : reseau (ip_network strict=False) qui contient
// l'adresse, entree active tant que maintenant < expires_at (null = permanente). Date illisible : Python echoue sur
// la requete ; ici, en mode degrade, l'entree est tenue pour active (jamais un banni libere par une date abimee).
// Fichier relu s'il change (verifie au plus une fois par seconde) ; illisible : derniere liste valide gardee.
//
// Lot 8 (`known_clear`) : en fonctionnement normal, le natif dit au processus de securite « l'adresse n'est pas dans
// la blocklist », ce qui lui evite sa propre lecture. Ce n'est qu'une indication, donnee seulement quand la liste
// en memoire est EXACTEMENT celle du fichier a cet instant (stat a chaque appel, comme le JsonBlocklistStore) ;
// bannie, fichier illisible ou en cours d'ecriture, date abimee : pas d'indication, Python verifie et journalise.
#pragma once

#include <chrono>
#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "ip.hpp"

namespace omega {

class NativeBlocklist {
public:
    explicit NativeBlocklist(std::string path) : path_(std::move(path)) {}
    // Adresse (texte normalise) bannie a l'instant `now_unix_us` ?
    bool is_blocked(std::string_view ip, std::int64_t now_unix_us);
    // Vrai seulement si la liste lue correspond au fichier actuel ET ne contient aucune entree active pour `ip`.
    bool known_clear(std::string_view ip, std::int64_t now_unix_us);

    struct Entry {
        IpNetwork network;
        std::optional<std::int64_t> expires_unix_us;  // absent : permanente (ou date illisible : tenue active)
    };
    // Expose pour les tests : analyse d'un contenu de blocklist.json.
    static std::optional<std::vector<Entry>> parse(std::string_view json_text);
    static std::optional<std::int64_t> parse_iso_datetime_us(std::string_view text);

private:
    void refresh_if_due();
    void refresh();
    bool blocked_locked(const IpAddress& address, std::int64_t now_unix_us) const;

    std::string path_;
    std::mutex mutex_;
    std::vector<Entry> entries_;
    std::chrono::steady_clock::time_point next_check_{};
    std::int64_t file_mtime_ns_ = -1;
    std::int64_t file_size_ = -1;
    std::uint64_t file_inode_ = 0;
    bool current_ = false;  // entries_ = contenu du fichier tel qu'il est au dernier stat (ou fichier absent)
};

// Une instance par chemin, partagee entre fils et generations.
NativeBlocklist& blocklist_for(const std::string& path);

}  // namespace omega

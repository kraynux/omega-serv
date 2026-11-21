// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Blocklist du WAF lue par le natif (decision utilisateur 2026-11-02) : quand le controle de securite Python est
// indisponible et que la politique est fail-open, une adresse deja bannie reste refusee (451) au lieu de passer
// sans controle. En fonctionnement normal, c'est toujours le WAF Python qui decide (et ecrit ses alertes).
//
// Meme regle que domain/security/waf/blocklist.py::BlocklistIndex : reseau (ip_network strict=False) qui contient
// l'adresse, entree active tant que maintenant < expires_at (null = permanente). Date illisible : Python echoue sur
// la requete ; ici, en mode degrade, l'entree est tenue pour active (jamais un banni libere par une date abimee).
// Fichier relu s'il change (verifie au plus une fois par seconde pour is_blocked, a chaque appel pour known_clear) ;
// illisible : derniere liste valide gardee.
//
// Lot 8 (`known_clear`) : en fonctionnement normal, le natif dit au processus de securite « l'adresse n'est pas dans
// la blocklist », ce qui lui evite sa propre lecture. Ce n'est qu'une indication, donnee seulement quand la liste
// en memoire est EXACTEMENT celle du fichier a cet instant (stat a chaque appel, comme le JsonBlocklistStore) ;
// bannie, fichier illisible ou en cours d'ecriture, date abimee : pas d'indication, Python verifie et journalise.
#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "ip.hpp"

namespace omega {

class NativeBlocklist {
public:
    explicit NativeBlocklist(std::string path) : path_(std::move(path)) {}
    ~NativeBlocklist();
    NativeBlocklist(const NativeBlocklist&) = delete;
    NativeBlocklist& operator=(const NativeBlocklist&) = delete;
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
    // Tests : la fraicheur passe-t-elle par inotify (true) ou par un stat() a chaque appel (false) ?
    [[nodiscard]] bool watching_for_tests() const { return watching_.load(); }

private:
    // Plan proxy natif v2, lot 1N (D33, 2e moitie) : liste indexee, partagee en lecture seule entre les fils. Avant,
    // un verrou global tenu pendant le stat() et le parcours de TOUTES les entrees a chaque requete : 3,2 us par
    // requete avec 10 bannis, 9 us avec 1000, et un debit total qui BAISSAIT avec 4 fils (mesure du 2026-11-12).
    // Le stat() reste fait a chaque appel de known_clear (fraicheur inchangee), hors de tout verrou.
    //
    // Lot 1N (demande de l'auteur du 2026-11-12) : le stat() seul coutait encore 2,1 us. Quand c'est sur, le dossier
    // du fichier est surveille par inotify et chaque appel demande seulement au noyau si un evenement attend
    // (ioctl FIONREAD, 0,45 us). Aussi frais : le noyau met l'evenement en file PENDANT le rename / write de
    // l'ecrivain, avant son retour. Chaque dossier du chemin est surveille : le dossier du fichier pour le fichier,
    // chaque parent pour le seul element suivant du chemin (supprime, renomme, recree). Le noyau ne signale pas
    // toujours la suppression du dossier surveille lui-meme : sans les parents, un dossier recree passait inapercu
    // et la liste du natif restait l'ancienne (un ban ignore). Sinon (lien symbolique dans le chemin, systeme de
    // fichiers reseau, dossier absent, structure du chemin changee) : stat() a chaque appel, comme avant.
    struct Index {
        // Adresses exactes (/32, /128 : auto-ban, RIPOSTE, omega-jail) -> echeances ; reseaux : parcourus.
        std::unordered_map<std::string, std::vector<std::optional<std::int64_t>>> hosts;
        std::vector<Entry> networks;
        [[nodiscard]] bool blocked(const IpAddress& address, std::int64_t now_unix_us) const;
    };
    struct FileId {
        std::int64_t mtime_ns = -1;
        std::int64_t size = -1;
        std::uint64_t inode = 0;
        bool operator==(const FileId&) const = default;
    };
    struct State {
        std::shared_ptr<const Index> index = std::make_shared<Index>();
        std::optional<FileId> file;  // fichier dont l'index est la copie exacte ; absent : fichier absent ou illisible
        bool current = false;        // index = contenu du fichier au dernier stat (ou fichier absent)
    };
    // Etat a jour pour le fichier tel qu'il est maintenant (`stat` fait ici, relecture seulement s'il a change).
    // `reload_held` : reload_mutex_ deja tenu par l'appelant.
    State refreshed_state(bool reload_held = false);
    State loaded_state();
    // Etat a jour, par inotify si la surveillance est active, sinon par stat().
    State current_state();
    State reload_after_events();
    void try_start_watch();
    void stop_watch_locked();

    std::string path_;
    std::mutex mutex_;         // protege state_ (sections tres courtes : copie d'un shared_ptr)
    std::mutex reload_mutex_;  // une seule relecture du fichier a la fois
    State state_;
    std::chrono::steady_clock::time_point next_check_{};

    int inotify_fd_ = -1;                     // ferme seulement a la destruction (lu sans verrou par les fils)
    std::atomic<bool> watching_{false};
    std::atomic<bool> reloading_{false};      // un fil vide la file et relit : les autres l'attendent
    std::atomic<bool> needs_reload_{true};    // liste illisible ou etat inconnu : relire a chaque appel
    std::atomic<std::int64_t> next_watch_attempt_ns_{0};  // nouvel essai de surveillance au plus 1 fois par seconde
    struct Watch {
        int wd;
        std::string child;  // element du chemin qui compte dans ce dossier
        bool leaf;          // dossier du fichier : un evenement sur `child` = relire ; parent : chemin change
    };
    std::vector<Watch> watches_;                          // protege par reload_mutex_
};

// Une instance par chemin, partagee entre fils et generations.
NativeBlocklist& blocklist_for(const std::string& path);

}  // namespace omega

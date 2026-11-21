// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Blocklist lue par le natif (fail-open sans liberer un banni) : meme regle que BlocklistIndex.
#include "doctest.h"

#include <atomic>
#include <chrono>
#include <cstdio>
#include <filesystem>
#include <thread>
#include <vector>
#include <fstream>
#include <string>

#include "blocklist.hpp"

using omega::NativeBlocklist;

TEST_CASE("dates ISO de la blocklist (datetime.fromisoformat)") {
    CHECK(NativeBlocklist::parse_iso_datetime_us("1970-01-01T00:00:00+00:00") == 0);
    CHECK(NativeBlocklist::parse_iso_datetime_us("2026-11-02T23:14:03.983248+00:00") == INT64_C(1793661243983248));
    CHECK(NativeBlocklist::parse_iso_datetime_us("2026-11-03T00:14:03.983248+01:00") == INT64_C(1793661243983248));
    CHECK(NativeBlocklist::parse_iso_datetime_us("2026-11-02T23:14:03Z") == INT64_C(1793661243000000));
    CHECK(NativeBlocklist::parse_iso_datetime_us("2026-11-02T23:14:03") == INT64_C(1793661243000000));  // sans fuseau : UTC
    CHECK(NativeBlocklist::parse_iso_datetime_us("2026-11-02") == INT64_C(1793577600000000));
    CHECK_FALSE(NativeBlocklist::parse_iso_datetime_us("demain"));
    CHECK_FALSE(NativeBlocklist::parse_iso_datetime_us("2026-13-02"));
}

TEST_CASE("blocklist : reseaux, expiration, date illisible tenue active") {
    const std::string path = "/tmp/omega-native-blocklist-test.json";
    {
        std::ofstream out(path);
        out << R"({"version": 1, "entries": [
            {"network": "203.0.113.66/32", "expires_at": null},
            {"network": "198.51.100.0/24", "expires_at": "2000-01-01T00:00:00+00:00"},
            {"network": "2001:db8::/32", "expires_at": "2999-01-01T00:00:00+00:00"},
            {"network": "192.0.2.9/32", "expires_at": "date abimee"},
            {"network": "pas un reseau", "expires_at": null}]})";
    }
    NativeBlocklist list(path);
    const std::int64_t now = INT64_C(1793661243000000);
    CHECK(list.is_blocked("203.0.113.66", now));
    CHECK_FALSE(list.is_blocked("203.0.113.67", now));
    CHECK_FALSE(list.is_blocked("198.51.100.7", now));  // ban expire
    CHECK(list.is_blocked("2001:db8::1", now));
    CHECK(list.is_blocked("192.0.2.9", now));           // date illisible : jamais un banni libere
    CHECK_FALSE(list.is_blocked("pas une ip", now));
    std::remove(path.c_str());
}

TEST_CASE("blocklist : indication « non bannie » seulement sur l'etat actuel du fichier (lot 8)") {
    const std::string path = "/tmp/omega-native-blocklist-clear-test.json";
    std::remove(path.c_str());
    NativeBlocklist list(path);
    const std::int64_t now = INT64_C(1793661243000000);
    CHECK(list.known_clear("203.0.113.66", now));  // pas de fichier : aucun ban (comme le store Python)
    {
        std::ofstream out(path);
        out << R"({"version": 1, "entries": [{"network": "203.0.113.66/32", "expires_at": null},
                  {"network": "192.0.2.9/32", "expires_at": "date abimee"}]})";
    }
    CHECK_FALSE(list.known_clear("203.0.113.66", now));  // ban ajoute : vu a l'appel suivant, sans delai
    CHECK(list.known_clear("203.0.113.67", now));
    CHECK_FALSE(list.known_clear("192.0.2.9", now));     // date abimee : Python tranche
    CHECK_FALSE(list.known_clear("pas une ip", now));
    {
        std::ofstream out(path);
        out << R"({"version": 1, "entries": [)";       // ecriture en cours / fichier abime
    }
    CHECK_FALSE(list.known_clear("203.0.113.67", now));  // liste en memoire perimee : aucune indication
    {
        std::ofstream out(path);
        out << R"({"version": 1, "entries": []})";
    }
    CHECK(list.known_clear("203.0.113.66", now));        // ban retire : vu tout de suite
    std::remove(path.c_str());
}

TEST_CASE("blocklist : index des adresses exactes et des reseaux (lot 1N, D33)") {
    const std::string path = "/tmp/omega-native-blocklist-index-test.json";
    {
        std::ofstream out(path);
        out << R"({"version": 1, "entries": [
            {"network": "203.0.113.66/32", "expires_at": "2020-01-01T00:00:00+00:00"},
            {"network": "203.0.113.66", "expires_at": null},
            {"network": "198.51.100.7/32", "expires_at": "2020-01-01T00:00:00+00:00"},
            {"network": "10.1.0.0/16", "expires_at": null},
            {"network": "::cb00:7142/128", "expires_at": null},
            {"network": "2001:db8::/32", "expires_at": "2099-01-01T00:00:00+00:00"}]})";
    }
    NativeBlocklist list(path);
    const std::int64_t now = INT64_C(1793661243000000);
    CHECK_FALSE(list.known_clear("203.0.113.66", now));  // une entree expiree, une active : bannie
    CHECK(list.known_clear("198.51.100.7", now));        // seule entree expiree
    CHECK_FALSE(list.known_clear("10.1.200.3", now));    // reseau
    CHECK(list.known_clear("10.2.0.1", now));
    CHECK_FALSE(list.known_clear("::cb00:7142", now));   // IPv6 exacte
    CHECK(list.known_clear("::cb00:7143", now));
    CHECK(list.known_clear("203.0.113.67", now));        // 203.0.113.66 en IPv4 != ::cb00:7142 en IPv6
    CHECK_FALSE(list.known_clear("2001:db8:1::5", now));
    CHECK(list.is_blocked("203.0.113.66", now));
    CHECK_FALSE(list.is_blocked("198.51.100.7", now));
    std::remove(path.c_str());
}

namespace {

void write_bans(const std::string& path, const std::string& networks_json) {
    const std::string tmp = path + ".tmp";
    {
        std::ofstream out(tmp);
        out << R"({"version": 1, "entries": [)" << networks_json << "]}";
    }
    std::rename(tmp.c_str(), path.c_str());  // comme os.replace cote Python
}

std::string ban_json(const std::string& network) {
    return R"({"network": ")" + network + R"(", "expires_at": null})";
}

}  // namespace

TEST_CASE("blocklist : fraicheur par inotify, aussi stricte que stat (lot 1N)") {
    const std::string dir = "/tmp/omega-native-blocklist-watch-test";
    const std::string path = dir + "/blocklist.json";
    std::filesystem::remove_all(dir);
    std::filesystem::create_directories(dir);
    NativeBlocklist list(path);
    const std::int64_t now = INT64_C(1793661243000000);
    CHECK(list.known_clear("203.0.113.66", now));
    CHECK(list.known_clear("203.0.113.66", now));
    CHECK(list.watching_for_tests());                    // /tmp local : surveillance active
    for (int round = 0; round < 50; ++round) {           // remplacement vu des l'appel suivant, sans attente
        write_bans(path, ban_json("203.0.113.66/32"));
        CHECK_FALSE(list.known_clear("203.0.113.66", now));
        CHECK(list.is_blocked("203.0.113.66", now));
        write_bans(path, "");
        CHECK(list.known_clear("203.0.113.66", now));
    }
    {
        std::ofstream out(path);                         // ecriture sur place, fichier abime
        out << R"({"version": 1, "entries": [)";
    }
    CHECK_FALSE(list.known_clear("203.0.113.67", now));  // aucune indication tant qu'il est illisible
    CHECK_FALSE(list.known_clear("203.0.113.67", now));
    write_bans(path, "");
    CHECK(list.known_clear("203.0.113.67", now));
    // Dossier supprime puis recree, sans aucun appel entre les deux : le nouveau ban doit etre vu.
    std::filesystem::remove_all(dir);
    std::filesystem::create_directories(dir);
    write_bans(path, ban_json("203.0.113.66/32"));
    CHECK_FALSE(list.known_clear("203.0.113.66", now));
    CHECK_FALSE(list.watching_for_tests());              // structure du chemin changee : stat() a chaque appel
    write_bans(path, "");
    CHECK(list.known_clear("203.0.113.66", now));
    std::this_thread::sleep_for(std::chrono::milliseconds(1100));
    CHECK(list.known_clear("203.0.113.66", now));
    CHECK(list.watching_for_tests());                    // surveillance reprise sur le nouveau dossier
    write_bans(path, ban_json("203.0.113.66/32"));
    CHECK_FALSE(list.known_clear("203.0.113.66", now));
    // Parent renomme et remplace (mv var var.old ; mkdir var) : meme exigence.
    const std::string parent = dir + "/var";
    const std::string deep = parent + "/blocklist.json";
    std::filesystem::create_directories(parent);
    write_bans(deep, "");
    NativeBlocklist nested(deep);
    CHECK(nested.known_clear("203.0.113.66", now));
    CHECK(nested.known_clear("203.0.113.66", now));
    CHECK(nested.watching_for_tests());
    std::filesystem::rename(parent, dir + "/var.old");
    std::filesystem::create_directories(parent);
    write_bans(deep, ban_json("203.0.113.66/32"));
    CHECK_FALSE(nested.known_clear("203.0.113.66", now));
    std::filesystem::remove_all(dir);
}

TEST_CASE("blocklist : lien symbolique ou dossier absent -> stat() a chaque appel (lot 1N)") {
    const std::string dir = "/tmp/omega-native-blocklist-link-test";
    std::filesystem::remove_all(dir);
    std::filesystem::create_directories(dir + "/real");
    const std::string target = dir + "/real/blocklist.json";
    const std::string link = dir + "/blocklist.json";
    write_bans(target, "");
    std::filesystem::create_symlink(target, link);
    NativeBlocklist linked(link);
    const std::int64_t now = INT64_C(1793661243000000);
    CHECK(linked.known_clear("203.0.113.66", now));
    CHECK(linked.known_clear("203.0.113.66", now));
    CHECK_FALSE(linked.watching_for_tests());
    write_bans(target, ban_json("203.0.113.66/32"));     // la cible change : aucun evenement dans le dossier du lien
    CHECK_FALSE(linked.known_clear("203.0.113.66", now));

    const std::string later = dir + "/plus-tard/blocklist.json";
    NativeBlocklist missing(later);
    CHECK(missing.known_clear("203.0.113.66", now));
    CHECK_FALSE(missing.watching_for_tests());
    std::filesystem::create_directories(dir + "/plus-tard");
    write_bans(later, ban_json("203.0.113.66/32"));
    CHECK_FALSE(missing.known_clear("203.0.113.66", now));
    std::this_thread::sleep_for(std::chrono::milliseconds(1100));  // nouvel essai de surveillance apres 1 s
    CHECK_FALSE(missing.known_clear("203.0.113.66", now));
    CHECK(missing.watching_for_tests());
    write_bans(later, "");
    CHECK(missing.known_clear("203.0.113.66", now));
    std::filesystem::remove_all(dir);
}

TEST_CASE("blocklist : jamais de reponse perimee apres le retour du rename, 4 fils (lot 1N)") {
    const std::string dir = "/tmp/omega-native-blocklist-race-test";
    const std::string path = dir + "/blocklist.json";
    std::filesystem::remove_all(dir);
    std::filesystem::create_directories(dir);
    write_bans(path, "");
    NativeBlocklist list(path);
    const std::int64_t now = INT64_C(1793661243000000);
    (void)list.known_clear("203.0.113.66", now);
    (void)list.known_clear("203.0.113.66", now);
    REQUIRE(list.watching_for_tests());
    std::atomic<int> version{0};  // impaire : 203.0.113.66 bannie ; publiee APRES le rename
    std::atomic<bool> stop{false};
    std::atomic<long> stale{0};
    std::atomic<long> checked{0};
    std::atomic<int> seen{0};  // derniere version verifiee par un lecteur
    std::vector<std::thread> readers;
    for (int t = 0; t < 4; ++t) {
        readers.emplace_back([&] {
            while (!stop.load()) {
                const int before = version.load();
                if (before < 0) continue;
                const bool clear = list.known_clear("203.0.113.66", now);
                if (version.load() != before) continue;  // remplacement pendant l'appel : les deux reponses sont justes
                ++checked;
                if (clear == (before % 2 == 1)) ++stale;
                seen.store(before);
            }
        });
    }
    int covered = 0;
    for (int k = 1; k <= 400; ++k) {
        version.store(-k);  // remplacement en cours : toute verification qui le chevauche est ignoree
        write_bans(path, k % 2 == 1 ? ban_json("203.0.113.66/32") : "");
        version.store(k);
        // Lot 11 : seuil relatif - on attend qu'un lecteur ait verifie cette version (au plus 100 ms), au lieu
        // d'un nombre fixe de verifications que la charge de la machine (ASan, suite en parallele) faisait manquer.
        const auto limit = std::chrono::steady_clock::now() + std::chrono::milliseconds(100);
        while (seen.load() != k && std::chrono::steady_clock::now() < limit) std::this_thread::yield();
        if (seen.load() == k) ++covered;
    }
    stop.store(true);
    for (auto& reader : readers) reader.join();
    MESSAGE("verifications : " << checked.load() << ", versions verifiees : " << covered << "/400");
    CHECK(covered >= 360);
    CHECK(stale.load() == 0);
    std::filesystem::remove_all(dir);
}

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Blocklist lue par le natif (fail-open sans liberer un banni) : meme regle que BlocklistIndex.
#include "doctest.h"

#include <cstdio>
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

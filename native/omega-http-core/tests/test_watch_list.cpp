// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Sources suivies (plan WAF natif, lot 3).
#include "doctest.h"

#include <string>

#include "watch_list.hpp"

TEST_CASE("sources suivies : echeance, prolongation, jamais raccourcie") {
    auto& list = omega::WatchList::instance();
    list.clear_for_tests();
    CHECK_FALSE(list.requires_python("203.0.113.1", 1000));
    CHECK(list.add("203.0.113.1", 1100, 1000));
    CHECK(list.requires_python("203.0.113.1", 1050));
    CHECK_FALSE(list.requires_python("203.0.113.2", 1050));
    CHECK(list.add("203.0.113.1", 1080, 1050));  // plus courte : ignoree
    CHECK(list.requires_python("203.0.113.1", 1090));
    CHECK(list.add("203.0.113.1", 1200, 1090));  // prolongee
    CHECK(list.requires_python("203.0.113.1", 1150));
    CHECK_FALSE(list.requires_python("203.0.113.1", 1200));  // echue : retiree
    CHECK(list.size() == 0);
    CHECK(list.add("2001:db8::1", 999, 1000));  // deja echue : rien
    CHECK(list.size() == 0);
}

TEST_CASE("sources suivies : table pleine -> tout va a Python, jusqu'a ce qu'une place se libere") {
    auto& list = omega::WatchList::instance();
    list.clear_for_tests();
    for (std::size_t i = 0; i < omega::WatchList::kMaxEntries; ++i) {
        REQUIRE(list.add("10." + std::to_string(i >> 16) + "." + std::to_string((i >> 8) & 255) + "." +
                             std::to_string(i & 255), 2000, 1000));
    }
    CHECK_FALSE(list.add("192.0.2.1", 2000, 1000));
    CHECK(list.requires_python("198.51.100.7", 1500));  // inconnue, mais table pleine
    CHECK_FALSE(list.requires_python("198.51.100.7", 2000));  // tout est echu : place liberee
    CHECK(list.add("192.0.2.1", 3000, 2000));
    CHECK(list.size() == 1);
    list.clear_for_tests();
}

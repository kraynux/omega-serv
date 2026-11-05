// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "doctest.h"

#include "util.hpp"

namespace {

std::string sha256_b64(std::string_view data) {
    const auto digest = omega::sha256(data);
    return omega::base64_encode(digest.data(), digest.size());
}

}  // namespace

TEST_CASE("SHA-256 + base64 : vecteurs FIPS 180-4 (comme hashlib + base64 de Python)") {
    CHECK(sha256_b64("") == "47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=");
    CHECK(sha256_b64("abc") == "ungWv48Bz+pBQUDeXa4iI7ADYaOWF3qctBD/YfIAFa0=");
    CHECK(sha256_b64("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq") ==
          "JI1qYdIGOLjlwCaTDD5gOaM85Flk/yFn9uzt1BnbBsE=");
    CHECK(sha256_b64(std::string(1000000, 'a')) == "zcduXJkU+5KBocfihNc+Z/GAmkiklyAOBG05zMcRLNA=");
    // longueurs aux frontieres de bloc (55, 56, 63, 64 octets)
    CHECK(sha256_b64(std::string(55, 'x')).size() == 44);
    CHECK(sha256_b64(std::string(56, 'x')) != sha256_b64(std::string(55, 'x')));
}

TEST_CASE("base64 : bourrage") {
    const std::uint8_t one[] = {'f'};
    const std::uint8_t two[] = {'f', 'o'};
    CHECK(omega::base64_encode(one, 1) == "Zg==");
    CHECK(omega::base64_encode(two, 2) == "Zm8=");
}

TEST_CASE("JSON strict") {
    const auto doc = omega::parse_json(R"({"a": 1.5, "b": [true, null, "x\u00e9\ud83d\ude00"], "c": {"d": "e"}})");
    REQUIRE(doc);
    CHECK(doc->num("a") == 1.5);
    CHECK(doc->array("b").size() == 3);
    CHECK(doc->array("b")[2].as_string() == "x\xc3\xa9\xf0\x9f\x98\x80");
    CHECK(doc->get("c")->str("d") == "e");
    std::string error;
    CHECK_FALSE(omega::parse_json("{\"a\": 1,}", &error));
    CHECK_FALSE(omega::parse_json("[01]"));
    CHECK_FALSE(omega::parse_json("\"\\ud800\""));
    CHECK_FALSE(omega::parse_json("{} x"));
    CHECK_FALSE(omega::parse_json(std::string(100, '[') + std::string(100, ']')));
}

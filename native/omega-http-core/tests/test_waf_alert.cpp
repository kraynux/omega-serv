// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Lot 1N (D36) : pieces de la ligne waf-alerts du natif (le contrat complet est dans les vecteurs `wafalert`).
#include "doctest.h"

#include "waf_alert.hpp"

TEST_CASE("waf_alert : decodage UTF-8 comme CPython (errors=replace)") {
    CHECK(omega::utf8_decode_replace("\xc3\xa9") == "\xc3\xa9");
    CHECK(omega::utf8_decode_replace("\xe0\x80") == "\xef\xbf\xbd\xef\xbf\xbd");  // E0 puis 80 : deux remplacements
    CHECK(omega::utf8_decode_replace("\xf0\x90\x80z") == "\xef\xbf\xbdz");          // sous-partie maximale : un seul
    CHECK(omega::utf8_decode_replace("\xed\xa0\x80") == "\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd");  // demi-codet refuse
}

TEST_CASE("waf_alert : redaction du corps de formulaire") {
    CHECK(omega::redact_form_urlencoded_body("user=a&password=s") == "user=a&password=%2A%2A%2AREDACTED%2A%2A%2A");
    CHECK(omega::redact_form_urlencoded_body("{\"password\": 1}") == "{\"password\": 1}");  // pas un formulaire
    CHECK(omega::redact_form_urlencoded_body("a=b+c%2Bd") == "a=b+c%2Bd");
}

TEST_CASE("waf_alert : horodatage et duree au format Python") {
    CHECK(omega::iso_utc_timestamp(0) == "1970-01-01T00:00:00+00:00");
    CHECK(omega::iso_utc_timestamp(1500001) == "1970-01-01T00:00:01.500001+00:00");
    CHECK(omega::python_float_3(0.0) == "0.0");
    CHECK(omega::python_float_3(0.0125) == "0.013");  // 0.0125 vaut un peu plus en binaire, comme round()
    CHECK(omega::python_float_3(2.675) == "2.675");
    CHECK(omega::python_float_3(2.0) == "2.0");
}

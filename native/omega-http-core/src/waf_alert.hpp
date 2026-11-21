// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Plan proxy natif v2, lot 1N (D36, P4) : ligne `waf-alerts` des refus que le natif decide seul (adresse bannie
// ou limite de debit depassee pendant une indisponibilite du controle en fail-open). Meme JSON que
// domain/logging/waf_alert_format.py::format_waf_alert_line - memes cles, meme ordre, memes plafonds,
// json.dumps(ensure_ascii=False) - lu par les failregex d'omega-jail et par RIPOSTE.
#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace omega {

// Section `inspect.waf_alerts` de l'instantane (WafLoggingConfig + chemin absolu du journal).
struct WafAlertSettings {
    std::string path;
    std::size_t max_path_chars = 2048;
    std::size_t max_user_agent_chars = 120;
    bool include_body_excerpt = false;
    std::size_t body_excerpt_max_bytes = 0;
};

// Textes en UTF-8 (str Python) ; `body` : octets bruts captures (ceux que Python recoit dans request.body).
struct WafAlert {
    std::int64_t unix_us = 0;
    std::string request_id;
    std::string remote_ip;
    std::string method;
    std::string path;
    std::optional<std::string> user_agent;
    std::string action;  // "block" ou "throttle"
    std::string stage;   // "blocklist" ou "rate_limit"
    int status_code = 0;
    std::string log_level = "warning";
    double duration_ms = 0.0;
    std::optional<std::string> body;
};

std::string format_waf_alert_line(const WafAlert& alert, const WafAlertSettings& settings);

// Pieces exposees pour les tests (memes noms que les fonctions Python imitees).
std::string utf8_decode_replace(std::string_view bytes);              // bytes.decode("utf-8", "replace")
std::string redact_form_urlencoded_body(std::string_view text_utf8);  // body_redaction.py (champs par defaut)
std::string json_string(std::string_view utf8);                       // json.dumps(str, ensure_ascii=False)
std::string iso_utc_timestamp(std::int64_t unix_us);                  // datetime(..., timezone.utc).isoformat()
std::string python_float_3(double value);                              // repr(round(value, 3))

}  // namespace omega

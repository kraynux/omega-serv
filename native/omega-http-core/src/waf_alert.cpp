// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "waf_alert.hpp"

#include <array>
#include <cstdio>
#include <ctime>
#include <utility>
#include <vector>

#include "text.hpp"

namespace omega {

namespace {

void append_replacement(std::string& out) { out += "\xEF\xBF\xBD"; }  // U+FFFD

int hex_value(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// urllib.parse._unquote_impl sur une suite ASCII : `%` suivi de deux chiffres hexadecimaux -> octet, sinon garde.
std::string unquote_ascii_run(std::string_view run) {
    std::string bytes;
    bytes.reserve(run.size());
    for (std::size_t i = 0; i < run.size(); ++i) {
        if (run[i] == '%' && i + 2 < run.size() && hex_value(run[i + 1]) >= 0 && hex_value(run[i + 2]) >= 0) {
            bytes.push_back(static_cast<char>(hex_value(run[i + 1]) * 16 + hex_value(run[i + 2])));
            i += 2;
        } else {
            bytes.push_back(run[i]);
        }
    }
    return bytes;
}

// urllib.parse.unquote(s, "utf-8", "replace") : chaque suite ASCII est decodee a part, le reste garde tel quel.
std::string unquote(std::string_view text) {
    if (text.find('%') == std::string_view::npos) return std::string(text);
    std::string out;
    std::size_t i = 0;
    while (i < text.size()) {
        std::size_t j = i;
        if (static_cast<unsigned char>(text[i]) < 0x80) {
            while (j < text.size() && static_cast<unsigned char>(text[j]) < 0x80) ++j;
            out += utf8_decode_replace(unquote_ascii_run(text.substr(i, j - i)));
        } else {
            while (j < text.size() && static_cast<unsigned char>(text[j]) >= 0x80) ++j;
            out.append(text.substr(i, j - i));
        }
        i = j;
    }
    return out;
}

std::string unquote_plus(std::string_view text) {
    std::string spaced(text);
    for (char& c : spaced) {
        if (c == '+') c = ' ';
    }
    return unquote(spaced);
}

// urllib.parse.quote_plus(s, safe="") : UTF-8, toujours surs A-Z a-z 0-9 _ . - ~, espace -> +, le reste %XX.
std::string quote_plus(std::string_view utf8) {
    static constexpr char kHex[] = "0123456789ABCDEF";
    std::string out;
    out.reserve(utf8.size());
    for (char ch : utf8) {
        const auto c = static_cast<unsigned char>(ch);
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '.' ||
            c == '-' || c == '~') {
            out.push_back(static_cast<char>(c));
        } else if (c == ' ') {
            out.push_back('+');
        } else {
            out.push_back('%');
            out.push_back(kHex[c >> 4]);
            out.push_back(kHex[c & 0x0f]);
        }
    }
    return out;
}

// str.lower() == champ sensible : les champs par defaut sont ASCII ; seul le signe kelvin (U+212A) devient une
// lettre ASCII en minuscule (« k »), il compte donc comme « k » ici aussi.
bool is_sensitive_field(std::string_view key) {
    static const std::array<std::string_view, 10> kFields = {
        "password", "passwd", "pwd", "token", "secret", "api_key", "apikey", "access_token", "refresh_token",
        "authorization"};
    std::string lowered;
    for (std::size_t i = 0; i < key.size(); ++i) {
        const auto c = static_cast<unsigned char>(key[i]);
        if (c == 0xE2 && i + 2 < key.size() && static_cast<unsigned char>(key[i + 1]) == 0x84 &&
            static_cast<unsigned char>(key[i + 2]) == 0xAA) {
            lowered.push_back('k');
            i += 2;
        } else if (c >= 'A' && c <= 'Z') {
            lowered.push_back(static_cast<char>(c - 'A' + 'a'));
        } else if (c >= 0x80) {
            return false;  // tout autre caractere non ASCII reste non ASCII en minuscule : aucun champ ne correspond
        } else {
            lowered.push_back(static_cast<char>(c));
        }
    }
    for (std::string_view field : kFields) {
        if (lowered == field) return true;
    }
    return false;
}

void append_two_digits(std::string& out, unsigned value) {
    out.push_back(static_cast<char>('0' + value / 10));
    out.push_back(static_cast<char>('0' + value % 10));
}

}  // namespace

std::string utf8_decode_replace(std::string_view bytes) {
    // Decodeur UTF-8 de CPython (errors="replace") : un U+FFFD par sous-partie maximale invalide (Unicode 3.9).
    std::string out;
    out.reserve(bytes.size());
    std::size_t i = 0;
    const std::size_t n = bytes.size();
    while (i < n) {
        const auto b = static_cast<unsigned char>(bytes[i]);
        if (b < 0x80) {
            out.push_back(static_cast<char>(b));
            ++i;
            continue;
        }
        std::size_t need = 0;
        unsigned char low = 0x80;
        unsigned char high = 0xBF;
        if (b >= 0xC2 && b <= 0xDF) {
            need = 1;
        } else if (b >= 0xE0 && b <= 0xEF) {
            need = 2;
            if (b == 0xE0) low = 0xA0;
            if (b == 0xED) high = 0x9F;
        } else if (b >= 0xF0 && b <= 0xF4) {
            need = 3;
            if (b == 0xF0) low = 0x90;
            if (b == 0xF4) high = 0x8F;
        } else {
            append_replacement(out);
            ++i;
            continue;
        }
        std::size_t matched = 0;
        while (matched < need && i + 1 + matched < n) {
            const auto next = static_cast<unsigned char>(bytes[i + 1 + matched]);
            const unsigned char lo = matched == 0 ? low : 0x80;
            const unsigned char hi = matched == 0 ? high : 0xBF;
            if (next < lo || next > hi) break;
            ++matched;
        }
        if (matched == need) {
            out.append(bytes.substr(i, need + 1));
        } else {
            append_replacement(out);
        }
        i += 1 + matched;
    }
    return out;
}

std::string redact_form_urlencoded_body(std::string_view text) {
    if (text.empty() || text.find('=') == std::string_view::npos) return std::string(text);
    std::vector<std::pair<std::string, std::string>> pairs;
    std::size_t start = 0;
    while (start <= text.size()) {
        const std::size_t end = std::min(text.find('&', start), text.size());
        const std::string_view field = text.substr(start, end - start);
        const std::size_t eq = field.find('=');
        // parse_qsl(keep_blank_values=False) : champ vide, sans `=` ou a valeur vide -> ignore.
        if (!field.empty() && eq != std::string_view::npos && eq + 1 < field.size()) {
            pairs.emplace_back(unquote_plus(field.substr(0, eq)), unquote_plus(field.substr(eq + 1)));
        }
        start = end + 1;
    }
    if (pairs.empty()) return std::string(text);
    std::string out;
    for (std::size_t k = 0; k < pairs.size(); ++k) {
        if (k > 0) out.push_back('&');
        out += quote_plus(pairs[k].first);
        out.push_back('=');
        out += quote_plus(is_sensitive_field(pairs[k].first) ? std::string_view("***REDACTED***") : pairs[k].second);
    }
    return out;
}

std::string json_string(std::string_view utf8) {
    std::string out = "\"";
    for (char ch : utf8) {
        const auto c = static_cast<unsigned char>(ch);
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            default:
                if (c < 0x20) {
                    char escaped[8];
                    std::snprintf(escaped, sizeof escaped, "\\u%04x", c);
                    out += escaped;
                } else {
                    out.push_back(static_cast<char>(c));
                }
        }
    }
    out.push_back('"');
    return out;
}

std::string iso_utc_timestamp(std::int64_t unix_us) {
    std::int64_t seconds = unix_us / 1000000;
    std::int64_t micros = unix_us % 1000000;
    if (micros < 0) {
        micros += 1000000;
        seconds -= 1;
    }
    const auto t = static_cast<std::time_t>(seconds);
    std::tm tm{};
    gmtime_r(&t, &tm);
    char base[32];
    std::snprintf(base, sizeof base, "%04d-", tm.tm_year + 1900);
    std::string out = base;
    append_two_digits(out, static_cast<unsigned>(tm.tm_mon + 1));
    out.push_back('-');
    append_two_digits(out, static_cast<unsigned>(tm.tm_mday));
    out.push_back('T');
    append_two_digits(out, static_cast<unsigned>(tm.tm_hour));
    out.push_back(':');
    append_two_digits(out, static_cast<unsigned>(tm.tm_min));
    out.push_back(':');
    append_two_digits(out, static_cast<unsigned>(tm.tm_sec));
    if (micros != 0) {  // isoformat() omet les microsecondes nulles
        char fraction[8];
        std::snprintf(fraction, sizeof fraction, ".%06lld", static_cast<long long>(micros));
        out += fraction;
    }
    out += "+00:00";
    return out;
}

std::string python_float_3(double value) {
    char buffer[64];
    std::snprintf(buffer, sizeof buffer, "%.3f", value);
    std::string out = buffer;
    while (out.size() > 1 && out.back() == '0' && out[out.size() - 2] != '.') out.pop_back();
    return out;
}

std::string format_waf_alert_line(const WafAlert& alert, const WafAlertSettings& settings) {
    std::optional<std::string> body_excerpt;
    if (settings.include_body_excerpt && alert.body && !alert.body->empty()) {
        const std::string redacted = redact_form_urlencoded_body(utf8_decode_replace(*alert.body));
        std::string taken(utf8_take(redacted, settings.body_excerpt_max_bytes));
        if (!taken.empty()) body_excerpt = std::move(taken);
    }
    std::string line = "{\"timestamp\": " + json_string(iso_utc_timestamp(alert.unix_us));
    line += ", \"request_id\": " + json_string(sanitize_log_field(alert.request_id, 64));
    line += ", \"remote_ip\": " + json_string(sanitize_log_field(alert.remote_ip, 64));
    line += ", \"method\": " + json_string(sanitize_log_field(alert.method, 16));
    line += ", \"path\": " + json_string(sanitize_log_field(alert.path, settings.max_path_chars));
    line += ", \"user_agent\": ";
    line += alert.user_agent && !alert.user_agent->empty()
                ? json_string(sanitize_log_field(*alert.user_agent, settings.max_user_agent_chars))
                : std::string("null");
    line += ", \"action\": " + json_string(alert.action);
    line += ", \"stage\": " + json_string(alert.stage);
    line += ", \"status_code\": " + std::to_string(alert.status_code);
    line += ", \"score\": 0, \"rules\": [], \"findings\": []";
    line += ", \"log_level\": " + json_string(alert.log_level);
    line += ", \"zone\": \"default\"";
    line += ", \"duration_ms\": " + python_float_3(alert.duration_ms);
    if (body_excerpt) line += ", \"body_excerpt\": " + json_string(*body_excerpt);
    line += "}";
    return line;
}

}  // namespace omega

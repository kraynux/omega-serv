// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "text.hpp"

namespace omega {

namespace {

bool is_continuation(char c) { return (static_cast<unsigned char>(c) & 0xC0) == 0x80; }

// Point de code a `i` (UTF-8 valide suppose) ; avance `i`.
char32_t next_code_point(std::string_view s, std::size_t& i) {
    const auto b0 = static_cast<unsigned char>(s[i++]);
    if (b0 < 0x80) return b0;
    int extra = b0 < 0xE0 ? 1 : b0 < 0xF0 ? 2 : 3;
    char32_t cp = extra == 1 ? (b0 & 0x1F) : extra == 2 ? (b0 & 0x0F) : (b0 & 0x07);
    for (; extra > 0 && i < s.size(); --extra, ++i) cp = (cp << 6) | (static_cast<unsigned char>(s[i]) & 0x3F);
    return cp;
}

}  // namespace

std::size_t utf8_length(std::string_view utf8) {
    std::size_t n = 0;
    for (char c : utf8) {
        if (!is_continuation(c)) ++n;
    }
    return n;
}

std::string_view utf8_skip(std::string_view utf8, std::size_t count) {
    std::size_t i = 0;
    while (count > 0 && i < utf8.size()) {
        ++i;
        while (i < utf8.size() && is_continuation(utf8[i])) ++i;
        --count;
    }
    return utf8.substr(i);
}

std::string_view utf8_take(std::string_view utf8, std::size_t count) {
    return utf8.substr(0, utf8.size() - utf8_skip(utf8, count).size());
}

bool python_isspace(char32_t cp) {
    // Py_UNICODE_ISSPACE (Unicode 16, bidirectionnel WS/B/S ou categorie Zs)
    switch (cp) {
        case 0x09: case 0x0A: case 0x0B: case 0x0C: case 0x0D: case 0x1C: case 0x1D: case 0x1E: case 0x1F:
        case 0x20: case 0x85: case 0xA0: case 0x1680: case 0x2028: case 0x2029: case 0x202F: case 0x205F:
        case 0x3000:
            return true;
        default:
            return cp >= 0x2000 && cp <= 0x200A;
    }
}

std::string_view py_strip(std::string_view utf8) {
    std::size_t start = 0;
    while (start < utf8.size()) {
        std::size_t next = start;
        if (!python_isspace(next_code_point(utf8, next))) break;
        start = next;
    }
    std::size_t end = utf8.size();
    while (end > start) {
        std::size_t begin = end - 1;
        while (begin > start && is_continuation(utf8[begin])) --begin;
        std::size_t probe = begin;
        if (!python_isspace(next_code_point(utf8, probe))) break;
        end = begin;
    }
    return utf8.substr(start, end - start);
}

std::vector<std::string_view> py_split_whitespace(std::string_view utf8) {
    std::vector<std::string_view> parts;
    std::size_t i = 0;
    std::size_t word_start = std::string_view::npos;
    while (i < utf8.size()) {
        const std::size_t at = i;
        const bool space = python_isspace(next_code_point(utf8, i));
        if (space) {
            if (word_start != std::string_view::npos) {
                parts.push_back(utf8.substr(word_start, at - word_start));
                word_start = std::string_view::npos;
            }
        } else if (word_start == std::string_view::npos) {
            word_start = at;
        }
    }
    if (word_start != std::string_view::npos) parts.push_back(utf8.substr(word_start));
    return parts;
}

std::optional<std::string> utf8_to_latin1(std::string_view utf8) {
    std::string out;
    out.reserve(utf8.size());
    for (std::size_t i = 0; i < utf8.size();) {
        const char32_t cp = next_code_point(utf8, i);
        if (cp > 0xFF) return std::nullopt;
        out.push_back(static_cast<char>(cp));
    }
    return out;
}

std::string sanitize_log_field(std::string_view utf8, std::size_t max_length) {
    std::string out(utf8_take(utf8, max_length));
    for (char& c : out) {
        if (static_cast<unsigned char>(c) < 0x20) c = ' ';
    }
    return out;
}

}  // namespace omega

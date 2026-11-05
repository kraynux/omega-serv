// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "static_rules.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <string_view>

#include "http_parser.hpp"

namespace omega {

namespace {

// ============================================================ texte « a la Python » (points de code)
using U32 = std::u32string;

U32 latin1_to_u32(std::string_view latin1) {
    U32 out;
    out.reserve(latin1.size());
    for (char c : latin1) out.push_back(static_cast<unsigned char>(c));
    return out;
}

void append_utf8(std::string& out, char32_t cp) {
    if (cp < 0x80) {
        out.push_back(static_cast<char>(cp));
    } else if (cp < 0x800) {
        out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else if (cp < 0x10000) {
        out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else {
        out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    }
}

std::string u32_to_utf8(const U32& text) {
    std::string out;
    out.reserve(text.size());
    for (char32_t cp : text) append_utf8(out, cp);
    return out;
}

// Decodeur UTF-8 strict de CPython (bytes.decode("utf-8", "strict")) : surlongueurs, substituts, > U+10FFFF
// et sequences tronquees refuses.
bool decode_utf8_strict(const std::string& bytes, U32& out) {
    std::size_t i = 0;
    const std::size_t n = bytes.size();
    while (i < n) {
        const auto b0 = static_cast<unsigned char>(bytes[i]);
        if (b0 < 0x80) {
            out.push_back(b0);
            ++i;
            continue;
        }
        int extra = 0;
        char32_t cp = 0;
        char32_t min = 0;
        if (b0 >= 0xC2 && b0 <= 0xDF) { extra = 1; cp = b0 & 0x1F; min = 0x80; }
        else if (b0 >= 0xE0 && b0 <= 0xEF) { extra = 2; cp = b0 & 0x0F; min = 0x800; }
        else if (b0 >= 0xF0 && b0 <= 0xF4) { extra = 3; cp = b0 & 0x07; min = 0x10000; }
        else return false;
        if (i + static_cast<std::size_t>(extra) >= n) return false;  // sequence tronquee
        for (int k = 1; k <= extra; ++k) {
            const auto b = static_cast<unsigned char>(bytes[i + static_cast<std::size_t>(k)]);
            if ((b & 0xC0) != 0x80) return false;
            cp = (cp << 6) | (b & 0x3F);
        }
        if (cp < min || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) return false;
        out.push_back(cp);
        i += static_cast<std::size_t>(extra) + 1;
    }
    return true;
}

int hex_value(char32_t c) {
    if (c >= '0' && c <= '9') return static_cast<int>(c - '0');
    if (c >= 'a' && c <= 'f') return static_cast<int>(c - 'a' + 10);
    if (c >= 'A' && c <= 'F') return static_cast<int>(c - 'A' + 10);
    return -1;
}

// urllib.parse._unquote_impl sur une plage ASCII : "%" suivi de deux chiffres hexa -> octet, sinon conserve.
std::string unquote_ascii_run(const U32& text, std::size_t begin, std::size_t end) {
    std::string bytes;
    bytes.reserve(end - begin);
    for (std::size_t i = begin; i < end; ++i) {
        // Deux caracteres hexadecimaux apres le '%', DANS la plage (item[:2] de Python) ; sinon '%' conserve.
        if (text[i] == '%' && i + 2 < end) {
            const int hi = hex_value(text[i + 1]);
            const int lo = hex_value(text[i + 2]);
            if (hi >= 0 && lo >= 0) {
                bytes.push_back(static_cast<char>(hi * 16 + lo));
                i += 2;
                continue;
            }
        }
        bytes.push_back(static_cast<char>(text[i]));
    }
    return bytes;
}

// urllib.parse.unquote(texte, errors="strict") ; false = UnicodeDecodeError.
bool python_unquote(const U32& text, U32& out) {
    if (std::find(text.begin(), text.end(), U'%') == text.end()) {
        out = text;
        return true;
    }
    out.clear();
    std::size_t i = 0;
    while (i < text.size()) {
        std::size_t j = i;
        if (text[i] < 0x80) {
            while (j < text.size() && text[j] < 0x80) ++j;
            if (!decode_utf8_strict(unquote_ascii_run(text, i, j), out)) return false;
        } else {
            while (j < text.size() && text[j] >= 0x80) ++j;
            out.append(text, i, j - i);
        }
        i = j;
    }
    return true;
}

bool python_isdigit_latin1(char32_t c) {
    return (c >= '0' && c <= '9') || c == 0xB2 || c == 0xB3 || c == 0xB9;  // str.isdigit() : 0-9, ², ³, ¹
}

// int() de Python sur un jeton sans espace : signe facultatif, chiffres ASCII, « _ » entre deux chiffres.
std::optional<long long> python_int(std::string_view token) {
    std::size_t i = 0;
    bool negative = false;
    if (i < token.size() && (token[i] == '+' || token[i] == '-')) {
        negative = token[i] == '-';
        ++i;
    }
    if (i >= token.size()) return std::nullopt;
    long long value = 0;
    bool previous_digit = false;
    for (; i < token.size(); ++i) {
        const char c = token[i];
        if (c >= '0' && c <= '9') {
            if (value > (std::numeric_limits<long long>::max() - (c - '0')) / 10) return std::nullopt;
            value = value * 10 + (c - '0');
            previous_digit = true;
        } else if (c == '_' && previous_digit && i + 1 < token.size() && token[i + 1] >= '0' && token[i + 1] <= '9') {
            previous_digit = false;
        } else {
            return std::nullopt;
        }
    }
    return negative ? -value : value;
}

std::string ascii_lower(std::string_view text) {
    std::string out(text);
    for (char& c : out) {
        if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
    }
    return out;
}

std::string ascii_upper(std::string_view text) {
    std::string out(text);
    for (char& c : out) {
        if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 'a' + 'A');
    }
    return out;
}

// str.split() (sans argument) sur du texte latin-1.
std::vector<std::string> python_split(std::string_view text) {
    std::vector<std::string> parts;
    std::size_t i = 0;
    while (i < text.size()) {
        while (i < text.size() && python_isspace_latin1(static_cast<unsigned char>(text[i]))) ++i;
        std::size_t j = i;
        while (j < text.size() && !python_isspace_latin1(static_cast<unsigned char>(text[j]))) ++j;
        if (j > i) parts.emplace_back(text.substr(i, j - i));
        i = j;
    }
    return parts;
}

std::vector<std::string> split_on(std::string_view text, char sep) {
    std::vector<std::string> parts;
    std::size_t start = 0;
    while (true) {
        const std::size_t pos = text.find(sep, start);
        if (pos == std::string_view::npos) {
            parts.emplace_back(text.substr(start));
            return parts;
        }
        parts.emplace_back(text.substr(start, pos - start));
        start = pos + 1;
    }
}

constexpr std::array<std::string_view, 24> kMonthNames = {
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december"};
constexpr std::array<std::string_view, 7> kDayNames = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"};

int month_index(std::string_view lower) {
    for (std::size_t i = 0; i < kMonthNames.size(); ++i) {
        if (kMonthNames[i] == lower) return static_cast<int>(i);
    }
    return -1;
}

std::optional<int> named_timezone(std::string_view upper) {
    static constexpr std::array<std::pair<std::string_view, int>, 14> zones = {{
        {"UT", 0}, {"UTC", 0}, {"GMT", 0}, {"Z", 0}, {"AST", -400}, {"ADT", -300}, {"EST", -500},
        {"EDT", -400}, {"CST", -600}, {"CDT", -500}, {"MST", -700}, {"MDT", -600}, {"PST", -800}, {"PDT", -700},
    }};
    for (const auto& [name, offset] : zones) {
        if (name == upper) return offset;
    }
    return std::nullopt;
}

long long days_from_civil(long long y, unsigned m, unsigned d) {
    y -= m <= 2;
    const long long era = (y >= 0 ? y : y - 399) / 400;
    const auto yoe = static_cast<unsigned>(y - era * 400);
    const unsigned doy = (153 * (m > 2 ? m - 3 : m + 9) + 2) / 5 + d - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + static_cast<long long>(doe) - 719468;
}

bool is_leap(long long y) { return (y % 4 == 0 && y % 100 != 0) || y % 400 == 0; }

int days_in_month(long long y, int m) {
    static constexpr std::array<int, 12> days = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    return m == 2 && is_leap(y) ? 29 : days[static_cast<std::size_t>(m - 1)];
}

}  // namespace

// ================================================================================ chemins
std::string latin1_to_utf8(std::string_view latin1) { return u32_to_utf8(latin1_to_u32(latin1)); }

namespace {
PathDecision normalize_text_path(U32 current);

// UTF-8 deja valide (texte produit par ce programme ou par la configuration JSON) -> points de code
U32 utf8_to_u32(std::string_view utf8) {
    U32 out;
    out.reserve(utf8.size());
    for (std::size_t i = 0; i < utf8.size();) {
        const auto b0 = static_cast<unsigned char>(utf8[i]);
        int extra = b0 < 0x80 ? 0 : b0 < 0xE0 ? 1 : b0 < 0xF0 ? 2 : 3;
        char32_t cp = extra == 0 ? b0 : extra == 1 ? (b0 & 0x1F) : extra == 2 ? (b0 & 0x0F) : (b0 & 0x07);
        ++i;
        for (; extra > 0 && i < utf8.size(); --extra, ++i) cp = (cp << 6) | (static_cast<unsigned char>(utf8[i]) & 0x3F);
        out.push_back(cp);
    }
    return out;
}
}  // namespace

PathDecision normalize_uri_path(std::string_view raw_path) {
    if (raw_path.empty()) {
        PathDecision decision;
        decision.status = 400;
        return decision;
    }
    return normalize_text_path(latin1_to_u32(raw_path));
}

PathDecision normalize_uri_path_utf8(std::string_view utf8_path) {
    if (utf8_path.empty()) {
        PathDecision decision;
        decision.status = 400;
        return decision;
    }
    return normalize_text_path(utf8_to_u32(utf8_path));
}

namespace {
PathDecision normalize_text_path(U32 current) {
    PathDecision decision;
    for (int pass = 0; pass < 2; ++pass) {  // _MAX_DECODE_PASSES
        U32 decoded;
        if (!python_unquote(current, decoded)) {
            decision.status = 400;
            return decision;
        }
        if (decoded == current) break;
        current = std::move(decoded);
    }
    for (char32_t c : current) {
        if (c < 0x20) {  // NUL ou caractere de controle : 400 dans les deux cas
            decision.status = 400;
            return decision;
        }
    }
    std::replace(current.begin(), current.end(), U'\\', U'/');
    std::vector<U32> normalized;
    std::size_t start = 0;
    while (start <= current.size()) {
        std::size_t end = current.find(U'/', start);
        if (end == U32::npos) end = current.size();
        U32 segment = current.substr(start, end - start);
        start = end + 1;
        if (segment.empty() || segment == U".") {
            if (end == current.size()) break;
            continue;
        }
        if (segment == U"..") {
            if (normalized.empty()) {
                decision.status = 403;
                return decision;
            }
            normalized.pop_back();
        } else {
            normalized.push_back(std::move(segment));
        }
        if (end == current.size()) break;
    }
    for (const U32& segment : normalized) decision.segments.push_back(u32_to_utf8(segment));
    return decision;
}
}  // namespace

// ============================================================================ conditionnels
std::string make_etag(std::uint64_t size, std::int64_t mtime) {
    char buffer[64];
    std::snprintf(buffer, sizeof buffer, "\"%llx-%llx\"", static_cast<unsigned long long>(mtime),
                  static_cast<unsigned long long>(size));
    return buffer;
}

std::string http_date(std::int64_t mtime) {
    static constexpr std::array<const char*, 7> days = {"Thu", "Fri", "Sat", "Sun", "Mon", "Tue", "Wed"};
    static constexpr std::array<const char*, 12> months = {"Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
    const std::time_t t = static_cast<std::time_t>(mtime);
    std::tm tm{};
    gmtime_r(&t, &tm);
    long long day_index = (mtime >= 0 ? mtime / 86400 : (mtime - 86399) / 86400) % 7;
    if (day_index < 0) day_index += 7;
    char buffer[64];
    std::snprintf(buffer, sizeof buffer, "%s, %02d %s %04d %02d:%02d:%02d GMT",
                  days[static_cast<std::size_t>(day_index)], tm.tm_mday,
                  months[static_cast<std::size_t>(tm.tm_mon)], tm.tm_year + 1900, tm.tm_hour, tm.tm_min, tm.tm_sec);
    return buffer;
}

std::optional<double> parse_http_date(std::string_view value) {
    // email._parseaddr._parsedate_tz, porte ligne a ligne.
    if (value.empty()) return std::nullopt;
    std::vector<std::string> data = python_split(value);
    if (data.empty()) return std::nullopt;
    const std::string first_lower = ascii_lower(data[0]);
    const bool dayname = std::find(kDayNames.begin(), kDayNames.end(), first_lower) != kDayNames.end();
    if (!data[0].empty() && (data[0].back() == ',' || dayname)) {
        data.erase(data.begin());
    } else {
        const std::size_t comma = data[0].rfind(',');
        if (comma != std::string::npos) data[0] = data[0].substr(comma + 1);
    }
    if (data.size() == 3) {
        std::vector<std::string> stuff = split_on(data[0], '-');
        if (stuff.size() == 3) {
            stuff.insert(stuff.end(), data.begin() + 1, data.end());
            data = std::move(stuff);
        }
    }
    if (data.size() == 4) {
        const std::string s = data[3];
        std::size_t i = s.find('+');
        if (i == std::string::npos) i = s.find('-');
        if (i != std::string::npos && i > 0) {
            data[3] = s.substr(0, i);
            data.push_back(s.substr(i));
        } else {
            data.emplace_back("");
        }
    }
    if (data.size() < 5) return std::nullopt;
    data.resize(5);
    std::string dd = data[0], mm = data[1], yy = data[2], tm = data[3], tz = data[4];
    if (dd.empty() || mm.empty() || yy.empty()) return std::nullopt;
    mm = ascii_lower(mm);
    int month = month_index(mm);
    if (month < 0) {
        std::swap(dd, mm);
        mm = ascii_lower(mm);
        month = month_index(mm);
        if (month < 0) return std::nullopt;
    }
    month += 1;
    if (month > 12) month -= 12;
    if (!dd.empty() && dd.back() == ',') dd.pop_back();
    if (const std::size_t colon = yy.find(':'); colon != std::string::npos && colon > 0) std::swap(yy, tm);
    if (!yy.empty() && yy.back() == ',') {
        yy.pop_back();
        if (yy.empty()) return std::nullopt;
    }
    if (yy.empty()) return std::nullopt;  // Python : IndexError sur yy[0] -> attrape -> None
    if (!python_isdigit_latin1(static_cast<unsigned char>(yy[0]))) std::swap(yy, tz);
    if (tm.empty()) return std::nullopt;  // tm[-1] sur une chaine vide : IndexError -> None
    if (tm.back() == ',') tm.pop_back();
    std::vector<std::string> parts = split_on(tm, ':');
    std::string thh, tmm, tss;
    if (parts.size() == 2) {
        thh = parts[0]; tmm = parts[1]; tss = "0";
    } else if (parts.size() == 3) {
        thh = parts[0]; tmm = parts[1]; tss = parts[2];
    } else if (parts.size() == 1 && parts[0].find('.') != std::string::npos) {
        parts = split_on(parts[0], '.');
        if (parts.size() == 2) {
            thh = parts[0]; tmm = parts[1]; tss = "0";
        } else if (parts.size() == 3) {
            thh = parts[0]; tmm = parts[1]; tss = parts[2];
        } else {
            return std::nullopt;
        }
    } else {
        return std::nullopt;
    }
    const auto year = python_int(yy);
    const auto day = python_int(dd);
    const auto hour = python_int(thh);
    const auto minute = python_int(tmm);
    const auto second = python_int(tss);
    if (!year || !day || !hour || !minute || !second) return std::nullopt;
    long long y = *year;
    if (y < 100) y += y > 68 ? 1900 : 2000;
    std::optional<long long> tzoffset;
    const std::string tz_upper = ascii_upper(tz);
    if (auto named = named_timezone(tz_upper)) {
        tzoffset = *named;
    } else {
        tzoffset = python_int(tz);
        if (tzoffset && *tzoffset == 0 && !tz.empty() && tz[0] == '-') tzoffset.reset();
    }
    long long offset = 0;  // secondes ; absent = 0 (value_or) - variable simple : GCC -O3 voyait a tort un optional non initialise
    if (tzoffset.has_value()) offset = tzoffset.value();
    if (offset != 0) {
        const long long sign = offset < 0 ? -1 : 1;
        const long long abs_offset = offset * sign;
        offset = sign * ((abs_offset / 100) * 3600 + (abs_offset % 100) * 60);
    }
    // datetime.datetime(...) : ValueError -> None (attrape par conditional.py)
    if (y < 1 || y > 9999) return std::nullopt;
    if (*day < 1 || *day > days_in_month(y, month)) return std::nullopt;
    if (*hour < 0 || *hour > 23 || *minute < 0 || *minute > 59 || *second < 0 || *second > 59) return std::nullopt;
    if (offset <= -86400 || offset >= 86400) return std::nullopt;  // timezone(timedelta) : |offset| < 24 h
    const long long days = days_from_civil(y, static_cast<unsigned>(month), static_cast<unsigned>(*day));
    return static_cast<double>(days * 86400 + *hour * 3600 + *minute * 60 + *second - offset);
}

namespace {

std::string_view strip_view(std::string_view text) { return python_strip(text); }

std::string_view remove_weak_prefix(std::string_view text) {
    return text.starts_with("W/") ? text.substr(2) : text;
}

bool etag_list_matches(std::string_view header, std::string_view etag) {
    if (strip_view(header) == "*") return true;
    const std::string_view wanted = remove_weak_prefix(etag);
    for (const std::string& candidate : split_on(header, ',')) {
        if (remove_weak_prefix(strip_view(candidate)) == wanted) return true;
    }
    return false;
}

long long python_int_trunc(double value) { return static_cast<long long>(std::trunc(value)); }

bool all_digits(std::string_view text) {
    if (text.empty()) return false;
    for (char c : text) {
        if (!python_isdigit_latin1(static_cast<unsigned char>(c))) return false;
    }
    return true;
}

}  // namespace

bool is_not_modified(const std::string* if_none_match, const std::string* if_modified_since,
                     std::string_view etag, std::int64_t mtime) {
    if (if_none_match != nullptr) return etag_list_matches(*if_none_match, etag);
    if (if_modified_since != nullptr) {
        const auto since = parse_http_date(*if_modified_since);
        return since.has_value() && mtime <= python_int_trunc(*since);
    }
    return false;
}

RangeDecision resolve_range(const std::string* range_header, const std::string* if_range,
                            std::uint64_t size, std::string_view etag, std::int64_t mtime) {
    RangeDecision full;
    if (range_header == nullptr) return full;
    if (if_range != nullptr) {
        const std::string_view value = strip_view(*if_range);
        if (value.starts_with('"') || value.starts_with("W/")) {
            if (value != etag) return full;
        } else {
            const auto since = parse_http_date(value);
            if (!since || mtime != python_int_trunc(*since)) return full;
        }
    }
    const std::string_view header = strip_view(*range_header);
    const std::size_t eq = header.find('=');
    const std::string_view unit = eq == std::string_view::npos ? header : header.substr(0, eq);
    const std::string_view spec = eq == std::string_view::npos ? std::string_view{} : header.substr(eq + 1);
    if (ascii_lower(strip_view(unit)) != "bytes" || spec.empty() || spec.find(',') != std::string_view::npos) return full;
    const std::string_view spec_stripped = strip_view(spec);
    const std::size_t dash = spec_stripped.find('-');
    if (dash == std::string_view::npos) return full;
    const std::string_view first = strip_view(spec_stripped.substr(0, dash));
    const std::string_view last = strip_view(spec_stripped.substr(dash + 1));
    if (!(all_digits(first) || first.empty()) || !(all_digits(last) || last.empty()) || (first.empty() && last.empty()))
        return full;
    // isdigit() vrai pour ¹²³ mais int() echoue : Python leverait ValueError (non attrape -> erreur 500 cote
    // Python). Cas pathologique : on renvoie la reponse complete, ecart documente (plan §14).
    const auto to_u64 = [](std::string_view digits) -> std::optional<std::uint64_t> {
        std::uint64_t v = 0;
        for (char c : digits) {
            if (c < '0' || c > '9') return std::nullopt;
            if (v > (UINT64_MAX - static_cast<std::uint64_t>(c - '0')) / 10) return UINT64_MAX;
            v = v * 10 + static_cast<std::uint64_t>(c - '0');
        }
        return v;
    };
    RangeDecision decision;
    if (first.empty()) {
        const auto suffix = to_u64(last);
        if (!suffix) return full;
        if (*suffix == 0 || size == 0) {
            decision.unsatisfiable = true;
            return decision;
        }
        decision.partial = true;
        decision.start = *suffix >= size ? 0 : size - *suffix;
        decision.end = size - 1;
        return decision;
    }
    const auto start = to_u64(first);
    if (!start) return full;
    if (*start >= size) {
        decision.unsatisfiable = true;
        return decision;
    }
    std::uint64_t end = size - 1;
    if (!last.empty()) {
        const auto last_value = to_u64(last);
        if (!last_value) return full;
        end = std::min(*last_value, size - 1);
    }
    if (end < *start) return full;
    decision.partial = true;
    decision.start = *start;
    decision.end = end;
    return decision;
}

// ======================================================================== types, cache, gzip
std::string py_lower(std::string_view utf8) {
    // Extensions, motifs et noms compares en minuscules : ASCII suffit pour les tables (toutes ASCII) ; les
    // lettres latin-1 accentuees (U+00C0-U+00DE) sont aussi converties comme le ferait str.lower().
    std::string out;
    out.reserve(utf8.size());
    for (std::size_t i = 0; i < utf8.size(); ++i) {
        const auto c = static_cast<unsigned char>(utf8[i]);
        if (c >= 'A' && c <= 'Z') {
            out.push_back(static_cast<char>(c - 'A' + 'a'));
        } else if (c == 0xC3 && i + 1 < utf8.size()) {
            const auto next = static_cast<unsigned char>(utf8[i + 1]);
            out.push_back(static_cast<char>(c));
            // U+00C0..U+00DE sauf U+00D7 (×) -> +0x20 (seconde unite 0x80..0x9E -> 0xA0..0xBE)
            out.push_back(static_cast<char>(next >= 0x80 && next <= 0x9E && next != 0x97 ? next + 0x20 : next));
            ++i;
        } else {
            out.push_back(static_cast<char>(c));
        }
    }
    return out;
}

std::string guess_mime_type(std::string_view filename) {
    static constexpr std::array<std::pair<std::string_view, std::string_view>, 19> table = {{
        {".html", "text/html; charset=utf-8"}, {".htm", "text/html; charset=utf-8"},
        {".txt", "text/plain; charset=utf-8"}, {".css", "text/css; charset=utf-8"},
        {".js", "text/javascript; charset=utf-8"}, {".mjs", "text/javascript; charset=utf-8"},
        {".json", "application/json"}, {".xml", "application/xml"}, {".svg", "image/svg+xml"},
        {".png", "image/png"}, {".jpg", "image/jpeg"}, {".jpeg", "image/jpeg"}, {".gif", "image/gif"},
        {".webp", "image/webp"}, {".ico", "image/x-icon"}, {".woff", "font/woff"}, {".woff2", "font/woff2"},
        {".ttf", "font/ttf"}, {".pdf", "application/pdf"},
    }};
    const std::size_t dot = filename.rfind('.');
    if (dot == std::string_view::npos) return "application/octet-stream";
    const std::string extension = py_lower(filename.substr(dot));
    for (const auto& [ext, mime] : table) {
        if (ext == extension) return std::string(mime);
    }
    return "application/octet-stream";
}

CachePolicy default_cache_policy() {
    CachePolicy policy;
    for (const char* ext : {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico"})
        policy.extensions.emplace_back(ext, "max-age=86400");
    for (const char* ext : {".mp4", ".webm", ".mp3", ".ogg"}) policy.extensions.emplace_back(ext, "max-age=86400");
    for (const char* ext : {".woff", ".woff2", ".ttf", ".otf"}) policy.extensions.emplace_back(ext, "max-age=604800");
    for (const char* ext : {".css", ".js"}) policy.extensions.emplace_back(ext, "max-age=3600");
    return policy;
}

bool path_matches_prefix(std::string_view path, std::string_view prefix) {
    if (prefix == "/") return true;
    std::string_view normalized = prefix;
    while (!normalized.empty() && normalized.back() == '/') normalized.remove_suffix(1);
    if (normalized.empty()) return true;
    return path == normalized || (path.size() > normalized.size() && path.starts_with(normalized) &&
                                  path[normalized.size()] == '/');
}

int resolve_zone_index(std::string_view path, const std::vector<std::string>& prefixes) {
    int best = -1;
    std::size_t best_length = 0;
    for (std::size_t i = 0; i < prefixes.size(); ++i) {
        if (!path_matches_prefix(path, prefixes[i])) continue;
        std::string_view normalized = prefixes[i];
        if (normalized == "/") normalized = "";
        while (!normalized.empty() && normalized.back() == '/') normalized.remove_suffix(1);
        // max() de Python : le premier des maxima gagne -> strictement plus long seulement.
        if (best < 0 || normalized.size() > best_length) {
            best = static_cast<int>(i);
            best_length = normalized.size();
        }
    }
    return best;
}

std::string resolve_cache_control(std::string_view path, std::string_view filename, const CachePolicy& policy) {
    std::vector<std::string> prefixes;
    prefixes.reserve(policy.zones.size());
    for (const auto& zone : policy.zones) prefixes.push_back(zone.first);
    const int zone = resolve_zone_index(path, prefixes);
    if (zone >= 0) return policy.zones[static_cast<std::size_t>(zone)].second;
    const std::size_t dot = filename.rfind('.');
    if (dot != std::string_view::npos) {
        const std::string extension = py_lower(filename.substr(dot));
        for (const auto& [ext, value] : policy.extensions) {
            if (ext == extension) return value;
        }
    }
    return policy.default_value;
}

bool is_compressible(std::string_view filename) {
    static constexpr std::array<std::string_view, 12> extensions = {
        ".html", ".htm", ".css", ".js", ".mjs", ".json", ".map", ".svg", ".xml", ".txt", ".md", ".csv"};
    const std::size_t dot = filename.rfind('.');
    if (dot == std::string_view::npos) return false;
    const std::string extension = py_lower(filename.substr(dot));
    return std::find(extensions.begin(), extensions.end(), extension) != extensions.end();
}

namespace {

// float() de Python (precompressed.py::_quality), echec -> 0.0 : « _ » entre deux chiffres accepte, inf/nan
// acceptes, hexadecimal refuse (strtod l'accepterait).
double python_float_or_zero(std::string_view text) {
    if (text.empty() || text.find_first_of("xX") != std::string_view::npos) return 0.0;
    std::string cleaned;
    for (std::size_t i = 0; i < text.size(); ++i) {
        if (text[i] == '_') {
            const bool between_digits = i > 0 && i + 1 < text.size() && std::isdigit(static_cast<unsigned char>(text[i - 1]))
                                        && std::isdigit(static_cast<unsigned char>(text[i + 1]));
            if (!between_digits) return 0.0;
            continue;
        }
        cleaned.push_back(text[i]);
    }
    char* end = nullptr;
    const double parsed = std::strtod(cleaned.c_str(), &end);
    if (end == nullptr || *end != '\0' || end == cleaned.c_str()) return 0.0;
    return parsed;
}

}  // namespace

std::vector<std::pair<std::string, std::string>> preferred_encodings(const std::string* accept_encoding) {
    std::vector<std::pair<std::string, std::string>> result;
    if (accept_encoding == nullptr || accept_encoding->empty()) return result;
    std::vector<std::pair<std::string, double>> qualities;  // dernier gagne, comme un dict Python
    for (const std::string& item : split_on(*accept_encoding, ',')) {
        const std::vector<std::string> pieces = split_on(item, ';');
        const std::string name = py_lower(std::string(strip_view(pieces[0])));
        if (name.empty()) continue;
        double quality = 1.0;
        for (std::size_t k = 1; k < pieces.size(); ++k) {
            const std::string_view parameter = strip_view(pieces[k]);
            const std::size_t eq = parameter.find('=');
            const std::string_view key = strip_view(eq == std::string_view::npos ? parameter : parameter.substr(0, eq));
            if (ascii_lower(key) == "q") {
                const std::string raw(eq == std::string_view::npos ? std::string_view{} : parameter.substr(eq + 1));
                // float() de Python : espaces tolerees autour ; echec -> 0.0
                quality = python_float_or_zero(strip_view(raw));
                break;
            }
        }
        auto existing = std::find_if(qualities.begin(), qualities.end(), [&](const auto& q) { return q.first == name; });
        if (existing != qualities.end()) existing->second = quality;
        else qualities.emplace_back(name, quality);
    }
    auto quality_of = [&](std::string_view encoding, double fallback) {
        for (const auto& [name, q] : qualities) {
            if (name == encoding) return q;
        }
        return fallback;
    };
    const double wildcard = quality_of("*", 0.0);
    struct Ranked { double quality; int neg_position; std::string encoding, suffix; };
    const auto sortable = [](double q) { return std::isnan(q) ? -1.0 : q; };  // NaN > 0 est faux : jamais retenu
    std::vector<Ranked> ranked = {
        {sortable(quality_of("br", wildcard)), 0, "br", ".br"},
        {sortable(quality_of("gzip", wildcard)), -1, "gzip", ".gz"},
    };
    // sorted(..., reverse=True) sur (qualite, -position, codage, suffixe)
    std::sort(ranked.begin(), ranked.end(), [](const Ranked& a, const Ranked& b) {
        if (a.quality != b.quality) return a.quality > b.quality;
        if (a.neg_position != b.neg_position) return a.neg_position > b.neg_position;
        if (a.encoding != b.encoding) return a.encoding > b.encoding;
        return a.suffix > b.suffix;
    });
    for (const auto& r : ranked) {
        if (r.quality > 0) result.emplace_back(r.encoding, r.suffix);
    }
    return result;
}

// ============================================================================ acces generique
bool is_denied_path(const std::vector<std::string>& segments, const DenyRules& rules) {
    if (rules.deny_hidden_files) {
        for (const std::string& segment : segments) {
            if (segment.starts_with('.')) return true;
        }
    }
    if (segments.empty()) return false;
    const std::string filename = py_lower(segments.back());
    for (const std::string& extension : rules.deny_sensitive_extensions) {
        const std::string ext = py_lower(extension);
        if (filename.size() >= ext.size() && filename.compare(filename.size() - ext.size(), ext.size(), ext) == 0)
            return true;
    }
    for (const std::string& pattern : rules.deny_patterns) {
        if (filename.find(py_lower(pattern)) != std::string::npos) return true;
    }
    return false;
}

}  // namespace omega

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "http_parser.hpp"

#include <algorithm>
#include <cctype>
#include <limits>

namespace omega {

namespace {

bool iequals(std::string_view a, std::string_view b) {
    if (a.size() != b.size()) return false;
    for (std::size_t i = 0; i < a.size(); ++i) {
        if (std::tolower(static_cast<unsigned char>(a[i])) != std::tolower(static_cast<unsigned char>(b[i])))
            return false;
    }
    return true;
}

ParseResult make_error(int status, std::string reason) {
    ParseResult result;
    result.state = ParseState::error;
    result.status = status;
    result.reason = std::move(reason);
    return result;
}

// Une ligne terminee par CRLF a partir de `start` (comme StreamReader.readuntil(b"\r\n")).
struct LineScan {
    enum Kind { found, need_more, too_long } kind = need_more;
    std::string_view line;      // sans le CRLF
    std::size_t next = 0;       // position apres le CRLF
};

LineScan scan_line(std::string_view buffer, std::size_t start, std::size_t max_size, std::size_t raw_limit) {
    LineScan scan;
    const std::size_t pos = buffer.find("\r\n", start);
    if (pos == std::string_view::npos) {
        // Python : LimitOverrunError quand la ligne en attente depasse la limite du flux (1 Mio) ;
        // une ligne deja plus longue que `max_size` ne peut plus devenir valide : on coupe tot.
        const std::size_t pending = buffer.size() - start;
        if (pending > raw_limit || pending > max_size + 1) scan.kind = LineScan::too_long;
        return scan;
    }
    scan.line = buffer.substr(start, pos - start);
    scan.next = pos + 2;
    scan.kind = scan.line.size() > max_size ? LineScan::too_long : LineScan::found;
    return scan;
}

bool has_control_characters(std::string_view value) {
    return std::any_of(value.begin(), value.end(),
                       [](char c) { return is_control_character(static_cast<unsigned char>(c)); });
}

}  // namespace

bool python_isspace_latin1(unsigned char c) {
    switch (c) {
        case 0x09: case 0x0a: case 0x0b: case 0x0c: case 0x0d:
        case 0x1c: case 0x1d: case 0x1e: case 0x1f: case 0x20:
        case 0x85: case 0xa0:
            return true;
        default:
            return false;
    }
}

bool is_control_character(unsigned char c) { return c < 0x20 && c != 0x09; }

std::string_view python_strip(std::string_view value) {
    std::size_t begin = 0;
    std::size_t end = value.size();
    while (begin < end && python_isspace_latin1(static_cast<unsigned char>(value[begin]))) ++begin;
    while (end > begin && python_isspace_latin1(static_cast<unsigned char>(value[end - 1]))) --end;
    return value.substr(begin, end - begin);
}

const std::string* RequestHead::header(std::string_view name) const {
    for (const auto& [header_name, value] : headers) {
        if (iequals(header_name, name)) return &value;
    }
    return nullptr;
}

ParseResult parse_request_head(std::string_view buffer, const ParserLimits& limits, bool eof) {
    // Ligne de requete (414 si trop longue, comme Python : on_too_long = URI_TOO_LONG).
    LineScan first = scan_line(buffer, 0, limits.max_request_line_size, limits.raw_line_buffer_limit);
    if (first.kind == LineScan::too_long) return make_error(414, "ligne trop longue");
    if (first.kind == LineScan::need_more) {
        if (eof && !buffer.empty()) return make_error(400, "connexion fermée de manière inattendue");
        return {};  // vide + eof = fermeture propre ; sinon attendre
    }

    // A partir d'ici, toute erreur emporte la ligne brute et les en-tetes deja lus (HttpParseError enrichie).
    ParseResult result;
    auto fail = [&](int status, std::string reason) {
        ParseResult error = make_error(status, std::move(reason));
        error.has_request_line = true;
        error.request_line.assign(first.line);
        error.head.headers = std::move(result.head.headers);
        return error;
    };

    // split(" ") exact : 3 parties, aucune vide, version commencant par "HTTP/".
    const std::string_view line = first.line;
    const std::size_t sp1 = line.find(' ');
    const std::size_t sp2 = sp1 == std::string_view::npos ? sp1 : line.find(' ', sp1 + 1);
    if (sp1 == std::string_view::npos || sp2 == std::string_view::npos || line.find(' ', sp2 + 1) != std::string_view::npos)
        return fail(400, "ligne de requête malformée");
    const std::string_view method = line.substr(0, sp1);
    const std::string_view target = line.substr(sp1 + 1, sp2 - sp1 - 1);
    const std::string_view version = line.substr(sp2 + 1);
    if (method.empty() || target.empty() || version.substr(0, 5) != "HTTP/")
        return fail(400, "ligne de requête malformée");
    // Durcissement 2026-11-02 (RFC 9112 §2.3, RFC 9110 §6.2), comme _HTTP_VERSION_RE cote Python.
    auto ascii_digit = [](char c) { return c >= '0' && c <= '9'; };
    if (version.size() != 8 || !ascii_digit(version[5]) || version[6] != '.' || !ascii_digit(version[7]))
        return fail(400, "version HTTP malformée");
    if (version[5] != '1') return fail(505, "version HTTP non supportée");

    result.head.method.assign(method);
    result.head.target.assign(target);
    result.head.http_version.assign(version[7] == '0' || version[7] == '1' ? version : std::string_view("HTTP/1.1"));

    std::size_t position = first.next;
    std::size_t total_header_bytes = 0;
    while (true) {
        LineScan scan = scan_line(buffer, position, limits.max_header_size, limits.raw_line_buffer_limit);
        if (scan.kind == LineScan::too_long) return fail(431, "ligne trop longue");
        if (scan.kind == LineScan::need_more) {
            // readuntil sur un flux termine : aucun octet de la ligne suivante = IncompleteReadError a partiel
            // vide = ConnectionClosedCleanly (fermeture sans reponse ni journal), meme apres la ligne de requete.
            if (eof && position < buffer.size()) return fail(400, "connexion fermée de manière inattendue");
            return {};
        }
        total_header_bytes += scan.line.size() + 2;
        if (total_header_bytes > limits.max_header_size)
            return fail(431, "en-têtes trop volumineux au total");
        position = scan.next;
        if (scan.line.empty()) break;
        if (result.head.headers.size() >= limits.max_header_count) return fail(431, "trop d'en-têtes");

        const std::string_view raw = scan.line;
        if (raw.front() == ' ' || raw.front() == '\t') return fail(400, "repliage d'en-tête non supporte");
        const std::size_t colon = raw.find(':');
        if (colon == std::string_view::npos) return fail(400, "en-tête malformé (pas de ':')");
        const std::string_view raw_name = raw.substr(0, colon);
        // Durcissement 2026-11-02 (RFC 9112 §5.1) : aucune espace dans le nom, ni avant les deux-points.
        if (raw_name.find_first_of(" \t") != std::string_view::npos)
            return fail(400, "en-tête malformé (espace dans le nom)");
        const std::string_view name = python_strip(raw_name);
        const std::string_view value = python_strip(raw.substr(colon + 1));
        if (name.empty()) return fail(400, "en-tête malformé (nom vide)");
        if (has_control_characters(name) || has_control_characters(value))
            return fail(400, "en-tête contient un caractère de contrôle");
        result.head.headers.emplace_back(std::string(name), std::string(value));
    }

    // Apres lecture complete des en-tetes, dans l'ordre de Python : Content-Length duplique, puis Expect.
    int content_length_count = 0;
    for (const auto& [name, value] : result.head.headers) {
        if (iequals(name, "content-length")) ++content_length_count;
    }
    if (content_length_count > 1) return fail(400, "Content-Length dupliqué");
    for (const auto& [name, value] : result.head.headers) {
        if (iequals(name, "expect")) return fail(417, "Expect non supporte");
    }

    result.state = ParseState::complete;
    result.consumed = position;
    return result;
}

BodyFraming body_framing(const RequestHead& head, std::uint64_t max_request_size) {
    BodyFraming framing;
    if (head.header("transfer-encoding") != nullptr) {
        framing.status = 400;
        framing.reason = "Transfer-Encoding non supporte en Phase 1";
        return framing;
    }
    const std::string* raw = head.header("content-length");
    if (raw == nullptr) return framing;
    // Durcissement 2026-11-02 : chiffres ASCII uniquement (Python int() acceptait "+5", "1_000", chiffres non
    // ASCII ; un "-1" reste "invalide/negatif" -> 400 dans les deux cas, comme avant).
    if (raw->empty() || !std::all_of(raw->begin(), raw->end(), [](char c) { return c >= '0' && c <= '9'; })) {
        framing.status = 400;
        const std::string_view unsigned_part = std::string_view(*raw).substr(raw->empty() ? 0 : 1);
        const bool negative_number = raw->starts_with('-') && !unsigned_part.empty() &&
                                     std::all_of(unsigned_part.begin(), unsigned_part.end(), [](char c) { return c >= '0' && c <= '9'; });
        framing.reason = negative_number ? "Content-Length négatif" : "Content-Length invalide";
        return framing;
    }
    std::uint64_t value = 0;
    for (char c : *raw) {
        const std::uint64_t digit = static_cast<std::uint64_t>(c - '0');
        if (value > (std::numeric_limits<std::uint64_t>::max() - digit) / 10) {
            value = std::numeric_limits<std::uint64_t>::max();  // depasse tout : traite comme trop grand
            break;
        }
        value = value * 10 + digit;
    }
    if (value > max_request_size) {
        framing.status = 413;
        framing.reason = "corps de requête trop volumineux";
        return framing;
    }
    framing.content_length = value;
    return framing;
}

}  // namespace omega

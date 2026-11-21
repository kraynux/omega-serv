// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "upstream.hpp"

#include <algorithm>
#include <array>
#include <limits>

#include "ip.hpp"
#include "static_rules.hpp"
#include "text.hpp"

namespace omega {

namespace {

constexpr std::array<std::string_view, 8> kHopByHop = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding",
    "upgrade"};  // serve_proxy.HOP_BY_HOP_HEADERS

constexpr std::array<std::string_view, 9> kDroppedFromClient = {
    "proxy-connection", "forwarded", "x-real-ip",  // CLIENT_FORWARDING_HEADERS_DROPPED (2.6.2, D25)
    "host", "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host", "x-forwarded-port", "x-omega-proxy-hops"};

std::string ascii_lower(std::string_view text) {
    std::string out(text);
    for (char& ch : out) {
        if (ch >= 'A' && ch <= 'Z') ch = static_cast<char>(ch - 'A' + 'a');
    }
    return out;
}

template <std::size_t N>
bool contains(const std::array<std::string_view, N>& names, std::string_view name) {
    return std::find(names.begin(), names.end(), name) != names.end();
}

// Python : int(texte) apres strip() - signe facultatif, chiffres ASCII, « _ » seul entre deux chiffres.
std::optional<long long> python_int(std::string_view text) {
    std::size_t i = 0;
    bool negative = false;
    if (i < text.size() && (text[i] == '+' || text[i] == '-')) negative = text[i++] == '-';
    if (i >= text.size()) return std::nullopt;
    long long value = 0;
    bool previous_digit = false;
    for (; i < text.size(); ++i) {
        const char ch = text[i];
        if (ch >= '0' && ch <= '9') {
            if (value < std::numeric_limits<long long>::max() / 10) value = value * 10 + (ch - '0');  // sature
            previous_digit = true;
        } else if (ch == '_' && previous_digit && i + 1 < text.size() && text[i + 1] >= '0' && text[i + 1] <= '9') {
            previous_digit = false;
        } else {
            return std::nullopt;
        }
    }
    return negative ? -value : value;
}

// En-tetes de la requete tels que HttpHeaders.from_pairs les voit : nom en minuscules, position de la premiere
// occurrence, valeur de la derniere (S3). Valeurs en texte UTF-8 (latin-1 decode), comme les str Python.
std::vector<std::pair<std::string, std::string>> python_headers(const RequestHead& head) {
    std::vector<std::pair<std::string, std::string>> out;
    for (const auto& [name, value] : head.headers) {
        std::string lowered = ascii_lower(name);
        auto it = std::find_if(out.begin(), out.end(), [&](const auto& item) { return item.first == lowered; });
        if (it != out.end()) it->second = latin1_to_utf8(value);
        else out.emplace_back(std::move(lowered), latin1_to_utf8(value));
    }
    return out;
}

const std::string* find_header(const std::vector<std::pair<std::string, std::string>>& headers, std::string_view name) {
    for (const auto& item : headers) {
        if (item.first == name) return &item.second;
    }
    return nullptr;
}

std::vector<std::string_view> split_commas(std::string_view value) {
    std::vector<std::string_view> parts;
    std::size_t start = 0;
    while (true) {
        const std::size_t comma = value.find(',', start);
        parts.push_back(value.substr(start, comma == std::string_view::npos ? std::string_view::npos : comma - start));
        if (comma == std::string_view::npos) return parts;
        start = comma + 1;
    }
}

bool is_tchar(char ch) {
    const auto c = static_cast<unsigned char>(ch);
    if ((c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) return true;
    return std::string_view("!#$%&'*+-.^_`|~").find(ch) != std::string_view::npos;
}

// _STATUS_LINE : (HTTP/1\.[01]) ([1-5][0-9]{2})(?:[ \t][^\r\n\x00]*)?\r?\n, ligne complete.
bool parse_status_line(std::string_view line, std::string& version, int& status) {
    if (line.size() < 13 || line.substr(0, 7) != "HTTP/1." || (line[7] != '0' && line[7] != '1') || line[8] != ' ')
        return false;
    if (line[9] < '1' || line[9] > '5' || line[10] < '0' || line[10] > '9' || line[11] < '0' || line[11] > '9')
        return false;
    std::string_view rest = line.substr(12);
    if (rest.empty() || rest.back() != '\n') return false;
    rest.remove_suffix(1);
    if (!rest.empty() && rest.back() == '\r') rest.remove_suffix(1);
    if (!rest.empty()) {
        if (rest[0] != ' ' && rest[0] != '\t') return false;
        for (char ch : rest.substr(1)) {
            if (ch == '\r' || ch == '\n' || ch == '\0') return false;
        }
    }
    version = std::string(line.substr(0, 8));
    status = (line[9] - '0') * 100 + (line[10] - '0') * 10 + (line[11] - '0');
    return true;
}

// _parse_header_line : nom en tchar, valeur sans controle (tabulation permise), jamais une ligne repliee.
bool parse_header_line(std::string_view line, std::pair<std::string, std::string>& out) {
    if (!line.empty() && (line[0] == ' ' || line[0] == '\t')) return false;
    std::string_view content = line;
    if (content.size() >= 2 && content.substr(content.size() - 2) == "\r\n") content.remove_suffix(2);
    else if (!content.empty() && content.back() == '\n') content.remove_suffix(1);
    const std::size_t colon = content.find(':');
    if (colon == std::string_view::npos) return false;
    const std::string_view name = content.substr(0, colon);
    std::string_view value = content.substr(colon + 1);
    while (!value.empty() && (value.front() == ' ' || value.front() == '\t')) value.remove_prefix(1);
    while (!value.empty() && (value.back() == ' ' || value.back() == '\t')) value.remove_suffix(1);
    if (name.empty() || !std::all_of(name.begin(), name.end(), is_tchar)) return false;
    for (char ch : value) {
        const auto c = static_cast<unsigned char>(ch);
        if ((c <= 0x08) || (c >= 0x0a && c <= 0x1f) || c == 0x7f) return false;
    }
    out = {std::string(name), std::string(value)};
    return true;
}

// Ligne suivante a partir de `pos` (fin comprise) ; nullopt si incomplete.
std::optional<std::string_view> next_line(std::string_view data, std::size_t pos) {
    const std::size_t end = data.find('\n', pos);
    if (end == std::string_view::npos) return std::nullopt;
    return data.substr(pos, end + 1 - pos);
}

UpstreamHead error(std::string reason) {
    UpstreamHead head;
    head.state = UpstreamHead::State::error;
    head.reason = std::move(reason);
    return head;
}

}  // namespace

int incoming_proxy_hop_count(const Request& request) {
    const std::string* raw = request.header("x-omega-proxy-hops");
    if (raw == nullptr) return 0;
    const auto value = python_int(py_strip(latin1_to_utf8(*raw)));
    if (!value || *value < 0) return 0;
    return *value > 1000000 ? 1000000 : static_cast<int>(*value);
}

std::string without_admin_cookies(const std::string& value) {
    if (value.find("omega_admin") == std::string::npos) return value;
    std::string kept;
    std::size_t start = 0;
    while (start <= value.size()) {
        const std::size_t end = std::min(value.find(';', start), value.size());
        const std::string_view piece = py_strip(std::string_view(value).substr(start, end - start));
        const std::string_view name = py_strip(piece.substr(0, piece.find('=')));
        if (!piece.empty() && name != "omega_admin" && name != "omega_admin_theme") {
            if (!kept.empty()) kept += "; ";
            kept.append(piece);
        }
        start = end + 1;
    }
    return kept;
}

std::optional<std::string> build_upstream_request(const Request& request, const UpstreamRequestContext& context,
                                                  std::string_view body) {
    const auto headers = python_headers(*request.head);
    std::vector<std::string> named_in_connection;
    if (const std::string* connection = find_header(headers, "connection")) {
        for (std::string_view token : split_commas(*connection)) {
            const std::string_view stripped = py_strip(token);
            if (!stripped.empty()) named_in_connection.push_back(ascii_lower(stripped));
        }
    }
    if (context.preserve_upgrade) {  // lot 10 : `upgrade` nomme dans Connection reste relaye (WebSocket)
        named_in_connection.erase(std::remove(named_in_connection.begin(), named_in_connection.end(), "upgrade"),
                                  named_in_connection.end());
    }
    auto dropped = [&](const std::string& name) {
        if (context.preserve_upgrade && (name == "connection" || name == "upgrade")) {
            return contains(kDroppedFromClient, name) ||
                   std::find(named_in_connection.begin(), named_in_connection.end(), name) != named_in_connection.end();
        }
        return contains(kHopByHop, name) || contains(kDroppedFromClient, name) ||
               std::find(named_in_connection.begin(), named_in_connection.end(), name) != named_in_connection.end();
    };
    const std::string* original_host = find_header(headers, "host");
    const bool has_host = original_host != nullptr && !original_host->empty();

    std::string head = latin1_to_utf8(request.head->method) + " " + context.effective_path;
    if (!request.query_text.empty()) head += "?" + request.query_text;
    head += " HTTP/1.1\r\n";
    // Scan de securite n° 1 (2026-11-20, F8) : comme build_outgoing_headers - la longueur du client n'est jamais
    // relayee (nommee dans Connection, elle etait retiree alors que le corps partait : contrebande vers le
    // backend) ; elle est recalculee sur le corps transmis des qu'un corps a ete annonce ou recu.
    for (const auto& [name, value] : headers) {
        if (dropped(name) || name == "content-length") continue;
        if (name == "cookie") {
            // Scan de securite n° 2 (2026-11-20, F16), comme admin_cookies.py : la session de l'administration web
            // (meme hote, autre port : le navigateur l'envoie aussi au site) n'est jamais transmise au backend.
            const std::string kept = without_admin_cookies(value);
            if (!kept.empty()) head += name + ": " + kept + "\r\n";
            continue;
        }
        head += name + ": " + value + "\r\n";
    }
    if (!body.empty() || find_header(headers, "content-length") != nullptr ||
        find_header(headers, "transfer-encoding") != nullptr)
        head += "Content-Length: " + std::to_string(body.size()) + "\r\n";
    head += "Host: " + (context.zone->preserve_host && has_host ? *original_host : context.upstream->host_header) + "\r\n";
    head += "X-Forwarded-For: " + request.remote_ip + "\r\n";
    head += "X-Real-IP: " + request.remote_ip + "\r\n";
    const bool from_trusted_relay =
        context.trusted_networks != nullptr && is_trusted_proxy(request.peer_ip, *context.trusted_networks);
    std::string proto = context.client_tls ? "https" : "http";
    if (const std::string* relayed = find_header(headers, "x-forwarded-proto")) {
        const std::string candidate = ascii_lower(py_strip(*relayed));
        if (from_trusted_relay && (candidate == "http" || candidate == "https")) proto = candidate;
    }
    head += "X-Forwarded-Proto: " + proto + "\r\n";
    int port = context.listen_port;
    if (const std::string* relayed = find_header(headers, "x-forwarded-port"); relayed != nullptr && from_trusted_relay) {
        const std::string_view digits = py_strip(*relayed);
        if (!digits.empty() && std::all_of(digits.begin(), digits.end(), [](char ch) { return ch >= '0' && ch <= '9'; })) {
            std::string_view significant = digits;
            while (significant.size() > 1 && significant.front() == '0') significant.remove_prefix(1);
            if (significant.size() <= 5) {
                const int value = std::stoi(std::string(significant));
                if (value >= 1 && value <= 65535) port = value;
            }
        }
    }
    head += "X-Forwarded-Port: " + std::to_string(port) + "\r\n";
    if (has_host) head += "X-Forwarded-Host: " + *original_host + "\r\n";
    head += "X-Omega-Proxy-Hops: " + std::to_string(incoming_proxy_hop_count(request) + 1) + "\r\n\r\n";
    auto encoded = utf8_to_latin1(head);
    if (!encoded) return std::nullopt;
    encoded->append(body);
    return encoded;
}

UpstreamHead parse_upstream_head(std::string_view data, std::string_view method, bool eof, bool upgrade) {
    std::size_t pos = 0;
    int interim = 0;
    UpstreamHead head;
    while (true) {
        const auto status_line = next_line(data, pos);
        if (!status_line) {
            if (data.size() - pos > kMaxResponseLine) return error("ligne de statut trop longue");
            if (!eof) return head;
            if (pos == data.size()) {
                return error(interim == 0 ? "upstream a fermé la connexion sans réponse"
                                          : "connexion fermee apres une reponse 1xx");
            }
            return error("ligne de statut invalide");
        }
        if (status_line->size() > kMaxResponseLine) return error("ligne de statut trop longue");
        if (!parse_status_line(*status_line, head.version, head.status)) return error("ligne de statut invalide");
        pos += status_line->size();
        head.headers.clear();
        std::size_t total = 0;
        while (true) {
            const auto line = next_line(data, pos);
            if (!line) {
                if (data.size() - pos > kMaxResponseLine) return error("en-tetes de reponse trop nombreux ou trop longs");
                if (!eof) return UpstreamHead{};
                return error("en-tetes de reponse incomplets (connexion fermee)");
            }
            pos += line->size();
            if (*line == "\r\n" || *line == "\n") break;
            total += line->size();
            if (head.headers.size() >= kMaxResponseHeaders || total > kMaxResponseHeaderBytes || line->size() > kMaxResponseLine)
                return error("en-tetes de reponse trop nombreux ou trop longs");
            std::pair<std::string, std::string> header;
            if (!parse_header_line(*line, header)) return error("en-tete de reponse invalide");
            head.headers.push_back(std::move(header));
        }
        if (upgrade || head.status >= 200) break;
        if (head.status == 101) return error("101 sans demande de mise a niveau");
        if (++interim > kMaxInterimResponses) return error("trop de reponses 1xx");
    }
    head.consumed = pos;
    head.state = UpstreamHead::State::complete;
    if (upgrade) return head;  // lot 10 : rien n'est lu comme un corps (tunnel, ou refus abandonne sans son corps)
    // _body_framing (D1, D2, S9, S10)
    if (method == "HEAD" || head.status == 204 || head.status == 304) {
        head.framing = UpstreamFraming::none;
        return head;
    }
    std::vector<std::string_view> transfer_encodings;
    std::vector<std::string_view> lengths;
    for (const auto& [name, value] : head.headers) {
        const std::string lowered = ascii_lower(name);
        if (lowered == "transfer-encoding") transfer_encodings.push_back(value);
        else if (lowered == "content-length") lengths.push_back(value);
    }
    if (!transfer_encodings.empty()) {
        if (!lengths.empty()) return error("réponse avec Content-Length et Transfer-Encoding (RFC 9112 §6.3)");
        std::vector<std::string> tokens;
        for (std::string_view value : transfer_encodings) {
            const std::string text = latin1_to_utf8(value);  // garde le texte en vie pendant le decoupage
            for (std::string_view token : split_commas(text)) {
                const std::string_view stripped = py_strip(token);
                if (!stripped.empty()) tokens.push_back(ascii_lower(stripped));
            }
        }
        if (tokens.size() != 1 || tokens[0] != "chunked") return error("Transfer-Encoding non pris en charge");
        head.framing = UpstreamFraming::chunked;
        return head;
    }
    if (lengths.empty()) {
        head.framing = UpstreamFraming::close;
        return head;
    }
    // _response_content_length (D21) : chiffres ASCII seulement, en-tetes repetes de meme valeur.
    std::optional<std::uint64_t> common;
    for (std::string_view value : lengths) {
        if (value.empty() || !std::all_of(value.begin(), value.end(), [](char ch) { return ch >= '0' && ch <= '9'; }))
            return error("Content-Length invalide ou contradictoire");
        std::uint64_t parsed = 0;
        for (char ch : value) {
            const auto digit = static_cast<std::uint64_t>(ch - '0');
            parsed = parsed > (std::numeric_limits<std::uint64_t>::max() - digit) / 10
                         ? std::numeric_limits<std::uint64_t>::max()  // sature : toujours « trop grand » ensuite
                         : parsed * 10 + digit;
        }
        if (common && *common != parsed) return error("Content-Length invalide ou contradictoire");
        common = parsed;
    }
    head.framing = UpstreamFraming::length;
    head.content_length = *common;
    return head;
}

Response relayed_response(const UpstreamHead& head, std::string body, std::string_view method) {
    Response response;
    response.status = head.status;
    for (const auto& [name, value] : head.headers) {
        const std::string lowered = ascii_lower(name);
        if (contains(kHopByHop, lowered)) continue;
        std::string text = latin1_to_utf8(value);
        if (lowered == "content-length") {
            // Lot 1 (D27) : longueur calculee par le serveur, jamais recopiee - sauf HEAD (D1).
            if (method == "HEAD") response.headers.replace("Content-Length", std::move(text));
            continue;
        }
        if (lowered == "set-cookie") {
            response.headers.add("Set-Cookie", std::move(text));  // lot 1 (D6) : tous les cookies du backend
            continue;
        }
        response.headers.replace(latin1_to_utf8(name), std::move(text));
    }
    response.body = std::move(body);
    return response;
}

std::string upgrade_response_head(int status, std::string_view reason,
                                  const std::vector<std::pair<std::string, std::string>>& headers,
                                  const std::string* set_cookie) {
    std::string out = "HTTP/1.1 " + std::to_string(status) + " ";
    out += reason;
    out += "\r\n";
    for (const auto& [name, value] : headers) {
        const std::string lowered = ascii_lower(name);
        if (lowered != "connection" && lowered != "upgrade" && contains(kHopByHop, lowered)) continue;
        if (status != 101 && (lowered == "content-length" || lowered == "connection")) continue;
        out += name + ": " + value + "\r\n";
    }
    if (status != 101) out += "Content-Length: 0\r\nConnection: close\r\n";
    if (set_cookie != nullptr) out += "Set-Cookie: " + *set_cookie + "\r\n";
    out += "\r\n";
    return out;
}

bool asks_close(const UpstreamHead& head) {
    for (const auto& [name, value] : head.headers) {
        if (ascii_lower(name) != "connection") continue;
        const std::string text = latin1_to_utf8(value);
        for (std::string_view token : split_commas(text)) {
            if (ascii_lower(py_strip(token)) == "close") return true;
        }
    }
    return false;
}

void ChunkedDecoder::fail(std::string reason) {
    state_ = State::failed;
    error_ = std::move(reason);
}

void ChunkedDecoder::finish_at_eof() {
    if (state_ != State::done && state_ != State::failed) fail("flux chunked incomplet (connexion fermee)");
}

std::size_t ChunkedDecoder::feed(std::string_view input, std::string& out, std::size_t max_out) {
    std::size_t pos = 0;
    std::size_t produced = 0;
    while (pos < input.size() && state_ != State::done && state_ != State::failed) {
        const std::string_view rest = input.substr(pos);
        if (state_ == State::size_line) {
            // readline : jusqu'au premier LF ; la ligne (CRLF compris) tient en 4096 octets.
            const std::size_t lf = rest.substr(0, kMaxChunkLineBytes).find('\n');
            if (lf == std::string_view::npos) {
                if (rest.size() >= kMaxChunkLineBytes) fail("ligne de taille de bloc invalide");
                break;
            }
            const std::string_view line = rest.substr(0, lf + 1);
            if (line.size() < 2 || line[line.size() - 2] != '\r') {
                fail("ligne de taille de bloc invalide");
                break;
            }
            std::string_view size_text = line.substr(0, line.size() - 2);
            size_text = size_text.substr(0, size_text.find(';'));
            while (!size_text.empty() && (size_text.back() == ' ' || size_text.back() == '\t')) size_text.remove_suffix(1);
            if (size_text.empty() || size_text.size() > 16 || !std::all_of(size_text.begin(), size_text.end(), [](char ch) {
                    return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f') || (ch >= 'A' && ch <= 'F');
                })) {
                fail("taille de bloc invalide");
                break;
            }
            std::uint64_t size = 0;
            for (char ch : size_text) {  // 16 chiffres au plus : jamais de depassement
                const int digit = ch <= '9' ? ch - '0' : (ch | 0x20) - 'a' + 10;
                size = (size << 4) | static_cast<std::uint64_t>(digit);
            }
            pos += line.size();
            if (size == 0) {
                state_ = State::trailers;
            } else {
                remaining_ = size;
                state_ = State::data;
            }
        } else if (state_ == State::data) {
            if (produced >= max_out) break;
            const std::size_t take = static_cast<std::size_t>(
                std::min<std::uint64_t>({remaining_, rest.size(), static_cast<std::uint64_t>(max_out - produced)}));
            out.append(rest.data(), take);
            produced += take;
            pos += take;
            remaining_ -= take;
            if (remaining_ == 0) {
                state_ = State::data_crlf;
                crlf_seen_ = 0;
            }
        } else if (state_ == State::data_crlf) {
            const char expected = crlf_seen_ == 0 ? '\r' : '\n';
            if (rest[0] != expected) {
                fail("bloc sans CRLF final");
                break;
            }
            ++pos;
            if (++crlf_seen_ == 2) state_ = State::size_line;
        } else {  // trailers
            const std::size_t budget = kMaxTrailerBytes - trailer_bytes_;  // la ligne vide finale n'est pas comptee
            const std::size_t lf = rest.substr(0, std::max<std::size_t>(budget, 2)).find('\n');
            if (lf == std::string_view::npos) {
                if (rest.size() >= std::max<std::size_t>(budget, 2)) fail("trailers trop nombreux ou trop longs");
                break;
            }
            const std::string_view line = rest.substr(0, lf + 1);
            pos += line.size();
            if (line == "\r\n") {
                state_ = State::done;
                break;
            }
            if (line.size() < 2 || line[line.size() - 2] != '\r') {
                fail("trailers incomplets");
                break;
            }
            trailer_lines_ += 1;
            trailer_bytes_ += line.size();
            if (trailer_lines_ > kMaxTrailerLines || trailer_bytes_ > kMaxTrailerBytes) {
                fail("trailers trop nombreux ou trop longs");
                break;
            }
            std::pair<std::string, std::string> ignored;
            if (!parse_header_line(line, ignored)) {
                fail("en-tete de reponse invalide");
                break;
            }
        }
    }
    return pos;
}

UpstreamDecoded decode_upstream_response(std::string_view data, std::string_view method) {
    UpstreamDecoded out;
    const UpstreamHead head = parse_upstream_head(data, method, true);
    if (head.state != UpstreamHead::State::complete) {
        out.error = head.reason.empty() ? "tete incomplete" : head.reason;
        return out;
    }
    out.status = head.status;
    out.framing = head.framing;
    const std::string_view body = data.substr(head.consumed);
    if (head.framing == UpstreamFraming::none) {
        out.ok = true;
        out.rest = body.size();
    } else if (head.framing == UpstreamFraming::length) {
        if (body.size() < head.content_length) {
            out.error = "reponse incomplete";
            return out;
        }
        out.body = std::string(body.substr(0, static_cast<std::size_t>(head.content_length)));
        out.rest = body.size() - static_cast<std::size_t>(head.content_length);
        out.ok = true;
    } else if (head.framing == UpstreamFraming::chunked) {
        ChunkedDecoder decoder;
        const std::size_t consumed = decoder.feed(body, out.body);
        if (!decoder.done()) decoder.finish_at_eof();
        if (decoder.failed()) {
            out.error = decoder.error();
            out.body.clear();
            return out;
        }
        out.rest = body.size() - consumed;
        out.ok = true;
    } else {
        out.body = std::string(body);
        out.ok = true;
    }
    return out;
}

}  // namespace omega

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "ip.hpp"

#include <algorithm>
#include <cstdio>

#include "http_parser.hpp"

namespace omega {

namespace {

bool is_ascii_digit(char c) { return c >= '0' && c <= '9'; }

int hex_digit(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

std::vector<std::string_view> split(std::string_view text, char sep) {
    std::vector<std::string_view> parts;
    std::size_t start = 0;
    while (true) {
        const std::size_t pos = text.find(sep, start);
        if (pos == std::string_view::npos) {
            parts.push_back(text.substr(start));
            return parts;
        }
        parts.push_back(text.substr(start, pos - start));
        start = pos + 1;
    }
}

// ipaddress.IPv4Address._parse_octet : 1 a 3 chiffres ASCII, pas de zero initial (sauf "0"), <= 255.
std::optional<std::uint8_t> parse_octet(std::string_view octet) {
    if (octet.empty() || octet.size() > 3) return std::nullopt;
    if (!std::all_of(octet.begin(), octet.end(), is_ascii_digit)) return std::nullopt;
    if (octet.size() > 1 && octet[0] == '0') return std::nullopt;
    int value = 0;
    for (char c : octet) value = value * 10 + (c - '0');
    if (value > 255) return std::nullopt;
    return static_cast<std::uint8_t>(value);
}

std::optional<std::array<std::uint8_t, 4>> parse_ipv4(std::string_view text) {
    if (text.empty()) return std::nullopt;
    const auto parts = split(text, '.');
    if (parts.size() != 4) return std::nullopt;
    std::array<std::uint8_t, 4> out{};
    for (std::size_t i = 0; i < 4; ++i) {
        auto octet = parse_octet(parts[i]);
        if (!octet) return std::nullopt;
        out[i] = *octet;
    }
    return out;
}

// ipaddress.IPv6Address._ip_int_from_string (sans la zone)
std::optional<std::array<std::uint8_t, 16>> parse_ipv6(std::string_view text) {
    if (text.empty()) return std::nullopt;
    std::vector<std::string_view> parts = split(text, ':');
    constexpr std::size_t min_parts = 3;
    if (parts.size() < min_parts) return std::nullopt;
    std::vector<std::uint16_t> tail_v4;
    if (parts.back().find('.') != std::string_view::npos) {
        auto v4 = parse_ipv4(parts.back());
        if (!v4) return std::nullopt;
        parts.pop_back();
        parts.emplace_back("%v4hi");  // marqueurs remplaces plus bas
        parts.emplace_back("%v4lo");
        tail_v4 = {static_cast<std::uint16_t>((*v4)[0] << 8 | (*v4)[1]), static_cast<std::uint16_t>((*v4)[2] << 8 | (*v4)[3])};
    }
    constexpr std::size_t max_parts = 9;  // _HEXTET_COUNT + 1
    if (parts.size() > max_parts) return std::nullopt;
    // un seul "::" (une partie vide hors debut / fin)
    std::optional<std::size_t> skip_index;
    for (std::size_t i = 1; i + 1 < parts.size(); ++i) {
        if (parts[i].empty()) {
            if (skip_index) return std::nullopt;
            skip_index = i;
        }
    }
    std::size_t parts_hi = 0, parts_lo = 0, parts_skipped = 0;
    if (skip_index) {
        parts_hi = *skip_index;
        parts_lo = parts.size() - *skip_index - 1;
        if (parts[0].empty()) {
            if (--parts_hi != 0) return std::nullopt;  // ":" initial seul
        }
        if (parts.back().empty()) {
            if (--parts_lo != 0) return std::nullopt;  // ":" final seul
        }
        if (parts_hi + parts_lo >= 8) return std::nullopt;
        parts_skipped = 8 - (parts_hi + parts_lo);
    } else {
        if (parts.size() != 8) return std::nullopt;
        if (parts[0].empty() || parts.back().empty()) return std::nullopt;
        parts_hi = parts.size();
        parts_lo = 0;
        parts_skipped = 0;
    }
    std::vector<std::uint16_t> hextets;
    auto parse_hextet = [&](std::string_view part) -> bool {
        if (part == "%v4hi") { hextets.push_back(tail_v4[0]); return true; }
        if (part == "%v4lo") { hextets.push_back(tail_v4[1]); return true; }
        if (part.empty() || part.size() > 4) return false;
        int value = 0;
        for (char c : part) {
            const int d = hex_digit(c);
            if (d < 0) return false;
            value = value * 16 + d;
        }
        hextets.push_back(static_cast<std::uint16_t>(value));
        return true;
    };
    for (std::size_t i = 0; i < parts_hi; ++i) {
        if (!parse_hextet(parts[i])) return std::nullopt;
    }
    for (std::size_t i = 0; i < parts_skipped; ++i) hextets.push_back(0);
    for (std::size_t i = parts.size() - parts_lo; i < parts.size(); ++i) {
        if (!parse_hextet(parts[i])) return std::nullopt;
    }
    if (hextets.size() != 8) return std::nullopt;
    std::array<std::uint8_t, 16> out{};
    for (std::size_t i = 0; i < 8; ++i) {
        out[i * 2] = static_cast<std::uint8_t>(hextets[i] >> 8);
        out[i * 2 + 1] = static_cast<std::uint8_t>(hextets[i] & 0xFF);
    }
    return out;
}

bool is_ipv4_mapped(const std::array<std::uint8_t, 16>& b) {
    for (std::size_t i = 0; i < 10; ++i) {
        if (b[i] != 0) return false;
    }
    return b[10] == 0xFF && b[11] == 0xFF;
}

std::string format_ipv4(const std::uint8_t* b) {
    char buffer[16];
    std::snprintf(buffer, sizeof buffer, "%u.%u.%u.%u", b[0], b[1], b[2], b[3]);
    return buffer;
}

}  // namespace

std::optional<IpAddress> parse_ip_address(std::string_view text) {
    if (auto v4 = parse_ipv4(text)) {
        IpAddress address;
        address.version = 4;
        std::copy(v4->begin(), v4->end(), address.bytes.begin());
        return address;
    }
    // IPv6Address : zone « %xxx » (non vide, sans second %)
    std::string_view body = text;
    std::string scope;
    if (const std::size_t pct = text.find('%'); pct != std::string_view::npos) {
        const std::string_view zone = text.substr(pct + 1);
        if (zone.empty() || zone.find('%') != std::string_view::npos) return std::nullopt;
        scope.assign(zone);
        body = text.substr(0, pct);
    }
    auto v6 = parse_ipv6(body);
    if (!v6) return std::nullopt;
    IpAddress address;
    address.version = 6;
    address.bytes = *v6;
    address.scope = std::move(scope);
    return address;
}

std::string format_ip(const IpAddress& address) {
    if (address.version == 4) return format_ipv4(address.bytes.data());
    const auto& b = address.bytes;
    std::string out;
    if (is_ipv4_mapped(b)) {
        out = "::ffff:" + format_ipv4(b.data() + 12);  // Python 3.13+ : forme pointee pour une IPv4 mappee
    } else {
        std::array<std::uint16_t, 8> h{};
        for (std::size_t i = 0; i < 8; ++i) h[i] = static_cast<std::uint16_t>(b[i * 2] << 8 | b[i * 2 + 1]);
        // _compress_hextets : plus longue suite de zeros (> 1 groupe), la premiere en cas d'egalite
        int best_start = -1, best_len = 0, cur_start = -1, cur_len = 0;
        for (int i = 0; i < 8; ++i) {
            if (h[static_cast<std::size_t>(i)] == 0) {
                if (cur_start < 0) cur_start = i;
                ++cur_len;
                if (cur_len > best_len) { best_len = cur_len; best_start = cur_start; }
            } else {
                cur_start = -1;
                cur_len = 0;
            }
        }
        if (best_len < 2) best_start = -1;
        char buffer[8];
        for (int i = 0; i < 8; ++i) {
            if (i == best_start) {
                out += i == 0 ? "::" : ":";
                i += best_len - 1;
                continue;
            }
            std::snprintf(buffer, sizeof buffer, "%x", h[static_cast<std::size_t>(i)]);
            out += buffer;
            if (i != 7) out += ':';
        }
    }
    if (!address.scope.empty()) out += "%" + address.scope;
    return out;
}

std::optional<IpNetwork> parse_ip_network(std::string_view text) {
    const std::size_t slash = text.find('/');
    const std::string_view addr_part = slash == std::string_view::npos ? text : text.substr(0, slash);
    const std::optional<std::string_view> mask_part =
        slash == std::string_view::npos ? std::nullopt : std::optional<std::string_view>(text.substr(slash + 1));
    if (mask_part && mask_part->find('/') != std::string_view::npos) return std::nullopt;
    IpNetwork network;
    if (auto v4 = parse_ipv4(addr_part)) {
        network.version = 4;
        std::copy(v4->begin(), v4->end(), network.bytes.begin());
        network.prefix = 32;
        if (mask_part) {
            const std::string_view m = *mask_part;
            if (!m.empty() && std::all_of(m.begin(), m.end(), is_ascii_digit)) {
                int p = 0;
                for (char c : m) {
                    p = p * 10 + (c - '0');
                    if (p > 32) return std::nullopt;
                }
                network.prefix = p;
            } else {
                // masque pointe (255.255.255.0) ou masque inverse (0.0.0.255)
                auto mask = parse_ipv4(m);
                if (!mask) return std::nullopt;
                const std::uint32_t value = static_cast<std::uint32_t>((*mask)[0]) << 24 | static_cast<std::uint32_t>((*mask)[1]) << 16 |
                                            static_cast<std::uint32_t>((*mask)[2]) << 8 | (*mask)[3];
                auto prefix_of = [](std::uint32_t netmask) -> int {
                    int ones = 0;
                    while (ones < 32 && (netmask & (0x80000000u >> ones))) ++ones;
                    const std::uint32_t expected = ones == 0 ? 0 : 0xFFFFFFFFu << (32 - ones);
                    return netmask == expected ? ones : -1;
                };
                int p = prefix_of(value);
                if (p < 0) p = prefix_of(~value);
                if (p < 0) return std::nullopt;
                network.prefix = p;
            }
        }
    } else {
        auto v6 = parse_ipv6(addr_part);
        if (!v6) return std::nullopt;
        network.version = 6;
        network.bytes = *v6;
        network.prefix = 128;
        if (mask_part) {
            const std::string_view m = *mask_part;
            if (m.empty() || !std::all_of(m.begin(), m.end(), is_ascii_digit)) return std::nullopt;
            int p = 0;
            for (char c : m) {
                p = p * 10 + (c - '0');
                if (p > 128) return std::nullopt;
            }
            network.prefix = p;
        }
    }
    const int total = network.version == 4 ? 32 : 128;
    for (int bit = network.prefix; bit < total; ++bit) {
        network.bytes[static_cast<std::size_t>(bit / 8)] &= static_cast<std::uint8_t>(~(0x80u >> (bit % 8)));
    }
    return network;
}

bool network_contains(const IpNetwork& network, const IpAddress& address) {
    if (network.version != address.version) return false;
    for (int bit = 0; bit < network.prefix; ++bit) {
        const auto byte = static_cast<std::size_t>(bit / 8);
        const auto mask = static_cast<std::uint8_t>(0x80u >> (bit % 8));
        if ((network.bytes[byte] & mask) != (address.bytes[byte] & mask)) return false;
    }
    return true;
}

// trusted_proxy._MAX_IP_TEXT : au-dela, la chaine est rendue telle quelle (meme une IPv6 a zone longue, valide)
constexpr std::size_t max_ip_text = 45;

std::string normalize_ip(std::string_view text) {
    if (text.size() > max_ip_text) return std::string(text);
    auto address = parse_ip_address(text);
    if (!address) return std::string(text);
    if (address->version == 6 && is_ipv4_mapped(address->bytes)) return format_ipv4(address->bytes.data() + 12);
    return format_ip(*address);
}

std::vector<IpNetwork> parse_trusted_networks(const std::vector<std::string>& networks) {
    std::vector<IpNetwork> parsed;
    for (const std::string& network : networks) {
        if (auto n = parse_ip_network(network)) parsed.push_back(*n);
    }
    return parsed;
}

bool is_trusted_proxy(std::string_view peer_ip, const std::vector<IpNetwork>& trusted) {
    const std::string normalized = normalize_ip(peer_ip);
    if (normalized.size() > max_ip_text) return false;
    auto address = parse_ip_address(normalized);
    if (!address) return false;
    return std::any_of(trusted.begin(), trusted.end(), [&](const IpNetwork& n) { return network_contains(n, *address); });
}

namespace {

std::string lower_ascii(std::string_view text) {
    std::string out(text);
    for (char& c : out) {
        if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
    }
    return out;
}

// _forwarded_hop_for : champ for= d'un maillon de « Forwarded » (RFC 7239)
std::optional<std::string> forwarded_hop_for(std::string_view hop) {
    for (std::string_view part : split(hop, ';')) {
        const std::string_view stripped = python_strip(part);
        const std::size_t eq = stripped.find('=');
        const std::string_view key = python_strip(eq == std::string_view::npos ? stripped : stripped.substr(0, eq));
        if (lower_ascii(key) != "for") continue;
        std::string_view raw = eq == std::string_view::npos ? std::string_view{} : stripped.substr(eq + 1);
        raw = python_strip(raw);
        while (!raw.empty() && raw.front() == '"') raw.remove_prefix(1);  // .strip('"')
        while (!raw.empty() && raw.back() == '"') raw.remove_suffix(1);
        if (!raw.empty() && raw.front() == '[') {
            const std::string_view inside = raw.substr(1);
            return std::string(inside.substr(0, inside.find(']')));
        }
        return std::string(raw.substr(0, raw.find(':')));
    }
    return std::nullopt;
}

}  // namespace

std::vector<std::string> header_hops(std::string_view header_name, std::string_view value) {
    std::vector<std::string> hops;
    if (lower_ascii(header_name) == "forwarded") {
        for (std::string_view hop : split(value, ',')) {
            auto h = forwarded_hop_for(hop);
            if (h && !h->empty()) hops.push_back(*h);
        }
        return hops;
    }
    for (std::string_view hop : split(value, ',')) {
        const std::string_view stripped = python_strip(hop);
        if (!stripped.empty()) hops.emplace_back(stripped);
    }
    return hops;
}

std::string rightmost_untrusted(const std::vector<std::string>& hops, const std::vector<IpNetwork>& trusted) {
    for (auto it = hops.rbegin(); it != hops.rend(); ++it) {
        if (!is_trusted_proxy(*it, trusted)) return normalize_ip(*it);
    }
    return normalize_ip(hops.front());
}

}  // namespace omega

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Adresses IP et IP client derriere un proxy de confiance - reproduction EXACTE de Python 3.14 :
//   ipaddress.ip_address / str() (forme canonique), ipaddress.ip_network(strict=False), `in`,
//   domain/security/trusted_proxy.py (normalize_ip, is_trusted_proxy, resolve_client_ip).
// L'adresse produite est celle du journal d'acces, lue par fail2ban : un seul caractere d'ecart casserait
// silencieusement un ban. Verifiee contre Python par des vecteurs (tools/differential/make_vectors.py).
#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace omega {

struct IpAddress {
    int version = 4;                       // 4 ou 6
    std::array<std::uint8_t, 16> bytes{};  // IPv4 : 4 premiers octets
    std::string scope;                     // IPv6 « %zone » (sans le %)
};

std::optional<IpAddress> parse_ip_address(std::string_view text);   // ipaddress.ip_address
std::string format_ip(const IpAddress& address);                     // str(ip_address(...))

struct IpNetwork {
    int version = 4;
    std::array<std::uint8_t, 16> bytes{};  // adresse de reseau (bits d'hote a zero, strict=False)
    int prefix = 32;
};
std::optional<IpNetwork> parse_ip_network(std::string_view text);   // ipaddress.ip_network(strict=False)
bool network_contains(const IpNetwork& network, const IpAddress& address);

// trusted_proxy.py
std::string normalize_ip(std::string_view text);
bool is_trusted_proxy(std::string_view peer_ip, const std::vector<IpNetwork>& trusted);
std::vector<IpNetwork> parse_trusted_networks(const std::vector<std::string>& networks);  // invalides ignores

// `header_value(name)` : premiere valeur de l'en-tete (insensible a la casse), nullptr si absent.
template <typename HeaderLookup>
std::string resolve_client_ip(std::string_view peer_ip, HeaderLookup header_value,
                              const std::vector<IpNetwork>& trusted, const std::vector<std::string>& preference);

// Details exposes pour resolve_client_ip (et les tests).
std::vector<std::string> header_hops(std::string_view header_name, std::string_view value);
std::string rightmost_untrusted(const std::vector<std::string>& hops, const std::vector<IpNetwork>& trusted);

template <typename HeaderLookup>
std::string resolve_client_ip(std::string_view peer_ip, HeaderLookup header_value,
                              const std::vector<IpNetwork>& trusted, const std::vector<std::string>& preference) {
    std::string normalized_peer = normalize_ip(peer_ip);
    if (!is_trusted_proxy(peer_ip, trusted)) return normalized_peer;
    for (const std::string& name : preference) {
        const std::string* value = header_value(name);
        if (value == nullptr || value->empty()) continue;
        std::vector<std::string> hops = header_hops(name, *value);
        if (!hops.empty()) return rightmost_untrusted(hops, trusted);
    }
    return normalized_peer;
}

}  // namespace omega

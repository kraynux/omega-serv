// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "rate_limiter.hpp"

#include <algorithm>
#include <functional>
#include <stdexcept>

#include "static_rules.hpp"

namespace omega {

namespace {

constexpr double kTtlSeconds = 3600.0;           // rate_limit_store.py::_DEFAULT_TTL_SECONDS
constexpr double kSweepIntervalSeconds = 60.0;   // rate_limit_store.py::_SWEEP_INTERVAL_SECONDS
// Lot A (D33) : plafond du nombre d'adresses suivies (rate_limit_store.py::MAX_TRACKED_KEYS, reparti entre les
// tranches). Avant, une entree par adresse gardee 1 h sans plafond : +5,4 Mo pour 40 000 adresses IPv6 (essai du
// 2026-11-12). Table pleine : l'adresse la moins recemment vue de la tranche est remplacee (meme regle que le moteur
// Python) - elle repartira a pleine capacite si elle revient.
constexpr std::size_t kMaxTrackedKeys = 100000;
constexpr std::size_t kMaxBucketsPerShard = kMaxTrackedKeys / 64;

std::int64_t whole(const Json& object, std::string_view key) {
    const Json* value = object.get(key);
    if (value == nullptr || !std::holds_alternative<double>(value->value)) {
        throw std::runtime_error("waf_filter.rate_limit : " + std::string(key) + " manquant");
    }
    return static_cast<std::int64_t>(std::get<double>(value->value));
}

// rate_limit_policy._parse_ip : une adresse IPv6 « IPv4 mappee » compte comme l'adresse IPv4.
std::optional<IpAddress> rate_ip(std::string_view text) {
    auto address = parse_ip_address(text);
    if (!address || address->version != 6) return address;
    const auto& b = address->bytes;
    for (std::size_t i = 0; i < 10; ++i) {
        if (b[i] != 0) return address;
    }
    if (b[10] != 0xff || b[11] != 0xff) return address;
    IpAddress v4;
    v4.version = 4;
    std::copy(b.begin() + 12, b.end(), v4.bytes.begin());
    return v4;
}

}  // namespace

std::shared_ptr<const RatePolicy> RatePolicy::from_json(const Json& section) {
    if (!section.is_object()) throw std::runtime_error("waf_filter.rate_limit : objet attendu");
    auto policy = std::shared_ptr<RatePolicy>(new RatePolicy());
    const Json* global = section.get("global");
    if (global == nullptr || !global->is_object()) throw std::runtime_error("waf_filter.rate_limit.global manquant");
    policy->global_requests_ = whole(*global, "requests");
    policy->global_window_ = whole(*global, "window_seconds");
    for (const Json& rule : section.array("path_policies")) {
        policy->paths_.push_back({rule.str("prefix"), whole(rule, "requests"), whole(rule, "window_seconds")});
        policy->path_prefixes_.push_back(rule.str("prefix"));
    }
    for (const Json& rule : section.array("source_policies")) {
        const std::string network = rule.str("network");
        // Reseau illisible : ignore, comme _parse_network (deja signale par la validation Python).
        policy->sources_.push_back({network, parse_ip_network(network), whole(rule, "requests"), whole(rule, "window_seconds")});
    }
    policy->error_css_path_ = section.str("error_css_path");
    // Lot 1N : refus du natif pendant une indisponibilite du controle en fail-open (champs absents : 429, aucune).
    if (const Json* status = section.get("response_status"); status != nullptr) {
        policy->response_status_ = static_cast<int>(whole(section, "response_status"));
    }
    if (const Json* trusted = section.get("trusted_networks"); trusted != nullptr && trusted->is_array()) {
        for (const Json& network : section.array("trusted_networks")) {
            if (!network.is_string()) continue;
            if (auto parsed = parse_ip_network(network.as_string())) policy->trusted_.push_back(*parsed);
        }
    }
    return policy;
}

bool RatePolicy::trusted_source(std::string_view ip) const {
    // is_trusted_rate_limit_source : adresse IPv4 mappee comptee comme IPv4 ; illisible = non sure.
    const auto address = rate_ip(ip);
    if (!address) return false;
    for (const IpNetwork& network : trusted_) {
        if (network.version == address->version && network_contains(network, *address)) return true;
    }
    return false;
}

SelectedRate RatePolicy::select(std::string_view path, std::string_view ip) const {
    const int zone = resolve_zone_index(path, path_prefixes_);
    if (zone >= 0) {
        const PathRule& rule = paths_[static_cast<std::size_t>(zone)];
        return {std::string(ip) + "|path:" + rule.prefix, rule.requests, rule.window};
    }
    if (!sources_.empty()) {
        if (const auto address = rate_ip(ip)) {
            const SourceRule* best = nullptr;
            for (const SourceRule& rule : sources_) {
                if (!rule.network || rule.network->version != address->version) continue;
                if (!network_contains(*rule.network, *address)) continue;
                if (best == nullptr || rule.network->prefix > best->network->prefix) best = &rule;  // premier gagne
            }
            if (best != nullptr) return {std::string(ip) + "|net:" + best->network_text, best->requests, best->window};
        }
    }
    return {std::string(ip), global_requests_, global_window_};
}

bool RatePolicy::exempt(std::string_view method, std::string_view path) const {
    return (method == "GET" || method == "HEAD") && !error_css_path_.empty() && path == error_css_path_;
}

RateLimiter& RateLimiter::instance() {
    static RateLimiter limiter;
    return limiter;
}

std::optional<std::uint32_t> RateLimiter::check(const SelectedRate& rate, double now) {
    Shard& shard = shards_[std::hash<std::string>{}(rate.key) % kShards];
    std::lock_guard<std::mutex> lock(shard.mutex);
    if (now - shard.last_sweep >= kSweepIntervalSeconds) {
        shard.last_sweep = now;
        for (auto it = shard.buckets.begin(); it != shard.buckets.end();) {
            if (now - it->second.last_refill > kTtlSeconds) {
                shard.order.erase(it->second.order);
                it = shard.buckets.erase(it);
            } else {
                ++it;
            }
        }
    }
    const double capacity = static_cast<double>(rate.requests);
    const double refill_rate = rate.window_seconds > 0 ? capacity / static_cast<double>(rate.window_seconds) : capacity;
    double tokens = capacity;
    auto found = shard.buckets.find(rate.key);
    if (found != shard.buckets.end()) {
        const double elapsed = std::max(0.0, now - found->second.last_refill);
        tokens = std::min(capacity, found->second.tokens + elapsed * refill_rate);
    }
    std::optional<std::uint32_t> retry;
    if (tokens >= 1.0) {
        tokens -= 1.0;
    } else {
        const double missing = 1.0 - tokens;
        const double seconds = refill_rate > 0 ? missing / refill_rate : static_cast<double>(rate.window_seconds);
        retry = static_cast<std::uint32_t>(std::min(seconds, 4.0e9)) + 1;
    }
    if (found != shard.buckets.end()) {
        found->second.tokens = tokens;
        found->second.last_refill = now;
        shard.order.splice(shard.order.end(), shard.order, found->second.order);  // la plus recente
        return retry;
    }
    if (shard.buckets.size() >= kMaxBucketsPerShard) {  // le balayage des expirees reste periodique (cout borne)
        const auto least_recent = shard.buckets.find(*shard.order.front());  // iterateur : la cle vit dans ce noeud
        shard.order.pop_front();
        shard.buckets.erase(least_recent);
    }
    auto inserted = shard.buckets.emplace(rate.key, Bucket{tokens, now, {}}).first;
    inserted->second.order = shard.order.insert(shard.order.end(), &inserted->first);
    return retry;
}

std::size_t RateLimiter::tracked_for_tests() {
    std::size_t total = 0;
    for (Shard& shard : shards_) {
        std::lock_guard<std::mutex> lock(shard.mutex);
        total += shard.buckets.size();
    }
    return total;
}

void RateLimiter::clear_for_tests() {
    for (Shard& shard : shards_) {
        std::lock_guard<std::mutex> lock(shard.mutex);
        shard.buckets.clear();
        shard.order.clear();
        shard.last_sweep = 0.0;
    }
}

}  // namespace omega

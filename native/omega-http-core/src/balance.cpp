// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "balance.hpp"

#include <algorithm>
#include <array>
#include <cstdlib>

#include "text.hpp"

namespace omega {

const char* BackendState::status() const {
    if (manual == BackendManual::draining) return "draining";
    if (manual == BackendManual::maintenance) return "maintenance";
    return down ? "down" : "up";
}

std::shared_ptr<BackendState> ZoneBalance::backend(const std::string& key) {
    std::lock_guard<std::mutex> lock(backends_mutex_);
    auto& slot = backends[key];
    if (!slot) slot = std::make_shared<BackendState>();
    return slot;
}

void ZoneBalance::retain(const std::unordered_set<std::string>& keys) {
    std::lock_guard<std::mutex> zone_lock(mutex);
    std::lock_guard<std::mutex> lock(backends_mutex_);
    for (auto it = backends.begin(); it != backends.end();) {
        it = keys.count(it->first) ? std::next(it) : backends.erase(it);
    }
    for (auto it = weighted_current.begin(); it != weighted_current.end();) {
        it = keys.count(it->first) ? std::next(it) : weighted_current.erase(it);
    }
}

void BalanceRegistry::retain(const ProxySettings* proxy) {
    std::unordered_map<std::string, std::unordered_set<std::string>> wanted;
    if (proxy != nullptr) {
        for (const ProxyZoneSettings& zone : proxy->zones) {
            if (!zone.native) continue;
            auto& keys = wanted[zone.prefix];
            for (const ProxyUpstream& upstream : zone.upstreams) keys.insert(upstream.key);
        }
    }
    std::vector<std::pair<std::shared_ptr<ZoneBalance>, std::unordered_set<std::string>>> kept;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        for (auto it = zones_.begin(); it != zones_.end();) {
            const auto found = wanted.find(it->first);
            if (found == wanted.end()) {
                it = zones_.erase(it);
            } else {
                kept.emplace_back(it->second, found->second);
                ++it;
            }
        }
    }
    for (auto& [balance, keys] : kept) balance->retain(keys);
}

std::shared_ptr<ZoneBalance> BalanceRegistry::zone(const std::string& prefix) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto& slot = zones_[prefix];
    if (!slot) slot = std::make_shared<ZoneBalance>();
    return slot;
}

std::vector<BalanceRegistry::Report> BalanceRegistry::report(const ProxySettings& proxy) {
    std::vector<Report> out;
    for (const ProxyZoneSettings& zone : proxy.zones) {
        if (!zone.native) continue;
        const auto balance = this->zone(zone.prefix);
        for (const ProxyUpstream& upstream : zone.upstreams) {
            const auto state = balance->backend(upstream.key);
            Report report{zone.prefix, upstream.key, upstream.name, "", state->active.load()};
            report.requests = state->requests.load(std::memory_order_relaxed);
            report.errors_502 = state->errors_502.load(std::memory_order_relaxed);
            report.errors_504 = state->errors_504.load(std::memory_order_relaxed);
            {
                std::lock_guard<std::mutex> lock(state->mutex);
                report.status = upstream.unusable ? "down" : state->status();
                if (state->response_avg_seconds) {
                    report.avg_us = static_cast<std::int64_t>(*state->response_avg_seconds * 1e6);
                }
            }
            out.push_back(std::move(report));
        }
    }
    return out;
}

std::uint32_t crc32(std::string_view data) {
    static const std::array<std::uint32_t, 256> table = [] {
        std::array<std::uint32_t, 256> t{};
        for (std::uint32_t i = 0; i < 256; ++i) {
            std::uint32_t c = i;
            for (int k = 0; k < 8; ++k) c = (c & 1u) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
            t[i] = c;
        }
        return t;
    }();
    std::uint32_t crc = 0xFFFFFFFFu;
    for (const char ch : data) crc = table[(crc ^ static_cast<unsigned char>(ch)) & 0xFFu] ^ (crc >> 8);
    return crc ^ 0xFFFFFFFFu;
}

std::optional<std::string> cookie_value(std::string_view header, std::string_view name) {
    std::optional<std::string> found;
    std::size_t start = 0;
    while (start <= header.size()) {
        const std::size_t semicolon = header.find(';', start);
        const std::string_view chunk =
            py_strip(header.substr(start, semicolon == std::string_view::npos ? std::string_view::npos : semicolon - start));
        const std::size_t equal = chunk.find('=');
        if (equal != std::string_view::npos && equal > 0 && chunk.substr(0, equal) == name) {
            found = std::string(chunk.substr(equal + 1));
        }
        if (semicolon == std::string_view::npos) break;
        start = semicolon + 1;
    }
    return found;
}

namespace {

// _header_value_matches : egalite, ou prefixe si le motif finit par « * ».
bool header_matches(std::string_view value, std::string_view pattern) {
    if (!pattern.empty() && pattern.back() == '*') return value.substr(0, pattern.size() - 1) == pattern.substr(0, pattern.size() - 1);
    return value == pattern;
}

struct Chooser {
    ZoneBalance& balance;
    const ProxyZoneSettings& zone;
    const BalanceRequest& request;
    BalanceClock::time_point now;
    std::vector<std::shared_ptr<BackendState>> states;

    [[nodiscard]] bool up(std::size_t i) const {
        std::lock_guard<std::mutex> lock(states[i]->mutex);
        return std::string_view(states[i]->status()) == "up";
    }

    [[nodiscard]] bool at_capacity(std::size_t i) const {
        const auto& limit = zone.upstreams[i].max_concurrent;
        return limit && states[i]->active.load() >= *limit;
    }

    // ProxyHealthState.start_half_open_trial
    bool start_trial(std::size_t i) {
        BackendState& state = *states[i];
        std::lock_guard<std::mutex> lock(state.mutex);
        if (std::string_view(state.status()) != "down") return false;
        if (state.trial_started && now - *state.trial_started < kPassiveRetry) return false;
        if (now - state.down_since < kPassiveRetry) return false;
        state.trial_started = now;
        return true;
    }

    Selection choose(std::size_t i) {
        states[i]->active.fetch_add(1);  // acquire, sous le verrou de la zone : plafond exact
        Selection selection;
        selection.result = Selection::Result::chosen;
        selection.index = i;
        selection.state = states[i];
        return selection;
    }

    [[nodiscard]] std::int64_t weight(std::size_t i) const { return std::max(1, zone.upstreams[i].weight); }

    // ProxyLoadBalancerState.select
    std::size_t pick(const std::vector<std::size_t>& candidates) {
        const std::string& strategy = zone.load_balancing;
        if (strategy == "weighted_round_robin") {
            std::int64_t total = 0;
            for (std::size_t i : candidates) total += weight(i);
            std::optional<std::size_t> chosen;
            std::int64_t chosen_value = 0;
            for (std::size_t i : candidates) {
                std::int64_t& value = balance.weighted_current[zone.upstreams[i].key];
                value += weight(i);
                if (!chosen || value > chosen_value) {
                    chosen = i;
                    chosen_value = value;
                }
            }
            balance.weighted_current[zone.upstreams[*chosen].key] -= total;
            return *chosen;
        }
        if (strategy == "least_connections" || strategy == "weighted_least_connections") {
            return least_connections(candidates, strategy == "weighted_least_connections");
        }
        if (strategy == "ip_hash") {
            std::vector<std::size_t> expanded;
            for (std::size_t i : candidates) expanded.insert(expanded.end(), static_cast<std::size_t>(weight(i)), i);
            return expanded[crc32(request.client_ip) % expanded.size()];
        }
        if (strategy == "least_response_time") {
            std::size_t best = candidates.front();
            double best_value = 0;
            bool first = true;
            for (std::size_t i : candidates) {
                double value = 0.0;
                {
                    std::lock_guard<std::mutex> lock(states[i]->mutex);
                    value = states[i]->response_avg_seconds.value_or(0.0);
                }
                if (first || value < best_value) {
                    best = i;
                    best_value = value;
                    first = false;
                }
            }
            return best;
        }
        if (strategy == "real_load") {
            std::optional<std::size_t> best;
            double best_score = 0;
            for (std::size_t i : candidates) {
                std::optional<double> score;
                {
                    std::lock_guard<std::mutex> lock(states[i]->mutex);
                    if (states[i]->load_score &&
                        now - states[i]->load_at <= std::chrono::milliseconds(zone.load_sample_max_age_ms))
                        score = states[i]->load_score;
                }
                if (score && (!best || *score < best_score)) {
                    best = i;
                    best_score = *score;
                }
            }
            if (best) return *best;
            return least_connections(candidates, false);  // repli (§19.2, §25)
        }
        // round_robin (et toute valeur inconnue, comme Python)
        const std::size_t index = balance.round_robin_next % candidates.size();
        balance.round_robin_next = index + 1;
        return candidates[index];
    }

    std::size_t least_connections(const std::vector<std::size_t>& candidates, bool weighted) {
        std::size_t best = candidates.front();
        double best_load = 0;
        bool first = true;
        for (std::size_t i : candidates) {
            const auto count = static_cast<double>(states[i]->active.load());
            const double load = weighted ? count / static_cast<double>(weight(i)) : count;
            if (first || load < best_load) {
                best = i;
                best_load = load;
                first = false;
            }
        }
        return best;
    }
};

}  // namespace

Selection select_backend(ZoneBalance& balance, const ProxyZoneSettings& zone, const BalanceRequest& request,
                         const std::unordered_set<std::string>& exclude, BalanceClock::time_point now) {
    std::lock_guard<std::mutex> lock(balance.mutex);
    Chooser chooser{balance, zone, request, now, {}};
    for (const ProxyUpstream& upstream : zone.upstreams) chooser.states.push_back(balance.backend(upstream.key));
    const std::size_t count = zone.upstreams.size();
    auto candidate = [&](std::size_t i) { return !zone.upstreams[i].unusable && exclude.count(zone.upstreams[i].key) == 0; };
    auto usable = [&](std::size_t i) { return candidate(i) && chooser.up(i) && !chooser.at_capacity(i); };

    // 1. regle d'en-tete : la premiere qui correspond et dont la cible existe ; une cible inutilisable passe la main.
    for (const ProxyRoutingRule& rule : zone.routing_rules) {
        const auto value = request.header(rule.header);
        if (!value || !header_matches(*value, rule.pattern)) continue;
        std::vector<std::size_t> targets;
        bool exists = false;
        for (std::size_t i = 0; i < count; ++i) {
            if (zone.upstreams[i].name != rule.upstream) continue;
            exists = true;
            if (usable(i)) targets.push_back(i);
        }
        if (!exists) continue;
        if (targets.size() == 1) return chooser.choose(targets.front());
        if (!targets.empty()) return chooser.choose(chooser.pick(targets));  // nom DNS : parmi ses adresses
        break;
    }
    // 2. cookie collant (valeur par adresse)
    if (zone.sticky) {
        if (const auto header = request.header("cookie")) {
            if (const auto value = cookie_value(*header, zone.sticky->cookie_name)) {
                for (std::size_t i = 0; i < count; ++i) {
                    if (zone.upstreams[i].cookie == *value) {
                        if (usable(i)) return chooser.choose(i);
                        break;
                    }
                }
            }
        }
    }
    // 3. strategie : essai a demi ouvert d'un DOWN (D7, Q10), sinon parmi les sains avec de la place.
    std::vector<std::size_t> remaining;
    for (std::size_t i = 0; i < count; ++i) {
        if (candidate(i)) remaining.push_back(i);
    }
    if (remaining.empty()) return Selection{};
    for (std::size_t i : remaining) {
        if (!zone.upstreams[i].active_check && !chooser.at_capacity(i) && chooser.start_trial(i)) return chooser.choose(i);
    }
    std::vector<std::size_t> healthy;
    for (std::size_t i : remaining) {
        if (chooser.up(i)) healthy.push_back(i);
    }
    if (healthy.empty()) return chooser.choose(chooser.pick(remaining));  // rien de sain : le moins pire (§18.1)
    std::vector<std::size_t> room;
    for (std::size_t i : healthy) {
        if (!chooser.at_capacity(i)) room.push_back(i);
    }
    if (room.empty()) {
        Selection full;
        full.result = Selection::Result::at_capacity;
        return full;
    }
    return chooser.choose(chooser.pick(room));
}

void release_backend(BackendState& state) {
    std::int64_t current = state.active.load();
    while (current > 0 && !state.active.compare_exchange_weak(current, current - 1)) {
    }
}

void record_backend_success(BackendState& state, int healthy_after) {
    std::lock_guard<std::mutex> lock(state.mutex);
    state.consecutive_failures = 0;
    state.consecutive_successes += 1;
    const bool trial = state.trial_started.has_value();
    state.trial_started.reset();
    if (state.consecutive_successes >= healthy_after || trial) state.down = false;
}

void record_backend_failure(BackendState& state, int unhealthy_after, BalanceClock::time_point now) {
    std::lock_guard<std::mutex> lock(state.mutex);
    state.consecutive_successes = 0;
    state.consecutive_failures += 1;
    const bool trial = state.trial_started.has_value();
    state.trial_started.reset();
    if (state.consecutive_failures >= unhealthy_after || trial) {
        state.down = true;
        state.down_since = now;
    }
}

void record_response_time(BackendState& state, double seconds) {
    std::lock_guard<std::mutex> lock(state.mutex);
    state.response_avg_seconds =
        state.response_avg_seconds ? *state.response_avg_seconds * 0.7 + seconds * 0.3 : seconds;
}

bool apply_backend_event(BalanceRegistry& registry, const ProxySettings& proxy, std::string_view zone_prefix,
                         std::string_view name, std::string_view kind, std::string_view value,
                         BalanceClock::time_point now) {
    std::optional<double> score;
    if (kind == "load") {
        const std::string text(value);
        char* end = nullptr;
        const double parsed = std::strtod(text.c_str(), &end);
        if (text.empty() || end != text.c_str() + text.size() || !(parsed >= 0 && parsed <= 100)) return false;
        score = parsed;
    } else if (!(kind == "probe" && (value == "ok" || value == "fail")) &&
               !(kind == "manual" && (value == "draining" || value == "maintenance" || value == "clear"))) {
        return false;
    }
    for (const ProxyZoneSettings& zone : proxy.zones) {
        if (zone.prefix != zone_prefix) continue;
        const auto balance = registry.zone(zone.prefix);
        for (const ProxyUpstream& upstream : zone.upstreams) {
            if (upstream.name != name) continue;
            const auto state = balance->backend(upstream.key);
            if (kind == "probe" && value == "ok") {
                record_backend_success(*state, zone.healthy_after);
            } else if (kind == "probe") {
                record_backend_failure(*state, zone.unhealthy_after, now);
            } else if (kind == "load") {
                std::lock_guard<std::mutex> lock(state->mutex);
                state->load_score = score;
                state->load_at = now;
            } else {
                std::lock_guard<std::mutex> lock(state->mutex);
                state->manual = value == "draining"      ? BackendManual::draining
                                : value == "maintenance" ? BackendManual::maintenance
                                                         : BackendManual::none;
            }
        }
    }
    return true;
}

}  // namespace omega

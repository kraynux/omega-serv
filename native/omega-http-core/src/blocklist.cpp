// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "blocklist.hpp"

#include <sys/stat.h>

#include <cerrno>

#include <fstream>
#include <map>
#include <memory>
#include <sstream>

#include "util.hpp"

namespace omega {

namespace {

// Jours depuis 1970-01-01 (algorithme civil de H. Hinnant).
std::int64_t days_from_civil(std::int64_t y, unsigned m, unsigned d) {
    y -= m <= 2;
    const std::int64_t era = (y >= 0 ? y : y - 399) / 400;
    const auto yoe = static_cast<unsigned>(y - era * 400);
    const unsigned doy = (153 * (m > 2 ? m - 3 : m + 9) + 2) / 5 + d - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + static_cast<std::int64_t>(doe) - 719468;
}

bool digits(std::string_view text, std::size_t at, std::size_t count, int& out) {
    if (at + count > text.size()) return false;
    out = 0;
    for (std::size_t i = 0; i < count; ++i) {
        const char ch = text[at + i];
        if (ch < '0' || ch > '9') return false;
        out = out * 10 + (ch - '0');
    }
    return true;
}

}  // namespace

std::optional<std::int64_t> NativeBlocklist::parse_iso_datetime_us(std::string_view text) {
    // datetime.fromisoformat (formes ecrites par omega-serv et par un humain) : AAAA-MM-JJ[(T| )HH:MM[:SS[.f+]]][Z|±HH:MM|±HHMM]
    int year = 0, month = 0, day = 0, hour = 0, minute = 0, second = 0;
    if (!digits(text, 0, 4, year) || text.size() < 10 || text[4] != '-' || !digits(text, 5, 2, month) || text[7] != '-' ||
        !digits(text, 8, 2, day))
        return std::nullopt;
    if (month < 1 || month > 12 || day < 1 || day > 31) return std::nullopt;
    std::size_t at = 10;
    std::int64_t micros = 0;
    if (at < text.size() && (text[at] == 'T' || text[at] == ' ')) {
        if (!digits(text, at + 1, 2, hour) || at + 3 >= text.size() || text[at + 3] != ':' || !digits(text, at + 4, 2, minute))
            return std::nullopt;
        at += 6;
        if (at < text.size() && text[at] == ':') {
            if (!digits(text, at + 1, 2, second)) return std::nullopt;
            at += 3;
            if (at < text.size() && (text[at] == '.' || text[at] == ',')) {
                ++at;
                int count = 0;
                std::int64_t fraction = 0;
                while (at < text.size() && text[at] >= '0' && text[at] <= '9') {
                    if (count < 6) fraction = fraction * 10 + (text[at] - '0');
                    ++count;
                    ++at;
                }
                if (count == 0) return std::nullopt;
                for (int i = count; i < 6; ++i) fraction *= 10;
                micros = fraction;
            }
        }
        if (hour > 23 || minute > 59 || second > 59) return std::nullopt;
    }
    std::int64_t offset_seconds = 0;  // sans fuseau : UTC (comme `_parsed_expiry`)
    if (at < text.size()) {
        if (text[at] == 'Z') {
            ++at;
        } else if (text[at] == '+' || text[at] == '-') {
            const int sign = text[at] == '-' ? -1 : 1;
            int oh = 0, om = 0;
            if (!digits(text, at + 1, 2, oh)) return std::nullopt;
            std::size_t next = at + 3;
            if (next < text.size() && text[next] == ':') ++next;
            if (!digits(text, next, 2, om)) return std::nullopt;
            at = next + 2;
            offset_seconds = sign * (oh * 3600 + om * 60);
        } else {
            return std::nullopt;
        }
    }
    if (at != text.size()) return std::nullopt;
    const std::int64_t seconds = days_from_civil(year, static_cast<unsigned>(month), static_cast<unsigned>(day)) * 86400 +
                                 hour * 3600 + minute * 60 + second - offset_seconds;
    return seconds * 1000000 + micros;
}

std::optional<std::vector<NativeBlocklist::Entry>> NativeBlocklist::parse(std::string_view json_text) {
    const auto root = parse_json(json_text);
    if (!root || !root->is_object()) return std::nullopt;
    const Json* list = root->get("entries");
    if (list == nullptr || !list->is_array()) return std::nullopt;
    std::vector<Entry> entries;
    for (const Json& item : *std::get<std::shared_ptr<JsonArray>>(list->value)) {
        if (!item.is_object()) continue;
        const Json* network_field = item.get("network");
        if (network_field == nullptr || !network_field->is_string()) continue;
        const auto network = parse_ip_network(network_field->as_string());
        if (!network) continue;  // reseau illisible : ignore, comme BlocklistIndex
        Entry entry{*network, std::nullopt};
        const Json* expires = item.get("expires_at");
        if (expires != nullptr && expires->is_string()) entry.expires_unix_us = parse_iso_datetime_us(expires->as_string());
        entries.push_back(entry);  // date illisible : expires vide = tenue active (mode degrade)
    }
    return entries;
}

void NativeBlocklist::refresh_if_due() {
    const auto now = std::chrono::steady_clock::now();
    if (now < next_check_) return;
    next_check_ = now + std::chrono::seconds(1);
    refresh();
}

void NativeBlocklist::refresh() {
    struct stat info {};
    if (::stat(path_.c_str(), &info) != 0) {
        const bool absent = errno == ENOENT;
        entries_.clear();  // pas de fichier : aucun ban (comme un store vide)
        file_mtime_ns_ = -1;
        current_ = absent;  // autre erreur (droits...) : etat inconnu, aucune indication
        return;
    }
    const std::int64_t mtime = static_cast<std::int64_t>(info.st_mtim.tv_sec) * 1000000000 + info.st_mtim.tv_nsec;
    if (mtime == file_mtime_ns_ && static_cast<std::int64_t>(info.st_size) == file_size_ && info.st_ino == file_inode_) {
        current_ = true;
        return;
    }
    std::ifstream file(path_, std::ios::binary);
    std::ostringstream buffer;
    buffer << file.rdbuf();
    auto parsed = file ? parse(buffer.str()) : std::nullopt;
    if (parsed) {
        entries_ = std::move(*parsed);
        file_mtime_ns_ = mtime;
        file_size_ = static_cast<std::int64_t>(info.st_size);
        file_inode_ = info.st_ino;
        current_ = true;
    } else {
        current_ = false;  // illisible (ecriture en cours...) : derniere liste valide gardee, relu au prochain tour
    }
}

bool NativeBlocklist::blocked_locked(const IpAddress& address, std::int64_t now_unix_us) const {
    for (const Entry& entry : entries_) {
        if (!network_contains(entry.network, address)) continue;
        if (!entry.expires_unix_us || now_unix_us < *entry.expires_unix_us) return true;
    }
    return false;
}

bool NativeBlocklist::is_blocked(std::string_view ip, std::int64_t now_unix_us) {
    const auto address = parse_ip_address(ip);
    if (!address) return false;
    std::lock_guard<std::mutex> lock(mutex_);
    refresh_if_due();
    return blocked_locked(*address, now_unix_us);
}

bool NativeBlocklist::known_clear(std::string_view ip, std::int64_t now_unix_us) {
    const auto address = parse_ip_address(ip);
    if (!address) return false;  // adresse illisible : Python tranche
    std::lock_guard<std::mutex> lock(mutex_);
    refresh();
    next_check_ = std::chrono::steady_clock::now() + std::chrono::seconds(1);
    return current_ && !blocked_locked(*address, now_unix_us);
}

NativeBlocklist& blocklist_for(const std::string& path) {
    static std::mutex mutex;
    static std::map<std::string, std::unique_ptr<NativeBlocklist>> lists;
    std::lock_guard<std::mutex> lock(mutex);
    auto& list = lists[path];
    if (!list) list = std::make_unique<NativeBlocklist>(path);
    return *list;
}

}  // namespace omega

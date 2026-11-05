// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "watch_list.hpp"

namespace omega {

WatchList& WatchList::instance() {
    static WatchList list;
    return list;
}

void WatchList::purge_locked(std::int64_t now) {
    for (auto it = entries_.begin(); it != entries_.end();) {
        if (it->second <= now) it = entries_.erase(it);
        else ++it;
    }
    count_.store(entries_.size());
    if (entries_.size() < kMaxEntries) overflow_.store(false);
}

bool WatchList::add(std::string ip, std::int64_t until, std::int64_t now) {
    if (until <= now) return true;  // deja echue : rien a suivre
    std::lock_guard<std::mutex> lock(mutex_);
    auto found = entries_.find(ip);
    if (found != entries_.end()) {
        if (until > found->second) found->second = until;  // jamais raccourcie
        return true;
    }
    if (entries_.size() >= kMaxEntries) purge_locked(now);
    if (entries_.size() >= kMaxEntries) {
        overflow_.store(true);
        return false;
    }
    entries_.emplace(std::move(ip), until);
    count_.store(entries_.size());
    return true;
}

bool WatchList::requires_python(std::string_view ip, std::int64_t now) {
    if (count_.load() == 0 && !overflow_.load()) return false;
    std::lock_guard<std::mutex> lock(mutex_);
    if (overflow_.load()) {
        purge_locked(now);
        if (overflow_.load()) return true;
    }
    const auto found = entries_.find(std::string(ip));
    if (found == entries_.end()) return false;
    if (found->second > now) return true;
    entries_.erase(found);
    count_.store(entries_.size());
    return false;
}

std::size_t WatchList::size() {
    std::lock_guard<std::mutex> lock(mutex_);
    return entries_.size();
}

void WatchList::clear_for_tests() {
    std::lock_guard<std::mutex> lock(mutex_);
    entries_.clear();
    count_.store(0);
    overflow_.store(false);
}

}  // namespace omega

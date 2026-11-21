// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "blocklist.hpp"

#include <sys/inotify.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <unistd.h>

#include <cerrno>

#include <fstream>
#include <array>
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

namespace {

// Cle d'une adresse exacte : version puis octets (la zone IPv6 n'entre pas dans `in network`, comme Python).
std::string host_key(int version, const std::array<std::uint8_t, 16>& bytes) {
    const std::size_t size = version == 4 ? 4 : 16;
    std::string key(1, static_cast<char>(version));
    key.append(reinterpret_cast<const char*>(bytes.data()), size);
    return key;
}

bool active(const std::optional<std::int64_t>& expires_unix_us, std::int64_t now_unix_us) {
    return !expires_unix_us || now_unix_us < *expires_unix_us;
}

}  // namespace

bool NativeBlocklist::Index::blocked(const IpAddress& address, std::int64_t now_unix_us) const {
    if (const auto found = hosts.find(host_key(address.version, address.bytes)); found != hosts.end()) {
        for (const auto& expires : found->second) {
            if (active(expires, now_unix_us)) return true;
        }
    }
    for (const Entry& entry : networks) {
        if (network_contains(entry.network, address) && active(entry.expires_unix_us, now_unix_us)) return true;
    }
    return false;
}

NativeBlocklist::~NativeBlocklist() {
    if (inotify_fd_ >= 0) ::close(inotify_fd_);
}

NativeBlocklist::State NativeBlocklist::loaded_state() {
    std::lock_guard<std::mutex> lock(mutex_);
    return state_;
}

NativeBlocklist::State NativeBlocklist::refreshed_state(bool reload_held) {
    struct stat info {};
    if (::stat(path_.c_str(), &info) != 0) {
        const bool absent = errno == ENOENT;
        std::lock_guard<std::mutex> lock(mutex_);
        if (state_.file || !state_.index->hosts.empty() || !state_.index->networks.empty()) {
            state_.index = std::make_shared<Index>();  // pas de fichier : aucun ban (comme un store vide)
        }
        state_.file.reset();
        state_.current = absent;  // autre erreur (droits...) : etat inconnu, aucune indication
        return state_;
    }
    const FileId id{static_cast<std::int64_t>(info.st_mtim.tv_sec) * 1000000000 + info.st_mtim.tv_nsec,
                    static_cast<std::int64_t>(info.st_size), static_cast<std::uint64_t>(info.st_ino)};
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (state_.file == id) {
            state_.current = true;
            return state_;
        }
    }
    std::unique_lock<std::mutex> reload(reload_mutex_, std::defer_lock);
    if (!reload_held) reload.lock();
    {
        std::lock_guard<std::mutex> lock(mutex_);  // un autre fil a peut-etre deja relu ce fichier
        if (state_.file == id) {
            state_.current = true;
            return state_;
        }
    }
    std::ifstream file(path_, std::ios::binary);
    std::ostringstream buffer;
    buffer << file.rdbuf();
    auto parsed = file ? parse(buffer.str()) : std::nullopt;
    std::lock_guard<std::mutex> lock(mutex_);
    if (!parsed) {
        state_.current = false;  // illisible (ecriture en cours...) : derniere liste valide gardee, relu au prochain tour
        return state_;
    }
    auto index = std::make_shared<Index>();
    for (const Entry& entry : *parsed) {
        const int host_prefix = entry.network.version == 4 ? 32 : 128;
        if (entry.network.prefix == host_prefix) {
            index->hosts[host_key(entry.network.version, entry.network.bytes)].push_back(entry.expires_unix_us);
        } else {
            index->networks.push_back(entry);
        }
    }
    state_.index = std::move(index);
    state_.file = id;
    state_.current = true;
    return state_;
}

namespace {

std::int64_t steady_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

// Systemes de fichiers ou inotify ne voit pas les ecritures faites ailleurs : stat() a chaque appel.
bool remote_filesystem(const struct statfs& fs) {
    switch (static_cast<std::uint64_t>(fs.f_type)) {
        case 0x6969:      // NFS
        case 0x517B:      // SMB
        case 0xFF534D42:  // CIFS
        case 0xFE534D42:  // SMB2
        case 0x65735546:  // FUSE
        case 0x01021997:  // 9P
        case 0x00C36400:  // Ceph
        case 0x5346414F:  // AFS
            return true;
        default:
            return false;
    }
}

}  // namespace

void NativeBlocklist::try_start_watch() {
    const std::int64_t now = steady_ns();
    if (now < next_watch_attempt_ns_.load()) return;
    std::lock_guard<std::mutex> reload(reload_mutex_);
    if (watching_.load() || now < next_watch_attempt_ns_.load()) return;
    next_watch_attempt_ns_.store(now + INT64_C(1000000000));
    if (path_.empty() || path_[0] != '/' || path_.back() == '/') return;
    // Dossiers du chemin, de la racine au dossier du fichier, chacun avec l'element qui le suit.
    std::vector<std::pair<std::string, std::string>> levels;
    std::size_t start = 1;
    std::string dir = "/";
    while (true) {
        const std::size_t slash = path_.find('/', start);
        const std::string name = path_.substr(start, slash == std::string::npos ? std::string::npos : slash - start);
        if (name.empty() || name == "." || name == "..") return;  // chemin non canonique : stat() a chaque appel
        levels.emplace_back(dir, name);
        if (slash == std::string::npos) break;
        dir = (dir == "/" ? "" : dir) + "/" + name;
        start = slash + 1;
    }
    struct stat link {};
    if (::lstat(path_.c_str(), &link) == 0 && S_ISLNK(link.st_mode)) return;  // la cible changerait sans evenement
    for (const auto& [level, name] : levels) {
        if (::lstat(level.c_str(), &link) != 0 || !S_ISDIR(link.st_mode)) return;  // absent, ou lien symbolique
    }
    struct statfs fs {};
    if (::statfs(levels.back().first.c_str(), &fs) != 0 || remote_filesystem(fs)) return;
    if (inotify_fd_ < 0) {
        const int fd = ::inotify_init1(IN_NONBLOCK | IN_CLOEXEC);
        if (fd < 0) return;  // limite d'instances inotify atteinte : stat() a chaque appel
        inotify_fd_ = fd;
    }
    for (const Watch& watch : watches_) (void)::inotify_rm_watch(inotify_fd_, watch.wd);
    watches_.clear();
    constexpr std::uint32_t kStructure = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO | IN_DELETE_SELF |
                                         IN_MOVE_SELF | IN_ONLYDIR | IN_DONT_FOLLOW;
    for (std::size_t i = 0; i < levels.size(); ++i) {
        const bool leaf = i + 1 == levels.size();
        const std::uint32_t mask = leaf ? kStructure | IN_MODIFY | IN_CLOSE_WRITE | IN_ATTRIB : kStructure;
        const int wd = ::inotify_add_watch(inotify_fd_, levels[i].first.c_str(), mask);
        if (wd < 0) {  // limite de surveillances atteinte : stat() a chaque appel
            for (const Watch& watch : watches_) (void)::inotify_rm_watch(inotify_fd_, watch.wd);
            watches_.clear();
            return;
        }
        watches_.push_back({wd, levels[i].second, leaf});
    }
    needs_reload_.store(true);  // premiere verification apres le debut de la surveillance : stat() et relecture
    watching_.store(true);
}

void NativeBlocklist::stop_watch_locked() {
    needs_reload_.store(true);
    watching_.store(false);
    for (const Watch& watch : watches_) {
        (void)::inotify_rm_watch(inotify_fd_, watch.wd);  // peut echouer : surveillance deja retiree par le noyau
    }
    watches_.clear();
    next_watch_attempt_ns_.store(steady_ns() + INT64_C(1000000000));
}

NativeBlocklist::State NativeBlocklist::reload_after_events() {
    std::lock_guard<std::mutex> reload(reload_mutex_);
    // Annonce AVANT de vider la file : un fil qui trouve ensuite la file vide voit aussi ce drapeau et attend.
    reloading_.store(true);
    bool changed = needs_reload_.load() || !watching_.load();
    if (watching_.load()) {
        alignas(struct inotify_event) char buffer[8192];
        bool lost = false;
        while (true) {
            const ssize_t n = ::read(inotify_fd_, buffer, sizeof buffer);
            if (n < 0 && errno == EINTR) continue;
            if (n < 0) {
                lost = lost || (errno != EAGAIN && errno != EWOULDBLOCK);
                break;
            }
            if (n == 0) break;
            for (char* cursor = buffer; cursor < buffer + n;) {
                const auto* event = reinterpret_cast<const struct inotify_event*>(cursor);
                cursor += sizeof(struct inotify_event) + event->len;
                if (event->mask & IN_Q_OVERFLOW) {  // evenements perdus : le stat() qui suit tranche
                    changed = true;
                    continue;
                }
                if (event->mask & (IN_IGNORED | IN_DELETE_SELF | IN_MOVE_SELF | IN_UNMOUNT)) {
                    lost = true;  // un dossier du chemin a disparu ou bouge
                    continue;
                }
                const std::string_view name = event->len > 0 ? std::string_view(event->name) : std::string_view();
                for (const Watch& watch : watches_) {
                    if (watch.wd != event->wd || name != watch.child) continue;
                    if (watch.leaf) changed = true;  // le fichier lui-meme
                    else lost = true;                // un dossier du chemin supprime, renomme ou recree
                }
            }
        }
        if (lost) {
            stop_watch_locked();
            changed = true;
        }
    }
    const State state = changed ? refreshed_state(true) : loaded_state();
    needs_reload_.store(!state.current);  // illisible ou etat inconnu : relire au prochain appel
    reloading_.store(false);
    return state;
}

NativeBlocklist::State NativeBlocklist::current_state() {
    if (watching_.load()) {
        int pending = 0;
        // Ordre voulu : la file d'abord, les drapeaux ensuite (voir reload_after_events).
        if (::ioctl(inotify_fd_, FIONREAD, &pending) == 0 && pending == 0 && !needs_reload_.load() &&
            !reloading_.load()) {
            return loaded_state();
        }
        return reload_after_events();
    }
    const State state = refreshed_state();
    try_start_watch();
    return state;
}

bool NativeBlocklist::is_blocked(std::string_view ip, std::int64_t now_unix_us) {
    const auto address = parse_ip_address(ip);
    if (!address) return false;
    if (watching_.load()) return current_state().index->blocked(*address, now_unix_us);
    bool due = false;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto now = std::chrono::steady_clock::now();
        if (now >= next_check_) {
            next_check_ = now + std::chrono::seconds(1);
            due = true;
        }
    }
    const State state = due ? current_state() : loaded_state();
    return state.index->blocked(*address, now_unix_us);
}

bool NativeBlocklist::known_clear(std::string_view ip, std::int64_t now_unix_us) {
    const auto address = parse_ip_address(ip);
    if (!address) return false;  // adresse illisible : Python tranche
    const State state = current_state();
    return state.current && !state.index->blocked(*address, now_unix_us);
}

NativeBlocklist& blocklist_for(const std::string& path) {
    // Lot 1N : cache par fil (une instance par chemin ne disparait jamais) - plus de verrou global par requete.
    thread_local std::unordered_map<std::string, NativeBlocklist*> cache;
    if (const auto found = cache.find(path); found != cache.end()) return *found->second;
    static std::mutex mutex;
    static std::map<std::string, std::unique_ptr<NativeBlocklist>> lists;
    std::lock_guard<std::mutex> lock(mutex);
    auto& list = lists[path];
    if (!list) list = std::make_unique<NativeBlocklist>(path);
    cache.emplace(path, list.get());
    return *list;
}

}  // namespace omega

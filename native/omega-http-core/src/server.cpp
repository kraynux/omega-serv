// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "server.hpp"

#include <arpa/inet.h>
#include <fcntl.h>
#include <net/if.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/epoll.h>
#include <sys/mman.h>
#include <sys/eventfd.h>
#include <sys/sendfile.h>
#include <sys/socket.h>
#include <unistd.h>

#include <openssl/err.h>
#include <openssl/ssl.h>

#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <deque>
#include <map>
#include <mutex>
#include <random>
#include <thread>
#include <unordered_map>

#include "blocklist.hpp"
#include "engine.hpp"
#include "http_parser.hpp"
#include "ip.hpp"
#include "waf_filter.hpp"
#include "watch_list.hpp"
#include "ipc.hpp"
#include "log_writer.hpp"
#include "text.hpp"
#include "tls.hpp"

namespace omega {

namespace {

using Clock = std::chrono::steady_clock;

std::int64_t unix_now() {
    return std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();
}

Clock::time_point after_seconds(double seconds) {
    return Clock::now() + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
}

// Journaux partages entre fils et generations (un LogWriter par chemin, jamais detruit).
LogWriter& log_for(const std::string& path) {
    static std::mutex mutex;
    static std::map<std::string, std::unique_ptr<LogWriter>> writers;
    std::lock_guard<std::mutex> lock(mutex);
    auto& writer = writers[path];
    if (!writer) writer = std::make_unique<LogWriter>(path);
    return *writer;
}

// uuid.uuid4().hex[:16]
std::string new_request_id() {
    thread_local std::mt19937_64 generator{std::random_device{}()};
    static constexpr char digits[] = "0123456789abcdef";
    std::uint64_t value = generator();
    std::string id(16, '0');
    for (int i = 15; i >= 0; --i) {
        id[static_cast<std::size_t>(i)] = digits[value & 0xF];
        value >>= 4;
    }
    return id;
}

std::string peer_address(const sockaddr_storage& address) {
    char text[INET6_ADDRSTRLEN] = {};
    if (address.ss_family == AF_INET) {
        const auto* in = reinterpret_cast<const sockaddr_in*>(&address);
        ::inet_ntop(AF_INET, &in->sin_addr, text, sizeof text);
    } else if (address.ss_family == AF_INET6) {
        const auto* in6 = reinterpret_cast<const sockaddr_in6*>(&address);
        ::inet_ntop(AF_INET6, &in6->sin6_addr, text, sizeof text);
        // asyncio : peername[0] d'une IPv6 a portee (fe80::1%eth0) porte la zone
        if (in6->sin6_scope_id != 0) {
            char name[IF_NAMESIZE] = {};
            std::string out = text;
            if (::if_indextoname(in6->sin6_scope_id, name) != nullptr) out += std::string("%") + name;
            else out += "%" + std::to_string(in6->sin6_scope_id);
            return out;
        }
    } else {
        return "unknown";
    }
    return text;
}

std::string format_seconds(double value) {
    // f"{x}" Python : un entier de la configuration s'ecrit sans decimale
    if (std::floor(value) == value && std::fabs(value) < 1e15) return std::to_string(static_cast<long long>(value));
    char buffer[64];
    std::snprintf(buffer, sizeof buffer, "%.17g", value);
    return buffer;
}

enum class Phase { handshake, read_head, read_body, inspect, write, closed };

// asyncio.start_server(ssl=...) : ssl_handshake_timeout par defaut (constants.SSL_HANDSHAKE_TIMEOUT).
constexpr double kTlsHandshakeTimeoutSeconds = 60.0;
constexpr std::size_t kTlsFileChunk = 256 * 1024;

// Resultat d'une lecture / ecriture, en clair ou en TLS.
enum class Io { done, eof, want_read, want_write, failed };

struct Connection {
    int fd = -1;
    std::string peer_ip;
    std::shared_ptr<const Snapshot> snapshot;
    Phase phase = Phase::read_head;
    std::string in;
    bool eof = false;
    Clock::time_point deadline;
    bool has_deadline = false;
    int requests_served = 0;
    double phase_timeout = 0;  // read_timeout (1re requete) ou keepalive_timeout

    // requete en cours
    RequestHead head;
    Request request;
    std::uint64_t body_remaining = 0;

    // ecriture en cours
    std::string out;
    std::size_t out_offset = 0;
    int file_fd = -1;
    std::uint64_t file_offset = 0;
    std::uint64_t file_remaining = 0;
    std::string file_path;
    Response response;
    bool log_access_after_write = false;
    // _write_error_response : l'echec d'envoi est avale, la ligne d'acces est ecrite quand meme.
    bool log_access_even_if_write_fails = false;
    bool keep_alive_after_write = false;
    bool want_write = false;

    // Lot 4 : corps capture pour l'INSPECT (premiers octets, waf.inspect), identifiant numerique de la requete.
    std::string body_capture;
    std::uint64_t capture_limit = 0;
    bool capture_body = false;
    std::uint64_t inspect_key = 0;
    bool delegating = false;  // route deleguee a Python (lot 5) : sa reponse est la reponse finale
    // Plan WAF natif, lot 6 : limite de debit comptee ici pour cette requete (etiquette INSPECT 11) - 0 = autorisee.
    bool rate_counted = false;
    std::uint32_t rate_retry = 0;
    std::string raw_head;     // octets bruts de la tete en cours (lot 6 : rendus a Python avec la connexion)

    SSL* ssl = nullptr;        // TLS direct (lot 3b)
    std::string tls_pending;   // poignee de main : octets produits par OpenSSL, pas encore envoyes
    bool handshake_done = false;
    bool counted = false;      // compte dans active_connections_ (en TLS : seulement apres la poignee de main)
    bool io_reversed = false;  // TLS : lecture qui attend une ecriture du protocole, ou l'inverse

    ~Connection() {
        if (ssl != nullptr) SSL_free(ssl);
        if (file_fd >= 0) ::close(file_fd);
        if (fd >= 0) ::close(fd);
    }
};

}  // namespace

struct Server::Worker {
    Server& server;
    std::size_t index = 0;
    int epoll_fd = -1;
    std::unordered_map<int, std::unique_ptr<Connection>> connections;
    bool accepting = true;

    std::uint64_t clean_decisions = 0;  // requetes jugees propres par ce fil (controle 1/N, plan WAF natif lot 4)
    // Canal INSPECT/VERDICT de ce fil (lot 4) : trames en attente d'envoi, requetes en attente de verdict.
    int data_fd = -1;
    struct Outgoing {
        std::string encoded;
        std::vector<int> fds;  // HANDOFF : descripteurs a transmettre (fermes ici apres envoi)
    };
    std::deque<Outgoing> data_out;
    std::unordered_map<std::uint64_t, int> awaiting_verdict;  // identifiant de requete -> fd de la connexion
    static constexpr std::size_t kMaxQueuedInspects = 4096;

    Worker(Server& owner, std::size_t rank) : server(owner), index(rank) {}
    ~Worker() {
        if (data_fd >= 0) ::close(data_fd);
        if (epoll_fd >= 0) ::close(epoll_fd);
    }

    bool setup() {
        epoll_fd = ::epoll_create1(EPOLL_CLOEXEC);
        if (epoll_fd < 0) return false;
        for (int fd : server.listen_fds_) {
            epoll_event event{};
            event.events = EPOLLIN | EPOLLEXCLUSIVE;
            event.data.fd = fd;
            if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, fd, &event) != 0) return false;
        }
        epoll_event event{};
        event.events = EPOLLIN;
        event.data.fd = server.stop_event_fd_;
        if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, server.stop_event_fd_, &event) != 0) return false;
        if (index < server.options_.data_fds.size()) adopt_data_channel(server.options_.data_fds[index]);
        return true;
    }

    // ------------------------------------------------------------------------------------- canal de securite (lot 4)
    void adopt_data_channel(int fd) {
        if (data_fd >= 0) data_channel_lost("canal remplace");
        if (fd < 0) return;
        ::fcntl(fd, F_SETFL, ::fcntl(fd, F_GETFL) | O_NONBLOCK);
        epoll_event event{};
        event.events = EPOLLIN;
        event.data.fd = fd;
        if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, fd, &event) != 0) {
            ::close(fd);
            return;
        }
        data_fd = fd;
    }

    void poll_new_data_channel() {
        int fd = -1;
        {
            std::lock_guard<std::mutex> lock(server.data_mutex_);
            if (index < server.pending_data_fds_.size()) std::swap(fd, server.pending_data_fds_[index]);
        }
        if (fd >= 0) adopt_data_channel(fd);
    }

    void set_data_interest(bool out) {
        epoll_event event{};
        event.events = EPOLLIN | (out ? static_cast<std::uint32_t>(EPOLLOUT) : 0u);
        event.data.fd = data_fd;
        ::epoll_ctl(epoll_fd, EPOLL_CTL_MOD, data_fd, &event);
    }

    // false : canal perdu (les inspections en attente ont suivi on_error).
    bool flush_data_out() {
        while (!data_out.empty() && data_fd >= 0) {
            const int result = ipc::send_encoded_nowait(data_fd, data_out.front().encoded, data_out.front().fds);
            if (result == 1) {
                set_data_interest(true);
                return true;
            }
            if (result < 0) {
                data_channel_lost("envoi impossible");
                return false;
            }
            for (int fd : data_out.front().fds) ::close(fd);  // Python a maintenant sa propre copie
            data_out.pop_front();
        }
        if (data_fd >= 0) set_data_interest(false);
        return data_fd >= 0;
    }

    void data_channel_lost(const char* why) {
        if (data_fd >= 0) {
            ::epoll_ctl(epoll_fd, EPOLL_CTL_DEL, data_fd, nullptr);
            ::close(data_fd);
            data_fd = -1;
        }
        for (const Outgoing& outgoing : data_out) {
            for (int fd : outgoing.fds) ::close(fd);  // connexions confiees non transmises : le client voit une fin
        }
        data_out.clear();
        auto waiting = std::move(awaiting_verdict);
        awaiting_verdict.clear();
        for (const auto& [key, fd] : waiting) {
            auto it = connections.find(fd);
            if (it != connections.end() && it->second->phase == Phase::inspect && it->second->inspect_key == key) {
                inspection_failed(*it->second, why);
            }
        }
    }

    void on_data_readable() {
        while (data_fd >= 0) {
            ipc::Frame frame;
            std::string error;
            const int result = ipc::recv_frame_nowait(data_fd, frame, &error);
            if (result == 2) return;
            if (result != 0) {
                data_channel_lost(result == 1 ? "processus de securite arrete" : "trame illisible");
                return;
            }
            if (frame.type == ipc::kVerdict) apply_verdict(frame);
            else if (frame.type == ipc::kWatch) apply_watch(frame);
        }
    }

    // Lot 3 : sources que Python veut voir pour toutes leurs requetes (table commune a tous les fils).
    void apply_watch(const ipc::Frame& frame) {
        const std::int64_t now = std::chrono::duration_cast<std::chrono::seconds>(
                                     std::chrono::system_clock::now().time_since_epoch()).count();
        for (const std::string& entry : frame.all(ipc::tag::kWatchEntry)) {
            const std::size_t zero = entry.find('\0');
            if (zero == std::string::npos || zero == 0) continue;
            std::int64_t until = 0;
            const std::string digits = entry.substr(zero + 1);
            if (digits.empty() || digits.size() > 18 || digits.find_first_not_of("0123456789") != std::string::npos) continue;
            until = std::stoll(digits);
            if (!WatchList::instance().add(entry.substr(0, zero), until, now)) {
                const auto snapshot = server.snapshot();
                log_for(snapshot->error_log).append_line(format_error_line(
                    "sources suivies : table pleine, toute requete est inspectee par Python", "", unix_now()));
            }
        }
    }

    // Lot 6 : la connexion entiere passe a Python (meme _handle_connection que le moteur Python), avec les octets
    // deja lus (tete en cours comprise) et le nombre de requetes deja servies. Le natif l'oublie aussitot.
    void hand_off(Connection& c) {
        static constexpr std::size_t kInlineBytes = 768 * 1024;
        if (c.ssl != nullptr) {  // session TLS en cours : Python ne peut pas la reprendre (repli prevu en amont)
            log_error(c, "route confiée à Python impossible en TLS direct", c.request.request_id);
            respond(c, error_response(503), false);
            return;
        }
        if (data_fd < 0 || data_out.size() >= kMaxQueuedInspects) {
            log_error(c, "route confiée à Python indisponible (connexion non transmise)", c.request.request_id);
            respond(c, error_response(503), false);
            return;
        }
        std::string pending = c.raw_head + c.in;
        ipc::Frame frame;
        frame.type = ipc::kHandoff;
        frame.generation = c.snapshot->generation;
        frame.add_u32(ipc::tag::kHandoffServed, static_cast<std::uint32_t>(c.requests_served));
        std::vector<int> fds;
        const int client = ::dup(c.fd);
        if (client < 0) {
            respond(c, error_response(503), false);
            return;
        }
        fds.push_back(client);
        if (pending.size() <= kInlineBytes) {
            frame.add(ipc::tag::kHandoffBytes, std::move(pending));
        } else {
            const int memfd = ::memfd_create("omega-handoff", MFD_CLOEXEC);
            std::size_t written = 0;
            while (memfd >= 0 && written < pending.size()) {
                const ssize_t n = ::write(memfd, pending.data() + written, pending.size() - written);
                if (n <= 0) break;
                written += static_cast<std::size_t>(n);
            }
            if (memfd < 0 || written != pending.size()) {
                if (memfd >= 0) ::close(memfd);
                ::close(client);
                respond(c, error_response(503), false);
                return;
            }
            frame.add_u64(ipc::tag::kHandoffBytesFd, pending.size());
            fds.push_back(memfd);
        }
        data_out.push_back(Outgoing{ipc::encode(frame), std::move(fds)});
        c.phase = Phase::inspect;  // plus aucune lecture ici ; close_connection retire la socket d'epoll
        close_connection(c);       // la copie du natif est fermee avec la Connection ; Python garde la sienne
        flush_data_out();
    }

    static std::uint64_t request_key(const std::string& request_id) {
        std::uint64_t key = 0;
        for (char ch : request_id) key = (key << 4) | static_cast<std::uint64_t>(ch <= '9' ? ch - '0' : ch - 'a' + 10);
        return key;
    }

    void start_inspection(Connection& c, bool delegate = false, bool audit = false) {
        c.delegating = delegate;
        const InspectSettings& settings = *c.snapshot->inspect;
        if (data_fd < 0) {
            inspection_failed(c, "aucun canal");
            return;
        }
        if (data_out.size() >= kMaxQueuedInspects) {
            inspection_failed(c, "file d'attente pleine");
            return;
        }
        ipc::Frame frame;
        frame.type = ipc::kInspect;
        frame.generation = c.snapshot->generation;
        c.inspect_key = request_key(c.request.request_id);
        frame.request_id = c.inspect_key;
        frame.add(ipc::tag::kInspectPeer, c.peer_ip);
        frame.add(ipc::tag::kInspectMethod, c.head.method);
        frame.add(ipc::tag::kInspectTarget, c.head.target);
        frame.add(ipc::tag::kInspectVersion, c.head.http_version);
        for (const auto& [name, value] : c.head.headers) frame.add(ipc::tag::kInspectHeader, name + '\0' + value);
        if (c.capture_body) frame.add(ipc::tag::kInspectBody, c.body_capture);
        if (delegate) frame.add_u8(ipc::tag::kInspectDelegate, 1);
        if (audit) frame.add_u8(ipc::tag::kInspectAudit, 1);
        if (!delegate && c.rate_counted) frame.add_u32(ipc::tag::kInspectRateLimit, c.rate_retry);
        // Lot 8 : pieces deja calculees ici, que Python n'a pas a refaire (lui seul decide toujours).
        frame.add(ipc::tag::kInspectClientIp, c.request.remote_ip);
        if (!delegate && settings.blocklist_path &&
            blocklist_for(*settings.blocklist_path)
                .known_clear(c.request.remote_ip, std::chrono::duration_cast<std::chrono::microseconds>(
                                                      std::chrono::system_clock::now().time_since_epoch()).count()))
            frame.add_u8(ipc::tag::kInspectBlocklistClear, 1);
        std::string encoded = ipc::encode(frame);
        if (encoded.size() > ipc::kHeaderSize + ipc::kMaxPayload) {
            inspection_failed(c, "requete trop grande pour le canal");
            return;
        }
        data_out.push_back(Outgoing{std::move(encoded), {}});
        c.phase = Phase::inspect;
        c.deadline = after_seconds(static_cast<double>(settings.timeout_ms) / 1000.0);
        c.has_deadline = true;
        awaiting_verdict[c.inspect_key] = c.fd;
        flush_data_out();
    }

    // Processus de securite indisponible, en retard ou canal plein : waf.on_internal_error (Auth : toujours refuse).
    void inspection_failed(Connection& c, const char* why) {
        awaiting_verdict.erase(c.inspect_key);
        if (c.delegating) {  // route Python injoignable : rien a servir a sa place (jamais une boucle de routage)
            log_error(c, std::string("route confiée à Python indisponible (") + why + ")", c.request.request_id);
            respond(c, error_response(503), true);
            return;
        }
        const bool fail_closed = c.snapshot->inspect->fail_closed;
        log_error(c, std::string("controle de securite indisponible (") + why + ") : requete " +
                         (fail_closed ? "refusee (503, fail-closed)" : "servie sans controle (fail-open)"),
                  c.request.request_id);
        if (!fail_closed && c.snapshot->inspect->blocklist_path &&
            blocklist_for(*c.snapshot->inspect->blocklist_path)
                .is_blocked(c.request.remote_ip, std::chrono::duration_cast<std::chrono::microseconds>(
                                                     std::chrono::system_clock::now().time_since_epoch()).count())) {
            // Decision utilisateur 2026-11-02 : fail-open ne libere jamais une adresse deja bannie (451, comme le WAF).
            log_error(c, "adresse bannie refusee par le moteur natif (451) pendant l'indisponibilite du controle",
                      c.request.request_id);
            Response response = error_response(451);
            apply_security_headers(response, *c.snapshot, c.request.path_text);
            c.requests_served += 1;
            start_write(c, std::move(response), false, true);
            return;
        }
        if (fail_closed) {
            Response response = error_response(503);
            apply_security_headers(response, *c.snapshot, c.request.path_text);
            c.requests_served += 1;
            start_write(c, std::move(response), false, true);
            return;
        }
        handle_request(c);
    }

    void apply_verdict(const ipc::Frame& frame) {
        const auto found = awaiting_verdict.find(frame.request_id);
        if (found == awaiting_verdict.end()) return;  // arrive apres le delai, ou client parti : ignore
        const int fd = found->second;
        awaiting_verdict.erase(found);
        auto it = connections.find(fd);
        if (it == connections.end()) return;
        Connection& c = *it->second;
        if (c.phase != Phase::inspect || c.inspect_key != frame.request_id) return;
        const std::uint64_t decision = frame.unsigned_field(ipc::tag::kVerdictDecision).value_or(1);
        if (decision == 3) {  // exception dans l'etape de securite : connexion fermee sans reponse, comme asyncio
            close_connection(c);
            return;
        }
        if (decision != 2) {
            if (c.delegating) {  // une route deleguee attend une reponse, jamais « continuer »
                log_error(c, "route confiée à Python : verdict sans réponse", c.request.request_id);
                respond(c, error_response(500), true);
                return;
            }
            handle_request(c);  // continuer : routage natif
            return;
        }
        Response response;
        response.status = static_cast<int>(frame.unsigned_field(ipc::tag::kVerdictStatus).value_or(500));
        for (const std::string& header : frame.all(ipc::tag::kVerdictHeader)) {
            const std::size_t zero = header.find('\0');
            if (zero != std::string::npos) response.headers.set(header.substr(0, zero), header.substr(zero + 1));
        }
        if (const std::string* body = frame.first(ipc::tag::kVerdictBody)) response.body = *body;
        if (const std::string* file = frame.first(ipc::tag::kVerdictFile)) {
            response.body_file = *file;
            response.body_file_offset = frame.unsigned_field(ipc::tag::kVerdictFileOffset).value_or(0);
            response.body_file_length = frame.unsigned_field(ipc::tag::kVerdictFileLength).value_or(0);
        }
        const bool keep_alive_allowed = frame.unsigned_field(ipc::tag::kVerdictKeepAlive).value_or(0) == 1;
        respond(c, std::move(response), keep_alive_allowed);
    }


    bool is_listen_fd(int fd) const {
        for (int l : server.listen_fds_) {
            if (l == fd) return true;
        }
        return false;
    }

    void log_error(const Connection& c, std::string_view message, std::string_view request_id) {
        log_for(c.snapshot->error_log).append_line(format_error_line(message, request_id, unix_now()));
    }

    void stop_accepting() {
        if (!accepting) return;
        accepting = false;
        for (int fd : server.listen_fds_) ::epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, nullptr);
        ::epoll_ctl(epoll_fd, EPOLL_CTL_DEL, server.stop_event_fd_, nullptr);  // reste lisible : sinon boucle active
        // Server.close() de Python : plus aucune connexion acceptee (les nouvelles sont refusees). shutdown()
        // sur la socket d'ecoute, jamais close() : son numero ne peut pas etre reattribue pendant le drainage.
        std::call_once(server.listen_shutdown_once_, [this] {
            for (int fd : server.listen_fds_) ::shutdown(fd, SHUT_RD);
        });
    }

    void close_connection(Connection& c) {
        if (c.phase == Phase::closed) return;
        if (c.ssl != nullptr && c.phase != Phase::handshake) {
            ERR_clear_error();
            (void)SSL_shutdown(c.ssl);  // close_notify, sans attendre la reponse (transport asyncio ferme)
            ERR_clear_error();
        }
        c.phase = Phase::closed;
        ::epoll_ctl(epoll_fd, EPOLL_CTL_DEL, c.fd, nullptr);
        if (c.counted) server.active_connections_.fetch_sub(1);
        c.counted = false;
    }

    // ------------------------------------------------------------------------------------- E/S
    Io io_read(Connection& c, char* buffer, std::size_t size, std::size_t& got) {
        got = 0;
        if (c.ssl == nullptr) {
            const ssize_t n = ::recv(c.fd, buffer, size, 0);
            if (n > 0) {
                got = static_cast<std::size_t>(n);
                return Io::done;
            }
            if (n == 0) return Io::eof;
            if (errno == EINTR) return io_read(c, buffer, size, got);
            if (errno == EAGAIN || errno == EWOULDBLOCK) return Io::want_read;
            return Io::failed;
        }
        ERR_clear_error();
        if (SSL_read_ex(c.ssl, buffer, size, &got) == 1) return Io::done;
        return tls_status(c, 0);
    }

    Io io_write(Connection& c, const char* data, std::size_t size, std::size_t& sent) {
        sent = 0;
        if (c.ssl == nullptr) {
            const ssize_t n = ::send(c.fd, data, size, MSG_NOSIGNAL);
            if (n > 0) {
                sent = static_cast<std::size_t>(n);
                return Io::done;
            }
            if (n < 0 && errno == EINTR) return io_write(c, data, size, sent);
            if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return Io::want_write;
            return Io::failed;
        }
        ERR_clear_error();
        if (SSL_write_ex(c.ssl, data, size, &sent) == 1) return Io::done;
        return tls_status(c, 0);
    }

    static Io tls_status(Connection& c, int result) {
        switch (SSL_get_error(c.ssl, result)) {
            case SSL_ERROR_WANT_READ: return Io::want_read;
            case SSL_ERROR_WANT_WRITE: return Io::want_write;
            case SSL_ERROR_ZERO_RETURN: return Io::eof;  // close_notify du client
            default: break;
        }
        ERR_clear_error();
        return Io::failed;
    }

    // ------------------------------------------------------------------------------------- poignee de main TLS
    void drain_handshake_output(Connection& c) {
        char buffer[16384];
        int n = 0;
        while ((n = BIO_read(SSL_get_wbio(c.ssl), buffer, sizeof buffer)) > 0) c.tls_pending.append(buffer, static_cast<std::size_t>(n));
    }

    // true : tout est parti ; false : en attente (EPOLLOUT arme) ou connexion fermee.
    bool flush_handshake_output(Connection& c) {
        while (!c.tls_pending.empty()) {
            const ssize_t n = ::send(c.fd, c.tls_pending.data(), c.tls_pending.size(), MSG_NOSIGNAL);
            if (n > 0) {
                c.tls_pending.erase(0, static_cast<std::size_t>(n));
                continue;
            }
            if (n < 0 && errno == EINTR) continue;
            if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                set_write_interest(c, true);
                return false;
            }
            close_connection(c);
            return false;
        }
        return true;
    }

    void on_handshake(Connection& c) {
        if (!flush_handshake_output(c)) return;
        if (!c.handshake_done) {
            ERR_clear_error();
            const int result = SSL_do_handshake(c.ssl);
            if (result != 1) {
                const Io status = tls_status(c, result);
                if (status != Io::want_read && status != Io::want_write) {
                    close_connection(c);  // echec : rien d'envoye, aucun journal (comme asyncio)
                    return;
                }
                drain_handshake_output(c);
                if (flush_handshake_output(c)) set_write_interest(c, false);
                return;
            }
            c.handshake_done = true;
            drain_handshake_output(c);
            if (!flush_handshake_output(c)) return;
        }
        // Poignee de main terminee et envoyee : la suite s'ecrit directement sur la socket.
        BIO* socket_bio = BIO_new_socket(c.fd, BIO_NOCLOSE);
        if (socket_bio == nullptr) {
            close_connection(c);
            return;
        }
        SSL_set0_wbio(c.ssl, socket_bio);
        // Comme asyncio : la connexion n'existe pour le serveur (compteur, 503) qu'apres la poignee de main.
        const std::size_t active = server.active_connections_.fetch_add(1);
        if (active >= c.snapshot->server.max_connections) {
            server.active_connections_.fetch_sub(1);
            server.rejected_over_capacity_.fetch_add(1, std::memory_order_relaxed);
            Response response = error_response(503);  // _write_error_response en TLS, sans journal
            start_write(c, std::move(response), false, false);
            return;
        }
        c.counted = true;
        c.phase = Phase::read_head;
        c.phase_timeout = c.snapshot->server.read_timeout_seconds;
        c.deadline = after_seconds(c.phase_timeout);
        c.has_deadline = true;
        set_write_interest(c, false);
        on_readable(c);  // des octets applicatifs ont pu arriver avec la fin de la poignee de main
    }

    void set_write_interest(Connection& c, bool want) {
        if (c.want_write == want) return;
        c.want_write = want;
        // En ecriture : EPOLLOUT SEUL. Des octets deja recus (pipelining) ou une demi-fermeture garderaient
        // EPOLLIN / EPOLLRDHUP actifs en permanence (declenchement par niveau) : la boucle tournerait a vide
        // tant que le client ne lit pas. Python ne lit pas non plus pendant l'ecriture.
        epoll_event event{};
        event.events = want ? static_cast<std::uint32_t>(EPOLLOUT) : static_cast<std::uint32_t>(EPOLLIN | EPOLLRDHUP);
        event.data.fd = c.fd;
        ::epoll_ctl(epoll_fd, EPOLL_CTL_MOD, c.fd, &event);
    }

    // ------------------------------------------------------------------------------------- acceptation
    void accept_all(int listen_fd) {
        while (true) {
            sockaddr_storage address{};
            socklen_t length = sizeof address;
            const int fd = ::accept4(listen_fd, reinterpret_cast<sockaddr*>(&address), &length, SOCK_NONBLOCK | SOCK_CLOEXEC);
            if (fd < 0) {
                if (errno == EINTR || errno == ECONNABORTED) continue;
                return;  // EAGAIN (un autre fil l'a prise) ou EMFILE : reessaye au prochain reveil
            }
            const int one = 1;
            ::setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
            auto c = std::make_unique<Connection>();
            c->fd = fd;
            c->peer_ip = peer_address(address);
            c->snapshot = server.snapshot();
            if (server.tls_context_) {
                c->ssl = SSL_new(server.tls_context_.get());
                if (c->ssl == nullptr) continue;  // ~Connection ferme le fd
                // Comme asyncio (sslproto, BIO memoire) : pendant la poignee de main, ce qu'OpenSSL veut envoyer
                // passe par un tampon que l'on n'envoie que si elle avance - un echec ne part donc jamais en
                // alerte TLS, la connexion est simplement fermee (meme comportement vu du client).
                BIO* read_bio = BIO_new_socket(fd, BIO_NOCLOSE);
                BIO* write_bio = BIO_new(BIO_s_mem());
                if (read_bio == nullptr || write_bio == nullptr) {
                    BIO_free(read_bio);
                    BIO_free(write_bio);
                    continue;
                }
                SSL_set_bio(c->ssl, read_bio, write_bio);
                SSL_set_accept_state(c->ssl);
                epoll_event event{};
                event.events = EPOLLIN | EPOLLRDHUP;
                event.data.fd = fd;
                if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, fd, &event) != 0) continue;
                c->phase = Phase::handshake;
                c->deadline = after_seconds(kTlsHandshakeTimeoutSeconds);
                c->has_deadline = true;
                connections[fd] = std::move(c);
                continue;
            }
            const std::size_t active = server.active_connections_.fetch_add(1);
            if (active >= c->snapshot->server.max_connections) {
                // _handle_connection_tracked : 503 puis fermeture, aucun journal
                reject_over_capacity(*c);
                server.rejected_over_capacity_.fetch_add(1, std::memory_order_relaxed);
                server.active_connections_.fetch_sub(1);
                continue;
            }
            epoll_event event{};
            event.events = EPOLLIN | EPOLLRDHUP;
            event.data.fd = fd;
            if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, fd, &event) != 0) {
                server.active_connections_.fetch_sub(1);
                continue;
            }
            c->counted = true;
            c->phase_timeout = c->snapshot->server.read_timeout_seconds;
            c->deadline = after_seconds(c->phase_timeout);
            c->has_deadline = true;
            connections[fd] = std::move(c);
        }
    }

    void reject_over_capacity(Connection& c) {
        Response response = error_response(503);
        const auto head = finalize_response(*c.snapshot, response, false);
        if (!head) return;
        const std::string data = *head + response.body;
        (void)::send(c.fd, data.data(), data.size(), MSG_NOSIGNAL | MSG_DONTWAIT);
    }

    // ------------------------------------------------------------------------------------- lecture
    void on_readable(Connection& c) {
        char buffer[65536];
        if (c.io_reversed) {  // la lecture TLS attendait de pouvoir ecrire : retour a l'ecoute normale
            c.io_reversed = false;
            set_write_interest(c, false);
        }
        while (c.phase == Phase::read_head || c.phase == Phase::read_body) {
            std::size_t got = 0;
            const Io status = io_read(c, buffer, sizeof buffer, got);
            if (status == Io::done) {
                c.in.append(buffer, got);
                if (c.in.size() > (4u << 20) && c.phase == Phase::read_head) break;  // le parseur tranchera
                continue;
            }
            if (status == Io::eof) {
                c.eof = true;
                break;
            }
            if (status == Io::want_read) break;
            if (status == Io::want_write) {  // TLS : le protocole doit d'abord ecrire
                c.io_reversed = true;
                set_write_interest(c, true);
                break;
            }
            close_connection(c);  // ConnectionResetError : fin silencieuse
            return;
        }
        process(c);
    }

    // _write_error_response puis _log_access (plan §14, valide 2026-11-02 : toute erreur dans access.log).
    void begin_error_response(Connection& c, int status) {
        Response response = error_response(status);
        start_write(c, std::move(response), false, true, true);
    }

    void process(Connection& c) {
        while (c.phase == Phase::read_head || c.phase == Phase::read_body) {
            if (c.phase == Phase::read_head) {
                if (!process_head(c)) return;
            } else if (!process_body(c)) {
                return;
            }
        }
    }

    // false = attendre (ou connexion terminee)
    bool process_head(Connection& c) {
        const Snapshot& snapshot = *c.snapshot;
        ParseResult parsed = parse_request_head(c.in, snapshot.parser_limits, c.eof);
        if (parsed.state == ParseState::need_more) {
            if (c.eof) close_connection(c);  // fermeture propre (ConnectionClosedCleanly)
            return false;
        }
        if (parsed.state == ParseState::error) {
            // _log_unparsed_access : ligne brute (« - » si illisible), IP client avec les en-tetes deja lus.
            c.head = std::move(parsed.head);
            c.request = Request{};
            c.request.request_id = new_request_id();
            c.request.peer_ip = c.peer_ip;
            c.request.head = &c.head;
            c.request.unparsed = true;
            c.request.raw_request_line_text = parsed.has_request_line ? latin1_to_utf8(parsed.request_line) : std::string("-");
            c.request.remote_ip = resolve_remote_ip(snapshot, c.peer_ip, c.head);
            log_error(c, "erreur de parsing : " + parsed.reason, c.request.request_id);
            begin_error_response(c, parsed.status);
            return false;
        }
        c.raw_head.assign(c.in, 0, parsed.consumed);
        c.in.erase(0, parsed.consumed);
        c.head = std::move(parsed.head);
        c.request = Request{};
        c.request.request_id = new_request_id();
        c.request.peer_ip = c.peer_ip;
        c.request.head = &c.head;
        fill_request_target(c.request);
        c.request.remote_ip = resolve_remote_ip(snapshot, c.peer_ip, c.head);

        if (auto early = check_before_body(snapshot, c.request)) {
            if (!early->error_log_message.empty()) log_error(c, early->error_log_message, c.request.request_id);
            start_write(c, std::move(early->response), false, early->log_access, early->is_error_response);
            return false;
        }
        if (wants_handoff(snapshot, c.request)) {  // lot 6 : reverse proxy, FastCGI, envoi de fichiers -> Python
            hand_off(c);
            return false;
        }
        const BodyFraming framing = body_framing(c.head, snapshot.server.max_request_size);
        if (framing.status != 0) {
            log_error(c, "erreur de corps de requete : " + framing.reason, c.request.request_id);
            begin_error_response(c, framing.status);
            return false;
        }
        c.body_remaining = framing.content_length;
        c.body_capture.clear();
        c.capture_body = false;
        if (snapshot.inspect && snapshot.inspect->body_bytes > 0) {
            const std::string method = latin1_to_utf8(c.head.method);
            for (const std::string& allowed : snapshot.inspect->body_methods) c.capture_body = c.capture_body || allowed == method;
        }
        c.capture_limit = c.capture_body ? snapshot.inspect->body_bytes : 0;
        c.phase = Phase::read_body;
        c.deadline = after_seconds(c.phase_timeout);  // nouveau wait_for(..., timeout) pour le corps
        c.has_deadline = true;
        return true;
    }

    bool process_body(Connection& c) {
        const std::uint64_t take = std::min<std::uint64_t>(c.body_remaining, c.in.size());
        if (c.capture_body && c.body_capture.size() < c.capture_limit) {
            const std::uint64_t room = c.capture_limit - c.body_capture.size();
            c.body_capture.append(c.in, 0, static_cast<std::size_t>(std::min<std::uint64_t>(room, take)));
        }
        c.in.erase(0, static_cast<std::size_t>(take));
        c.body_remaining -= take;
        if (c.body_remaining > 0) {
            if (c.eof) {
                log_error(c, "erreur de corps de requete : corps de requête incomplet", c.request.request_id);
                begin_error_response(c, 400);
            }
            return false;
        }
        if (!c.snapshot->inspect || !c.snapshot->inspect->security_stage) {
            handle_request(c);
            return false;
        }
        count_rate_limit(c);
        const NativeDecision decision = c.rate_retry > 0 ? NativeDecision::python : native_decision(c);
        if (decision == NativeDecision::clean) handle_request(c);
        else start_inspection(c, false, decision == NativeDecision::audit);  // leurres, WAF, AD, Auth : Python decide
        return false;
    }

    enum class NativeDecision { python, clean, audit };

    // Lot 6 : chaque requete compte (propre ou non), meme seau et memes regles que Python. Depassement -> Python
    // repond 429 et journalise ; jamais de reponse de blocage ecrite ici.
    void count_rate_limit(Connection& c) {
        c.rate_counted = false;
        c.rate_retry = 0;
        const auto& filter = c.snapshot->waf_filter;
        const RatePolicy* policy = filter ? filter->rate_policy() : nullptr;
        if (policy == nullptr || data_fd < 0) return;  // sans canal : on_internal_error, et Python ne compte rien
        c.rate_counted = true;
        if (policy->exempt(c.head.method, c.request.path_text)) return;
        const SelectedRate rate = policy->select(c.request.path_text, c.request.remote_ip);
        if (rate.requests <= 0) return;  // illimite
        const double now = std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
        if (const auto retry = RateLimiter::instance().check(rate, now)) c.rate_retry = *retry;
    }

    // Lot 4 : controle 1/N - la N-ieme requete jugee propre (par fil) part quand meme a Python, marquee « controle ».
    NativeDecision native_decision(Connection& c) {
        if (!clean_without_python(c)) return NativeDecision::python;
        const std::uint32_t every = c.snapshot->waf_filter->check_every();
        if (every > 0 && ++clean_decisions % every == 0) return NativeDecision::audit;
        return NativeDecision::clean;
    }

    // Plan WAF natif, lot 2 : requete servie sans passer par Python seulement si TOUT est certain - aucune fonction
    // ne demande Python pour chaque requete, chemin hors zone protegee, adresse absente de la blocklist ACTUELLE,
    // textes ASCII et aucune regle qui correspond. Au moindre doute, INSPECT comme avant : Python decide et
    // journalise. Une requete propre ne produit aucune ligne de securite cote Python : seul le journal d'acces
    // (ecrit ici) la voit, comme apres un verdict « continuer ».
    bool clean_without_python(Connection& c) {
        // Sans canal vers Python, rien ne change : waf.on_internal_error decide (fail-closed et Auth : 503), comme
        // avant le filtre - le natif ne remplace jamais un controle absent.
        if (data_fd < 0) return false;
        const auto& filter = c.snapshot->waf_filter;
        if (!filter || !filter->decides_alone()) return false;
        if (filter->in_protected_zone(c.request.path_text)) return false;
        const InspectSettings& settings = *c.snapshot->inspect;
        if (!settings.blocklist_path) return false;
        if (!blocklist_for(*settings.blocklist_path)
                 .known_clear(c.request.remote_ip, std::chrono::duration_cast<std::chrono::microseconds>(
                                                       std::chrono::system_clock::now().time_since_epoch()).count()))
            return false;
        const std::int64_t now_us = std::chrono::duration_cast<std::chrono::microseconds>(
                                        std::chrono::system_clock::now().time_since_epoch()).count();
        if (WatchList::instance().requires_python(c.request.remote_ip, now_us / 1000000)) return false;  // lot 3
        const auto texts = filter->prepare(c.request, c.capture_body && !c.body_capture.empty());
        return texts && filter->evaluate(*texts) == WafFilterOutcome::clean;
    }

    void handle_request(Connection& c) {
        const Snapshot& snapshot = *c.snapshot;
        Response response = route_request(snapshot, c.request);
        if (response.abort_connection) {
            close_connection(c);
            return;
        }
        if (response.needs_python) {
            if (c.snapshot->inspect) {  // lot 5 : listing de repertoire, /load, /admin -> route_request Python
                start_inspection(c, true);
                return;
            }
            log_error(c, "route confiée à Python indisponible (moteur natif autonome)", c.request.request_id);
            response = error_response(503);
        }
        respond(c, std::move(response), true);
    }

    // En-tetes de securite du chemin, compteur, keep-alive (comme apres route_request cote Python). `keep_alive_allowed`
    // false : reponse de blocage du controle de securite (connexion fermee comme en Python).
    void respond(Connection& c, Response response, bool keep_alive_allowed) {
        const Snapshot& snapshot = *c.snapshot;
        apply_security_headers(response, snapshot, c.request.path_text);
        c.requests_served += 1;
        server.requests_served_.fetch_add(1, std::memory_order_relaxed);
        const std::string* connection = c.head.header("connection");
        const bool keep_alive = keep_alive_allowed && c.requests_served < snapshot.server.max_keepalive_requests &&
                                c.head.http_version == "HTTP/1.1" &&
                                !(connection != nullptr && ascii_lower(*connection) == "close");
        start_write(c, std::move(response), keep_alive, true);
    }

    static std::string ascii_lower(std::string_view text) {
        std::string out(text);
        for (char& ch : out) {
            if (ch >= 'A' && ch <= 'Z') ch = static_cast<char>(ch - 'A' + 'a');
        }
        return out;
    }

    // ------------------------------------------------------------------------------------- ecriture
    void start_write(Connection& c, Response response, bool keep_alive, bool log_access, bool log_even_if_write_fails = false) {
        auto head = finalize_response(*c.snapshot, response, keep_alive);
        if (!head) {
            close_connection(c);  // UnicodeEncodeError cote Python : ni reponse ni journal
            return;
        }
        c.log_access_even_if_write_fails = log_access && log_even_if_write_fails;
        c.response = std::move(response);
        c.out = std::move(*head);
        c.out += c.response.body;
        c.out_offset = 0;
        c.file_path = c.response.body_file;
        c.file_offset = c.response.body_file_offset;
        c.file_remaining = c.response.body_file.empty() ? 0 : c.response.body_file_length;
        c.log_access_after_write = log_access;
        c.keep_alive_after_write = keep_alive;
        c.phase = Phase::write;
        c.has_deadline = false;  // Python : aucun delai d'ecriture (drain sans limite)
        on_writable(c);
    }

    void on_writable(Connection& c) {
        if (c.io_reversed) {
            c.io_reversed = false;
            set_write_interest(c, true);
        }
        while (true) {
            if (c.out_offset >= c.out.size()) {
                // TLS : pas de sendfile, le fichier part par morceaux chiffres (repli de loop.sendfile).
                if (c.ssl == nullptr || c.file_remaining == 0) break;
                if (!load_file_chunk(c)) return;
                continue;
            }
            std::size_t sent = 0;
            const Io status = io_write(c, c.out.data() + c.out_offset, c.out.size() - c.out_offset, sent);
            if (status == Io::done) {
                c.out_offset += sent;
                continue;
            }
            if (status == Io::want_write) {
                set_write_interest(c, true);
                return;
            }
            if (status == Io::want_read) {  // TLS : le protocole doit d'abord lire
                c.io_reversed = true;
                set_write_interest(c, false);
                return;
            }
            if (c.log_access_even_if_write_fails) write_access_line(c);
            close_connection(c);
            return;
        }
        if (c.file_remaining > 0) {
            if (c.file_fd < 0) {
                c.file_fd = ::open(c.file_path.c_str(), O_RDONLY | O_CLOEXEC);
                if (c.file_fd < 0) {
                    log_error(c, "envoi interrompu de " + c.file_path + " : [Errno " + std::to_string(errno) + "] " +
                                     std::strerror(errno) + ": '" + c.file_path + "'", "");
                    close_connection(c);
                    return;
                }
            }
            while (c.file_remaining > 0) {
                off_t offset = static_cast<off_t>(c.file_offset);
                const ssize_t n = ::sendfile(c.fd, c.file_fd, &offset, static_cast<std::size_t>(std::min<std::uint64_t>(c.file_remaining, 1u << 30)));
                if (n > 0) {
                    c.file_offset += static_cast<std::uint64_t>(n);
                    c.file_remaining -= static_cast<std::uint64_t>(n);
                    continue;
                }
                if (n < 0 && errno == EINTR) continue;
                if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                    set_write_interest(c, true);
                    return;
                }
                close_connection(c);  // fichier tronque entre-temps (n == 0) ou pair parti
                return;
            }
            ::close(c.file_fd);
            c.file_fd = -1;
        }
        set_write_interest(c, false);
        finish_write(c);
    }

    // Morceau suivant d'un fichier envoye en TLS. false : connexion fermee (fichier illisible ou tronque).
    bool load_file_chunk(Connection& c) {
        if (c.file_fd < 0) {
            c.file_fd = ::open(c.file_path.c_str(), O_RDONLY | O_CLOEXEC);
            if (c.file_fd < 0) {
                log_error(c, "envoi interrompu de " + c.file_path + " : [Errno " + std::to_string(errno) + "] " +
                                 std::strerror(errno) + ": '" + c.file_path + "'", "");
                close_connection(c);
                return false;
            }
        }
        const std::size_t size = static_cast<std::size_t>(std::min<std::uint64_t>(c.file_remaining, kTlsFileChunk));
        c.out.resize(size);
        c.out_offset = 0;
        std::size_t done = 0;
        while (done < size) {
            const ssize_t n = ::pread(c.file_fd, c.out.data() + done, size - done, static_cast<off_t>(c.file_offset + done));
            if (n < 0 && errno == EINTR) continue;
            if (n <= 0) {
                close_connection(c);  // fichier tronque entre-temps
                return false;
            }
            done += static_cast<std::size_t>(n);
        }
        c.file_offset += size;
        c.file_remaining -= size;
        if (c.file_remaining == 0) {
            ::close(c.file_fd);
            c.file_fd = -1;
        }
        return true;
    }

    void write_access_line(Connection& c) {
        log_for(c.snapshot->access_log).append_line(format_access_line(c.request, c.response, unix_now()));
    }

    void finish_write(Connection& c) {
        if (c.log_access_after_write) write_access_line(c);
        c.out.clear();
        c.response = Response{};
        if (!c.keep_alive_after_write || server.stopping_.load()) {
            if (!c.keep_alive_after_write) {
                close_connection(c);
                return;
            }
        }
        c.phase = Phase::read_head;
        c.phase_timeout = c.snapshot->server.keepalive_timeout_seconds;
        c.deadline = after_seconds(c.phase_timeout);
        c.has_deadline = true;
        process(c);  // requete deja recue (pipelining)
    }

    // ------------------------------------------------------------------------------------- delais
    void check_deadlines() {
        const auto now = Clock::now();
        for (auto& [fd, c] : connections) {
            if (c->phase == Phase::closed || !c->has_deadline || now < c->deadline) continue;
            if (c->phase == Phase::handshake || c->phase == Phase::read_head) {
                close_connection(*c);  // asyncio.TimeoutError sur la tete (ou poignee de main) : fermeture sans reponse
            } else if (c->phase == Phase::inspect) {
                inspection_failed(*c, "delai depasse");
            } else if (c->phase == Phase::read_body) {
                log_error(*c, "corps de requete trop lent (timeout)", c->request.request_id);
                begin_error_response(*c, 408);
            }
        }
    }

    void collect_closed() {
        for (auto it = connections.begin(); it != connections.end();) {
            if (it->second->phase == Phase::closed) it = connections.erase(it);
            else ++it;
        }
    }

    void run() {
        epoll_event events[256];
        auto next_scan = Clock::now();
        while (true) {
            poll_new_data_channel();
            if (server.stopping_.load()) {
                stop_accepting();
                collect_closed();
                if (connections.empty()) return;
                if (Clock::now().time_since_epoch().count() >= server.force_deadline_.load()) {
                    server.forced_closures_.fetch_add(force_close_all());
                    return;
                }
            }
            const int n = ::epoll_wait(epoll_fd, events, 256, 250);
            for (int i = 0; i < n; ++i) {
                const int fd = events[i].data.fd;
                if (fd == server.stop_event_fd_) continue;  // reste lisible : reveille tous les fils
                if (fd == data_fd) {
                    if (events[i].events & EPOLLOUT) flush_data_out();
                    if (events[i].events & (EPOLLIN | EPOLLHUP | EPOLLERR)) on_data_readable();
                    continue;
                }
                if (is_listen_fd(fd)) {
                    if (accepting && !server.stopping_.load()) accept_all(fd);
                    continue;
                }
                auto it = connections.find(fd);
                if (it == connections.end()) continue;
                Connection& c = *it->second;
                if (c.phase == Phase::handshake) {
                    on_handshake(c);
                    continue;
                }
                if (c.io_reversed && (c.phase == Phase::read_head || c.phase == Phase::read_body) &&
                    (events[i].events & EPOLLOUT)) {
                    on_readable(c);
                    continue;
                }
                if (c.io_reversed && c.phase == Phase::write && (events[i].events & EPOLLIN)) {
                    on_writable(c);
                    continue;
                }
                if ((events[i].events & EPOLLOUT) && c.phase == Phase::write) on_writable(c);
                if ((events[i].events & (EPOLLIN | EPOLLRDHUP | EPOLLHUP | EPOLLERR)) &&
                    (c.phase == Phase::read_head || c.phase == Phase::read_body)) {
                    on_readable(c);
                } else if ((events[i].events & (EPOLLHUP | EPOLLERR)) && c.phase == Phase::write) {
                    close_connection(c);
                }
            }
            if (Clock::now() >= next_scan) {
                check_deadlines();
                next_scan = Clock::now() + std::chrono::milliseconds(250);
            }
            collect_closed();
        }
    }

    std::size_t force_close_all() {
        std::size_t count = 0;
        for (auto& [fd, c] : connections) {
            if (c->phase != Phase::closed) {
                close_connection(*c);
                ++count;
            }
        }
        connections.clear();
        return count;
    }
};

namespace {

// Plan WAF natif, lot 4 : chaque regle que le natif laisse a Python est dite dans error.log (une ligne par regle,
// a chaque instantane installe : demarrage et rechargement).
void report_waf_filter(const Snapshot& snapshot) {
    if (!snapshot.waf_filter) return;
    for (const std::string& reason : snapshot.waf_filter->python_only_reasons()) {
        log_for(snapshot.error_log).append_line(format_error_line(
            "filtre WAF natif : regle evaluee par Python seulement - " + reason, "", unix_now()));
    }
}

}  // namespace

Server::Server(std::shared_ptr<const Snapshot> snapshot, ServerOptions options)
    : snapshot_(std::move(snapshot)), options_(std::move(options)) {
    stop_event_fd_ = ::eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK);
    grace_period_seconds_.store(snapshot_.load()->server.shutdown_grace_period_seconds);
    report_waf_filter(*snapshot_.load());
}

Server::~Server() {
    for (int fd : listen_fds_) ::close(fd);
    if (stop_event_fd_ >= 0) ::close(stop_event_fd_);
}

bool Server::listen(std::string* error) {
    if (const auto& tls = snapshot_.load()->tls) {
        tls_context_ = make_tls_context(*tls, error);
        if (!tls_context_) return false;  // jamais de HTTP a la place de HTTPS
    }
    if (!options_.listen_fds.empty()) {
        for (int fd : options_.listen_fds) {
            ::fcntl(fd, F_SETFL, ::fcntl(fd, F_GETFL) | O_NONBLOCK);
            listen_fds_.push_back(fd);
        }
        return true;
    }
    const auto current = snapshot_.load();
    const ServerSettings& settings = current->server;
    addrinfo hints{};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_PASSIVE;
    addrinfo* results = nullptr;
    const std::string port = std::to_string(settings.port);
    const int rc = ::getaddrinfo(settings.bind.empty() ? nullptr : settings.bind.c_str(), port.c_str(), &hints, &results);
    if (rc != 0) {
        if (error) *error = std::string("adresse d'ecoute invalide : ") + ::gai_strerror(rc);
        return false;
    }
    for (addrinfo* ai = results; ai != nullptr; ai = ai->ai_next) {
        const int fd = ::socket(ai->ai_family, ai->ai_socktype | SOCK_NONBLOCK | SOCK_CLOEXEC, ai->ai_protocol);
        if (fd < 0) continue;
        const int one = 1;
        ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
        if (ai->ai_family == AF_INET6) ::setsockopt(fd, IPPROTO_IPV6, IPV6_V6ONLY, &one, sizeof one);  // comme asyncio
        if (::bind(fd, ai->ai_addr, ai->ai_addrlen) != 0 || ::listen(fd, settings.listen_backlog) != 0) {
            if (error) *error = std::string("impossible d'ecouter sur ") + settings.bind + ":" + port + " : " + std::strerror(errno);
            ::close(fd);
            ::freeaddrinfo(results);
            for (int open_fd : listen_fds_) ::close(open_fd);
            listen_fds_.clear();
            return false;
        }
        listen_fds_.push_back(fd);
    }
    ::freeaddrinfo(results);
    if (listen_fds_.empty()) {
        if (error) *error = "aucune socket d'ecoute ouverte";
        return false;
    }
    return true;
}

void Server::stop() {
    // Appelee depuis un gestionnaire de signal : rien que des operations async-signal-safe.
    const auto grace = std::chrono::duration_cast<Clock::duration>(
        std::chrono::duration<double>(grace_period_seconds_.load()));
    force_deadline_.store((Clock::now() + grace).time_since_epoch().count());
    stopping_.store(true);
    const std::uint64_t one = 1;
    [[maybe_unused]] const ssize_t ignored = ::write(stop_event_fd_, &one, sizeof one);
}

void Server::attach_data_channel(std::size_t index, int fd) {
    std::lock_guard<std::mutex> lock(data_mutex_);
    if (pending_data_fds_.size() <= index) pending_data_fds_.resize(index + 1, -1);
    if (pending_data_fds_[index] >= 0) ::close(pending_data_fds_[index]);
    pending_data_fds_[index] = fd;
}

void Server::install_snapshot(std::shared_ptr<const Snapshot> snapshot) {
    report_waf_filter(*snapshot);
    grace_period_seconds_.store(snapshot->server.shutdown_grace_period_seconds);
    snapshot_.store(std::move(snapshot));
}

int Server::run() {
    int thread_count = options_.threads > 0 ? options_.threads : static_cast<int>(std::thread::hardware_concurrency());
    if (thread_count <= 0) thread_count = 1;
    std::vector<std::unique_ptr<Worker>> workers;
    for (int i = 0; i < thread_count; ++i) {
        auto worker = std::make_unique<Worker>(*this, static_cast<std::size_t>(i));
        if (!worker->setup()) return -1;
        workers.push_back(std::move(worker));
    }
    std::vector<std::thread> threads;
    threads.reserve(workers.size());
    for (auto& worker : workers) threads.emplace_back([w = worker.get()] { w->run(); });
    for (auto& thread : threads) thread.join();
    const std::size_t forced = forced_closures_.load();
    if (forced > 0) {
        // asyncio_server.py::shutdown
        const auto current = snapshot();
        log_for(current->error_log).append_line(format_error_line(
            "arret force de " + std::to_string(forced) + " connexion(s) encore actives apres le delai de grace de " +
                format_seconds(current->server.shutdown_grace_period_seconds) + "s",
            "", unix_now()));
    }
    return static_cast<int>(forced);
}

}  // namespace omega

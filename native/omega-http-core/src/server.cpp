// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "server.hpp"

#include <arpa/inet.h>
#include <fcntl.h>
#include <net/if.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/epoll.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/eventfd.h>
#include <sys/sendfile.h>
#include <sys/socket.h>
#include <unistd.h>

#include <openssl/err.h>
#include <openssl/rand.h>
#include <openssl/ssl.h>

#include <array>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <deque>
#include <map>
#include <mutex>
#include <optional>
#include <random>
#include <thread>
#include <tuple>
#include <unordered_map>
#include <unordered_set>

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
#include "upstream.hpp"
#include "upstream_tls.hpp"
#include "waf_alert.hpp"
#include "websocket.hpp"

namespace omega {

namespace {

using Clock = std::chrono::steady_clock;

std::int64_t unix_now() {
    return std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();
}

Clock::time_point after_seconds(double seconds) {
    return Clock::now() + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
}

// Lot 11, constat F1 (decision de l'auteur du 2026-11-14 : dans le code, pas une option) : le corps d'une requete n'a
// plus a arriver en entier dans read_timeout_seconds. Delai relance a chaque bloc recu, et debit moyen minimal :
// echeance = min(dernier octet + delai, debut du corps + delai + recu / 500 o/s) - comme mod_reqtimeout d'Apache
// (body=20,MinRate=500). Meme regle que le moteur Python (http_parser.BODY_MIN_RATE_BYTES_PER_SECOND).
constexpr double kBodyMinRateBytesPerSecond = 500.0;

Clock::time_point body_deadline(Clock::time_point started, std::uint64_t received, double timeout) {
    const auto at = [](Clock::time_point from, double seconds) {
        return from + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds));
    };
    return std::min(at(Clock::now(), timeout),
                    at(started, timeout + static_cast<double>(received) / kBodyMinRateBytesPerSecond));
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

enum class Phase { handshake, read_head, read_body, inspect, upstream, tunnel, write, closed };  // tunnel : lot 10
enum class UpstreamPhase { connecting, handshaking, sending, reading };  // plan proxy natif v2, lot 4 (TLS : lot 8)

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
    Clock::time_point body_started{};  // lot 11 (F1) : echeance du corps relancee a chaque bloc recu
    std::uint64_t body_received = 0;

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
    // Lot 1N (P3) : envoi interrompu -> ligne d'acces avec les octets du corps acquittes par le client, comme Python
    // (_write_response : TCP_INFO avant l'en-tete, taille de l'en-tete).
    std::optional<std::uint64_t> write_mark;
    std::size_t head_size = 0;
    bool keep_alive_after_write = false;
    bool want_write = false;
    // Correctif 2.6.2 (D29) : surveillance epoll vide pendant l'attente d'un verdict (voir pause_interest).
    bool interest_paused = false;
    // Lot 1N (P3, regle nginx) : client parti (fin de flux, demi-fermeture comprise, ou RST) pendant l'attente du
    // verdict - abandon a la premiere verification de 250 ms qui suit, comme _unless_client_leaves en Python.
    // Plan proxy natif v2, lot 4 (decision de l'auteur du 2026-11-13) : comme _unless_client_leaves en Python, le
    // depart du client n'est surveille que pendant la route (le relais vers le backend), jamais pendant le controle
    // de securite - pendant celui-ci il est seulement note (client_gone), et le verdict est toujours applique.
    std::chrono::steady_clock::time_point route_started{};
    bool client_gone = false;
    std::chrono::steady_clock::time_point abandon_at{};

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

    // Plan proxy natif v2, lot 4 : zone relayee par le natif (index dans snapshot->proxy->zones, -1 sinon), corps
    // entier garde pour le backend (C2 : recu en entier, inspecte, puis envoye), budgets reserves.
    int proxy_zone = -1;
    std::string body_full;
    std::uint64_t reserved_body = 0;
    bool reserved_inspection = false;
    int up_fd = -1;
    SSL* up_ssl = nullptr;      // lot 8 (C15) : TLS vers le backend, libere avec la socket (ou confie au pool)
    bool up_want_write = false;  // lot 8 : lecture TLS qui attend de pouvoir ecrire (renegociation, cle mise a jour)
    std::uint32_t up_events = 0;  // lot 11 : surveillance epoll posee sur up_fd (0 : pas inscrite)
    bool reserved_upstream = false;
    UpstreamPhase up_phase = UpstreamPhase::connecting;
    std::string up_out;
    std::size_t up_out_offset = 0;
    std::string up_in;
    bool up_eof = false;
    bool up_sent = false;
    std::string effective_path;  // chemin apres reecritures, envoye au backend

    // Plan proxy natif v2, lot 5 : relais en flux (C5, C12), pool (S14), nouvel essai (C8). Remis a zero a chaque
    // requete relayee (start_upstream).
    struct Relay {
        bool head_parsed = false;
        UpstreamHead head;                  // tete du backend (statut, en-tetes) : reponse construite a partir d'elle
        UpstreamFraming framing = UpstreamFraming::none;
        std::uint64_t remaining = 0;        // Content-Length : octets du corps encore attendus
        ChunkedDecoder chunked;
        bool reusable = false;              // HTTP/1.1 sans jeton close : recyclable si la reponse finit exactement
        bool done = false;                  // backend fini (lu en entier, ou coupe) : il ne reste qu'a vider vers le client
        bool paused = false;                // contre-pression : lecture du backend suspendue
        bool reused = false;                // connexion empruntee au pool
        bool retried = false;               // nouvel essai deja fait (un seul)
        bool retry_reserved = false;        // compte dans upstream_retries_in_flight_
        bool response_byte = false;         // au moins un octet de reponse recu (C8 : plus aucun nouvel essai)
        Clock::time_point deadline{};       // delai du backend (connexion, premier octet, entre deux blocs)
        bool deadline_armed = false;
        std::string pool_key;
        Response::Stream client = Response::Stream::none;  // decoupage vers le client
        bool head_sent = false;             // tete envoyee au client : la reponse ne peut plus etre remplacee (C4)
        std::uint64_t body_relayed = 0;     // octets du corps decodes, mis en file pour le client (P2)
        std::uint64_t wire_queued = 0;      // octets mis en file apres la tete, decoupage chunked compris
        // P2 : correspondance octets envoyes / octets du corps, pour une reponse chunked interrompue.
        struct ChunkMark {
            std::uint64_t wire_start;
            std::uint64_t header;
            std::uint64_t data;
            std::uint64_t body_start;
        };
        std::deque<ChunkMark> marks;
        // Lot 6 : backend choisi (index dans zone.upstreams), reservation (C9), nouvel essai sur un autre backend.
        std::size_t backend_index = 0;
        std::shared_ptr<BackendState> backend;
        bool backend_held = false;
        Clock::time_point attempt_started{};
        std::unordered_set<std::string> excluded;
        bool other_backend_tried = false;
        std::size_t body_offset = 0;  // debut du corps dans up_out (requete reconstruite pour un autre backend)
    };
    Relay relay;

    // Plan proxy natif v2, lot 10 (C17) : mise a niveau WebSocket vers une zone native (chemin de serve_websocket_proxy),
    // puis tunnel apres le 101 : octets relayes tels quels dans les deux sens (out vers le client, up_out vers le backend).
    bool websocket = false;
    struct Tunnel {
        WebSocketFrameTracker to_client;   // fin des trames en file vers le client (trame 1001 seulement entre deux)
        WebSocketFrameTracker to_backend;
        std::uint64_t bytes_to_client = 0;  // octets du backend mis en file pour le client (journal, decision 2026-11-14)
        std::int64_t idle_ms = 0;           // websocket_idle_timeout_ms de la zone (0 : aucun delai)
        Clock::time_point idle_deadline{};
        bool closing = false;               // un cote a ferme, delai ecoule ou arret : plus de lecture, on vide puis ferme
        Clock::time_point closing_deadline{};
        bool client_eof = false, backend_eof = false;    // plus rien a lire de ce cote
        bool client_dead = false, backend_dead = false;  // plus rien ne peut y etre ecrit
        bool client_read_wants_write = false, client_write_wants_read = false;    // TLS : sens inverse attendu
        bool backend_read_wants_write = false, backend_write_wants_read = false;
        std::uint32_t client_events = ~0u, backend_events = ~0u;  // surveillance epoll en place (~0 : inconnue)
    };
    Tunnel tunnel;

    SSL* ssl = nullptr;        // TLS direct (lot 3b)
    std::string tls_pending;   // poignee de main : octets produits par OpenSSL, pas encore envoyes
    bool handshake_done = false;
    bool counted = false;      // compte dans active_connections_ (en TLS : seulement apres la poignee de main)
    // Lot 9b (trafic des sites) : ce que la socket avait deja vu a l'arrivee ici, plus ce qui est deja compte
    std::uint64_t traffic_in = 0;
    std::uint64_t traffic_out = 0;
    bool io_reversed = false;  // TLS : lecture qui attend une ecriture du protocole, ou l'inverse

    ~Connection() {
        if (up_fd >= 0) ::close(up_fd);  // filet : release_proxy l'a normalement deja ferme
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
    bool accept_paused = false;           // lot A (D32) : acceptation suspendue apres EMFILE
    Clock::time_point accept_resume_at{};

    std::uint64_t clean_decisions = 0;  // requetes jugees propres par ce fil (controle 1/N, plan WAF natif lot 4)
    // Canal INSPECT/VERDICT de ce fil (lot 4) : trames en attente d'envoi, requetes en attente de verdict.
    int data_fd = -1;
    struct Outgoing {
        std::string encoded;
        std::vector<int> fds;  // HANDOFF : descripteurs a transmettre (fermes ici apres envoi)
        std::uint64_t inspect_key = 0;  // INSPECT : requete a refuser si le noyau rejette la trame (correctif 2.6.2)
    };
    std::deque<Outgoing> data_out;
    std::unordered_map<std::uint64_t, int> awaiting_verdict;  // identifiant de requete -> fd de la connexion
    std::unordered_map<int, int> upstream_owner;  // plan proxy natif v2, lot 4 : fd du backend -> fd du client
    static constexpr std::size_t kMaxQueuedInspects = 4096;
    // Correctif 2.6.2 (D20) : plus grande trame que le canal accepte d'un bloc (SOCK_SEQPACKET : tampon d'envoi moins
    // l'en-tete du noyau). Le systeme le fixe a 208 Kio par defaut (net.core.wmem_default) : bien en dessous de
    // kMaxPayload. Le superviseur l'agrandit quand le systeme le permet ; la valeur reelle est relue ici.
    std::size_t max_message = ipc::kHeaderSize + ipc::kMaxPayload;
    static constexpr std::size_t kInspectFrameMargin = 16 * 1024;  // champs de la trame hors tete et corps
    static constexpr std::size_t kInlineBytes = 768 * 1024;  // au-dela : memfd (connexion confiee, corps inspecte)

    // memfd rempli de `content` (fd >= 0) ; -1 si impossible. Ferme par l'envoi (Outgoing) ou par l'appelant.
    static int memfd_with(const std::string& content) {
        const int memfd = ::memfd_create("omega-inspect", MFD_CLOEXEC);
        if (memfd < 0) return -1;
        std::size_t written = 0;
        while (written < content.size()) {
            const ssize_t n = ::write(memfd, content.data() + written, content.size() - written);
            if (n <= 0) {
                ::close(memfd);
                return -1;
            }
            written += static_cast<std::size_t>(n);
        }
        return memfd;
    }

    Worker(Server& owner, std::size_t rank) : server(owner), index(rank) {}
    ~Worker() {
        for (const IdleUpstream& idle : idle_upstreams) {  // lot 5 : pool
            free_upstream_tls(idle.ssl);
            ::close(idle.fd);
            server.upstream_idle_.fetch_sub(1);
            server.upstream_connections_.fetch_sub(1);
        }
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
        if (index == 0 && server.transfer_event_fd_ >= 0) {  // lot 3 (P6) : seul le fil 0 reprend les connexions
            epoll_event transfer{};
            transfer.events = EPOLLIN;
            transfer.data.fd = server.transfer_event_fd_;
            if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, server.transfer_event_fd_, &transfer) != 0) return false;
        }
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
        int sndbuf = 0;
        socklen_t length = sizeof sndbuf;
        max_message = ipc::kHeaderSize + ipc::kMaxPayload;
        if (::getsockopt(fd, SOL_SOCKET, SO_SNDBUF, &sndbuf, &length) == 0 && sndbuf > 1024) {
            max_message = std::min(max_message, static_cast<std::size_t>(sndbuf) - 512);  // en-tete du noyau : marge
        }
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
            if (result == 2) {  // D20 : trame refusee par le noyau - le canal reste bon, seule cette requete est refusee
                Outgoing rejected = std::move(data_out.front());
                data_out.pop_front();
                for (int fd : rejected.fds) ::close(fd);  // connexion confiee non transmise : le client voit une fin
                const auto waiting = rejected.inspect_key != 0 ? awaiting_verdict.find(rejected.inspect_key)
                                                               : awaiting_verdict.end();
                if (waiting != awaiting_verdict.end()) {
                    auto it = connections.find(waiting->second);
                    if (it != connections.end() && it->second->phase == Phase::inspect &&
                        it->second->inspect_key == rejected.inspect_key) {
                        inspection_failed(*it->second, "requete trop grande pour le canal", true);
                    }
                }
                continue;
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
            int fd = -1;
            const int result = ipc::recv_frame_nowait(data_fd, frame, &fd, &error);
            if (result == 2) return;
            if (result != 0) {
                data_channel_lost(result == 1 ? "processus de securite arrete" : "trame illisible");
                return;
            }
            if (frame.type == ipc::kHandoffDone && fd >= 0) {
                adopt_returned_connection(frame, fd);
                continue;
            }
            if (fd >= 0) ::close(fd);  // aucun autre message n'apporte de descripteur
            if (frame.type == ipc::kVerdict) apply_verdict(frame);
            else if (frame.type == ipc::kWatch) apply_watch(frame, ipc::tag::kWatchEntry);
            else if (frame.type == ipc::kBackendEvent) apply_backend_events(frame);
        }
    }

    // Lot 3 : sources que Python veut voir pour toutes leurs requetes (table commune a tous les fils).
    void apply_watch(const ipc::Frame& frame, std::uint16_t tag) {
        const std::int64_t now = std::chrono::duration_cast<std::chrono::seconds>(
                                     std::chrono::system_clock::now().time_since_epoch()).count();
        for (const std::string& entry : frame.all(tag)) {
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

    // Plan proxy natif v2, lot 4 (D12, HANDOFF_DONE du contrat IPC) : Python rend la connexion apres sa reponse, avec
    // les octets deja lus (requete suivante eventuelle). Le natif la reprend comme une connexion neuve de ce fil : chaque
    // requete repasse par lui, et la limite de debit n'a plus qu'une autorite (avant : Python gardait la connexion et
    // comptait ses requetes a part - limite doublee).
    void adopt_returned_connection(const ipc::Frame& frame, int fd) {
        sockaddr_storage address{};
        socklen_t length = sizeof address;
        if (::getpeername(fd, reinterpret_cast<sockaddr*>(&address), &length) != 0) {
            ::close(fd);  // client deja parti
            return;
        }
        ::fcntl(fd, F_SETFL, ::fcntl(fd, F_GETFL) | O_NONBLOCK);
        auto c = std::make_unique<Connection>();
        c->fd = fd;
        c->peer_ip = peer_address(address);
        c->snapshot = server.snapshot();
        if (const std::string* bytes = frame.first(ipc::tag::kHandoffDoneBytes)) c->in = *bytes;
        c->requests_served = static_cast<int>(frame.unsigned_field(ipc::tag::kHandoffDoneServed).value_or(0));
        // Lot 9b : rendue par Python, qui a compte jusqu'ici ; seule la suite compte
        if (const auto seen = socket_traffic(fd)) std::tie(c->traffic_in, c->traffic_out) = *seen;
        server.active_connections_.fetch_add(1);  // deja admise : jamais refusee pour capacite ici
        c->counted = true;
        epoll_event event{};
        event.events = EPOLLIN | EPOLLRDHUP;
        event.data.fd = fd;
        if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, fd, &event) != 0) {
            server.active_connections_.fetch_sub(1);
            return;  // ~Connection ferme le fd
        }
        c->phase_timeout = c->snapshot->server.keepalive_timeout_seconds;
        c->deadline = after_seconds(c->phase_timeout);
        c->has_deadline = true;
        Connection& adopted = *c;
        connections[fd] = std::move(c);
        on_readable(adopted);
    }

    // Lot 6 : la connexion entiere passe a Python (meme _handle_connection que le moteur Python), avec les octets
    // deja lus (tete en cours comprise) et le nombre de requetes deja servies. Lot 4 : Python la rend apres sa reponse.
    void hand_off(Connection& c) {
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
        // Plan proxy natif v2, lot 4 (D12) : la requete confiee est comptee ici, comme toutes les autres ; Python
        // applique ce resultat au lieu de compter dans son propre magasin.
        if (c.snapshot->inspect && c.snapshot->inspect->security_stage) {
            count_rate_limit(c);
            if (c.rate_counted) frame.add_u32(ipc::tag::kHandoffRateLimit, c.rate_retry);
        }
        std::vector<int> fds;
        const int client = ::dup(c.fd);
        if (client < 0) {
            respond(c, error_response(503), false);
            return;
        }
        fds.push_back(client);
        // D20 : en ligne seulement si la trame tient dans le tampon du canal ; sinon memfd (deja prevu au-dela de 768 Kio).
        if (pending.size() <= kInlineBytes && pending.size() + kInspectFrameMargin <= max_message) {
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
        if (c.proxy_zone >= 0 && !delegate && !c.reserved_inspection) {
            // Plan proxy natif v2, lot 4 (C2, S16) : INSPECT simultanes du relais bornes - 503 immediat au-dela.
            const std::uint64_t before = server.proxy_inspections_.fetch_add(1);
            c.reserved_inspection = true;
            if (before >= c.snapshot->proxy->budgets.inspections) {
                release_inspection(c);
                log_error(c, "reverse proxy natif : budget des controles en attente epuise "
                             "(options.reverse_proxy.max_concurrent_inspections) - 503", c.request.request_id);
                respond(c, error_response(503), false);
                return;
            }
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
        // Plan proxy natif v2, lot 4 (S23) : corps capture dans la trame s'il y tient (768 Kio au plus, comme la
        // connexion confiee), sinon par memfd - jusqu'a body_max_inspect_bytes, plus de cas « trop grand » pour lui.
        std::vector<int> fds;
        if (c.capture_body) {
            constexpr std::size_t kTlvHeader = 6;
            const std::size_t without_body = ipc::encode(frame).size();
            if (c.body_capture.size() <= kInlineBytes && without_body + kTlvHeader + c.body_capture.size() <= max_message) {
                frame.add(ipc::tag::kInspectBody, c.body_capture);
            } else {
                const int memfd = memfd_with(c.body_capture);
                if (memfd < 0) {
                    inspection_failed(c, "memfd impossible pour le corps inspecte", true);
                    return;
                }
                frame.add_u64(ipc::tag::kInspectBodyFd, c.body_capture.size());
                fds.push_back(memfd);
            }
        }
        std::string encoded = ipc::encode(frame);
        if (encoded.size() > max_message) {
            // Correctif 2.6.2 (D20) : seule une tete demesuree (max_header_size enorme) peut encore depasser la trame,
            // condition que le client provoque lui-meme. Jamais servie sans controle, quel que soit on_error.
            for (int fd : fds) ::close(fd);
            inspection_failed(c, "requete trop grande pour le canal", true);
            return;
        }
        data_out.push_back(Outgoing{std::move(encoded), std::move(fds), c.inspect_key});
        c.phase = Phase::inspect;
        pause_interest(c);
        c.deadline = after_seconds(static_cast<double>(settings.timeout_ms) / 1000.0);
        c.has_deadline = true;
        awaiting_verdict[c.inspect_key] = c.fd;
        flush_data_out();
    }

    // Correctif 2.6.2 (D29) : pendant l'attente du verdict, plus aucune surveillance en lecture. En declenchement par
    // niveau, un client a demi ferme (ou des octets deja recus) faisait tourner le fil a 100 % jusqu'au verdict.
    // Lot 1N (P3) : fin de flux (EPOLLRDHUP), EPOLLHUP et EPOLLERR surveilles PAR FRONT - signales une fois, jamais en
    // boucle - pour reconnaitre le client parti (client_left_during_inspection) ; les octets recus ne reveillent rien.
    // Lot 11 (mesures) : EPOLLOUT par front aussi - surveillance deja prete pour la reponse relayee (begin_stream ne
    // la repose plus) ; signale une fois, sans effet avant la tete envoyee, jamais en boucle.
    void pause_interest(Connection& c) {
        epoll_event event{};
        event.events = kPausedEvents;
        event.data.fd = c.fd;
        ::epoll_ctl(epoll_fd, EPOLL_CTL_MOD, c.fd, &event);
        c.interest_paused = true;
    }

    // P3 (regle nginx), comme _unless_client_leaves : fin de flux (demi-fermeture comprise), RST ou erreur du client.
    // Pendant le controle de securite : seulement note. Pendant le relais : constate aux verifications faites toutes les
    // 250 ms depuis le debut de la route - une reponse prete avant part toujours (decision de l'auteur du 2026-11-13).
    void client_left(Connection& c, std::uint32_t events) {
        if (c.client_gone) return;
        if (!(events & (EPOLLHUP | EPOLLERR)) && pending_client_bytes(c)) {
            // StreamReader.at_eof() : fin de flux ET plus rien a lire - un client qui a deja envoye la requete suivante
            // (pipelining) puis s'est ferme a demi n'est pas parti.
            return;
        }
        c.client_gone = true;
        if (c.phase == Phase::upstream && !c.websocket) schedule_abandon(c);  // lot 10 : comme serve_websocket_proxy
    }

    [[nodiscard]] static bool pending_client_bytes(const Connection& c) {
        if (!c.in.empty()) return true;
        int available = 0;
        return ::ioctl(c.fd, FIONREAD, &available) == 0 && available > 0;
    }

    void schedule_abandon(Connection& c) {
        constexpr auto kPoll = std::chrono::milliseconds(250);
        const auto elapsed = Clock::now() - c.route_started;
        const auto ticks = std::max<std::int64_t>(1, (elapsed + kPoll - Clock::duration(1)) / kPoll);
        c.abandon_at = c.route_started + ticks * kPoll;
    }

    [[nodiscard]] static bool abandon_due(const Connection& c, Clock::time_point now) {
        // Lot 5 : seulement tant que le backend est lu (la route) ; ensuite il ne reste qu'a ecrire, comme Python.
        return c.phase == Phase::upstream && !c.websocket && c.client_gone && !c.relay.done && now >= c.abandon_at;
    }

    // Lot 1N (D36, P4) : meme ligne waf-alerts que _log_waf_alert pour un refus que le natif decide seul.
    void write_native_alert(const Connection& c, const char* stage, const char* action, int status,
                            Clock::time_point decision_start) {
        const auto& settings = c.snapshot->inspect->waf_alerts;
        if (!settings) return;
        WafAlert alert;
        alert.unix_us = std::chrono::duration_cast<std::chrono::microseconds>(
                            std::chrono::system_clock::now().time_since_epoch()).count();
        alert.request_id = c.request.request_id;
        alert.remote_ip = c.request.remote_ip;
        alert.method = latin1_to_utf8(c.head.method);
        alert.path = c.request.path_text;
        if (const std::string* user_agent = c.head.header("user-agent")) alert.user_agent = latin1_to_utf8(*user_agent);
        alert.action = action;
        alert.stage = stage;
        alert.status_code = status;
        alert.duration_ms = std::chrono::duration<double, std::milli>(Clock::now() - decision_start).count();
        if (c.capture_body && !c.body_capture.empty()) alert.body = c.body_capture;
        log_for(settings->path).append_line(format_waf_alert_line(alert, *settings));
    }

    // Processus de securite indisponible, en retard ou canal plein : waf.on_internal_error (Auth : toujours refuse).
    // `always_refuse` : requete impossible a controler (trop grande pour le canal) - jamais servie sans controle.
    void inspection_failed(Connection& c, const char* why, bool always_refuse = false) {
        release_inspection(c);
        awaiting_verdict.erase(c.inspect_key);
        if (c.delegating) {  // route Python injoignable : rien a servir a sa place (jamais une boucle de routage)
            log_error(c, std::string("route confiée à Python indisponible (") + why + ")", c.request.request_id);
            respond(c, error_response(503), true);
            return;
        }
        const bool fail_closed = always_refuse || c.snapshot->inspect->fail_closed;
        log_error(c, std::string("controle de securite indisponible (") + why + ") : requete " +
                         (always_refuse ? "refusee (503, jamais servie sans controle)"
                          : fail_closed ? "refusee (503, fail-closed)" : "servie sans controle (fail-open)"),
                  c.request.request_id);
        const auto decision_start = Clock::now();
        if (!fail_closed && c.snapshot->inspect->blocklist_path &&
            blocklist_for(*c.snapshot->inspect->blocklist_path)
                .is_blocked(c.request.remote_ip, std::chrono::duration_cast<std::chrono::microseconds>(
                                                     std::chrono::system_clock::now().time_since_epoch()).count())) {
            // Decision utilisateur 2026-11-02 : fail-open ne libere jamais une adresse deja bannie (451, comme le WAF).
            log_error(c, "adresse bannie refusee par le moteur natif (451) pendant l'indisponibilite du controle",
                      c.request.request_id);
            write_native_alert(c, "blocklist", "block", 451, decision_start);  // lot 1N (D36)
            Response response = error_response(451);
            apply_security_headers(response, *c.snapshot, c.request.path_text);
            c.requests_served += 1;
            start_write(c, std::move(response), false, true);
            return;
        }
        const RatePolicy* rate_policy = c.snapshot->waf_filter ? c.snapshot->waf_filter->rate_policy() : nullptr;
        if (!fail_closed && c.rate_retry > 0 && rate_policy != nullptr) {
            // Lot 1N (decision de l'auteur du 2026-11-12) : fail-open ne leve jamais une limite deja mesuree - meme
            // reponse que le WAF (statut regle, Retry-After, connexion fermee) et meme alerte (« throttle » pour une
            // source sure, jamais comptee par fail2ban).
            const int status = rate_policy->response_status();
            log_error(c, "limite de debit depassee : requete refusee par le moteur natif (" + std::to_string(status) +
                             ") pendant l'indisponibilite du controle",
                      c.request.request_id);
            write_native_alert(c, "rate_limit", rate_policy->trusted_source(c.request.remote_ip) ? "throttle" : "block",
                               status, decision_start);
            Response response = error_response(status);
            response.headers.set("Retry-After", std::to_string(c.rate_retry));
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

    // Plan proxy natif v2, lot 6 (P6) : sonde active, score de charge et etat manuel envoyes par le processus n° 0,
    // appliques a la table commune (tous les fils, toutes les adresses du nom).
    void apply_backend_events(const ipc::Frame& frame) {
        const auto snapshot = server.snapshot();
        if (!snapshot->proxy) return;
        const auto now = Clock::now();
        for (const std::string& entry : frame.all(ipc::tag::kBackendEntry)) {
            std::vector<std::string_view> parts;
            std::size_t start = 0;
            while (parts.size() < 4) {
                const std::size_t zero = entry.find('\0', start);
                parts.push_back(std::string_view(entry).substr(start, zero == std::string::npos ? std::string::npos : zero - start));
                if (zero == std::string::npos) break;
                start = zero + 1;
            }
            if (parts.size() != 4) continue;
            apply_backend_event(server.balance_registry_, *snapshot->proxy, parts[0], parts[1], parts[2], parts[3], now);
        }
    }

    // Lot 6 (Q7) : etat des backends des zones natives pour le processus n° 0 (administration, ecran Reverse proxy).
    void send_backend_state() {
        if (index != 0 || data_fd < 0) return;
        const auto snapshot = server.snapshot();
        if (!snapshot->proxy) return;
        ipc::Frame frame;
        frame.type = ipc::kBackendState;
        frame.generation = snapshot->generation;
        bool any = false;
        for (const auto& report : server.balance_registry_.report(*snapshot->proxy)) {
            // Tableau de bord (2026-11-16) : requetes, 502, 504 et temps moyen (us, -1 : jamais) apres « actives ».
            frame.add(ipc::tag::kBackendEntry, report.zone + '\0' + report.key + '\0' + report.name + '\0' + report.status +
                                                   '\0' + std::to_string(report.active) + '\0' +
                                                   std::to_string(report.requests) + '\0' +
                                                   std::to_string(report.errors_502) + '\0' +
                                                   std::to_string(report.errors_504) + '\0' + std::to_string(report.avg_us));
            any = true;
        }
        if (!any) return;
        std::string encoded = ipc::encode(frame);
        if (encoded.size() > max_message) return;  // des milliers de backends : jamais un canal bloque pour l'affichage
        data_out.push_back(Outgoing{std::move(encoded), {}, 0});
        flush_data_out();
    }

    void apply_verdict(const ipc::Frame& frame) {
        // Lot 6 (P5, S26) : la surveillance decidee par ce verdict s'applique avant lui, meme si la requete est partie.
        apply_watch(frame, ipc::tag::kVerdictWatch);
        const auto found = awaiting_verdict.find(frame.request_id);
        if (found == awaiting_verdict.end()) return;  // arrive apres le delai, ou client parti : ignore
        const int fd = found->second;
        awaiting_verdict.erase(found);
        auto it = connections.find(fd);
        if (it == connections.end()) return;
        Connection& c = *it->second;
        if (c.phase != Phase::inspect || c.inspect_key != frame.request_id) return;
        release_inspection(c);
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

    // Lot A (D32) : plus de descripteur (EMFILE...) -> la socket d'ecoute restait lisible, en declenchement par niveau,
    // et le fil tournait a vide (5,9 s de CPU en 3 s, essai du 2026-11-12). Comme asyncio (ACCEPT_RETRY_DELAY) :
    // l'acceptation s'arrete 1 s sur ce fil, avec un message, puis reprend.
    void pause_accepting() {
        const int error = errno;
        if (accept_paused || !accepting) return;
        accept_paused = true;
        accept_resume_at = Clock::now() + std::chrono::seconds(1);
        for (int fd : server.listen_fds_) ::epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, nullptr);
        std::fprintf(stderr, "omega-http-core : acceptation suspendue 1 s (plus de ressources systeme : %s)\n",
                     std::strerror(error));
    }

    void resume_accepting() {
        accept_paused = false;
        if (!accepting || server.stopping_.load()) return;
        for (int fd : server.listen_fds_) {
            epoll_event event{};
            event.events = EPOLLIN | EPOLLEXCLUSIVE;
            event.data.fd = fd;
            ::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, fd, &event);
        }
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

    // Lot 7 (decision de l'auteur du 2026-11-13, comme nginx) : a l'arret, une connexion qui attend sa premiere ou sa
    // prochaine requete (rien de recu) est fermee tout de suite, sans journal - jamais un faux « arret force ».
    void close_idle_connections() {
        for (auto& [fd, c] : connections) {
            if (c->phase == Phase::handshake || (c->phase == Phase::read_head && c->in.empty())) close_connection(*c);
        }
    }

    // ------------------------------------------------------------------------------------- trafic (lot 9b)
    // Compteurs du noyau de la socket cliente : recu (tcpi_bytes_received) et confie au noyau (tcpi_bytes_acked + file
    // d'envoi pas encore acquittee, TIOCOUTQ) - meme mesure que le moteur Python (traffic_meter.py). tcp_info est lu
    // par decalage : la version de la glibc ne declare pas toujours ces champs (linux/tcp.h : octets 120 et 128).
    static std::optional<std::pair<std::uint64_t, std::uint64_t>> socket_traffic(int fd) {
        unsigned char info[136] = {};
        socklen_t length = sizeof info;
        if (fd < 0 || ::getsockopt(fd, IPPROTO_TCP, TCP_INFO, info, &length) != 0 || length < sizeof info) {
            return std::nullopt;
        }
        std::uint64_t acked = 0;
        std::uint64_t received = 0;
        std::memcpy(&acked, info + 120, sizeof acked);
        std::memcpy(&received, info + 128, sizeof received);
        int queued = 0;
        if (::ioctl(fd, TIOCOUTQ, &queued) != 0 || queued < 0) queued = 0;
        return std::make_pair(received, acked + static_cast<std::uint64_t>(queued));
    }

    void account_traffic(Connection& c) {
        const auto seen = socket_traffic(c.fd);
        if (!seen) return;
        if (seen->first > c.traffic_in) {
            server.bytes_in_.fetch_add(seen->first - c.traffic_in, std::memory_order_relaxed);
            c.traffic_in = seen->first;
        }
        if (seen->second > c.traffic_out) {
            server.bytes_out_.fetch_add(seen->second - c.traffic_out, std::memory_order_relaxed);
            c.traffic_out = seen->second;
        }
    }

    void close_connection(Connection& c) {
        if (c.phase == Phase::closed) return;
        release_proxy(c);
        if (c.ssl != nullptr && c.phase != Phase::handshake) {
            ERR_clear_error();
            (void)SSL_shutdown(c.ssl);  // close_notify, sans attendre la reponse (transport asyncio ferme)
            ERR_clear_error();
        }
        account_traffic(c);  // lot 9b : socket encore ouverte (confiee a Python : il compte a partir d'ici)
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
        // Lot A (D30) : la connexion est deja comptee depuis son acceptation (accept_all).
        c.phase = Phase::read_head;
        c.phase_timeout = c.snapshot->server.read_timeout_seconds;
        c.deadline = after_seconds(c.phase_timeout);
        c.has_deadline = true;
        set_write_interest(c, false);
        on_readable(c);  // des octets applicatifs ont pu arriver avec la fin de la poignee de main
    }

    void set_write_interest(Connection& c, bool want) {
        if (c.want_write == want && !c.interest_paused) return;  // surveillance suspendue : toujours retablie
        c.want_write = want;
        c.interest_paused = false;
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
                if (errno == EMFILE || errno == ENFILE || errno == ENOBUFS || errno == ENOMEM) {
                    pause_accepting();  // lot A (D32)
                }
                return;  // EAGAIN : un autre fil l'a prise
            }
            const int one = 1;
            ::setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
            auto c = std::make_unique<Connection>();
            c->fd = fd;
            c->peer_ip = peer_address(address);
            c->snapshot = server.snapshot();
            if (server.tls_context_) {
                // Lot A (D30) : comptee des l'acceptation, comme en clair - avant, seulement apres la poignee de main
                // (comme asyncio), donc 300 poignees muettes tenues avec max_connections = 5. Au-dela de la
                // capacite : fermeture immediate, rien ne peut partir en clair et la poignee de main couterait
                // justement ce que la capacite protege (le moteur Python fait de meme).
                const std::size_t active = server.active_connections_.fetch_add(1);
                if (active >= c->snapshot->server.max_connections) {
                    server.active_connections_.fetch_sub(1);
                    server.rejected_over_capacity_.fetch_add(1, std::memory_order_relaxed);
                    continue;  // ~Connection ferme le fd
                }
                auto release = [this] { server.active_connections_.fetch_sub(1); };
                c->ssl = SSL_new(server.tls_context_.get());
                if (c->ssl == nullptr) {
                    release();
                    continue;  // ~Connection ferme le fd
                }
                // Comme asyncio (sslproto, BIO memoire) : pendant la poignee de main, ce qu'OpenSSL veut envoyer
                // passe par un tampon que l'on n'envoie que si elle avance - un echec ne part donc jamais en
                // alerte TLS, la connexion est simplement fermee (meme comportement vu du client).
                BIO* read_bio = BIO_new_socket(fd, BIO_NOCLOSE);
                BIO* write_bio = BIO_new(BIO_s_mem());
                if (read_bio == nullptr || write_bio == nullptr) {
                    BIO_free(read_bio);
                    BIO_free(write_bio);
                    release();
                    continue;
                }
                SSL_set_bio(c->ssl, read_bio, write_bio);
                SSL_set_accept_state(c->ssl);
                epoll_event event{};
                event.events = EPOLLIN | EPOLLRDHUP;
                event.data.fd = fd;
                if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, fd, &event) != 0) {
                    release();
                    continue;
                }
                c->counted = true;
                c->phase = Phase::handshake;
                c->deadline = after_seconds(c->snapshot->server.read_timeout_seconds);  // lot A (D30) : 60 s avant
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
    // ------------------------------------------------------------------------------- relais natif (proxy, lots 4 et 5)
    // Lot 4 : premier trajet (Content-Length, une connexion par requete). Lot 5 : reponse relayee EN FLUX (C12) -
    // Content-Length annonce tel quel, chunked decode puis redecoupe par le serveur (Q4), fin par la fermeture relayee
    // en chunked (decision de l'auteur du 2026-11-13) ; tampon vers le client borne (marques haute et basse) ; pool de
    // connexions par fil (S14, regles de la 2.6.2) ; un seul nouvel essai sur une connexion du pool morte avant le
    // moindre octet de reponse (C8, D42). Chaque reservation (corps, INSPECT, connexion, essai) est rendue par
    // release_proxy sur tous les chemins, close_connection compris.
    // Lot 11 (mesures, accord de l'auteur du 2026-11-14) : 32 connexions inactives par backend ET PAR FIL (au lot 5 :
    // 10 tous fils confondus, une connexion neuve toutes les 5 requetes a 32 clients) ; toutes les connexions
    // inactives du moteur restent sous la moitie de max_upstream_connections, l'autre moitie toujours libre.
    static constexpr std::size_t kPoolIdlePerBackendPerThread = 32;
    static constexpr auto kPoolIdleTimeout = std::chrono::seconds(60);
    static constexpr std::uint32_t kIdleEvents = EPOLLIN | EPOLLRDHUP;  // connexion inactive : tout evenement la ferme
    // Client en attente (verdict, relais) puis reponse relayee : ecriture et depart par front, jamais la lecture.
    static constexpr std::uint32_t kPausedEvents = EPOLLOUT | EPOLLRDHUP | EPOLLET;
    static constexpr std::size_t kRelayHigh = 128 * 1024;  // C12 : au-dela, lecture du backend suspendue
    static constexpr std::size_t kRelayLow = 32 * 1024;    // en dessous, reprise
    static constexpr std::size_t kMaxChunkMarks = 8192;
    static constexpr std::size_t kHeadReadCap = 10 * (kMaxResponseLine + kMaxResponseHeaderBytes);

    struct IdleUpstream {
        int fd;
        std::string key;
        Clock::time_point since;
        SSL* ssl = nullptr;  // lot 8 : session TLS gardee avec la connexion
    };
    std::deque<IdleUpstream> idle_upstreams;  // ordre de mise au repos : le plus ancien devant
    std::uint64_t deadline_ticks = 0;
    std::uint32_t pool_generation = 0;

    // Lot 8 (D4, C15) : cle du pool = adresse, port et, en TLS, politique de verification et nom (SNI, nom verifie) -
    // une connexion ouverte sans verification ne sert jamais une zone qui l'exige.
    static std::string pool_key_for(const ProxyZoneSettings& zone, const ProxyUpstream& upstream) {
        std::string key = *upstream.address + "|" + std::to_string(upstream.port);
        if (upstream.tls) key += std::string(zone.verify_tls ? "|tls-verifie|" : "|tls-non-verifie|") + upstream.host;
        return key;
    }

    // Plan proxy natif v2, lot 7 (C13) : a chaque nouvelle generation, les connexions inactives d'un backend inchange
    // (meme cle : adresse, port, TLS et nom) restent au pool, celles des autres sont fermees.
    void prune_pool_on_new_generation() {
        const auto snapshot = server.snapshot();
        if (snapshot->generation == pool_generation) return;
        pool_generation = snapshot->generation;
        std::unordered_set<std::string> kept;
        if (snapshot->proxy) {
            for (const ProxyZoneSettings& zone : snapshot->proxy->zones) {
                for (const ProxyUpstream& upstream : zone.upstreams) {
                    if (zone.native && upstream.address) kept.insert(pool_key_for(zone, upstream));
                }
            }
        }
        for (std::size_t i = idle_upstreams.size(); i-- > 0;) {
            if (kept.count(idle_upstreams[i].key) == 0) close_idle_at(i);
        }
    }
    std::unordered_set<int> idle_fds;

    void release_inspection(Connection& c) {
        if (!c.reserved_inspection) return;
        c.reserved_inspection = false;
        server.proxy_inspections_.fetch_sub(1);
    }

    void release_body(Connection& c) {
        if (c.reserved_body > 0) {
            server.proxy_pending_body_.fetch_sub(c.reserved_body);
            c.reserved_body = 0;
        }
        std::string().swap(c.body_full);
    }

    // Socket vers le backend fermee et reservation rendue ; la requete sortante reste (nouvel essai possible).
    void drop_upstream_socket(Connection& c) {
        if (c.up_fd >= 0) {
            ::epoll_ctl(epoll_fd, EPOLL_CTL_DEL, c.up_fd, nullptr);
            upstream_owner.erase(c.up_fd);
            free_upstream_tls(c.up_ssl);
            c.up_ssl = nullptr;
            ::close(c.up_fd);
            c.up_fd = -1;
        }
        c.up_events = 0;
        c.up_want_write = false;
        if (c.reserved_upstream) {
            c.reserved_upstream = false;
            server.upstream_connections_.fetch_sub(1);
        }
    }

    void close_upstream(Connection& c) {
        drop_upstream_socket(c);
        std::string().swap(c.up_out);
        std::string().swap(c.up_in);
    }

    void release_proxy(Connection& c) {
        close_upstream(c);
        release_backend_of(c);  // lot 6 : requete abandonnee ou connexion fermee - ni succes ni echec
        release_inspection(c);
        release_body(c);
        if (c.relay.retry_reserved) {
            c.relay.retry_reserved = false;
            server.upstream_retries_in_flight_.fetch_sub(1);
        }
    }

    const ProxyZoneSettings& zone_of(const Connection& c) const {
        return c.snapshot->proxy->zones[static_cast<std::size_t>(c.proxy_zone)];
    }

    const ProxyUpstream& upstream_of(const Connection& c) const {
        return zone_of(c).upstreams[c.relay.backend_index];
    }

    // Lot 6 : reservation du backend rendue (requete finie, echouee ou abandonnee) - exactement une fois.
    void release_backend_of(Connection& c) {
        if (!c.relay.backend_held) return;
        c.relay.backend_held = false;
        release_backend(*c.relay.backend);
    }

    // _attempt_forward : echec (connexion, delai, reponse invalide ou coupee) - compte pour la sante, temps de reponse
    // pris egal au delai de lecture, comme Python.
    // Tableau de bord (2026-11-16) : l'echec compte aussi pour le backend, 504 si delai depasse apres l'envoi, sinon 502.
    void record_attempt_failure(Connection& c, int status) {
        if (!c.relay.backend_held) return;
        (status == 504 ? c.relay.backend->errors_504 : c.relay.backend->errors_502).fetch_add(1, std::memory_order_relaxed);
        const ProxyZoneSettings& zone = zone_of(c);
        record_response_time(*c.relay.backend, static_cast<double>(zone.read_timeout_ms) / 1000.0);
        record_backend_failure(*c.relay.backend, zone.unhealthy_after, Clock::now());
        release_backend_of(c);
    }

    void record_attempt_success(Connection& c) {
        if (!c.relay.backend_held) return;
        record_response_time(*c.relay.backend,
                             std::chrono::duration<double>(Clock::now() - c.relay.attempt_started).count());
        record_backend_success(*c.relay.backend, zone_of(c).healthy_after);
        release_backend_of(c);
    }

    BalanceRequest balance_request(const Connection& c) const {
        BalanceRequest request;
        request.client_ip = c.request.remote_ip;
        request.header = [&c](std::string_view name) -> std::optional<std::string> {
            const std::string* value = c.request.header(name);
            if (value == nullptr) return std::nullopt;
            return latin1_to_utf8(*value);  // HttpHeaders : texte, derniere valeur
        };
        return request;
    }

    bool take_selection(Connection& c, const Selection& selection) {
        if (selection.result != Selection::Result::chosen) return false;
        c.relay.backend_index = selection.index;
        c.relay.backend = selection.state;
        c.relay.backend_held = true;
        c.relay.attempt_started = Clock::now();
        selection.state->requests.fetch_add(1, std::memory_order_relaxed);  // tableau de bord : une tentative
        return true;
    }

    // Lot 6 : choix du backend (resolve_upstream) ; false : reponse deja envoyee (503 tout plein, 502 aucun backend).
    bool choose_backend(Connection& c) {
        const ProxyZoneSettings& zone = zone_of(c);
        const auto selection = select_backend(*server.balance_registry_.zone(zone.prefix), zone, balance_request(c),
                                              c.relay.excluded, Clock::now());
        if (selection.result == Selection::Result::at_capacity) {  // AllUpstreamsAtCapacityError
            finish_upstream(c, error_response(503));
            return false;
        }
        if (!take_selection(c, selection)) {
            log_error(c, "reverse proxy natif : aucun backend utilisable dans la zone " + zone.prefix +
                             " (nom DNS non resolu ou boucle) - 502", c.request.request_id);
            finish_upstream(c, error_response(502));
            return false;
        }
        return true;
    }

    // Requete vers le backend choisi, puis connexion : prise au pool (GET, HEAD, OPTIONS) ou neuve.
    void attempt_backend(Connection& c, std::string_view body) {
        const ProxyUpstream& upstream = upstream_of(c);
        UpstreamRequestContext context;
        context.zone = &zone_of(c);
        context.upstream = &upstream;
        context.effective_path = c.effective_path;
        context.client_tls = c.ssl != nullptr;
        context.listen_port = c.snapshot->server.port;
        context.trusted_networks = &c.snapshot->trusted_networks_for_internal;
        context.preserve_upgrade = c.websocket;
        auto outgoing = build_upstream_request(c.request, context, body);
        if (!outgoing || !upstream.address) {  // UnicodeEncodeError cote Python : 502
            release_backend_of(c);
            finish_upstream(c, error_response(502));
            return;
        }
        c.relay.body_offset = outgoing->size() - body.size();
        c.up_out = std::move(*outgoing);
        c.relay.pool_key = pool_key_for(zone_of(c), upstream);
        c.relay.reused = false;
        c.relay.retried = false;
        c.relay.response_byte = false;
        if (replayable(c.head.method) && !c.websocket) {  // lot 10 : un tunnel ouvre toujours une connexion neuve
            SSL* ssl = nullptr;
            const int fd = borrow_idle(c.relay.pool_key, &ssl);
            if (fd >= 0) {
                c.reserved_upstream = true;
                c.relay.reused = true;
                attach_upstream(c, fd, true, ssl, kIdleEvents);
                return;
            }
        }
        connect_fresh(c);
    }

    // C8 : nouvel essai sur un AUTRE backend (serve_proxy : GET, HEAD, OPTIONS, plusieurs backends, une seule fois),
    // seulement si rien n'est arrive du backend (le natif relaie en flux : rien a rejouer apres un octet de reponse).
    bool retry_other_backend(Connection& c) {
        const ProxyZoneSettings& zone = zone_of(c);
        if (c.relay.other_backend_tried || c.relay.response_byte || !replayable(c.head.method) || zone.upstreams.size() < 2)
            return false;
        if (!reserve_retry(c)) return false;
        c.relay.other_backend_tried = true;
        c.relay.excluded.insert(upstream_of(c).key);
        const std::string body = c.up_out.substr(std::min(c.relay.body_offset, c.up_out.size()));
        drop_upstream_socket(c);
        const auto selection = select_backend(*server.balance_registry_.zone(zone.prefix), zone, balance_request(c),
                                              c.relay.excluded, Clock::now());
        if (!take_selection(c, selection)) return false;  // tout plein ou rien d'autre : pas d'essai
        server.upstream_retries_.fetch_add(1, std::memory_order_relaxed);
        attempt_backend(c, body);
        return true;
    }

    // S19 : nouveaux essais en cours plafonnes pour tout le moteur (une reservation par requete, rendue a la fin).
    bool reserve_retry(Connection& c) {
        if (c.relay.retry_reserved) return true;
        const std::uint64_t cap = std::max<std::uint64_t>(3, c.snapshot->proxy->budgets.upstream_connections / 5);
        if (server.upstream_retries_in_flight_.fetch_add(1) >= cap) {
            server.upstream_retries_in_flight_.fetch_sub(1);
            log_error(c, "reverse proxy natif : nouvel essai refuse (trop de nouveaux essais en cours)",
                      c.request.request_id);
            return false;
        }
        c.relay.retry_reserved = true;
        return true;
    }

    void arm_upstream_deadline(Connection& c, std::int64_t milliseconds) {
        c.relay.deadline = after_seconds(static_cast<double>(milliseconds) / 1000.0);
        c.relay.deadline_armed = true;
    }

    // ---- pool (S14) : par fil, sans verrou ; une connexion inactive reste comptee dans max_upstream_connections.
    // Lot 11 : kPoolIdlePerBackendPerThread par backend dans chaque fil, et au plus la moitie du budget pour tout le
    // moteur (un fil sans connexion inactive a evincer trouve toujours de la place pour une connexion neuve).
    bool pool_has_room(const Connection& c, std::size_t same_key) const {
        return same_key < kPoolIdlePerBackendPerThread &&
               server.upstream_idle_.load(std::memory_order_relaxed) < c.snapshot->proxy->budgets.upstream_connections / 2;
    }

    void close_idle_at(std::size_t position) {
        const int fd = idle_upstreams[position].fd;
        ::epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, nullptr);
        free_upstream_tls(idle_upstreams[position].ssl);
        ::close(fd);
        idle_fds.erase(fd);
        idle_upstreams.erase(idle_upstreams.begin() + static_cast<std::ptrdiff_t>(position));
        server.upstream_idle_.fetch_sub(1);
        server.upstream_connections_.fetch_sub(1);
    }

    // Connexion inactive qui se signale (fin de flux, RST, octets hors reponse) : jamais reprise (D22). Lot 8 : en TLS,
    // des octets qui ne portent aucune donnee (ticket de session TLS 1.3 envoye apres la reponse) la laissent au pool,
    // comme asyncio qui les consomme sans les voir.
    void on_idle_event(int fd, std::uint32_t events) {
        for (std::size_t i = 0; i < idle_upstreams.size(); ++i) {
            if (idle_upstreams[i].fd == fd) {
                if (idle_upstreams[i].ssl != nullptr && (events & (EPOLLRDHUP | EPOLLHUP | EPOLLERR)) == 0 &&
                    tls_quiet(idle_upstreams[i].ssl))
                    return;
                close_idle_at(i);
                return;
            }
        }
    }

    // Lot 8 : rien a lire cote donnees - seulement des messages TLS sans donnee (ou rien du tout).
    static bool tls_quiet(SSL* ssl) {
        char byte = 0;
        std::size_t got = 0;
        ERR_clear_error();
        if (SSL_read_ex(ssl, &byte, 1, &got) == 1) return false;  // donnee hors reponse : connexion sale
        const int error = SSL_get_error(ssl, 0);
        ERR_clear_error();
        return error == SSL_ERROR_WANT_READ;
    }

    void expire_idle(Clock::time_point now) {
        while (!idle_upstreams.empty() && now - idle_upstreams.front().since >= kPoolIdleTimeout) close_idle_at(0);
    }

    // _borrow_idle_connection : la plus recente d'abord ; fermee, a EOF ou avec des octets en attente -> ecartee,
    // sans compter un essai (C8). La reservation de la connexion passe a la requete.
    int borrow_idle(const std::string& key, SSL** ssl) {
        for (std::size_t i = idle_upstreams.size(); i-- > 0;) {
            if (idle_upstreams[i].key != key) continue;
            const int fd = idle_upstreams[i].fd;
            char probe = 0;
            const ssize_t n = ::recv(fd, &probe, 1, MSG_PEEK | MSG_DONTWAIT);
            const bool quiet = (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) ||
                               (n > 0 && idle_upstreams[i].ssl != nullptr && tls_quiet(idle_upstreams[i].ssl));
            if (!quiet) {
                close_idle_at(i);
                continue;
            }
            *ssl = idle_upstreams[i].ssl;
            idle_fds.erase(fd);  // lot 11 : reste inscrite a epoll (kIdleEvents), reprise par attach_upstream
            idle_upstreams.erase(idle_upstreams.begin() + static_cast<std::ptrdiff_t>(i));
            server.upstream_idle_.fetch_sub(1);
            return fd;
        }
        return -1;
    }

    // D22 : reponse finie exactement, HTTP/1.1, aucun jeton close, aucun octet en attente -> au pool ; sinon fermee.
    void recycle_or_close(Connection& c) {
        bool reusable = c.relay.reusable && c.relay.framing != UpstreamFraming::close && c.up_in.empty() && !c.up_eof &&
                        c.up_fd >= 0 && c.reserved_upstream;
        if (reusable && c.up_ssl != nullptr) {
            reusable = tls_quiet(c.up_ssl);  // lot 8 : ticket de session lu, aucune donnee hors reponse
        } else if (reusable) {
            int available = 0;
            reusable = ::ioctl(c.up_fd, FIONREAD, &available) == 0 && available == 0;
        }
        std::size_t same = 0;
        for (const IdleUpstream& idle : idle_upstreams) same += idle.key == c.relay.pool_key ? 1u : 0u;
        if (!reusable || !pool_has_room(c, same)) {
            close_upstream(c);
            return;
        }
        const int fd = c.up_fd;
        upstream_owner.erase(fd);
        set_upstream_mask(c, kIdleEvents);  // tout evenement d'une connexion inactive la ferme
        c.up_events = 0;
        idle_upstreams.push_back(IdleUpstream{fd, c.relay.pool_key, Clock::now(), c.up_ssl});
        idle_fds.insert(fd);
        server.upstream_idle_.fetch_add(1);
        c.up_fd = -1;
        c.up_ssl = nullptr;
        c.reserved_upstream = false;  // la reservation reste comptee : elle appartient desormais au pool
        std::string().swap(c.up_out);
        std::string().swap(c.up_in);
    }

    [[nodiscard]] static bool replayable(std::string_view method) {
        return method == "GET" || method == "HEAD" || method == "OPTIONS";  // _REPLAYABLE_METHODS (D42)
    }

    void start_upstream(Connection& c) {
        c.relay = Connection::Relay{};
        // Debut de la route (_unless_client_leaves) : un client deja parti (note pendant le controle, ou fin de flux
        // deja lue) est constate a la premiere verification, 250 ms plus tard.
        c.route_started = Clock::now();
        if (!c.websocket) {  // lot 10 : la mise a niveau ne surveille pas le client (serve_websocket_proxy)
            if (c.eof && !pending_client_bytes(c)) c.client_gone = true;
            if (c.client_gone) schedule_abandon(c);
        }
        if (incoming_proxy_hop_count(c.request) >= kMaxProxyHops) {
            // Boucle indirecte entre instances : refus AVANT tout choix de backend (S6).
            finish_upstream(c, error_response(502));
            return;
        }
        c.phase = Phase::upstream;
        if (!c.interest_paused) pause_interest(c);  // S21 : aucune lecture du client pendant le relais
        c.has_deadline = false;  // delais du relais : backend (relay.deadline), puis ecriture vers le client
        if (!choose_backend(c)) return;
        const std::string body = std::move(c.body_full);
        release_body(c);  // copie dans la requete sortante : le corps en attente n'occupe plus le budget
        attempt_backend(c, c.websocket ? std::string_view() : std::string_view(body));  // lot 10 : tete seule
    }

    void connect_fresh(Connection& c) {
        const ProxyUpstream& upstream = upstream_of(c);
        const std::uint64_t before = server.upstream_connections_.fetch_add(1);
        c.reserved_upstream = true;
        if (before >= c.snapshot->proxy->budgets.upstream_connections && !evict_oldest_idle()) {
            log_error(c, "reverse proxy natif : budget des connexions vers les backends epuise "
                         "(options.reverse_proxy.max_upstream_connections) - 503", c.request.request_id);
            release_backend_of(c);
            finish_upstream(c, error_response(503));
            return;
        }
        addrinfo hints{};
        hints.ai_flags = AI_NUMERICHOST | AI_NUMERICSERV;
        hints.ai_socktype = SOCK_STREAM;
        addrinfo* found = nullptr;
        const std::string port = std::to_string(upstream.port);
        if (::getaddrinfo(upstream.address->c_str(), port.c_str(), &hints, &found) != 0 || found == nullptr) {
            attempt_failed(c, 502, false);
            return;
        }
        const int fd = ::socket(found->ai_family, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
        int connected = -1;
        if (fd >= 0) {
            const int one = 1;
            ::setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
            connected = ::connect(fd, found->ai_addr, found->ai_addrlen);
        }
        ::freeaddrinfo(found);
        if (fd < 0 || (connected != 0 && errno != EINPROGRESS)) {
            if (fd >= 0) ::close(fd);
            attempt_failed(c, 502, false);  // connexion impossible
            return;
        }
        attach_upstream(c, fd, false, nullptr);
    }

    // Budget atteint : une connexion inactive de ce fil cede sa place (la plus ancienne), sinon 503.
    bool evict_oldest_idle() {
        if (idle_upstreams.empty()) return false;
        close_idle_at(0);
        return true;
    }

    // Lot 11 (mesures) : `registered` = surveillance deja posee (connexion du pool, inscrite avec kIdleEvents) - ni
    // retrait ni nouvelle inscription. Connexion etablie (pool, ou connect() immediat) : la requete part tout de suite,
    // sans attendre un tour de boucle pour EPOLLOUT.
    void attach_upstream(Connection& c, int fd, bool connected, SSL* ssl, std::uint32_t registered = 0) {
        c.up_fd = fd;
        c.up_ssl = ssl;  // connexion du pool : session TLS deja etablie
        c.up_want_write = false;
        c.up_out_offset = 0;
        c.up_in.clear();
        c.up_eof = false;
        c.up_sent = false;
        c.up_phase = connected ? UpstreamPhase::sending : UpstreamPhase::connecting;
        upstream_owner[fd] = c.fd;
        if (registered != 0) {
            c.up_events = registered;
        } else {
            epoll_event event{};
            event.events = EPOLLOUT;
            event.data.fd = fd;
            ::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, fd, &event);
            c.up_events = EPOLLOUT;
        }
        arm_upstream_deadline(c, connected ? zone_of(c).read_timeout_ms : zone_of(c).connect_timeout_ms);
        if (connected) on_upstream_event(c, EPOLLOUT);
    }

    // C8 : connexion du pool morte avant le moindre octet de reponse (fermee, RST, delai) - _NoResponseFromReused-
    // Connection : une seule reprise, sur une connexion neuve. Nouveaux essais comptes globalement (S19) et plafonnes
    // (contre la tempete d'essais) : max(3, max_upstream_connections / 5) en cours a la fois.
    bool retry_on_fresh(Connection& c) {
        if (!c.relay.reused || c.relay.response_byte || c.relay.retried) return false;
        drop_upstream_socket(c);
        if (!reserve_retry(c)) return false;
        c.relay.retried = true;
        c.relay.reused = false;
        server.upstream_retries_.fetch_add(1, std::memory_order_relaxed);
        connect_fresh(c);
        return true;
    }

    // Echec d'une tentative. Tete deja envoyee : coupure (C4). Sinon : connexion du pool morte -> connexion neuve, sans
    // compter d'echec ; puis echec compte pour la sante, autre backend si permis, sinon 502 (504 : delai apres envoi).
    void attempt_failed(Connection& c, int status, bool timeout) {
        if (c.websocket) {  // lot 10 : HttpProxyConnectionError - echec compte, aucun nouvel essai, 502
            record_attempt_failure(c, 502);
            finish_upstream(c, error_response(502));
            return;
        }
        if (c.relay.head_sent) {
            record_attempt_failure(c, status);
            relay_cut(c, timeout ? "reverse proxy natif : réponse de " + upstream_of(c).host + ":" +
                                       std::to_string(upstream_of(c).port) +
                                       " interrompue pendant le relais (délai de lecture dépassé)"
                                 : std::string("reverse proxy natif : connexion au backend perdue pendant le relais"));
            return;
        }
        if (retry_on_fresh(c)) return;
        record_attempt_failure(c, status);
        if (retry_other_backend(c)) return;
        finish_upstream(c, error_response(status));
    }

    void upstream_failed(Connection& c, int status) { attempt_failed(c, status, false); }

    void on_upstream_event(Connection& c, std::uint32_t events) {
        if (c.phase == Phase::tunnel) {
            tunnel_backend_event(c, events);
            return;
        }
        if (c.phase != Phase::upstream || c.up_fd < 0) return;
        if (c.up_phase == UpstreamPhase::connecting) {
            int error = 0;
            socklen_t length = sizeof error;
            if (::getsockopt(c.up_fd, SOL_SOCKET, SO_ERROR, &error, &length) != 0 || error != 0) {
                upstream_failed(c, 502);
                return;
            }
            if (upstream_of(c).tls) {
                if (!begin_upstream_tls(c)) return;
            } else {
                c.up_phase = UpstreamPhase::sending;
                arm_upstream_deadline(c, zone_of(c).read_timeout_ms);
            }
        }
        if (c.up_phase == UpstreamPhase::handshaking && !continue_upstream_tls(c)) return;
        if (c.up_phase == UpstreamPhase::sending) {
            while (c.up_out_offset < c.up_out.size()) {
                std::size_t sent = 0;
                const Io status = up_write(c, c.up_out.data() + c.up_out_offset, c.up_out.size() - c.up_out_offset, sent);
                if (status == Io::done) {
                    c.up_out_offset += sent;
                    arm_upstream_deadline(c, zone_of(c).read_timeout_ms);
                    continue;
                }
                if (status == Io::want_write) {
                    set_upstream_events(c, EPOLLOUT);
                    return;
                }
                if (status == Io::want_read) {  // TLS : message du backend a lire avant de pouvoir ecrire
                    set_upstream_events(c, EPOLLIN);
                    return;
                }
                upstream_failed(c, 502);
                return;
            }
            if (!replayable(c.head.method) || c.websocket) std::string().swap(c.up_out);  // nouvel essai seulement
            c.up_sent = true;
            c.up_phase = UpstreamPhase::reading;
            set_upstream_reading(c, true);
            arm_upstream_deadline(c, zone_of(c).read_timeout_ms);
            return;
        }
        read_upstream(c);
    }

    void set_upstream_events(Connection& c, std::uint32_t events) { set_upstream_mask(c, events); }

    // Lot 11 : surveillance par niveau deja posee -> aucun appel (une surveillance par front est toujours reposee :
    // la reposer re-signale un etat deja present).
    void set_upstream_mask(Connection& c, std::uint32_t events) {
        if (c.up_events == events && (events & EPOLLET) == 0) return;
        epoll_event event{};
        event.events = events;
        event.data.fd = c.up_fd;
        ::epoll_ctl(epoll_fd, EPOLL_CTL_MOD, c.up_fd, &event);
        c.up_events = events;
    }

    // ---- lot 8 (C15) : TLS vers le backend. Poignee de main bornee par connect_timeout_seconds, comme
    // asyncio.wait_for(open_connection(ssl=...)) : le delai de connexion court jusqu'a la fin de la poignee de main.
    bool begin_upstream_tls(Connection& c) {
        const ProxyUpstream& upstream = upstream_of(c);
        const bool verify = zone_of(c).verify_tls;
        std::string error;
        SSL_CTX* context = server.upstream_tls_context(verify, &error);
        if (context == nullptr) {
            log_error(c, "reverse proxy natif : " + error, c.request.request_id);
            upstream_failed(c, 502);
            return false;
        }
        c.up_ssl = new_upstream_tls(context, c.up_fd, upstream.host, verify);
        if (c.up_ssl == nullptr) {
            upstream_failed(c, 502);
            return false;
        }
        c.up_phase = UpstreamPhase::handshaking;
        return true;
    }

    // false : en attente (interet pose) ou echec deja traite ; true : poignee de main finie, envoi de la requete.
    bool continue_upstream_tls(Connection& c) {
        ERR_clear_error();
        const int result = SSL_connect(c.up_ssl);
        if (result == 1) {
            c.up_phase = UpstreamPhase::sending;
            set_upstream_events(c, EPOLLOUT);
            arm_upstream_deadline(c, zone_of(c).read_timeout_ms);
            return true;
        }
        const int error = SSL_get_error(c.up_ssl, result);
        if (error == SSL_ERROR_WANT_READ || error == SSL_ERROR_WANT_WRITE) {
            ERR_clear_error();
            set_upstream_events(c, error == SSL_ERROR_WANT_READ ? EPOLLIN : EPOLLOUT);
            return false;
        }
        if (error == SSL_ERROR_SSL) {
            bool certificate = false;
            const std::string reason = upstream_tls_failure(c.up_ssl, upstream_of(c).host, &certificate);
            if (!reason.empty()) log_tls_failure(c, reason, certificate);
        }
        ERR_clear_error();
        upstream_failed(c, 502);  // connexion impossible : echec de sante, autre backend si permis (comme Python)
        return false;
    }

    // serve_proxy.log_tls_failure : au plus une ligne par backend et par minute, tous fils confondus, meme texte.
    void log_tls_failure(const Connection& c, const std::string& reason, bool certificate) {
        const ProxyUpstream& upstream = upstream_of(c);
        const std::string key = upstream.host + ":" + std::to_string(upstream.port);
        if (!server.tls_failure_due(key, Clock::now())) return;
        log_error(c, certificate ? "reverse proxy : certificat de " + key + " refusé : " + reason
                                 : "reverse proxy : poignée de main TLS avec " + key + " impossible : " + reason,
                  c.request.request_id);
    }

    Io up_write(Connection& c, const char* data, std::size_t size, std::size_t& sent) {
        sent = 0;
        if (c.up_ssl == nullptr) {
            while (true) {
                const ssize_t n = ::send(c.up_fd, data, size, MSG_NOSIGNAL);
                if (n > 0) {
                    sent = static_cast<std::size_t>(n);
                    return Io::done;
                }
                if (n < 0 && errno == EINTR) continue;
                if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return Io::want_write;
                return Io::failed;
            }
        }
        ERR_clear_error();
        if (SSL_write_ex(c.up_ssl, data, size, &sent) == 1) return Io::done;
        const int error = SSL_get_error(c.up_ssl, 0);
        ERR_clear_error();
        if (error == SSL_ERROR_WANT_WRITE) return Io::want_write;
        if (error == SSL_ERROR_WANT_READ) return Io::want_read;
        return Io::failed;
    }

    // Io::eof : fin de flux, close_notify du backend, ou fermeture sans close_notify (asyncio la traite en fin de flux).
    Io up_read(Connection& c, char* buffer, std::size_t size, std::size_t& got) {
        got = 0;
        if (c.up_ssl == nullptr) {
            while (true) {
                const ssize_t n = ::recv(c.up_fd, buffer, size, 0);
                if (n > 0) {
                    got = static_cast<std::size_t>(n);
                    return Io::done;
                }
                if (n == 0) return Io::eof;
                if (errno == EINTR) continue;
                if (errno == EAGAIN || errno == EWOULDBLOCK) return Io::want_read;
                return Io::failed;
            }
        }
        ERR_clear_error();
        if (SSL_read_ex(c.up_ssl, buffer, size, &got) == 1) return Io::done;
        const int error = SSL_get_error(c.up_ssl, 0);
        const unsigned long code = ERR_peek_last_error();
        ERR_clear_error();
        switch (error) {
            case SSL_ERROR_WANT_READ: return Io::want_read;
            case SSL_ERROR_WANT_WRITE: return Io::want_write;
            case SSL_ERROR_ZERO_RETURN: return Io::eof;
            case SSL_ERROR_SYSCALL: return errno == 0 ? Io::eof : Io::failed;
            case SSL_ERROR_SSL:
                return ERR_GET_LIB(code) == ERR_LIB_SSL && ERR_GET_REASON(code) == SSL_R_UNEXPECTED_EOF_WHILE_READING
                           ? Io::eof : Io::failed;
            default: return Io::failed;
        }
    }

    // Lecture du backend surveillee (par niveau) ou suspendue : en pause, seuls la fin de flux et les erreurs sont
    // signalees, une fois (par front) - jamais une boucle a vide (S21).
    void set_upstream_reading(Connection& c, bool reading) {
        set_upstream_mask(c, reading ? static_cast<std::uint32_t>(EPOLLIN | EPOLLRDHUP)
                                     : static_cast<std::uint32_t>(EPOLLRDHUP | EPOLLET));
    }

    [[nodiscard]] static std::size_t pending_out(const Connection& c) { return c.out.size() - c.out_offset; }

    void read_upstream(Connection& c) {
        if (c.relay.paused || c.relay.done || c.up_fd < 0) return;
        if (c.up_want_write) {  // lot 8 : l'ecriture TLS attendue est possible, retour a la lecture
            c.up_want_write = false;
            set_upstream_reading(c, true);
        }
        char buffer[65536];
        bool progress = false;
        while (!c.up_eof) {
            if (c.relay.head_sent && pending_out(c) >= kRelayHigh) {  // C12 : client lent, backend en pause
                c.relay.paused = true;
                c.relay.deadline_armed = false;  // le delai d'ecriture vers le client prend le relais
                set_upstream_reading(c, false);
                break;
            }
            if (!c.relay.head_parsed && c.up_in.size() > kHeadReadCap) break;  // l'analyse de la tete tranche
            std::size_t got = 0;
            const Io status = up_read(c, buffer, sizeof buffer, got);
            if (status == Io::done) {
                c.relay.response_byte = true;
                c.up_in.append(buffer, got);
                progress = true;
                if (!advance(c)) return;
                if (c.relay.head_sent && !relay_flush(c)) return;
                if (c.relay.done || c.phase != Phase::upstream) return;
                continue;
            }
            if (status == Io::eof) {
                c.up_eof = true;
                break;
            }
            if (status == Io::want_read) break;
            if (status == Io::want_write) {  // TLS : le backend attend une ecriture avant de livrer la suite
                c.up_want_write = true;
                set_upstream_events(c, EPOLLOUT | EPOLLRDHUP);
                break;
            }
            upstream_failed(c, 502);  // RST : erreur de communication
            return;
        }
        if (progress && !c.relay.paused) arm_upstream_deadline(c, zone_of(c).read_timeout_ms);  // C11 : entre deux blocs
        if (c.up_eof) {
            if (!advance(c)) return;
            if (c.relay.head_sent) relay_flush(c);
        }
    }

    // Traite les octets recus du backend (tete, puis corps) ; false : la requete est terminee (connexion servie,
    // coupee ou fermee) - plus rien a faire ici.
    bool advance(Connection& c) {
        if (c.websocket) return advance_upgrade(c);
        Connection::Relay& relay = c.relay;
        if (!relay.head_parsed) {
            if (c.up_eof && c.up_in.empty()) {  // backend ferme sans repondre
                upstream_failed(c, 502);
                return false;
            }
            UpstreamHead head = parse_upstream_head(c.up_in, latin1_to_utf8(c.head.method), c.up_eof);
            if (head.state == UpstreamHead::State::need_more) return true;
            if (head.state == UpstreamHead::State::error) {  // reponse invalide : echec du backend (502)
                attempt_failed(c, 502, false);
                return false;
            }
            c.up_in.erase(0, head.consumed);
            relay.head_parsed = true;
            relay.framing = head.framing;
            relay.remaining = head.content_length;
            relay.reusable = head.version == "HTTP/1.1" && !asks_close(head);
            if (relay.framing == UpstreamFraming::length && relay.remaining == 0) relay.framing = UpstreamFraming::none;
            relay.head = std::move(head);
            std::string().swap(c.up_out);
            server.proxy_relayed_.fetch_add(1, std::memory_order_relaxed);
            if (relay.framing == UpstreamFraming::none) return complete_relay(c);
            // C7 : page d'erreur decidee avant l'envoi de la tete. Avec une longueur annoncee non nulle, ou un statut
            // sous 400, aucune substitution : la tete part tout de suite. Sinon (chunked ou fin par la fermeture, 4xx
            // ou 5xx) : tete retenue jusqu'au premier octet du corps - un corps vide recoit la page d'erreur.
            if (relay.framing == UpstreamFraming::length || relay.head.status < 400) {
                if (!begin_stream(c)) return false;
            }
        }
        if (relay.framing == UpstreamFraming::length) {
            const std::size_t take = static_cast<std::size_t>(std::min<std::uint64_t>(relay.remaining, c.up_in.size()));
            if (!queue_body(c, std::string_view(c.up_in).substr(0, take))) return false;
            c.up_in.erase(0, take);
            relay.remaining -= take;
            if (relay.remaining == 0) return complete_relay(c);
            if (c.up_eof) return relay_broken(c, "reponse incomplete (connexion fermee)");  // IncompleteReadError
            return true;
        }
        if (relay.framing == UpstreamFraming::chunked) {
            std::string decoded;
            const std::size_t consumed = relay.chunked.feed(c.up_in, decoded);
            c.up_in.erase(0, consumed);
            if (!queue_body(c, decoded)) return false;
            if (relay.chunked.failed()) return relay_broken(c, relay.chunked.error());
            if (relay.chunked.done()) return complete_relay(c);
            if (c.up_eof) {
                relay.chunked.finish_at_eof();
                return relay_broken(c, relay.chunked.error());
            }
            return true;
        }
        // Fin par la fermeture (S13) : bornee par max_response_body_mb (D23), jamais recyclee.
        const std::uint64_t limit = c.snapshot->proxy->max_response_body_bytes;
        const std::uint64_t room = limit > relay.body_relayed ? limit - relay.body_relayed : 0;
        const bool over = c.up_in.size() > room;
        const std::string_view data = std::string_view(c.up_in).substr(0, over ? static_cast<std::size_t>(room) : c.up_in.size());
        if (!queue_body(c, data)) return false;
        c.up_in.clear();
        if (over) {
            const ProxyUpstream& upstream = upstream_of(c);
            log_error(c, "reverse proxy : réponse de " + upstream.host + ":" + std::to_string(upstream.port) +
                             " coupée : corps de réponse au-delà de " + std::to_string(limit) +
                             " octets (max_response_body_mb)",
                      c.request.request_id);
            return relay_broken(c, "");
        }
        if (c.up_eof) return complete_relay(c);
        return true;
    }

    // Tete envoyee au client : en-tetes du backend (serve_proxy), X-Omega-Cache, en-tetes de securite, journal a la fin.
    bool begin_stream(Connection& c) {
        if (abandon_due(c, Clock::now())) {  // P3 : verification de 250 ms deja passee, client parti
            abandon_upstream(c);
            return false;
        }
        Connection::Relay& relay = c.relay;
        const std::string method = latin1_to_utf8(c.head.method);
        Response response = relayed_response(relay.head, std::string(), method);
        if (relay.framing == UpstreamFraming::length) {
            response.stream = Response::Stream::length;
            response.stream_length = relay.remaining;
        } else {
            response.stream = c.head.http_version == "HTTP/1.1" ? Response::Stream::chunked : Response::Stream::close;
        }
        relay.client = response.stream;
        add_sticky_cookie(c, response);
        response.headers.replace("X-Omega-Cache", "BYPASS");
        apply_security_headers(response, *c.snapshot, c.request.path_text);
        c.requests_served += 1;
        server.requests_served_.fetch_add(1, std::memory_order_relaxed);
        const bool keep_alive = keep_alive_for(c, true) && response.stream != Response::Stream::close;
        auto head = finalize_response(*c.snapshot, response, keep_alive);
        if (!head) {
            close_connection(c);  // UnicodeEncodeError cote Python : ni reponse ni journal
            return false;
        }
        c.write_mark = tcp_bytes_acked(c.fd);
        c.head_size = head->size();
        c.response = std::move(response);
        c.keep_alive_after_write = keep_alive;
        c.log_access_after_write = true;
        c.log_access_even_if_write_fails = false;
        c.out = std::move(*head);
        c.out_offset = 0;
        relay.head_sent = true;
        // Client : ecriture (par front, toujours jusqu'a EAGAIN) et depart, jamais la lecture (S21). Lot 11 : deja en
        // place si la surveillance est suspendue (pause_interest pose le meme masque).
        if (!c.interest_paused) {
            epoll_event event{};
            event.events = kPausedEvents;
            event.data.fd = c.fd;
            ::epoll_ctl(epoll_fd, EPOLL_CTL_MOD, c.fd, &event);
        }
        c.interest_paused = true;  // set_write_interest retablira la surveillance normale apres la reponse
        arm_write_deadline(c);
        return true;
    }

    // Corps vers le client, redecoupe si besoin ; false : connexion terminee.
    bool queue_body(Connection& c, std::string_view data) {
        if (data.empty()) return true;
        Connection::Relay& relay = c.relay;
        if (!relay.head_sent && !begin_stream(c)) return false;  // premier octet d'une reponse 4xx/5xx retenue
        if (pending_out(c) == 0) arm_write_deadline(c);
        if (relay.client == Response::Stream::chunked) {
            char header[24];
            const int length = std::snprintf(header, sizeof header, "%zx\r\n", data.size());
            if (relay.marks.size() >= kMaxChunkMarks) relay.marks.pop_front();
            relay.marks.push_back(Connection::Relay::ChunkMark{relay.wire_queued, static_cast<std::uint64_t>(length),
                                                               data.size(), relay.body_relayed});
            c.out.append(header, static_cast<std::size_t>(length));
            c.out.append(data);
            c.out.append("\r\n");
            relay.wire_queued += static_cast<std::uint64_t>(length) + data.size() + 2;
        } else {
            c.out.append(data);
            relay.wire_queued += data.size();
        }
        relay.body_relayed += data.size();
        return true;
    }

    // Reponse du backend finie exactement.
    bool complete_relay(Connection& c) {
        Connection::Relay& relay = c.relay;
        relay.done = true;
        relay.deadline_armed = false;
        record_attempt_success(c);
        if (!relay.head_sent) {
            // Rien parti : reponse sans corps (HEAD, 204, 304, longueur nulle), ou 4xx/5xx au corps vide - servie
            // comme la reponse de serve_proxy (page d'erreur, Content-Length), identique au moteur Python.
            Response response = relayed_response(relay.head, std::string(), latin1_to_utf8(c.head.method));
            add_sticky_cookie(c, response);
            recycle_or_close(c);
            finish_upstream(c, std::move(response));
            return false;
        }
        if (relay.client == Response::Stream::chunked) {
            if (pending_out(c) == 0) arm_write_deadline(c);
            c.out.append("0\r\n\r\n");  // trailers retires (§2.1 point 3)
            relay.wire_queued += 5;
        }
        recycle_or_close(c);
        return relay_flush(c);
    }

    // Erreur du backend apres l'envoi de la tete (C4) : la reponse n'est jamais remplacee - ce qui est deja en file
    // part, puis la connexion du client est fermee sans fin de reponse (ni bloc final ni longueur atteinte).
    bool relay_broken(Connection& c, const std::string& why) {
        if (why.empty()) {
            // Depassement de max_response_body_mb : le backend repond, ce n'est pas une panne (comme Python, D23).
            if (c.relay.backend_held) {
                record_response_time(*c.relay.backend,
                                     std::chrono::duration<double>(Clock::now() - c.relay.attempt_started).count());
                c.relay.backend->errors_502.fetch_add(1, std::memory_order_relaxed);  // comme Python : refusee (502)
            }
            release_backend_of(c);
        } else {
            record_attempt_failure(c, 502);
        }
        if (!c.relay.head_sent) {  // 4xx/5xx retenue sans le moindre octet : 502, comme Python
            finish_upstream(c, error_response(502));
            return false;
        }
        if (!why.empty()) {
            const ProxyUpstream& upstream = upstream_of(c);
            log_error(c, "reverse proxy natif : réponse de " + upstream.host + ":" + std::to_string(upstream.port) +
                             " interrompue pendant le relais (" + why + ")",
                      c.request.request_id);
        }
        c.relay.done = true;
        c.relay.deadline_armed = false;
        c.keep_alive_after_write = false;
        close_upstream(c);
        return relay_flush(c);
    }

    void relay_cut(Connection& c, const std::string& why) {
        log_error(c, why, c.request.request_id);
        c.relay.done = true;
        c.relay.deadline_armed = false;
        c.keep_alive_after_write = false;
        close_upstream(c);
        relay_flush(c);
    }

    // Envoi vers le client ; false : connexion terminee (reponse finie ou envoi impossible).
    bool relay_flush(Connection& c) {
        while (c.out_offset < c.out.size()) {
            std::size_t sent = 0;
            const Io status = io_write(c, c.out.data() + c.out_offset, c.out.size() - c.out_offset, sent);
            if (status == Io::done) {
                c.out_offset += sent;
                if (sent > 0) arm_write_deadline(c);
                continue;
            }
            // EPOLLOUT par front. TLS direct (lot 9) : SSL_write ne demande une lecture que pour une renegociation,
            // refusee par OpenSSL >= 3 cote serveur (SSL_OP_ALLOW_CLIENT_RENEGOTIATION absent) ; sinon le delai
            // d'ecriture coupe la reponse, jamais de boucle.
            if (status == Io::want_write || status == Io::want_read) break;
            relay_client_failed(c);
            return false;
        }
        if (c.out_offset >= c.out.size()) {
            c.out.clear();
            c.out_offset = 0;
            c.has_deadline = false;  // rien en attente : seul le delai du backend court
        } else if (c.out_offset >= kRelayLow) {
            c.out.erase(0, c.out_offset);
            c.out_offset = 0;
        }
        if (c.relay.paused && pending_out(c) <= kRelayLow && c.up_fd >= 0) {  // C12 : reprise (evenement par niveau)
            c.relay.paused = false;
            set_upstream_reading(c, true);
            arm_upstream_deadline(c, zone_of(c).read_timeout_ms);
            // Lot 8 : donnees deja dechiffrees par OpenSSL, que epoll ne signalera pas - lues a la fin du tour de boucle.
            if (c.up_ssl != nullptr && SSL_has_pending(c.up_ssl) == 1) tls_pending_reads.push_back(c.fd);
        }
        if (c.relay.done && c.out.empty()) {
            relay_finished(c);
            return false;
        }
        return true;
    }

    // P2 : octets du corps parmi les octets acquittes par le client (decoupage chunked retire).
    static std::uint64_t body_bytes_sent(const Connection& c, std::uint64_t wire) {
        const Connection::Relay& relay = c.relay;
        if (relay.client != Response::Stream::chunked) return std::min(wire, relay.body_relayed);
        std::uint64_t body = relay.marks.empty() ? 0 : relay.marks.front().body_start;
        for (const auto& mark : relay.marks) {
            if (wire < mark.wire_start + mark.header) return mark.body_start;
            if (wire < mark.wire_start + mark.header + mark.data) return mark.body_start + (wire - mark.wire_start - mark.header);
            body = mark.body_start + mark.data;
        }
        return body;
    }

    // Client parti, ou rien d'envoye pendant write_timeout_seconds, apres l'envoi de la tete (P3) : statut reellement
    // envoye et octets du corps acquittes par le client, comme write_failed.
    void relay_client_failed(Connection& c) {
        const auto acked = tcp_bytes_acked(c.fd);
        std::uint64_t wire = 0;
        if (c.write_mark && acked && *acked > *c.write_mark + c.head_size) wire = *acked - *c.write_mark - c.head_size;
        write_access_line(c, body_bytes_sent(c, wire));
        close_connection(c);
    }

    void relay_finished(Connection& c) {
        const std::uint64_t size = c.relay.body_relayed;
        release_proxy(c);
        write_access_line(c, size);
        c.response = Response{};
        std::string().swap(c.out);
        c.out_offset = 0;
        c.relay = Connection::Relay{};
        if (c.keep_alive_after_write && !server.stopping_.load()) set_write_interest(c, false);  // lecture, depart
        next_request(c);
    }

    // Fin du relais avant l'envoi de la tete : reponse servie comme celle de route_request (respond).
    void finish_upstream(Connection& c, Response response) {
        if (c.websocket) {  // lot 10 : _write_status_line_and_headers(writer, statut, ()) - ni page ni en-tetes
            const int status = response.status;
            write_upgrade_answer(c, upgrade_response_head(status, reason_of(c, status), {}), status);
            return;
        }
        if (abandon_due(c, Clock::now())) {  // P3 : verification de 250 ms deja passee, client parti
            abandon_upstream(c);
            return;
        }
        release_proxy(c);
        c.relay = Connection::Relay{};
        // serve_proxy : zone sans cache (toute zone native, Q6) -> X-Omega-Cache: BYPASS, erreurs comprises.
        response.headers.replace("X-Omega-Cache", "BYPASS");
        respond(c, std::move(response), true);
    }

    void upstream_timed_out(Connection& c) {
        // Python : delai depasse apres l'envoi -> 504 (HttpProxyTimeoutError) ; avant (connexion, envoi) -> 502.
        attempt_failed(c, c.up_sent ? 504 : 502, true);
    }

    // serve_proxy : cookie collant du backend qui a reellement servi, sans ecraser ceux du backend (C6).
    void add_sticky_cookie(const Connection& c, Response& response) const {
        if (auto cookie = sticky_cookie(c)) response.headers.add("Set-Cookie", *cookie);
    }

    std::optional<std::string> sticky_cookie(const Connection& c) const {
        const auto& sticky = zone_of(c).sticky;
        if (!sticky) return std::nullopt;
        return sticky->cookie_name + "=" + upstream_of(c).cookie + "; Max-Age=" + std::to_string(sticky->max_age_seconds) +
               "; Path=/; SameSite=Lax; Secure; HttpOnly";
    }

    // P3 (regle nginx) : client parti pendant le relais. Rien d'envoye : requete vers le backend annulee, ligne 499.
    // Tete deja envoyee : statut reellement envoye et octets partiels (C10).
    void abandon_upstream(Connection& c) {
        if (c.relay.head_sent) {
            relay_client_failed(c);
            return;
        }
        release_proxy(c);
        c.response = Response{};
        c.response.status = 499;
        write_access_line(c);
        close_connection(c);
    }

    // ------------------------------------------------------------------------------ WebSocket (proxy natif, lot 10)
    // C17 : copie de serve_websocket_proxy. Poignee de main : connexion neuve (jamais le pool), aucun nouvel essai,
    // 502/503 nus (_write_status_line_and_headers), temps de reponse = poignee de main seule, reservation du backend
    // gardee pendant tout le tunnel (acquire/release). Apres le 101 : octets relayes tels quels ; un cote qui ferme (ou
    // qui echoue) arrete les lectures, ce qui est en file part, puis tout est ferme. Delai d'inactivite (Q11) et fin du
    // delai de grace (C14) : trame 1001 dans chaque sens ou elle tombe entre deux trames (decision du 2026-11-14).
    // Journal : 101 et octets du backend envoyes au client, a la fermeture du tunnel.
    static constexpr auto kTunnelCloseWithoutProgress = std::chrono::seconds(2);  // _CLOSE_FLUSH_SECONDS (Python)

    static std::string reason_of(const Connection& c, int status) {
        const auto found = c.snapshot->reason_phrases.find(status);
        return found == c.snapshot->reason_phrases.end() ? std::string() : found->second;
    }

    // Reponse ecrite telle quelle (aucun en-tete du serveur), puis fermeture ; ligne d'acces meme si l'envoi echoue.
    void write_upgrade_answer(Connection& c, std::string head, int status) {
        release_proxy(c);
        c.relay = Connection::Relay{};
        c.requests_served += 1;
        server.requests_served_.fetch_add(1, std::memory_order_relaxed);
        c.response = Response{};
        c.response.status = status;
        c.file_path.clear();
        c.file_offset = 0;
        c.file_remaining = 0;
        c.write_mark = std::nullopt;
        c.head_size = head.size();
        c.out = std::move(head);
        c.out_offset = 0;
        c.log_access_after_write = true;
        c.log_access_even_if_write_fails = true;
        c.keep_alive_after_write = false;
        c.phase = Phase::write;
        arm_write_deadline(c);
        on_writable(c);
    }

    // Tete de la reponse du backend a la mise a niveau ; false : requete terminee ici.
    bool advance_upgrade(Connection& c) {
        if (c.up_eof && c.up_in.empty()) {  // « upstream a ferme la connexion sans reponse »
            attempt_failed(c, 502, false);
            return false;
        }
        const UpstreamHead head = parse_upstream_head(c.up_in, "GET", c.up_eof, true);
        if (head.state == UpstreamHead::State::need_more) return true;
        if (head.state == UpstreamHead::State::error) {
            attempt_failed(c, 502, false);
            return false;
        }
        c.up_in.erase(0, head.consumed);
        c.relay.head_parsed = true;
        c.relay.deadline_armed = false;
        if (c.relay.backend_held) {  // record_response_time + record_success, reservation gardee
            record_response_time(*c.relay.backend,
                                 std::chrono::duration<double>(Clock::now() - c.relay.attempt_started).count());
            record_backend_success(*c.relay.backend, zone_of(c).healthy_after);
        }
        server.proxy_relayed_.fetch_add(1, std::memory_order_relaxed);
        if (head.status != 101) {  // refus : sans son corps (D14)
            write_upgrade_answer(c, upgrade_response_head(head.status, reason_of(c, head.status), head.headers),
                                 head.status);
            return false;
        }
        begin_tunnel(c, head);
        return false;
    }

    void begin_tunnel(Connection& c, const UpstreamHead& head) {
        std::optional<std::string> cookie;
        if (const auto text = sticky_cookie(c)) cookie = utf8_to_latin1(*text);
        std::string answer = upgrade_response_head(101, reason_of(c, 101), head.headers, cookie ? &*cookie : nullptr);
        c.phase = Phase::tunnel;
        c.requests_served += 1;
        server.requests_served_.fetch_add(1, std::memory_order_relaxed);
        c.response = Response{};
        c.response.status = 101;
        c.has_deadline = false;
        c.interest_paused = false;
        c.up_want_write = false;
        c.tunnel = Connection::Tunnel{};
        c.tunnel.idle_ms = zone_of(c).websocket_idle_timeout_ms;
        touch_tunnel(c);
        c.out = std::move(answer);
        c.out_offset = 0;
        std::string().swap(c.up_out);
        c.up_out_offset = 0;
        if (!c.up_in.empty()) {  // octets du backend arrives avec le 101
            queue_to_client(c, c.up_in);
            std::string().swap(c.up_in);
        }
        if (!c.in.empty()) {  // octets du client arrives avec la requete
            queue_to_backend(c, c.in);
            std::string().swap(c.in);
        }
        tunnel_pump(c);
    }

    [[nodiscard]] static std::size_t up_pending(const Connection& c) { return c.up_out.size() - c.up_out_offset; }

    static void touch_tunnel(Connection& c) {
        if (c.tunnel.idle_ms > 0) c.tunnel.idle_deadline = Clock::now() + std::chrono::milliseconds(c.tunnel.idle_ms);
    }

    static void queue_to_client(Connection& c, std::string_view data) {
        c.tunnel.to_client.feed(data);
        c.tunnel.bytes_to_client += data.size();
        c.out.append(data);
    }

    static void queue_to_backend(Connection& c, std::string_view data) {
        c.tunnel.to_backend.feed(data);
        c.up_out.append(data);
    }

    static void start_closing(Connection& c) {
        c.tunnel.closing = true;
        c.tunnel.closing_deadline = Clock::now() + kTunnelCloseWithoutProgress;
    }

    void tunnel_client_dead(Connection& c) {
        Connection::Tunnel& t = c.tunnel;
        t.client_dead = true;
        t.client_eof = true;
        std::string().swap(c.out);
        c.out_offset = 0;
        ::epoll_ctl(epoll_fd, EPOLL_CTL_DEL, c.fd, nullptr);
        if (!t.closing) start_closing(c);
    }

    void tunnel_backend_dead(Connection& c) {
        Connection::Tunnel& t = c.tunnel;
        t.backend_dead = true;
        t.backend_eof = true;
        drop_upstream_socket(c);
        std::string().swap(c.up_out);
        c.up_out_offset = 0;
        if (!t.closing) start_closing(c);
    }

    bool tunnel_flush_client(Connection& c) {
        Connection::Tunnel& t = c.tunnel;
        bool progress = false;
        while (!t.client_dead && c.out_offset < c.out.size()) {
            std::size_t sent = 0;
            const Io status = io_write(c, c.out.data() + c.out_offset, c.out.size() - c.out_offset, sent);
            if (status == Io::done) {
                c.out_offset += sent;
                t.client_write_wants_read = false;
                progress = true;
                continue;
            }
            if (status == Io::want_write) break;
            if (status == Io::want_read) {
                t.client_write_wants_read = true;
                break;
            }
            tunnel_client_dead(c);
        }
        if (c.out_offset >= c.out.size()) {
            c.out.clear();
            c.out_offset = 0;
        } else if (c.out_offset >= kRelayLow) {
            c.out.erase(0, c.out_offset);
            c.out_offset = 0;
        }
        return progress;
    }

    bool tunnel_flush_backend(Connection& c) {
        Connection::Tunnel& t = c.tunnel;
        bool progress = false;
        while (!t.backend_dead && c.up_fd >= 0 && c.up_out_offset < c.up_out.size()) {
            std::size_t sent = 0;
            const Io status = up_write(c, c.up_out.data() + c.up_out_offset, c.up_out.size() - c.up_out_offset, sent);
            if (status == Io::done) {
                c.up_out_offset += sent;
                t.backend_write_wants_read = false;
                progress = true;
                continue;
            }
            if (status == Io::want_write) break;
            if (status == Io::want_read) {
                t.backend_write_wants_read = true;
                break;
            }
            tunnel_backend_dead(c);
        }
        if (c.up_out_offset >= c.up_out.size()) {
            c.up_out.clear();
            c.up_out_offset = 0;
        } else if (c.up_out_offset >= kRelayLow) {
            c.up_out.erase(0, c.up_out_offset);
            c.up_out_offset = 0;
        }
        return progress;
    }

    bool tunnel_read_client(Connection& c, char* buffer, std::size_t size) {
        Connection::Tunnel& t = c.tunnel;
        bool progress = false;
        while (!t.closing && !t.client_eof && up_pending(c) < kRelayHigh) {
            std::size_t got = 0;
            const Io status = io_read(c, buffer, size, got);
            if (status == Io::done) {
                t.client_read_wants_write = false;
                queue_to_backend(c, std::string_view(buffer, got));
                touch_tunnel(c);
                progress = true;
                continue;
            }
            t.client_read_wants_write = status == Io::want_write;
            if (status == Io::eof) t.client_eof = true;
            else if (status == Io::failed) tunnel_client_dead(c);  // RST : _pump s'arrete comme a la fin du flux
            break;
        }
        return progress;
    }

    bool tunnel_read_backend(Connection& c, char* buffer, std::size_t size) {
        Connection::Tunnel& t = c.tunnel;
        bool progress = false;
        while (!t.closing && !t.backend_eof && c.up_fd >= 0 && pending_out(c) < kRelayHigh) {
            std::size_t got = 0;
            const Io status = up_read(c, buffer, size, got);
            if (status == Io::done) {
                t.backend_read_wants_write = false;
                queue_to_client(c, std::string_view(buffer, got));
                touch_tunnel(c);
                progress = true;
                continue;
            }
            t.backend_read_wants_write = status == Io::want_write;
            if (status == Io::eof) t.backend_eof = true;
            else if (status == Io::failed) tunnel_backend_dead(c);
            break;
        }
        return progress;
    }

    // Tout ce qui peut avancer avance (jamais de surveillance sans traitement, S21) ; fin quand tout est vide.
    void tunnel_pump(Connection& c) {
        char buffer[65536];
        Connection::Tunnel& t = c.tunnel;
        bool progress = true;
        while (progress && c.phase == Phase::tunnel) {
            progress = false;
            if (tunnel_flush_client(c)) progress = true;
            if (tunnel_flush_backend(c)) progress = true;
            if (tunnel_read_client(c, buffer, sizeof buffer)) progress = true;
            if (tunnel_read_backend(c, buffer, sizeof buffer)) progress = true;
            if (!t.closing && (t.client_eof || t.backend_eof)) start_closing(c);
            if (progress && t.closing) t.closing_deadline = Clock::now() + kTunnelCloseWithoutProgress;
        }
        if (c.phase != Phase::tunnel) return;
        const bool client_empty = t.client_dead || pending_out(c) == 0;
        const bool backend_empty = t.backend_dead || c.up_fd < 0 || up_pending(c) == 0;
        if (t.closing && client_empty && backend_empty) {
            tunnel_end(c);
            return;
        }
        tunnel_watch(c);
    }

    // Surveillance par niveau, recalculee apres chaque passage : lecture seulement si elle peut avancer, ecriture
    // seulement s'il reste des octets (TLS : le sens inverse quand OpenSSL le demande).
    void tunnel_watch(Connection& c) {
        Connection::Tunnel& t = c.tunnel;
        if (!t.client_dead) {
            const bool reading = !t.closing && !t.client_eof && up_pending(c) < kRelayHigh;
            const bool writing = pending_out(c) > 0;
            std::uint32_t events = 0;
            if ((reading && !t.client_read_wants_write) || (writing && t.client_write_wants_read)) events |= EPOLLIN;
            if ((writing && !t.client_write_wants_read) || (reading && t.client_read_wants_write)) events |= EPOLLOUT;
            if (events != t.client_events) {
                epoll_event event{};
                event.events = events;
                event.data.fd = c.fd;
                ::epoll_ctl(epoll_fd, EPOLL_CTL_MOD, c.fd, &event);
                t.client_events = events;
            }
        }
        if (!t.backend_dead && c.up_fd >= 0) {
            const bool reading = !t.closing && !t.backend_eof && pending_out(c) < kRelayHigh;
            const bool writing = up_pending(c) > 0;
            std::uint32_t events = 0;
            if ((reading && !t.backend_read_wants_write) || (writing && t.backend_write_wants_read)) events |= EPOLLIN;
            if ((writing && !t.backend_write_wants_read) || (reading && t.backend_read_wants_write)) events |= EPOLLOUT;
            if (events != t.backend_events) {
                epoll_event event{};
                event.events = events;
                event.data.fd = c.up_fd;
                ::epoll_ctl(epoll_fd, EPOLL_CTL_MOD, c.up_fd, &event);
                t.backend_events = events;
                c.up_events = events;
            }
        }
    }

    // EPOLLHUP / EPOLLERR (RST) : signales meme sans surveillance - le cote est perdu, jamais une boucle a vide.
    void tunnel_client_event(Connection& c, std::uint32_t events) {
        if (events & (EPOLLHUP | EPOLLERR)) tunnel_client_dead(c);
        tunnel_pump(c);
    }

    void tunnel_backend_event(Connection& c, std::uint32_t events) {
        if (events & (EPOLLHUP | EPOLLERR)) tunnel_backend_dead(c);
        tunnel_pump(c);
    }

    // Delai d'inactivite, ou fin du delai de grace (`forced` : un seul essai d'envoi, puis fermeture).
    void tunnel_going_away(Connection& c, bool forced) {
        Connection::Tunnel& t = c.tunnel;
        if (!t.closing) {
            if (!t.client_dead && t.to_client.can_send_close()) c.out += close_frame_to_client();
            if (!t.backend_dead && c.up_fd >= 0 && t.to_backend.can_send_close()) {
                std::array<unsigned char, 4> mask{};
                if (RAND_bytes(mask.data(), static_cast<int>(mask.size())) != 1) {
                    std::random_device device;
                    for (unsigned char& byte : mask) byte = static_cast<unsigned char>(device());
                }
                c.up_out += close_frame_to_server(mask);
            }
            start_closing(c);
        }
        if (forced) {
            tunnel_flush_client(c);
            tunnel_flush_backend(c);
            tunnel_end(c);
            return;
        }
        tunnel_pump(c);
    }

    void tunnel_end(Connection& c) {
        if (c.phase != Phase::tunnel) return;
        write_access_line(c, c.tunnel.bytes_to_client);
        release_backend_of(c);  // reservation (C9) : ni succes ni echec
        close_connection(c);    // release_proxy : socket du backend fermee, budget rendu
    }

    // ------------------------------------------------------------------------- administration (proxy natif, lot 3)
    // P6 : le processus de securite n° 0 seul tient la sante des backends ; /.omega-serv-admin/ doit donc l'atteindre,
    // quel que soit le fil qui a accepte la connexion. Le fil i est servi par le processus i % N : un fil d'un autre
    // processus confie la connexion (en clair seulement) au fil 0, qui la traite comme si elle venait d'arriver -
    // controles, INSPECT et routage compris, sur le processus n° 0. Lot 9 : en TLS direct aussi, avec sa session.
    bool admin_belongs_to_first_process(const Connection& c) const {
        const Snapshot& snapshot = *c.snapshot;
        if (!snapshot.inspect || snapshot.inspect->security_processes <= 1) return false;  // TLS : lot 9
        if (index % snapshot.inspect->security_processes == 0) return false;
        const std::string& prefix = snapshot.internal.admin_prefix;
        return !prefix.empty() && c.request.path_text.compare(0, prefix.size(), prefix) == 0;
    }

    void transfer_to_first_worker(Connection& c) {
        Server::Transfer transfer;
        transfer.fd = c.fd;
        transfer.ssl = c.ssl;  // lot 9 : la session suit la connexion (octets dechiffres deja dans c.in)
        c.ssl = nullptr;
        transfer.peer_ip = c.peer_ip;
        transfer.pending = c.raw_head + c.in;
        transfer.requests_served = c.requests_served;
        transfer.eof = c.eof;
        transfer.snapshot = c.snapshot;
        account_traffic(c);  // lot 9b : compte jusqu'ici ; le fil 0 repart de ce que la socket a vu
        ::epoll_ctl(epoll_fd, EPOLL_CTL_DEL, c.fd, nullptr);
        c.fd = -1;          // le descripteur suit la connexion : jamais ferme ici
        c.counted = false;  // compte dans active_connections_ : repris tel quel par le fil 0
        c.phase = Phase::closed;
        {
            std::lock_guard<std::mutex> lock(server.transfer_mutex_);
            server.transfers_.push_back(std::move(transfer));
        }
        const std::uint64_t one = 1;
        (void)!::write(server.transfer_event_fd_, &one, sizeof one);
    }

    void adopt_transfers() {
        std::uint64_t count = 0;
        (void)!::read(server.transfer_event_fd_, &count, sizeof count);
        std::vector<Server::Transfer> transfers;
        {
            std::lock_guard<std::mutex> lock(server.transfer_mutex_);
            transfers.swap(server.transfers_);
        }
        for (Server::Transfer& transfer : transfers) {
            auto c = std::make_unique<Connection>();
            c->fd = transfer.fd;
            c->ssl = transfer.ssl;  // lot 9 : TLS direct, poignee de main deja faite par le fil d'origine
            c->handshake_done = c->ssl != nullptr;
            transfer.ssl = nullptr;
            if (const auto seen = socket_traffic(c->fd)) std::tie(c->traffic_in, c->traffic_out) = *seen;  // lot 9b
            c->peer_ip = std::move(transfer.peer_ip);
            c->snapshot = std::move(transfer.snapshot);
            c->in = std::move(transfer.pending);
            c->requests_served = transfer.requests_served;
            c->eof = transfer.eof;
            c->counted = true;
            epoll_event event{};
            event.events = EPOLLIN | EPOLLRDHUP;
            event.data.fd = c->fd;
            if (::epoll_ctl(epoll_fd, EPOLL_CTL_ADD, c->fd, &event) != 0) {
                server.active_connections_.fetch_sub(1);
                continue;  // ~Connection ferme le fd
            }
            c->phase_timeout = c->requests_served == 0 ? c->snapshot->server.read_timeout_seconds
                                                       : c->snapshot->server.keepalive_timeout_seconds;
            c->deadline = after_seconds(c->snapshot->server.read_timeout_seconds);  // tete deja la : delai de lecture
            c->has_deadline = true;
            Connection& adopted = *c;
            connections[adopted.fd] = std::move(c);
            on_readable(adopted);
        }
    }

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
        if (admin_belongs_to_first_process(c)) {  // plan proxy natif v2, lot 3 (P6)
            transfer_to_first_worker(c);
            return false;
        }
        if (wants_handoff(snapshot, c.request)) {  // lot 6 : reverse proxy, FastCGI, envoi de fichiers -> Python
            hand_off(c);
            return false;
        }
        // Lot 10 : mise a niveau WebSocket - zone choisie parmi les zones `websocket` seulement (asyncio_server).
        c.websocket = false;
        std::string websocket_path;
        int websocket_zone = -1;
        if (is_websocket_upgrade(c.request)) {
            websocket_zone = websocket_proxy_zone(snapshot, c.request, &websocket_path);
            if (websocket_zone >= 0 && !snapshot.proxy->zones[static_cast<std::size_t>(websocket_zone)].native) {
                hand_off(c);  // zone confiee : le tunnel reste en Python
                return false;
            }
            c.websocket = websocket_zone >= 0;
        }
        const BodyFraming framing = body_framing(c.head, snapshot.server.max_request_size);
        if (framing.status != 0) {
            log_error(c, "erreur de corps de requete : " + framing.reason, c.request.request_id);
            begin_error_response(c, framing.status);
            return false;
        }
        if (snapshot.inspect && snapshot.inspect->body_reject_over &&
            framing.content_length > *snapshot.inspect->body_reject_over) {
            // Lot 2 : waf.inspect.body_over_limit = reject - meme refus que read_and_discard_body (Python).
            const std::string method = latin1_to_utf8(c.head.method);
            bool inspected_method = false;
            for (const std::string& allowed : snapshot.inspect->body_methods) inspected_method = inspected_method || allowed == method;
            if (inspected_method) {
                log_error(c, "erreur de corps de requete : corps plus grand que la partie inspectée par le WAF "
                             "(waf.inspect.body_over_limit = reject)", c.request.request_id);
                begin_error_response(c, 413);
                return false;
            }
        }
        // Plan proxy natif v2, lot 4 : zone relayee par le natif - corps garde en entier (C2), dans le budget global.
        release_proxy(c);  // requete precedente de la connexion (keep-alive) : rien ne reste reserve
        c.body_full.clear();
        c.client_gone = false;
        c.effective_path.clear();
        c.proxy_zone = native_proxy_zone(snapshot, c.request, &c.effective_path);
        if (c.websocket) {
            c.proxy_zone = websocket_zone;
            c.effective_path = std::move(websocket_path);
        }
        if (c.proxy_zone >= 0 && framing.content_length > 0) {
            const std::uint64_t budget = snapshot.proxy->budgets.pending_body_bytes;
            const std::uint64_t before = server.proxy_pending_body_.fetch_add(framing.content_length);
            c.reserved_body = framing.content_length;
            if (before + framing.content_length > budget) {
                release_proxy(c);
                log_error(c, "reverse proxy natif : budget des corps en attente epuise "
                             "(options.reverse_proxy.max_pending_body_mb) - 503", c.request.request_id);
                respond(c, error_response(503), false);
                return false;
            }
            c.body_full.reserve(static_cast<std::size_t>(framing.content_length));
        }
        c.body_remaining = framing.content_length;
        c.body_capture.clear();
        c.capture_body = false;
        if (snapshot.inspect && snapshot.inspect->body_bytes > 0) {
            const std::string method = latin1_to_utf8(c.head.method);
            for (const std::string& allowed : snapshot.inspect->body_methods) c.capture_body = c.capture_body || allowed == method;
        }
        // Plan proxy natif v2, lot 4 (S23, P10 revu) : plus de plafond lie au canal - au-dela de ce qu'une trame
        // porte, le corps capture part par memfd (start_inspection). body_bytes = waf.inspect.body_max_inspect_bytes.
        c.capture_limit = c.capture_body ? snapshot.inspect->body_bytes : 0;
        c.phase = Phase::read_body;
        c.body_started = Clock::now();
        c.body_received = 0;
        c.deadline = after_seconds(c.phase_timeout);  // lot 11 (F1) : relancee par process_body a chaque bloc
        c.has_deadline = true;
        return true;
    }

    bool process_body(Connection& c) {
        const std::uint64_t take = std::min<std::uint64_t>(c.body_remaining, c.in.size());
        if (c.capture_body && c.body_capture.size() < c.capture_limit) {
            const std::uint64_t room = c.capture_limit - c.body_capture.size();
            c.body_capture.append(c.in, 0, static_cast<std::size_t>(std::min<std::uint64_t>(room, take)));
        }
        if (c.proxy_zone >= 0) c.body_full.append(c.in, 0, static_cast<std::size_t>(take));
        c.in.erase(0, static_cast<std::size_t>(take));
        c.body_remaining -= take;
        if (take > 0) {
            c.body_received += take;
            c.deadline = body_deadline(c.body_started, c.body_received, c.phase_timeout);
        }
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
        NativeDecision decision = c.rate_retry > 0 ? NativeDecision::python : native_decision(c);
        // Plan proxy natif v2, lot 4 (C1) : zone qui demande l'INSPECT pour chaque requete (magnet, zone protegee...).
        if (c.proxy_zone >= 0 && decision == NativeDecision::clean &&
            c.snapshot->proxy->zones[static_cast<std::size_t>(c.proxy_zone)].inspect == ZoneInspect::always)
            decision = NativeDecision::python;
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
        // Lot 1N : compte aussi sans canal - le depassement est alors refuse ici (inspection_failed, fail-open).
        if (policy == nullptr) return;
        c.rate_counted = true;
        // Scan de securite n° 2 (2026-11-20, F36) : regle par dossier choisie sur le chemin canonique, comme les
        // autres decisions de securite - « //login » ou « /%6cogin » tombaient dans la limite globale.
        const std::string& rate_path = c.request.match_path_invalid ? c.request.path_text : c.request.match_path;
        if (policy->exempt(c.head.method, rate_path)) return;
        const SelectedRate rate = policy->select(rate_path, c.request.remote_ip);
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
        if (filter->in_protected_zone(c.request.match_path)) return false;  // scan n° 1 : chemin canonique
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
        if (c.proxy_zone >= 0) {  // plan proxy natif v2, lot 4 : verdict obtenu (ou non requis), relais natif
            start_upstream(c);
            return;
        }
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
        start_write(c, std::move(response), keep_alive_for(c, keep_alive_allowed), true);
    }

    // Apres le compte de la requete (requests_served deja incremente).
    bool keep_alive_for(const Connection& c, bool keep_alive_allowed) const {
        const std::string* connection = c.head.header("connection");
        return keep_alive_allowed && !server.stopping_.load() &&  // lot 7 : arret en cours, Connection: close
               c.requests_served < c.snapshot->server.max_keepalive_requests &&
               c.head.http_version == "HTTP/1.1" && !(connection != nullptr && ascii_lower(*connection) == "close");
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
        c.write_mark = tcp_bytes_acked(c.fd);
        c.head_size = head->size();
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
        arm_write_deadline(c);  // lot A (D31) : avant, aucun delai d'ecriture (comme Python, qui l'ignorait aussi)
        on_writable(c);
    }

    // Lot A (D31) : server.write_timeout_seconds = delai SANS PROGRES, comme send_timeout de nginx et le moteur
    // Python (_drain) : rearme a chaque octet envoye ; un client qui ne lit plus rien pendant tout le delai est coupe.
    void arm_write_deadline(Connection& c) {
        c.phase_timeout = c.snapshot->server.write_timeout_seconds;
        c.deadline = after_seconds(c.phase_timeout);
        c.has_deadline = true;
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
                if (sent > 0) arm_write_deadline(c);
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
            write_failed(c);
            return;
        }
        if (c.file_remaining > 0) {
            if (c.file_fd < 0) {
                c.file_fd = ::open(c.file_path.c_str(), O_RDONLY | O_CLOEXEC);
                if (c.file_fd < 0) {
                    log_error(c, "envoi interrompu de " + c.file_path + " : [Errno " + std::to_string(errno) + "] " +
                                     std::strerror(errno) + ": '" + c.file_path + "'", "");
                    write_failed(c);  // lot 1N : ConnectionResetError cote Python, donc ligne d'acces
                    return;
                }
            }
            while (c.file_remaining > 0) {
                off_t offset = static_cast<off_t>(c.file_offset);
                const ssize_t n = ::sendfile(c.fd, c.file_fd, &offset, static_cast<std::size_t>(std::min<std::uint64_t>(c.file_remaining, 1u << 30)));
                if (n > 0) {
                    c.file_offset += static_cast<std::uint64_t>(n);
                    c.file_remaining -= static_cast<std::uint64_t>(n);
                    arm_write_deadline(c);
                    continue;
                }
                if (n < 0 && errno == EINTR) continue;
                if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                    set_write_interest(c, true);
                    return;
                }
                if (n < 0) {
                    write_failed(c);  // lot 1N : pair parti, comme ConnectionResetError cote Python
                } else {
                    close_connection(c);  // fichier tronque entre-temps (n == 0)
                }
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
                write_failed(c);  // lot 1N : comme ci-dessus
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

    void write_access_line(Connection& c, std::optional<std::uint64_t> size = std::nullopt) {
        // Decision de l'auteur du 2026-11-16 (choix a) : un appel accepte a /.omega-serv-admin/ vient de cette machine
        // (TUI, administration web, toutes les 2 s) et n'est jamais ecrit ; refuse (403), il reste ecrit pour omega-jail
        // et RIPOSTE. Meme regle que asyncio_server.py::is_internal_admin_call.
        const std::string& admin = c.snapshot->internal.admin_prefix;
        if (!admin.empty() && c.response.status != 403 && c.request.path_text.compare(0, admin.size(), admin) == 0) {
            return;
        }
        log_for(c.snapshot->access_log).append_line(format_access_line(c.request, c.response, unix_now(), size));
    }

    // `tcpi_bytes_acked` (Linux >= 4.1, octets 120 a 128 de tcp_info, comme _tcp_bytes_acked cote Python).
    static std::optional<std::uint64_t> tcp_bytes_acked(int fd) {
        unsigned char info[256] = {};
        socklen_t size = sizeof info;
        if (::getsockopt(fd, IPPROTO_TCP, TCP_INFO, info, &size) != 0 || size < 128) return std::nullopt;
        std::uint64_t acked = 0;
        std::memcpy(&acked, info + 120, sizeof acked);
        return acked;
    }

    // Envoi interrompu (client parti, ou rien d'envoye pendant write_timeout_seconds). Pages d'erreur : ligne complete,
    // comme _write_error_response ; autres reponses (lot 1N, P3, comme Python depuis le lot 1) : vrai statut et octets
    // du corps acquittes (0 si inconnu). Avant, aucune ligne.
    void write_failed(Connection& c) {
        if (c.log_access_even_if_write_fails) {
            write_access_line(c);
        } else if (c.log_access_after_write) {
            const auto acked = tcp_bytes_acked(c.fd);
            std::uint64_t sent = 0;
            if (c.write_mark && acked && *acked > *c.write_mark + c.head_size) sent = *acked - *c.write_mark - c.head_size;
            write_access_line(c, std::min<std::uint64_t>(sent, c.response.content_length()));
        }
        close_connection(c);
    }

    void finish_write(Connection& c) {
        if (c.log_access_after_write) write_access_line(c);
        c.out.clear();
        c.response = Response{};
        next_request(c);
    }

    // Reponse finie. Plan proxy natif v2, lot 7 (decisions de l'auteur du 2026-11-13) :
    // - arret en cours : plus de keep-alive, la connexion est fermee ;
    // - sinon la requete suivante prend la configuration EN COURS (rechargement compris), comme le moteur Python -
    //   avant, la connexion gardait celle de son ouverture jusqu'a sa fermeture (C20).
    void next_request(Connection& c) {
        if (!c.keep_alive_after_write || server.stopping_.load()) {
            close_connection(c);
            return;
        }
        c.snapshot = server.snapshot();  // contexte TLS tenu par le serveur (son changement demande un redemarrage)
        c.phase = Phase::read_head;
        c.phase_timeout = c.snapshot->server.keepalive_timeout_seconds;
        c.deadline = after_seconds(c.phase_timeout);
        c.has_deadline = true;
        // Scan de securite n° 2 (2026-11-20, F45) : la requete suivante deja recue (pipelining) n'est plus traitee
        // sur la meme pile (start_write -> ... -> next_request -> process -> ... -> start_write) : avec un
        // max_keepalive_requests eleve, des milliers de requetes en pipeline epuisaient la pile du fil. Elle est
        // reprise par la boucle d'evenements (run_pipelined_pending), toujours avant le prochain epoll_wait.
        pipelined_pending.emplace_back(c.fd, &c);
    }

    std::vector<std::pair<int, Connection*>> pipelined_pending;
    void run_pipelined_pending() {
        while (!pipelined_pending.empty()) {
            std::vector<std::pair<int, Connection*>> pending;
            pending.swap(pipelined_pending);
            for (const auto& [fd, expected] : pending) {
                auto it = connections.find(fd);
                if (it == connections.end() || it->second.get() != expected) continue;
                if (expected->phase == Phase::read_head) process(*expected);
            }
        }
    }

    // ------------------------------------------------------------------------------------- delais
    void check_deadlines() {
        const auto now = Clock::now();
        expire_idle(now);  // lot 5 : pool, 60 s d'inactivite
        prune_pool_on_new_generation();  // lot 7 (C13)
        if (++deadline_ticks % 4 == 0) send_backend_state();  // lot 6 (Q7) : environ 1 fois par seconde
        if (deadline_ticks % 8 == 0) {  // lot 9b : connexions longues (telechargements, tunnels) comptees en route
            for (auto& [fd, c] : connections) {
                if (c->phase != Phase::closed) account_traffic(*c);
            }
        }
        for (auto& [fd, c] : connections) {
            if (c->phase == Phase::tunnel) {  // lot 10 : fin de fermeture sans progres, ou delai d'inactivite (Q11)
                const Connection::Tunnel& tunnel = c->tunnel;
                if (tunnel.closing) {
                    if (now >= tunnel.closing_deadline) tunnel_end(*c);
                } else if (tunnel.idle_ms > 0 && now >= tunnel.idle_deadline) {
                    tunnel_going_away(*c, false);
                }
                continue;
            }
            if (c->phase == Phase::upstream) {
                if (abandon_due(*c, now)) {
                    abandon_upstream(*c);  // plan proxy natif v2, lot 4 (P3)
                } else if (c->relay.deadline_armed && now >= c->relay.deadline) {
                    upstream_timed_out(*c);  // lot 5 (C11) : connexion, premier octet, entre deux blocs
                } else if (c->relay.head_sent && c->has_deadline && now >= c->deadline) {
                    relay_client_failed(*c);  // lot 5 (D31) : client qui ne lit plus pendant write_timeout_seconds
                }
                continue;
            }
            if (c->phase == Phase::closed || !c->has_deadline || now < c->deadline) continue;
            if (c->phase == Phase::handshake || c->phase == Phase::read_head) {
                close_connection(*c);  // asyncio.TimeoutError sur la tete (ou poignee de main) : fermeture sans reponse
            } else if (c->phase == Phase::inspect) {
                inspection_failed(*c, "delai depasse");
            } else if (c->phase == Phase::read_body) {
                log_error(*c, "corps de requete trop lent (timeout)", c->request.request_id);
                begin_error_response(*c, 408);
            } else if (c->phase == Phase::write) {
                // Lot A (D31) : rien d'envoye pendant write_timeout_seconds - comme le moteur Python
                // (ConnectionResetError) ; ligne d'acces : voir write_failed (lot 1N).
                write_failed(*c);
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
                close_idle_connections();  // lot 7 : seules les requetes en cours ont le delai de grace
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
                if (fd == server.transfer_event_fd_) {
                    adopt_transfers();
                    continue;
                }
                if (fd == data_fd) {
                    if (events[i].events & EPOLLOUT) flush_data_out();
                    if (events[i].events & (EPOLLIN | EPOLLHUP | EPOLLERR)) on_data_readable();
                    continue;
                }
                if (is_listen_fd(fd)) {
                    if (accepting && !server.stopping_.load()) accept_all(fd);
                    continue;
                }
                if (idle_fds.count(fd) != 0) {  // lot 5 : connexion inactive du pool qui se signale
                    on_idle_event(fd, events[i].events);
                    continue;
                }
                if (const auto owner = upstream_owner.find(fd); owner != upstream_owner.end()) {
                    auto client = connections.find(owner->second);
                    if (client != connections.end()) on_upstream_event(*client->second, events[i].events);
                    continue;
                }
                auto it = connections.find(fd);
                if (it == connections.end()) continue;
                Connection& c = *it->second;
                if (c.phase == Phase::tunnel) {  // lot 10
                    tunnel_client_event(c, events[i].events);
                    continue;
                }
                if (c.phase == Phase::inspect || c.phase == Phase::upstream) {  // D29, lot 1N : fin de flux, EPOLLHUP, EPOLLERR (par front)
                    if (events[i].events & (EPOLLRDHUP | EPOLLHUP | EPOLLERR)) client_left(c, events[i].events);
                    // Lot 5 : reponse en flux vers le client (EPOLLOUT par front, pose par begin_stream).
                    if (c.phase == Phase::upstream && c.relay.head_sent && (events[i].events & (EPOLLOUT | EPOLLERR)))
                        relay_flush(c);
                    continue;
                }
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
                    write_failed(c);  // lot 1N : comme l'echec d'envoi qui suivrait en Python
                }
            }
            run_tls_pending_reads();
            run_pipelined_pending();
            if (accept_paused && Clock::now() >= accept_resume_at) resume_accepting();
            if (Clock::now() >= next_scan) {
                check_deadlines();
                next_scan = Clock::now() + std::chrono::milliseconds(250);
            }
            collect_closed();
        }
    }

    // Lot 8 : reprise d'une lecture TLS dont OpenSSL garde deja des donnees (voir relay_flush).
    std::vector<int> tls_pending_reads;
    void run_tls_pending_reads() {
        while (!tls_pending_reads.empty()) {
            std::vector<int> fds;
            fds.swap(tls_pending_reads);
            for (int fd : fds) {
                auto it = connections.find(fd);
                if (it == connections.end()) continue;
                Connection& c = *it->second;
                if (c.phase == Phase::upstream && c.up_ssl != nullptr && c.up_phase == UpstreamPhase::reading)
                    read_upstream(c);
            }
        }
    }

    std::size_t force_close_all() {
        std::size_t count = 0;
        for (auto& [fd, c] : connections) {
            if (c->phase == Phase::tunnel) {  // lot 10 (C14) : trame 1001, ligne d'acces, puis fermeture
                tunnel_going_away(*c, true);
                ++count;
            } else if (c->phase != Phase::closed) {
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
    transfer_event_fd_ = ::eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK);
    grace_period_seconds_.store(snapshot_.load()->server.shutdown_grace_period_seconds);
    report_waf_filter(*snapshot_.load());
    prepare_upstream_tls(*snapshot_.load());
}

Server::~Server() {
    for (int fd : listen_fds_) ::close(fd);
    if (stop_event_fd_ >= 0) ::close(stop_event_fd_);
    if (transfer_event_fd_ >= 0) ::close(transfer_event_fd_);
    for (const Transfer& transfer : transfers_) {
        if (transfer.ssl != nullptr) SSL_free(transfer.ssl);
        if (transfer.fd >= 0) ::close(transfer.fd);  // jamais reprises (arret) : le client voit une fin
    }
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
    // Plan proxy natif v2, lot 7 (C13) : sante, charge et compteurs d'un backend inchange gardes ; ceux des backends et
    // zones retires oublies (une requete encore en cours garde sa propre reference jusqu'a sa fin).
    balance_registry_.retain(snapshot->proxy ? &*snapshot->proxy : nullptr);
    prepare_upstream_tls(*snapshot);
    grace_period_seconds_.store(snapshot->server.shutdown_grace_period_seconds);
    snapshot_.store(std::move(snapshot));
}

// Lot 8 : contextes TLS vers les backends construits avant la premiere requete qui en a besoin (le magasin de
// confiance se lit une fois) ; une erreur reste pour la requete, qui la journalise et repond 502.
void Server::prepare_upstream_tls(const Snapshot& snapshot) {
    if (!snapshot.proxy) return;
    for (const ProxyZoneSettings& zone : snapshot.proxy->zones) {
        if (!zone.native) continue;
        for (const ProxyUpstream& upstream : zone.upstreams) {
            if (upstream.tls) (void)upstream_tls_context(zone.verify_tls, nullptr);
        }
    }
}

SSL_CTX* Server::upstream_tls_context(bool verify, std::string* error) {
    std::lock_guard<std::mutex> lock(upstream_tls_mutex_);
    UpstreamTls& slot = upstream_tls_[verify ? 1 : 0];
    if (!slot.tried) {
        slot.tried = true;
        slot.context = make_upstream_tls_context(verify, &slot.error);
    }
    if (!slot.context && error != nullptr) *error = slot.error;
    return slot.context.get();
}

bool Server::tls_failure_due(const std::string& key, std::chrono::steady_clock::time_point now) {
    std::lock_guard<std::mutex> lock(upstream_tls_mutex_);
    const auto found = tls_failure_logged_.find(key);
    if (found != tls_failure_logged_.end() && now - found->second < std::chrono::seconds(60)) return false;
    tls_failure_logged_[key] = now;
    return true;
}

int Server::run() {
    int thread_count = options_.threads > 0 ? options_.threads : static_cast<int>(std::thread::hardware_concurrency());
    if (thread_count <= 0) thread_count = 1;
    std::vector<std::unique_ptr<Worker>> workers;
    thread_count_.store(static_cast<std::size_t>(thread_count));
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

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "control.hpp"

#include <poll.h>
#include <signal.h>
#include <sys/stat.h>
#include <unistd.h>

#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <thread>

#include "ipc.hpp"
#include "util.hpp"

namespace omega {

namespace {

constexpr int kHelloAckTimeoutMs = 5000;   // contrat §5 : pas de reponse sous 5 s = repli
constexpr int kFirstConfigTimeoutMs = 10000;
constexpr int kHealthIntervalMs = 1000;
constexpr int kMaxConsecutiveBadFrames = 5;  // contrat §5 : trame invalide repetee -> fermeture

// 0 = trame lue, 1 = fin du canal, 2 = delai depasse, -1 = erreur.
int wait_frame(int fd, int timeout_ms, ipc::Frame& frame, int* received_fd, std::string* error) {
    pollfd p{fd, POLLIN, 0};
    int ready = 0;
    do {
        ready = ::poll(&p, 1, timeout_ms);
    } while (ready < 0 && errno == EINTR);
    if (ready == 0) return 2;
    if (ready < 0) {
        if (error) *error = std::strerror(errno);
        return -1;
    }
    return ipc::recv_frame(fd, frame, received_fd, error);
}

void send_config_ack(int fd, std::uint32_t generation, bool ok, const std::string& error) {
    ipc::Frame ack;
    ack.type = ipc::kConfigAck;
    ack.generation = generation;
    ack.add_u8(ipc::tag::kConfigOk, ok ? 1 : 0);
    if (!ok) ack.add(ipc::tag::kConfigError, error);
    ipc::send_frame(fd, ack);
}

void send_error(int fd, std::uint16_t code, const std::string& message) {
    ipc::Frame frame;
    frame.type = ipc::kError;
    frame.add_u16(ipc::tag::kErrorCode, code);
    frame.add(ipc::tag::kErrorMessage, message);
    ipc::send_frame(fd, frame);
}

std::shared_ptr<const Snapshot> snapshot_from_frame(const ipc::Frame& frame, int memfd, std::string* error) {
    return snapshot_from_config_frame(frame.generation, frame.first(ipc::tag::kConfigSize),
                                      frame.first(ipc::tag::kConfigSha256), memfd, error);
}

}  // namespace

std::vector<std::string> native_capabilities() {
    return {"static", "range", "precompressed", "redirects", "rewrites", "aliases", "access_rules",
            "security_headers", "trusted_proxy", "access_log", "tls"};
}

std::shared_ptr<const Snapshot> snapshot_from_config_frame(std::uint32_t frame_generation, const std::string* size_field,
                                                           const std::string* sha_field, int memfd, std::string* error) {
    struct Closer {
        int fd;
        ~Closer() {
            if (fd >= 0) ::close(fd);
        }
    } closer{memfd};
    auto fail = [&](std::string reason) -> std::shared_ptr<const Snapshot> {
        if (error) *error = std::move(reason);
        return nullptr;
    };
    if (memfd < 0) return fail("CONFIG sans memfd");
    if (size_field == nullptr || size_field->size() != 8 || sha_field == nullptr || sha_field->size() != 32)
        return fail("CONFIG : taille ou empreinte absente");
    std::uint64_t size = 0;
    for (std::size_t i = 0; i < 8; ++i)
        size |= static_cast<std::uint64_t>(static_cast<unsigned char>((*size_field)[i])) << (8 * i);
    struct stat info {};
    if (::fstat(memfd, &info) != 0 || static_cast<std::uint64_t>(info.st_size) != size)
        return fail("CONFIG : taille du memfd differente de la taille annoncee");
    if (size > (64u << 20)) return fail("CONFIG : instantane trop grand");
    std::string text(size, '\0');
    std::size_t done = 0;
    while (done < size) {
        const ssize_t n = ::pread(memfd, text.data() + done, size - done, static_cast<off_t>(done));
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return fail("CONFIG : lecture du memfd impossible");
        done += static_cast<std::size_t>(n);
    }
    const auto digest = sha256(text);
    if (std::memcmp(digest.data(), sha_field->data(), 32) != 0) return fail("CONFIG : empreinte SHA-256 differente");
    std::string parse_error;
    auto snapshot = parse_snapshot(text, &parse_error);
    if (!snapshot) return fail("instantane refuse : " + parse_error);
    if (snapshot->generation != frame_generation)
        return fail("CONFIG : generation de la trame differente de celle de l'instantane");
    return snapshot;
}

int run_controlled(int control_fd, ServerOptions options, const char* binary_version) {
    // Signaux bloques AVANT tout fil (heritage du masque) ; traites par sigwait.
    sigset_t signals;
    sigemptyset(&signals);
    sigaddset(&signals, SIGTERM);
    sigaddset(&signals, SIGINT);
    sigaddset(&signals, SIGHUP);
    pthread_sigmask(SIG_BLOCK, &signals, nullptr);
    signal(SIGPIPE, SIG_IGN);

    ipc::Frame hello;
    hello.type = ipc::kHello;
    hello.add_u16(ipc::tag::kHelloContract, ipc::kContractVersion);
    hello.add(ipc::tag::kHelloBinary, binary_version);
    for (const std::string& capability : native_capabilities()) hello.add(ipc::tag::kHelloCapability, capability);
    hello.add_u32(ipc::tag::kHelloPid, static_cast<std::uint32_t>(::getpid()));
    if (!ipc::send_frame(control_fd, hello)) {
        std::fprintf(stderr, "omega-http-core : envoi de HELLO impossible : %s\n", std::strerror(errno));
        return 3;
    }

    std::string error;
    ipc::Frame frame;
    int rc = wait_frame(control_fd, kHelloAckTimeoutMs, frame, nullptr, &error);
    if (rc != 0 || frame.type != ipc::kHelloAck) {
        std::fprintf(stderr, "omega-http-core : pas de HELLO_ACK (%s)\n", rc == 2 ? "delai depasse" : error.c_str());
        return 3;
    }
    if (frame.unsigned_field(ipc::tag::kAckAccepted).value_or(0) != 1) {
        const std::string* reason = frame.first(ipc::tag::kAckReason);
        std::fprintf(stderr, "omega-http-core : refuse par le superviseur : %s\n", reason ? reason->c_str() : "?");
        return 3;
    }

    int memfd = -1;
    rc = wait_frame(control_fd, kFirstConfigTimeoutMs, frame, &memfd, &error);
    if (rc != 0 || frame.type != ipc::kConfig) {
        if (memfd >= 0) ::close(memfd);
        std::fprintf(stderr, "omega-http-core : pas de configuration initiale (%s)\n",
                     rc == 2 ? "delai depasse" : error.c_str());
        return 2;
    }
    auto snapshot = snapshot_from_frame(frame, memfd, &error);
    if (!snapshot) {
        send_config_ack(control_fd, frame.generation, false, error);
        std::fprintf(stderr, "omega-http-core : %s\n", error.c_str());
        return 2;
    }

    Server server(snapshot, options);
    if (!server.listen(&error)) {
        send_config_ack(control_fd, frame.generation, false, error);
        std::fprintf(stderr, "omega-http-core : %s\n", error.c_str());
        return 1;
    }
    send_config_ack(control_fd, frame.generation, true, "");

    std::atomic<bool> finished{false};
    std::thread signal_thread([&] {
        while (true) {
            int received = 0;
            if (sigwait(&signals, &received) != 0) continue;
            if (received == SIGHUP) continue;  // mode pilote : les generations arrivent par CONFIG
            server.stop();
            return;
        }
    });

    std::thread control_thread([&] {
        int bad_frames = 0;
        while (!finished.load()) {
            ipc::Frame message;
            int fd = -1;
            std::string reason;
            const int result = wait_frame(control_fd, kHealthIntervalMs, message, &fd, &reason);
            if (finished.load()) {
                if (fd >= 0) ::close(fd);
                break;
            }
            if (result == 2) {
                ipc::Frame health;
                health.type = ipc::kHealth;
                const auto current = server.snapshot();
                health.generation = current->generation;
                health.add_u64(ipc::tag::kHealthConnections, server.open_connections());
                health.add_u64(ipc::tag::kHealthRequests, server.requests_served());
                health.add_u64(ipc::tag::kHealthRejected, server.rejected_over_capacity());
                health.add_u32(ipc::tag::kHealthGeneration, current->generation);
                ipc::send_frame(control_fd, health);
                continue;
            }
            if (result == 1) {  // superviseur parti : jamais un moteur orphelin qui continue de servir
                std::fprintf(stderr, "omega-http-core : canal de controle ferme, arret\n");
                server.stop();
                break;
            }
            if (result < 0) {
                std::fprintf(stderr, "omega-http-core : trame refusee : %s\n", reason.c_str());
                send_error(control_fd, 1, reason);
                if (++bad_frames >= kMaxConsecutiveBadFrames) {
                    server.stop();
                    break;
                }
                continue;
            }
            bad_frames = 0;
            if (message.type == ipc::kConfig) {
                std::string config_error;
                auto next = snapshot_from_frame(message, fd, &config_error);
                if (next) {
                    server.install_snapshot(std::move(next));
                    send_config_ack(control_fd, message.generation, true, "");
                } else {
                    send_config_ack(control_fd, message.generation, false, config_error);
                }
                continue;
            }
            if (message.type == ipc::kDataAttach) {
                const auto thread = message.unsigned_field(ipc::tag::kAttachThread);
                if (fd >= 0 && thread) server.attach_data_channel(static_cast<std::size_t>(*thread), fd);
                else if (fd >= 0) ::close(fd);
                continue;
            }
            if (fd >= 0) ::close(fd);
            if (message.type == ipc::kShutdown) {
                if (auto grace = message.unsigned_field(ipc::tag::kShutdownGraceMs)) {
                    server.set_grace_period(static_cast<double>(*grace) / 1000.0);
                }
                server.stop();
                break;
            }
            // autres types : ignores (compatibilite ascendante)
        }
    });

    const int forced = server.run();
    finished.store(true);
    ::kill(::getpid(), SIGTERM);  // libere le fil des signaux (sigwait) si l'arret est venu du canal
    signal_thread.join();
    control_thread.join();
    return forced < 0 ? 1 : 0;
}

}  // namespace omega

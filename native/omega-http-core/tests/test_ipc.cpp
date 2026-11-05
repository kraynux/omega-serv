// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Canal de controle (lot 3) : trames sur une vraie paire SOCK_SEQPACKET, memfd en SCM_RIGHTS, controles de
// l'instantane recu (taille, SHA-256, generation).
#include "doctest.h"

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <unistd.h>

#include <string>

#include "control.hpp"
#include "ipc.hpp"
#include "util.hpp"

namespace {

int memfd_with(const std::string& content) {
    const int fd = ::memfd_create("test", MFD_CLOEXEC);
    REQUIRE(fd >= 0);
    REQUIRE(::write(fd, content.data(), content.size()) == static_cast<ssize_t>(content.size()));
    return fd;
}

std::string le64(std::uint64_t value) {
    std::string out;
    for (int i = 0; i < 8; ++i) out.push_back(static_cast<char>((value >> (8 * i)) & 0xFF));
    return out;
}

std::string digest(const std::string& text) {
    const auto d = omega::sha256(text);
    return std::string(reinterpret_cast<const char*>(d.data()), d.size());
}

}  // namespace

TEST_CASE("trame et descripteur sur une paire SOCK_SEQPACKET") {
    int pair[2];
    REQUIRE(::socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, pair) == 0);
    omega::ipc::Frame frame;
    frame.type = omega::ipc::kConfig;
    frame.generation = 4;
    frame.add_u64(omega::ipc::tag::kConfigSize, 3);
    const int memfd = memfd_with("abc");
    REQUIRE(omega::ipc::send_frame(pair[0], frame, memfd));
    ::close(memfd);

    omega::ipc::Frame received;
    int fd = -1;
    std::string error;
    REQUIRE(omega::ipc::recv_frame(pair[1], received, &fd, &error) == 0);
    CHECK(received.type == omega::ipc::kConfig);
    CHECK(received.generation == 4);
    CHECK(received.unsigned_field(omega::ipc::tag::kConfigSize) == 3);
    REQUIRE(fd >= 0);
    char buffer[4] = {};
    CHECK(::pread(fd, buffer, 3, 0) == 3);
    CHECK(std::string(buffer) == "abc");
    ::close(fd);

    // un fd non attendu est ferme, jamais garde
    const int extra = memfd_with("x");
    REQUIRE(omega::ipc::send_frame(pair[0], frame, extra));
    ::close(extra);
    CHECK(omega::ipc::recv_frame(pair[1], received, nullptr, &error) == -1);

    ::close(pair[0]);
    CHECK(omega::ipc::recv_frame(pair[1], received, &fd, &error) == 1);  // fin du canal
    ::close(pair[1]);
}

TEST_CASE("instantane recu : taille, empreinte et generation verifiees") {
    const std::string bad_json = "{\"format\": 1, \"generation\": 2}";
    std::string error;
    const std::string size = le64(bad_json.size());
    const std::string sha = digest(bad_json);

    CHECK(omega::snapshot_from_config_frame(2, &size, &sha, -1, &error) == nullptr);
    CHECK(error.find("memfd") != std::string::npos);

    const std::string wrong_size = le64(bad_json.size() + 1);
    CHECK(omega::snapshot_from_config_frame(2, &wrong_size, &sha, memfd_with(bad_json), &error) == nullptr);
    CHECK(error.find("taille") != std::string::npos);

    const std::string wrong_sha = digest("autre");
    CHECK(omega::snapshot_from_config_frame(2, &size, &wrong_sha, memfd_with(bad_json), &error) == nullptr);
    CHECK(error.find("SHA-256") != std::string::npos);

    // empreinte juste mais instantane incomplet : refuse par parse_snapshot (jamais de valeur devinee)
    CHECK(omega::snapshot_from_config_frame(2, &size, &sha, memfd_with(bad_json), &error) == nullptr);
    CHECK(error.find("instantane refuse") != std::string::npos);
}

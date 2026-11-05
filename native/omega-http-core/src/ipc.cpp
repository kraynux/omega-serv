// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "ipc.hpp"

#include <sys/socket.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>

namespace omega::ipc {

namespace {

void put_le(std::string& out, std::uint64_t value, int bytes) {
    for (int i = 0; i < bytes; ++i) out.push_back(static_cast<char>((value >> (8 * i)) & 0xFF));
}

std::uint64_t get_le(std::string_view data, std::size_t offset, int bytes) {
    std::uint64_t value = 0;
    for (int i = 0; i < bytes; ++i)
        value |= static_cast<std::uint64_t>(static_cast<unsigned char>(data[offset + static_cast<std::size_t>(i)])) << (8 * i);
    return value;
}

std::string le_bytes(std::uint64_t value, int bytes) {
    std::string out;
    put_le(out, value, bytes);
    return out;
}

}  // namespace

void Frame::add_u8(std::uint16_t tag, std::uint8_t value) { add(tag, le_bytes(value, 1)); }
void Frame::add_u16(std::uint16_t tag, std::uint16_t value) { add(tag, le_bytes(value, 2)); }
void Frame::add_u32(std::uint16_t tag, std::uint32_t value) { add(tag, le_bytes(value, 4)); }
void Frame::add_u64(std::uint16_t tag, std::uint64_t value) { add(tag, le_bytes(value, 8)); }

const std::string* Frame::first(std::uint16_t tag) const {
    for (const auto& [t, value] : fields) {
        if (t == tag) return &value;
    }
    return nullptr;
}

std::vector<std::string> Frame::all(std::uint16_t tag) const {
    std::vector<std::string> out;
    for (const auto& [t, value] : fields) {
        if (t == tag) out.push_back(value);
    }
    return out;
}

std::optional<std::uint64_t> Frame::unsigned_field(std::uint16_t tag) const {
    const std::string* value = first(tag);
    if (value == nullptr) return std::nullopt;
    const std::size_t size = value->size();
    if (size != 1 && size != 2 && size != 4 && size != 8) return std::nullopt;
    return get_le(*value, 0, static_cast<int>(size));
}

std::string encode(const Frame& frame) {
    std::string payload;
    for (const auto& [tag, value] : frame.fields) {
        put_le(payload, tag, 2);
        put_le(payload, value.size(), 4);
        payload += value;
    }
    std::string out;
    out.reserve(kHeaderSize + payload.size());
    put_le(out, kMagic, 4);
    put_le(out, kContractVersion, 2);
    put_le(out, frame.type, 2);
    put_le(out, frame.request_id, 8);
    put_le(out, frame.generation, 4);
    put_le(out, payload.size(), 4);
    out += payload;
    return out;
}

bool decode(std::string_view data, Frame& frame, std::string* error) {
    auto fail = [&](const char* reason) {
        if (error) *error = reason;
        return false;
    };
    if (data.size() < kHeaderSize) return fail("trame plus courte que l'en-tete");
    if (get_le(data, 0, 4) != kMagic) return fail("magic invalide");
    if (get_le(data, 4, 2) != kContractVersion) return fail("version de contrat differente");
    const std::uint64_t length = get_le(data, 20, 4);
    if (length != data.size() - kHeaderSize) return fail("longueur annoncee differente de la trame");
    if (length > kMaxPayload) return fail("charge utile trop grande");
    frame = Frame{};
    frame.type = static_cast<std::uint16_t>(get_le(data, 6, 2));
    frame.request_id = get_le(data, 8, 8);
    frame.generation = static_cast<std::uint32_t>(get_le(data, 16, 4));
    std::size_t offset = kHeaderSize;
    while (offset < data.size()) {
        if (data.size() - offset < 6) return fail("champ TLV tronque");
        const auto tag = static_cast<std::uint16_t>(get_le(data, offset, 2));
        const std::uint64_t size = get_le(data, offset + 2, 4);
        offset += 6;
        if (size > data.size() - offset) return fail("champ TLV deborde de la trame");
        frame.fields.emplace_back(tag, std::string(data.substr(offset, size)));
        offset += size;
    }
    return true;
}

bool send_frame(int socket_fd, const Frame& frame, int pass_fd) {
    const std::string data = encode(frame);
    iovec io{const_cast<char*>(data.data()), data.size()};
    msghdr message{};
    message.msg_iov = &io;
    message.msg_iovlen = 1;
    alignas(cmsghdr) char control[CMSG_SPACE(sizeof(int))];
    if (pass_fd >= 0) {
        std::memset(control, 0, sizeof control);
        message.msg_control = control;
        message.msg_controllen = sizeof control;
        cmsghdr* header = CMSG_FIRSTHDR(&message);
        header->cmsg_level = SOL_SOCKET;
        header->cmsg_type = SCM_RIGHTS;
        header->cmsg_len = CMSG_LEN(sizeof(int));
        std::memcpy(CMSG_DATA(header), &pass_fd, sizeof(int));
    }
    while (true) {
        const ssize_t sent = ::sendmsg(socket_fd, &message, MSG_NOSIGNAL);
        if (sent == static_cast<ssize_t>(data.size())) return true;
        if (sent < 0 && errno == EINTR) continue;
        return false;
    }
}

int send_encoded_nowait(int socket_fd, const std::string& encoded, const std::vector<int>& fds) {
    iovec io{const_cast<char*>(encoded.data()), encoded.size()};
    msghdr message{};
    message.msg_iov = &io;
    message.msg_iovlen = 1;
    alignas(cmsghdr) char control[CMSG_SPACE(sizeof(int) * 4)];
    if (!fds.empty()) {
        if (fds.size() > 4) return -1;
        std::memset(control, 0, sizeof control);
        message.msg_control = control;
        message.msg_controllen = CMSG_SPACE(sizeof(int) * fds.size());
        cmsghdr* header = CMSG_FIRSTHDR(&message);
        header->cmsg_level = SOL_SOCKET;
        header->cmsg_type = SCM_RIGHTS;
        header->cmsg_len = CMSG_LEN(sizeof(int) * fds.size());
        std::memcpy(CMSG_DATA(header), fds.data(), sizeof(int) * fds.size());
    }
    while (true) {
        const ssize_t sent = ::sendmsg(socket_fd, &message, MSG_NOSIGNAL | MSG_DONTWAIT);
        if (sent == static_cast<ssize_t>(encoded.size())) return 0;
        if (sent < 0 && errno == EINTR) continue;
        if (sent < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return 1;
        return -1;
    }
}

int recv_frame_nowait(int socket_fd, Frame& frame, std::string* error) {
    thread_local std::string buffer(kHeaderSize + kMaxPayload, '\0');  // une allocation par fil, pas par trame
    ssize_t received = 0;
    do {
        received = ::recv(socket_fd, buffer.data(), buffer.size(), MSG_DONTWAIT | MSG_TRUNC);
    } while (received < 0 && errno == EINTR);
    if (received == 0) return 1;
    if (received < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) return 2;
        if (error) *error = std::string("lecture du canal : ") + std::strerror(errno);
        return -1;
    }
    if (static_cast<std::size_t>(received) > buffer.size()) {
        if (error) *error = "trame tronquee a la reception";
        return -1;
    }
    return decode(std::string_view(buffer.data(), static_cast<std::size_t>(received)), frame, error) ? 0 : -1;
}

int recv_frame(int socket_fd, Frame& frame, int* received_fd, std::string* error) {
    if (received_fd) *received_fd = -1;
    std::string buffer(kHeaderSize + kMaxPayload, '\0');
    iovec io{buffer.data(), buffer.size()};
    msghdr message{};
    message.msg_iov = &io;
    message.msg_iovlen = 1;
    alignas(cmsghdr) char control[CMSG_SPACE(sizeof(int) * 4)];
    message.msg_control = control;
    message.msg_controllen = sizeof control;
    ssize_t received = 0;
    do {
        received = ::recvmsg(socket_fd, &message, MSG_CMSG_CLOEXEC);
    } while (received < 0 && errno == EINTR);
    if (received == 0) return 1;
    if (received < 0) {
        if (error) *error = std::string("lecture du canal : ") + std::strerror(errno);
        return -1;
    }
    // Tout fd recu est pris en charge ici : jamais une fuite, meme sur une trame refusee.
    std::vector<int> fds;
    for (cmsghdr* header = CMSG_FIRSTHDR(&message); header != nullptr; header = CMSG_NXTHDR(&message, header)) {
        if (header->cmsg_level != SOL_SOCKET || header->cmsg_type != SCM_RIGHTS) continue;
        const std::size_t count = (header->cmsg_len - CMSG_LEN(0)) / sizeof(int);
        for (std::size_t i = 0; i < count; ++i) {
            int fd = -1;
            std::memcpy(&fd, CMSG_DATA(header) + i * sizeof(int), sizeof(int));
            fds.push_back(fd);
        }
    }
    auto close_all = [&] {
        for (int fd : fds) ::close(fd);
    };
    if ((message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) != 0) {
        close_all();
        if (error) *error = "trame tronquee a la reception";
        return -1;
    }
    buffer.resize(static_cast<std::size_t>(received));
    if (!decode(buffer, frame, error)) {
        close_all();
        return -1;
    }
    if (fds.size() > 1 || (fds.size() == 1 && received_fd == nullptr)) {
        close_all();
        if (error) *error = "descripteur de fichier inattendu";
        return -1;
    }
    if (fds.size() == 1) *received_fd = fds[0];
    return 0;
}

}  // namespace omega::ipc

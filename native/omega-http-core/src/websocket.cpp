// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "websocket.hpp"

#include <algorithm>

#include "text.hpp"

namespace omega {

namespace {

std::string ascii_lower(std::string_view text) {
    std::string out(text);
    for (char& ch : out) {
        if (ch >= 'A' && ch <= 'Z') ch = static_cast<char>(ch - 'A' + 'a');
    }
    return out;
}

}  // namespace

bool is_websocket_upgrade(const Request& request) {
    if (request.head == nullptr || request.head->method != "GET") return false;
    bool upgrade_token = false;
    if (const std::string* connection = request.header("connection")) {
        const std::string text = latin1_to_utf8(*connection);
        std::size_t start = 0;
        while (start <= text.size()) {
            const std::size_t comma = std::min(text.find(',', start), text.size());
            upgrade_token = upgrade_token || ascii_lower(py_strip(std::string_view(text).substr(start, comma - start))) == "upgrade";
            start = comma + 1;
        }
    }
    if (!upgrade_token) return false;
    const std::string* upgrade = request.header("upgrade");
    return upgrade != nullptr && ascii_lower(py_strip(latin1_to_utf8(*upgrade))) == "websocket";
}

std::size_t WebSocketFrameTracker::header_needed() const {
    if (header_size_ < 2) return 2;
    const unsigned length = header_[1] & 0x7Fu;
    const std::size_t extended = length == 126 ? 2 : length == 127 ? 8 : 0;
    return 2 + extended + ((header_[1] & 0x80u) != 0 ? 4 : 0);
}

void WebSocketFrameTracker::end_of_header() {
    std::uint64_t length = header_[1] & 0x7Fu;
    if (length == 126) {
        length = (static_cast<std::uint64_t>(header_[2]) << 8) | header_[3];
    } else if (length == 127) {
        length = 0;
        for (std::size_t i = 2; i < 10; ++i) length = (length << 8) | header_[i];
    }
    if ((header_[0] & 0x0Fu) == 0x8u) close_seen_ = true;
    remaining_ = length;
    header_size_ = 0;
}

void WebSocketFrameTracker::feed(std::string_view data) {
    std::size_t position = 0;
    while (position < data.size()) {
        if (remaining_ > 0) {
            const std::uint64_t take = std::min<std::uint64_t>(remaining_, data.size() - position);
            remaining_ -= take;
            position += static_cast<std::size_t>(take);
            continue;
        }
        header_[header_size_++] = static_cast<unsigned char>(data[position++]);
        if (header_size_ == header_needed()) end_of_header();
    }
}

std::string close_frame_to_client(std::uint16_t code) {
    return std::string{'\x88', '\x02', static_cast<char>(code >> 8), static_cast<char>(code & 0xFF)};
}

std::string close_frame_to_server(const std::array<unsigned char, 4>& mask, std::uint16_t code) {
    std::string frame{'\x88', '\x82'};
    for (unsigned char byte : mask) frame.push_back(static_cast<char>(byte));
    frame.push_back(static_cast<char>((code >> 8) ^ mask[0]));
    frame.push_back(static_cast<char>((code & 0xFF) ^ mask[1]));
    return frame;
}

}  // namespace omega

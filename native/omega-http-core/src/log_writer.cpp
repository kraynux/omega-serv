// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "log_writer.hpp"

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>

namespace omega {

namespace {

long long monotonic_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

void make_parents(const std::string& path) {
    for (std::size_t slash = path.find('/', 1); slash != std::string::npos; slash = path.find('/', slash + 1)) {
        const std::string parent = path.substr(0, slash);
        if (::mkdir(parent.c_str(), 0777) != 0 && errno != EEXIST) return;
    }
}

}  // namespace

LogWriter::LogWriter(std::string path) : path_(std::move(path)) {}

LogWriter::~LogWriter() {
    if (fd_ >= 0) ::close(fd_);
}

bool LogWriter::ensure_open_locked() {
    if (fd_ >= 0) {
        const long long now = monotonic_ms();
        if (now >= next_check_ms_) {
            next_check_ms_ = now + 1000;  // _REOPEN_CHECK_SECONDS
            struct stat on_disk {}, opened {};
            const bool replaced = ::stat(path_.c_str(), &on_disk) != 0 || ::fstat(fd_, &opened) != 0 ||
                                  on_disk.st_ino != opened.st_ino || on_disk.st_dev != opened.st_dev;
            if (replaced) {
                ::close(fd_);
                fd_ = -1;
            }
        }
    }
    if (fd_ >= 0) return true;
    make_parents(path_);
    struct stat existing {};
    const bool is_new = ::stat(path_.c_str(), &existing) != 0;
    fd_ = ::open(path_.c_str(), O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC, 0666);
    if (fd_ < 0) return false;
    if (is_new) ::fchmod(fd_, 0664);  // _SHARED_LOG_FILE_MODE
    next_check_ms_ = monotonic_ms() + 1000;
    return true;
}

void LogWriter::append_line(std::string_view line) {
    std::string buffer;
    buffer.reserve(line.size() + 1);
    buffer.append(line);
    buffer.push_back('\n');
    std::lock_guard<std::mutex> lock(mutex_);
    if (!ensure_open_locked()) {
        std::fprintf(stderr, "Avertissement : echec d'ecriture du journal %s : %s\n", path_.c_str(), std::strerror(errno));
        return;
    }
    const ssize_t written = ::write(fd_, buffer.data(), buffer.size());
    if (written != static_cast<ssize_t>(buffer.size())) {
        std::fprintf(stderr, "Avertissement : echec d'ecriture du journal %s : %s\n", path_.c_str(),
                     written < 0 ? std::strerror(errno) : "ecriture partielle");
        ::close(fd_);
        fd_ = -1;
    }
}

}  // namespace omega

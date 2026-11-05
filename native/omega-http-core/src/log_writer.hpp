// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Ecriture des journaux, meme contrat que infrastructure/logging/file_line_logger.py :
//   - ajout en O_APPEND, une ligne = un seul write() (atomique entre fils et avec les processus Python) ;
//   - fichier cree en 0664 (partage avec le compte du service, jamais 0644 selon l'umask) ;
//   - fichier remplace ou supprime (« Voir et traiter IP » : os.replace) -> reouverture, verifiee au plus
//     une fois par seconde ;
//   - une erreur d'ecriture n'interrompt jamais une requete : avertissement sur stderr.
#pragma once

#include <mutex>
#include <string>
#include <string_view>

namespace omega {

class LogWriter {
public:
    explicit LogWriter(std::string path);
    ~LogWriter();
    LogWriter(const LogWriter&) = delete;
    LogWriter& operator=(const LogWriter&) = delete;

    void append_line(std::string_view line);
    [[nodiscard]] const std::string& path() const { return path_; }

private:
    bool ensure_open_locked();

    std::string path_;
    std::mutex mutex_;
    int fd_ = -1;
    long long next_check_ms_ = 0;
};

}  // namespace omega

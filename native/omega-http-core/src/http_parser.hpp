// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Parseur HTTP/1.1 strict du moteur natif - reproduction EXACTE du parseur Python de reference
// (src/omega_serv/infrastructure/server/http_parser.py) : memes limites, memes codes d'erreur, meme ordre de
// verification. Toute divergence est un bug (corpus differentiel tools/differential, plan moteur C++ §9).
//
// Deux durcissements appliques AUX DEUX MOTEURS (plan §14, 2026-11-02, RFC 9112) :
//   - un nom d'en-tete contenant une espace ou une tabulation ("X-A : 1") -> 400 ;
//   - Content-Length fait d'autre chose que des chiffres ASCII ("+5", "1_000") -> 400 ;
//   - version : `HTTP/` chiffre `.` chiffre, sinon 400 ; majeure autre que 1 -> 505 ; 1.2 a 1.9 lue comme 1.1.
#pragma once

#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace omega {

struct ParserLimits {
    std::size_t max_request_line_size = 8192;  // ServerConfig.max_request_line_size
    std::size_t max_header_size = 16384;        // ServerConfig.max_header_size
    std::size_t max_header_count = 100;         // http_parser.py::MAX_HEADER_COUNT
    std::size_t raw_line_buffer_limit = 1048576;  // http_parser.py::RAW_LINE_BUFFER_LIMIT
};

struct RequestHead {
    std::string method;
    std::string target;
    std::string http_version;
    std::vector<std::pair<std::string, std::string>> headers;  // ordre et casse d'origine

    // Premiere valeur de l'en-tete (nom insensible a la casse), comme ParsedRequestHead.header().
    [[nodiscard]] const std::string* header(std::string_view name) const;
};

enum class ParseState {
    need_more,       // tete incomplete : attendre d'autres octets
    complete,        // tete complete : `head` et `consumed` remplis
    error,           // erreur de protocole : repondre `status` puis fermer
};

struct ParseResult {
    ParseState state = ParseState::need_more;
    int status = 0;            // code HTTP de l'erreur (400, 414, 417, 431)
    std::string reason;        // pour error.log (meme texte que Python quand il existe)
    std::size_t consumed = 0;  // octets de la tete, CRLF final compris
    RequestHead head;          // en erreur : en-tetes deja analyses (methode / cible / version vides)
    // En erreur : ligne de requete brute (HttpParseError.request_line), absente si illisible (trop longue,
    // connexion coupee pendant sa lecture) - pour la ligne d'access.log (plan §14, valide 2026-11-02).
    bool has_request_line = false;
    std::string request_line;
};

// Analyse la tete d'une requete au debut de `buffer`. Ne lit jamais le corps.
// `eof` : le pair a ferme sa moitie d'ecriture. Avec un tampon vide, c'est une fermeture propre
// (ConnectionClosedCleanly cote Python) : etat `need_more`, status 0 - l'appelant ferme sans repondre.
ParseResult parse_request_head(std::string_view buffer, const ParserLimits& limits, bool eof = false);

// Cadrage du corps (read_and_discard_body cote Python), apres les controles Host / methode du serveur :
// Transfer-Encoding -> 400, Content-Length invalide / negatif -> 400, trop grand -> 413.
struct BodyFraming {
    int status = 0;                 // 0 = valide
    std::string reason;
    std::uint64_t content_length = 0;
};
BodyFraming body_framing(const RequestHead& head, std::uint64_t max_request_size);

// Ensembles de caracteres reproduits a l'identique de Python.
bool python_isspace_latin1(unsigned char c);            // str.isspace() sur un caractere latin-1
bool is_control_character(unsigned char c);              // headers.py::_CONTROL_CHARS
std::string_view python_strip(std::string_view value);   // str.strip() sur du texte latin-1

}  // namespace omega

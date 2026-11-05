// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Pipeline d'une requete, reproduction de Python (moteur de reference) :
//   infrastructure/server/asyncio_server.py::_handle_connection / _write_response / _log_access
//   application/server/route_request.py, serve_static_file.py, healthz.py, serve_icon.py,
//   serve_dirlisting_css.py, serve_error_css.py, resolve_error_page.py
//   domain/security/security_headers.py, csp.py::allow_inline_styles_by_hash
// Aucune socket ici : le serveur (server.cpp) lit, appelle ces fonctions, ecrit.
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "config.hpp"
#include "http_parser.hpp"

namespace omega {

// En-tetes de reponse : dict Python (cle sensible a la casse ; reaffecter une cle garde sa position).
class ResponseHeaders {
public:
    void set(std::string_view name, std::string value);
    void set_default(std::string_view name, std::string value);
    [[nodiscard]] const std::string* find(std::string_view name) const;
    void erase(std::string_view name);
    [[nodiscard]] const std::vector<std::pair<std::string, std::string>>& items() const { return items_; }

private:
    std::vector<std::pair<std::string, std::string>> items_;
};

struct Response {
    int status = 200;
    ResponseHeaders headers;
    std::string body;
    // Corps envoye depuis un fichier (> 256 Kio, comme STREAM_THRESHOLD_BYTES) : jamais en memoire.
    std::string body_file;
    std::uint64_t body_file_offset = 0;
    std::uint64_t body_file_length = 0;
    bool needs_python = false;  // route applicative / non portee : confiee a Python (lot 3+)
    bool abort_connection = false;  // exception non rattrapee cote Python : fermeture sans reponse ni journal

    [[nodiscard]] std::uint64_t content_length() const { return body_file.empty() ? body.size() : body_file_length; }
};

struct Request {
    std::string request_id;
    std::string remote_ip;   // UTF-8 (texte), deja normalise / resolu
    std::string peer_ip;
    const RequestHead* head = nullptr;
    std::string path_text;   // chemin (avant « ? »), texte UTF-8 de la cible latin-1
    std::string query_text;
    std::string target_text; // cible complete, texte UTF-8 (journal d'acces)
    bool absolute_target_invalid = false;  // forme absolue inutilisable -> 400 (check_before_body)
    // Requete refusee pendant l'analyse de sa tete : `head` ne porte que les en-tetes deja lus et le journal
    // d'acces ecrit cette ligne brute (texte UTF-8, « - » si illisible) a la place de « METHODE CIBLE HTTP/1.1 ».
    bool unparsed = false;
    std::string raw_request_line_text;

    // HttpRequest.header (HttpHeaders) : la DERNIERE valeur d'un en-tete repete - a ne pas confondre avec
    // RequestHead::header (ParsedRequestHead.header, la premiere), utilise pour Connection.
    [[nodiscard]] const std::string* header(std::string_view name) const;
};

// request.py::absolute_form_parts (RFC 9112 §3.2.2) sur la cible brute (octets latin-1, comme le texte Python).
struct AbsoluteForm {
    enum Kind { none, valid, invalid } kind = none;
    std::string host;
    std::string origin;  // cible en forme origine (« / » si chemin absent)
};
AbsoluteForm absolute_form_parts(std::string_view target);

// Python : forme absolue eventuelle, split_request_target + decodage latin-1.
void fill_request_target(Request& request);

// Etape 3 : IP client (option trusted_proxy).
std::string resolve_remote_ip(const Snapshot& snapshot, std::string_view peer_ip, const RequestHead& head);

// Etapes avant le corps. nullopt = continuer ; sinon la reponse a ecrire, la connexion est fermee ensuite.
struct EarlyOutcome {
    Response response;
    bool log_access = true;          // toujours depuis 2026-11-02 (Host invalide compris, plan §14)
    std::string error_log_message;   // non vide : ligne dans error.log
    bool is_error_response = false;  // _write_error_response (aucun en-tete de securite)
};
std::optional<EarlyOutcome> check_before_body(const Snapshot& snapshot, const Request& request);

// Lot 6 : la requete peut-elle atteindre une route applicative (reverse proxy, FastCGI, envoi de fichiers en POST) ?
// Sur-ensemble volontaire (prefixe du chemin d'origine OU reecrit) : Python, reference, retraite alors toute la
// connexion - au pire une requete statique servie par Python, jamais l'inverse.
bool wants_handoff(const Snapshot& snapshot, const Request& request);

// Etape 11-12 : routage + en-tetes de securite.
Response route_request(const Snapshot& snapshot, const Request& request);
void apply_security_headers(Response& response, const Snapshot& snapshot, std::string_view path_text);

// _write_response : page d'erreur, empreinte CSP, Connection, Content-Length, 304 sans corps.
// Rend la tete serialisee (latin-1) ; nullopt si un en-tete n'est pas encodable en latin-1 (Python : exception
// UnicodeEncodeError, connexion fermee sans reponse ni journal).
std::optional<std::string> finalize_response(const Snapshot& snapshot, Response& response, bool keep_alive);

Response error_response(int status);

// Journaux (une ligne, sans saut de ligne final).
std::string format_access_line(const Request& request, const Response& response, std::int64_t unix_seconds);
std::string format_error_line(std::string_view message, std::string_view request_id, std::int64_t unix_seconds);

// csp.py::allow_inline_styles_by_hash
std::string allow_inline_styles_by_hash(std::string_view policy, std::string_view html);

// Python realpath (os.path.realpath, strict=False) et LocalFilesystem.resolve_real_path_under.
std::string real_path(std::string_view path);
std::string resolve_real_path_under(const std::string& real_root, const std::vector<std::string>& segments);

}  // namespace omega

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Plan proxy natif v2, lot 4 : relais d'une requete vers un backend HTTP en clair. Fonctions pures, copies exactes du
// proxy Python (reference : application/server/serve_proxy.py, infrastructure/proxy/asyncio_http_proxy_client.py) :
// - build_upstream_request = build_outgoing_headers + la ligne et l'encodage latin-1 de _send_and_read (C6) ;
// - parse_upstream_head = _read_final_head + _body_framing (C5 : S7, S8, S9, S10, S12) ;
// - relayed_response = la reponse que serve_proxy rend au serveur (en-tetes de saut retires, Set-Cookie multiples,
//   Content-Length recalcule sauf HEAD).
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "config.hpp"
#include "engine.hpp"

namespace omega {

inline constexpr int kMaxProxyHops = 5;  // serve_proxy.MAX_PROXY_HOPS

// incoming_proxy_hop_count : int(valeur.strip()) de X-Omega-Proxy-Hops, 0 si absent ou illisible, jamais negatif.
int incoming_proxy_hop_count(const Request& request);

struct UpstreamRequestContext {
    const ProxyZoneSettings* zone = nullptr;
    const ProxyUpstream* upstream = nullptr;
    std::string effective_path;  // chemin apres reecritures (texte UTF-8, comme request.path_text)
    bool client_tls = false;     // request.is_tls
    int listen_port = 0;         // ForwardingContext.listen_port (server.port)
    const std::vector<IpNetwork>* trusted_networks = nullptr;  // trusted_proxy (vide si l'option est coupee)
    bool preserve_upgrade = false;  // lot 10 : build_outgoing_headers(preserve_upgrade=True), chemin WebSocket
};

// Octets envoyes au backend (tete latin-1 + corps) ; nullopt si un texte ne s'ecrit pas en latin-1 (UnicodeEncodeError
// cote Python, rattrapee comme ValueError : 502).
// Scan de securite n° 2 (F16) : en-tete Cookie sans omega_admin / omega_admin_theme (admin_cookies.py).
std::string without_admin_cookies(const std::string& value);

std::optional<std::string> build_upstream_request(const Request& request, const UpstreamRequestContext& context,
                                                  std::string_view body);

enum class UpstreamFraming { none, length, chunked, close };

struct UpstreamHead {
    enum class State { need_more, complete, error } state = State::need_more;
    std::string reason;          // erreur : pour error.log
    std::size_t consumed = 0;    // octets des tetes (1xx comprises)
    std::string version;         // HTTP/1.0 | HTTP/1.1
    int status = 0;
    std::vector<std::pair<std::string, std::string>> headers;  // octets latin-1, ordre d'origine
    UpstreamFraming framing = UpstreamFraming::none;
    std::uint64_t content_length = 0;
};

inline constexpr std::size_t kMaxResponseLine = 64 * 1024;       // StreamReader.readline (limite par defaut)
inline constexpr std::size_t kMaxResponseHeaders = 100;          // MAX_RESPONSE_HEADERS
inline constexpr std::size_t kMaxResponseHeaderBytes = 64 * 1024;  // MAX_RESPONSE_HEADER_BYTES
inline constexpr int kMaxInterimResponses = 8;                   // MAX_INTERIM_RESPONSES

// Tete de reponse lue depuis le debut de `data` ; `eof` : le backend a ferme (une ligne inachevee devient une erreur).
// Lot 10 : `upgrade` (mise a niveau WebSocket, _read_status_and_headers) - une seule tete, aucune 1xx sautee, 101
// acceptee ; ce qui suit la tete appartient au tunnel (framing none).
UpstreamHead parse_upstream_head(std::string_view data, std::string_view method, bool eof, bool upgrade = false);

// Lot 10 : _write_status_line_and_headers (serve_websocket_proxy) - tete ecrite au client pour une mise a niveau :
// en-tetes du backend sans ceux de saut (Connection et Upgrade gardes) ; refus (statut autre que 101) : sans corps,
// Content-Length: 0 et Connection: close. `set_cookie` : cookie collant (101 seulement). Octets latin-1.
std::string upgrade_response_head(int status, std::string_view reason,
                                  const std::vector<std::pair<std::string, std::string>>& headers,
                                  const std::string* set_cookie = nullptr);

// serve_proxy : reponse rendue au client (avant en-tetes de securite, page d'erreur et journal).
Response relayed_response(const UpstreamHead& head, std::string body, std::string_view method);

// _asks_close (D22) : un jeton `close` dans Connection (liste de jetons, casse ignoree).
bool asks_close(const UpstreamHead& head);

inline constexpr std::size_t kMaxChunkLineBytes = 4096;      // MAX_CHUNK_LINE_BYTES
inline constexpr std::size_t kMaxTrailerLines = 32;          // MAX_TRAILER_LINES
inline constexpr std::size_t kMaxTrailerBytes = 16 * 1024;   // MAX_TRAILER_BYTES

// Plan proxy natif v2, lot 5 (Q4, S11) : decodage chunked au fil de l'eau, meme regles que _read_chunked - taille
// hexadecimale sans signe de 1 a 16 chiffres, extensions bornees par la ligne (4096 octets, CRLF compris), CRLF strict
// apres les donnees, trailers bornes (32 lignes, 16 Kio), valides puis retires. Aucune allocation non bornee : les
// donnees passent directement dans `out`, seule une ligne inachevee reste chez l'appelant (bornee ci-dessus).
class ChunkedDecoder {
public:
    enum class State { size_line, data, data_crlf, trailers, done, failed };

    // Consomme le debut de `input` autant que possible et ajoute les donnees decodees a `out` (au plus `max_out`
    // octets). Rend le nombre d'octets consommes ; le reste (ligne inachevee) est a representer avec la suite.
    std::size_t feed(std::string_view input, std::string& out, std::size_t max_out = static_cast<std::size_t>(-1));
    // Le backend a ferme : un flux inacheve est une erreur (asyncio.IncompleteReadError, ou ligne incomplete).
    void finish_at_eof();

    [[nodiscard]] State state() const { return state_; }
    [[nodiscard]] bool done() const { return state_ == State::done; }
    [[nodiscard]] bool failed() const { return state_ == State::failed; }
    [[nodiscard]] const std::string& error() const { return error_; }

private:
    State state_ = State::size_line;
    std::uint64_t remaining_ = 0;
    std::size_t crlf_seen_ = 0;
    std::size_t trailer_lines_ = 0;
    std::size_t trailer_bytes_ = 0;
    std::string error_;
    void fail(std::string reason);
};

// Lot 5, tests : reponse complete du backend (octets recus jusqu'a sa fermeture) lue comme le relais la lit - tete,
// puis corps selon son decoupage. Compare aux vraies fonctions Python par pytest (--decode-responses du binaire).
struct UpstreamDecoded {
    bool ok = false;
    std::string error;
    int status = 0;
    UpstreamFraming framing = UpstreamFraming::none;
    std::string body;  // corps decode (chunked : donnees seulement)
    std::size_t rest = 0;  // octets laisses apres la reponse (jamais pour une fin par la fermeture)
};
UpstreamDecoded decode_upstream_response(std::string_view data, std::string_view method);

}  // namespace omega

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Regles pures du service statique, reproduction EXACTE des fonctions Python de reference :
//   domain/security/path_policy.py::normalize_uri_path   -> normalize_uri_path
//   domain/http/conditional.py (make_etag, http_date, is_not_modified, resolve_range)
//   domain/http/mime_types.py::guess_mime_type            -> guess_mime_type
//   domain/routing/cache_policy.py::resolve_cache_control -> resolve_cache_control
//   domain/http/precompressed.py (is_compressible, preferred_encodings)
//   domain/security/access_policy.py::is_denied_path      -> is_denied_path
// Verifiees contre Python par des vecteurs generes (tests/vectors, tools/differential/make_vectors.py).
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace omega {

// ------------------------------------------------------------------------------------- chemins
// Statut 0 = ok (segments remplis) ; sinon 400 (vide, decodage, NUL, controle) ou 403 (remontee).
struct PathDecision {
    int status = 0;
    std::vector<std::string> segments;  // UTF-8, ni "", ni ".", ni ".."
};
// `raw_path` : octets bruts de la cible (sans la query), interpretes comme Python les voit : texte latin-1.
PathDecision normalize_uri_path(std::string_view raw_path);
// Meme regle sur un chemin deja texte (UTF-8) : chemin reecrit ou alias, dont une partie vient de la
// configuration et peut contenir des caracteres hors latin-1 (Python les manipule comme des str).
PathDecision normalize_uri_path_utf8(std::string_view utf8_path);

// --------------------------------------------------------------------------------- conditionnels
std::string make_etag(std::uint64_t size, std::int64_t mtime);
std::string http_date(std::int64_t mtime);
// Date HTTP -> secondes Unix (email.utils.parsedate_to_datetime + timestamp), nullopt si illisible.
std::optional<double> parse_http_date(std::string_view value);
bool is_not_modified(const std::string* if_none_match, const std::string* if_modified_since,
                     std::string_view etag, std::int64_t mtime);

struct RangeDecision {
    bool partial = false;        // 206
    bool unsatisfiable = false;  // 416
    std::uint64_t start = 0;
    std::uint64_t end = 0;       // inclus
};
RangeDecision resolve_range(const std::string* range_header, const std::string* if_range,
                            std::uint64_t size, std::string_view etag, std::int64_t mtime);

// --------------------------------------------------------------------------- types, cache, gzip
std::string guess_mime_type(std::string_view filename);

struct CachePolicy {
    std::string default_value = "no-cache, must-revalidate";
    std::vector<std::pair<std::string, std::string>> zones;       // (prefixe, valeur)
    std::vector<std::pair<std::string, std::string>> extensions;  // (".css", valeur)
};
CachePolicy default_cache_policy();
std::string resolve_cache_control(std::string_view path, std::string_view filename, const CachePolicy& policy);

bool is_compressible(std::string_view filename);
// (codage, suffixe) acceptes, du plus au moins voulu (meme tri que Python).
std::vector<std::pair<std::string, std::string>> preferred_encodings(const std::string* accept_encoding);

// ------------------------------------------------------------------------------------ zones
// zone_resolver.py::resolve_zone : prefixe le plus long qui correspond « par segment ».
bool path_matches_prefix(std::string_view path, std::string_view prefix);
int resolve_zone_index(std::string_view path, const std::vector<std::string>& prefixes);  // -1 = aucune

// ------------------------------------------------------------------------------- acces generique
struct DenyRules {
    bool deny_hidden_files = true;
    std::vector<std::string> deny_sensitive_extensions;
    std::vector<std::string> deny_patterns;
};
bool is_denied_path(const std::vector<std::string>& segments, const DenyRules& rules);

// ---------------------------------------------------------------------------------- utilitaires
// str.lower() de Python sur du texte UTF-8 (ASCII + latin-1 ; le reste est conserve tel quel, comme les
// extensions et motifs comparees cote Python, toutes ASCII en pratique).
std::string py_lower(std::string_view utf8);
std::string latin1_to_utf8(std::string_view latin1);

}  // namespace omega

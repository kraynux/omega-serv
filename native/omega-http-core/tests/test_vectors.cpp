// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Rejoue les vecteurs calcules par les VRAIES fonctions Python (tools/differential/make_vectors.py) :
// toute difference est un ecart de comportement entre les deux moteurs.
#include "doctest.h"

#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "engine.hpp"
#include "http_parser.hpp"
#include "ipc.hpp"
#include "text.hpp"
#include "ip.hpp"
#include "static_rules.hpp"

namespace {

std::string unhex(const std::string& hex) {
    std::string out;
    out.reserve(hex.size() / 2);
    for (std::size_t i = 0; i + 1 < hex.size(); i += 2) {
        out.push_back(static_cast<char>(std::stoi(hex.substr(i, 2), nullptr, 16)));
    }
    return out;
}

std::vector<std::string> split_tabs(const std::string& line) {
    std::vector<std::string> fields;
    std::stringstream stream(line);
    std::string field;
    while (std::getline(stream, field, '\t')) fields.push_back(field);
    if (!line.empty() && line.back() == '\t') fields.emplace_back();
    return fields;
}

std::string printable(const std::string& bytes) {
    std::string out;
    for (unsigned char c : bytes) {
        if (c >= 0x20 && c < 0x7f) {
            out.push_back(static_cast<char>(c));
        } else {
            char buffer[8];
            std::snprintf(buffer, sizeof buffer, "\\x%02x", c);
            out += buffer;
        }
    }
    return out;
}

}  // namespace

TEST_CASE("vecteurs Python : regles pures du statique") {
    std::ifstream file(OMEGA_VECTORS_FILE);
    REQUIRE(file.good());
    std::map<std::string, int> checked;
    std::map<std::string, int> failed;
    std::string line;
    while (std::getline(file, line)) {
        if (line.empty()) continue;
        const std::vector<std::string> f = split_tabs(line);
        const std::string& kind = f[0];
        std::string got, want, input;
        if (kind == "path") {
            input = unhex(f[1]);
            want = unhex(f[2]);
            const omega::PathDecision d = omega::normalize_uri_path(input);
            if (d.status == 0) {
                got = "OK";
                for (const auto& s : d.segments) got += "\x1f" + s;
            } else {
                got = std::to_string(d.status);
            }
        } else if (kind == "date") {
            input = unhex(f[1]);
            want = unhex(f[2]);
            const auto parsed = omega::parse_http_date(input);
            got = parsed ? std::to_string(static_cast<long long>(*parsed)) : "N";
        } else if (kind == "range") {
            const std::string spec = unhex(f[1]);
            const std::string if_range = unhex(f[2]);
            const bool has_if_range = f[3] == "1";
            const auto size = std::stoull(unhex(f[4]));
            want = unhex(f[5]);
            input = spec + " | " + if_range + " | " + std::to_string(size);
            const std::string etag = omega::make_etag(1000, 1700000000);
            const auto d = omega::resolve_range(&spec, has_if_range ? &if_range : nullptr, size, etag, 1700000000);
            got = d.unsatisfiable ? "UNSAT" : d.partial ? std::to_string(d.start) + "-" + std::to_string(d.end) : "FULL";
        } else if (kind == "cond") {
            const std::string inm = unhex(f[1]);
            const std::string ims = unhex(f[3]);
            want = f[5];
            input = inm + " | " + ims;
            const std::string etag = omega::make_etag(927, 1700000000);
            got = omega::is_not_modified(f[2] == "1" ? &inm : nullptr, f[4] == "1" ? &ims : nullptr, etag, 1700000000)
                      ? "1" : "0";
        } else if (kind == "etag") {
            const long long mtime = std::stoll(unhex(f[1]));
            const auto size = std::stoull(unhex(f[2]));
            input = unhex(f[1]) + " " + unhex(f[2]);
            want = unhex(f[3]) + " " + unhex(f[4]);
            got = omega::make_etag(size, mtime) + " " + omega::http_date(mtime);
        } else if (kind == "mime") {
            input = unhex(f[1]);
            want = unhex(f[2]);
            got = omega::guess_mime_type(input);
        } else if (kind == "compress") {
            input = unhex(f[1]);
            want = f[2];
            got = omega::is_compressible(input) ? "1" : "0";
        } else if (kind == "cache") {
            const std::string path = unhex(f[1]);
            input = unhex(f[2]);
            want = unhex(f[3]);
            got = omega::resolve_cache_control(path, input, omega::default_cache_policy());
        } else if (kind == "enc") {
            input = unhex(f[1]);
            want = unhex(f[3]);
            const auto encodings = omega::preferred_encodings(f[2] == "1" ? &input : nullptr);
            for (std::size_t i = 0; i < encodings.size(); ++i) got += (i ? "," : "") + encodings[i].first;
        } else if (kind == "normip") {
            input = unhex(f[1]);
            want = unhex(f[2]);
            got = omega::normalize_ip(input);
        } else if (kind == "trusted") {
            input = unhex(f[1]) + " in " + unhex(f[2]);
            want = f[3];
            got = omega::is_trusted_proxy(unhex(f[1]), omega::parse_trusted_networks({unhex(f[2])})) ? "1" : "0";
        } else if (kind == "client") {
            const std::string peer = unhex(f[1]);
            const std::string xff = unhex(f[2]);
            const std::string fwd = unhex(f[4]);
            std::vector<std::string> preference;
            std::stringstream names(unhex(f[6]));
            for (std::string name; std::getline(names, name, ',');) preference.push_back(name);
            const bool has_xff = f[3] == "1";
            const bool has_fwd = f[5] == "1";
            input = peer + " xff=" + (has_xff ? xff : "-") + " fwd=" + (has_fwd ? fwd : "-") + " pref=" + unhex(f[6]);
            want = unhex(f[7]);
            const auto trusted = omega::parse_trusted_networks({"127.0.0.1", "::1", "10.0.0.0/8"});
            auto lookup = [&](const std::string& name) -> const std::string* {
                const std::string lower = omega::py_lower(name);
                if (lower == "x-forwarded-for" && has_xff) return &xff;
                if (lower == "forwarded" && has_fwd) return &fwd;
                return nullptr;
            };
            got = omega::resolve_client_ip(peer, lookup, trusted, preference);
        } else if (kind == "csp") {
            const std::string policy = unhex(f[1]);
            const std::string html = unhex(f[2]);
            input = policy + " | " + html;
            want = unhex(f[3]);
            got = omega::allow_inline_styles_by_hash(policy, html);
        } else if (kind == "absform") {
            input = unhex(f[1]);
            want = unhex(f[2]);
            const omega::AbsoluteForm form = omega::absolute_form_parts(input);
            got = form.kind == omega::AbsoluteForm::none ? "none"
                  : form.kind == omega::AbsoluteForm::invalid ? "invalid" : "valid " + form.host + " " + form.origin;
        } else if (kind == "reqline") {
            input = unhex(f[1]);
            want = unhex(f[2]);
            const omega::ParseResult r = omega::parse_request_head(input, omega::ParserLimits{}, true);
            if (r.state == omega::ParseState::need_more) {
                got = "closed";
            } else if (r.state == omega::ParseState::complete) {
                got = "ok " + r.head.method + " " + r.head.target + " " + r.head.http_version;
            } else {
                got = std::to_string(r.status) + " " + omega::utf8_to_latin1(r.reason).value_or("?")  /* hx() : texte en latin-1 */ + " | " +
                      (r.has_request_line ? r.request_line : std::string("-")) + " | " + std::to_string(r.head.headers.size());
            }
        } else if (kind == "ipc") {
            // Python encode ; le C++ doit produire les memes octets et relire les memes champs.
            omega::ipc::Frame frame;
            frame.type = static_cast<std::uint16_t>(std::stoul(f[2]));
            frame.request_id = std::stoull(f[3]);
            frame.generation = static_cast<std::uint32_t>(std::stoul(f[4]));
            std::stringstream fields(f.size() > 5 ? f[5] : std::string());
            for (std::string item; std::getline(fields, item, ';');) {
                const std::size_t colon = item.find(':');
                frame.add(static_cast<std::uint16_t>(std::stoul(item.substr(0, colon))), unhex(item.substr(colon + 1)));
            }
            input = f[1];
            want = unhex(f[1]);
            got = omega::ipc::encode(frame);
            omega::ipc::Frame decoded;
            std::string error;
            if (!omega::ipc::decode(want, decoded, &error) || decoded.type != frame.type ||
                decoded.request_id != frame.request_id || decoded.generation != frame.generation ||
                decoded.fields != frame.fields) {
                got = "decodage different : " + error;
            }
        } else if (kind == "ipcdecode") {
            input = f[1];
            want = f[2];
            omega::ipc::Frame decoded;
            got = omega::ipc::decode(unhex(f[1]), decoded, nullptr) ? "ok" : "refuse";
        } else {
            FAIL("type de vecteur inconnu : " << kind);
        }
        ++checked[kind];
        if (got != want) {
            if (++failed[kind] <= 8) {
                MESSAGE(kind << " entree=[" << printable(input) << "] attendu=[" << printable(want) << "] obtenu=["
                             << printable(got) << "]");
            }
        }
    }
    for (const auto& [kind, count] : checked) {
        const int bad = failed.count(kind) ? failed[kind] : 0;
        MESSAGE(kind << " : " << count << " vecteurs, " << bad << " ecart(s)");
        CHECK(bad == 0);
    }
}

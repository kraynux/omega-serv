// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "util.hpp"

#include <array>
#include <cmath>
#include <cstdlib>
#include <cstring>

namespace omega {

// ============================================================================================ SHA-256
namespace {

constexpr std::array<std::uint32_t, 64> K = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

constexpr std::uint32_t rotr(std::uint32_t x, int n) {
    return (x >> n) | (x << (32 - n));
}

void sha256_block(std::array<std::uint32_t, 8>& h, const std::uint8_t* block) {
    std::array<std::uint32_t, 64> w{};
    for (std::size_t i = 0; i < 16; ++i) {
        w[i] = static_cast<std::uint32_t>(block[i * 4]) << 24 | static_cast<std::uint32_t>(block[i * 4 + 1]) << 16 |
               static_cast<std::uint32_t>(block[i * 4 + 2]) << 8 | static_cast<std::uint32_t>(block[i * 4 + 3]);
    }
    for (std::size_t i = 16; i < 64; ++i) {
        const std::uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
        const std::uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    std::uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
    for (std::size_t i = 0; i < 64; ++i) {
        const std::uint32_t s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        const std::uint32_t ch = (e & f) ^ (~e & g);
        const std::uint32_t t1 = hh + s1 + ch + K[i] + w[i];
        const std::uint32_t s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        const std::uint32_t t2 = s0 + maj;
        hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
}

}  // namespace

std::array<std::uint8_t, 32> sha256(std::string_view data) {
    std::array<std::uint32_t, 8> h = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
    const auto* bytes = reinterpret_cast<const std::uint8_t*>(data.data());
    std::size_t offset = 0;
    for (; offset + 64 <= data.size(); offset += 64) sha256_block(h, bytes + offset);
    std::array<std::uint8_t, 128> tail{};
    const std::size_t rest = data.size() - offset;
    if (rest > 0) std::memcpy(tail.data(), bytes + offset, rest);
    tail[rest] = 0x80;
    const std::size_t tail_size = rest + 1 + 8 <= 64 ? 64 : 128;
    const std::uint64_t bit_length = static_cast<std::uint64_t>(data.size()) * 8;
    for (std::size_t i = 0; i < 8; ++i) tail[tail_size - 1 - i] = static_cast<std::uint8_t>(bit_length >> (8 * i));
    sha256_block(h, tail.data());
    if (tail_size == 128) sha256_block(h, tail.data() + 64);
    std::array<std::uint8_t, 32> digest{};
    for (std::size_t i = 0; i < 8; ++i) {
        digest[i * 4] = static_cast<std::uint8_t>(h[i] >> 24);
        digest[i * 4 + 1] = static_cast<std::uint8_t>(h[i] >> 16);
        digest[i * 4 + 2] = static_cast<std::uint8_t>(h[i] >> 8);
        digest[i * 4 + 3] = static_cast<std::uint8_t>(h[i]);
    }
    return digest;
}

std::string base64_encode(const std::uint8_t* data, std::size_t size) {
    static constexpr char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    out.reserve((size + 2) / 3 * 4);
    std::size_t i = 0;
    for (; i + 3 <= size; i += 3) {
        const std::uint32_t v = static_cast<std::uint32_t>(data[i]) << 16 | static_cast<std::uint32_t>(data[i + 1]) << 8 | data[i + 2];
        out.push_back(alphabet[(v >> 18) & 63]);
        out.push_back(alphabet[(v >> 12) & 63]);
        out.push_back(alphabet[(v >> 6) & 63]);
        out.push_back(alphabet[v & 63]);
    }
    if (size - i == 1) {
        const std::uint32_t v = static_cast<std::uint32_t>(data[i]) << 16;
        out.push_back(alphabet[(v >> 18) & 63]);
        out.push_back(alphabet[(v >> 12) & 63]);
        out += "==";
    } else if (size - i == 2) {
        const std::uint32_t v = static_cast<std::uint32_t>(data[i]) << 16 | static_cast<std::uint32_t>(data[i + 1]) << 8;
        out.push_back(alphabet[(v >> 18) & 63]);
        out.push_back(alphabet[(v >> 12) & 63]);
        out.push_back(alphabet[(v >> 6) & 63]);
        out.push_back('=');
    }
    return out;
}

// ============================================================================================== JSON
namespace {

const JsonArray kEmptyArray{};
const JsonObject kEmptyObject{};
const std::string kEmptyString{};

class JsonParser {
public:
    explicit JsonParser(std::string_view text) : text_(text) {}

    std::optional<Json> parse(std::string* error) {
        skip_ws();
        auto value = parse_value(0);
        skip_ws();
        if (!value || pos_ != text_.size()) {
            if (error) *error = "JSON invalide pres de l'octet " + std::to_string(pos_) + (reason_.empty() ? "" : " : " + reason_);
            return std::nullopt;
        }
        return value;
    }

private:
    std::string_view text_;
    std::size_t pos_ = 0;
    std::string reason_;

    void skip_ws() {
        while (pos_ < text_.size() && (text_[pos_] == ' ' || text_[pos_] == '\t' || text_[pos_] == '\n' || text_[pos_] == '\r'))
            ++pos_;
    }

    bool consume(std::string_view literal) {
        if (text_.substr(pos_, literal.size()) != literal) return false;
        pos_ += literal.size();
        return true;
    }

    std::optional<Json> fail(const char* why) {
        reason_ = why;
        return std::nullopt;
    }

    std::optional<Json> parse_value(int depth) {
        if (depth > 64) return fail("imbrication trop profonde");
        if (pos_ >= text_.size()) return fail("fin inattendue");
        const char c = text_[pos_];
        if (c == '{') return parse_object(depth);
        if (c == '[') return parse_array(depth);
        if (c == '"') {
            auto s = parse_string();
            if (!s) return std::nullopt;
            return Json{*s};
        }
        if (consume("true")) return Json{true};
        if (consume("false")) return Json{false};
        if (consume("null")) return Json{nullptr};
        return parse_number();
    }

    std::optional<Json> parse_number() {
        const std::size_t start = pos_;
        if (pos_ < text_.size() && text_[pos_] == '-') ++pos_;
        if (pos_ >= text_.size() || !std::isdigit(static_cast<unsigned char>(text_[pos_]))) return fail("nombre invalide");
        if (text_[pos_] == '0') ++pos_;
        else while (pos_ < text_.size() && std::isdigit(static_cast<unsigned char>(text_[pos_]))) ++pos_;
        if (pos_ < text_.size() && text_[pos_] == '.') {
            ++pos_;
            if (pos_ >= text_.size() || !std::isdigit(static_cast<unsigned char>(text_[pos_]))) return fail("nombre invalide");
            while (pos_ < text_.size() && std::isdigit(static_cast<unsigned char>(text_[pos_]))) ++pos_;
        }
        if (pos_ < text_.size() && (text_[pos_] == 'e' || text_[pos_] == 'E')) {
            ++pos_;
            if (pos_ < text_.size() && (text_[pos_] == '+' || text_[pos_] == '-')) ++pos_;
            if (pos_ >= text_.size() || !std::isdigit(static_cast<unsigned char>(text_[pos_]))) return fail("nombre invalide");
            while (pos_ < text_.size() && std::isdigit(static_cast<unsigned char>(text_[pos_]))) ++pos_;
        }
        const std::string number(text_.substr(start, pos_ - start));
        return Json{std::strtod(number.c_str(), nullptr)};
    }

    static void append_utf8(std::string& out, std::uint32_t cp) {
        if (cp < 0x80) out.push_back(static_cast<char>(cp));
        else if (cp < 0x800) { out.push_back(static_cast<char>(0xC0 | (cp >> 6))); out.push_back(static_cast<char>(0x80 | (cp & 0x3F))); }
        else if (cp < 0x10000) { out.push_back(static_cast<char>(0xE0 | (cp >> 12))); out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F))); out.push_back(static_cast<char>(0x80 | (cp & 0x3F))); }
        else { out.push_back(static_cast<char>(0xF0 | (cp >> 18))); out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F))); out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F))); out.push_back(static_cast<char>(0x80 | (cp & 0x3F))); }
    }

    std::optional<std::uint32_t> hex4() {
        if (pos_ + 4 > text_.size()) return std::nullopt;
        std::uint32_t v = 0;
        for (int i = 0; i < 4; ++i) {
            const char c = text_[pos_++];
            v <<= 4;
            if (c >= '0' && c <= '9') v |= static_cast<std::uint32_t>(c - '0');
            else if (c >= 'a' && c <= 'f') v |= static_cast<std::uint32_t>(c - 'a' + 10);
            else if (c >= 'A' && c <= 'F') v |= static_cast<std::uint32_t>(c - 'A' + 10);
            else return std::nullopt;
        }
        return v;
    }

    std::optional<std::string> parse_string() {
        ++pos_;  // '"'
        std::string out;
        while (pos_ < text_.size()) {
            const char c = text_[pos_++];
            if (c == '"') return out;
            if (static_cast<unsigned char>(c) < 0x20) { reason_ = "caractere de controle dans une chaine"; return std::nullopt; }
            if (c != '\\') { out.push_back(c); continue; }
            if (pos_ >= text_.size()) break;
            const char e = text_[pos_++];
            switch (e) {
                case '"': out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                case '/': out.push_back('/'); break;
                case 'b': out.push_back('\b'); break;
                case 'f': out.push_back('\f'); break;
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                case 'u': {
                    auto cp = hex4();
                    if (!cp) { reason_ = "\\u invalide"; return std::nullopt; }
                    std::uint32_t code = *cp;
                    if (code >= 0xD800 && code <= 0xDBFF && consume("\\u")) {
                        auto low = hex4();
                        if (!low || *low < 0xDC00 || *low > 0xDFFF) { reason_ = "paire de substitution invalide"; return std::nullopt; }
                        code = 0x10000 + ((code - 0xD800) << 10) + (*low - 0xDC00);
                    } else if (code >= 0xD800 && code <= 0xDFFF) {
                        reason_ = "substitut isole";
                        return std::nullopt;
                    }
                    append_utf8(out, code);
                    break;
                }
                default: reason_ = "echappement inconnu"; return std::nullopt;
            }
        }
        reason_ = "chaine non terminee";
        return std::nullopt;
    }

    std::optional<Json> parse_array(int depth) {
        ++pos_;
        auto array = std::make_shared<JsonArray>();
        skip_ws();
        if (consume("]")) return Json{array};
        while (true) {
            skip_ws();
            auto value = parse_value(depth + 1);
            if (!value) return std::nullopt;
            array->push_back(std::move(*value));
            skip_ws();
            if (consume("]")) return Json{array};
            if (!consume(",")) return fail("',' ou ']' attendu");
        }
    }

    std::optional<Json> parse_object(int depth) {
        ++pos_;
        auto object = std::make_shared<JsonObject>();
        skip_ws();
        if (consume("}")) return Json{object};
        while (true) {
            skip_ws();
            if (pos_ >= text_.size() || text_[pos_] != '"') return fail("cle attendue");
            auto key = parse_string();
            if (!key) return std::nullopt;
            skip_ws();
            if (!consume(":")) return fail("':' attendu");
            skip_ws();
            auto value = parse_value(depth + 1);
            if (!value) return std::nullopt;
            object->emplace_back(std::move(*key), std::move(*value));
            skip_ws();
            if (consume("}")) return Json{object};
            if (!consume(",")) return fail("',' ou '}' attendu");
        }
    }
};

}  // namespace

const Json* Json::get(std::string_view key) const {
    if (!is_object()) return nullptr;
    for (const auto& [name, member] : *std::get<std::shared_ptr<JsonObject>>(value)) {
        if (name == key) return &member;
    }
    return nullptr;
}

std::string Json::str(std::string_view key, std::string fallback) const {
    const Json* v = get(key);
    return v && v->is_string() ? std::get<std::string>(v->value) : fallback;
}

double Json::num(std::string_view key, double fallback) const {
    const Json* v = get(key);
    return v && std::holds_alternative<double>(v->value) ? std::get<double>(v->value) : fallback;
}

bool Json::boolean(std::string_view key, bool fallback) const {
    const Json* v = get(key);
    return v && std::holds_alternative<bool>(v->value) ? std::get<bool>(v->value) : fallback;
}

const JsonArray& Json::array(std::string_view key) const {
    const Json* v = get(key);
    return v && v->is_array() ? *std::get<std::shared_ptr<JsonArray>>(v->value) : kEmptyArray;
}

const JsonObject& Json::object() const {
    return is_object() ? *std::get<std::shared_ptr<JsonObject>>(value) : kEmptyObject;
}

const std::string& Json::as_string() const {
    return is_string() ? std::get<std::string>(value) : kEmptyString;
}

std::optional<Json> parse_json(std::string_view text, std::string* error) {
    return JsonParser(text).parse(error);
}

}  // namespace omega

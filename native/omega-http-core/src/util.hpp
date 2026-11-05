// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
// Utilitaires sans dependance : SHA-256 (FIPS 180-4), base64 (RFC 4648), lecteur JSON strict (RFC 8259).
#pragma once

#include <array>
#include <cstdint>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

namespace omega {

std::array<std::uint8_t, 32> sha256(std::string_view data);
std::string base64_encode(const std::uint8_t* data, std::size_t size);

// --------------------------------------------------------------------------------------------- JSON
struct Json;
using JsonObject = std::vector<std::pair<std::string, Json>>;  // ordre conserve (comme un dict Python)
using JsonArray = std::vector<Json>;

struct Json {
    std::variant<std::nullptr_t, bool, double, std::string, std::shared_ptr<JsonArray>, std::shared_ptr<JsonObject>> value;

    [[nodiscard]] bool is_null() const { return std::holds_alternative<std::nullptr_t>(value); }
    [[nodiscard]] bool is_object() const { return std::holds_alternative<std::shared_ptr<JsonObject>>(value); }
    [[nodiscard]] bool is_array() const { return std::holds_alternative<std::shared_ptr<JsonArray>>(value); }
    [[nodiscard]] bool is_string() const { return std::holds_alternative<std::string>(value); }
    // Acces types ; valeur par defaut si la cle manque ou n'a pas le bon type (la configuration est deja
    // validee par Python : le natif ne fait qu'un controle de structure).
    [[nodiscard]] const Json* get(std::string_view key) const;
    [[nodiscard]] std::string str(std::string_view key, std::string fallback = {}) const;
    [[nodiscard]] double num(std::string_view key, double fallback = 0) const;
    [[nodiscard]] bool boolean(std::string_view key, bool fallback = false) const;
    [[nodiscard]] const JsonArray& array(std::string_view key) const;
    [[nodiscard]] const JsonObject& object() const;
    [[nodiscard]] const std::string& as_string() const;
};

// Erreur : nullopt et `error` rempli (position + raison).
std::optional<Json> parse_json(std::string_view text, std::string* error = nullptr);

}  // namespace omega

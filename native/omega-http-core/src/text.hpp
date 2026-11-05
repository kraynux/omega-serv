// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Texte « a la Python » dans le moteur : toute chaine manipulee comme un `str` Python est gardee en UTF-8
// (bijection avec les points de code). Les octets venant du reseau sont du latin-1 (decodage du parseur
// Python) et passent par latin1_to_utf8 avant toute comparaison avec la configuration (JSON, donc UTF-8) :
// « /é » configure ne doit jamais correspondre aux octets bruts C3 A9 de la requete, comme en Python.
#pragma once

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace omega {

std::size_t utf8_length(std::string_view utf8);                        // len(str)
std::string_view utf8_skip(std::string_view utf8, std::size_t count);  // s[count:]
std::string_view utf8_take(std::string_view utf8, std::size_t count);  // s[:count]

bool python_isspace(char32_t cp);                                       // str.isspace()
std::string_view py_strip(std::string_view utf8);                       // str.strip()
std::vector<std::string_view> py_split_whitespace(std::string_view utf8);  // str.split()

// UTF-8 -> latin-1 (encodage des en-tetes de reponse cote Python) ; nullopt si un caractere depasse U+00FF
// (Python leve alors UnicodeEncodeError et la connexion est fermee sans reponse).
std::optional<std::string> utf8_to_latin1(std::string_view utf8);

// access_log_format.py::sanitize_log_field : caracteres 0x00-0x1F -> espace, puis s[:max_length].
std::string sanitize_log_field(std::string_view utf8, std::size_t max_length);

}  // namespace omega

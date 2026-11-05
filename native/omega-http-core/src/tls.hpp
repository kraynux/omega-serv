// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// TLS direct du moteur natif (plan moteur C++ lot 3b, §16.3) : meme bibliotheque que le module `ssl` de Python
// (OpenSSL du systeme) et meme contexte que infrastructure/tls/ssl_context_builder.py::build_ssl_context, construit
// comme CPython construit `ssl.SSLContext(PROTOCOL_TLS_SERVER)` : options par defaut de CPython, versions min/max,
// suites TLS 1.2 de Python (transmises par l'instantane, une seule source), chaine de certificats + cle (phrase de
// passe lue dans la variable d'environnement nommee par la configuration), verification cle/certificat.
#pragma once

#include <memory>
#include <string>

#include "config.hpp"

typedef struct ssl_ctx_st SSL_CTX;

namespace omega {

// nullptr + raison si le certificat, la cle ou les reglages sont inutilisables : jamais de HTTP a la place.
std::shared_ptr<SSL_CTX> make_tls_context(const TlsSettings& settings, std::string* error);

}  // namespace omega

// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Plan proxy natif v2, lot 8 (C15, S15) : TLS du relais natif vers le backend. Meme bibliotheque que le module `ssl`
// de Python (OpenSSL du systeme) et meme contexte que infrastructure/tls/ssl_context_builder.py::
// build_client_ssl_context, construit comme CPython construit `ssl.create_default_context()` : options, versions,
// suites et source des CA (set_default_verify_paths : SSL_CERT_FILE et SSL_CERT_DIR compris) identiques ; SNI
// seulement pour un nom DNS ; nom verifie par X509_VERIFY_PARAM_set1_host, ou set1_ip pour une adresse.
#pragma once

#include <memory>
#include <string>

typedef struct ssl_ctx_st SSL_CTX;
typedef struct ssl_st SSL;

namespace omega {

// Contexte verifie (CERT_REQUIRED, check_hostname) ou non verifie (CERT_NONE). nullptr + raison si OpenSSL refuse.
std::shared_ptr<SSL_CTX> make_upstream_tls_context(bool verify, std::string* error);

// Session prete pour SSL_connect sur `fd` (socket deja connectee) : nullptr si OpenSSL refuse.
SSL* new_upstream_tls(SSL_CTX* context, int fd, const std::string& host, bool verify);

// Echec de poignee de main (SSL_get_error == SSL_ERROR_SSL) : raison ecrite dans error.log, comme le module ssl la
// donne (verify_message pour un certificat, nom de la raison OpenSSL sinon). Vide : pas un echec TLS a journaliser
// (fin de flux pendant la poignee de main, SSLEOFError cote Python). Vide la file d'erreurs d'OpenSSL.
std::string upstream_tls_failure(SSL* ssl, const std::string& host, bool* certificate);

// close_notify sans attendre la reponse (poignee de main finie seulement), puis liberation. nullptr : rien.
void free_upstream_tls(SSL* ssl);

// Adresse IP litterale (a2i_IPADDRESS de CPython) : ni SNI, ni set1_host.
bool is_ip_literal(const std::string& host);

}  // namespace omega

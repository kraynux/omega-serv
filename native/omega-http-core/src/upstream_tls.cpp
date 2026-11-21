// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "upstream_tls.hpp"

#include <arpa/inet.h>
#include <openssl/err.h>
#include <openssl/ssl.h>
#include <openssl/x509v3.h>

#include <cctype>
#include <cstdint>

namespace omega {

namespace {

// PY_SSL_DEFAULT_CIPHER_STRING (Modules/_ssl.c, PY_SSL_DEFAULT_CIPHERS == 1) : suites TLS 1.2 de tout contexte cree
// par CPython ; TLS 1.3 : suites par defaut d'OpenSSL, comme Python.
constexpr const char* kPythonDefaultCiphers =
    "@SECLEVEL=2:ECDH+AESGCM:ECDH+CHACHA20:ECDH+AES:DHE+AES:!aNULL:!eNULL:!aDSS:!SHA1:!AESCCM";

std::string openssl_errors() {
    std::string out;
    while (const unsigned long code = ERR_get_error()) {
        char buffer[256];
        ERR_error_string_n(code, buffer, sizeof buffer);
        if (!out.empty()) out += " ; ";
        out += buffer;
    }
    return out.empty() ? "erreur OpenSSL inconnue" : out;
}

}  // namespace

bool is_ip_literal(const std::string& host) {
    unsigned char buffer[16];
    return ::inet_pton(AF_INET, host.c_str(), buffer) == 1 || ::inet_pton(AF_INET6, host.c_str(), buffer) == 1;
}

std::shared_ptr<SSL_CTX> make_upstream_tls_context(bool verify, std::string* error) {
    auto fail = [&](const std::string& what) -> std::shared_ptr<SSL_CTX> {
        if (error) *error = "TLS vers le backend : " + what;
        return nullptr;
    };
    ERR_clear_error();
    // ssl.SSLContext(PROTOCOL_TLS_CLIENT) : TLS_client_method, puis les options de _ssl__SSLContext_impl.
    std::shared_ptr<SSL_CTX> context(SSL_CTX_new(TLS_client_method()), SSL_CTX_free);
    if (!context) return fail(openssl_errors());
    SSL_CTX* ctx = context.get();
    std::uint64_t options = SSL_OP_ALL & ~static_cast<std::uint64_t>(SSL_OP_DONT_INSERT_EMPTY_FRAGMENTS);
    options |= SSL_OP_NO_SSLv3 | SSL_OP_NO_COMPRESSION | SSL_OP_CIPHER_SERVER_PREFERENCE | SSL_OP_SINGLE_DH_USE |
               SSL_OP_SINGLE_ECDH_USE;
    SSL_CTX_set_options(ctx, options);
    // ACCEPT_MOVING_WRITE_BUFFER et AUTO_RETRY : CPython ; ecritures partielles : socket non bloquante.
    SSL_CTX_set_mode(ctx, SSL_MODE_ACCEPT_MOVING_WRITE_BUFFER | SSL_MODE_AUTO_RETRY | SSL_MODE_ENABLE_PARTIAL_WRITE);
    if (SSL_CTX_set_min_proto_version(ctx, TLS1_2_VERSION) != 1)  // CPython >= 3.10 : TLS 1.2 au minimum
        return fail("version refusee : " + openssl_errors());
    if (SSL_CTX_set_cipher_list(ctx, kPythonDefaultCiphers) != 1)
        return fail("suites de chiffrement refusees : " + openssl_errors());
    X509_VERIFY_PARAM* params = SSL_CTX_get0_param(ctx);
    // TRUSTED_FIRST : CPython ; PARTIAL_CHAIN et X509_STRICT : create_default_context (Python >= 3.13).
    X509_VERIFY_PARAM_set_flags(params, X509_V_FLAG_TRUSTED_FIRST | X509_V_FLAG_PARTIAL_CHAIN | X509_V_FLAG_X509_STRICT);
    X509_VERIFY_PARAM_set_hostflags(params, X509_CHECK_FLAG_NO_PARTIAL_WILDCARDS);  // hostflags par defaut de CPython
    // load_default_certs -> set_default_verify_paths : magasin du systeme, SSL_CERT_FILE et SSL_CERT_DIR compris.
    if (SSL_CTX_set_default_verify_paths(ctx) != 1) return fail("magasin de confiance illisible : " + openssl_errors());
    SSL_CTX_set_verify(ctx, verify ? SSL_VERIFY_PEER : SSL_VERIFY_NONE, nullptr);
    ERR_clear_error();
    return context;
}

SSL* new_upstream_tls(SSL_CTX* context, int fd, const std::string& host, bool verify) {
    ERR_clear_error();
    SSL* ssl = SSL_new(context);
    if (ssl == nullptr) return nullptr;
    if (SSL_set_fd(ssl, fd) != 1) {
        SSL_free(ssl);
        return nullptr;
    }
    // _ssl_configure_hostname : SNI pour un nom seulement ; nom ou adresse verifies si check_hostname.
    const bool ip = is_ip_literal(host);
    bool ok = true;
    if (!ip) ok = SSL_set_tlsext_host_name(ssl, host.c_str()) == 1;
    if (ok && verify) {
        X509_VERIFY_PARAM* params = SSL_get0_param(ssl);
        ok = ip ? X509_VERIFY_PARAM_set1_ip_asc(params, host.c_str()) == 1
                : X509_VERIFY_PARAM_set1_host(params, host.c_str(), host.size()) == 1;
    }
    if (!ok) {
        SSL_free(ssl);
        ERR_clear_error();
        return nullptr;
    }
    SSL_set_connect_state(ssl);
    return ssl;
}

std::string upstream_tls_failure(SSL* ssl, const std::string& host, bool* certificate) {
    *certificate = false;
    const unsigned long code = ERR_peek_last_error();  // fill_and_set_sslerror : derniere erreur de la file
    std::string reason;
    if (code != 0 && ERR_GET_LIB(code) == ERR_LIB_SSL && ERR_GET_REASON(code) == SSL_R_CERTIFICATE_VERIFY_FAILED) {
        *certificate = true;
        const long verify = SSL_get_verify_result(ssl);
        if (verify == X509_V_ERR_HOSTNAME_MISMATCH) {
            reason = "Hostname mismatch, certificate is not valid for '" + host + "'.";
        } else if (verify == X509_V_ERR_IP_ADDRESS_MISMATCH) {
            reason = "IP address mismatch, certificate is not valid for '" + host + "'.";
        } else {
            reason = X509_verify_cert_error_string(verify);
        }
    } else if (code != 0 && !(ERR_GET_LIB(code) == ERR_LIB_SSL &&
                              ERR_GET_REASON(code) == SSL_R_UNEXPECTED_EOF_WHILE_READING)) {
        // SSLError.reason : nom de la raison OpenSSL (« wrong version number » -> WRONG_VERSION_NUMBER).
        if (const char* text = ERR_reason_error_string(code)) {
            for (const char* p = text; *p != '\0'; ++p) {
                reason += *p == ' ' ? '_' : static_cast<char>(std::toupper(static_cast<unsigned char>(*p)));
            }
        }
    }
    ERR_clear_error();
    return reason;
}

void free_upstream_tls(SSL* ssl) {
    if (ssl == nullptr) return;
    if (SSL_is_init_finished(ssl)) {
        ERR_clear_error();
        (void)SSL_shutdown(ssl);  // close_notify, sans attendre celui du backend
    }
    ERR_clear_error();
    SSL_free(ssl);
}

}  // namespace omega

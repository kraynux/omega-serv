// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "tls.hpp"

#include <openssl/err.h>
#include <openssl/ssl.h>

#include <cstdlib>
#include <cstring>

namespace omega {

namespace {

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

int version_constant(const std::string& name) { return name == "TLS1.3" ? TLS1_3_VERSION : TLS1_2_VERSION; }

int passphrase_callback(char* buffer, int size, int /*rwflag*/, void* user_data) {
    const auto* passphrase = static_cast<const std::string*>(user_data);
    if (passphrase == nullptr || passphrase->empty() || static_cast<int>(passphrase->size()) > size) return 0;
    std::memcpy(buffer, passphrase->data(), passphrase->size());
    return static_cast<int>(passphrase->size());
}

}  // namespace

std::shared_ptr<SSL_CTX> make_tls_context(const TlsSettings& settings, std::string* error) {
    auto fail = [&](const std::string& what) -> std::shared_ptr<SSL_CTX> {
        if (error) *error = "TLS : " + what;
        return nullptr;
    };
    ERR_clear_error();
    std::shared_ptr<SSL_CTX> context(SSL_CTX_new(TLS_server_method()), SSL_CTX_free);
    if (!context) return fail(openssl_errors());
    SSL_CTX* ctx = context.get();

    // Modules/_ssl.c (_ssl__SSLContext_impl) : options posees par CPython sur tout nouveau contexte.
    std::uint64_t options = SSL_OP_ALL & ~static_cast<std::uint64_t>(SSL_OP_DONT_INSERT_EMPTY_FRAGMENTS);
    options |= SSL_OP_NO_SSLv3 | SSL_OP_NO_COMPRESSION | SSL_OP_CIPHER_SERVER_PREFERENCE | SSL_OP_SINGLE_DH_USE |
               SSL_OP_SINGLE_ECDH_USE;
    SSL_CTX_set_options(ctx, options);
    // Ecritures partielles (socket non bloquante) ; la meme donnee peut etre repassee depuis une autre adresse.
    SSL_CTX_set_mode(ctx, SSL_MODE_ENABLE_PARTIAL_WRITE | SSL_MODE_ACCEPT_MOVING_WRITE_BUFFER);
    static const unsigned char kSessionContext[] = "Python";  // SSL_CTX_set_session_id_context de CPython
    SSL_CTX_set_session_id_context(ctx, kSessionContext, 6);

    if (SSL_CTX_set_min_proto_version(ctx, version_constant(settings.min_version)) != 1 ||
        SSL_CTX_set_max_proto_version(ctx, version_constant(settings.max_version)) != 1)
        return fail("versions refusees : " + openssl_errors());
    if (SSL_CTX_set_cipher_list(ctx, settings.ciphers.c_str()) != 1)
        return fail("suites de chiffrement refusees : " + openssl_errors());

    std::string passphrase;
    if (!settings.passphrase_env.empty()) {
        if (const char* value = std::getenv(settings.passphrase_env.c_str())) passphrase = value;
    }
    SSL_CTX_set_default_passwd_cb(ctx, passphrase_callback);
    SSL_CTX_set_default_passwd_cb_userdata(ctx, &passphrase);
    const bool loaded = SSL_CTX_use_certificate_chain_file(ctx, settings.certificate.c_str()) == 1 &&
                        SSL_CTX_use_PrivateKey_file(ctx, settings.private_key.c_str(), SSL_FILETYPE_PEM) == 1 &&
                        SSL_CTX_check_private_key(ctx) == 1;
    SSL_CTX_set_default_passwd_cb_userdata(ctx, nullptr);  // la phrase de passe ne sert qu'au chargement
    if (!passphrase.empty()) OPENSSL_cleanse(passphrase.data(), passphrase.size());
    if (!loaded) return fail("certificat ou cle inutilisable (" + settings.certificate + ") : " + openssl_errors());
    return context;
}

}  // namespace omega

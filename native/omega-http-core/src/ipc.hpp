// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Trames du contrat IPC v1 (OMEGA-SERV_CONTRAT_IPC_MOTEUR.md §2-3) - meme encodage que
// src/omega_serv/infrastructure/server/native_ipc.py, verifie sur les memes vecteurs binaires.
// En-tete fixe de 24 octets petit-boutiste + champs TLV (tag u16, longueur u32, valeur brute).
#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace omega::ipc {

inline constexpr std::uint32_t kMagic = 0x4F4D4743;  // « OMGC »
inline constexpr std::uint16_t kContractVersion = 1;
inline constexpr std::size_t kHeaderSize = 24;
inline constexpr std::size_t kMaxPayload = 1u << 20;  // 1 Mio (au-dela : memfd, jamais une trame)

enum MessageType : std::uint16_t {
    kHello = 1,
    kHelloAck = 2,
    kConfig = 3,
    kConfigAck = 4,
    kHealth = 5,
    kShutdown = 6,
    kDataAttach = 7,  // superviseur -> natif : nouveau canal de donnees pour un fil (fd en SCM_RIGHTS)
    kInspect = 10,
    kVerdict = 11,
    kHandoff = 12,  // natif -> Python : connexion confiee (socket client + octets deja lus) - lot 6
    kHandoffDone = 13,  // Python -> natif : connexion rendue apres une reponse (plan proxy natif v2, lot 4, D12)
    kWatch = 14,    // Python -> natif : sources a toujours inspecter (plan WAF natif, lot 3)
    kBackendEvent = 15,  // Python (processus n° 0) -> natif : sonde, score de charge, etat manuel (proxy natif, lot 6)
    kBackendState = 16,  // natif -> Python (canal n° 0) : etat des backends, environ 1 fois/s (lot 6, Q7)
    kError = 20,
};

// Tags par message (contrat §3.5).
namespace tag {
// HELLO
inline constexpr std::uint16_t kHelloContract = 1;    // u16
inline constexpr std::uint16_t kHelloBinary = 2;      // texte
inline constexpr std::uint16_t kHelloCapability = 3;  // texte, repete
inline constexpr std::uint16_t kHelloPid = 4;         // u32
// HELLO_ACK
inline constexpr std::uint16_t kAckAccepted = 1;  // u8
inline constexpr std::uint16_t kAckReason = 2;    // texte
// CONFIG (instantane JSON dans un memfd scelle, transmis en SCM_RIGHTS)
inline constexpr std::uint16_t kConfigSize = 1;    // u64
inline constexpr std::uint16_t kConfigSha256 = 2;  // 32 octets
// CONFIG_ACK
inline constexpr std::uint16_t kConfigOk = 1;     // u8
inline constexpr std::uint16_t kConfigError = 2;  // texte, repete
// HEALTH
inline constexpr std::uint16_t kHealthConnections = 1;  // u64
inline constexpr std::uint16_t kHealthRequests = 2;     // u64
inline constexpr std::uint16_t kHealthRejected = 3;     // u64
inline constexpr std::uint16_t kHealthGeneration = 4;   // u32
// Plan proxy natif v2, lot 4 : relais natif (C2 : budgets en cours ; Q7 : compteurs remontes environ 1 fois/s)
inline constexpr std::uint16_t kHealthProxyRelayed = 5;        // u64 : requetes relayees par le natif (cumul)
inline constexpr std::uint16_t kHealthProxyPendingBody = 6;    // u64 : octets de corps en attente
inline constexpr std::uint16_t kHealthProxyInspections = 7;    // u64 : INSPECT du relais en attente
inline constexpr std::uint16_t kHealthUpstreamConnections = 8; // u64 : connexions ouvertes vers les backends
inline constexpr std::uint16_t kHealthUpstreamRetries = 9;     // u64 : nouveaux essais (cumul, lot 5)
inline constexpr std::uint16_t kHealthUpstreamIdle = 10;       // u64 : connexions inactives du pool (lot 5)
inline constexpr std::uint16_t kHealthBytesIn = 11;            // u64 : octets recus des visiteurs (cumul, lot 9b)
inline constexpr std::uint16_t kHealthBytesOut = 12;           // u64 : octets envoyes aux visiteurs (cumul, lot 9b)
// SHUTDOWN
inline constexpr std::uint16_t kShutdownGraceMs = 1;  // u32
// ERROR
inline constexpr std::uint16_t kErrorCode = 1;     // u16
inline constexpr std::uint16_t kErrorMessage = 2;  // texte
// DATA_ATTACH
inline constexpr std::uint16_t kAttachThread = 1;  // u32 : rang du fil natif
// INSPECT (request_id de l'en-tete = identifiant de la requete, 16 chiffres hexa du journal)
inline constexpr std::uint16_t kInspectPeer = 1;     // texte : IP du pair TCP
inline constexpr std::uint16_t kInspectMethod = 2;   // octets bruts (latin-1)
inline constexpr std::uint16_t kInspectTarget = 3;   // octets bruts
inline constexpr std::uint16_t kInspectVersion = 4;  // octets bruts
inline constexpr std::uint16_t kInspectHeader = 5;   // nom\0valeur, repete, ordre et casse d'origine
inline constexpr std::uint16_t kInspectBody = 6;     // corps capture (absent : pas de capture)
inline constexpr std::uint16_t kInspectDelegate = 7; // u8 1 : route deleguee (listing, /load, /admin) - Python
inline constexpr std::uint16_t kInspectClientIp = 8; // texte : IP cliente resolue (trusted_proxy) - lot 8
inline constexpr std::uint16_t kInspectBlocklistClear = 9;  // u8 1 : etat ACTUEL de la blocklist lu, adresse absente
inline constexpr std::uint16_t kInspectAudit = 10;  // u8 1 : jugee propre par le filtre WAF, envoyee pour controle (1/N)
inline constexpr std::uint16_t kInspectRateLimit = 11;  // u32 : limite de debit comptee par le natif - 0 autorisee, N = Retry-After (s)
inline constexpr std::uint16_t kInspectBodyFd = 12;  // u64 : taille du corps capture passe par memfd (fd 1), plan
                                                    // proxy natif v2, lot 4 (S23) - remplace kInspectBody
                                                     // repond par route_request, pas par l'etape de securite
// HANDOFF (fd 1 = socket du client ; fd 2 optionnel = memfd des octets deja lus s'ils sont trop gros pour la trame)
inline constexpr std::uint16_t kHandoffBytes = 1;     // octets deja lus et non traites (tete de la requete comprise)
inline constexpr std::uint16_t kHandoffServed = 2;    // u32 : requetes deja servies sur cette connexion (keep-alive)
inline constexpr std::uint16_t kHandoffBytesFd = 3;   // u64 : taille des octets passes par memfd (fd 2)
inline constexpr std::uint16_t kHandoffRateLimit = 4;  // u32 : limite de debit comptee par le natif pour la requete
                                                      // confiee - 0 autorisee, N = Retry-After (s) (lot 4, D12)
// HANDOFF_DONE (fd 1 = socket du client) : Python rend la connexion au natif apres sa reponse (keep-alive)
inline constexpr std::uint16_t kHandoffDoneBytes = 1;   // octets deja lus par Python (requete suivante), peut etre vide
inline constexpr std::uint16_t kHandoffDoneServed = 2;  // u32 : requetes servies sur la connexion
// VERDICT
inline constexpr std::uint16_t kVerdictDecision = 1;   // u8 : 1 continuer (routage natif), 2 repondre,
                                                       //      3 abandonner (exception Python : fermeture sans reponse)
inline constexpr std::uint16_t kVerdictStatus = 2;     // u16
inline constexpr std::uint16_t kVerdictHeader = 3;     // nom\0valeur, repete, dans l'ordre de la reponse Python
inline constexpr std::uint16_t kVerdictBody = 4;       // octets
inline constexpr std::uint16_t kVerdictKeepAlive = 5;  // u8 : keep-alive permis (leurre) ou non (blocage)
inline constexpr std::uint16_t kVerdictFile = 6;       // texte : corps lu dans ce fichier
inline constexpr std::uint16_t kVerdictFileOffset = 7; // u64
inline constexpr std::uint16_t kVerdictFileLength = 8; // u64
// Plan proxy natif v2, lot 6 (P5, S26) : source que ce verdict fait surveiller (« adresse\0echeance », repete),
// appliquee avant le verdict lui-meme - la requete suivante de la source est inspectee, sur tous les fils.
inline constexpr std::uint16_t kVerdictWatch = 9;
// BACKEND_EVENT : « zone\0nom\0probe|load|manual\0valeur », repete. BACKEND_STATE : « zone\0cle\0nom\0etat\0actives ».
// Tableau de bord (2026-11-16) : BACKEND_STATE ajoute « \0requetes\0erreurs502\0erreurs504\0moyenne_us » (-1 : jamais).
inline constexpr std::uint16_t kBackendEntry = 1;
inline constexpr std::uint16_t kWatchEntry = 1;  // texte « adresse\0echeance » (secondes Unix), repete
}  // namespace tag

struct Frame {
    std::uint16_t type = 0;
    std::uint64_t request_id = 0;
    std::uint32_t generation = 0;
    std::vector<std::pair<std::uint16_t, std::string>> fields;

    void add(std::uint16_t tag, std::string value) { fields.emplace_back(tag, std::move(value)); }
    void add_u8(std::uint16_t tag, std::uint8_t value);
    void add_u16(std::uint16_t tag, std::uint16_t value);
    void add_u32(std::uint16_t tag, std::uint32_t value);
    void add_u64(std::uint16_t tag, std::uint64_t value);

    [[nodiscard]] const std::string* first(std::uint16_t tag) const;
    [[nodiscard]] std::vector<std::string> all(std::uint16_t tag) const;
    [[nodiscard]] std::optional<std::uint64_t> unsigned_field(std::uint16_t tag) const;  // u8/u16/u32/u64
};

std::string encode(const Frame& frame);
// false + raison : magic, version, longueur annoncee, TLV debordant. Un tag inconnu est garde (ignore plus haut).
bool decode(std::string_view data, Frame& frame, std::string* error);

// Envoi / reception d'une trame sur une socket SOCK_SEQPACKET, avec au plus un fd en SCM_RIGHTS.
// recv : 0 = trame lue, 1 = fin du canal (pair parti), -1 = erreur (raison dans `error`).
bool send_frame(int socket_fd, const Frame& frame, int pass_fd = -1);
int recv_frame(int socket_fd, Frame& frame, int* received_fd, std::string* error);
// Envoi / reception sans attente (canal de donnees, dans la boucle epoll d'un fil).
// send : 0 envoye, 1 a reessayer (EAGAIN), 2 trame refusee par le noyau (EMSGSIZE : plus grande que le tampon
// d'envoi du canal - le canal reste bon), -1 erreur. recv : comme recv_frame, plus 2 = rien a lire (EAGAIN).
int send_encoded_nowait(int socket_fd, const std::string& encoded, const std::vector<int>& fds = {});
int recv_frame_nowait(int socket_fd, Frame& frame, std::string* error);
// Idem, avec au plus un descripteur recu (SCM_RIGHTS) dans `received_fd` (-1 sinon) ; tout autre est ferme.
int recv_frame_nowait(int socket_fd, Frame& frame, int* received_fd, std::string* error);

}  // namespace omega::ipc

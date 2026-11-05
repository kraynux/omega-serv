// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
//
// Filtre WAF du moteur natif (OMEGA-SERV_PLAN-DETAILLE_WAF_NATIF.md, lot 1). Il ne juge pas : il reconnait
// seulement une requete sur laquelle AUCUNE regle ne peut correspondre. Tout le reste (correspondance, texte non
// ASCII, regle non evaluable ici, erreur PCRE2) est un « doute » : la requete part au processus Python, qui decide
// comme toujours. Les motifs viennent de Python (section `waf_filter` de l'instantane, retraduits depuis l'arbre de
// `re` : classes ASCII explicites, sans option de compilation) ; ce module ne les interprete jamais.
//
// Textes inspectes : PythonWafEngine._build_scope_texts, a l'identique pour un texte ASCII.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "engine.hpp"
#include "rate_limiter.hpp"
#include "util.hpp"

namespace omega {

enum class WafScope : std::size_t { path, query, headers, user_agent, referer, body, count };
inline constexpr std::size_t kWafScopeCount = static_cast<std::size_t>(WafScope::count);

// Textes d'une requete par scope ; absent (nullopt) ou vide = rien a inspecter pour ce scope (`if not text`).
using WafScopeTexts = std::array<std::optional<std::string>, kWafScopeCount>;

enum class WafFilterOutcome { clean, match, doubt };

// normalization.py::decode_bounded_for_inspection pour un texte ASCII : au plus max(1, max_passes) decodages « % »
// (urllib.parse.unquote), arret des que le texte ne change plus. nullopt si un octet non ASCII apparait (texte ou
// resultat d'un decodage) : Python appliquerait alors NFKC, que le natif ne fait pas -> doute.
std::optional<std::string> decode_ascii_for_inspection(std::string_view raw, int max_passes);

class WafFilter {
public:
    // Section `waf_filter` (deja validee par Python). Structure invalide -> exception (instantane refuse, comme les
    // autres sections) ; motif refuse par PCRE2 -> regle traitee comme non exportee (doute), raison dans
    // compile_errors().
    static std::shared_ptr<const WafFilter> from_json(const Json& section);
    ~WafFilter();
    WafFilter(const WafFilter&) = delete;
    WafFilter& operator=(const WafFilter&) = delete;

    [[nodiscard]] bool available() const { return available_; }
    // Lot 2 : le natif peut-il servir seul une requete propre ? Faux si une fonction demande Python pour chaque
    // requete (magnet, limite de debit, leurres, zones illisibles) ; `python_reason` dit laquelle (code).
    // Lot 3 : `native_decides_with_watch` (leurres actifs) - decision seule permise pour une source non suivie.
    // Lot 6 : `native_decides_with_rate_limit` (limite de debit et/ou leurres actifs) - decision seule permise si le
    // natif compte lui-meme la limite (rate_policy) et connait les sources suivies.
    [[nodiscard]] bool decides_alone() const {
        return available_ && (native_decides_ || native_decides_with_watch_ || (native_decides_with_rate_limit_ && rate_policy_));
    }
    // Lot 6 : limite de debit a compter ici pour TOUTES les requetes (nullptr : desactivee, ou Python compte).
    [[nodiscard]] const RatePolicy* rate_policy() const { return rate_policy_.get(); }
    [[nodiscard]] const std::string& python_reason() const { return python_reason_; }
    // Zone Auth : zone_resolver.path_matches_prefix sur le chemin, et aussi sur le chemin decode (sur-ensemble).
    [[nodiscard]] bool in_protected_zone(std::string_view path_text) const;
    [[nodiscard]] std::size_t exported_count() const { return rules_.size(); }
    [[nodiscard]] std::size_t python_only_count() const { return python_only_.size(); }
    [[nodiscard]] const std::vector<std::string>& compile_errors() const { return compile_errors_; }
    // Toutes les regles confiees a Python, avec la raison (motif refuse, controle en desaccord, non traduite) :
    // une ligne au journal d'erreurs par regle, a chaque instantane installe.
    [[nodiscard]] const std::vector<std::string>& python_only_reasons() const { return python_only_reasons_; }
    // Lot 4 : controle 1/N (0 = jamais) - une requete propre sur N est quand meme soumise a Python.
    [[nodiscard]] std::uint32_t check_every() const { return check_every_; }

    // Textes a inspecter ; nullopt = doute (texte non ASCII, en-tetes ou corps a inspecter : V1 -> Python).
    // `body_inspected` : un corps non vide a ete capture pour une methode de waf.inspect.body_methods.
    [[nodiscard]] std::optional<WafScopeTexts> prepare(const Request& request, bool body_inspected) const;

    [[nodiscard]] WafFilterOutcome evaluate(const WafScopeTexts& texts) const;
    // Identifiants des regles exportees qui correspondent (tests et vecteurs) ; nullopt si erreur PCRE2.
    [[nodiscard]] std::optional<std::vector<std::string>> matching_rules(const WafScopeTexts& texts) const;

private:
    struct Rule;
    WafFilter() = default;

    bool available_ = false;
    int decode_depth_ = 2;
    bool inspect_path_ = true;
    bool inspect_query_ = true;
    bool inspect_headers_ = false;
    bool native_decides_ = false;
    bool native_decides_with_watch_ = false;
    bool native_decides_with_rate_limit_ = false;
    std::shared_ptr<const RatePolicy> rate_policy_;
    std::string python_reason_;
    std::vector<std::string> auth_prefixes_;  // deja normalises (« / » -> vide, « / » final retire)
    std::array<bool, kWafScopeCount> used_{};  // scope lu par au moins une regle (exportee ou non)
    std::vector<std::unique_ptr<Rule>> rules_;
    std::vector<std::vector<WafScope>> python_only_;  // scopes des regles que seul Python evalue
    std::vector<std::string> compile_errors_;
    std::vector<std::string> python_only_reasons_;
    std::uint32_t check_every_ = 0;
};

}  // namespace omega

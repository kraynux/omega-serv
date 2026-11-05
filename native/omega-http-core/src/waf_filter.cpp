// Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
#include "waf_filter.hpp"

#include <stdexcept>

#ifdef OMEGA_HAS_PCRE2
#include <pcre2.h>
#endif

namespace omega {

namespace {

constexpr std::array<std::string_view, kWafScopeCount> kScopeNames = {"path", "query", "headers", "user_agent",
                                                                     "referer", "body"};

std::optional<WafScope> scope_from_name(std::string_view name) {
    for (std::size_t i = 0; i < kWafScopeCount; ++i) {
        if (kScopeNames[i] == name) return static_cast<WafScope>(i);
    }
    return std::nullopt;  // scope que Python ne construit jamais : la regle n'y lit rien, ici non plus
}

bool is_ascii(std::string_view text) {
    for (const char c : text) {
        if (static_cast<unsigned char>(c) >= 0x80) return false;
    }
    return true;
}

int hex_value(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// urllib.parse.unquote_to_bytes : « %XX » (deux chiffres hexadecimaux) -> octet, tout autre « % » garde tel quel.
std::string percent_decode(std::string_view text) {
    std::string out;
    out.reserve(text.size());
    for (std::size_t i = 0; i < text.size(); ++i) {
        if (text[i] == '%' && i + 2 < text.size()) {
            const int high = hex_value(text[i + 1]);
            const int low = hex_value(text[i + 2]);
            if (high >= 0 && low >= 0) {
                out.push_back(static_cast<char>(high * 16 + low));
                i += 2;
                continue;
            }
        }
        out.push_back(text[i]);
    }
    return out;
}

[[maybe_unused]] std::string ascii_lower(std::string_view text) {
    std::string out(text);
    for (char& c : out) {
        if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
    }
    return out;
}

const Json& need_field(const Json& object, std::string_view key) {
    const Json* value = object.get(key);
    if (value == nullptr) throw std::runtime_error("waf_filter." + std::string(key) + " manquant");
    return *value;
}

[[maybe_unused]] bool need_flag(const Json& object, std::string_view key) {
    const Json& value = need_field(object, key);
    if (!std::holds_alternative<bool>(value.value)) throw std::runtime_error("waf_filter." + std::string(key) + " : booleen attendu");
    return std::get<bool>(value.value);
}

[[maybe_unused]] std::vector<WafScope> scopes_of(const Json& rule) {
    if (!need_field(rule, "scopes").is_array()) throw std::runtime_error("waf_filter : scopes attendus");
    std::vector<WafScope> scopes;
    for (const Json& name : rule.array("scopes")) {
        if (!name.is_string()) throw std::runtime_error("waf_filter : scope non textuel");
        if (const auto scope = scope_from_name(name.as_string())) scopes.push_back(*scope);
    }
    return scopes;
}

[[maybe_unused]] int need_count(const Json& object, std::string_view key, int maximum) {
    const Json& value = need_field(object, key);
    if (!std::holds_alternative<double>(value.value)) throw std::runtime_error("waf_filter." + std::string(key) + " : entier attendu");
    const double number = std::get<double>(value.value);
    if (number < 0 || number > maximum || number != static_cast<double>(static_cast<int>(number)))
        throw std::runtime_error("waf_filter." + std::string(key) + " hors limites");
    return static_cast<int>(number);
}

[[maybe_unused]] int need_small_integer(const Json& object, std::string_view key) {
    const Json& value = need_field(object, key);
    if (!std::holds_alternative<double>(value.value)) throw std::runtime_error("waf_filter." + std::string(key) + " : entier attendu");
    const double number = std::get<double>(value.value);
    if (number < 0 || number > 100 || number != static_cast<double>(static_cast<int>(number)))
        throw std::runtime_error("waf_filter." + std::string(key) + " hors limites");
    return static_cast<int>(number);
}

}  // namespace

std::optional<std::string> decode_ascii_for_inspection(std::string_view raw, int max_passes) {
    if (!is_ascii(raw)) return std::nullopt;
    std::string current(raw);
    if (current.find('%') == std::string::npos) return current;  // meme raccourci que Python (resultat identique)
    const int passes = max_passes < 1 ? 1 : max_passes;
    for (int pass = 0; pass < passes; ++pass) {
        std::string decoded = percent_decode(current);
        if (!is_ascii(decoded)) return std::nullopt;
        if (decoded == current) break;
        current = std::move(decoded);
    }
    return current;
}

#ifdef OMEGA_HAS_PCRE2

struct WafFilter::Rule {
    std::string id;
    std::vector<WafScope> scopes;
    pcre2_code* pattern = nullptr;
    pcre2_code* exclude = nullptr;
    bool lowered = false;

    ~Rule() {
        if (pattern != nullptr) pcre2_code_free(pattern);
        if (exclude != nullptr) pcre2_code_free(exclude);
    }
};

namespace {

// Motif sans option : la semantique (casse, classes, ancres) est entierement ecrite dans le motif par Python.
pcre2_code* compile_pattern(const std::string& pattern, std::string* error) {
    int code = 0;
    PCRE2_SIZE offset = 0;
    pcre2_code* compiled = pcre2_compile(reinterpret_cast<PCRE2_SPTR>(pattern.data()), pattern.size(), 0, &code,
                                         &offset, nullptr);
    if (compiled == nullptr) {
        PCRE2_UCHAR message[256];
        pcre2_get_error_message(code, message, sizeof message);
        *error = std::string(reinterpret_cast<const char*>(message)) + " (position " + std::to_string(offset) + ")";
        return nullptr;
    }
    pcre2_jit_compile(compiled, PCRE2_JIT_COMPLETE);  // sans JIT (non disponible) : interpreteur, meme resultat
    return compiled;
}

struct MatchState {
    pcre2_match_data* data = nullptr;
    pcre2_match_context* context = nullptr;
    MatchState() {
        data = pcre2_match_data_create(1, nullptr);
        context = pcre2_match_context_create(nullptr);
        // Motif trop couteux sur ce texte -> erreur -> doute (Python decide, meme exposition qu'aujourd'hui).
        pcre2_set_match_limit(context, 200000);
        pcre2_set_depth_limit(context, 10000);
    }
    ~MatchState() {
        pcre2_match_data_free(data);
        pcre2_match_context_free(context);
    }
    MatchState(const MatchState&) = delete;
    MatchState& operator=(const MatchState&) = delete;
};

// 1 : correspondance, 0 : aucune, -1 : erreur (limite, memoire) -> doute.
int search(const pcre2_code* code, const std::string& text) {
    thread_local MatchState state;
    const int result = pcre2_match(code, reinterpret_cast<PCRE2_SPTR>(text.data()), text.size(), 0, 0, state.data,
                                   state.context);
    if (result >= 0) return 1;
    return result == PCRE2_ERROR_NOMATCH ? 0 : -1;
}

}  // namespace

WafFilter::~WafFilter() = default;

namespace {

// Vide si tous les controles concordent ; sinon la raison (premier texte en desaccord, ou erreur de recherche).
const JsonArray& items_of(const Json& value) { return *std::get<std::shared_ptr<JsonArray>>(value.value); }

std::string check_controls(const pcre2_code* pattern, const pcre2_code* exclude, bool lowered, const Json& rule_json) {
    const Json* controls = rule_json.get("controls");
    if (controls == nullptr || controls->is_null()) return {};
    if (!controls->is_array()) throw std::runtime_error("waf_filter.controls : liste attendue");
    for (const Json& control : rule_json.array("controls")) {
        if (!control.is_array() || items_of(control).size() != 2 || !items_of(control)[0].is_string() ||
            !std::holds_alternative<bool>(items_of(control)[1].value))
            throw std::runtime_error("waf_filter.controls : [texte, booleen] attendu");
        const std::string& text = items_of(control)[0].as_string();
        const bool expected = std::get<bool>(items_of(control)[1].value);
        if (!is_ascii(text)) continue;  // jamais juge par le natif
        const std::string subject = lowered ? ascii_lower(text) : text;
        const int hit = search(pattern, subject);
        int excluded = 0;
        if (hit == 1 && exclude != nullptr) excluded = search(exclude, subject);
        if (hit < 0 || excluded < 0) return "controle impossible (erreur PCRE2)";
        if ((hit == 1 && excluded == 0) != expected) return "controle en desaccord avec Python";
    }
    return {};
}

}  // namespace

std::shared_ptr<const WafFilter> WafFilter::from_json(const Json& section) {
    std::shared_ptr<WafFilter> filter(new WafFilter());
    filter->available_ = need_flag(section, "available");
    if (!filter->available_) return filter;
    filter->decode_depth_ = need_small_integer(section, "decode_depth");
    filter->inspect_path_ = need_flag(section, "inspect_path");
    filter->inspect_query_ = need_flag(section, "inspect_query");
    filter->inspect_headers_ = need_flag(section, "inspect_headers");
    filter->native_decides_ = need_flag(section, "native_decides");
    filter->native_decides_with_watch_ = need_flag(section, "native_decides_with_watch");
    // Lot 6 : champs absents d'un instantane plus ancien -> Python compte, comme avant.
    if (const Json* flag = section.get("native_decides_with_rate_limit"); flag != nullptr && !flag->is_null())
        filter->native_decides_with_rate_limit_ = need_flag(section, "native_decides_with_rate_limit");
    if (const Json* rate = section.get("rate_limit"); rate != nullptr && !rate->is_null())
        filter->rate_policy_ = RatePolicy::from_json(*rate);
    if (const Json& reason = need_field(section, "python_reason"); reason.is_string()) filter->python_reason_ = reason.as_string();
    if (!need_field(section, "auth_prefixes").is_array()) throw std::runtime_error("waf_filter.auth_prefixes : liste attendue");
    for (const Json& prefix : section.array("auth_prefixes")) {
        if (!prefix.is_string()) throw std::runtime_error("waf_filter.auth_prefixes : texte attendu");
        std::string normalized = prefix.as_string() == "/" ? std::string() : prefix.as_string();
        while (!normalized.empty() && normalized.back() == '/') normalized.pop_back();
        filter->auth_prefixes_.push_back(std::move(normalized));
    }
    if (!need_field(section, "rules").is_array() || !need_field(section, "unexported").is_array())
        throw std::runtime_error("waf_filter : listes rules / unexported attendues");
    for (const Json& rule_json : section.array("rules")) {
        auto rule = std::make_unique<Rule>();
        rule->id = need_field(rule_json, "id").as_string();
        rule->scopes = scopes_of(rule_json);
        rule->lowered = need_flag(rule_json, "lowered");
        for (const WafScope scope : rule->scopes) filter->used_[static_cast<std::size_t>(scope)] = true;
        std::string error;
        rule->pattern = compile_pattern(need_field(rule_json, "pattern").as_string(), &error);
        const Json& exclude = need_field(rule_json, "exclude");
        if (rule->pattern != nullptr && exclude.is_string()) rule->exclude = compile_pattern(exclude.as_string(), &error);
        if (rule->pattern == nullptr || (exclude.is_string() && rule->exclude == nullptr)) {
            filter->compile_errors_.push_back(rule->id + " : " + error);
            filter->python_only_reasons_.push_back(rule->id + " : motif refuse par PCRE2 (" + error + ")");
            filter->python_only_.push_back(rule->scopes);  // jamais ignoree : ses requetes vont a Python
            continue;
        }
        // Lot 4 : textes de controle calcules par Python ; un seul desaccord -> regle confiee a Python.
        if (const std::string mismatch = check_controls(rule->pattern, rule->exclude, rule->lowered, rule_json);
            !mismatch.empty()) {
            filter->compile_errors_.push_back(rule->id + " : " + mismatch);
            filter->python_only_reasons_.push_back(rule->id + " : " + mismatch);
            filter->python_only_.push_back(rule->scopes);
            continue;
        }
        filter->rules_.push_back(std::move(rule));
    }
    for (const Json& rule_json : section.array("unexported")) {
        filter->python_only_.push_back(scopes_of(rule_json));
        for (const WafScope scope : filter->python_only_.back()) filter->used_[static_cast<std::size_t>(scope)] = true;
        const Json* reason = rule_json.get("reason");
        filter->python_only_reasons_.push_back(need_field(rule_json, "id").as_string() + " : non traduite (" +
                                               (reason != nullptr && reason->is_string() ? reason->as_string() : "?") + ")");
    }
    if (const Json* every = section.get("check_every"); every != nullptr && !every->is_null())
        filter->check_every_ = static_cast<std::uint32_t>(need_count(section, "check_every", 1000000));
    return filter;
}

std::optional<std::vector<std::string>> WafFilter::matching_rules(const WafScopeTexts& texts) const {
    std::array<std::string, kWafScopeCount> lowered;
    std::array<bool, kWafScopeCount> lowered_ready{};
    std::vector<std::string> found;
    for (const auto& rule : rules_) {
        for (const WafScope scope : rule->scopes) {
            const std::size_t index = static_cast<std::size_t>(scope);
            const std::optional<std::string>& text = texts[index];
            if (!text || text->empty()) continue;
            const std::string* subject = &*text;
            if (rule->lowered) {
                if (!lowered_ready[index]) {
                    lowered[index] = ascii_lower(*text);
                    lowered_ready[index] = true;
                }
                subject = &lowered[index];
            }
            const int hit = search(rule->pattern, *subject);
            if (hit < 0) return std::nullopt;
            if (hit == 0) continue;
            if (rule->exclude != nullptr) {
                const int excluded = search(rule->exclude, *subject);
                if (excluded < 0) return std::nullopt;
                if (excluded == 1) continue;
            }
            found.push_back(rule->id);
            break;  // une regle ne compte qu'une fois par requete
        }
    }
    return found;
}

#else  // sans PCRE2 : aucun filtre, toute requete va a Python (comportement d'avant le filtre)

struct WafFilter::Rule {};

WafFilter::~WafFilter() = default;

std::shared_ptr<const WafFilter> WafFilter::from_json(const Json& /*section*/) {
    return std::shared_ptr<WafFilter>(new WafFilter());  // available_ = false
}

std::optional<std::vector<std::string>> WafFilter::matching_rules(const WafScopeTexts& /*texts*/) const {
    return std::nullopt;
}

#endif

bool WafFilter::in_protected_zone(std::string_view path_text) const {
    auto matches = [this](std::string_view path) {
        for (const std::string& prefix : auth_prefixes_) {
            if (prefix.empty() || path == prefix ||
                (path.size() > prefix.size() && path.substr(0, prefix.size()) == prefix && path[prefix.size()] == '/'))
                return true;
        }
        return false;
    };
    if (auth_prefixes_.empty()) return false;
    if (matches(path_text)) return true;
    const auto decoded = decode_ascii_for_inspection(path_text, decode_depth_);
    return !decoded || matches(*decoded);  // chemin non decodable en ASCII : Python tranche
}

std::optional<WafScopeTexts> WafFilter::prepare(const Request& request, bool body_inspected) const {
    if (!available_) return std::nullopt;
    WafScopeTexts texts;
    auto used = [this](WafScope scope) { return used_[static_cast<std::size_t>(scope)]; };
    if (inspect_path_ && used(WafScope::path)) {
        auto text = decode_ascii_for_inspection(request.path_text, decode_depth_);
        if (!text) return std::nullopt;
        texts[static_cast<std::size_t>(WafScope::path)] = std::move(text);
    }
    if (inspect_query_ && used(WafScope::query)) {
        auto text = decode_ascii_for_inspection(request.query_text, decode_depth_);
        if (!text) return std::nullopt;
        texts[static_cast<std::size_t>(WafScope::query)] = std::move(text);
    }
    if (inspect_headers_ && used(WafScope::headers)) return std::nullopt;  // V1 : en-tetes inspectes -> Python
    for (const auto& [scope, name] : {std::pair{WafScope::user_agent, std::string_view("user-agent")},
                                      std::pair{WafScope::referer, std::string_view("referer")}}) {
        if (!used(scope)) continue;
        const std::string* value = request.header(name);  // derniere valeur, comme HttpHeaders
        if (value == nullptr || value->empty()) continue;
        if (!is_ascii(*value)) return std::nullopt;
        texts[static_cast<std::size_t>(scope)] = *value;
    }
    if (body_inspected && used(WafScope::body)) return std::nullopt;  // V1 : corps inspecte -> Python
    return texts;
}

WafFilterOutcome WafFilter::evaluate(const WafScopeTexts& texts) const {
    if (!available_) return WafFilterOutcome::doubt;
    for (const auto& scopes : python_only_) {
        for (const WafScope scope : scopes) {
            const auto& text = texts[static_cast<std::size_t>(scope)];
            if (text && !text->empty()) return WafFilterOutcome::doubt;  // regle que seul Python sait evaluer
        }
    }
    const auto found = matching_rules(texts);
    if (!found) return WafFilterOutcome::doubt;
    return found->empty() ? WafFilterOutcome::clean : WafFilterOutcome::match;
}

}  // namespace omega

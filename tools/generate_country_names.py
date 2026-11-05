# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Genere src/omega_serv/domain/declaration/country_names.json depuis le paquet systeme
iso-codes (ISO 3166-1, noms traduits par le projet Debian iso-codes, LGPL-2.1+).

Outil de maintenance (machine de developpement) : omega-serv ne lit jamais iso-codes a
l'execution, seulement le JSON genere. Nom courant (ex. « Corée du Sud ») prefere au nom
officiel (« Corée, République de ») quand la langue le traduit.

    python3 tools/generate_country_names.py [/usr/share/iso-codes/json] [/usr/share/locale]"""
from __future__ import annotations

import gettext
import json
import sys
from pathlib import Path

LANGUAGES = ("fr", "en", "de", "es", "it", "pt_BR", "nl", "pl", "ru", "zh_CN",
             "vi", "th", "id", "ja", "ko", "hi", "ar")
OUTPUT = Path(__file__).resolve().parent.parent / "src" / "omega_serv" / "domain" / "declaration" / "country_names.json"


def main() -> int:
    json_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/usr/share/iso-codes/json")
    locale_dir = sys.argv[2] if len(sys.argv) > 2 else "/usr/share/locale"
    countries = json.loads((json_dir / "iso_3166-1.json").read_text(encoding="utf-8"))["3166-1"]
    names: dict[str, dict[str, str]] = {}
    for language in LANGUAGES:
        translation: gettext.NullTranslations = (
            gettext.NullTranslations() if language == "en"
            else gettext.translation("iso_3166-1", locale_dir, [language])
        )
        table: dict[str, str] = {}
        for country in countries:
            common = country.get("common_name")
            translated_common = translation.gettext(common) if common else None
            if common and (language == "en" or translated_common != common):
                table[country["alpha_2"]] = translated_common or common
            else:
                table[country["alpha_2"]] = translation.gettext(country["name"])
        names[language] = dict(sorted(table.items()))
    payload = {
        "_source": "iso-codes (ISO 3166-1), Debian iso-codes project, LGPL-2.1+ - genere par tools/generate_country_names.py",
        "names": names,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print(f"{OUTPUT} : {len(countries)} pays x {len(LANGUAGES)} langues")
    return 0


if __name__ == "__main__":
    sys.exit(main())

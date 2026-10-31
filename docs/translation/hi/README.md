<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**स्वतंत्र, पोर्टेबल और डिफ़ॉल्ट रूप से मज़बूत किया गया HTTP वेब सर्वर**

> [kraynux](https://github.com/kraynux) द्वारा [Omega-Server](https://kraynux.snake-mackarel.ts.net) के लिए विकसित   

आधिकारिक पेज: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/hi/) &nbsp; संदर्भ, उपयोग, सहायता और FAQ: [पूर्ण गाइड](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/hi/guide.html)  
झलक: [स्क्रीनशॉट](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; डेमो [डेमो सर्वर](https://craftdark.snake-mackarel.ts.net) &nbsp; [वेब सर्वरों की तुलना/परीक्षण](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![HTML](https://img.shields.io/badge/HTML-5-E34F26.svg)](https://developer.mozilla.org/docs/Web/HTML)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-उपयोग)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 दस्तावेज़, एक्सपोर्ट और इंटरफ़ेस **17 भाषाओं** में उपलब्ध — देखें [इंटरफ़ेस की भाषाएँ](#इंटरफ़ेस-की-भाषाएँ)।  
**भाषाएँ:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** शुद्ध Python में लिखा गया एक HTTP/1.1 सर्वर है (सर्वर के मूल भाग के लिए केवल मानक लाइब्रेरी), जिसे स्थैतिक सामग्री और, वैकल्पिक रूप से, PHP-FPM परोसने के लिए बनाया गया है। इसमें प्रोटोकॉल की ऐसी मज़बूती है जिसे बंद नहीं किया जा सकता, और सुरक्षा मॉड्यूल (WAF, TLS, प्रमाणीकरण) थोपे नहीं जाते बल्कि ज़रूरत के अनुसार ऊपर जोड़े जाते हैं। `omega-` सूट का सातवाँ टूल, लेकिन जानबूझकर **भविष्य के `omega-suite` एकीकरण से बाहर** (यह दूरस्थ लक्ष्यों पर नहीं, बल्कि उसे चलाने वाली स्थानीय मशीन पर काम करता है — `omega-fire` वाले परिवार का); Clean Architecture में संरचित, जहाँ `bootstrap/` composition root का काम करता है।

## 1. दृष्टि और दायरा

घोषित प्राथमिकता है **पहले HTTP कोर की मज़बूती/सुरक्षा** — WAF और TLS ऊपर रखे जाने वाले वैकल्पिक मॉड्यूल हैं, कभी पूर्व-आवश्यकता नहीं। ऐसा सर्वर जो एक ही काम करता है (फ़ाइलें परोसना, संभवतः PHP) लेकिन उसे सही ढंग से, ऐसी असली प्रोटोकॉल मज़बूती के साथ करता है जिसे दरकिनार न किया जा सके — बजाय ऐसे सर्वर के जो बहुत कुछ आधा-अधूरा करता हो।

### OMEGA-SERV क्या करता है

- स्थैतिक सामग्री परोसता है (फ़ाइलें, वैकल्पिक डायरेक्टरी सूची, alias, redirect, rewrite, कैश) सुरक्षित पाथ रिज़ॉल्यूशन के साथ (traversal, दोहरी एन्कोडिंग, symbolic links)। बड़ी फ़ाइलें डिस्क से ब्लॉक में भेजी जाती हैं, कभी मेमोरी में लोड नहीं होतीं; हर फ़ाइल में `ETag` और `Last-Modified` होता है (रीलोड = खाली 304 उत्तर), आंशिक `Range` अनुरोध स्वीकार होते हैं (डाउनलोड फिर से शुरू करना, वीडियो); इमेज, मीडिया, फ़ॉन्ट, CSS और JS को डिफ़ॉल्ट `Cache-Control` मिलता है, जिसे कैश स्क्रीन में बदला जा सकता है। पहले से संपीड़ित टेक्स्ट फ़ाइलें: यदि `site.css` के बगल में `site.css.br` या `site.css.gz` मौजूद है (`brotli -k site.css` या `gzip -k site.css` से बनाई गई) और ब्राउज़र उन्हें स्वीकार करता है, तो उनकी जगह वही भेजी जाती हैं, मूल से पुराना संस्करण कभी नहीं।
- HTTP प्रोटोकॉल को डिफ़ॉल्ट रूप से मज़बूत करता है, इसे बंद करने का कोई विकल्प नहीं: स्पष्ट अनुमत मेथड, `Host` हेडर का सत्यापन, `Content-Length`/`Transfer-Encoding` अस्पष्टता की अस्वीकृति, ऐसे सुरक्षा हेडर और मूल CSP जिन्हें दरकिनार नहीं किया जा सकता।
- वैकल्पिक रूप से: WAF फ़िल्टरिंग (सिग्नेचर, दर सीमा, ब्लॉक सूची), सीधा TLS (self-signed प्रमाणपत्र, स्थानीय CA द्वारा हस्ताक्षरित, या Let's Encrypt/Certbot से सार्वजनिक, स्वचालित नवीनीकरण के साथ — §9 देखें), ज़ोन के अनुसार HTTP Basic प्रमाणीकरण, FastCGI/PHP-FPM से PHP, सीमित अपलोड ज़ोन।
- «boost» मोड: कई सर्वर प्रोसेस, मशीन के हर उपलब्ध CPU के लिए अधिकतम एक (मज़बूती और सीमाएँ स्क्रीन); सुरक्षा काउंटर (rate limit, पुनरावृत्ति) उनके बीच साझा होते हैं और सटीक रहते हैं।
- अपनी ही कॉन्फ़िगरेशन का ऑडिट करता है (`audit security`) और सिस्टम सर्विस के रूप में इंस्टॉल होता है (systemd/OpenRC/runit)।
- शुरू से अंत तक स्क्रिप्ट की जा सकने वाली गैर-इंटरैक्टिव CLI, **और इंटरैक्टिव इंटरफ़ेस (Textual)** जो ठीक वही उपयोग-स्थितियाँ प्रस्तुत करता है — §3 देखें। इंटरफ़ेस रोडमैप (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) **पूरी तरह पूरा**: क्षमता रजिस्टर, प्रोफ़ाइल/विकल्प, विस्तृत कॉन्फ़िगरेशन (alias/redirect/rewrite/FastCGI/dirlisting/प्रमाणीकरण/कैश/WAF/विश्वसनीय प्रॉक्सी/आउटबाउंड रिवर्स प्रॉक्सी/TLS), लॉग प्रबंधन (लाइब्रेरी/पसंदीदा, 3 viewer — सरल/क्लासिक/मिश्रित lnav —, IP देखें और संसाधित करें, SSH से रिमोट स्रोत, रोटेशन/बैकअप/स्वचालन/पुनर्स्थापना/सफ़ाई/एक्सपोर्ट), सिस्टम सर्विस, मल्टी-इंस्टेंस (रजिस्टर, निर्माण), जाँच/सिमुलेशन/ऑडिट, कॉन्फ़िगरेशन का बैकअप/पुनर्स्थापना, पहली बार सेटअप विज़ार्ड, एप्लिकेशन सेटिंग्स (थीम, रेंडरिंग प्रोफ़ाइल, एक्सपोर्ट/स्क्रीनशॉट पाथ), संदर्भ-आधारित सहायता गाइड (हर स्क्रीन के लिए ठोस उदाहरणों वाला कार्ड, FAQ, HTML एक्सपोर्ट, परीक्षण से जाँचा गया संपूर्ण कवरेज), हर सहेजने के बाद रीलोड/रीस्टार्ट का व्यवस्थित संकेत, फ़ाइल को हाथ से संपादित किए बिना Active Defense की पूर्ण कॉन्फ़िगरेशन।

### OMEGA-SERV क्या नहीं करता

- कच्चा CGI (V1 के दायरे से हटाया गया — केवल FastCGI/PHP-FPM समर्थित है)।
- पारस्परिक TLS प्रमाणीकरण (mTLS), OCSP stapling — V1 के दायरे से बाहर, §15 देखें। (Certbot के माध्यम से ACME/Let's Encrypt उपलब्ध है, §9c/9d देखें।)
- प्रोसेस के बीच साझा HTTP कैश।
- किसी दूरस्थ लक्ष्य का स्कैन/ऑडिट (इसके लिए `omega-check`/`omega-scan`/`omega-deep` देखें — Omega-serv केवल अपना ऑडिट करता है, कभी किसी तीसरे पक्ष का नहीं)।

### बाज़ार के वेब सर्वरों के सामने OMEGA-SERV

देखें [माप और तुलना](comparatif-serveurs-web.md)  
मापी गई तुलना: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/hi/)

### उपयोग संबंधी चेतावनी

Omega-serv **root के रूप में शुरू होने से इनकार करता है**। किसी भी दिए गए प्रोफ़ाइल में, `hardened` सहित, कोई भी सुरक्षा मॉड्यूल (WAF, TLS, प्रमाणीकरण) डिफ़ॉल्ट रूप से सक्षम नहीं है — उन्हें सक्षम करना हमेशा एक स्पष्ट कदम है (`config enable-tls`, `option enable waf`...)। `hardened` प्रोफ़ाइल स्वयं असली इंटरनेट एक्सपोज़र के लिए उसकी जगह लेने के बजाय एक रिवर्स प्रॉक्सी की सलाह देता है।

## 2. इंस्टॉलेशन

### पूर्व-आवश्यकताएँ

- Python 3.10+
- TLS प्रमाणपत्रों से जुड़ी हर चीज़ के लिए `openssl` (बाइनरी, Python लाइब्रेरी नहीं) — बाकी सुविधाएँ इसके बिना काम करती हैं।

### डाउनलोड

नवीनतम संस्करण का आर्काइव और हर संस्करण के SHA-256 फ़िंगरप्रिंट: [omega-serv-2.0.1.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### इंस्टॉलेशन

> ⚠️ **क्या आप किसी मौजूदा इंस्टॉलेशन को अपडेट कर रहे हैं?** नीचे दी गई कमांड, यदि `omega-serv/` पहले से मौजूद है, तो **चुपचाप एक्सट्रैक्शन छोड़ देती है** (वह इसे अपडेट नहीं, बल्कि बीच में रुका हुआ पहला इंस्टॉलेशन मानती है) — तब आप **बिना बदले पुराने कोड** पर ही डिपेंडेंसी दोबारा इंस्टॉल कर देंगे, बिना किसी त्रुटि संदेश के। इसके बजाय नीचे दिए गए [अपडेट](#अपडेट) अनुभाग का उपयोग करें।

```bash
[ -d omega-serv ] && echo "ℹ️ यहाँ पहले से एक्सट्रैक्ट है, यह चरण छोड़ा गया।" || tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. यदि पहले से मौजूद नहीं है तो वर्चुअल एनवायरनमेंट `.venv` बनाता है।
2. पैकेज इंस्टॉल करता है (`pip install -e .`) — **कोई बाहरी डिपेंडेंसी नहीं** (§6 देखें)।
3. `omega-serv.sh` और `install.sh` को निष्पादन-योग्य बनाता है।
4. `~/.bashrc` और `~/.zshrc` में alias `serv` जोड़ता है (पहले से मौजूद हो तो दोहराव नहीं)।

### अपडेट

यदि `omega-serv/` पहले से मौजूद है (पिछला इंस्टॉलेशन), तो **इस फ़ोल्डर के अंदर से कभी `tar` न चलाएँ**: वह एक नेस्टेड `omega-serv/omega-serv/` बनाने की कोशिश करेगा और विफल होगा। omega-fire के विपरीत, `install.sh` फ़ोल्डर की अनुमतियों को कभी नहीं छूता (कोई भी चरण `sudo` नहीं माँगता) — इसलिए यहाँ `root` के स्वामित्व वाले फ़ोल्डर का कोई जोखिम नहीं, मौजूदा इंस्टॉलेशन के ऊपर सीधे एक्सट्रैक्ट करना सुरक्षित है।

```bash
# omega-serv/ के PARENT फ़ोल्डर से (कभी उसके अंदर से नहीं)
tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
./install.sh
```

आर्काइव जानबूझकर सारी जीवित अवस्था को बाहर रखता है (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — वास्तव में परोसी जा रही साइट**...) — ऊपर से एक्सट्रैक्ट करने पर मौजूदा डेटा, प्रमाणपत्र, सेटिंग्स या परोसी जा रही सामग्री को कभी नहीं छुआ जाता, केवल एप्लिकेशन कोड बदला जाता है। `install.sh` मौजूदा `.venv` का पुनः उपयोग करता है और बस उसके ऊपर डिपेंडेंसी दोबारा इंस्टॉल करता है।

2026-10-18 से, `var/` और `secure/auth/` आर्काइव में बिल्कुल नहीं हैं, खाली भी नहीं: इसलिए ऊपर से एक्सट्रैक्ट करने पर अब उनकी अनुमतियाँ रीसेट नहीं होतीं (systemd सर्विस खाते के साथ साझा) — अपडेट के बाद अब «सर्विस → अनुमतियाँ फिर से लागू करें» की ज़रूरत नहीं। `install.sh` ये फ़ोल्डर न हों तो बनाता है, मौजूदा फ़ोल्डरों को कभी नहीं छूता।

> ⚠️ **यदि कोई सर्विस पहले से सक्रिय है, तो ऊपर का चरण पर्याप्त नहीं है।** यह डिस्क पर कोड बदल देता है, लेकिन पहले से चल रहा प्रोसेस मेमोरी में लोड किए गए पुराने कोड के साथ ही चलता रहता है — इसके बाद हमेशा एक **पूर्ण रीस्टार्ट** आवश्यक है:
> ```bash
> sudo systemctl restart <nom-du-service>
> ```
> **कभी सिर्फ़ रीलोड नहीं** (`systemctl reload`, या सर्विस स्क्रीन → *रीलोड*): वह केवल कुछ कॉन्फ़िगरेशन विकल्प दोबारा पढ़ता है (WAF नियम, प्रमाणीकरण ज़ोन...), **Python कोड को स्वयं कभी नहीं**। यदि `systemctl status <nom-du-service>` आपके अपडेट से पुरानी शुरुआत की तारीख दिखाता है, तो इसकी पुष्टि होती है कि वह अभी भी पुराने कोड पर चल रहा है। यदि आप हमेशा उसी फ़ोल्डर के ऊपर लिखकर अपडेट करते हैं (ऊपर का सामान्य मामला), तो यह रीस्टार्ट ही एकमात्र छूटा हुआ चरण है — सर्विस को दोबारा इंस्टॉल करने की आवश्यकता नहीं।

> ⚠️ **यदि इसके बाद सर्विस बार-बार रीस्टार्ट के चक्र में फँस जाए** (`systemctl status` सक्रिय/निष्क्रिय के बीच बदलता है, `journalctl -u <nom-du-service>` `var/` के अंतर्गत फ़ाइल लिखते समय `PermissionError` दिखाता है): `tar` एक्सट्रैक्शन फ़ोल्डरों की अनुमतियाँ आर्काइव में दर्ज रूप में बहाल कर देता है, जिससे प्रारंभिक इंस्टॉलेशन के समय समर्पित सिस्टम खाते के लिए सेट की गई साझा अनुमतियाँ मिट सकती हैं — भले ही `install.sh` स्वयं उन्हें कभी न छुए। यूनिट दोबारा इंस्टॉल करने की ज़रूरत नहीं: सर्विस स्क्रीन → **अनुमतियाँ सुधारें** (`var/` और `secure/auth/` पर साझा अनुमतियाँ फिर से लागू करता है, systemd यूनिट को छुए बिना)।

### डिपेंडेंसी

सर्वर का मूल भाग (HTTP/1.1 पार्सर, FastCGI क्लाइंट, `hashlib.scrypt` से पासवर्ड हैशिंग) शुद्ध Python/stdlib में रहता है, और TLS प्रमाणपत्रों से जुड़ी हर चीज़ Python crypto लाइब्रेरी के बजाय sub-process में `openssl` बाइनरी से होती है — **इसके लिए कोई बाहरी डिपेंडेंसी नहीं**। केवल इंटरैक्टिव इंटरफ़ेस (§3) कुछ जोड़ता है: `omega-lib` (थीम, टर्मिनल पहचान — सूट की साझा लाइब्रेरी, PyPI पर प्रकाशित नहीं, वितरण आर्काइव में vendored), `textual` और `pyte` (इंटरफ़ेस में मिश्रित `lnav` रेंडरिंग के लिए टर्मिनल एमुलेशन), `jinja2` (थीम वाले HTML एक्सपोर्ट) और `psutil` (स्थिति और संसाधन स्क्रीन — CPU/RAM/डिस्क/नेटवर्क)। वैकल्पिक विकास/परीक्षण डिपेंडेंसी (`pip install -e ".[test]"`): `hypothesis` (HTTP पार्सर और पाथ रिज़ॉल्वर के property tests, उत्पादन में कभी नहीं)। गुणवत्ता टूलिंग (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`। अतिरिक्त वैकल्पिक extra (`pip install -e ".[magnet]"`): `lupa` (एम्बेडेड Lua बाइंडिंग, precompiled wheel, सिस्टम `lua` interpreter आवश्यक नहीं), केवल पूरक «magnet» WAF स्क्रिप्ट के लिए (§7) — डिफ़ॉल्ट रूप से कभी इंस्टॉल नहीं; इसकी अनुपस्थिति सटीक इंस्टॉलेशन कमांड के साथ बताई जाती है (क्षमता `waf-magnet`, **क्षमताएँ** स्क्रीन), सर्वर के बाकी हिस्से को रोके बिना।

### अनुशंसित वैकल्पिक टूल

ये टूल न होने पर इंटरफ़ेस सीमित मोड में काम करता है:

- `openssl` — TLS प्रमाणपत्रों से जुड़ी हर चीज़ के लिए आवश्यक (self-signed, स्थानीय CA, इम्पोर्ट); इसके बिना `certs *` कमांड विफल होती हैं लेकिन बाकी सर्वर सामान्य रूप से काम करता है (§9 देखें)।
- `certbot` — केवल **Let's Encrypt** विज़ार्ड और उसके स्वचालित नवीनीकरण के लिए आवश्यक (§9c/9d); self-signed TLS/स्थानीय CA को इसकी ज़रूरत नहीं।
- `lnav` — **लॉग प्रबंधन** स्क्रीन में मिश्रित उन्नत लॉग विश्लेषण (§3); executable न मिलने पर स्पष्ट और साफ़ त्रुटि संदेश, कोई crash नहीं, स्क्रीन का बाकी हिस्सा (देखना/फ़ॉलो करना/रोटेशन/आँकड़े) इसके बिना सामान्य रूप से काम करता है।
- `scp` (पैकेज `openssh`/`openssh-clients`, लगभग हमेशा पहले से मौजूद) — केवल **रिमोट स्रोत (SSH)** के लिए आवश्यक (§13a); इसके बिना प्राप्ति एक स्पष्ट संदेश के साथ विफल होती है, लाइब्रेरी का बाकी हिस्सा सामान्य रूप से काम करता है।
- `python-psutil` (PyPI के `psutil` के समकक्ष सिस्टम पैकेज) — हर स्थिति में `pip install -e .` द्वारा स्वचालित रूप से इंस्टॉल होता है (पैकेज की अनिवार्य डिपेंडेंसी, **स्थिति और संसाधन** स्क्रीन को इसकी हमेशा ज़रूरत होती है), लेकिन इसे सिस्टम पैकेज मैनेजर से पहले से इंस्टॉल करने पर `pip` को इसका wheel स्थानीय रूप से compile नहीं करना पड़ता।

```bash
# Arch Linux और व्युत्पन्न
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu और व्युत्पन्न
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. उपयोग

कार्यात्मक रूप से पूरी तरह समकक्ष दो इंटरफ़ेस, दोनों के बीच कभी दोहराया गया तर्क नहीं: गैर-इंटरैक्टिव CLI (स्क्रिप्ट योग्य, नीचे उपयोग की गई) और इंटरैक्टिव Textual इंटरफ़ेस (मेन्यू, फ़ॉर्म, तालिकाएँ) — एक की हर क्रिया CLI में मौजूद है, इंटरफ़ेस केवल उन्हीं उपयोग-स्थितियों को प्रस्तुत करता है।

### इंटरैक्टिव मोड (TUI)

दैनिक उपयोग के लिए अनुशंसित — बिना आर्ग्युमेंट के चलाएँ:

```bash
./omega-serv.sh
```
यदि आपने alias बनाया है, तो टर्मिनल में बस `serv` टाइप करें:
```bash
serv
```

### इंटरफ़ेस की भाषाएँ

17 भाषाएँ: फ़्रेंच, अंग्रेज़ी, स्पैनिश, पुर्तगाली (ब्राज़ील), इतालवी, जर्मन, डच, पोलिश, रूसी, चीनी, वियतनामी, थाई, इंडोनेशियाई, जापानी, कोरियाई, हिन्दी, अरबी। चयन सेटिंग्स में (कुंजी `o`, «Langue / Language», लेबल कभी अनुवादित नहीं), या एक बार के लिए `OMEGA_SERV_LANG=en serv`। Linux टेक्स्ट कंसोल (TTY) में, जिन भाषाओं की लिपि कंसोल फ़ॉन्ट में मौजूद नहीं है (वियतनामी, चीनी, थाई, जापानी, कोरियाई, हिन्दी, अरबी), वे उस सत्र के लिए अंग्रेज़ी में दिखती हैं। हिन्दी में, जो टर्मिनल संयुक्त अक्षरों को स्वयं जोड़ते हैं (Kitty, Ghostty, Konsole), वे फ़ॉन्ट के अनुसार अलग-अलग ढंग से फ़्रेम और कॉलम खिसका देते हैं: शुरुआत में एक चेतावनी दिखाई जाती है; Terminator, GNOME Terminal, Xfce Terminal और Alacritty हिन्दी को संरेखित दिखाते हैं। दो अलग सेटिंग्स: **विज़िटर पेजों की भाषा** (त्रुटि पेज, डायरेक्टरी सूची — त्रुटि पेज स्क्रीन, डिफ़ॉल्ट रूप से फ़्रेंच) और **एक्सपोर्ट की भाषा** (HTML और इंसिडेंट रिपोर्ट — सेटिंग्स, डिफ़ॉल्ट रूप से «इंटरफ़ेस जैसी»)। सर्वर के लॉग (`journalctl`) फ़्रेंच में ही रहते हैं।

### सामान्य प्रवाह

प्रारंभ स्क्रीन (splash, किसी कुंजी या क्लिक पर बंद) → मुख्य मेन्यू (पहली बार सेटअप विज़ार्ड / क्षमता रजिस्टर / प्रोफ़ाइल / विस्तृत कॉन्फ़िगरेशन / एक्टिव सुरक्षा / लॉग प्रबंधन / सर्विस / मल्टी-इंस्टेंस / स्थिति और संसाधन / ऑडिट / बैकअप) → एक अनुभाग, फिर एक क्रिया का चयन, हर फ़ॉर्म आगे बढ़ने से पहले अपने आवश्यक फ़ील्ड सत्यापित करता है → किसी भी संवेदनशील या विनाशकारी क्रिया (रीस्टार्ट, हटाना, पुनर्स्थापना...) से पहले स्पष्ट पुष्टि → पहले से परोसी जा रही कॉन्फ़िगरेशन को बदलने वाले हर सहेजने के बाद अगले कदम का व्यवस्थित संकेत (स्वचालित हॉट रीलोड, या पूर्ण रीस्टार्ट की पुष्टि)। टर्मिनल के अनुसार अनुकूलन (रंग, आकार, रेंडरिंग प्रोफ़ाइल का संरचनात्मक अवनयन) स्वचालित है और किसी मैनुअल flag के बिना — §4 देखें।

#### कीबोर्ड शॉर्टकट (इंटरैक्टिव इंटरफ़ेस)

| कुंजी | क्रिया |
|---|---|
| `↑` / `↓` | स्क्रीन के तत्वों के बीच नेविगेट करें |
| `Tab` / `Shift+Tab` | फ़ॉर्म के फ़ील्ड के बीच नेविगेट करें |
| `Esc` | पिछली स्क्रीन पर वापस (होम पर बाहर निकलने की पुष्टि) |
| `t` | अगली थीम (तुरंत लागू, बिना पुष्टि) |
| `r` | टर्मिनल पहचान ताज़ा करें |
| `F1` | सक्रिय स्क्रीन की सहायता (संदर्भ कार्ड — नीचे "सहायता गाइड" देखें) |
| `a` | पूर्ण सहायता गाइड (नेविगेट करने योग्य मेन्यू + FAQ) |
| `o` | एप्लिकेशन सेटिंग्स (थीम, रेंडरिंग प्रोफ़ाइल, एक्सपोर्ट/स्क्रीनशॉट पाथ — नीचे देखें) |
| `q` | बाहर निकलें (पुष्टि के साथ) |
| `Ctrl+P` | कमांड पैलेट (थीम, स्क्रीनशॉट, विकल्प...) |

> **अपवाद — सूची संपादक (WAF → Custom)**: कोई शॉर्टकट नहीं, सब कुछ माउस से होता है; कीबोर्ड केवल टाइप करने के लिए है (अक्षर, Enter, तीर, Home/End, Page Up/Down, Backspace, Delete)। वहाँ `Esc`, `F1` और `Ctrl+P` निष्क्रिय हैं (**सहायता** बटन); केवल `Ctrl+Q` सक्रिय रहता है, बिना सहेजे बदलावों की पुष्टि के साथ।

#### सहायता गाइड (कुंजियाँ `F1`/`a`)

अंतर्निहित सहायता प्रणाली, कभी साधारण स्थिर पाठ नहीं: हर प्रलेखित स्क्रीन (परिभाषा/ठोस उदाहरणों के साथ भरने वाले फ़ील्ड/ट्रिगर होने वाली क्रिया/प्रतिक्रिया — रीलोड, रीस्टार्ट या कुछ नहीं वाला कार्ड) उसी से सीधे `F1` द्वारा खुलती है; कुंजी `a` पूरा मेन्यू खोलती है (एप्लिकेशन के वास्तविक नेविगेशन जैसा ही वृक्ष) जिसमें FAQ तक पहुँच (वास्तविक उपयोग में मिले जाल, उदा. Active Defense के हमला वर्ग, साझा सर्विस की अनुमतियाँ) और पूरे गाइड का स्वतंत्र HTML एक्सपोर्ट (सक्रिय थीम सुरक्षित) है। जब तक किसी स्क्रीन का विशिष्ट कार्ड न हो, एक सामान्य संदर्भ स्क्रीन पर वापसी — वर्तमान कवरेज संपूर्ण है, परीक्षण से जाँचा गया।

#### मुख्य मेन्यू (इंटरैक्टिव इंटरफ़ेस)

- **पहली बार सेटअप विज़ार्ड** — 8 चरणों वाला निर्देशित प्रवाह (स्वागत → केवल-पढ़ने वाली क्षमताएँ → प्रोफ़ाइल चयन → bind/पोर्ट → वैकल्पिक TLS → जाँच → सारांश + लेखन → सर्विस इंस्टॉल करने का प्रस्ताव); CLI जाने बिना पूरी कॉन्फ़िगरेशन बनाने और सर्वर चालू करने देता है।
- **क्षमता रजिस्टर** — केवल-पढ़ने वाला सिस्टम probe (init सिस्टम, कॉन्फ़िगर किया गया पोर्ट पहले से व्यस्त है या नहीं, `openssl`/`logrotate`/`tailscale`/`lnav` मौजूद, डिस्क स्थान, descriptor सीमा...), JSON/HTML एक्सपोर्ट।
- **प्रोफ़ाइल** — CLI के `profile` जैसी ही उपयोग-स्थिति (§5), लिखने से पहले हमेशा diff दिखाया जाता है।
- **सर्वर की विस्तृत कॉन्फ़िगरेशन** — alias/redirect/rewrite/dirlisting/विश्वसनीय प्रॉक्सी/आउटबाउंड रिवर्स प्रॉक्सी/FastCGI/कैश/प्रमाणीकरण/एक्सेस नियंत्रण/त्रुटि पेज पर पूर्ण CRUD, साथ ही **TLS** उप-मेन्यू (स्थिति, self-signed निर्माण, स्थानीय CA विज़ार्ड, Let's Encrypt/Certbot विज़ार्ड, स्वचालित नवीनीकरण, निरस्तीकरण, सक्षम/अक्षम — §9 देखें); एक दूसरा फ़्रेम **विकल्प और जाँच** वहाँ **विकल्प** (CLI `option`, §7) और **कॉन्फ़िगरेशन जाँचें** (CLI `config check`, §10) के शॉर्टकट एक साथ रखता है — सेटिंग्स समायोजित करके फिर जाँचने जैसा ही प्रवाह, ये दोनों स्क्रीन अब मुख्य मेन्यू से सीधे उपलब्ध नहीं हैं। WAF अब यहाँ नहीं रहता (नीचे "एक्टिव सुरक्षा" देखें): वह मुख्य रूप से लगातार बदलने वाली परिचालन स्थिति दिखाता है, कोई साधारण स्थिर कॉन्फ़िगरेशन फ़ॉर्म नहीं। हर सहेजना अगला कदम व्यवस्थित रूप से बताता है: सर्विस सक्रिय होने पर स्वचालित और मौन हॉट रीलोड (dirlisting, एक्सेस, alias/redirect/rewrite, कैश, त्रुटि पेज, विश्वसनीय प्रॉक्सी, रिवर्स प्रॉक्सी/FastCGI ज़ोन, उपयोगकर्ता/प्रमाणीकरण ज़ोन), या जब बदलाव listen socket, TLS या Active Defense को छूता है तो पूर्ण रीस्टार्ट की स्पष्ट पुष्टि — अब कोई भी स्क्रीन यह अनुमान लगाने के लिए नहीं छोड़ती कि सर्वर दोबारा शुरू करना है या नहीं।
- **एक्टिव सुरक्षा** — एक ही स्क्रीन जिसमें दो खंड अगल-बगल हैं: **Active Defense** (स्थिति, स्कोर/स्तर के साथ ट्रैक किए गए खतरे, कालक्रम/IoC एक्सपोर्ट/रिपोर्ट के साथ इंसिडेंट, Deception असाइनमेंट, dry-run में निर्णय सिम्युलेट करें, **सेटिंग्स** — `config/omega-serve.json` को कभी हाथ से संपादित किए बिना पूर्ण कॉन्फ़िगरेशन, §11 देखें) और **WAF** (स्थिति, मॉड्यूल — मोड/नियम पैक/ब्लॉक सूची, अनुरोध टेस्ट करें, Custom — कस्टम नियमों का लेखन और माउस से संपादित होने वाली पाथ/कीवर्ड सूचियों को लोड करना (§11b देखें), Magnet — सक्रिय करने से पहले संगतता जाँच के साथ बाहरी `mod_magnet` स्क्रिप्ट इम्पोर्ट करें) — §11 देखें।
- **लॉग प्रबंधन** — दो कॉलम वाला मेन्यू। **लाइब्रेरी** कॉलम: संसाधित किए जाने वाले हर लॉग को संदर्भित करने वाला केंद्रीय स्थान (हाथ से भरा जाता है, एक क्लिक इंस्टेंस के अपने लॉग सीधे जोड़ देता है — access/error/मूल WAF, + सक्रिय होने पर magnet स्क्रिप्ट §7 —, या SSH से प्राप्त एक **रिमोट स्रोत**, नीचे देखें); **पसंदीदा** (एक नाम से सहेजा गया लॉग + viewer संयोजन, सीधा लॉन्च); **लॉग देखें** चुने गए लॉग की संख्या के अनुसार 3 viewer में से एक के साथ — सरल (लाइव tail + किसी भी फ़ॉर्मेट पर IP/त्रुटि/HTTP कोड के सामान्य आँकड़े), क्लासिक (पढ़ना + फ़ॉलो करना), मिश्रित `lnav` (इंटरफ़ेस में असली टर्मिनल रेंडरिंग, magnet लॉग स्वतः शामिल + सत्रों के बीच रखने के लिए **पिन** किए गए मैनुअल पाथ); **IP देखें और संसाधित करें** (चुने गए एक या अधिक लॉग पर शीर्ष IP, अवधि 24h/7d/30d/सभी, किसी IP को हटाना)। **रखरखाव** कॉलम (अपरिवर्तित): मैनुअल या आकार-सीमा के अनुसार स्वचालित रोटेशन/आर्काइव, तुरंत बैकअप बनाना, निर्धारित स्वचालनों की कॉन्फ़िगरेशन/प्रबंधन (घोषणात्मक — नीचे नोट देखें), आर्काइव पुनर्स्थापित/साफ़ करना, सूची का एक्सपोर्ट।
- **सर्विस** — CLI के `service` जैसी ही क्रियाएँ (§12), हर क्रिया के लिए एक बार की `sudo` अनुमति, पूरा एप्लिकेशन कभी root के रूप में नहीं चलाया जाता।
- **मल्टी-इंस्टेंस** — मशीन पर ज्ञात इंस्टॉलेशनों का वैश्विक रजिस्टर (`~/.config/omega-serv/instances.json`, किसी भी प्रोजेक्ट डायरेक्टरी से बाहर), हर एक की systemd स्थिति के साथ; इंटरफ़ेस से सीधे नया इंस्टेंस बनाना (डायरेक्टरी ट्री की प्रति, अपना वर्चुअल एनवायरनमेंट और डिपेंडेंसी, अलग पोर्ट के साथ नई कॉन्फ़िगरेशन, नेस्टिंग और पोर्ट टकराव की जाँच)। एकल इंस्टॉलेशन के लिए बटन व्यावहारिक रूप से अदृश्य (2 ज्ञात होते ही लेबल "मल्टी-इंस्टेंस" "Instances (N)" बन जाता है); किसी दूसरे इंस्टेंस पर पूर्ण स्विच (`os.execv`, स्पष्ट पुष्टि, रीस्टार्ट पर स्विच की घोषणा करने वाला समर्पित splash); किसी इंस्टेंस की पूर्ण अनइंस्टॉलेशन (यूनिट हटाना, समर्पित सिस्टम खाता यदि किसी अन्य इंस्टेंस द्वारा उपयोग में नहीं है, और डायरेक्टरी का वैकल्पिक विलोपन, डिफ़ॉल्ट रूप से कभी नहीं)।
- **स्थिति और संसाधन** — एक नज़र में अवलोकन, हर 2 सेकंड में ताज़ा: सर्वर की स्थिति (प्रोसेस/PID, सिस्टम सर्विस की स्थिति, प्रोफ़ाइल/सक्रिय विकल्प/TLS/पोर्ट), लाइव access लॉग प्रवाह (थ्रूपुट, स्टेटस कोड के अनुसार वितरण, अद्वितीय IP, त्रुटि दर), सिस्टम संसाधन (CPU/RAM/डिस्क/swap/लोड/नेटवर्क, `psutil` से); इसमें **अनुरोध सिम्युलेट करें** शॉर्टकट भी है (संबंधित CLI कमांड जैसी ही उपयोग-स्थिति, §10)।
- **सुरक्षा ऑडिट** — संबंधित CLI कमांड जैसी ही उपयोग-स्थिति (§10)।
- **कॉन्फ़िगरेशन बैकअप** — कॉन्फ़िगरेशन फ़ाइल का tar.gz आर्काइव और, स्पष्ट विकल्प पर, WAF नियम/प्रमाणीकरण ज़ोन/प्रमाणपत्र (असली रहस्य शामिल होते ही पुष्टि अनिवार्य)/Active Defense डेटाबेस, पुनर्स्थापना, सूची, विलोपन।

> निर्धारित रोटेशन स्वचालनों पर नोट: वे दर्ज किए जाते हैं (आवृत्ति + लक्षित लॉग) लेकिन **उन्हें स्वचालित रूप से कोई नहीं चलाता** — न इंटरफ़ेस की ओर से, न पृष्ठभूमि कार्य के रूप में। यह `omega-fire` की समकक्ष स्क्रीन के साथ समानता का जानबूझकर किया गया चुनाव है, जिसका व्यवहार भी वैसा ही घोषणात्मक है। वास्तविक आवधिक निष्पादन (systemd timer, पृष्ठभूमि कार्य) ज़रूरत की पुष्टि होने पर अलग से बनाना बाकी है।

#### एप्लिकेशन सेटिंग्स (कुंजी `o` या कमांड पैलेट)

केवल इंटरफ़ेस प्राथमिकताएँ — `config/omega-serve.json` (सर्वर कॉन्फ़िगरेशन) से कभी नहीं मिलाई जातीं: सक्रिय थीम, रेंडरिंग प्रोफ़ाइल (`complete`/`standard`/`reduced`/`mono`, रीस्टार्ट आवश्यक), एक्सपोर्ट पाथ (डिफ़ॉल्ट `var/exports/`), स्क्रीनशॉट पाथ (डिफ़ॉल्ट `var/screenshots/`), इनमें से किसी भी फ़ोल्डर की सफ़ाई (पुष्टि अनिवार्य)।

```bash
# सर्वर चलाएँ (foreground, SIGTERM = grace period के साथ साफ़ बंद, SIGHUP = WAF/Auth हॉट रीलोड)
./omega-serv.sh serve

# कॉन्फ़िगरेशन
./omega-serv.sh config init                # config/omega-serve.json बनाता है (डिफ़ॉल्ट रूप से सुरक्षित मान)
./omega-serv.sh config check                # शुरू किए बिना जाँचता है (शुरुआत जैसे ही रोकने वाले गेट)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# प्रोफ़ाइल (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # लागू करने से पहले diff, हमेशा

# विकल्प (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# सर्वर चलाए बिना अनुरोध सिम्युलेट करें (सक्रिय करने से पहले नियम जाँचने में उपयोगी)
./omega-serv.sh simulate-request GET /index.html

# WAF (विकल्प अक्षम होने पर भी काम करता है, अंतर्निहित --force के माध्यम से)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "scan detecte" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + वॉर मोड, विकल्प "active_defense" - §11 देखें)
./omega-serv.sh active-defense status
./omega-serv.sh active-defense simulate --ip 203.0.113.42 --path /wp-login.php --attack-class scan --score 40
./omega-serv.sh active-defense purge
./omega-serv.sh threats list --level hostile
./omega-serv.sh threats show 203.0.113.42:ab12cd34
./omega-serv.sh incidents list --status open
./omega-serv.sh incidents show <incident-id>
./omega-serv.sh incidents close <incident-id>
./omega-serv.sh incidents export-ioc <incident-id> --format json,csv
./omega-serv.sh incidents generate-report <incident-id>
./omega-serv.sh deception list
./omega-serv.sh deception release --subject 203.0.113.42:ab12cd34

# TLS प्रमाणपत्र - self-signed (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# TLS प्रमाणपत्र - स्थानीय CA (9b)
./omega-serv.sh certs generate-ca --cn "Mon CA locale" --days 3650
./omega-serv.sh certs generate-csr --cn serveur.local --san-dns serveur.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# TLS प्रमाणपत्र - इम्पोर्ट (9c, उदा. Certbot hook से)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# HTTP Basic प्रमाणीकरण
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# सुरक्षा ऑडिट (कभी नहीं रोकता, केवल जानकारी)
./omega-serv.sh audit security --format text --min-severity medium

# कॉन्फ़िगरेशन बैकअप (कॉन्फ़िगरेशन हमेशा शामिल; असली रहस्य
# डिफ़ॉल्ट रूप से कभी एन्क्रिप्ट नहीं, उन्हें शामिल करने के लिए --confirm-secrets अनिवार्य)
./omega-serv.sh config backup --description "avant migration"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "menaces/incidents"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# सिस्टम सर्विस (systemd/OpenRC/runit, स्वचालित पहचान)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### उल्लेखनीय exit कोड

| कमांड | कोड | अर्थ |
|---|---:|---|
| `audit security` | `0` | कुछ भी गंभीर नहीं (कोई `CRITICAL`/`HIGH` नहीं) |
| `audit security` | `1` | कम से कम एक `CRITICAL` finding |
| `audit security` | `2` | `CRITICAL` के बिना कम से कम एक `HIGH` |
| `audit security` | `3` | निष्पादन त्रुटि (कॉन्फ़िगरेशन नहीं मिली...) |
| `certs check-expiry` | `1` | प्रमाणपत्र की अवधि समाप्त |
| कोई भी अन्य कमांड | `0`/`1` | सफलता / सत्यापन विफलता |

## 4. टर्मिनल संगतता

इंटरैक्टिव इंटरफ़ेस ([Rich](https://rich.readthedocs.io/) पर बना [Textual](https://textual.textualize.io/)) टर्मिनल की क्षमताओं (एमुलेटर, आकार) को स्वचालित रूप से पहचानता है और उसके अनुसार अपनी संरचनात्मक स्टाइलशीट (`complete`/`standard`/`reduced`/`mono`) बदलता है, बिना मैनुअल flag के। CLI मोड हमेशा सादे टेक्स्ट में रहता है, टर्मिनल से स्वतंत्र। पूरे `omega-` सूट द्वारा साझा नीति (`omega-lib`, `terminal/policies.py`) — `omega-check`/`omega-fire` जैसी ही।

### पहचाने गए एमुलेटर के अनुसार प्रोफ़ाइल

| एमुलेटर | प्रारंभिक प्रोफ़ाइल |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, आधुनिक SSH | `reduced` |
| Linux TTY, पुराना SSH | `mono` |
| अपरिचित एमुलेटर | `reduced` (डिफ़ॉल्ट वापसी) |

### टर्मिनल के आकार के अनुसार प्रोफ़ाइल

| न्यूनतम आकार (कॉलम × पंक्तियाँ) | प्रोफ़ाइल की ऊपरी सीमा |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| इससे कम | `mono` |

अंतिम रूप से चुना गया प्रोफ़ाइल **दोनों में से सबसे प्रतिबंधात्मक** होता है (एमुलेटर और आकार) — 70 कॉलम तक छोटा किया गया फ़ुल-स्क्रीन Ghostty `mono` पर उतर आता है, भले ही उसका एमुलेटर `complete` की अनुमति देता हो। कुंजी `r` से लाइव ताज़ा किया जा सकता है, या एप्लिकेशन सेटिंग्स (कुंजी `o`, §3) से हाथ से बदला जा सकता है।

## 5. प्रोफ़ाइल

| प्रोफ़ाइल | लक्षित उपयोग |
|---|---|
| `minimal` | डेमो/सरल स्थानीय उपयोग: केवल स्थैतिक, कोई विकल्प सक्षम नहीं |
| `standard` | स्थैतिक साइट या छोटा उत्पादन: सामान्य हेडर, मूल CSP, dirlisting/CGI/FastCGI अक्षम |
| `hardened` | न्यूनतम विशेषाधिकार के साथ एक्सपोज़र: डिफ़ॉल्ट रूप से स्थानीय bind (इंटरनेट के लिए रिवर्स प्रॉक्सी अनुशंसित), सीमित मेथड GET/HEAD, सख़्त CSP, anti-slowloris — WAF यहाँ भी **कभी** स्वचालित रूप से सक्षम नहीं होता |
| `development` | केवल स्थानीय विकास, कभी इंटरनेट के लिए उपयुक्त नहीं बताया जाता: loopback bind अनिवार्य, report-only CSP, विस्तृत त्रुटि पेज |

कॉन्फ़िगरेशन विलय का क्रम: अंतर्निहित सुरक्षित मान → चुना गया प्रोफ़ाइल → वर्तमान में सक्रिय विकल्प संरक्षित (प्रोफ़ाइल बदलने पर भी बने रहते हैं) → स्पष्ट उपयोगकर्ता overlay। लिखने से पहले हमेशा पूरा diff दिखाया जाता है (`profile apply`)।

## 6. आर्किटेक्चर

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` composition root है (सूट के अन्य टूल के `app/` के समकक्ष)। इस प्रोजेक्ट की स्वीकृत विशेषता, जिसे माना नहीं बल्कि `import-linter` से जाँचा जाता है: `application/server/start_server.py` (और `validate_config.py`, `run_audit.py`) **वास्तविक कॉन्फ़िगरेशन पर निर्भर निर्माण फ़ैक्टरी** की भूमिका निभाते हैं (कौन सा सर्विस मैनेजर, WAF सक्षम करना या नहीं...) और ठोस `infrastructure/` adapter सीधे instantiate करते हैं — CHECK/TRACK के अधिक सख़्त पैटर्न के विपरीत, जहाँ `application/` केवल `ports/` का उपयोग करता है। वास्तव में लागू एकमात्र सार्वभौमिक नियम: `domain/`/`core/` कभी बाहरी परतों पर निर्भर नहीं होते।

```text
src/omega_serv/
├── core/            साझा शब्दावली (platform_info, स्थिरांक)
├── domain/           शुद्ध व्यावसायिक तर्क (HTTP, कॉन्फ़िगरेशन, WAF/TLS/auth/audit सुरक्षा, रूटिंग)
├── ports/            एप्लिकेशन द्वारा अपेक्षित अनुबंध (Protocol)
├── application/      उपयोग-स्थितियाँ - कुछ फ़ंक्शन (build_server...) ठोस adapter भी जोड़ते हैं (ऊपर देखें)
├── infrastructure/    वास्तविक कार्यान्वयन (asyncio, subprocess में openssl, systemd/OpenRC/runit, फ़ाइलें)
├── interfaces/cli/    गैर-इंटरैक्टिव argparse CLI
├── interfaces/tui/    इंटरैक्टिव Textual इंटरफ़ेस (वही उपयोग-स्थितियाँ, कभी दोहराया तर्क नहीं)
└── bootstrap/         DependencyContainer, प्रोजेक्ट रूट का निर्धारण
```

`import-linter` द्वारा जाँचे गए नियम (8 अनुबंध): `domain`/`core` कभी बाहरी परतों पर निर्भर नहीं; `interfaces.tui` कभी सीधे `infrastructure` पर निर्भर नहीं; `textual` केवल `interfaces.tui` तक सीमित; `subprocess` केवल `infrastructure/process/subprocess_runner.py` तक सीमित (और `infrastructure/lnav/`, इंटरैक्टिव PTY प्रवाह); `ssl` केवल `infrastructure/tls/ssl_context_builder.py` तक सीमित; `jinja2` केवल `infrastructure/exporters/html_exporter.py` तक सीमित; `sqlite3` केवल `infrastructure/persistence/sqlite_active_defense_connection.py` तक सीमित (प्रोजेक्ट का एकमात्र रिलेशनल भंडारण, Active Defense के लिए आरक्षित — §11 देखें); `lupa` केवल `infrastructure/waf/lua_waf_adapter.py` तक सीमित (पूरक «magnet» WAF स्क्रिप्ट, §7)।

## 7. वैकल्पिक मॉड्यूल

सभी दिए गए प्रोफ़ाइलों में डिफ़ॉल्ट रूप से अक्षम — सक्रियण हमेशा स्पष्ट (`option enable <nom>` या `config enable-tls`):

| मॉड्यूल | भूमिका |
|---|---|
| `waf` | सिग्नेचर (संवेदनशील पाथ, scanner UA/Referer, body में SQLi/XSS/CMDi), टेक्स्ट फ़ाइल में संपादन योग्य सूचियाँ (कीवर्ड, या `!` अपवादों के साथ संवेदनशील पाथ, ऑब्ज़र्वेशन मोड और हर सूची की अपनी पुनरावृत्ति — दो संदर्भ सूचियाँ साथ आती हैं, स्पष्ट लोडिंग, §11b देखें), दर सीमा (token bucket, फ़ोल्डर और IP/नेटवर्क के अनुसार नियम, §11c देखें), ब्लॉक सूची (CIDR + समाप्ति), प्रतिष्ठा/escalation, वैकल्पिक «magnet» सुदृढ़ीकरण के रूप में मौजूदा Lighttpd `mod_magnet` WAF स्क्रिप्ट का इम्पोर्ट (बिना दोबारा लिखे, extra `pip install -e ".[magnet]"` — केवल जोड़ता है, मूल ब्लॉक को कभी नहीं हटा सकता; इम्पोर्ट के समय संगतता जाँच, समर्पित TUI स्क्रीन) — `log-only` मोड संरचनात्मक रूप से ब्लॉक करने में असमर्थ |
| TLS | सीधा (self-signed, स्थानीय CA, या Let's Encrypt/Certbot से सार्वजनिक, स्वचालित नवीनीकरण के साथ — §9 देखें), V1 में कभी mTLS/OCSP नहीं |
| प्रमाणीकरण | ज़ोन के अनुसार HTTP Basic (`url_prefix`), timing-विरोधी रक्षा के साथ `hashlib.scrypt` (अज्ञात उपयोगकर्ता के लिए भी स्थिर समय) |
| FastCGI/PHP-FPM | केवल एक `(url_prefix, script_root)`, `script_root` बनावट से ही `webroot/` के बाहर सीमित (स्थैतिक handler कभी PHP स्रोत उजागर नहीं कर सकता) |
| आउटबाउंड रिवर्स प्रॉक्सी | Omega-serv स्वयं एक या अधिक backend की ओर प्रॉक्सी का काम करता है (`server.tls.mode = "behind_proxy"` की उलटी दिशा) — लोड वितरण (round-robin, भारित, least-connections, ip-hash, least-response-time, वास्तविक लोड), सत्र affinity और हेडर पर रूटिंग नियम, निष्क्रिय और सक्रिय स्वास्थ्य जाँच, उत्तर कैश (बहु-संस्करण `Vary`), backpressure, लूप-रोधी सुरक्षा, हॉट प्रशासन API — पूरे विवरण के लिए §7a देखें |
| अपलोड | सीमित ज़ोन, ज़ोन के अनुसार कोटा, सर्वर की ओर से बनाए गए फ़ाइल नाम — V1 में streaming नहीं (`server.max_request_size` से सीमित) |
| `active_defense` | पहले से गणना किए गए WAF संकेतों से Deception + वॉर मोड (कभी दूसरा स्कोर नहीं): स्थिर डिकॉय, लक्षित धीमापन/समृद्ध लॉगिंग/दर सीमा, इंसिडेंट + IoC एक्सपोर्ट — §11 देखें |

### 7a. आउटबाउंड रिवर्स प्रॉक्सी — विवरण

OMEGA-SERV स्वयं एक या अधिक HTTP/HTTPS backend की ओर रिवर्स प्रॉक्सी का काम कर सकता है — इसे `server.tls.mode = "behind_proxy"` (OMEGA-SERV किसी प्रॉक्सी के **पीछे**, उलटा तंत्र) से कभी न मिलाएँ। पूर्ण CRUD में कॉन्फ़िगर करने योग्य ज़ोन (TUI: *विस्तृत कॉन्फ़िगरेशन → रिवर्स प्रॉक्सी*), हर ज़ोन में एक या अधिक upstream।

- **लोड वितरण** — `round_robin` (डिफ़ॉल्ट), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (भारित), `least_connections`, `least_response_time`, `real_load` (वास्तविक लोड)। मूल `real_load` मोड (probe `/.omega-serv-load/`, «स्थिति और संसाधन» स्क्रीन वाला ही `psutil` माप पुनः उपयोग करता है, कभी दूसरी कॉल नहीं) या घोषणात्मक (तीसरे पक्ष का HTTP probe, न्यूनतम फ़ॉर्मेट `{"load_percent": ...}` या केवल संख्या) — upstream के स्तर पर, एक ही ज़ोन दोनों को मिला सकता है।
- **सत्र affinity और सशर्त रूटिंग** — अपारदर्शी sticky cookie (वास्तविक host:port क्लाइंट को कभी उजागर नहीं) और हेडर पर नियम (समानता या prefix), दोनों लक्षित upstream की पात्रता से फ़िल्टर (लक्षित upstream अनुपलब्ध हो तो साफ़ तरीके से सक्रिय रणनीति पर लौटते हैं)।
- **स्वास्थ्य** — निष्क्रिय (लगातार विफलता/सफलता, flapping सीमित करने के लिए down/up के अलग-अलग सीमा मान) **और** सक्रिय (वास्तविक ट्रैफ़िक से स्वतंत्र आवधिक probe, हर upstream के लिए वैकल्पिक, वास्तविक लोड वाला ही पृष्ठभूमि कार्य तंत्र पुनः उपयोग करता है)। अवस्थाएँ `DOWN` (हमेशा स्वचालित), `DRAINING`/`MAINTENANCE` (हमेशा मैनुअल, स्पष्ट रूप से अस्थायी, कभी स्थायी रूप से सहेजी नहीं जातीं) — हाथ से ट्रिगर किया गया upstream नए चयनों से बाहर रहता है, पहले से स्थापित कनेक्शन को कभी बाधित किए बिना। दूसरे upstream पर स्वचालित retry, केवल idempotent मेथड (GET/HEAD/OPTIONS) के लिए और केवल कनेक्शन त्रुटि पर।
- **Backpressure** — हर upstream के लिए सक्रिय कनेक्शनों की कॉन्फ़िगर करने योग्य ऊपरी सीमा; संतृप्त upstream साफ़ तरीके से 503 के साथ मना करता है, खराब upstream (502, फिर भी retry किया जाता है) से अलग।
- **उत्तर कैश** — केवल GET/HEAD, कभी त्रुटि उत्तर नहीं, ज़ोन के अनुसार स्पष्ट opt-in के बिना कभी `Set-Cookie` नहीं; upstream के `Cache-Control`/`Vary` का सम्मान करता है (अक्षम करने योग्य लेकिन खतरनाक विकल्प, TLS सत्यापन वाला ही दर्शन)। एक ही संसाधन के कई संस्करण (`Vary`) वास्तव में डिस्क पर साथ रहते हैं, कभी साधारण «आख़िरी आने वाला जीतता है» नहीं। Anti-stampede लॉक (केवल एक समवर्ती अनुरोध वास्तव में कैश फिर से बनाता है)। हर उत्तर पर निदान हेडर `X-Omega-Cache: HIT`/`MISS`/`BYPASS`। समर्पित TUI स्क्रीन (*रिवर्स प्रॉक्सी कैश*) में निगरानी/सफ़ाई।
- **लूप-रोधी सुरक्षा** — hop-by-hop हेडर हटाए जाते हैं, `X-Forwarded-*` हमेशा ओवरराइट (क्लाइंट वालों के साथ कभी मिलाए नहीं जाते), हर रिले पर बढ़ने वाला `X-Omega-Proxy-Hops` काउंटर (5 hop से अधिक पर साफ़ अस्वीकृति — दो इंस्टेंस के बीच अप्रत्यक्ष लूप पकड़ता है, जिसे स्थानीय कॉन्फ़िगरेशन सत्यापन कभी नहीं देख सकता)।
- **WebSocket** — ज़ोन के अनुसार अनुमति योग्य upgrade, स्थापित होने के बाद पूरी पाइप अवधि के लिए एक ही निश्चित upstream, बिना एप्लिकेशन timeout के।
- **हॉट प्रशासन** — छोटी स्थानीय HTTP API (`/.omega-serv-admin/`, मूल लोड probe की तरह `trusted_proxy` से सुरक्षित) जो TUI को किसी backend की DRAINING/MAINTENANCE अवस्था पढ़ने/लागू करने और **वास्तव में चल रहे सर्वर** के कैश का hits/miss अनुपात पढ़ने देती है (समर्पित स्क्रीन *बैकएंड की लाइव स्थिति*) — TUI और सर्वर बिना साझा मेमोरी के दो अलग प्रोसेस रहते हैं, यह स्थानीय HTTP चैनल ही दोनों के बीच एकमात्र पुल है।

## 8. HTTP मज़बूती (अक्षम नहीं की जा सकती)

- पढ़ते **समय** ही सीमित अनुरोध हेडर/लाइन (कभी बाद में नहीं), पुराना header folding अस्वीकृत, `Transfer-Encoding` हमेशा अस्वीकृत (कभी अनुमान नहीं)।
- दोहराया गया `Content-Length` अस्वीकृत; `Expect: 100-continue` साफ़ तरीके से अस्वीकृत (417)।
- मेथड की स्पष्ट श्वेत सूची (अन्यथा 405 + `Allow`), `Host` हेडर सत्यापित (अनुपस्थित/खाली/दोहराया-भले-समान/control character → 400)।
- सुरक्षा हेडर और मूल CSP (`enforce`/`report-only`) त्रुटियों सहित **हर** उत्तर पर लागू — किसी विकल्प से दरकिनार नहीं। `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` हमेशा `same-origin`, साइट तोड़ने का कोई वास्तविक जोखिम नहीं। `Cross-Origin-Embedder-Policy` हमेशा स्पष्ट रूप से भेजा जाता है (कभी अनुपस्थित नहीं — बाहरी scanner «विचार नहीं किया गया» को «चुनाव से अनुमतिपूर्ण» से अलग पहचानता है), `hardened` सहित **सभी** प्रोफ़ाइलों पर डिफ़ॉल्ट `unsafe-none`: पिछले दोनों के विपरीत, `require-corp`/`credentialless` वास्तव में परोसी जा रही साइट के cross-origin संसाधनों (फ़ॉन्ट, इमेज, तीसरे पक्ष के iframe) को रोक सकते हैं — समायोज्य (`security.coep_mode`)। CSP ज़ोन (`security.csp_zones`): पाथ prefix के अनुसार **स्पष्ट** अपवाद (उदा. `unsafe-inline` केवल `/un-dossier/` के अंतर्गत जिसे वास्तव में इसकी ज़रूरत है), हर एक अपने prefix के लिए डिफ़ॉल्ट नीति को पूरी तरह बदल देता है — कभी विलय नहीं, कभी वैश्विक ढील नहीं; हर अपवाद `audit security` में दिखाई देता रहता है (CSP-001/CSP-002 ज़ोन भी स्कैन करते हैं), जानबूझकर होने पर भी। एक विज़ार्ड के माध्यम से directive-दर-directive निर्देशित निर्माण (**सामान्य सुरक्षा** स्क्रीन), हर फ़ील्ड वैश्विक नीति के **वर्तमान** मान से पहले से भरा — केवल वही बदलने के लिए जिसे बदलना है, न कि खाली फ़ील्ड से शुरू करके अनजाने में दूसरे directive खो देने के लिए; यदि बनाया गया ज़ोन `unsafe-inline`/`unsafe-eval`/सामान्य स्रोत `*` में ढील देता है तो एक अतिरिक्त स्पष्ट पुष्टि माँगी जाती है।
- IPv4-mapped-IPv6 पते (`::ffff:x.x.x.x`) किसी भी तुलना (ब्लॉक सूची, विश्वसनीय प्रॉक्सी, दर सीमा) से पहले सामान्यीकृत — अन्यथा ज्ञात bypass।
- सामान्य unit/integration परीक्षणों के अलावा, HTTP पार्सर और पाथ रिज़ॉल्वर के विरुद्ध property tests (`hypothesis`, हज़ारों उत्पन्न उदाहरण) से जाँचा गया।

## 9. TLS

### 9a. Self-signed प्रमाणपत्र (न्यूनतम)

यथार्थवादी स्थानीय/लैब/VPN (Tailscale...) उपयोग को कवर करता है: एक ही listener, सीधा `ssl.SSLContext`, RSA 2048/4096 या ECDSA P-256/P-384।

### 9b. स्थानीय CA

कई क्लाइंट उपकरणों के लिए जिन्हें हर प्रमाणपत्र अलग से इम्पोर्ट किए बिना भरोसा करना है: एक स्थानीय प्रमाणन प्राधिकरण ज़रूरत के अनुसार जितने चाहिए उतने सर्वर प्रमाणपत्रों पर हस्ताक्षर करता है।

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - प्रोजेक्ट का सबसे संवेदनशील तत्व
├── root-ca.pem    # 0644 - क्लाइंट के trust store में इम्पोर्ट करना है
├── serial.txt     # 0600 - अगले serial number का रिकॉर्ड
└── index.txt      # 0600 - हर हस्ताक्षरित प्रमाणपत्र की V(वैध)/R(निरस्त) स्थिति का रिकॉर्ड
```

प्रवाह: `certs generate-ca` (CA कुंजी का passphrase **अनिवार्य**, `--password` छोड़ने पर दोहरी पुष्टि के साथ इंटरैक्टिव प्रविष्टि) → `certs generate-csr` (सर्वर कुंजी + CSR) → `certs sign-csr` (CA से हस्ताक्षर करता है, CSR का SAN कॉपी करता है, माँगने पर `fullchain.pem` बनाता है) → `tls.certificate.certificate_path` को इस `fullchain.pem` की ओर इंगित करें। समझौता किया गया प्रमाणपत्र `certs revoke` से हटाया जाता है (`index.txt` में चिह्नित करता है, पहले जाँचता है कि प्रमाणपत्र वास्तव में इसी CA का है — अन्यथा मना करता है)। V1 में न CRL वितरण, न बाहरी CA/तीसरे पक्ष के प्राधिकरण के लिए CSR, न mTLS (§15 देखें)।

### 9c. Let's Encrypt / ACME (Certbot) — सार्वजनिक, self-hosted

ब्राउज़रों द्वारा मान्य प्रमाणपत्र वाली वास्तव में सार्वजनिक साइट के लिए, पूर्ण self-hosted योजना: DDNS (Dynu या समकक्ष, पूरी तरह ऑपरेटर की ज़िम्मेदारी) → Certbot → Omega-serv। केवल TUI विज़ार्ड (`विस्तृत कॉन्फ़िगरेशन → TLS → Let's Encrypt विज़ार्ड`) — sub-process में `certbot certonly --webroot` चलाता है (**कभी** `--standalone` नहीं, पोर्ट 80 पहले से Omega-serv के पास है; **कभी** दोबारा लिखा गया ACME क्लाइंट नहीं) जिसमें `--config-dir`/`--work-dir`/`--logs-dir` प्रोजेक्ट के `secure/certificates/letsencrypt/` के अंतर्गत इंगित होते हैं — **कभी** `/etc/letsencrypt/` नहीं — जिससे Certbot स्वयं पूरी तरह बिना विशेषाधिकार के चलता है। प्राप्त प्रमाणपत्र स्वचालित रूप से इम्पोर्ट होता है (`certs import` वाला ही तंत्र, ऊपर के CLI उदाहरण देखें) और नवीनीकरण hook स्क्रिप्ट लिखी जाती है। टेस्ट मोड (staging) डिफ़ॉल्ट रूप से चयनित — डोमेन/webroot के ठीक काम करने की पुष्टि होने पर इसे हटाएँ, ताकि Let's Encrypt की वास्तविक दर सीमाओं से बचा जा सके।

पूर्व-आवश्यकताएँ पूरी तरह Omega-serv के दायरे से बाहर: सार्वजनिक IP की ओर इंगित डोमेन (DDNS), और इस मशीन की ओर forward किए गए पोर्ट 80/443।

### 9d. स्वचालित नवीनीकरण (Certbot)

`विस्तृत कॉन्फ़िगरेशन → TLS → स्वचालित नवीनीकरण` **इस इंस्टेंस के लिए** वास्तव में पहचाने गए सर्विस मैनेजर के अनुसार ढलता है (मल्टी-इंस्टेंस में कई इंस्टेंस के बीच साझा तंत्र कभी नहीं): systemd → एक timer बनाता और इंस्टॉल करता है (`<service>-certbot-renew.timer`, दिन में दो बार + यादृच्छिक विलंब, `certbot renew` इंस्टेंस के `--config-dir` तक सीमित); अन्यथा → `crontab` उपलब्ध हो तो crontab पंक्ति (वर्तमान उपयोगकर्ता, कोई विशेषाधिकार नहीं); अन्यथा → मैनुअल निर्देश दिखाए जाते हैं, कोई ज़बरदस्ती लेखन नहीं। कुछ वितरणों (Arch/Manjaro सहित) पर, Debian/Ubuntu के विपरीत, Certbot पैकेज डिफ़ॉल्ट रूप से **कोई भी** timer इंस्टॉल नहीं करता — इसीलिए यह स्क्रीन है, न कि पहले से मौजूद माने गए तंत्र की साधारण जाँच। कॉन्फ़िगर होने के बाद, नवीनीकरण हर नवीनीकृत प्रमाणपत्र को स्वचालित रूप से फिर से इम्पोर्ट करता है (`certs import`) और फिर सर्विस रीस्टार्ट करता है, फिर कभी हाथ से हस्तक्षेप किए बिना।

## 10. सुरक्षा ऑडिट

`audit security` **रोकता नहीं**: यह `config check` के पहले से रोकने वाले गेट को `CRITICAL` के रूप में फिर से चलाता है, फिर परामर्शी नियम लागू करता है (शुद्ध रूप से TLS, CSP, खतरनाक मेथड, timeout, अपलोड स्वच्छता; वास्तविक I/O में फ़ाइल अनुमतियाँ, प्रमाणपत्र समाप्ति, इंस्टॉल की गई systemd यूनिट, लॉग का आकार)। `WAF-001` (WAF `log-only` में ही रह गया) एक छोटी स्थिति फ़ाइल (`var/run/waf-mode-state.json`) के माध्यम से समय के साथ देखा जाता है — बार-बार चलाने पर `log-only` में ≥14 दिन देखे जाने के बाद ही ट्रिगर होता है, पहले `audit` पर नहीं।

## 11. Active Defense (deception + वॉर मोड)

वैकल्पिक मॉड्यूल (`option enable active_defense`, डिफ़ॉल्ट रूप से अक्षम) जो पहले से गणना किए गए WAF संकेतों (`WafDecision`/प्रतिष्ठा/ब्लॉक सूची — कभी अलग से दूसरी स्कोर गणना नहीं) से शत्रुतापूर्ण व्यवहार का आकलन करता है, और किसी स्रोत को डिकॉय की ओर मोड़ सकता है, उसके उत्तर धीमे कर सकता है और अधिक बारीकी से लॉग कर सकता है, उपयोगी इंसिडेंट बना सकता है, फिर समझौता संकेतक (IoC) एक्सपोर्ट कर सकता है। यह स्वयं कभी ट्रैफ़िक को ब्लॉक नहीं करता — नेटवर्क ब्लॉकिंग `omega-fire` का काम है; Active Defense देखता है, मोड़ता है, धीमा करता है और दर्ज करता है।

**खतरे और स्कोर**: हर स्रोत (`IP + User-Agent का SHA-256 hash`) स्कोर जमा करता है (रोकने वाला `WAF-001` +10, प्रतिष्ठा escalation +25, ज्ञात प्रतिबंध +25, पहले से असाइन डिकॉय पर POST +30 — नई घटना के बिना हर 15 मिनट में -5 की कमी) जिसे `normal`/`suspicious`/`hostile`/`contained` के रूप में आँका जाता है (`contained` के लिए पहले से ज्ञात प्रतिबंध भी आवश्यक है)। `mode: monitor` बिना कार्रवाई के देखता है; `mode: enforce` नीचे दी गई क्रियाएँ वास्तव में लागू करता है।

**वॉर मोड** (`options.active_defense.settings.war_mode`): एक `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) जो कॉन्फ़िगर करने योग्य सीमा मानों से ट्रिगर होता है, हर गैर-`normal` स्रोत के लिए:
- `enrich_log` — अलग JSONL लॉग (`var/log/active-defense-enriched.jsonl`, WAF/उत्पादन लॉग के साथ कभी मिलाया नहीं जाता), हेडर redacted, HTTP body `logging.capture_request_body` के अनुसार hashed (SHA-256) या छोटा किया गया।
- `delay` — सीमित और jitter वाला धीमापन (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), asyncio लूप को कभी ब्लॉक नहीं करता।
- `rate_limit` — हर स्रोत के लिए समर्पित दर सीमा (`war_mode.rate_limit.requests`/`window_seconds`), अलग कुंजी के साथ WAF वाला ही तंत्र पुनः उपयोग करता है।
- `create_incident` — `thresholds.incident_score` पार होने पर इंसिडेंट का स्वचालित खुलना/विलय।

**Deception**: एक `hostile`/`contained` स्रोत को एक स्थिर डिकॉय (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — विश्वसनीय लेकिन हमेशा निश्चित उत्तर, कभी वास्तविक फ़ाइल पढ़ना या sub-process नहीं) पर असाइन किया जा सकता है, जो देखे गए हमला वर्ग के अनुसार चुना जाता है (`deception.profiles.<nom>.match_attack_classes`, `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown` में से एक या अधिक)। अलगाव के दो स्तर, स्वीकृत और उसी रूप में प्रलेखित:
- **स्तर 1** (in-process fixture, `isolation_level: "fixture"`, डिफ़ॉल्ट) — स्पष्ट रूप से कमज़ोर अलगाव: उत्पादन वाला ही प्रोसेस, वही OS उपयोगकर्ता, केवल इसलिए स्वीकार्य क्योंकि fixture स्थिर टेम्पलेट लौटाने के अलावा कभी कुछ नहीं करता। प्रोफ़ाइल का नाम ऊपर के 4 fixture में से किसी एक से ठीक-ठीक मेल खाना चाहिए — अन्यथा सत्यापन (`validate_active_defense_config`) में अस्वीकृत, ताकि गलत नाम वाले उस डिकॉय के जाल से बचा जा सके जो तब चुपचाप कभी ट्रिगर नहीं होता।
- **स्तर 2** (वास्तव में अलग backend, `isolation_level: "proxy"`) — `options.active_defense.settings.deception.decoy_zones.<nom>` के माध्यम से अलग प्रोसेस की ओर रिले (पहले से चल रहे सर्वर का upstream `host`/`port`, कभी स्वचालित रूप से नहीं बनाया जाता; कभी `options.reverse_proxy` से नहीं पढ़ा जाता — डिकॉय गलती से भी किसी उत्पादन ज़ोन की ओर कभी इंगित नहीं कर सकता, `config check` पर जाँचा जाता है), उत्पादन वाला ही आउटबाउंड रिवर्स प्रॉक्सी तंत्र पुनः उपयोग करते हुए (`serve_proxy()` — वास्तविक अनुरोध के समय upstream पहुँच से बाहर: हमलावर को 502 लौटाया जाता है, कभी crash नहीं)।

**सेटिंग्स स्क्रीन** (TUI, एक्टिव सुरक्षा → Active Defense → सेटिंग्स): ऊपर की हर चीज़ की पूर्ण कॉन्फ़िगरेशन — मोड, वॉर मोड सक्रियण, दायरा/क्रियाएँ/सीमा मान/धीमापन/अनुरोध सीमा, deception (डिफ़ॉल्ट व्यवहार, हर फ़ील्ड में दिखाए गए उदाहरण मानों के साथ डिकॉय प्रोफ़ाइल और डिकॉय ज़ोन का CRUD), IoC, भंडारण और लॉगिंग — किसी भी सहेजने से पहले CLI जैसे ही नियमों से सत्यापित, `config/omega-serve.json` के मैनुअल संपादन की कभी ज़रूरत नहीं। किसी भी बदलाव के बाद हमेशा पूर्ण रीस्टार्ट आवश्यक (Active Defense कभी हॉट रीलोड नहीं होता)।

**इंसिडेंट और IoC**: हर इंसिडेंट का पूरा कालक्रम, संकेतकों का निष्कर्षण (IP, hashed User-Agent), versioned JSON/साझा करने योग्य IoC तक सीमित CSV/Markdown रिपोर्ट के रूप में एक्सपोर्ट, और आदान-प्रदान फ़ॉर्मेट **STIX 2.1** (OpenCTI, किसी SIEM… में लोड करने के लिए bundle) और **MISP** (MISP इंटरफ़ेस से इम्पोर्ट करने के लिए event), डिफ़ॉल्ट रूप से TLP:AMBER चिह्नित — स्थानीय फ़ाइलें, कभी भेजी नहीं जातीं; हर एक्सपोर्ट के साथ एक `<export>.sha256` फ़ाइल (मानक `sha256sum` फ़ॉर्मेट)। `ioc.auto_export_on_close` (डिफ़ॉल्ट रूप से true) होने पर इंसिडेंट बंद होने पर स्वचालित एक्सपोर्ट। समाप्त अवस्थाएँ और ऑडिट लॉग स्वचालित रूप से साफ़ किए जाते हैं, डेटाबेस की ऊपरी सीमा तय है (डिस्क भरने से सुरक्षा); `active-defense purge` इसके अलावा फिर से शांत हो चुके इंसिडेंट बंद करता है।

**सिमुलेशन**: `active-defense simulate` (CLI) और "सिम्युलेट करें" बटन (TUI, एक्टिव सुरक्षा स्क्रीन) स्कोर/स्तर का अनुमान दिखाते हैं और ट्रिगर होने वाली हर क्रिया समझाते हैं — सख़्त dry-run, कोई वास्तविक लेखन नहीं, कोई नेटवर्क प्रभाव नहीं।

बैकअप/पुनर्स्थापना: `config backup --include-active-defense` sqlite डेटाबेस (खतरे/इंसिडेंट/असाइनमेंट) को आर्काइव में शामिल करता है — कभी कोई सादा रहस्य नहीं, इसलिए `--include-auth` के विपरीत `--confirm-secrets` की आवश्यकता नहीं।

## 11b. संवेदनशील पाथ की सूचियाँ (WAF)

WAF टेक्स्ट फ़ाइल में **संपादन योग्य सूचियाँ** लोड कर सकता है, हर पंक्ति में एक पाथ (या एक कीवर्ड), **एक्टिव सुरक्षा → Custom → जोड़ें → «पाथ सूची लोड करें»** से। डिफ़ॉल्ट रूप से कुछ भी कभी लोड नहीं होता: यह एक स्पष्ट क्रिया है।

- **साथ आने वाली संदर्भ सूचियाँ**: `sensitive-paths-hostile` (बिना वैध उपयोग वाले 298 पाथ: रहस्य, बैकअप, VCS, कंसोल…) और `sensitive-paths-probe` (जाँच के 132 पाथ, जिन्हें कभी-कभी असली साइट भी परोसती है: `/admin`, `/api`, निगरानी…)। लोड करते समय `secure/waf/rules/keywords/` में एक **स्थानीय प्रति** बनाई जाती है: आप इसी को बदलते हैं, omega-serv का अपडेट इसे कभी ओवरराइट नहीं करता (बाद में «संदर्भ सूची में नया» नई प्रविष्टियाँ एक-एक करके सुझाता है)।
- **सिंटैक्स**: `/admin` (→ `/admin` और `/admin/xxx`, कभी `/administrator` नहीं), `/.git/` (इसके नीचे सब कुछ), `/*.bak` (एक्सटेंशन), `!/api/v1` (अपवाद, हमेशा प्राथमिकता)। पाथ इंजन की तरह ही डिकोड किए जाते हैं (`%2e`, दोहरी एन्कोडिंग, पूर्ण-चौड़ाई अक्षर)।
- **गंभीरता**: *ऑब्ज़र्वेशन* (केवल लॉग, पहली बार लोड करने पर अनुशंसित), फिर मध्यम (अकेले कभी ब्लॉक नहीं करता) या उच्च (पहली पहुँच से ही 403)।
- **हर सूची की अपनी पुनरावृत्ति**: पहली पहुँच = सूचना या अस्वीकृति; M मिनट में N पहुँच = अस्थायी एप्लिकेशन प्रतिबंध (उत्तर 451, Tailscale से भी); बार-बार ब्लॉक = omega-jail द्वारा नेटवर्क प्रतिबंध। संदर्भ: hostile 10 मिनट में 2 पहुँच → 24 घंटे, probe 10 मिनट में 5 → 1 घंटा।
- स्थानीय host, Tailscale (`100.64.0.0/10`) और स्थानीय नेटवर्क (`options.waf.reputation.never_auto_block`) के लिए **कभी स्वचालित प्रतिबंध नहीं**: केवल बाहरी ट्रैफ़िक प्रतिबंधित हो सकता है। स्थानीय प्रॉक्सी के पीछे, `127.0.0.1` की छूट के लिए `trusted_proxy` सक्रिय होना चाहिए। `X-Forwarded-For` दाएँ से बाएँ पढ़ा जाता है: कोई क्लाइंट स्वयं को स्थानीय घोषित नहीं कर सकता।
- **सुरक्षा उपाय**: महत्वपूर्ण पाथ सुरक्षित (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), ऐसी ब्लॉक करने वाली सूची की अस्वीकृति जो वास्तव में परोसे जा रहे route (alias, रिवर्स प्रॉक्सी, Auth ज़ोन, webroot) को छूती हो, संपादक में **«मेरे लॉग से जाँचें»** (वे पंक्तियाँ जो सफल अनुरोधों को छू जातीं, एक क्लिक में अपवाद)।
- **अंतर्निहित संपादक**: पंक्ति संख्या के साथ लाइव निदान, किसी पाथ का «टेस्ट», सुरक्षित लेखन (अनुमतियाँ और समूह संरक्षित, symbolic links अस्वीकृत, बाहरी बदलाव की पहचान), सर्विस खाते द्वारा पठनीयता की जाँच («अनुमतियाँ ठीक करें»), और **ईमानदार** रीलोड: सूची जाँच में पास न हो तो कारण के साथ अस्वीकृत, तब सर्वर अपने वर्तमान नियम बनाए रखता है।

## 11c. फ़ोल्डर और IP/नेटवर्क के अनुसार दर सीमा (WAF)

WAF की दर सीमा (token bucket, `options.waf.rate_limit`, डिफ़ॉल्ट रूप से प्रति IP 60 अनुरोध / 60 s) को **एक्टिव सुरक्षा → अपवाद और दर सीमा** से (या हाथ से, `rate_limit.path_policies` / `rate_limit.source_policies`) बारीकी से समायोजित किया जा सकता है:

- **फ़ोल्डर के अनुसार नियम** (`prefix`, `requests`, `window_seconds`): यह उस फ़ोल्डर के लिए वैश्विक सीमा को **बदल देता है**, अपने काउंटर के साथ (`requests: 0` = असीमित)। सबसे लंबा prefix जीतता है; `/images` में `/images/a.png` आता है, कभी `/images2` नहीं। आमतौर पर एक भारी पेज (इमेज गैलरी) जो 429 लौटाता है।
- **IP/नेटवर्क के अनुसार नियम** (`network`, `requests`, `window_seconds`, `trusted`): वही सिद्धांत; सबसे सटीक नेटवर्क जीतता है। प्राथमिकता: फ़ोल्डर, फिर IP/नेटवर्क, फिर वैश्विक सीमा।
- **सार्वजनिक के लिए प्रतिबंध अपरिवर्तित**: किसी सार्वजनिक IP द्वारा सीमा पार करना `waf-alerts.log` में `"action": "block"` के रूप में ही लॉग होता है, इसलिए omega-jail द्वारा प्रतिबंधित किया जा सकता है (10 मिनट में 3 अस्वीकृति → 12 घंटे)। एक **सुरक्षित स्रोत** — `never_auto_block` नेटवर्क या `trusted: true` चिह्नित नियम — को फिर भी 429 मिलता है लेकिन वह `"action": "throttle"` के रूप में लॉग होता है, जिसे jail कभी नहीं गिनता।
- **Magnet स्क्रिप्ट**: इसकी अपनी rate limit (उत्तर 429) कभी पहचान के रूप में नहीं गिनी जाती, इसलिए कभी स्वचालित प्रतिबंध तक नहीं ले जाती; फ़ोल्डर या IP/नेटवर्क नियम के दायरे में आने वाले अनुरोध पर मूल नियम ही मान्य होता है और magnet का 429 अनदेखा किया जाता है (इसके हमला सिग्नेचर लागू रहते हैं)।
- दर सीमा का नियम WAF निरीक्षण को **कभी** अक्षम नहीं करता; उलटे, निरीक्षण अपवाद (`exclusions.path_prefixes`) rate limit को कभी नहीं हटाता। `trusted_proxy` सक्रिय न होने पर, `127.0.0.1`/`::1` को कवर करने वाला नियम अनदेखा किया जाता है (`never_auto_block` वाला ही सुरक्षा उपाय)।

## 12. सर्विस और संचालन

systemd/OpenRC/runit की स्वचालित पहचान (`service install/status/start/stop/restart/enable/disable/uninstall`)। बनाई गई systemd यूनिट डिफ़ॉल्ट रूप से गैर-परक्राम्य मज़बूती लागू करती है: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `var/` तक सीमित `ReadWritePaths`, समर्पित उपयोगकर्ता/समूह अनिवार्य, `UMask=0077`, `Restart=on-failure`। SIGTERM पर साफ़ बंद (चल रहे कनेक्शनों को निपटाना, कॉन्फ़िगर करने योग्य grace period फिर ज़बरदस्ती बंद); SIGHUP पर हॉट रीलोड (केवल WAF नियम और Auth ज़ोन — bind/पोर्ट/TLS और Active Defense पूर्ण रीस्टार्ट के बिना कभी नहीं बदले जा सकते)।

## 13. लॉग

`var/log/access.log` (Apache combined फ़ॉर्मेट + `request_id`, log injection-रोधी escaping), `var/log/error.log`। आकार/रखी गई फ़ाइलों की संख्या के अनुसार रोटेशन (`logs.rotation`)। मूल WAF: `var/log/waf-alerts.log` (`options.waf.logging.path`)। Magnet स्क्रिप्ट (§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, डिफ़ॉल्ट `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — लाइब्रेरी में सीधे जोड़े जाते हैं (बटन *Omega-Serv के ज्ञात लॉग जोड़ें*) केवल तभी जब magnet सक्रिय हो; इसके विपरीत `lnav` उन्हें हमेशा सुझाता है (अनुपस्थित फ़ाइल लॉन्च पर बस अनदेखी कर दी जाती है)।

### 13a. रिमोट स्रोत (SSH)

स्पष्ट अनुरोध पर, रिवर्स प्रॉक्सी के पीछे उसी स्थानीय नेटवर्क पर स्थित backend सर्वर का लॉग केंद्रीकृत करता है (स्क्रीन **लॉग प्रबंधन → लाइब्रेरी → रिमोट स्रोत (SSH)**)। एक «fetch» मैनुअल और एक बार की क्रिया है, कभी लाइव प्रवाह या स्वचालित polling नहीं: *अभी प्राप्त करें* पर क्लिक के समय `scp` से एक **प्रति** प्राप्त की जाती है, `var/log/remote/` के अंतर्गत लिखी जाती है, फिर सामान्य लॉग की तरह लाइब्रेरी में जोड़ी जाती है (*एक्सेस* कॉलम = `ssh`, *संशोधित* कॉलम = **इसी** प्राप्ति की तारीख — दूरस्थ फ़ाइल की कभी नहीं); नई प्राप्ति बस पिछली प्रति को नई प्रति से बदल देती है।

जानबूझकर रखे गए सुरक्षा उपाय (पूरे अध्ययन के लिए `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` देखें): कोई स्वचालित नेटवर्क स्कैन नहीं, स्पष्ट कॉन्फ़िगरेशन के बिना कोई कनेक्शन नहीं (लेबल/host/दूरस्थ पाथ, उपयोगकर्ता/पोर्ट/निजी कुंजी वैकल्पिक — खाली हों तो `ssh`/`~/.ssh/config` वैसे ही तय करते हैं जैसे कमांड हाथ से टाइप की गई हो), कभी कोई पासवर्ड माँगा या सहेजा नहीं जाता (निजी कुंजी केवल उसके पाथ से संदर्भित होती है, Omega-serv उसे कभी पढ़ता या सहेजता नहीं), स्थानांतरण से पहले आकार की कोई जाँच नहीं। `scp` क्षमता स्थानीय रूप से **क्षमता रजिस्टर** में पहचानी जाती है (केवल बाइनरी की उपस्थिति, किसी host की पहुँच का परीक्षण कभी नहीं); Samba को स्पष्ट रूप से अलग रखा गया (YAGNI, जब तक कोई वास्तविक ज़रूरत पुष्ट न हो)।

## 14. परीक्षण

```bash
source .venv/bin/activate
lint-imports        # परतों के 8 अनुबंध जाँचता है
pytest -q           # 2485 परीक्षण
ruff check .
mypy src
```

संरचना: `tests/unit/` (domain/application, test doubles), `tests/integration/` (असली TCP sockets पर असली asyncio सर्वर, sub-process में असली `openssl`, पूर्ण अस्थायी प्रोजेक्ट पर असली CLI कमांड, Textual की `Pilot` API से इंटरैक्टिव इंटरफ़ेस - कभी स्क्रीनशॉट नहीं), `tests/security/` (HTTP पार्सर और पाथ रिज़ॉल्वर पर `hypothesis` property tests)।

## 15. दायरे से बाहर

- कच्चा CGI (केवल FastCGI/PHP-FPM)
- mTLS (प्रमाणपत्र द्वारा क्लाइंट प्रमाणीकरण), OCSP stapling
- बाहरी CA / तीसरे पक्ष के प्राधिकरण के लिए CSR, पूर्ण CRL वितरण
- Active Defense: `omega-fire` की प्रतिबंध घटनाओं के साथ वास्तविक एकीकरण (`omega-fire` की ओर से अवरुद्ध, जो आज पढ़ने का कोई इंटरफ़ेस उपलब्ध नहीं कराता)

---

> 🔒 OMEGA-SERV — एक मज़बूत, पूर्ण, सुरक्षित और रक्षात्मक वेब सर्वर।

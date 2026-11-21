# omega-serv في مواجهة خوادم الويب في السوق — النسخة البيانية

**omega-serv في مواجهة nginx · lighttpd · Apache · Caddy · Traefik — قياسات على ثلاثة أجهزة (نوفمبر 2026).**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · [Español](../es/comparatif-server-web-graphique.md) · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · [Nederlands](../nl/comparatif-server-web-graphique.md) · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · **العربية**

> **طريقة القراءة:** كلما كان الشريط أطول كان الخادم أسرع. المرجع **nginx = 1.00**.

## دليل الألوان

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-1.png" alt="دليل الألوان" width="1024">
</div>

---

## 📊 ملفات 1 KB — الإنتاجية (طلب/ثانية)

الأجهزة A (i5 2010) وB (Celeron 2016) وC (Ryzen 2024). الأشرطة مُطبَّعة بالنسبة إلى nginx (1.00) على الجهاز نفسه.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-2.png" alt="ملفات 1 KB — الأجهزة A وB وC" width="1024">
</div>

> \* الجهاز C: يستخدم المحرك الأصلي 4 أنوية، وnginx 2 عمليات (2 أنوية). عند تساوي الأنوية تعود النسبة إلى ~0.70.
---

## 📦 ملفات متوسطة (100 KB) — وضع الويب العادي

هنا يفاجئ Apache: فهو يتجاوز في الغالب المحرك الأصلي لـ omega-serv. ويظل lighttpd الأسرع. المرجع: nginx = 1.00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-3.png" alt="ملفات 100 KB — الأجهزة A وB وC" width="1024">
</div>

---

## 💿 ملفات كبيرة (5 MB) — وضع الويب العادي

في الملفات الكبيرة تتقارب الخوادم: فنواة النظام هي التي تنسخ البيانات (sendfile). Caddy استثناء على الجهاز C. الإنتاجية بوحدة MB/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-4.png" alt="ملفات 5 MB — الأجهزة A وB وC" width="1024">
</div>

---

## 🔄 الوكيل العكسي — ردود صغيرة (1 KB)

كل وكيل يمرّر الطلبات إلى خادم خلفي nginx. المرجع: nginx = 1.00. الجهاز C: 4 عمليات.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-5.png" alt="الوكيل 1 KB — الأجهزة A وB وC" width="1024">
</div>

---

## 🔄 الوكيل العكسي — ردود 100 KB

في الردود المتوسطة يتعادل omega-serv الأصلي مع nginx أو يتجاوزه.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-6.png" alt="الوكيل 100 KB — الأجهزة A وB وC" width="1024">
</div>

---

## 💾 الذاكرة (PSS) — في السكون → بعد الحمل

كلما كان الشريط أقصر كان الخادم أكثر اقتصادًا. lighttpd وnginx وApache هي الأكثر اقتصادًا، ويليها omega-serv 3.0.0 (أُعيد قياسه في 19 نوفمبر) بـ 10 إلى 16 MB مع المحرك الأصلي.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-7.png" alt="الذاكرة — الأجهزة A وB وC" width="1024">
</div>

---

## 🏆 ترتيب وضع الويب العادي — من الأسرع؟

خلاصة الأجهزة الثلاثة في تقديم الملفات الثابتة.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 omega-serv natif — très bon, 2ᵉ en reverse proxy · 4. Apache — bon, robuste, écosystème · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-8.png" alt="ترتيب وضع الويب العادي" width="1024">
</div>

---

## 🔄 ترتيب الوكيل العكسي — من الأفضل؟

يبقى nginx المرجع؛ وomega-serv الأصلي هو الأقرب إليه، متقدمًا كثيرًا على البقية.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-9.png" alt="ترتيب الوكيل العكسي" width="1024">
</div>

---

## 🆚 وجهًا لوجه — ترتيب الويب والوكيل العكسي جنبًا إلى جنب

استخدامان وترتيبان. قد يتألق خادم في أحدهما ويخيب في الآخر: Apache يفاجئ في التمرير، وCaddy يخيب في كل شيء إلا بساطته.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/ar/omega-serv/stats-10.png" alt="وجهًا لوجه: الويب مقابل الوكيل العكسي" width="1024">
</div>

### خلاصة مقارنة

| الخادم | الموقع |
|---|---|
| 🟢 **omega-serv الأصلي** | الأكثر تنوعًا: المركز 3 في الويب، **المركز 2 في الوكيل العكسي**. الخادم الوحيد المزوّد بـ WAF مدمج الذي يبقى متقدمًا على lighttpd وApache في التمرير. أفضل حل وسط لأداة واحدة تغطي الاستخدامين، مع الأمان فوق ذلك. |
| 🔵 **nginx** | الأكثر انتظامًا: المركز 2 في الويب، **المركز 1 في الوكيل العكسي**. دائمًا في أعلى الترتيب، دون نقطة ضعف بارزة. الخيار الافتراضي عند عدم وجود متطلبات خاصة. |
| 🟢 **lighttpd** | عدّاء الملفات الثابتة: **المركز 1 في الويب**، لكنه في المركز 4 في التمرير. الأفضل للمحتوى الثابت الخالص، ويفسح المجال لـ omega-serv أو nginx متى أُضيف وكيل عكسي. |
| 🔴 **Apache** | المثال المعاكس: المركز 4 في الويب، والمركز 5 في التمرير. في الملفات الكبيرة يفاجئ حتى nginx (الجهاز C). ليس الأسرع ولا الأخف: تبقى ميزته منظومة PHP. |
| 🟠 **Caddy** | البساطة قبل السرعة: المركز 5 في الويب، **المركز 7 في التمرير**. ليس مصممًا للإنتاجية: HTTPS تلقائي وإعداد قصير. يُخصَّص للمشاريع الصغيرة. |
| 🟣 **Traefik** | خارج فئة الويب: ليس خادم ملفات، والمركز 6 في التمرير. ميدانه Docker وKubernetes، لا الأداء الخام. |

---

## 📋 جدول ملخص كامل — النسب مقارنةً بـ nginx (1.00)

نظرة شاملة على **جميع** المقاييس: وضع الويب العادي (1 KB و100 KB و5 MB) والوكيل العكسي (1 KB و100 KB)، إضافةً إلى الذاكرة. كلما اقتربت القيمة من 1.00 أو تجاوزتها كان أفضل.

| الخادم | ويب 1 KB (A/B/C) | ويب 100 KB (A/B/C) | ويب 5 MB (A/B/C) | وكيل 1 KB (A/B/C) | وكيل 100 KB (A/B/C) | الذاكرة (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1.52 / 1.26 / 1.53 | 1.08 / 1.07 / 1.26 | 1.05 / 0.99 / 0.81 | 0.61 / 0.56 / 0.53 | 0.74 / 0.62 / 0.96 | 1 MB |
| **nginx** | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 4–5 MB |
| **omega-serv (أصلي)** | **0.70 / 0.67 / 1.15\*** | **0.38 / 0.28 / 0.61** | **0.99 / 0.91 / 1.09** | **0.85 / 0.91 / 0.82** | **1.11 / 0.97 / 1.43** | 10–16 MB |
| **omega-serv + WAF** | 0.56 / 0.53 / 1.07\* | 0.37 / 0.27 / 0.62 | — | 0.81 / 0.89 / 0.77 | 1.10 / 0.93 / 1.30 | 28–33 MB |
| **Apache** | 0.42 / 0.35 / 0.76 | 0.55 / 0.62 / 0.97 | 1.01 / 1.00 / 1.19 | 0.59 / 0.53 / 0.50 | 0.62 / 0.65 / 0.71 | 4–9 MB |
| **Caddy** | 0.26 / 0.17 / 0.21 | 0.40 / 0.33 / 0.14 | 0.95 / 0.94 / 0.11 | 0.32 / 0.28 / 0.23 | 0.60 / 0.54 / 0.59 | 46–67 MB |
| **Traefik** | — | — | — | 0.35 / 0.35 / 0.29 | 0.64 / 0.60 / 0.70 | 93–131 MB |
| **omega-serv (Python)** | 0.11 / 0.05 / 0.08 | 0.14 / 0.10 / 0.12 | 0.92 / 0.91 / 0.75 | 0.09 / 0.08 / 0.07 | 0.21 / 0.19 / — | 20–48 MB |

> \* الجهاز C: 4 أنوية للأصلي مقابل 2 لـ nginx؛ وعند تساوي الأنوية تبلغ النسبة ~0.67–0.71.
> القيم الثلاث في كل خلية تقابل الأجهزة **A / B / C**. «—»: لم يُقَس أو لا ينطبق.

---

## ⚖️ نقاط القوة والضعف — جميع الخوادم

لكل خادم ميزاته وحدوده. هذه هي الصورة الكاملة، دون محاباة.

### 🟢 omega-serv (أصلي)

**نقاط القوة**
- ✅ إدارة كاملة من الطرفية (TUI، 17 لغة)
- ✅ WAF + Active Defense + RIPOSTE مدمجة
- ✅ محرك أصلي بلغة C++: نحو 0.7× من nginx في المحتوى الثابت
- ✅ المركز 2 في الوكيل العكسي بعد nginx
- ✅ حدود مشتركة بين العمليات (أمان دقيق)
- ✅ استيراد سكربتات lighttpd mod_magnet
- ✅ إدارة عدة نسخ
- ✅ إدارة عبر الويب


**نقاط الضعف**
- ❌ لا HTTP/2 ولا HTTP/3
- ❌ لا ضغط أثناء التشغيل
- ❌ لا اكتشاف تلقائي لـ Docker/Kubernetes
- ❌ ACME عبر Certbot (غير مدمج أصلًا)
- ❌ ملفات 100 KB: 0.3–0.6× من nginx
- ❌ الذاكرة 10–55 MB حسب الوضع (مقابل 1–5 MB في nginx/lighttpd)
- ❌ منظومة ناشئة، يتولى صيانتها شخص واحد

---

### 🔵 nginx

**نقاط القوة**
- ✅ المرجع في الأداء والاستقرار
- ✅ HTTP/2 وHTTP/3 والضغط
- ✅ منظومة ضخمة (وحدات، وثائق، مجتمع)
- ✅ اقتصادي جدًا في الذاكرة (4–5 MB)
- ✅ وكيل عكسي ممتاز
- ✅ وحدة ACME رسمية
- ✅ إعداد ناضج ومجرَّب

**نقاط الضعف**
- ❌ إعداد مطوّل، وصياغة خاصة تحتاج إلى تعلّم
- ❌ لا WAF مدمج (يتطلب ModSecurity أو ما يعادله)
- ❌ لا واجهة إدارة أصلية
- ❌ إعادة تحميل الإعداد دقيقة أحيانًا في الإنتاج
- ❌ النسخة مفتوحة المصدر محدودة (بعض الميزات في Nginx Plus المدفوع)
- ❌ لا اكتشاف أصلي لـ Docker/Kubernetes (عبر القوالب)

---

### 🟢 lighttpd

**نقاط القوة**
- ✅ الأسرع في الملفات الصغيرة والمتوسطة
- ✅ الأكثر اقتصادًا في الذاكرة (1 MB)
- ✅ خفيف، يناسب الأنظمة محدودة الموارد
- ✅ وكيل عكسي جيد
- ✅ إعداد بسيط ومقروء

**نقاط الضعف**
- ❌ لا HTTP/3 (HTTP/2 جزئي بحسب البناء)
- ❌ المركز 4 فقط في الوكيل العكسي (0.53–0.61× من nginx)
- ❌ منظومة أضيق من nginx/Apache
- ❌ لا WAF مدمج
- ❌ لا اكتشاف تلقائي لـ Docker/Kubernetes
- ❌ تطوير أقل نشاطًا مما كان
- ❌ ضعيف في الملفات الكبيرة (0.81× من nginx على الجهاز C)

---

### 🔴 Apache

**نقاط القوة**
- ✅ منظومة تاريخية ضخمة (وحدات، `.htaccess`، PHP)
- ✅ متين ومجرَّب منذ عقود
- ✅ ممتاز في الملفات الكبيرة (يتجاوز nginx على الجهاز C)
- ✅ دعم `.htaccess` دون إعادة تشغيل
- ✅ الضغط وHTTP/2 وACME متاحة
- ✅ وثائق وافرة

**نقاط الضعف**
- ❌ بطيء في الملفات الصغيرة (0.35–0.42× من nginx)
- ❌ نهم للذاكرة في وضع prefork (4–9 MB، ترتفع بسرعة تحت الحمل)
- ❌ نموذج عمليات أقل كفاءة من النموذج المبني على الأحداث
- ❌ إعداد مطوّل
- ❌ المركز 5 في الوكيل العكسي (0.50–0.59× من nginx)
- ❌ لا WAF مدمج (ModSecurity وحدة منفصلة)
- ❌ سطح هجوم أوسع تاريخيًا

---

### 🟠 Caddy

**نقاط القوة**
- ✅ HTTPS تلقائي (ACME مدمج، دون إعداد)
- ✅ إعداد قصير جدًا ومقروء (Caddyfile)
- ✅ HTTP/2 وHTTP/3 أصليان
- ✅ ملف تنفيذي واحد، نشر بسيط
- ✅ وكيل عكسي مقبول في الردود المتوسطة

**نقاط الضعف**
- ❌ بطيء في الإنتاجية الخام (المركز 5 في الويب، 7 في التمرير)
- ❌ ذاكرة مرتفعة (46–67 MB)
- ❌ ضعيف جدًا في الملفات الكبيرة على الجهاز C (0.11× من nginx)
- ❌ لا WAF مدمج
- ❌ منظومة أحدث من nginx/Apache
- ❌ لا يناسب الإنتاجية العالية جدًا

---

### 🟣 Traefik

**نقاط القوة**
- ✅ اكتشاف تلقائي لـ Docker/Kubernetes
- ✅ مثالي في بيئات الحاويات
- ✅ HTTPS تلقائي (ACME مدمج)
- ✅ إعداد ديناميكي دون إعادة تشغيل
- ✅ جيد كوكيل عكسي في الردود المتوسطة (0.60–0.70× من nginx)

**نقاط الضعف**
- ❌ ليس خادم ملفات (غائب عن ترتيب الويب)
- ❌ المركز 6 في الوكيل العكسي (0.29–0.35× من nginx في 1 KB)
- ❌ ذاكرة مرتفعة جدًا (93–131 MB)
- ❌ تعقيد الإعداد خارج سياق الحاويات
- ❌ لا WAF مدمج
- ❌ أكبر من اللازم لموقع ثابت بسيط

---

## 🎯 أي خادم لأي استخدام؟

| الاستخدام | الخادم الموصى به | السبب |
|---|---|---|
| موقع كثيف الزيارات | **nginx** أو **lighttpd** | أقصى إنتاجية، HTTP/2-3 |
| جهاز محدود الموارد / مدمج | **lighttpd** | 1 MB من الذاكرة، الأسرع والأقل استهلاكًا |
| HTTPS تلقائي بسيط | **Caddy** | شهادات تلقائية، إعداد قصير |
| Docker / Kubernetes | **Traefik** | اكتشاف الخدمات |
| تطبيق PHP / .htaccess | **Apache** | منظومة تاريخية |
| الوكيل العكسي | **nginx** أو **omega-serv (أصلي)** | أفضل أداء |
| مواقع ويب + أمان + واجهة | **omega-serv (أصلي)** | بنية تحتية كاملة: WAF، إدارة عبر الويب، عدة نسخ، وكيل عكسي، مدير سجلات، نسخ احتياطي… |

---

بيانات مأخوذة من مقارنة omega-serv (نوفمبر 2026) — kraynux. الرخصة MIT.
[oha](https://github.com/hatoo/oha) للقياس · رسوم HTML/CSS مستقلة.

> *نسخة بيانية من مقارنة omega-serv المقيسة (الأرقام نفسها الواردة في المقارنة التفصيلية: قياسات 3 و4 نوفمبر 2026 على ثلاثة أجهزة؛ الوكيل العكسي: 14 نوفمبر 2026؛ ذاكرة omega-serv 3.0.0: 19 نوفمبر 2026). لأي قرار يتعلق بالسعة، قِس على عتادك الخاص.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — الرخصة MIT (انظر ملف LICENSE).

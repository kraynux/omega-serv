# omega-serv frente a los servidores web del mercado — versión gráfica

**omega-serv frente a nginx · lighttpd · Apache · Caddy · Traefik — mediciones en tres máquinas (nov. 2026).**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · **Español** · [Português (Brasil)](../pt-BR/comparatif-server-web-graphique.md) · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · [Nederlands](../nl/comparatif-server-web-graphique.md) · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **Lectura:** cuanto más larga es la barra, más rápido es el servidor. La referencia es **nginx = 1,00**.

## Leyenda de colores

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-1.png" alt="Leyenda de colores" width="1024">
</div>

---

## 📊 Archivos de 1 KB — rendimiento (peticiones/s)

Máquinas A (i5 2010), B (Celeron 2016) y C (Ryzen 2024). Las barras están normalizadas respecto a nginx (1,00) en la misma máquina.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-2.png" alt="Archivos de 1 KB — máquinas A, B y C" width="1024">
</div>

> \* Máquina C: el motor nativo usa 4 núcleos, nginx 2 procesos (2 núcleos). Con los mismos núcleos, la relación baja a ~0,70.
---

## 📦 Archivos medianos (100 KB) — modo web normal

Aquí, Apache sorprende: a menudo supera al motor nativo de omega-serv. lighttpd sigue siendo el más rápido. Referencia: nginx = 1,00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-3.png" alt="Archivos de 100 KB — máquinas A, B y C" width="1024">
</div>

---

## 💿 Archivos grandes (5 MB) — modo web normal

En los archivos grandes, los servidores se igualan: es el núcleo del sistema el que copia los datos (sendfile). Caddy es la excepción en la máquina C. Rendimiento en MB/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-4.png" alt="Archivos de 5 MB — máquinas A, B y C" width="1024">
</div>

---

## 🔄 Proxy inverso — respuestas pequeñas (1 KB)

Cada proxy reenvía a un backend nginx. Referencia: nginx = 1,00. Máquina C: 4 procesos.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-5.png" alt="Proxy 1 KB — máquinas A, B y C" width="1024">
</div>

---

## 🔄 Proxy inverso — respuestas de 100 KB

En las respuestas medianas, omega-serv nativo iguala o supera a nginx.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-6.png" alt="Proxy 100 KB — máquinas A, B y C" width="1024">
</div>

---

## 💾 Memoria (PSS) — en reposo → tras la carga

Cuanto más corta es la barra, más sobrio es el servidor. lighttpd, nginx y Apache son los más sobrios; omega-serv 3.0.0 (medido de nuevo el 19 de noviembre) los sigue, con 10 a 16 MB para el motor nativo.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-7.png" alt="Memoria — máquinas A, B y C" width="1024">
</div>

---

## 🏆 Clasificación web normal — ¿quién es el más rápido?

Síntesis de las tres máquinas sirviendo archivos estáticos.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 Apache — bon, robuste, écosystème · 4. omega-serv natif — très bon, 2ᵉ en reverse proxy · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-8.png" alt="Clasificación web normal" width="1024">
</div>

---

## 🔄 Clasificación proxy inverso — ¿quién es el mejor?

nginx sigue siendo la referencia; omega-serv nativo es su subcampeón más cercano, muy por delante de los demás.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-9.png" alt="Clasificación proxy inverso" width="1024">
</div>

---

## 🆚 Cara a cara — clasificación web y proxy inverso lado a lado

Dos usos, dos clasificaciones. Un servidor puede brillar en una y decepcionar en la otra: Apache sorprende reenviando, Caddy decepciona en todo salvo en su simplicidad.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-serv/stats-10.png" alt="Cara a cara web frente a proxy inverso" width="1024">
</div>

### Síntesis cruzada

| Servidor | Posicionamiento |
|---|---|
| 🟢 **omega-serv nativo** | El más polivalente: 4.º en web, **2.º en proxy inverso**. Único servidor con un WAF integrado que se mantiene por delante de lighttpd y Apache al reenviar. El mejor compromiso para una sola herramienta que cubra los dos usos, con la seguridad además. |
| 🔵 **nginx** | El más regular: 2.º en web, **1.º en proxy inverso**. Siempre en la parte alta de la clasificación, sin punto débil destacado. La elección por defecto sin exigencia particular. |
| 🟢 **lighttpd** | El velocista de lo estático: **1.º en web**, pero 4.º reenviando. La mejor elección para estático puro, cede el sitio a omega-serv o nginx en cuanto se añade proxy inverso. |
| 🔴 **Apache** | El contraejemplo: 3.º en web, 5.º reenviando. En los archivos grandes, incluso sorprende a nginx (máquina C). Ni el más rápido ni el más ligero: su baza sigue siendo el ecosistema PHP. |
| 🟠 **Caddy** | La simplicidad antes que la velocidad: 5.º en web, **7.º reenviando**. No está hecho para el rendimiento: HTTPS automático y configuración corta. Para reservar a proyectos pequeños. |
| 🟣 **Traefik** | Fuera de la categoría web: no es un servidor de archivos, 6.º reenviando. Su terreno sigue siendo Docker y Kubernetes, no el rendimiento bruto. |

---

## 📋 Tabla resumen completa — ratios frente a nginx (1,00)

Vista general de **todas** las métricas: modo web normal (1 KB, 100 KB, 5 MB) y proxy inverso (1 KB, 100 KB), más la memoria. Cuanto más cerca de 1,00 o por encima esté el valor, mejor.

| Servidor | Web 1 KB (A/B/C) | Web 100 KB (A/B/C) | Web 5 MB (A/B/C) | Proxy 1 KB (A/B/C) | Proxy 100 KB (A/B/C) | Memoria (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1,52 / 1,26 / 1,53 | 1,08 / 1,07 / 1,26 | 1,05 / 0,99 / 0,81 | 0,61 / 0,56 / 0,53 | 0,74 / 0,62 / 0,96 | 1 MB |
| **nginx** | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 4–5 MB |
| **omega-serv (nativo)** | **0,70 / 0,67 / 1,15\*** | **0,38 / 0,28 / 0,61** | **0,99 / 0,91 / 1,09** | **0,85 / 0,91 / 0,82** | **1,11 / 0,97 / 1,43** | 10–16 MB |
| **omega-serv + WAF** | 0,56 / 0,53 / 1,07\* | 0,37 / 0,27 / 0,62 | — | 0,81 / 0,89 / 0,77 | 1,10 / 0,93 / 1,30 | 28–33 MB |
| **Apache** | 0,42 / 0,35 / 0,76 | 0,55 / 0,62 / 0,97 | 1,01 / 1,00 / 1,19 | 0,59 / 0,53 / 0,50 | 0,62 / 0,65 / 0,71 | 4–9 MB |
| **Caddy** | 0,26 / 0,17 / 0,21 | 0,40 / 0,33 / 0,14 | 0,95 / 0,94 / 0,11 | 0,32 / 0,28 / 0,23 | 0,60 / 0,54 / 0,59 | 46–67 MB |
| **Traefik** | — | — | — | 0,35 / 0,35 / 0,29 | 0,64 / 0,60 / 0,70 | 93–131 MB |
| **omega-serv (Python)** | 0,11 / 0,05 / 0,08 | 0,14 / 0,10 / 0,12 | 0,92 / 0,91 / 0,75 | 0,09 / 0,08 / 0,07 | 0,21 / 0,19 / — | 20–48 MB |

> \* Máquina C: 4 núcleos para el nativo frente a 2 para nginx; con los mismos núcleos, ratio ~0,67–0,71.
> Los tres valores de cada celda corresponden a las máquinas **A / B / C**. «—»: no medido o no aplicable.

---

## ⚖️ Puntos fuertes y débiles — todos los servidores

Cada servidor tiene sus ventajas y sus límites. Aquí está la vista completa, sin favoritismos.

### 🟢 omega-serv (nativo)

**Puntos fuertes**
- ✅ Administración completa en terminal (TUI, 17 idiomas)
- ✅ WAF + Active Defense + RIPOSTE integrados
- ✅ Motor nativo C++: ~0,7× nginx en estático
- ✅ 2.º en proxy inverso por detrás de nginx
- ✅ Límites compartidos entre procesos (seguridad exacta)
- ✅ Importación de scripts lighttpd mod_magnet
- ✅ Gestión multiinstancia
- ✅ Administración web


**Puntos débiles**
- ❌ Sin HTTP/2 ni HTTP/3
- ❌ Sin compresión al vuelo
- ❌ Sin descubrimiento Docker/Kubernetes
- ❌ ACME mediante Certbot (no integrado de forma nativa)
- ❌ Archivos de 100 KB: 0,3–0,6× nginx
- ❌ Memoria 10–55 MB según el modo (frente a 1–5 MB nginx/lighttpd)
- ❌ Ecosistema joven, mantenido por una persona

---

### 🔵 nginx

**Puntos fuertes**
- ✅ Referencia de rendimiento y estabilidad
- ✅ HTTP/2, HTTP/3, compresión
- ✅ Ecosistema inmenso (módulos, documentación, comunidad)
- ✅ Muy sobrio en memoria (4–5 MB)
- ✅ Proxy inverso excelente
- ✅ Módulo ACME oficial
- ✅ Configuración madura y probada

**Puntos débiles**
- ❌ Configuración verbosa, sintaxis propia que aprender
- ❌ Sin WAF integrado (requiere ModSecurity o equivalente)
- ❌ Sin interfaz de administración nativa
- ❌ Recarga de la configuración a veces delicada en producción
- ❌ Versión de código abierto limitada (algunas funciones en Nginx Plus de pago)
- ❌ Sin descubrimiento Docker/Kubernetes nativo (mediante plantillas)

---

### 🟢 lighttpd

**Puntos fuertes**
- ✅ El más rápido en archivos pequeños/medianos
- ✅ El más sobrio en memoria (1 MB)
- ✅ Ligero, adaptado a sistemas con recursos limitados
- ✅ Buen proxy inverso
- ✅ Configuración simple y legible

**Puntos débiles**
- ❌ Sin HTTP/3 (HTTP/2 parcial según la compilación)
- ❌ Solo 4.º en proxy inverso (0,53–0,61× nginx)
- ❌ Ecosistema más reducido que nginx/Apache
- ❌ Sin WAF integrado
- ❌ Sin descubrimiento Docker/Kubernetes
- ❌ Desarrollo menos activo que antes
- ❌ Flojo en archivos grandes (0,81× nginx en la máquina C)

---

### 🔴 Apache

**Puntos fuertes**
- ✅ Ecosistema histórico inmenso (módulos, `.htaccess`, PHP)
- ✅ Robusto y probado desde hace décadas
- ✅ Excelente en archivos grandes (supera a nginx en la máquina C)
- ✅ Compatibilidad con `.htaccess` sin reiniciar
- ✅ Compresión, HTTP/2, ACME disponibles
- ✅ Documentación abundante

**Puntos débiles**
- ❌ Lento en archivos pequeños (0,35–0,42× nginx)
- ❌ Voraz en memoria en modo prefork (4–9 MB, sube rápido bajo carga)
- ❌ Modelo de procesos menos eficiente que el basado en eventos
- ❌ Configuración verbosa
- ❌ 5.º en proxy inverso (0,50–0,59× nginx)
- ❌ Sin WAF integrado (ModSecurity como módulo aparte)
- ❌ Superficie de ataque históricamente mayor

---

### 🟠 Caddy

**Puntos fuertes**
- ✅ HTTPS automático (ACME integrado, cero configuración)
- ✅ Configuración muy corta y legible (Caddyfile)
- ✅ HTTP/2 y HTTP/3 nativos
- ✅ Binario único, despliegue simple
- ✅ Proxy inverso correcto en respuestas medianas

**Puntos débiles**
- ❌ Lento en rendimiento bruto (5.º en web, 7.º reenviando)
- ❌ Memoria elevada (46–67 MB)
- ❌ Muy flojo en archivos grandes en la máquina C (0,11× nginx)
- ❌ Sin WAF integrado
- ❌ Ecosistema más joven que nginx/Apache
- ❌ Poco adecuado para rendimientos muy altos

---

### 🟣 Traefik

**Puntos fuertes**
- ✅ Descubrimiento automático Docker/Kubernetes
- ✅ Ideal en entorno de contenedores
- ✅ HTTPS automático (ACME integrado)
- ✅ Configuración dinámica sin reiniciar
- ✅ Bueno como proxy inverso en respuestas medianas (0,60–0,70× nginx)

**Puntos débiles**
- ❌ No es un servidor de archivos (ausente de la clasificación web)
- ❌ 6.º en proxy inverso (0,29–0,35× nginx en 1 KB)
- ❌ Memoria muy elevada (93–131 MB)
- ❌ Complejidad de configuración fuera del contexto de contenedores
- ❌ Sin WAF integrado
- ❌ Sobredimensionado para un simple sitio estático

---

## 🎯 ¿Qué servidor para qué uso?

| Uso | Servidor recomendado | Motivo |
|---|---|---|
| Sitio con mucho tráfico | **nginx** o **lighttpd** | Rendimiento máximo, HTTP/2-3 |
| Máquina limitada / embebido | **lighttpd** | 1 MB de memoria, el más rápido y el menos voraz |
| HTTPS automático simple | **Caddy** | Certificados automáticos, configuración corta |
| Docker / Kubernetes | **Traefik** | Descubrimiento de servicios |
| Aplicación PHP / .htaccess | **Apache** | Ecosistema histórico |
| Proxy inverso | **nginx** o **omega-serv (nativo)** | Mejor rendimiento |
| Sitios web + seguridad + interfaz | **omega-serv (nativo)** | Infraestructura completa: WAF, administración web, multiinstancia, proxy inverso, gestor de logs, copias de seguridad... |

---

Datos procedentes de la comparativa omega-serv (noviembre de 2026) — kraynux. Licencia MIT.
[oha](https://github.com/hatoo/oha) para la medición · gráficos HTML/CSS autónomos.

> *Versión gráfica de la comparativa medida de omega-serv (mismas cifras que la comparativa detallada: mediciones del 3 y 4 de noviembre de 2026 en tres máquinas; proxy inverso: 14 de noviembre de 2026; memoria de omega-serv 3.0.0: 19 de noviembre de 2026). Para cualquier decisión de capacidad, mida en su propio hardware.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — Licencia MIT (véase el archivo LICENSE).

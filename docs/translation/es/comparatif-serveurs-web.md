<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv frente a los servidores web del mercado

**Comparativa medida: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · **Español** · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Este documento sitúa omega-serv entre los servidores web más extendidos. No pretende designar un «mejor servidor»: cada herramienta responde a necesidades distintas. Aporta tres cosas:

1. **mediciones reales**, hechas en la misma máquina, con el mismo cliente y los mismos archivos, y reproducibles;
2. una **comparativa de funciones**, cada una verificada en la documentación oficial de cada servidor (enlaces al final del documento), distinguiendo lo que está integrado de lo que requiere un módulo o un plugin;
3. lo que omega-serv **aporta realmente de más**, y lo que los demás hacen **mejor que él**.

Todas las cifras siguientes se midieron el 26 de octubre de 2026. Ninguna cifra procede de otro sitio ni es una estimación.

---

## Índice

1. [En resumen](#1-en-resumen)
2. [Método de medición](#2-método-de-medición)
3. [Rendimiento: omega-serv frente a nginx, lighttpd y Caddy](#3-rendimiento-omega-serv-frente-a-nginx-lighttpd-y-caddy)
4. [omega-serv 1.0 → 2.0: qué cambió, medido](#4-omega-serv-10--20-qué-cambió-medido)
5. [Comparativa de funciones](#5-comparativa-de-funciones)
6. [Administración y ergonomía](#6-administración-y-ergonomía)
7. [Lo que omega-serv aporta de más](#7-lo-que-omega-serv-aporta-de-más)
8. [Lo que los demás hacen mejor](#8-lo-que-los-demás-hacen-mejor)
9. [Qué servidor para qué uso](#9-qué-servidor-para-qué-uso)
10. [Reproducir las mediciones](#10-reproducir-las-mediciones)
11. [Fuentes](#11-fuentes)

---

## 1. En resumen

- **Rendimiento bruto con archivos pequeños**: nginx y lighttpd, escritos en C, sirven **de 10 a 20 veces más** peticiones por segundo que omega-serv, escrito en Python. Caddy, escrito en Go, queda en medio. Es una diferencia de naturaleza, no de ajuste: omega-serv no apunta a ese terreno.
- **Archivos grandes**: desde la 2.0, omega-serv confía el envío al núcleo (`sendfile`). Alcanza entonces **el mismo orden de rendimiento** que nginx, lighttpd y Caddy en esta máquina: 2,1 GB/s frente a 2,0–2,4 GB/s.
- **Memoria**: lighttpd (1 MB) y nginx (4–5 MB) quedan fuera de alcance. omega-serv se mantiene por debajo de 30 MB bajo carga con 1 proceso, Caddy en torno a 55 MB.
- **De la 1.0 a la 2.0**: rendimiento con archivos grandes multiplicado por 2,8; memoria durante descargas grandes dividida por 45; hasta +50 % con archivos pequeños usando 2 procesos (modo boost); coste de Active Defense dividido por 12.
- **Lo que omega-serv tiene de más**: administración completa desde una interfaz de terminal (TUI), en 17 idiomas; un WAF y una defensa activa integrados; límites de seguridad que siguen siendo exactos con varios procesos; importación de scripts mod_magnet de lighttpd; gestión de varias instancias.
- **Lo que no tiene**: HTTP/2 y HTTP/3, descubrimiento de servicios Docker/Kubernetes, un cliente ACME integrado (pasa por Certbot), el rendimiento de un servidor escrito en C.

---

## 2. Método de medición

### Máquina y software

| Elemento | Valor |
|---|---|
| Procesador | Intel Core i5 M480 a 2,67 GHz (2010): 2 núcleos físicos, 4 hilos |
| Memoria | 8 GB |
| Sistema | Manjaro Linux, núcleo 6.18 |
| Red | bucle local (127.0.0.1) |
| Cliente de carga | [oha](https://github.com/hatoo/oha) 1.16.0 (escrito en Rust) |
| nginx | 1.30.4 (paquete de Manjaro) |
| lighttpd | 1.4.85 (paquete de Manjaro) |
| Caddy | 2.11.4 (paquete de Manjaro) |
| omega-serv | 1.0.0 (archivo publicado) y 2.0.0, con Python 3.14.7 |

Apache y Traefik no se midieron, por no estar instalados en esta máquina. Traefik, además, no es un servidor de archivos (ver §5). Estos dos servidores solo figuran en la comparativa de funciones.

### Protocolo

- **Aislamiento del procesador**: cada servidor se fija al núcleo físico 0 (hilos 0 y 2) y el cliente al núcleo físico 1 (hilos 1 y 3). Así el cliente no le roba tiempo al servidor, y todos los servidores disponen exactamente de los mismos recursos.
- **Los mismos archivos para todos**: `small.html` (1 KB), `medium.png` (100 KB) y `large.bin` (5 MB), servidos desde la misma carpeta.
- **Registro de accesos activo en todos**, porque un servidor en producción registra.
- **HTTP/1.1 sin cifrar, conexiones persistentes (keep-alive)**. La concurrencia es de 32 conexiones para los archivos de 1 KB y 100 KB, y de 8 para el de 5 MB.
- **Duración**: 10 segundos por archivo y por configuración.
- **Repeticiones**: 3 rondas completas, intercaladas (todos los servidores en la ronda 1, luego todos en la ronda 2, etc.). Las tablas dan la **mediana** de las tres rondas.
- **Memoria**: PSS (*Proportional Set Size*) sumada de todos los procesos del servidor. A diferencia del RSS, una página compartida entre procesos se cuenta una sola vez. Se mide en reposo y después de la carga.
- **Configuraciones**: nginx, lighttpd y Caddy en su configuración básica (archivos estáticos, registro de accesos). omega-serv usa el perfil `standard`, con el WAF desactivado y luego activado con todas sus reglas incluidas.
- **Número de procesos**: cada servidor se mide con 1 y luego con 2 procesos (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Límites que hay que conocer

- **Máquina modesta y antigua.** Los valores absolutos serían mucho más altos en un servidor reciente. Lo que tiene sentido son las **proporciones** entre servidores medidos en la misma sesión.
- **Variabilidad de una sesión a otra**: entre un 10 y un 30 % según la carga de fondo de la máquina. Las rondas de una misma sesión son coherentes: menos de un 5 % de diferencia para omega-serv y Caddy, algo más para nginx y lighttpd, cuyo rendimiento muy alto es más sensible al resto de la máquina.
- **Bucle local**: la medición no pasa por una red real. En una red real, el rendimiento con archivos grandes casi siempre lo limita el ancho de banda, no el servidor.
- **Sin TLS** en estas mediciones. Con HTTPS, omega-serv no puede usar `sendfile` y envía los archivos por bloques.
- **Cifras brutas**: se publican con este documento en [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Rendimiento: omega-serv frente a nginx, lighttpd y Caddy

### Archivos pequeños (1 KB): peticiones por segundo

| Servidor | 1 proceso | 2 procesos | Latencia p99 (1 proc.) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25 521 | 29 700 | 4,5 ms |
| nginx 1.30.4 | 14 054 | 18 315 | 4,7 ms |
| Caddy 2.11.4 | 3 697 | 5 345 | 25,3 ms |
| **omega-serv 2.0** | **1 358** | **1 953** | **37,5 ms** |
| omega-serv 2.0 + WAF | 1 130 | 1 617 | 48,5 ms |
| omega-serv 1.0 | 1 304 | — | 41,2 ms |

### Archivos medianos (100 KB): peticiones por segundo

| Servidor | 1 proceso | 2 procesos |
|---|---:|---:|
| lighttpd | 11 635 | 13 037 |
| nginx | 8 024 | 9 555 |
| Caddy | 3 280 | 4 344 |
| **omega-serv 2.0** | **1 247** | **1 629** |
| omega-serv 2.0 + WAF | 1 012 | 1 347 |
| omega-serv 1.0 | 1 064 | — |

### Archivo grande (5 MB): rendimiento

| Servidor | 1 proceso | 2 procesos |
|---|---:|---:|
| lighttpd | 2 379 MB/s | 2 407 MB/s |
| nginx | 2 242 MB/s | 1 981 MB/s |
| Caddy | 2 165 MB/s | 2 229 MB/s |
| **omega-serv 2.0** | **1 658 MB/s** | **2 115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### Memoria (PSS, todos los procesos del servidor)

| Servidor | En reposo | Tras la carga |
|---|---:|---:|
| lighttpd (1 o 2 proc.) | 1 MB | 1 MB |
| nginx (1 o 2 proc.) | 4–5 MB | 4–5 MB |
| **omega-serv 2.0 (1 proc.)** | **26 MB** | **30 MB** |
| omega-serv 2.0 (2 proc.) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### Lectura

- **Con archivos pequeños y medianos**, la diferencia con nginx y lighttpd es de un orden de magnitud (×10 a ×20). Es el coste de un servidor escrito en Python: cada petición pasa por el intérprete, mientras que nginx y lighttpd la procesan en C compilado. El modo boost reduce la distancia, sin eliminarla.
- **Con archivos grandes**, los servidores se igualan, porque es el núcleo quien copia los datos (`sendfile`). Con 2 procesos, omega-serv 2.0 llega a 2,1 GB/s, en la misma zona que los demás (2,0–2,4 GB/s).
- **El WAF de omega-serv cuesta alrededor de un 17 %** con archivos pequeños: inspecciona cada petición. nginx, lighttpd y Caddy se midieron sin WAF; un WAF añadido a estos servidores (ModSecurity, Coraza) también tiene un coste, no medido aquí.
- **Para situar estas cifras**: 1 300 peticiones por segundo son más de 110 millones de peticiones al día en esta máquina de 2010. Es muy superior a las necesidades de un sitio personal, un servicio interno o un laboratorio, que son los usos a los que apunta omega-serv.

---

## 4. omega-serv 1.0 → 2.0: qué cambió, medido

### Rendimiento

Ambas versiones se midieron en la misma sesión, en la misma máquina y con el mismo protocolo.

| Medición | 1.0.0 | 2.0.0 | Evolución |
|---|---:|---:|---:|
| Archivos pequeños (1 KB), 1 proceso | 1 304 pet/s | 1 358 pet/s | +4 % |
| Archivos pequeños (1 KB), modo boost 2 procesos | — | 1 953 pet/s | **+50 %** vs 1.0 |
| Archivos pequeños con WAF, 1 proceso | 1 097 pet/s | 1 130 pet/s | +3 % |
| Archivos pequeños con WAF, 2 procesos | — | 1 617 pet/s | **+47 %** vs 1.0 |
| Archivos de 100 KB, 1 proceso | 1 064 pet/s | 1 247 pet/s | +17 % |
| Archivo grande (5 MB), 1 proceso | 584 MB/s | 1 658 MB/s | **×2,8** |
| Archivo grande (5 MB), 2 procesos | — | 2 115 MB/s | **×3,6** vs 1.0 |
| Memoria tras la carga, 1 proceso | 100 MB | 30 MB | **÷3** |

### Descargas grandes simultáneas

Prueba: 3 descargas simultáneas de un archivo de 300 MB, mientras se pide continuamente una página pequeña. Dos pasadas dan resultados idénticos.

| Medición | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Memoria máxima del servidor | 1 835 MB | 40 MB |
| Página pequeña durante las descargas: mediana | 3–4 ms | 2 ms |
| Página pequeña durante las descargas: peor caso | 1,7–1,8 s | 5 ms |

La 1.0 cargaba cada archivo entero en memoria antes de enviarlo. La 2.0 lo envía por bloques, o lo confía al núcleo: la memoria ya no depende del tamaño de los archivos, y el servidor sigue respondiendo durante las descargas.

### Coste de la defensa activa

Coste de una observación de amenaza por Active Defense, para cada petición sospechosa, medido en disco (ext4) sobre 2 000 observaciones:

| Medición | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediana | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Máximo | 18–20 ms | 37–46 ms |

La mediana se divide por 12. El máximo, en cambio, es más alto en la 2.0: algunos picos aislados, debidos a la escritura periódica del diario SQLite en disco.

### Funciones que llegaron con la 2.0

**Puesta al nivel de los estándares del mercado**: nginx, lighttpd, Caddy y Apache ya hacen todo esto. omega-serv se pone al día.

- Peticiones condicionales (ETag, Last-Modified, respuestas 304): al recargar una página solo se vuelve a descargar lo que ha cambiado.
- Peticiones parciales (Range, 206/416): reanudar una descarga, avanzar en un vídeo.
- Envío de archivos con `sendfile` o por bloques, con memoria estable.
- Archivos precomprimidos (`.gz`, `.br`) colocados junto al original.
- Cache-Control por defecto según el tipo de archivo (imágenes, fuentes, CSS/JS), ajustable.
- Varios procesos de servidor (modo boost, `server.workers`).

**Funciones más amplias:**

- **Proxy inverso completo.** La 1.0 solo tenía un reenvío simple (turno rotativo, TLS hacia el servidor de origen, WebSocket). La 2.0 añade:
  - 6 estrategias de reparto, 7 en total;
  - afinidad de sesión y enrutamiento por cabecera;
  - comprobación de salud pasiva y activa de los servidores de origen;
  - una caché de respuestas;
  - protección contra la sobrecarga y contra los bucles;
  - control en caliente.
- **Límite de tasa por carpeta y por dirección o red**, además del límite global.
- **Contadores de seguridad compartidos entre procesos** (ver §7).
- **Listas de rutas sensibles** listas para usar, con un modo observación y un editor integrado.
- **Importación de scripts mod_magnet de lighttpd** (ver §7).
- **Interfaz en 17 idiomas**, con un idioma aparte para las páginas que ven los visitantes y para las exportaciones.
- **Registros completamente renovados**:
  - una biblioteca de registros;
  - tres visores, entre ellos lnav;
  - la obtención de registros remotos por SSH.

---

## 5. Comparativa de funciones

Leyenda:
- ✅ integrado;
- 🧩 módulo oficial del proyecto, que hay que activar o instalar;
- 🔌 módulo o plugin de terceros;
- ⚙️ mediante una herramienta externa;
- ❌ ausente.

«Comercial» designa una función reservada a la edición de pago.

### Servicio HTTP

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Servir archivos estáticos | ✅ | ✅ | ✅ | ✅ | ❌ (solo proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Archivos precomprimidos `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 receta mod_rewrite | — | ✅ |
| Compresión al vuelo | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP mediante FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Varios procesos o núcleos | ✅ workers | ⚠️ `max-worker`, desaconsejado por la documentación | ✅ (Go, todos los núcleos) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Proxy inverso

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Reparto de carga | ✅ turno rotativo, menos conexiones, hash | ✅ fair, round-robin, hash, sticky | ✅ una docena de estrategias | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 estrategias, entre ellas la carga real |
| Salud pasiva (apartar un servidor caído) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Salud activa (sonda periódica) | Comercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Caché de respuestas | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Comercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Descubrimiento de servicios (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (núcleo del proyecto) | ❌ |

### TLS

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Certificados automáticos (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ por defecto | 🧩 mod_md | ✅ | ⚙️ Certbot, con asistente integrado y renovación programada |
| CA local | ❌ | ❌ | ✅ CA interna (emisión automática) | ❌ | ❌ | ✅ generación, firma de CSR, revocación |

### Seguridad

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Límite de tasa por cliente | ✅ `limit_req` | ⚠️ mod_evasive (solo conexiones simultáneas) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Límite compartido entre procesos | ✅ zona de memoria compartida | ❌ contado por proceso | — (un solo proceso) | según el módulo | 1 instancia; varias con Redis | ✅ memoria compartida |
| WAF (firmas SQLi/XSS, escáneres…) | 🔌 ModSecurity, Comercial (App Protect) | ❌ (scripts Lua por escribir) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ integrado |
| Lista de bloqueo con caducidad, reincidencia | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ integrado |
| Señuelos, modo guerra, incidentes, exportación de IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Auditoría de seguridad de la configuración | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Modo observación (registrar sin bloquear) | según el módulo | — | según el plugin | ✅ ModSecurity `DetectionOnly` | según el plugin | ✅ |

### Extensibilidad

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Lenguaje de script | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | módulos Go (recompilación) | 🧩 mod_lua | plugins Go o WebAssembly | 🔌 importación de scripts mod_magnet (opción `magnet`) |
| Ecosistema de módulos | muy amplio | específico | amplio | muy amplio | amplio | ninguno: todo está integrado |

---

## 6. Administración y ergonomía

| Servidor | Modo de administración principal | Interfaz | Recarga sin corte |
|---|---|---|---|
| nginx | archivos de configuración | ninguna (panel: NGINX Plus, comercial) | ✅ `nginx -s reload` |
| lighttpd | archivo de configuración | ninguna (mod_status, solo lectura) | ✅ reinicio ordenado |
| Caddy | Caddyfile o JSON | API REST de administración | ✅ mediante la API |
| Apache | archivos de configuración y `.htaccess` | ninguna (mod_status, solo lectura) | ✅ `graceful` |
| Traefik | etiquetas de contenedores, archivos o Kubernetes | panel web (solo lectura) | ✅ configuración dinámica |
| omega-serv | interfaz de terminal (TUI) y línea de comandos (CLI); el archivo JSON no hay que editarlo | **TUI completa con teclado y ratón, 17 idiomas, ayuda integrada** | ✅ para la mayoría de los ajustes; reinicio anunciado para el puerto, TLS y el número de procesos |

En la práctica, con omega-serv, la configuración, la seguridad, los registros, los servicios del sistema, las copias de seguridad y las instancias se gestionan desde una sola interfaz. Cada ajuste se explica y se comprueba antes de escribirse. Con los demás servidores, se editan archivos de texto y luego se recurre a herramientas aparte (Certbot, fail2ban, logrotate, ModSecurity, una herramienta de supervisión…).

A cambio, el enfoque de «archivo de configuración» de nginx, Apache y Caddy se automatiza muy bien (Ansible, contenedores, control de versiones). omega-serv tiene una CLI programable, pero su ecosistema de automatización sigue siendo limitado.

---

## 7. Lo que omega-serv aporta de más

Esta sección solo recoge lo que ninguno de los servidores comparados ofrece tal cual, sin módulo de terceros ni herramienta externa.

1. **Administración completa desde una interfaz de terminal.**
   - La interfaz cubre todo el servidor: el sitio, la seguridad, los registros, los servicios, las copias de seguridad y las instancias.
   - Se usa con teclado y ratón, en un servidor sin entorno gráfico, incluso a través de SSH.
   - Está disponible en 17 idiomas y explica cada ajuste.
   - Los demás servidores no tienen interfaz de administración (nginx, lighttpd, Apache), o solo una API (Caddy) o un panel de solo lectura (Traefik).
2. **Seguridad activa integrada, sin módulos que ensamblar.**
   - El WAF incluye firmas, listas de rutas editables, reincidencia, una lista de bloqueo con caducidad, reputación y un modo observación.
   - Active Defense añade señuelos, un modo guerra, seguimiento de incidentes, exportación de indicadores de compromiso y una simulación en seco.
   - En otros servidores, estas funciones exigen ensamblar ModSecurity o Coraza, conjuntos de reglas y fail2ban.
3. **Límites de seguridad exactos con varios procesos.**
   - En modo boost, el límite de tasa y la reincidencia del WAF se comparten en memoria entre los procesos. Un atacante no puede, por tanto, multiplicar su límite por el número de procesos.
   - lighttpd documenta el caso contrario: con `server.max-worker`, `mod_evasive` y `mod_status` cuentan por separado en cada proceso.
   - nginx también comparte sus contadores (zonas `limit_req`), pero no tiene WAF integrado.
4. **Importación de scripts mod_magnet de lighttpd.**
   - Un script de protección Lua ya escrito para lighttpd se importa sin reescribirlo.
   - Se suma a la protección integrada sin poder debilitarla nunca, y su compatibilidad se comprueba antes de activarlo.
5. **Gestión de varias instancias.**
   - Un registro reúne todas las instancias, y la interfaz pasa de una a otra.
   - También sabe desinstalar por completo una instancia.
6. **Una auditoría de seguridad de la configuración**: el comando `audit security` es informativo, nunca bloquea y devuelve códigos de salida aprovechables en un script.
7. **Fuentes de registros remotas.**
   - La interfaz obtiene por SSH el registro de otro servidor, bajo demanda, sin contraseña guardada.
   - Puede leerlo con lnav, fusionado con los registros locales.
8. **Un endurecimiento HTTP que no se puede desactivar**, activo desde la instalación, sea cual sea el perfil:
   - validación estricta de la cabecera Host;
   - rechazo de las ambigüedades Content-Length / Transfer-Encoding;
   - cabeceras de seguridad y CSP, incluso en las páginas de error;
   - lectura segura de X-Forwarded-For;
   - negativa a arrancar como root.

---

## 8. Lo que los demás hacen mejor

- **Rendimiento y latencia**: nginx y lighttpd sirven de 10 a 20 veces más peticiones pequeñas, con una latencia de 8 a 10 veces menor. Para un sitio de mucho tráfico, una API pública o una CDN, son los que hay que elegir.
- **Memoria**: lighttpd (1 MB) y nginx (4–5 MB) convienen a máquinas muy limitadas (embebido, Raspberry Pi de gama de entrada, contenedores pequeños).
- **Protocolos**: HTTP/2 en todos los demás, HTTP/3 en nginx, Caddy y Traefik. omega-serv solo habla HTTP/1.1.
- **HTTPS automático**: Caddy y Traefik lo integran por defecto, y nginx (`ngx_http_acme_module`) y Apache (`mod_md`) mediante un módulo oficial. omega-serv delega en Certbot, con un asistente y renovación programada.
- **Entornos de contenedores**: el descubrimiento automático de servicios de Traefik (Docker, Kubernetes) no tiene equivalente en omega-serv.
- **Ecosistema**: nginx y Apache ofrecen miles de módulos, guías e integraciones. Caddy ofrece un sistema de módulos en Go. omega-serv es un proyecto joven, mantenido por una sola persona.
- **Compresión al vuelo**: omega-serv solo sirve archivos ya comprimidos.

---

## 9. Qué servidor para qué uso

| Necesidad | Elección recomendada |
|---|---|
| Sitio de mucho tráfico, API pública, CDN, rendimiento máximo | **nginx** |
| Máquina muy limitada, embebido, archivos estáticos | **lighttpd** |
| Arranque rápido con HTTPS automático, configuración corta | **Caddy** |
| Aplicación PHP heredada, `.htaccess`, alojamiento compartido | **Apache** |
| Docker, Kubernetes, microservicios | **Traefik** |
| Sitio pequeño, servicio interno, laboratorio, VPN, administración sin editar archivos | **omega-serv** |
| Servidor expuesto en el que se quiere ver y controlar la seguridad (WAF, bloqueos, señuelos) desde una sola interfaz | **omega-serv** |
| Proxy inverso interno con reparto, salud y caché, gestionado desde una interfaz | **omega-serv** |
| Aprender el endurecimiento HTTP y la defensa activa | **omega-serv** |

Estas herramientas también se combinan. Por ejemplo:
- nginx o Traefik delante, de cara a Internet, con omega-serv detrás para un servicio interno, su seguridad y su administración;
- omega-serv como proxy inverso interno delante de varios servidores de aplicaciones.

---

## 10. Reproducir las mediciones

Las herramientas se incluyen en el repositorio, en `tools/bench/`. Hace falta tener instalados nginx, lighttpd, Caddy y oha, así como el entorno de desarrollo de omega-serv (`.venv`).

```sh
# 1. preparar una carpeta de medición (archivos de prueba, configuraciones, omega-serv 1.0 y 2.0)
tools/bench/compare/setup.sh /ruta/medicion omega-serv-1.0.0.tar.gz

# 2. las 12 configuraciones, 3 repeticiones intercaladas (unos 22 minutos)
tools/bench/compare/campaign.sh /ruta/medicion > resultados.txt

# 3. medianas
python3 tools/bench/compare/summarize.py resultados.txt

# descargas grandes (memoria y capacidad de respuesta), 2.0 y luego 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/ruta/medicion/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/ruta/medicion/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# medir cualquier otro servidor ya en marcha, sin oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-de-prueba
python3 tools/bench/bench_any.py --port 8080
```

Por defecto, el servidor se fija a los hilos 0 y 2, y el cliente a los hilos 1 y 3, lo que corresponde a la máquina de medición. Adapte este reparto a su procesador (`lscpu -e` muestra la topología) con las variables `SRV_CPUS` y `CLI_CPUS`.

Para publicar sus propios resultados, indique la máquina, las versiones, el reparto de los procesadores y las tres repeticiones.

---

## 11. Fuentes

Funciones de los demás servidores, según su documentación oficial (consultada el 26 de octubre de 2026).

**nginx**
- [Límite de tasa `limit_req` (zona de memoria compartida)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Archivos precomprimidos `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Módulo ACME oficial `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Reparto de carga (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Conector ModSecurity para nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: desaconsejado, contadores por proceso para mod_status y mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (scripts Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (compresión, caché)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (reparto, salud pasiva, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (conexiones simultáneas por dirección)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [HTTPS automático](https://caddyserver.com/docs/automatic-https)
- [`file_server` y `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (estrategias, salud activa y pasiva)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API de administración](https://caddyserver.com/docs/api)
- [Plugin de límite de tasa caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza para Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, contenido precomprimido](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (en memoria por instancia, Redis opcional)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Herramienta de medición**
- [oha](https://github.com/hatoo/oha)

---

*Comparativa realizada por kraynux para omega-serv 2.0.0: mediciones del 26 de octubre de 2026. Las mediciones corresponden a una sola máquina. Para cualquier decisión de capacidad, mida en su propio hardware con las herramientas proporcionadas.*

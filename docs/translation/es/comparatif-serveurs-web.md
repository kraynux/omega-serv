<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv frente a los servidores web del mercado

**Comparativa medida: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5 y 3.0.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · **Español** · [Português (Brasil)](../pt-BR/comparatif-serveurs-web.md) · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Este documento sitúa omega-serv entre los servidores web más extendidos. No pretende designar un «mejor servidor»: cada herramienta responde a necesidades distintas, y cada una tiene sus puntos fuertes. Aporta tres cosas:

1. **medidas reales**, hechas en **tres máquinas** muy distintas, con el mismo cliente, los mismos archivos y el mismo protocolo, y reproducibles;
2. una **comparativa de funciones**, cada una verificada en la documentación oficial de cada servidor (enlaces al final del documento), distinguiendo lo integrado de lo que requiere un módulo o un plugin;
3. lo que omega-serv **aporta realmente de más**, y lo que los demás hacen **mejor que él**.

Las medidas como servidor de archivos se hicieron el 3 y el 4 de noviembre de 2026 (omega-serv 2.5), las del proxy inverso el 14 de noviembre de 2026 (omega-serv 3.0.0, en preparación). La memoria de omega-serv 3.0.0, muy reducida desde entonces, se volvió a medir el 19 de noviembre de 2026 en las tres máquinas, con el mismo protocolo (§4, §5 y §6). Ninguna cifra se ha tomado de otro sitio ni se ha estimado. Las cifras en bruto se publican con este documento.

---

## Índice

1. [En resumen](#1-en-resumen)
2. [Cómo leer esta comparativa](#2-cómo-leer-esta-comparativa)
3. [Método de medida](#3-método-de-medida)
4. [Rendimiento: omega-serv frente a nginx, lighttpd, Apache y Caddy](#4-rendimiento-omega-serv-frente-a-nginx-lighttpd-apache-y-caddy)
5. [Rendimiento como proxy inverso: omega-serv frente a nginx, lighttpd, Apache, Caddy y Traefik](#5-rendimiento-como-proxy-inverso-omega-serv-frente-a-nginx-lighttpd-apache-caddy-y-traefik)
6. [Las versiones de omega-serv: 1.0 → 2.0 → 2.5 → 3.0.0](#6-las-versiones-de-omega-serv-10--20--25--300)
7. [Comparativa de funciones](#7-comparativa-de-funciones)
8. [Administración y ergonomía](#8-administración-y-ergonomía)
9. [Lo que omega-serv aporta de más](#9-lo-que-omega-serv-aporta-de-más)
10. [Lo que los demás hacen mejor](#10-lo-que-los-demás-hacen-mejor)
11. [Qué servidor para qué uso](#11-qué-servidor-para-qué-uso)
12. [Reproducir las medidas](#12-reproducir-las-medidas)
13. [Fuentes](#13-fuentes)

---

## 1. En resumen

- **omega-serv tiene dos motores.** El **motor Python** lo procesa todo él mismo. El **motor nativo**, escrito en C++ y aparecido con la 2.5, sirve él mismo las peticiones; Python conserva la configuración y las decisiones de seguridad, y el nativo reconoce solo las peticiones a las que no corresponde ninguna regla del WAF.
- **Con el motor nativo, sin WAF**, omega-serv sirve los archivos pequeños a **unas 0,7 veces la velocidad de nginx**, en las tres máquinas. Se sitúa así **por delante de Apache y Caddy, por detrás de nginx y lighttpd**.
- **Con el motor Python**, omega-serv queda muy por detrás de todos los demás: **del 3 al 11 % de la velocidad de nginx**.
- **Con el WAF activo**, omega-serv inspecciona cada petición, algo que los demás servidores medidos no hacen. Con el motor nativo, sirve entonces **de 0,53 a 0,56 veces** la velocidad de nginx (sin WAF) en las máquinas A y B, y 1,07 veces en la máquina C (4 núcleos frente a 2): el WAF solo le resta de un 5 a un 22 % de su rendimiento. Sigue por delante de Apache y Caddy medidos sin WAF.
- **Archivos medianos (100 KB)**: es el punto débil actual del motor nativo, con **de 0,3 a 0,6 veces** nginx, por detrás de Apache.
- **Archivos grandes (5 MB)**: nginx, lighttpd, Apache y omega-serv nativo alcanzan el mismo orden de rendimiento. Caddy es claramente más lento en la máquina más rápida.
- **Como proxy inverso (3.0.0)**, el motor nativo reenvía las respuestas pequeñas a **entre 0,82 y 0,91 veces la velocidad de nginx**, y las respuestas de 100 KB **igual de rápido que él o más** (de 0,97 a 1,43). Es **segundo por detrás de nginx**, por delante de lighttpd, Apache, Traefik y Caddy. En HTTPS, sigue segundo en las respuestas pequeñas de las máquinas A y B; lighttpd lo iguala en la máquina C.
- **Memoria**: lighttpd (1 MB), nginx (de 4 a 5 MB) y Apache (de 4 a 9 MB) son muy austeros. omega-serv 3.0.0 ocupa **de 10 a 16 MB** con el motor nativo, **de 20 a 33 MB** con el motor Python o el WAF, y de 35 a 55 MB con 2 procesos; Caddy **de 50 a 67 MB**. La 2.5 ocupaba de 28 a 57 MB.
- **Lo que omega-serv tiene de más**: una administración completa en interfaz de terminal, en 17 idiomas; un WAF y una defensa activa integrados; límites de seguridad exactos con varios procesos; la importación de scripts mod_magnet de lighttpd; la gestión de varias instancias.
- **Lo que no tiene**: HTTP/2 y HTTP/3, la compresión al vuelo, el descubrimiento de servicios Docker/Kubernetes, un cliente ACME integrado (pasa por Certbot), un ecosistema de módulos.

---

## 2. Cómo leer esta comparativa

Algunas nociones vuelven a lo largo del documento.

- **Peticiones por segundo (req/s)**: el número de archivos que un servidor envía en un segundo. Cuanto más alto, mejor.
- **Diferencia con nginx**: los valores absolutos dependen enormemente de la máquina. En nuestras tres máquinas, nginx va de 22 000 a 440 000 req/s. Lo que se mantiene estable es **la relación entre servidores**. Las tablas dan por tanto, junto a cada valor, su relación con nginx medido en la misma sesión: **1,00 = tan rápido como nginx**, 0,50 = la mitad, 1,50 = la mitad más.
- **Latencia p99**: el tiempo de respuesta que no supera el 99 % de las peticiones. Muestra los «malos momentos» que una media oculta.
- **PSS (*Proportional Set Size*)**: la memoria realmente ocupada por todos los procesos del servidor. Una página compartida entre varios procesos solo se cuenta una vez.
- **Procesos y núcleos**: un servidor puede usar varios núcleos del procesador. Cada uno lo hace a su manera. nginx, lighttpd, Apache y omega-serv en modo Python lanzan varios procesos. Caddy, en Go, reparte su trabajo entre los núcleos. El motor nativo de omega-serv lanza un hilo por núcleo disponible. Para comparar en igualdad de condiciones, damos a cada servidor **los mismos núcleos**.
- **WAF (*Web Application Firewall*)**: un filtro que inspecciona cada petición para bloquear los ataques (inyecciones, escáneres…). omega-serv lo integra. Los demás servidores pueden recibir uno como módulo (ModSecurity, Coraza), pero **se midieron sin él**, en su configuración básica.

**El buen reflejo**: comparar las relaciones, no los valores absolutos, y comprobar siempre si el WAF está activo.

---

## 3. Método de medida

### Las tres máquinas

| | Máquina A | Máquina B | Máquina C |
|---|---|---|---|
| Procesador | Intel Core i5 M480, 2,67 GHz (2010) | Intel Celeron J3455, 1,5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Núcleos | 2 núcleos físicos, 4 hilos | 4 núcleos, sin hyperthreading | 10 núcleos (4 Zen 5 + 6 Zen 5c), 20 hilos |
| Memoria | 8 GB | 8 GB | 32 GB |
| Sistema | Mabox Linux (base Manjaro), núcleo 6.18 | EndeavourOS, núcleo 7.2 | Arch Linux, núcleo 7.2 (CachyOS) |
| Núcleos del servidor | 1 núcleo físico (hilos 0 y 2) | 2 núcleos (0 y 1) | 4 núcleos Zen 5, un hilo cada uno (0 a 3) |
| Núcleos del cliente | 1 núcleo físico (hilos 1 y 3) | 2 núcleos (2 y 3) | 6 núcleos Zen 5c (4 a 9) |

La máquina A es un portátil antiguo, la máquina B un mini PC de bajo consumo, la máquina C un portátil reciente, conectado a la red, en perfil de energía «equilibrado». Cubren un abanico que va de un pequeño servidor doméstico a una máquina actual.

### Software

| Software | Versión |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 y 2.0.0 (archivos publicados), 2.5 y 3.0.0, con Python 3.14 |
| Cliente de carga | [oha](https://github.com/hatoo/oha) 1.16.0 (escrito en Rust) |

Traefik no se midió como servidor de archivos: no lo es (véase §7). Se mide como proxy inverso, su función, en el §5.

### Protocolo

- **Aislamiento del procesador**: el servidor y el cliente están fijados en núcleos separados (tabla anterior). El cliente no le roba tiempo al servidor, y todos los servidores disponen exactamente de los mismos recursos.
- **Mismos archivos para todos**: `small.html` (1 KB), `medium.png` (100 KB) y `large.bin` (5 MB), servidos desde la misma carpeta.
- **Registro de acceso activo en todas partes**, porque un servidor en producción registra.
- **HTTP/1.1 en claro, conexiones persistentes (keep-alive)**. La concurrencia es de 32 conexiones para los archivos de 1 KB y 100 KB, y de 8 para el archivo de 5 MB.
- **Duración**: 10 segundos por archivo y por configuración.
- **Repeticiones**: 3 rondas completas, entrelazadas (todas las configuraciones en la ronda 1, luego todas en la ronda 2, etc.). Las tablas dan la **mediana** de las tres rondas. De una ronda a otra, la diferencia suele quedar por debajo del 5 %.
- **Memoria**: PSS de todos los procesos del servidor, tomada en reposo y después de la carga. La de omega-serv 3.0.0 se volvió a medir el 19 de noviembre de 2026 con nginx como referencia en la misma sesión: se queda a menos del 3 % de su rendimiento del 4 de noviembre en archivos pequeños, y a menos de 1 MB de su memoria.
- **Configuraciones**:
  - nginx, lighttpd, Apache y Caddy en su configuración básica: archivos estáticos y registro de acceso;
  - omega-serv con el perfil `standard`, el WAF desactivado y luego activado con todas sus reglas suministradas (sin límite de tasa).
- **Número de procesos**: cada servidor se mide con 1 y luego 2 procesos: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Para el motor nativo de omega-serv, `server.workers` cuenta los procesos Python de seguridad; el motor nativo, por su parte, usa siempre todos los núcleos que se le dan.
- **Ningún error**: todas las respuestas de todas las medidas son 200.

### Límites que hay que conocer

- **Lo que comparamos son las relaciones.** Los valores absolutos serían distintos en su hardware, o en un servidor dedicado.
- **Bucle local (127.0.0.1)**: la medida no pasa por una red real. En una red real, el rendimiento de los archivos grandes casi siempre está limitado por el ancho de banda, no por el servidor. Los rendimientos de varias decenas de GB/s de la máquina C solo son posibles en bucle local.
- **Sin TLS** en las medidas como servidor de archivos (§4 y §6). El proxy inverso (§5) se mide en HTTP y en HTTPS.
- **Máquina A**: el servicio omega-serv de producción de esta máquina funcionaba en segundo plano, sin recibir tráfico.
- **Máquina C**: procesador híbrido (núcleos Zen 5 y Zen 5c). El servidor recibió los 4 núcleos rápidos, el cliente los otros 6.
- **Configuraciones básicas**: ningún servidor se optimizó. Un administrador experimentado sacaría sin duda más de cada uno, omega-serv incluido.
- **Cifras en bruto**: [`docs/benchmarks/`](../../benchmarks/) (un archivo por máquina y por campaña; nueva medida de la 3.0.0: `2026-11-19-*-memoire-3.0.0-brut.txt`).

---

## 4. Rendimiento: omega-serv frente a nginx, lighttpd, Apache y Caddy

En todas las tablas, el valor de referencia es **nginx con 2 procesos** (= 1,00), medido en la misma sesión en la misma máquina. En las máquinas A y B, es la configuración que ocupa todos los núcleos dados al servidor.

### Archivos pequeños (1 KB): peticiones por segundo

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd, 2 procesos | 33 138 (**1,52**) | 31 125 (**1,26**) | 378 590 (**1,53**) |
| nginx, 2 procesos | 21 801 (1,00) | 24 705 (1,00) | 248 184 (1,00) |
| **omega-serv, motor nativo** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15 \*)** |
| omega-serv, nativo + WAF † | 11 990 (0,56) | 12 998 (0,53) | 264 484 (1,07 \*) |
| omega-serv, nativo + WAF, 2 procesos de seguridad † | 11 746 (0,55) | 12 718 (0,52) | 253 527 (1,02 \*) |
| Apache, 2 procesos | 9 192 (0,42) | 8 634 (0,35) | 188 335 (0,76) |
| Caddy, 2 procesos | 5 749 (0,26) | 4 116 (0,17) | 52 897 (0,21) |
| omega-serv, motor Python, 2 procesos | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| omega-serv, Python + WAF, 2 procesos | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| omega-serv, motor Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| omega-serv, Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |

\* En la máquina C, el motor nativo usa sus 4 núcleos, mientras que nginx solo usa 2 con 2 procesos. La comparación con igual número de núcleos se da más abajo: la relación vuelve allí a **0,67 a 0,71**, como en las demás máquinas.

† Medido el 4 de noviembre, tras la optimización del WAF, en una campaña separada con el mismo protocolo. La relación se calcula con nginx (2 procesos) de esa campaña: 21 439, 24 424 y 248 127 req/s en archivos pequeños, 11 545, 11 004 y 157 491 en archivos de 100 KB. Antes de esta optimización, el motor nativo con WAF servía 3 495, 2 622 y 39 000 req/s (de 0,11 a 0,16 veces nginx), porque cada petición pasaba por Python. Cifras en bruto: archivos `*-waf-natif-brut.txt`.

Con un solo proceso, nginx hace de 0,52 a 0,73, lighttpd de 0,81 a 1,43, Apache de 0,33 a 0,74 y Caddy de 0,09 a 0,17 (cifras en bruto).

### Latencia p99 en archivos pequeños

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd, 2 procesos | 4,4 ms | 4,1 ms | 0,2 ms |
| nginx, 2 procesos | 4,9 ms | 5,2 ms | 0,2 ms |
| **omega-serv, motor nativo** | **6,1 ms** | **6,2 ms** | **0,3 ms** |
| omega-serv, nativo + WAF † | 7,2 ms | 6,7 ms | 0,3 ms |
| Apache, 2 procesos | 18,8 ms | 20,6 ms | 0,8 ms |
| Caddy, 2 procesos | 24,1 ms | 30,5 ms | 2,8 ms |
| omega-serv, motor Python, 2 procesos | 22,6 ms | 28,1 ms | 3,3 ms |
| omega-serv, motor Python | 32,0 ms | 51,6 ms | 4,4 ms |

### Archivos medianos (100 KB): peticiones por segundo

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd, 2 procesos | 13 561 (**1,08**) | 12 126 (**1,07**) | 197 905 (**1,26**) |
| nginx, 2 procesos | 12 513 (1,00) | 11 303 (1,00) | 157 224 (1,00) |
| Apache, 2 procesos | 6 939 (0,55) | 7 035 (0,62) | 153 265 (0,97) |
| Caddy, 2 procesos | 5 059 (0,40) | 3 744 (0,33) | 22 094 (0,14) |
| **omega-serv, motor nativo** | **4 738 (0,38)** | **3 115 (0,28)** | **96 277 (0,61)** |
| omega-serv, nativo + WAF † | 4 229 (0,37) | 2 926 (0,27) | 98 185 (0,62) |
| omega-serv, motor Python, 2 procesos | 1 741 (0,14) | 1 154 (0,10) | 18 806 (0,12) |
| omega-serv, motor Python | 1 329 (0,11) | 611 (0,05) | 9 805 (0,06) |

### Archivo grande (5 MB): rendimiento

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd, 2 procesos | 2 440 MB/s (1,05) | 2 110 MB/s (0,99) | 28 011 MB/s (0,81) |
| nginx, 2 procesos | 2 322 MB/s (1,00) | 2 124 MB/s (1,00) | 34 651 MB/s (1,00) |
| Apache, 2 procesos | 2 355 MB/s (1,01) | 2 134 MB/s (1,00) | 41 153 MB/s (**1,19**) |
| **omega-serv, motor nativo** | **2 294 MB/s (0,99)** | **1 936 MB/s (0,91)** | **37 918 MB/s (1,09)** |
| Caddy, 2 procesos | 2 205 MB/s (0,95) | 1 996 MB/s (0,94) | 3 811 MB/s (0,11) |
| omega-serv, motor Python, 2 procesos | 2 145 MB/s (0,92) | 1 931 MB/s (0,91) | 25 829 MB/s (0,75) |
| omega-serv, motor Python | 1 686 MB/s (0,73) | 1 472 MB/s (0,69) | 14 227 MB/s (0,41) |

### Memoria (PSS, todos los procesos del servidor): en reposo → tras la carga

omega-serv: versión 3.0.0, medida de nuevo el 19 de noviembre de 2026 (los valores de la 2.5 están en el §6). Otros servidores: campaña del 4 de noviembre.

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| **omega-serv, motor nativo** | **10 → 10 MB** | **10 → 12 MB** | **12 → 16 MB** |
| omega-serv, motor Python | 20 → 23 MB | 21 → 24 MB | 22 → 28 MB |
| omega-serv, nativo + WAF | 28 → 30 MB | 29 → 32 MB | 30 → 33 MB |
| omega-serv, motor Python, 2 procesos | 35 → 46 MB | 36 → 46 MB | 38 → 48 MB |
| omega-serv, nativo + WAF, 2 procesos de seguridad ‡ | 28 → 28 MB | 29 → 31 MB | 51 → 55 MB |
| Caddy, 2 procesos | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

‡ En las máquinas A y B, el servidor solo dispone de 2 núcleos: omega-serv solo lanza allí un proceso de seguridad (lanza 2 a partir de 4 núcleos). En la máquina C, con 2 procesos de seguridad, el supervisor Python conserva su forma completa, necesaria para los contadores que comparten: 51 MB en lugar de 30.

### Con igual número de núcleos: máquina C con 4 procesos

Campaña separada del 3 de noviembre, mismo protocolo, en la máquina C: cada servidor recibe 4 procesos (o 4 núcleos para Caddy y el motor nativo). Referencia: nginx con 4 procesos. El motor nativo con WAF ya no figura aquí: medido antes de la optimización del WAF, todavía no se ha vuelto a medir con 4 procesos. Memoria de omega-serv: 3.0.0, medida de nuevo el 19 de noviembre (rendimientos: 2.5, 3 de noviembre).

| Servidor | 1 KB | 100 KB | 5 MB | Memoria |
|---|---:|---:|---:|---:|
| lighttpd, 4 procesos | 638 907 (**1,46**) | 312 402 (**1,21**) | 41 982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 procesos | 438 496 (1,00) | 258 242 (1,00) | 45 162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, motor nativo** | **294 083 a 310 972 (0,67 a 0,71)** | **108 991 a 109 955 (0,42)** | **40 137 a 40 463 MB/s (0,89 a 0,90)** | **12 → 16 a 18 MB** |
| Apache, 4 procesos | 200 592 (0,46) | 162 607 (0,63) | 39 664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 núcleos | 97 085 (0,22) | 35 900 (0,14) | 5 998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, motor Python, 4 procesos | 37 697 (0,09) | 35 064 (0,14) | 37 123 MB/s (0,82) | 45 → 60 MB |

### Lectura

- **El motor nativo cambia el lugar de omega-serv.**
  - En archivos pequeños, pasa de 0,03-0,11 veces nginx (motor Python) a unas **0,7 veces nginx**, sea cual sea la máquina.
  - Se sitúa por delante de Apache y Caddy, y por detrás de nginx y lighttpd, que siguen siendo los más rápidos.
  - Su latencia p99 es cercana a la de nginx.
- **lighttpd es el más rápido en archivos pequeños y medianos**, en las tres máquinas, y el más austero en memoria. Su documentación desaconseja sin embargo `server.max-worker` (varios procesos), que usamos para comparar con igual número de procesos.
- **Los archivos medianos son el punto débil actual del motor nativo**: de 0,28 a 0,61 veces nginx, por detrás de Apache, y no mejor con más núcleos. Es una vía de mejora identificada.
- **En los archivos grandes**, los servidores se igualan, porque es el núcleo el que copia los datos (`sendfile`). Caddy es la excepción en la máquina C: no intentamos optimizar su configuración básica.
- **El WAF le cuesta poco al motor nativo, y hay que leerlo con justicia.**
  - El motor nativo busca él mismo las reglas del WAF: una petición a la que no corresponde ninguna se sirve sin pasar por Python. Ante la menor duda (coincidencia, texto no ASCII, origen vigilado por Active Defense, zona de autenticación…), decide Python. Con el WAF, el motor nativo conserva así del 78 al 95 % de su rendimiento en archivos pequeños, y del 93 al 99 % en archivos de 100 KB. Antes de esta optimización, su rendimiento se dividía entre 4 y 7.
  - La limitación de tasa la cuenta el motor nativo: activarla no cambia estas cifras (máquina A: 11 391 req/s con ella, 11 330 sin ella). Si magnet está activo, todas las peticiones siguen pasando por Python, y el coste vuelve a ser el de antes.
  - omega-serv con WAF sigue por delante de Apache y Caddy **sin** WAF.
  - nginx, lighttpd, Apache y Caddy se midieron **sin** WAF. Un WAF añadido a estos servidores (ModSecurity, Coraza) también tiene un coste, que no hemos medido. La comparación «con WAF» no se hace pues en igualdad de condiciones, y no pretendemos que omega-serv sería más rápido que otro servidor equipado con un WAF.
- **Varios procesos de seguridad ya no ayudan al tráfico normal**: ya no pasa por ellos, y el rendimiento sigue igual con 2 procesos (−2 a −4 %, dentro del ruido de medida). Solo sirven cuando muchas peticiones pasan por Python (magnet activo, ataque): medido antes de la optimización, cuando todas las peticiones pasaban por ahí, 2 procesos de seguridad multiplicaban el rendimiento con WAF por 1,5 a 1,7 en 4 núcleos, pero solo aportaban de un 5 a un 12 % en 2 núcleos.
- **El motor Python progresa con los procesos** (×1,6 a ×2 con 2 procesos, unas ×3,5 con 4), pero se queda en un 5-11 % de nginx.
- **Memoria**: con el motor nativo sin WAF, omega-serv 3.0.0 ocupa de 10 a 16 MB, de dos a cuatro veces nginx o Apache y de tres a seis veces menos que Caddy. Con el WAF o el motor Python, hay que contar de 20 a 33 MB, sobre todo a causa de Python: un proceso Python con asyncio cuesta al menos 10 MB. Con un proceso, es de un 30 a un 70 % menos que en la 2.5 (§6).
- **Para situar estas cifras**: incluso el caso más lento, el motor Python con WAF en la máquina B (564 req/s), representa casi 50 millones de peticiones al día. Es muy superior a las necesidades de un sitio personal, un servicio interno o un laboratorio. La velocidad solo es realmente decisiva para un sitio con mucho tráfico.

---

## 5. Rendimiento como proxy inverso: omega-serv frente a nginx, lighttpd, Apache, Caddy y Traefik

Aquí, los servidores no sirven archivos: cada uno **reenvía** las peticiones a un servidor de aplicaciones (el *backend*) y devuelve su respuesta. Medidas del 14 de noviembre de 2026, con omega-serv 3.0.0 (en preparación), cuyo motor nativo reenvía él mismo el proxy inverso.

### Protocolo propio de estas medidas

- **Mismo backend para todos**: un nginx estático con 2 procesos, que sirve `small.html` (1 KB) y `medium.png` (100 KB). Cada medida comprueba que la respuesta viene realmente del backend (cabecera añadida por él): el proxy reenvía, nunca sirve el archivo él mismo.
- **Núcleos**: máquina A, el proxy en un núcleo físico (hilos 0 y 2), el cliente y el backend en el otro (1 y 3); máquina B, el proxy en los núcleos 0 y 1, el cliente y el backend en 2 y 3; máquina C, el proxy en los 4 núcleos Zen 5 (0 a 3), el backend en 2 núcleos Zen 5c (4 y 5), el cliente en los otros 4 (6 a 9).
- **Procesos**: 2 en las máquinas A y B, **4 en la máquina C**, para que cada servidor use todos los núcleos dados al proxy. El motor nativo de omega-serv usa siempre todos esos núcleos, con un proceso Python de seguridad.
- **HTTP y HTTPS** del lado del cliente (certificado ECDSA P-256 autofirmado); al backend se llega siempre en HTTP.
- **Configuraciones**:
  - nginx: `proxy_pass` hacia un grupo `upstream` que conserva sus conexiones con el backend (`keepalive 64`); sin este ajuste, ausente de su configuración básica, nginx abre una conexión por petición;
  - lighttpd: `mod_proxy`, configuración básica;
  - Apache: `mod_proxy` y `mod_proxy_http`, MPM `event`, una línea `ProxyPass`;
  - Caddy: `reverse_proxy`, configuración básica;
  - Traefik 3.7: un router y un servicio, configuración básica;
  - omega-serv: una zona de proxy inverso en `/`, perfil `standard`, motor nativo sin y luego con el WAF (todas sus reglas suministradas, sin límite de tasa), y motor Python con 2 procesos.
- **El resto no cambia** (§3): registro de acceso activo en todas partes, oha, 32 conexiones persistentes, 10 segundos, 3 rondas entrelazadas, mediana. **Ningún error**: todas las respuestas son 200.

Entre paréntesis: la relación con nginx con el mismo número de procesos, medido en la misma sesión (= 1,00).

### Respuestas pequeñas (1 KB): peticiones por segundo

| Servidor | Máquina A (2 procesos) | Máquina B (2 procesos) | Máquina C (4 procesos) |
|---|---:|---:|---:|
| nginx | 11 151 (1,00) | 11 049 (1,00) | 246 595 (1,00) |
| **omega-serv, motor nativo** | **9 507 (0,85)** | **10 098 (0,91)** | **203 021 (0,82)** |
| omega-serv, nativo + WAF | 9 078 (0,81) | 9 857 (0,89) | 190 201 (0,77) |
| lighttpd | 6 752 (0,61) | 6 242 (0,56) | 129 827 (0,53) |
| Apache | 6 616 (0,59) | 5 872 (0,53) | 124 458 (0,50) |
| Traefik | 3 940 (0,35) | 3 890 (0,35) | 70 465 (0,29) |
| Caddy | 3 578 (0,32) | 3 117 (0,28) | 55 910 (0,23) |
| omega-serv, motor Python | 1 039 (0,09) | 859 (0,08) | — \* |

\* El motor Python solo se midió con 2 procesos en la máquina C: 11 530 req/s, es decir 0,07 veces nginx con 2 procesos (171 075 req/s).

### Respuestas medianas (100 KB): peticiones por segundo

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| **omega-serv, motor nativo** | **4 281 (1,11)** | **3 497 (0,97)** | **80 361 (1,43)** |
| omega-serv, nativo + WAF | 4 236 (1,10) | 3 335 (0,93) | 73 025 (1,30) |
| nginx | 3 855 (1,00) | 3 605 (1,00) | 56 011 (1,00) |
| lighttpd | 2 834 (0,74) | 2 252 (0,62) | 53 523 (0,96) |
| Apache | 2 404 (0,62) | 2 357 (0,65) | 39 807 (0,71) |
| Traefik | 2 477 (0,64) | 2 181 (0,60) | 39 419 (0,70) |
| Caddy | 2 294 (0,60) | 1 956 (0,54) | 33 120 (0,59) |
| omega-serv, motor Python | 821 (0,21) | 669 (0,19) | — |

### HTTPS: peticiones por segundo

| Servidor | 1 KB: A | 1 KB: B | 1 KB: C | 100 KB: A | 100 KB: B | 100 KB: C |
|---|---:|---:|---:|---:|---:|---:|
| nginx | 9 203 (1,00) | 9 305 (1,00) | 202 095 (1,00) | 780 (1,00) | 2 338 (1,00) | 47 609 (1,00) |
| **omega-serv, motor nativo** | **6 840 (0,74)** | **7 976 (0,86)** | **130 337 (0,64) †** | **690 (0,88)** | **1 917 (0,82)** | **42 507 (0,89)** |
| omega-serv, nativo + WAF | 6 372 (0,69) | 7 456 (0,80) | 146 590 (0,73) † | 683 (0,88) | 1 882 (0,80) | 39 400 (0,83) |
| lighttpd | 5 188 (0,56) | 5 513 (0,59) | 130 572 (0,65) | 638 (0,82) | 1 381 (0,59) | 45 566 (0,96) |
| Apache | 5 038 (0,55) | 4 193 (0,45) | 114 898 (0,57) | 588 (0,75) | 1 368 (0,59) | 29 948 (0,63) |
| Traefik | 3 389 (0,37) | 3 195 (0,34) | 62 251 (0,31) | 889 (**1,14**) | 1 548 (0,66) | 28 513 (0,60) |
| Caddy | 3 263 (0,35) | 2 733 (0,29) | 54 279 (0,27) | 1 135 (**1,46**) | 1 424 (0,61) | 26 452 (0,56) |
| omega-serv, motor Python | 922 (0,10) | 759 (0,08) | — | 423 (0,54) | 549 (0,23) | — |

† En la máquina C, en HTTPS, el motor nativo varía mucho de una ronda a otra: de 130 000 a 185 000 req/s sin WAF, de 138 000 a 150 000 con él. La diferencia entre las dos líneas queda pues dentro del ruido de esta medida.

### Latencia p99 en respuestas pequeñas (HTTP)

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| nginx | 7,7 ms | 7,8 ms | 0,4 ms |
| **omega-serv, motor nativo** | **10,5 ms** | **9,7 ms** | **0,6 ms** |
| omega-serv, nativo + WAF | 9,6 ms | 11,0 ms | 0,8 ms |
| lighttpd | 11,9 ms | 14,0 ms | 0,9 ms |
| Apache | 14,7 ms | 21,3 ms | 2,0 ms |
| Traefik | 25,9 ms | 26,5 ms | 2,1 ms |
| Caddy | 23,9 ms | 27,2 ms | 2,5 ms |
| omega-serv, motor Python | 41,0 ms | 47,6 ms | — |

### Memoria del proxy (PSS): en reposo → tras la carga, en HTTP

omega-serv: versión 3.0.0, medida de nuevo el 19 de noviembre de 2026; los rendimientos anteriores son del 14 de noviembre.

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd | 3 → 4 MB | 3 → 4 MB | 3 → 4 MB |
| nginx | 7 → 8 MB | 7 → 8 MB | 10 → 11 MB |
| Apache | 6 → 12 MB | 6 → 12 MB | 8 → 15 MB |
| **omega-serv, motor nativo** | **27 → 28 MB** | **27 → 28 MB** | **29 → 33 MB** |
| omega-serv, nativo + WAF | 29 → 30 MB | 29 → 31 MB | 31 → 36 MB |
| Caddy | 48 → 57 MB | 48 → 59 MB | 50 → 60 MB |
| omega-serv, motor Python | 42 → 50 MB | 43 → 51 MB | — |
| Traefik | 93 → 117 MB | 107 → 131 MB | 100 → 123 MB |

En HTTPS, la memoria tras la carga aumenta de 0 a 5 MB en la mayoría de los servidores, más en Apache (hasta 66 MB en la máquina C) y en el motor Python (hasta 72 MB): véanse las cifras en bruto.

### Lectura

- **Como proxy inverso, omega-serv con el motor nativo es segundo por detrás de nginx**, en las tres máquinas.
  - En respuestas pequeñas, reenvía de 0,82 a 0,91 veces lo que nginx. Es de 1,4 a 1,7 veces lighttpd y Apache, y de 2,4 a 3,6 veces Traefik y Caddy.
  - Su latencia p99 es la más baja después de la de nginx.
- **En respuestas de 100 KB, iguala o supera a nginx** (de 0,97 a 1,43). El motor nativo reenvía la respuesta sobre la marcha, con un búfer acotado. En su configuración básica, nginx solo guarda en memoria unas decenas de KB por respuesta reenviada (`proxy_buffers`) y puede escribir el resto en un archivo temporal. No hemos ajustado este punto.
- **En HTTPS**, el motor nativo sigue segundo en las respuestas pequeñas de las máquinas A y B. En la máquina C, lighttpd y él están al mismo nivel.
  - En las respuestas de 100 KB, lighttpd lo adelanta en la máquina C.
  - En la máquina A, Caddy y Traefik adelantan a todos, nginx incluido. Están escritos en Go, con su propia biblioteca TLS, al parecer más eficiente en este procesador de 2010. No lo hemos estudiado más a fondo.
- **El WAF cuesta poco como proxy inverso**: del 1 al 9 % del rendimiento en HTTP, con todas las reglas activas. Los demás servidores se midieron sin WAF: la comparación «con WAF» no se hace en igualdad de condiciones (véase §4).
- **Memoria**: con el motor nativo, omega-serv 3.0.0 ocupa unos 30 MB (de 27 a 36 MB). Este total incluye el supervisor Python, el proceso de seguridad y el motor nativo. Es varias veces nginx, lighttpd o Apache, pero menos que Caddy y de tres a cuatro veces menos que Traefik. En la medida del 14 de noviembre (3.0.0 en preparación), ocupaba unos 50 MB.
- **El motor Python** reenvía de 0,08 a 0,10 veces lo que nginx en respuestas pequeñas: sigue siendo el motor de reserva. Las zonas de proxy inverso con caché se le siguen confiando, y conservan por tanto su rendimiento.
- **Una corrección hecha antes de estas medidas.** Una primera pasada, el mismo día y con el mismo protocolo, situaba el motor nativo en 0,32 a 0,69 veces nginx en respuestas pequeñas. Se estancaba en torno a 78 000 req/s en la máquina C, fuera cual fuera el número de núcleos. Su reserva de conexiones con el backend era demasiado pequeña: abría una nueva cada cinco peticiones. Esta reserva se amplió y el reenvío se aligeró antes de la pasada publicada aquí. Las cifras de la primera pasada también se publican.

### Límites propios de estas medidas

- **nginx está ajustado a su favor**: conserva sus conexiones con el backend, algo que no hace en su configuración básica. Los demás servidores están en su configuración básica.
- **El backend funciona en la misma máquina**, en bucle local. En las máquinas A y B, comparte sus núcleos con el cliente. Solo cuentan pues las relaciones entre servidores, medidas en las mismas condiciones. Por sí solo, este backend sirve unas 345 000 req/s en la máquina C: allí no limita a ninguno de los proxys.
- **Solo HTTP/1.1**, tanto hacia el cliente como hacia el backend: omega-serv no habla HTTP/2.
- **Cifras en bruto**: [`docs/benchmarks/`](../../benchmarks/), archivos `2026-11-14-*-reverse-proxy-brut.txt`, incluida la primera pasada (`2026-11-14-reverse-proxy-avant-correctif-brut.txt`).

---

## 6. Las versiones de omega-serv: 1.0 → 2.0 → 2.5 → 3.0.0

Las tres versiones se midieron en la misma sesión que el §4, en las tres máquinas, con el mismo protocolo. Entre paréntesis: la relación con nginx (2 procesos) de la misma sesión. †: campaña del 4 de noviembre tras la optimización del WAF (véase §4). La 3.0.0 se midió el 19 de noviembre, con el mismo protocolo; sus relaciones se calculan con nginx (2 procesos) medido de nuevo en esa sesión, que se queda a menos del 3 % de su valor del 4 de noviembre.

### Archivos pequeños (1 KB): peticiones por segundo

| Versión y modo | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| 1.0.0 | 1 547 (0,07) | 645 (0,03) | 8 870 (0,04) |
| 1.0.0 + WAF | 1 453 (0,07) | 561 (0,02) | 7 687 (0,03) |
| 2.0.0 | 1 740 (0,08) | 650 (0,03) | 10 245 (0,04) |
| 2.0.0 + WAF | 1 456 (0,07) | 565 (0,02) | 8 371 (0,03) |
| 2.0.0, 2 procesos | 2 153 (0,10) | 1 277 (0,05) | 19 192 (0,08) |
| 2.0.0 + WAF, 2 procesos | 1 775 (0,08) | 1 113 (0,05) | 15 351 (0,06) |
| 2.5, motor Python | 1 507 (0,07) | 663 (0,03) | 10 553 (0,04) |
| 2.5, motor Python + WAF | 1 561 (0,07) | 564 (0,02) | 8 365 (0,03) |
| 2.5, motor Python, 2 procesos | 2 354 (0,11) | 1 312 (0,05) | 19 911 (0,08) |
| 2.5, motor Python + WAF, 2 procesos | 1 901 (0,09) | 1 104 (0,04) | 15 783 (0,06) |
| **2.5, motor nativo** | **15 222 (0,70)** | **16 542 (0,67)** | **285 213 (1,15)** |
| **2.5, motor nativo + WAF †** | **11 990 (0,56)** | **12 998 (0,53)** | **264 484 (1,07)** |
| **2.5, motor nativo + WAF, 2 procesos de seguridad †** | **11 746 (0,55)** | **12 718 (0,52)** | **253 527 (1,02)** |
| 3.0.0, motor Python | 1 309 (0,06) | 752 (0,03) | 9 482 (0,04) |
| 3.0.0, motor Python + WAF | 1 168 (0,05) | 653 (0,03) | 8 788 (0,04) |
| 3.0.0, motor Python, 2 procesos | 1 733 (0,08) | 1 154 (0,05) | 17 234 (0,07) |
| 3.0.0, motor Python + WAF, 2 procesos | 1 605 (0,07) | 994 (0,04) | 14 873 (0,06) |
| **3.0.0, motor nativo** | **14 503 (0,68)** | **15 075 (0,63)** | **276 938 (1,15)** |
| **3.0.0, motor nativo + WAF** | **12 762 (0,60)** | **11 618 (0,48)** | **257 741 (1,07)** |
| **3.0.0, motor nativo + WAF, 2 procesos de seguridad** | **12 974 (0,61)** | **11 957 (0,50)** | **253 993 (1,06)** |

### Archivos medianos, archivo grande y memoria (1 proceso, sin WAF)

| Versión | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Memoria en reposo → tras la carga (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1 071 / 563 / 7 625 | 578 / 549 / 3 640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1 570 / 603 / 9 469 | 1 665 / 1 470 / 14 058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, motor Python | 1 329 / 611 / 9 805 | 1 686 / 1 472 / 14 227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, motor nativo** | **4 738 / 3 115 / 96 277** | **2 294 / 1 936 / 37 918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |
| 3.0.0, motor Python | 1 185 / 606 / 8 655 | 1 765 / 1 318 / 13 028 | 20 → 23 / 21 → 24 / 22 → 28 MB |
| **3.0.0, motor nativo** | **4 665 / 3 026 / 100 513** | **2 399 / 1 932 / 40 755** | **10 → 10 / 10 → 12 / 12 → 16 MB** |

### Grandes descargas simultáneas

Prueba: 3 descargas simultáneas de un archivo de 300 MB, mientras se pide continuamente una página pequeña. Dos pasadas por versión y por máquina, con resultados casi idénticos. La memoria es aquí la **RSS** de todos los procesos del servidor, como en la prueba original: cuenta varias veces la memoria compartida, lo que da valores más altos que la PSS de las demás tablas.

| Versión | Memoria máxima | Página pequeña, peor caso: A / B / C |
|---|---:|---|
| 1.0.0 | **1 833 a 1 836 MB** | **1,4 a 1,9 s** / **1,4 a 1,7 s** / 0,16 s |
| 2.0.0 | 39 a 42 MB | 3 ms / 4 a 6 ms / 1 ms |
| 2.5, motor Python | 41 a 44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, motor nativo | 49 a 55 MB | 1 a 2 ms / 2 a 4 ms / menos de 1 ms |
| 3.0.0, motor Python | 39 MB | 3 ms / 5 a 8 ms / 1 ms |
| 3.0.0, motor nativo | 23 a 26 MB | 1 ms / 2 a 3 ms / menos de 1 ms |

### Coste de la defensa activa (1.0 → 2.0)

Medida del 26 de octubre de 2026 en la máquina A, no repetida desde entonces: coste de una observación de amenaza por Active Defense, para cada petición sospechosa, medido en disco (ext4) sobre 2 000 observaciones.

| Medida | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediana | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Máximo | 18 a 20 ms | 37 a 46 ms |

La mediana se divide entre 12. El máximo, en cambio, es más alto en la 2.0: algunos picos aislados, ligados a la escritura periódica del diario SQLite en disco.

### Lectura

- **De la 1.0 a la 2.0**, el progreso se centra en la memoria y los archivos grandes, no en la velocidad de las páginas pequeñas:
  - la memoria tras la carga pasa de 73-98 MB a 30-32 MB;
  - durante grandes descargas, pasa de más de 1,8 GB a unos 40 MB, y el servidor sigue respondiendo (unos milisegundos en lugar de casi 2 segundos);
  - el rendimiento de los archivos grandes se multiplica por 2,7 a 3,9;
  - la 2.0 añade varios procesos, que aumentan del 25 % a casi el 100 % el rendimiento de las páginas pequeñas según la máquina.
  La 1.0 cargaba cada archivo entero en memoria antes de enviarlo. La 2.0 lo envía por bloques, o lo confía al núcleo.
- **De la 2.0 a la 2.5, el motor Python no cambia de velocidad**: las diferencias se quedan por debajo del 4 % en las máquinas B y C, y dentro del ruido de medida de la máquina A (−13 % a +9 %), la más sensible a la carga de fondo. Toda la ganancia de la 2.5 viene del **motor nativo**: unas ×10 a ×27 en archivos pequeños respecto al motor Python, y la latencia dividida entre 5 y 15.
- **En la 2.5, el motor nativo ocupaba unos 5 MB más** en reposo que el motor Python (PSS): el precio del segundo programa. Con el WAF, unos 8 MB más todavía: las reglas cargadas en el nativo.
- **De la 2.5 a la 3.0.0, la memoria baja del 30 al 70 %** con un proceso:
  - motor nativo: 33-35 → 10-12 MB en reposo. Cuando nada más lo exige, el supervisor Python se reduce a un pequeño programa de vigilancia, que no guarda en memoria ni la configuración ni el servidor Python;
  - motor Python: 28-30 → 20-22 MB. El código de una opción solo se carga si está activa, y la biblioteca TLS solo si se usa;
  - nativo + WAF: 43-45 → 28-30 MB. El proceso de seguridad nace del supervisor reducido y comparte sus páginas con él;
  - motor Python con 2 procesos: 40-43 → 35-38 MB;
  - durante grandes descargas: 39 MB (Python) y de 23 a 26 MB (nativo), frente a 41-55 MB;
  - el motor nativo ocupa ahora la mitad de memoria que el motor Python.
- **El trabajo sobre la memoria no cambia el rendimiento**: una prueba entrelazada en las máquinas B y C, con el código 3.0.0 antes y después de este trabajo, da una diferencia del 1 al 4 %. Respecto a la 2.5, el motor Python con 2 procesos sirve de un 12 a un 13 % menos en las máquinas B y C (un 26 % en la máquina A, la más sensible a la carga de fondo); el código 3.0.0 de antes de este trabajo muestra el mismo retroceso, que viene por tanto de otros cambios de la 3.0.0 y queda por estudiar. Las demás diferencias con la 2.5 van de −13 % a +13 %, en ambos sentidos.

### Lo que hay que saber del motor nativo

- Es **opcional**: el motor Python sigue siendo el motor por defecto, y el de reserva.
- Sirve él mismo el contenido estático, las redirecciones, las reescrituras, los alias, la caché, las páginas de error, las cabeceras de seguridad y TLS.
- Busca él mismo las reglas del WAF y sirve solo una petición a la que no corresponde ninguna. Cualquier otra petición (coincidencia o duda del WAF, Active Defense, autenticación) la decide Python, con exactamente los mismos controles y los mismos registros. Un control ajustable somete igualmente a Python una petición limpia de cada N, para comprobar que ambos dan el mismo veredicto.
- Reenvía él mismo el proxy inverso, WebSocket incluido (desde la 3.0.0). El listado de directorios y las páginas internas se piden a Python; FastCGI, el envío de archivos y las zonas de proxy inverso con caché se le confían para toda la conexión. Esas funciones conservan pues la velocidad del motor Python.
- Con TLS directo, FastCGI, el envío de archivos y las zonas de proxy inverso con caché no los admite el nativo: sirve entonces el motor Python, y la interfaz lo indica.
- Requiere glibc 2.38 o más reciente y OpenSSL 3. Si no arranca, la instalación lo recompila en el sitio, y si no es posible omega-serv se queda con el motor Python.

---

## 7. Comparativa de funciones

Leyenda:
- ✅ integrado;
- 🧩 módulo oficial del proyecto, que hay que activar o instalar;
- 🔌 módulo o plugin de terceros;
- ⚙️ mediante una herramienta externa;
- ❌ ausente.

«Commercial» designa una función reservada a la edición de pago.

### Servicio HTTP

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Lenguaje del servidor | C | C | Go | C | Go | Python, con un motor nativo C++ opcional |
| Servir archivos estáticos | ✅ | ✅ | ✅ | ✅ | ❌ (solo proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Archivos precomprimidos `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 receta mod_rewrite | — | ✅ |
| Compresión al vuelo | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP vía FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Varios procesos o núcleos | ✅ workers | ⚠️ `max-worker`, desaconsejado por la documentación | ✅ (Go, todos los núcleos) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; motor nativo: todos los núcleos |

### Proxy inverso

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Reparto de carga | ✅ por turnos, menos conexiones, hash | ✅ fair, round-robin, hash, sticky | ✅ una docena de estrategias | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 estrategias, entre ellas la carga real |
| Salud pasiva (apartar un servidor caído) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Salud activa (sonda periódica) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Caché de respuestas | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Descubrimiento de servicios (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (núcleo del proyecto) | ❌ |

### TLS

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Certificados automáticos (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ por defecto | 🧩 mod_md | ✅ | ⚙️ Certbot, con asistente integrado y renovación programada |
| CA local | ❌ | ❌ | ✅ CA interna (emisión automática) | ❌ | ❌ | ✅ generación, firma de CSR, revocación |

### Seguridad

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Límite de tasa por cliente | ✅ `limit_req` | ⚠️ mod_evasive (solo conexiones simultáneas) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Límite compartido entre procesos | ✅ zona de memoria compartida | ❌ contado por proceso | — (un solo proceso) | según el módulo | 1 instancia; varias con Redis | ✅ memoria compartida |
| WAF (firmas SQLi/XSS, escáneres…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (scripts Lua que escribir) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ integrado |
| Lista de bloqueo con caducidad, reincidencia | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ integrado |
| Señuelos, modo guerra, incidentes, exportación de IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Bloqueos graduados en el tiempo | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Auditoría de seguridad de la configuración | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Modo observación (registrar sin bloquear) | según el módulo | — | según el plugin | ✅ ModSecurity `DetectionOnly` | según el plugin | ✅ |

Bloqueos graduados: bloqueos cada vez más largos para las direcciones que vuelven, a lo largo de semanas, en local o a nivel de red. fail2ban los obtiene con su opción `bantime.increment`; RIPOSTE añade políticas medidas sobre los registros y simuladas antes de activarse, el levantamiento de una acción y una parada de emergencia.

### Extensibilidad

| Función | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Lenguaje de script | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | módulos Go (recompilación) | 🧩 mod_lua | plugins Go o WebAssembly | 🔌 importación de scripts mod_magnet (opción `magnet`) |
| Ecosistema de módulos | muy amplio | específico | amplio | muy amplio | amplio | ninguno: todo está integrado |

---

## 8. Administración y ergonomía

| Servidor | Modo de administración principal | Interfaz | Recarga sin corte |
|---|---|---|---|
| nginx | archivos de configuración | ninguna (panel: NGINX Plus, comercial) | ✅ `nginx -s reload` |
| lighttpd | archivo de configuración | ninguna (mod_status de solo lectura) | ✅ reinicio suave |
| Caddy | Caddyfile o JSON | API REST de administración | ✅ mediante la API |
| Apache | archivos de configuración y `.htaccess` | ninguna (mod_status de solo lectura) | ✅ `graceful` |
| Traefik | etiquetas de contenedores, archivos o Kubernetes | panel web (solo lectura) | ✅ configuración dinámica |
| omega-serv | interfaz de terminal (TUI) y línea de comandos (CLI); no hay que editar el archivo JSON | **TUI completa con teclado y ratón, 17 idiomas, ayuda integrada** | ✅ para la mayoría de los ajustes; reinicio anunciado para el puerto, TLS, el motor y el número de procesos |

En concreto, con omega-serv, la configuración, la seguridad, los registros, los servicios del sistema, las copias de seguridad y las instancias se gestionan desde una sola interfaz. Cada ajuste se explica y se verifica antes de escribirse. Con los demás servidores, se editan archivos de texto y luego se recurre a herramientas separadas (Certbot, fail2ban, logrotate, ModSecurity, una herramienta de supervisión…).

En contrapartida, el enfoque «archivo de configuración» de nginx, Apache y Caddy se automatiza muy bien (Ansible, contenedores, control de versiones). omega-serv tiene una CLI programable, pero su ecosistema de automatización sigue siendo limitado.

---

## 9. Lo que omega-serv aporta de más

Esta sección solo recoge lo que ninguno de los servidores comparados ofrece tal cual, sin módulo de terceros ni herramienta externa.

1. **Una administración completa en interfaz de terminal.**
   - La interfaz cubre todo el servidor: el sitio, la seguridad, los registros, los servicios, las copias de seguridad y las instancias.
   - Se usa con teclado y ratón, en un servidor sin pantalla gráfica, incluso a través de SSH.
   - Está disponible en 17 idiomas y explica cada ajuste.
   - Los demás servidores no tienen interfaz de administración (nginx, lighttpd, Apache), o solo una API (Caddy) o un panel de solo lectura (Traefik).
2. **Una seguridad activa integrada, sin módulos que ensamblar.**
   - El WAF incluye firmas, listas de rutas editables, la reincidencia, una lista de bloqueo con caducidad, la reputación y un modo observación.
   - Active Defense añade señuelos, un modo guerra, el seguimiento de incidentes, la exportación de indicadores de compromiso y una simulación en seco.
   - RIPOSTE responde en el tiempo: recuerda las direcciones que vuelven y les aplica respuestas graduadas, bloqueos cada vez más largos (1 h, 6 h, 24 h, 7 días por defecto), locales en la lista de bloqueo o de red mediante fail2ban (omega-jail), o un señuelo prolongado. Cada política puede medirse sobre los registros reales y simularse antes de activarse; cada acción sigue visible y puede levantarse, con una parada de emergencia.
   - En otros servidores, estas funciones exigen ensamblar ModSecurity o Coraza, conjuntos de reglas y fail2ban.
3. **Límites de seguridad exactos con varios procesos.**
   - Con varios procesos, el límite de tasa y la reincidencia del WAF se comparten en memoria entre ellos. Un atacante no puede así multiplicar su límite por el número de procesos.
   - lighttpd documenta el caso contrario: con `server.max-worker`, `mod_evasive` y `mod_status` cuentan por separado en cada proceso.
   - nginx también comparte sus contadores (zonas `limit_req`), pero no tiene WAF integrado.
4. **Dos motores, un solo comportamiento.** El motor nativo y el motor Python producen las mismas respuestas y los mismos registros, verificados automáticamente en un banco de comparación. Las herramientas que leen los registros (fail2ban, por ejemplo) no ven ninguna diferencia.
5. **La importación de scripts mod_magnet de lighttpd.**
   - Un script de protección Lua ya escrito para lighttpd se importa sin reescribirlo.
   - Se suma a la protección integrada sin poder debilitarla nunca, y su compatibilidad se verifica antes de activarlo.
6. **La gestión de varias instancias.**
   - Un registro recoge todas las instancias, y la interfaz pasa de una a otra.
   - También sabe desinstalar completamente una instancia.
7. **Una auditoría de seguridad de la configuración**: el comando `audit security` es informativo, nunca bloquea y devuelve códigos de salida utilizables en un script.
8. **Fuentes de registros remotas.**
   - La interfaz recupera por SSH el registro de otro servidor, a demanda, sin contraseña guardada.
   - Puede leerlo con lnav, fusionándolo con los registros locales.
9. **Un endurecimiento HTTP no desactivable**, activo desde la instalación, sea cual sea el perfil y el motor:
   - validación estricta de la cabecera Host;
   - rechazo de las ambigüedades Content-Length / Transfer-Encoding;
   - cabeceras de seguridad y CSP en las respuestas del sitio, incluidas sus páginas de error;
   - lectura segura de X-Forwarded-For;
   - negativa a arrancar como root.

---

## 10. Lo que los demás hacen mejor

- **Rendimiento**: lighttpd y nginx siguen siendo los más rápidos en archivos pequeños y medianos, en las tres máquinas. Incluso con el motor nativo, omega-serv sirve unas 0,7 veces nginx y 0,5 veces lighttpd en archivos pequeños, y de 0,3 a 0,6 veces nginx en archivos de 100 KB. Para un sitio con mucho tráfico, una API pública o una CDN, son ellos los que hay que elegir.
- **Archivos medianos**: Apache sirve los archivos de 100 KB más rápido que el motor nativo de omega-serv, en las tres máquinas.
- **Proxy inverso**:
  - nginx reenvía las respuestas pequeñas entre un 10 y un 22 % más rápido que el motor nativo, y hasta 1,6 veces más rápido en HTTPS en la máquina C;
  - en HTTPS, en las respuestas de 100 KB, lighttpd lo supera en la máquina C, y Caddy y Traefik en la máquina A;
  - nginx, lighttpd y Apache reenvían con 4 a 15 MB de memoria, omega-serv con unos 30.
- **Memoria**: lighttpd (1 MB), nginx (de 4 a 5 MB) y Apache (de 4 a 9 MB) convienen a máquinas muy limitadas (embebido, contenedores pequeños). omega-serv 3.0.0 necesita de 10 a 55 según el modo.
- **Coste de la seguridad**: el WAF sigue teniendo un coste. Con el motor nativo, resta del 5 al 22 % del rendimiento en archivos pequeños, limitación de tasa incluida: omega-serv con WAF sirve de 0,53 a 0,56 veces nginx sin WAF en las máquinas A y B. Una petición sospechosa o dudosa (coincidencia de una regla, texto no ASCII, origen vigilado por Active Defense) pasa siempre por Python, y se sirve a la velocidad del motor Python. Con magnet activo, todas las peticiones pasan por Python, y el WAF divide entonces el rendimiento del motor nativo entre 4 y 7, como antes de la optimización.
- **Protocolos**: HTTP/2 en todos los demás, HTTP/3 en nginx, Caddy y Traefik. omega-serv solo habla HTTP/1.1.
- **HTTPS automático**: Caddy y Traefik lo integran por defecto, y nginx (`ngx_http_acme_module`) y Apache (`mod_md`) con un módulo oficial. omega-serv delega en Certbot, con un asistente y una renovación programada.
- **Entornos de contenedores**: el descubrimiento automático de servicios de Traefik (Docker, Kubernetes) no tiene equivalente en omega-serv.
- **Ecosistema y madurez**: nginx y Apache ofrecen miles de módulos, guías e integraciones, y décadas de uso en producción. Caddy ofrece un sistema de módulos en Go. omega-serv es un proyecto joven, mantenido por una sola persona, y su motor nativo es reciente.
- **Compresión al vuelo**: omega-serv solo sirve archivos ya comprimidos.

---

## 11. Qué servidor para qué uso

| Necesidad | Elección aconsejada |
|---|---|
| Sitio con mucho tráfico, API pública, CDN, rendimiento máximo | **nginx** o **lighttpd** |
| Proxy inverso con el máximo rendimiento, HTTP/2 o HTTP/3 hacia los clientes | **nginx** |
| Máquina muy limitada, embebido, archivos estáticos | **lighttpd** |
| Inicio rápido con HTTPS automático, configuración corta | **Caddy** |
| Aplicación PHP histórica, `.htaccess`, alojamiento compartido | **Apache** |
| Docker, Kubernetes, microservicios | **Traefik** |
| Sitio pequeño o mediano, servicio interno, laboratorio, VPN, administración sin editar archivos | **omega-serv** (motor nativo si es posible) |
| Servidor expuesto en el que se quiere ver y controlar la seguridad (WAF, bloqueos graduados, señuelos) desde una sola interfaz | **omega-serv** |
| Proxy inverso con reparto, salud, caché y WAF, gestionado desde una interfaz | **omega-serv** (motor nativo: segundo por detrás de nginx en rendimiento) |
| Aprender el endurecimiento HTTP y la defensa activa | **omega-serv** |

Estas herramientas también se combinan. Por ejemplo:
- nginx o Traefik al frente en Internet, con omega-serv detrás para un servicio interno, su seguridad y su administración;
- omega-serv como proxy inverso interno delante de varios servidores de aplicaciones.

---

## 12. Reproducir las medidas

Las herramientas se entregan en el repositorio, en `tools/bench/`. Hacen falta nginx, lighttpd, Apache, Caddy y oha instalados (y Traefik para el proxy inverso), el entorno de desarrollo de omega-serv (`.venv`) y, para el motor nativo, el binario compilado en `native/omega-http-core/build-release`.

```sh
# 1. preparar una carpeta de medida (archivos de prueba, configuraciones, omega-serv 1.0, 2.0 y versión actual)
tools/bench/compare/setup.sh /ruta/medida omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. las 21 configuraciones, 3 repeticiones entrelazadas (de 40 a 60 minutos)
#    SRV_CPUS / CLI_CPUS: núcleos del servidor y del cliente (lscpu -e da la topología)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /ruta/medida > resultados.txt

# 3. medianas
python3 tools/bench/compare/summarize.py resultados.txt

# otra lista de configuraciones, por ejemplo 4 procesos
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /ruta/medida > resultados-4.txt

# grandes descargas (memoria y reactividad): versión actual, motor Python y luego nativo, y luego 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/ruta/medida/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/ruta/medida/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# proxy inverso (§5): backend, certificado, configuraciones de los 6 proxys, y luego 3 repeticiones entrelazadas
#    máquina C: SRV_CPUS=0-3 BACK_CPUS=4,5 CLI_CPUS=6-9 y CONFIGS="nginx-4 lighttpd-4 apache-4 caddy-4 traefik-4 omega-nat-1-0 omega-nat-1-1"
tools/bench/proxy/setup.sh /ruta/proxy /ruta/a/traefik
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/proxy/campaign.sh /ruta/proxy > proxy.txt
python3 tools/bench/proxy/summarize.py proxy.txt

# volver a medir solo omega-serv (memoria de la 3.0.0): archivos, grandes descargas y proxy inverso, nginx como referencia
MACHINE=a SRV_CPUS=0,2 CLI_CPUS=1,3 tools/bench/memoire-3.0.0.sh /ruta/medida > memoria.txt

# medir cualquier otro servidor ya en marcha, sin oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-de-prueba
python3 tools/bench/bench_any.py --port 8080
```

Nombres de las configuraciones: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N procesos, o N núcleos para Caddy); `omega-vX-N-W` para omega-serv (versión `v1`, `v20` o `v2` para la versión actual, N procesos, W = 0 sin WAF o 1 con él), seguido de `-native` para el motor nativo.

Para el proxy inverso: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N`, `traefik-N`, `omega-py-N-W` (motor Python) y `omega-nat-N-W` (motor nativo, N procesos de seguridad), seguidos de `-tls` para HTTPS del lado del cliente.

Para publicar sus propios resultados, indique la máquina, las versiones, el reparto de los núcleos y las tres repeticiones.

---

## 13. Fuentes

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
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
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

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (bloqueos más largos para los reincidentes)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (consultado el 4 de noviembre de 2026)

**Herramienta de medida**
- [oha](https://github.com/hatoo/oha)

---

*Comparativa realizada por kraynux para omega-serv 2.5 y 3.0.0: medidas del 3 y el 4 de noviembre de 2026 en tres máquinas (proxy inverso: 14 de noviembre de 2026; memoria de omega-serv 3.0.0: 19 de noviembre de 2026; defensa activa: 26 de octubre de 2026). Para cualquier decisión de capacidad, mida en su propio hardware con las herramientas suministradas.*

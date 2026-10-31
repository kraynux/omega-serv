<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Servidor web HTTP autónomo, portable y reforzado por defecto**

> Desarrollado por [kraynux](https://github.com/kraynux) para [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Página oficial: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/es/) &nbsp; Referencia, uso, Ayuda y FAQ: [Guía completa](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/es/guide.html)  
Vista previa: [Capturas de pantalla](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; Demostración [Servidor de demostración](https://craftdark.snake-mackarel.ts.net) &nbsp; [Comparativa/pruebas de servidores web](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-uso)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 Documentación, exportaciones e interfaz disponibles en **17 idiomas** — vea [Idiomas de la interfaz](#idiomas-de-la-interfaz).  
**Idiomas:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** es un servidor HTTP/1.1 escrito en Python puro (solo biblioteca estándar para el núcleo del servidor), pensado para servir contenido estático y, opcionalmente, PHP-FPM, con un endurecimiento del protocolo que no se puede desactivar y módulos de seguridad (WAF, TLS, autenticación) que se superponen en lugar de imponerse. Séptima herramienta de la suite `omega-`, pero deliberadamente **fuera de la futura integración `omega-suite`** (actúa sobre la máquina local que lo aloja, no sobre objetivos remotos — misma familia que `omega-fire`); estructurado en Clean Architecture, con `bootstrap/` como raíz de composición.

## 1. Visión y alcance

La prioridad declarada es **la solidez/seguridad del núcleo HTTP primero** — WAF y TLS son módulos opcionales colocados encima, nunca requisitos previos. Un servidor que hace una sola cosa (servir archivos, eventualmente PHP) pero la hace correctamente, con un endurecimiento de protocolo real e imposible de eludir, en lugar de un servidor que hace muchas cosas a medias.

### Lo que hace OMEGA-SERV

- Sirve contenido estático (archivos, listado de directorio opcional, alias, redirecciones, reescrituras, caché) con una resolución de rutas segura (traversal, doble codificación, enlaces simbólicos). Los archivos grandes salen por bloques directamente desde el disco, nunca se cargan en memoria; cada archivo lleva un `ETag` y un `Last-Modified` (recarga = respuesta 304 vacía) y acepta peticiones parciales `Range` (reanudar una descarga, vídeo); imágenes, multimedia, fuentes, CSS y JS reciben un `Cache-Control` por defecto, modificable en la pantalla Caché. Archivos de texto precomprimidos: si `site.css.br` o `site.css.gz` existe junto a `site.css` (creados con `brotli -k site.css` o `gzip -k site.css`) y el navegador los acepta, se envían en su lugar, nunca una versión más antigua que el original.
- Endurece el protocolo HTTP por defecto, sin opción para desactivarlo: métodos permitidos explícitos, validación de la cabecera `Host`, rechazo de la ambigüedad `Content-Length`/`Transfer-Encoding`, cabeceras de seguridad y CSP de base imposibles de eludir.
- Opcionalmente: filtrado WAF (firmas, limitación de tasa, lista de bloqueo), TLS directo (certificado autofirmado, firmado por una CA local, o público mediante Let's Encrypt/Certbot con renovación automática — vea §9), autenticación HTTP Basic por zona, PHP mediante FastCGI/PHP-FPM, zonas de subida confinadas.
- Modo « boost »: varios procesos de servidor, como máximo uno por CPU disponible en la máquina (pantalla Resistencia y límites); los contadores de seguridad (límite de tasa, reincidencia) se comparten entre ellos y siguen siendo exactos.
- Audita su propia configuración (`audit security`) y se instala como servicio del sistema (systemd/OpenRC/runit).
- CLI no interactiva programable de principio a fin, **e interfaz interactiva (Textual)** que reviste exactamente los mismos casos de uso — vea §3. Hoja de ruta de la interfaz (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) **entregada por completo**: registro de capacidades, perfiles/opciones, configuración detallada (alias/redirecciones/reescrituras/FastCGI/listado de directorio/autenticación/caché/WAF/proxies de confianza/reverse proxy saliente/TLS), gestión de logs (Biblioteca/Favoritos, 3 visores — simple/clásico/lnav fusionado —, Ver y tratar IP, fuentes remotas SSH, rotación/copia de seguridad/automatización/restauración/purga/exportación), servicio del sistema, multi-instancia (registro, creación), verificación/simulación/auditoría, copia de seguridad/restauración de la configuración, asistente de primer inicio, ajustes de la aplicación (tema, perfil de renderizado, rutas de exportación/capturas), guía de ayuda contextual (ficha por pantalla con ejemplos concretos, FAQ, exportación HTML, cobertura exhaustiva verificada por prueba), indicación sistemática de recarga/reinicio tras cada guardado, configuración completa de Active Defense sin edición manual de archivos.

### Lo que OMEGA-SERV no hace

- CGI en bruto (retirado del alcance de la V1 — solo se admite FastCGI/PHP-FPM).
- Autenticación TLS mutua (mTLS), OCSP stapling — fuera del alcance de la V1, vea §15. (ACME/Let's Encrypt mediante Certbot está disponible, vea §9c/9d.)
- Caché HTTP compartida entre procesos.
- Escaneo/auditoría de un objetivo remoto (vea `omega-check`/`omega-scan`/`omega-deep` para eso — Omega-serv solo se audita a sí mismo, nunca a un tercero).

### OMEGA-SERV frente a los servidores web del mercado

Ver [Mediciones y comparativa](comparatif-serveurs-web.md)  
Comparativa medida entre: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/es/)

### Advertencia de uso

Omega-serv **se niega a arrancar como root**. Ningún módulo de seguridad (WAF, TLS, autenticación) está activado por defecto en ninguno de los perfiles suministrados, incluido `hardened` — activarlos es siempre un gesto explícito (`config enable-tls`, `option enable waf`...). El propio perfil `hardened` recomienda un reverse proxy para una exposición real a Internet en lugar de sustituirlo.

## 2. Instalación

### Requisitos previos

- Python 3.10+
- `openssl` (el binario, no una biblioteca de Python) para todo lo relacionado con los certificados TLS — las demás funciones funcionan sin él.

### Descarga

Archivo de la última versión y sumas SHA-256 de cada versión: [omega-serv-2.0.1.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### Instalación

> ⚠️ **¿Está actualizando una instalación existente?** El comando siguiente **omite silenciosamente la extracción** si `omega-serv/` ya existe (supone que se trata de una primera instalación interrumpida, no de una actualización) — reinstalaría entonces las dependencias sobre el **código antiguo sin cambios**, sin el menor mensaje de error. Use en su lugar la sección [Actualización](#actualización) más abajo.

```bash
[ -d omega-serv ] && echo "ℹ️ Ya extraído aquí, paso omitido." || tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Crea el entorno virtual `.venv` si todavía no existe.
2. Instala el paquete (`pip install -e .`) — **ninguna dependencia externa** (vea §6).
3. Hace ejecutables `omega-serv.sh` e `install.sh`.
4. Añade el alias `serv` a `~/.bashrc` y `~/.zshrc` (sin duplicados si ya está presente).

### Actualización

Si `omega-serv/` ya existe (instalación anterior), **no ejecute nunca `tar` desde el interior de esa carpeta**: intentaría crear un `omega-serv/omega-serv/` anidado y fallaría. A diferencia de omega-fire, `install.sh` nunca toca los permisos de la carpeta (ningún paso pide `sudo`) — por lo tanto no hay riesgo de una carpeta perteneciente a `root` aquí, y extraer directamente encima de la instalación existente es seguro.

```bash
# Desde la carpeta PADRE de omega-serv/ (nunca desde el interior)
tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
./install.sh
```

El archivo excluye deliberadamente todo el estado vivo (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — el sitio realmente servido**...) — una extracción encima nunca toca sus datos, certificados, ajustes ni el contenido servido; solo se sustituye el código de la aplicación. `install.sh` reutiliza el `.venv` existente y simplemente reinstala las dependencias encima.

Desde el 2026-10-18, `var/` y `secure/auth/` ya no figuran en absoluto en el archivo, ni siquiera vacíos: una extracción encima ya no restablece sus permisos (compartidos con la cuenta del servicio systemd) — ya no es necesario « Servicio → Reparar los permisos » tras una actualización. `install.sh` crea esas carpetas si faltan, sin tocar nunca las que existen.

> ⚠️ **Si ya hay un servicio activo, el paso anterior no basta.** Sustituye el código en disco, pero el proceso que ya se está ejecutando sigue funcionando con el código antiguo cargado en memoria — a continuación es siempre necesario un **reinicio completo**:
> ```bash
> sudo systemctl restart <nombre-del-servicio>
> ```
> **Nunca una simple recarga** (`systemctl reload`, o pantalla SERVICIO → *Recargar*): esta solo vuelve a leer algunas opciones de configuración (reglas WAF, zonas de autenticación...), **nunca el propio código Python**. Un `systemctl status <nombre-del-servicio>` que muestre una fecha de inicio anterior a su actualización confirma que sigue ejecutando el código antiguo. Si siempre actualiza sobrescribiendo la misma carpeta (caso estándar anterior), este reinicio es el único paso que falta — no es necesario reinstalar el servicio.

> ⚠️ **Si el servicio entra después en un bucle de reinicios** (`systemctl status` alternando activo/inactivo, `journalctl -u <nombre-del-servicio>` mostrando un `PermissionError` al escribir un archivo bajo `var/`): la extracción con `tar` restaura los permisos de las carpetas tal como se capturaron en el archivo, lo que puede borrar los permisos compartidos establecidos para la cuenta de sistema dedicada durante la instalación inicial — aunque `install.sh` en sí nunca los toque. No es necesario reinstalar la unidad: pantalla SERVICIO → **Reparar los permisos** (vuelve a aplicar el reparto en `var/` y `secure/auth/`, sin tocar la unidad systemd).

### Dependencias

El núcleo del servidor (parser HTTP/1.1, cliente FastCGI, hash de contraseñas mediante `hashlib.scrypt`) sigue siendo Python puro/stdlib, y todo lo relacionado con los certificados TLS pasa por el binario `openssl` como subproceso en lugar de una biblioteca criptográfica de Python — **ninguna dependencia externa para eso**. Solo la interfaz interactiva (§3) introduce algunas: `omega-lib` (temas, detección de terminal — biblioteca compartida de la suite, no publicada en PyPI, incluida en el archivo distribuido), `textual` y `pyte` (emulación de terminal para el renderizado de `lnav` fusionado en la interfaz), `jinja2` (exportaciones HTML con tema) y `psutil` (pantalla Estado y recursos — CPU/RAM/disco/red). Dependencia opcional de desarrollo/pruebas (`pip install -e ".[test]"`): `hypothesis` (pruebas basadas en propiedades del parser HTTP y del resolvedor de rutas, nunca en producción). Herramientas de calidad (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. Extra opcional adicional (`pip install -e ".[magnet]"`): `lupa` (enlace Lua embebido, rueda precompilada, no requiere ningún intérprete `lua` del sistema), únicamente para el script WAF complementario « magnet » (§7) — nunca instalado por defecto; su ausencia se señala (capacidad `waf-magnet`, pantalla **Capacidades**) con el comando de instalación exacto, sin bloquear el resto del servidor.

### Herramientas opcionales recomendadas

La interfaz funciona en modo degradado si faltan estas herramientas:

- `openssl` — necesario para todo lo relacionado con los certificados TLS (autofirmado, CA local, importación); sin él, los comandos `certs *` fallan pero el resto del servidor funciona con normalidad (vea §9).
- `certbot` — necesario únicamente para el asistente **Let's Encrypt** y su renovación automática (§9c/9d); el TLS autofirmado/CA local no lo requiere.
- `lnav` — análisis avanzado de logs fusionado en la pantalla **Gestión de logs** (§3); mensaje de error claro y explícito si no se encuentra el ejecutable, ningún bloqueo, el resto de la pantalla (ver/seguir/rotación/estadísticas) funciona con normalidad sin él.
- `scp` (paquete `openssh`/`openssh-clients`, casi siempre presente) — necesario únicamente para las **Fuentes remotas (SSH)** (§13a); sin él, la recuperación falla con un mensaje claro, el resto de la Biblioteca funciona con normalidad.
- `python-psutil` (paquete del sistema equivalente al `psutil` de PyPI) — instalado automáticamente por `pip install -e .` en todos los casos (dependencia obligatoria del paquete, la pantalla **Estado y recursos** lo necesita siempre), pero preinstalarlo con el gestor del sistema evita que `pip` tenga que compilar su wheel localmente.

```bash
# Arch Linux y derivadas
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu y derivadas
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. Uso

Dos interfaces estrictamente equivalentes en funcionalidad, nunca lógica duplicada entre ambas: CLI no interactiva (programable, usada a continuación) e interfaz interactiva Textual (menús, formularios, tablas) — cada acción de una existe en el lado de la CLI, la interfaz solo reviste los mismos casos de uso.

### Modo interactivo (TUI)

Recomendado para el uso diario — se lanza sin argumentos:

```bash
./omega-serv.sh
```
si ha creado el alias, escriba simplemente `serv` en el terminal:
```bash
serv
```

### Idiomas de la interfaz

17 idiomas: francés, inglés, español, portugués (Brasil), italiano, alemán, neerlandés, polaco, ruso, chino, vietnamita, tailandés, indonesio, japonés, coreano, hindi, árabe. Se elige en los Ajustes (tecla `o`, « Langue / Language », etiqueta que nunca se traduce), o puntualmente con `OMEGA_SERV_LANG=es serv`. En la consola de texto de Linux (TTY), los idiomas cuya escritura no existe en las fuentes de consola (vietnamita, chino, tailandés, japonés, coreano, hindi, árabe) se muestran en inglés durante la sesión. En hindi, los terminales que componen ellos mismos las letras ligadas (Kitty, Ghostty, Konsole) desplazan marcos y columnas, de forma variable según la fuente: se muestra un aviso al iniciar; Terminator, GNOME Terminal, Xfce Terminal y Alacritty muestran el hindi alineado. Dos ajustes aparte: el **idioma de las páginas para visitantes** (páginas de error, listado de directorio — pantalla Páginas de error, francés por defecto) y el **idioma de las exportaciones** (HTML e informe de incidente — Ajustes, « Como la interfaz » por defecto). Los registros del servidor (`journalctl`) permanecen en francés.

### Recorrido general

Pantalla de inicio (splash, se cierra con una tecla o un clic) → menú principal (Asistente de primer inicio / Registro de capacidades / Perfiles / Configuración detallada / Seguridad activa / Gestión de logs / Servicio / Multi-instancia / Estado y recursos / Auditoría / Copia de seguridad) → selección de una sección y después de una acción, cada formulario valida sus campos obligatorios antes de continuar → confirmación explícita antes de cualquier operación sensible o destructiva (reinicio, eliminación, restauración...) → indicación sistemática de lo que sigue (recarga en caliente automática, o confirmación de reinicio completo) tras cualquier guardado que modifique una configuración ya servida. La adaptación al terminal (colores, tamaño, degradación estructural del perfil de renderizado) es automática y sin flag manual — vea §4.

#### Atajos de teclado (interfaz interactiva)

| Tecla | Acción |
|---|---|
| `↑` / `↓` | Navegar entre los elementos de una pantalla |
| `Tab` / `Mayús+Tab` | Navegar entre los campos de un formulario |
| `Esc` | Volver a la pantalla anterior (confirmación de salida en el inicio) |
| `t` | Tema siguiente (aplicado inmediatamente, sin confirmación) |
| `r` | Refrescar la detección del terminal |
| `F1` | Ayuda de la pantalla activa (ficha contextual — vea "Guía de ayuda" más abajo) |
| `a` | Guía de ayuda completa (menú navegable + FAQ) |
| `o` | Ajustes de la aplicación (tema, perfil de renderizado, rutas de exportación/capturas — vea más abajo) |
| `q` | Salir (con confirmación) |
| `Ctrl+P` | Paleta de comandos (Tema, Captura de pantalla, Opciones...) |

> **Excepción — editor de listas (WAF → Custom)**: ningún atajo, todo se hace con el ratón; el teclado solo sirve para escribir (caracteres, Intro, flechas, Inicio/Fin, Re Pág/Av Pág, Retroceso, Supr). `Esc`, `F1` y `Ctrl+P` están inactivos ahí (botón **Ayuda**); solo `Ctrl+Q` sigue activo, con confirmación de los cambios no guardados.

#### Guía de ayuda (teclas `F1`/`a`)

Sistema de ayuda integrado, nunca un simple texto estático: cada pantalla documentada (ficha con definición/campos a rellenar con ejemplos concretos/acción desencadenada/reacción — recarga, reinicio o ninguna) es accesible directamente desde ella con `F1`; la tecla `a` abre el menú completo (árbol idéntico a la navegación real de la aplicación) con acceso a la FAQ (trampas encontradas en el uso real, p. ej. clases de ataque de Active Defense, permisos de servicio compartido) y una exportación HTML autónoma (conservando el tema activo) de toda la guía. Recurre a una pantalla de referencia genérica mientras no exista una ficha precisa — cobertura actualmente exhaustiva, verificada por prueba.

#### Menú principal (interfaz interactiva)

- **Asistente de primer inicio** — recorrido guiado en 8 pasos (bienvenida → capacidades en solo lectura → elección del perfil → bind/puerto → TLS opcional → verificación → resumen + escritura → propuesta de instalación del servicio); permite generar una configuración completa y poner el servidor en marcha sin conocer la CLI.
- **Registro de capacidades** — sonda del sistema en solo lectura (sistema de init, puerto configurado ya ocupado o no, presencia de `openssl`/`logrotate`/`tailscale`/`lnav`, espacio en disco, límite de descriptores...), exportación JSON/HTML.
- **Perfiles** — mismo caso de uso que `profile` en la CLI (§5), diff siempre mostrado antes de escribir.
- **Configuración detallada del servidor** — CRUD completo sobre alias/redirecciones/reescrituras/listado de directorio/proxies de confianza/reverse proxy saliente/FastCGI/caché/autenticación/control de acceso/páginas de error, más el submenú **TLS** (estado, generación autofirmada, asistente de CA local, asistente Let's Encrypt/Certbot, renovación automática, revocación, activar/desactivar — vea §9); un segundo marco, **OPCIONES Y VERIFICACIÓN**, agrupa los accesos directos a **Opciones** (`option` CLI, §7) y **Comprobar la configuración** (`config check` CLI, §10) — el mismo recorrido que ajustar y luego verificar; estas dos pantallas ya no son accesibles directamente desde el menú principal. El WAF ya no vive ahí (vea "Seguridad activa" más abajo): expone sobre todo un estado operativo que cambia continuamente, no un simple formulario de configuración estático. Cada guardado indica sistemáticamente lo que sigue: recarga en caliente automática y silenciosa si hay un servicio activo (listado de directorio, acceso, alias/redirecciones/reescrituras, caché, páginas de error, proxies de confianza, zonas de reverse proxy/FastCGI, usuarios/zonas de autenticación), o confirmación explícita de reinicio completo cuando el cambio afecta al socket de escucha, a TLS o a Active Defense — ninguna pantalla deja ya adivinar si hay que reiniciar el servidor.
- **Seguridad activa** — pantalla única que agrupa dos bloques uno al lado del otro: **Active Defense** (Estado, Amenazas seguidas con puntuación/nivel, Incidentes con cronología/exportación IoC/informe, asignaciones de Deception, Simular una decisión en dry-run, **Ajustes** — configuración completa sin editar nunca `config/omega-serve.json` a mano, vea §11) y **WAF** (Estado, Módulos — modo/paquetes de reglas/lista de bloqueo, Probar una petición, Custom — autoría de reglas personalizadas y carga de listas de rutas/palabras clave editables con el ratón (vea §11b), Magnet — importar un script `mod_magnet` externo con comprobación de compatibilidad antes de activarlo) — vea §11.
- **Gestión de logs** — menú en dos columnas. Columna **Biblioteca**: centro que referencia todo log a tratar (alimentación manual, un clic añade de oficio los logs propios de la instancia — access/error/WAF nativo, + script magnet §7 si está activo —, o una **fuente remota** recuperada por SSH, vea más abajo); **Favoritos** (combinación logs + visor guardada con un nombre, lanzamiento directo); **Ver los logs** con 3 visores a elegir según el número de logs seleccionados — Simple (tail en directo + estadísticas genéricas IP/errores/códigos HTTP sobre cualquier formato), Clásico (lectura + seguimiento), `lnav` fusionado (renderizado de terminal real dentro de la interfaz, logs magnet incluidos de oficio + rutas manuales **fijadas** para conservarlas entre sesiones); **Ver y tratar IP** (top de IP en uno o varios logs a elegir, periodo 24 h/7 d/30 d/todo, eliminación de una IP). Columna **Mantenimiento** (sin cambios): rotación/archivado manual o automático por umbral de tamaño, creación inmediata de copia de seguridad, configuración/gestión de automatizaciones planificadas (declarativas — vea la nota más abajo), restaurar/purgar un archivo, exportación de la lista.
- **Servicio** — mismas acciones que `service` en la CLI (§12), elevación `sudo` puntual por acción, nunca la aplicación entera lanzada como root.
- **Multi-instancia** — registro global (`~/.config/omega-serv/instances.json`, fuera de cualquier directorio de proyecto) de las instalaciones conocidas en la máquina, con el estado systemd de cada una; creación de una nueva instancia (copia del árbol, entorno virtual y dependencias propias, configuración nueva con un puerto distinto, comprobación de no anidamiento y de conflicto de puertos) directamente desde la interfaz. Botón prácticamente invisible para una instalación única (la etiqueta "Multi-instancia" pasa a "Instancias (N)" en cuanto se conocen 2); cambio completo a otra instancia (`os.execv`, confirmación explícita, splash dedicado que anuncia el cambio al reiniciar); desinstalación completa de una instancia (retirada de la unidad, de la cuenta de sistema dedicada si ninguna otra instancia la usa, y eliminación opcional del directorio, nunca por defecto).
- **Estado y recursos** — vista general de un vistazo, refrescada cada 2 segundos: estado del servidor (proceso/PID, estado del servicio del sistema, perfil/opciones activas/TLS/puerto), flujo del log de acceso en directo (caudal, reparto por código de estado, IP únicas, tasa de errores), recursos del sistema (CPU/RAM/disco/swap/carga/red, mediante `psutil`); agrupa también el acceso directo **Simular una petición** (mismo caso de uso que el comando CLI correspondiente, §10).
- **Auditoría de seguridad** — mismo caso de uso que el comando CLI correspondiente (§10).
- **Copia de seguridad de la configuración** — archivo tar.gz del archivo de configuración y, con opción explícita, de las reglas WAF/zonas de autenticación/certificados (confirmación obligatoria en cuanto se incluyen secretos reales)/base de Active Defense, restauración, lista, eliminación.

> Nota sobre las automatizaciones de rotación planificadas: se registran (frecuencia + log objetivo) pero **nada las ejecuta automáticamente** — ni en la interfaz ni como tarea en segundo plano. Es una elección deliberada de paridad con la pantalla equivalente de `omega-fire`, que tiene el mismo comportamiento declarativo. Una ejecución periódica real (temporizador systemd, tarea en segundo plano) queda por construir por separado si se confirma la necesidad.

#### Ajustes de la aplicación (tecla `o` o paleta de comandos)

Solo preferencias de la interfaz — nunca confundidas con `config/omega-serve.json` (configuración del servidor): tema activo, perfil de renderizado (`complete`/`standard`/`reduced`/`mono`, requiere reinicio), ruta de las exportaciones (`var/exports/` por defecto), ruta de las capturas de pantalla (`var/screenshots/` por defecto), purga de una u otra carpeta (confirmación obligatoria).

```bash
# Lanzar el servidor (primer plano, SIGTERM = parada limpia con periodo de gracia, SIGHUP = recarga en caliente WAF/Auth)
./omega-serv.sh serve

# Configuración
./omega-serv.sh config init                # genera config/omega-serve.json (valores seguros por defecto)
./omega-serv.sh config check                # comprueba sin arrancar (mismas barreras bloqueantes que al arrancar)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Perfiles (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # diff antes de aplicar, siempre

# Opciones (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Simular una petición sin lanzar el servidor (útil para validar una regla antes de activarla)
./omega-serv.sh simulate-request GET /index.html

# WAF (funciona incluso con la opción desactivada, mediante --force implícito)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "escaneo detectado" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + modo guerra, opción "active_defense" - vea §11)
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

# Certificados TLS - autofirmado (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# Certificados TLS - CA local (9b)
./omega-serv.sh certs generate-ca --cn "Mi CA local" --days 3650
./omega-serv.sh certs generate-csr --cn servidor.local --san-dns servidor.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# Certificados TLS - importación (9c, p. ej. desde un hook de Certbot)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# Autenticación HTTP Basic
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Auditoría de seguridad (nunca bloquea, informativa)
./omega-serv.sh audit security --format text --min-severity medium

# Copia de seguridad de la configuración (config siempre incluida; secretos reales
# nunca cifrados por defecto, --confirm-secrets obligatorio para incluirlos)
./omega-serv.sh config backup --description "antes de la migración"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "amenazas/incidentes"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Servicio del sistema (systemd/OpenRC/runit, detección automática)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Códigos de salida notables

| Comando | Código | Significado |
|---|---:|---|
| `audit security` | `0` | Nada grave (ningún `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Al menos un hallazgo `CRITICAL` |
| `audit security` | `2` | Al menos un `HIGH` sin `CRITICAL` |
| `audit security` | `3` | Error de ejecución (config no encontrada...) |
| `certs check-expiry` | `1` | Certificado caducado |
| cualquier otro comando | `0`/`1` | Éxito / fallo de validación |

## 4. Compatibilidad con terminales

La interfaz interactiva ([Textual](https://textual.textualize.io/), construida sobre [Rich](https://rich.readthedocs.io/)) detecta automáticamente las capacidades del terminal (emulador, tamaño) y adapta en consecuencia su hoja de estilo estructural (`complete`/`standard`/`reduced`/`mono`), sin flag manual. El modo CLI permanece siempre en texto simple, independiente del terminal. Política compartida por toda la suite `omega-` (`omega-lib`, `terminal/policies.py`) — idéntica a la de `omega-check`/`omega-fire`.

### Perfil según el emulador detectado

| Emulador | Perfil inicial |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, SSH moderno | `reduced` |
| TTY de Linux, SSH antiguo | `mono` |
| Emulador no reconocido | `reduced` (alternativa por defecto) |

### Perfil según el tamaño del terminal

| Tamaño mínimo (columnas × líneas) | Techo de perfil |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| por debajo | `mono` |

El perfil final elegido es **el más restrictivo de los dos** (emulador y tamaño) — un Ghostty a pantalla completa redimensionado a 70 columnas baja a `mono`, aunque su emulador permitiría `complete`. Se puede refrescar en directo con la tecla `r`, o forzar manualmente desde los Ajustes de la aplicación (tecla `o`, §3).

## 5. Perfiles

| Perfil | Uso previsto |
|---|---|
| `minimal` | Demostración/local sencillo: solo estático, ninguna opción activada |
| `standard` | Sitio estático o pequeña producción: cabeceras habituales, CSP de base, dirlisting/CGI/FastCGI desactivados |
| `hardened` | Exposición con mínimo privilegio: bind local por defecto (reverse proxy recomendado para Internet), métodos limitados a GET/HEAD, CSP estricta, anti-slowloris — el WAF **nunca** se activa automáticamente, ni siquiera aquí |
| `development` | Solo desarrollo local, nunca presentado como apto para Internet: bind loopback obligatorio, CSP en report-only, páginas de error detalladas |

Orden de fusión de la configuración: valores seguros integrados → perfil seleccionado → opciones activas actualmente conservadas (sobreviven a un cambio de perfil) → capa explícita del usuario. Siempre se muestra un diff completo antes de escribir (`profile apply`).

## 6. Arquitectura

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` es la raíz de composición (equivalente al `app/` de las demás herramientas de la suite). Particularidad asumida de este proyecto, verificada por `import-linter` en lugar de supuesta: `application/server/start_server.py` (y `validate_config.py`, `run_audit.py`) desempeñan un papel de **fábrica de construcción dependiente de la configuración real** (qué gestor de servicios, activar o no el WAF...) e instancian directamente adaptadores concretos de `infrastructure/` — a diferencia del patrón más estricto de CHECK/TRACK, donde `application/` solo consume `ports/`. La única regla universal realmente impuesta: `domain/`/`core/` nunca dependen de las capas externas.

```text
src/omega_serv/
├── core/            Vocabulario transversal (platform_info, constantes)
├── domain/           Lógica de negocio pura (HTTP, config, seguridad WAF/TLS/auth/auditoría, enrutamiento)
├── ports/            Contratos (Protocol) esperados por la aplicación
├── application/      Casos de uso - algunas funciones (build_server...) también componen adaptadores concretos (vea arriba)
├── infrastructure/    Implementaciones reales (asyncio, openssl como subproceso, systemd/OpenRC/runit, archivos)
├── interfaces/cli/    CLI argparse no interactiva
├── interfaces/tui/    Interfaz interactiva Textual (mismos casos de uso, nunca lógica duplicada)
└── bootstrap/         DependencyContainer, resolución de la raíz del proyecto
```

Reglas verificadas por `import-linter` (8 contratos): `domain`/`core` nunca dependen de las capas externas; `interfaces.tui` nunca depende directamente de `infrastructure`; `textual` confinado a `interfaces.tui`; `subprocess` confinado a `infrastructure/process/subprocess_runner.py` (y `infrastructure/lnav/`, flujo PTY interactivo); `ssl` confinado a `infrastructure/tls/ssl_context_builder.py`; `jinja2` confinado a `infrastructure/exporters/html_exporter.py`; `sqlite3` confinado a `infrastructure/persistence/sqlite_active_defense_connection.py` (único almacenamiento relacional del proyecto, reservado a Active Defense — vea §11); `lupa` confinado a `infrastructure/waf/lua_waf_adapter.py` (script WAF complementario « magnet », §7).

## 7. Módulos opcionales

Todos desactivados por defecto en todos los perfiles suministrados — activación siempre explícita (`option enable <nombre>` o `config enable-tls`):

| Módulo | Función |
|---|---|
| `waf` | Firmas (rutas sensibles, UA/Referer de escáner, SQLi/XSS/CMDi en el cuerpo), listas editables en archivo de texto (palabras clave, o rutas sensibles con excepciones `!`, modo Observación y reincidencia propia de cada lista — dos referencias suministradas, carga explícita, vea §11b), limitación de tasa (cubeta de fichas, reglas por carpeta y por IP/red, vea §11c), lista de bloqueo (CIDR + caducidad), reputación/escalada, importación de un script WAF `mod_magnet` de Lighttpd existente como refuerzo opcional tipo « magnet » (sin reescribirlo, extra `pip install -e ".[magnet]"` — aditivo, nunca puede levantar un bloqueo nativo; comprobación de compatibilidad en el momento de la importación, pantalla TUI dedicada) — modo `log-only` estructuralmente incapaz de bloquear |
| TLS | Directo (autofirmado, CA local, o público mediante Let's Encrypt/Certbot con renovación automática — vea §9), nunca mTLS/OCSP en la V1 |
| Autenticación | HTTP Basic por zona (`url_prefix`), `hashlib.scrypt` con defensa contra ataques de tiempo (tiempo constante incluso para un usuario desconocido) |
| FastCGI/PHP-FPM | Un único `(url_prefix, script_root)`, `script_root` confinado fuera de `webroot/` por construcción (el manejador estático nunca puede divulgar código fuente PHP) |
| Reverse proxy saliente | Omega-serv actúa él mismo como proxy hacia uno o varios backends (sentido inverso de `server.tls.mode = "behind_proxy"`) — reparto de carga (round-robin, ponderado, least-connections, ip-hash, least-response-time, carga real), afinidad de sesión y reglas de enrutamiento por cabecera, salud pasiva y activa, caché de respuestas (multivariante `Vary`), backpressure, protección contra bucles, API de administración en caliente — vea §7a para el detalle completo |
| Upload | Zonas confinadas, cuotas por zona, nombres de archivo generados en el servidor — sin streaming en la V1 (limitado por `server.max_request_size`) |
| `active_defense` | Deception + modo guerra a partir de las señales WAF ya calculadas (nunca una segunda puntuación): señuelos estáticos, ralentización/registro enriquecido/limitación de tasa dirigidos, incidentes + exportación IoC — vea §11 |

### 7a. Reverse proxy saliente — detalle

OMEGA-SERV puede actuar él mismo como reverse proxy hacia uno o varios backends HTTP/HTTPS — no confundir nunca con `server.tls.mode = "behind_proxy"` (OMEGA-SERV **detrás** de un proxy, mecanismo inverso). Zonas configurables con CRUD completo (TUI: *Configuración detallada → Reverse Proxy*), uno o varios upstreams por zona.

- **Reparto de carga** — `round_robin` (por defecto), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (ponderados), `least_connections`, `least_response_time`, `real_load` (carga real). Modo `real_load` nativo (sonda `/.omega-serv-load/`, reutiliza la misma lectura de `psutil` que la pantalla « Estado y recursos », nunca una segunda llamada) o declarativo (sonda HTTP de terceros, formato mínimo `{"load_percent": ...}` o número simple) — granularidad por upstream, una misma zona puede mezclar ambos.
- **Afinidad de sesión y enrutamiento condicional** — cookie sticky opaca (nunca expone al cliente el host:puerto real) y reglas por cabecera (igualdad o prefijo), ambas filtradas por la elegibilidad del upstream objetivo (vuelven limpiamente a la estrategia activa si el upstream elegido no está disponible).
- **Salud** — pasiva (fallos/éxitos consecutivos, umbrales de cambio down/up distintos para limitar el flapping) **y** activa (sonda periódica independiente del tráfico real, opcional por upstream, reutiliza el mismo mecanismo de tarea en segundo plano que la carga real). Estados `DOWN` (siempre automático), `DRAINING`/`MAINTENANCE` (siempre manuales, explícitamente efímeros, nunca persistidos) — un upstream activado manualmente queda excluido de las nuevas elecciones sin interrumpir nunca una conexión ya establecida. Reintento automático en otro upstream, solo para los métodos idempotentes (GET/HEAD/OPTIONS) y solo ante un error de conexión.
- **Backpressure** — límite de conexiones activas configurable por upstream; un upstream saturado rechaza limpiamente con un 503, distinto de un upstream averiado (502, que se reintenta igualmente).
- **Caché de respuestas** — solo GET/HEAD, nunca una respuesta de error, nunca `Set-Cookie` salvo activación explícita por zona; respeta `Cache-Control`/`Vary` del upstream (opción desactivable pero peligrosa, misma filosofía que la verificación TLS). Varias variantes de un mismo recurso (`Vary`) coexisten realmente en disco, nunca un simple « el último gana ». Bloqueo anti-stampede (una única petición concurrente reconstruye realmente la caché). Cabecera de diagnóstico `X-Omega-Cache: HIT`/`MISS`/`BYPASS` en cada respuesta. Supervisión/purga en una pantalla TUI dedicada (*Caché del reverse proxy*).
- **Protección contra bucles** — cabeceras hop-by-hop retiradas, `X-Forwarded-*` siempre sobrescritas (nunca fusionadas con las del cliente), contador `X-Omega-Proxy-Hops` incrementado en cada salto (rechazo limpio más allá de 5 saltos — detecta un bucle indirecto entre dos instancias, que una simple validación de la configuración local nunca puede ver).
- **WebSocket** — upgrade permitido por zona, un único upstream fijado durante toda la vida del túnel una vez establecido, sin timeout de aplicación.
- **Administración en caliente** — pequeña API HTTP local (`/.omega-serv-admin/`, protegida por `trusted_proxy` como la sonda de carga nativa) que permite a la TUI leer/forzar el estado DRAINING/MAINTENANCE de un backend y leer la proporción hits/miss de la caché **del servidor realmente en ejecución** (pantalla dedicada *Estado en directo de los backends*) — al ser la TUI y el servidor dos procesos separados sin memoria compartida, este canal HTTP local es el único puente entre ambos.

## 8. Endurecimiento HTTP (no desactivable)

- Cabecera/línea de petición limitadas **durante** la lectura (nunca después), plegado de cabeceras obsoleto rechazado, `Transfer-Encoding` siempre rechazado (nunca adivinado).
- `Content-Length` duplicado rechazado; `Expect: 100-continue` rechazado limpiamente (417).
- Lista blanca explícita de métodos (405 + `Allow` en caso contrario), cabecera `Host` validada (ausente/vacía/duplicada-aunque-idéntica/carácter de control → 400).
- Cabeceras de seguridad y CSP de base (`enforce`/`report-only`) aplicadas a **toda** respuesta, incluidos los errores — imposibles de eludir mediante una opción. `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` siempre `same-origin`, sin riesgo real de romper un sitio. `Cross-Origin-Embedder-Policy` siempre emitida explícitamente (nunca ausente — un escáner externo distingue « no considerada » de « permisiva por elección »), por defecto `unsafe-none` en **todos** los perfiles, incluido `hardened`: a diferencia de las dos anteriores, `require-corp`/`credentialless` pueden bloquear recursos cross-origin (fuentes, imágenes, iframes de terceros) propios del sitio realmente servido — ajustable (`security.coep_mode`). Zonas CSP (`security.csp_zones`): excepciones **explícitas** por prefijo de ruta (p. ej. `unsafe-inline` solo bajo `/una-carpeta/` que realmente lo necesita), cada una sustituye por completo la política por defecto para su prefijo — nunca una fusión, nunca una relajación global; toda excepción sigue siendo visible en `audit security` (CSP-001/CSP-002 también analizan las zonas), aunque sea deliberada. Creación guiada por un asistente directiva por directiva (pantalla **Seguridad genérica**), cada campo rellenado previamente con el valor **actual** de la política global — para modificar solo lo que deba cambiar en lugar de partir de un campo vacío que sacrificaría las demás directivas sin querer; se pide una confirmación explícita adicional si la zona resultante relaja `unsafe-inline`/`unsafe-eval`/una fuente genérica `*`.
- Direcciones IPv4 mapeadas en IPv6 (`::ffff:x.x.x.x`) normalizadas antes de cualquier comparación (lista de bloqueo, proxy de confianza, limitación de tasa) — de lo contrario, elusión conocida.
- Verificado mediante pruebas basadas en propiedades (`hypothesis`, miles de ejemplos generados) contra el parser HTTP y el resolvedor de rutas, además de las pruebas unitarias/de integración clásicas.

## 9. TLS

### 9a. Certificado autofirmado (mínimo)

Cubre el uso realista local/laboratorio/VPN (Tailscale...): un único listener, `ssl.SSLContext` directo, RSA 2048/4096 o ECDSA P-256/P-384.

### 9b. CA local

Para varios dispositivos cliente que deben confiar sin volver a importar un certificado individualmente: una autoridad de certificación local firma tantos certificados de servidor como sea necesario.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - el elemento más sensible del proyecto
├── root-ca.pem    # 0644 - a importar en el almacén de confianza de los clientes
├── serial.txt     # 0600 - seguimiento del siguiente número de serie
└── index.txt      # 0600 - seguimiento del estado V(álido)/R(evocado) por certificado firmado
```

Flujo: `certs generate-ca` (frase de contraseña de la clave de la CA **obligatoria**, introducción interactiva con doble confirmación si se omite `--password`) → `certs generate-csr` (clave + CSR del servidor) → `certs sign-csr` (firma con la CA, copia el SAN de la CSR, construye `fullchain.pem` si se solicita) → apuntar `tls.certificate.certificate_path` a ese `fullchain.pem`. Un certificado comprometido se retira con `certs revoke` (marca `index.txt`, comprueba primero que el certificado procede realmente de esta CA — se niega en caso contrario). Sin distribución de CRL en la V1, ni CA externa/CSR para una autoridad de terceros, ni mTLS (vea §15).

### 9c. Let's Encrypt / ACME (Certbot) — público, autoalojado

Para un sitio realmente público con un certificado reconocido por los navegadores, esquema autoalojado completo: DDNS (Dynu o equivalente, enteramente a cargo del operador) → Certbot → Omega-serv. Solo asistente TUI (`Configuración detallada → TLS → Asistente Let's Encrypt`) — invoca `certbot certonly --webroot` como subproceso (**nunca** `--standalone`, el puerto 80 ya está ocupado por Omega-serv; **nunca** un cliente ACME reimplementado) con `--config-dir`/`--work-dir`/`--logs-dir` apuntando a `secure/certificates/letsencrypt/` del proyecto — **nunca** `/etc/letsencrypt/` — lo que hace que el propio Certbot funcione totalmente sin privilegios. El certificado obtenido se importa automáticamente (mismo mecanismo que `certs import`, vea los ejemplos CLI anteriores) y se escribe un script de hook de renovación. Modo prueba (staging) marcado por defecto — desmárquelo una vez verificado que el dominio/webroot funcionan, para evitar los límites de tasa reales de Let's Encrypt.

Requisitos previos completamente fuera del alcance de Omega-serv: un dominio que apunte a la IP pública (DDNS), y los puertos 80/443 redirigidos a esta máquina.

### 9d. Renovación automática (Certbot)

`Configuración detallada → TLS → Renovación automática` se adapta al gestor de servicios realmente detectado **para esta instancia** (nunca un mecanismo compartido entre varias instancias multi-instancia): systemd → genera e instala un temporizador (`<servicio>-certbot-renew.timer`, dos veces al día + retardo aleatorio, `certbot renew` limitado al `--config-dir` de la instancia); si no → línea de crontab (usuario actual, sin privilegios) si `crontab` está disponible; si no → instrucciones manuales mostradas, sin escritura forzada. En algunas distribuciones (entre ellas Arch/Manjaro), el paquete Certbot no instala **ningún** temporizador por defecto, a diferencia de Debian/Ubuntu — de ahí esta pantalla en lugar de una simple comprobación de un mecanismo que se supone presente. Una vez configurada, la renovación vuelve a importar automáticamente cada certificado renovado (`certs import`) y luego reinicia el servicio, sin ninguna intervención manual más.

## 10. Auditoría de seguridad

`audit security` es **no bloqueante**: vuelve a ejecutar las barreras ya bloqueantes de `config check` como `CRITICAL`, y después aplica reglas consultivas (TLS, CSP, métodos peligrosos, timeouts, higiene de las subidas, de forma pura; permisos de archivos, caducidad de certificados, unidad systemd instalada, tamaño de los logs con E/S real). `WAF-001` (WAF que se ha quedado en `log-only`) se observa a lo largo del tiempo mediante un pequeño archivo de estado (`var/run/waf-mode-state.json`) — solo se activa tras ≥14 días observados en `log-only` en ejecuciones repetidas, no en la primera `audit`.

## 11. Active Defense (deception + modo guerra)

Módulo opcional (`option enable active_defense`, desactivado por defecto) que califica un comportamiento hostil a partir de las señales WAF ya calculadas (`WafDecision`/reputación/lista de bloqueo — nunca un segundo cálculo de puntuación independiente), y puede desviar una fuente hacia un señuelo, ralentizar sus respuestas y registrarla con más detalle, construir un incidente aprovechable y después exportar indicadores de compromiso (IoC). Nunca bloquea el tráfico por sí mismo — el bloqueo de red sigue siendo competencia de `omega-fire`; Active Defense observa, desvía, ralentiza y registra.

**Amenazas y puntuación**: cada fuente (`IP + hash SHA-256 del User-Agent`) acumula una puntuación (`WAF-001` bloqueante +10, escalada de reputación +25, baneo conocido +25, POST sobre un señuelo ya asignado +30 — decremento de -5 cada 15 minutos sin un nuevo evento) calificada como `normal`/`suspicious`/`hostile`/`contained` (`contained` exige además un baneo ya conocido). `mode: monitor` observa sin actuar; `mode: enforce` aplica realmente las acciones siguientes.

**Modo guerra** (`options.active_defense.settings.war_mode`): un `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) desencadenado por umbrales configurables, para toda fuente que no sea `normal`:
- `enrich_log` — registro JSONL separado (`var/log/active-defense-enriched.jsonl`, nunca mezclado con el log WAF/de producción), cabeceras ocultadas, cuerpo HTTP con hash (SHA-256) o truncado según `logging.capture_request_body`.
- `delay` — ralentización acotada y con jitter (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), nunca un bloqueo del bucle asyncio.
- `rate_limit` — limitación de tasa dedicada por fuente (`war_mode.rate_limit.requests`/`window_seconds`), reutiliza el mismo mecanismo que el WAF con una clave distinta.
- `create_incident` — apertura/fusión automática de un incidente al superar `thresholds.incident_score`.

**Deception**: una fuente `hostile`/`contained` puede asignarse a un señuelo estático (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — respuestas plausibles pero siempre fijas, nunca una lectura real de archivos ni un subproceso) elegido según la clase de ataque observada (`deception.profiles.<nombre>.match_attack_classes`, una o varias entre `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Dos niveles de aislamiento, asumidos y documentados como tales:
- **Nivel 1** (fixture en el proceso, `isolation_level: "fixture"`, por defecto) — aislamiento DÉBIL explícito: mismo proceso, mismo usuario del sistema que la producción, aceptable solo porque la fixture nunca hace otra cosa que devolver una plantilla estática. El NOMBRE del perfil debe coincidir exactamente con una de las 4 fixtures anteriores — si no, se rechaza en la validación (`validate_active_defense_config`), para evitar la trampa de un señuelo mal nombrado que entonces nunca se activaría, en silencio.
- **Nivel 2** (backend realmente aislado, `isolation_level: "proxy"`) — reenviado a un proceso separado mediante `options.active_defense.settings.deception.decoy_zones.<nombre>` (upstream `host`/`port` de un servidor ya en ejecución, nunca creado automáticamente; nunca leído desde `options.reverse_proxy` — un señuelo nunca puede apuntar por accidente a una zona de producción, comprobado por `config check`), reutilizando el mismo mecanismo de reverse proxy saliente que la producción (`serve_proxy()` — upstream inalcanzable en el momento de una petición real: 502 devuelto al atacante, nunca un fallo del servidor).

**Pantalla Ajustes** (TUI, Seguridad activa → Active Defense → Ajustes): configuración completa de todo lo anterior — modo, activación del modo guerra, alcance/acciones/umbrales/ralentización/límite de peticiones, deception (comportamiento por defecto, CRUD de perfiles de señuelo y de zonas de señuelo con valores de ejemplo mostrados en cada campo), IoC, almacenamiento y registro — validada por las mismas reglas que la CLI antes de cualquier guardado, sin necesidad nunca de editar a mano `config/omega-serve.json`. Siempre se requiere un reinicio completo tras cualquier cambio (Active Defense nunca se recarga en caliente).

**Incidentes e IoC**: cronología completa por incidente, extracción de indicadores (IP, User-Agent con hash), exportación JSON versionada/CSV limitada a los IoC compartibles/informe Markdown, y formatos de intercambio **STIX 2.1** (bundle para cargar en OpenCTI, un SIEM…) y **MISP** (evento para importar desde la interfaz de MISP), marcados TLP:AMBER por defecto — archivos locales, nunca enviados; cada exportación va acompañada de un archivo `<export>.sha256` (formato `sha256sum` estándar). Exportación automática al cerrar un incidente si `ioc.auto_export_on_close` (verdadero por defecto). Los estados caducados y el registro de auditoría se purgan automáticamente y la base está limitada (protección contra el llenado del disco); `active-defense purge` además cierra los incidentes que han vuelto a quedar en silencio.

**Simulación**: `active-defense simulate` (CLI) y el botón "Simular" (TUI, pantalla Seguridad activa) proyectan la puntuación/nivel y explican cada acción que se desencadenaría — dry-run estricto, ninguna escritura real, ningún impacto en la red.

Copia de seguridad/restauración: `config backup --include-active-defense` incluye la base sqlite (amenazas/incidentes/asignaciones) en el archivo — nunca un secreto en claro, por lo que no se requiere `--confirm-secrets`, a diferencia de `--include-auth`.

## 11b. Listas de rutas sensibles (WAF)

El WAF puede cargar **listas editables** en archivo de texto, una ruta (o palabra clave) por línea, desde **Seguridad activa → Custom → Añadir → « CARGAR una lista »**. Nunca se carga nada por defecto: es una acción explícita.

- **Referencias suministradas**: `sensitive-paths-hostile` (298 rutas sin uso legítimo: secretos, copias de seguridad, VCS, consolas…) y `sensitive-paths-probe` (132 rutas de sondeo, a veces servidas por un sitio real: `/admin`, `/api`, supervisión…). Al cargarla, se crea una **copia local** en `secure/waf/rules/keywords/`: es la que usted modifica, y una actualización de omega-serv nunca la sobrescribe (« Novedades de la referencia » propone después, casilla por casilla, las nuevas entradas).
- **Sintaxis**: `/admin` (→ `/admin` y `/admin/xxx`, nunca `/administrator`), `/.git/` (todo lo que hay debajo), `/*.bak` (extensión), `!/api/v1` (excepción, siempre prioritaria). Rutas decodificadas como en el motor (`%2e`, doble codificación, caracteres de ancho completo).
- **Gravedad**: *Observación* (solo registro, aconsejado en la primera carga), después Media (nunca bloquea por sí sola) o Alta (403 desde el primer acceso).
- **Reincidencia propia de cada lista**: 1.er acceso = información o rechazo; N accesos en M minutos = baneo de aplicación temporal (respuesta 451, incluso a través de Tailscale); bloqueos repetidos = baneo de red por omega-jail. Referencias: hostile 2 accesos en 10 min → 24 h, sondeo 5 en 10 min → 1 h.
- **Nunca un baneo automático** para el host local, Tailscale (`100.64.0.0/10`) y la red local (`options.waf.reputation.never_auto_block`): solo el tráfico externo puede ser baneado. Detrás de un proxy local, la exención de `127.0.0.1` exige `trusted_proxy` activo. `X-Forwarded-For` se lee de derecha a izquierda: un cliente no puede declararse local.
- **Salvaguardas**: rutas vitales protegidas (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), rechazo de una lista bloqueante que afectaría a una ruta realmente servida (alias, reverse proxy, zona Auth, webroot), **« Comprobar con mis logs »** en el editor (líneas que habrían afectado a peticiones correctas, excepción en un clic).
- **Editor integrado**: diagnósticos en directo con número de línea, « Probar » una ruta, escritura segura (permisos y grupo conservados, enlaces simbólicos rechazados, modificación externa detectada), legibilidad por la cuenta del servicio verificada (« Corregir permisos »), y recarga **honesta**: rechazada con su motivo si la lista no supera la verificación, y el servidor conserva entonces sus reglas actuales.

## 11c. Límite de tasa por carpeta y por IP/red (WAF)

El límite de tasa del WAF (cubeta de fichas, `options.waf.rate_limit`, 60 peticiones / 60 s por IP por defecto) puede afinarse desde **Seguridad activa → Exclusiones y límite de tasa** (o a mano, `rate_limit.path_policies` / `rate_limit.source_policies`):

- **Regla por carpeta** (`prefix`, `requests`, `window_seconds`): **sustituye** al límite global para esa carpeta, con su propio contador (`requests: 0` = ilimitado). Gana el prefijo más largo; `/images` cubre `/images/a.png`, nunca `/images2`. Típicamente una página pesada (galería de imágenes) que devuelve 429.
- **Regla por IP/red** (`network`, `requests`, `window_seconds`, `trusted`): mismo principio; gana la red más precisa. Prioridad: carpeta, luego IP/red, luego el límite global.
- **Baneo sin cambios para el público**: un exceso de una IP pública sigue registrándose `"action": "block"` en `waf-alerts.log`, por lo que omega-jail puede banearla (3 rechazos en 10 min → 12 h). Una **fuente segura** — red `never_auto_block` o regla marcada `trusted: true` — sigue recibiendo el 429 pero se registra `"action": "throttle"`, que la jail nunca cuenta.
- **Script magnet**: su propio límite de tasa (respuesta 429) nunca cuenta como una detección, así que nunca lleva al auto-baneo; en una petición cubierta por una regla de carpeta o de IP/red, prevalece la regla nativa y se ignora el 429 de magnet (sus firmas de ataque siguen aplicándose).
- Una regla de tasa **nunca** desactiva la inspección del WAF; a la inversa, una exclusión de inspección (`exclusions.path_prefixes`) nunca levanta el límite de tasa. Sin `trusted_proxy` activo, se ignora una regla que cubra `127.0.0.1`/`::1` (la misma salvaguarda que `never_auto_block`).

## 12. Servicios y explotación

Detección automática de systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). La unidad systemd generada aplica por defecto un endurecimiento no negociable: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` limitado a `var/`, usuario/grupo dedicados obligatorios, `UMask=0077`, `Restart=on-failure`. Parada limpia con SIGTERM (drenaje de las conexiones en curso, periodo de gracia configurable y después cierre forzado); recarga en caliente con SIGHUP (solo reglas WAF y zonas Auth — bind/puerto/TLS y Active Defense nunca modificables sin un reinicio completo).

## 13. Registros

`var/log/access.log` (formato Apache combined + `request_id`, escapado contra la inyección en los logs), `var/log/error.log`. Rotación por tamaño/número de archivos conservados (`logs.rotation`). WAF nativo: `var/log/waf-alerts.log` (`options.waf.logging.path`). Script magnet (§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, por defecto `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — añadidos de oficio a la Biblioteca (botón *Añadir los logs conocidos de Omega-Serv*) solo si magnet está activo; `lnav`, en cambio, siempre los propone (un archivo ausente simplemente se ignora al lanzarlo).

### 13a. Fuentes remotas (SSH)

Centraliza, a petición explícita, el log de un servidor backend situado en la misma red local detrás del reverse proxy (pantalla **Gestión de logs → Biblioteca → Fuentes remotas (SSH)**). Un « fetch » es una acción manual y puntual, nunca un flujo en directo ni un sondeo automático: se recupera una **copia** mediante `scp` en el momento de hacer clic en *Recuperar ahora*, se escribe bajo `var/log/remote/` y después se añade a la Biblioteca como un log normal (columna *Acceso* = `ssh`, columna *Modificado* = fecha de **esta** recuperación — nunca la del archivo remoto); una nueva recuperación simplemente sustituye la copia anterior por una más reciente.

Salvaguardas deliberadas (vea `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` para el estudio completo): ningún escaneo de red automático, ninguna conexión sin configuración explícita (etiqueta/host/ruta remota, usuario/puerto/clave privada opcionales — vacíos, dejan que `ssh`/`~/.ssh/config` decidan como si el comando se escribiera a mano), ninguna contraseña pedida ni almacenada nunca (una clave privada solo se referencia por su ruta, nunca la lee ni la almacena Omega-serv), ninguna comprobación de tamaño antes de la transferencia. Capacidad `scp` detectada localmente en el **Registro de capacidades** (solo presencia del binario, nunca una prueba de accesibilidad de un host); Samba dejado de lado explícitamente (YAGNI, mientras no se confirme una necesidad real).

## 14. Pruebas

```bash
source .venv/bin/activate
lint-imports        # verifica los 8 contratos de capas
pytest -q           # 2485 pruebas
ruff check .
mypy src
```

Estructura: `tests/unit/` (dominio/aplicación, dobles de prueba), `tests/integration/` (servidor asyncio real sobre sockets TCP reales, `openssl` real como subproceso, comandos CLI reales contra un proyecto temporal completo, interfaz interactiva mediante la API `Pilot` de Textual - nunca una captura de pantalla), `tests/security/` (pruebas basadas en propiedades `hypothesis` sobre el parser HTTP y el resolvedor de rutas).

## 15. Fuera del alcance

- CGI en bruto (solo FastCGI/PHP-FPM)
- mTLS (autenticación de cliente por certificado), OCSP stapling
- CA externa / CSR para una autoridad de terceros, distribución completa de CRL
- Active Defense: integración real con los eventos de baneo de `omega-fire` (bloqueada del lado de `omega-fire`, que hoy no expone ninguna superficie de lectura)

---

> 🔒 OMEGA-SERV — Un servidor web sólido, completo, seguro y defensivo.

<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Servidor web HTTP autonomo, portable y reforzado por defecto**

> Desarrollado por **kraynux** para **Omega-server**
[https://kraynux.snake-mackarel.ts.net](https://kraynux.snake-mackarel.ts.net)

Página oficial: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/) &nbsp; Wiki y FAQ: [Guía de uso](https://kraynux.snake-mackarel.ts.net/omega-serv/guide.html) &nbsp; Vista previa : [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-uso)

**Idiomas:**
[Français](README.md) · [English](README.en.md) · [Español](README.es.md) · [Русский](README.ru.md) · [中文](README.zh-CN.md)

---

**Omega-serv** es un servidor HTTP/1.1 escrito en Python puro (solo biblioteca estandar para el nucleo del servidor), pensado para servir contenido estatico y, opcionalmente, PHP-FPM, con un endurecimiento de protocolo no desactivable y modulos de seguridad (WAF, TLS, autenticacion) superpuestos en lugar de impuestos. Septima herramienta de la suite `omega-`, pero deliberadamente **fuera de la futura integracion `omega-suite`** (actua sobre la maquina local que lo aloja, no sobre objetivos remotos — misma familia que `omega-fire`); estructurado en Clean Architecture, con `bootstrap/` como raiz de composicion.

## 1. Vision y alcance

La prioridad declarada es la **solidez/seguridad del nucleo HTTP primero** — WAF y TLS son modulos opcionales superpuestos, nunca requisitos previos. Un servidor que hace una sola cosa (servir archivos, opcionalmente PHP) pero la hace correctamente, con un endurecimiento de protocolo real e infranqueable, en lugar de un servidor que hace muchas cosas a medias.

### Lo que hace Omega-serv

- Sirve contenido estatico (archivos, listado de directorio opcional, alias, redirecciones, reescrituras, cache) con resolucion de rutas segura (traversal, doble codificacion, enlaces simbolicos).
- Endurece el protocolo HTTP por defecto, sin opcion para desactivarlo: metodos permitidos explicitos, validacion de la cabecera `Host`, rechazo de la ambiguedad `Content-Length`/`Transfer-Encoding`, cabeceras de seguridad y CSP basica no evitables.
- Opcionalmente: filtrado WAF (firmas, limitacion de tasa, lista de bloqueo), TLS directo (certificado autofirmado, firmado por una CA local, o publico via Let's Encrypt/Certbot con renovacion automatica — vease §9), autenticacion HTTP Basic por zona, PHP via FastCGI/PHP-FPM, zonas de subida confinadas.
- Audita su propia configuracion (`audit security`) y se instala como servicio del sistema (systemd/OpenRC/runit).
- CLI no interactiva totalmente scriptable, **y una interfaz interactiva (Textual)** que reviste exactamente los mismos casos de uso — vease §3. La hoja de ruta de la interfaz (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) esta **completamente entregada**: registro de capacidades, perfiles/opciones, configuracion detallada (alias/redirecciones/reescrituras/FastCGI/listado de directorio/autenticacion/cache/WAF/proxies de confianza/proxy inverso saliente/TLS), gestion de logs (ver/seguir/lnav/rotacion/copia de seguridad/automatizacion/estadisticas/top IPs), servicio del sistema, multi-instancia (registro, creacion), verificacion/simulacion/auditoria, copia de seguridad/restauracion de la configuracion, asistente de primer arranque, ajustes de la aplicacion (tema, perfil de renderizado, rutas de exportacion/capturas), guia de ayuda contextual (ficha por pantalla con ejemplos concretos, FAQ, exportacion HTML, cobertura exhaustiva verificada por prueba), indicacion sistematica de recarga/reinicio tras cada guardado, configuracion integral de Active Defense sin edicion manual de archivo.

### Lo que Omega-serv no hace

- CGI puro (retirado del alcance V1 — solo se admite FastCGI/PHP-FPM).
- Autenticacion mutua TLS (mTLS), OCSP stapling — fuera de alcance en V1, vease §15. (ACME/Let's Encrypt via Certbot esta disponible, vease §9c/9d.)
- Cache HTTP compartida entre procesos.
- Escaneo/auditoria de un objetivo remoto (vease `omega-check`/`omega-scan`/`omega-deep` para eso — Omega-serv solo se audita a si mismo, nunca a un tercero).

### Advertencia de uso

Omega-serv **se niega a arrancar como root**. Ningun modulo de seguridad (WAF, TLS, autenticacion) esta activado por defecto en ningun perfil suministrado, incluido `hardened` — activarlos siempre es un gesto explicito (`config enable-tls`, `option enable waf`...). El propio perfil `hardened` recomienda un proxy inverso para una exposicion real a Internet en lugar de sustituirlo.

## 2. Instalacion

### Requisitos previos

- Python 3.10+
- `openssl` (el binario, no una biblioteca Python) para todo lo relacionado con certificados TLS — el resto de funciones funcionan sin el.

### Instalacion

```bash
[ -d omega-serv ] && echo "ℹ️ Ya extraido aqui, paso omitido." || tar -xzf omega-serv.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Crea el entorno virtual `.venv` si no existe todavia.
2. Instala el paquete (`pip install -e .`) — **ninguna dependencia externa** (vease §6).
3. Hace ejecutables `omega-serv.sh` e `install.sh`.
4. Añade el alias `serv` a `~/.bashrc` y `~/.zshrc` (sin duplicado si ya esta presente).

### Actualización

Si `omega-serv/` ya existe (instalación anterior), **nunca ejecutes `tar` desde el interior de esa carpeta**: intentaría crear un `omega-serv/omega-serv/` anidado y fallaría. A diferencia de omega-fire, `install.sh` nunca toca los permisos de la carpeta aquí (ningún paso usa `sudo`) — así que no hay riesgo de una carpeta propiedad de `root`, extraer directamente sobre la instalación existente es seguro.

```bash
# Desde la carpeta PADRE de omega-serv/ (nunca desde su interior)
tar -xzf omega-serv.tar.gz
cd omega-serv/
./install.sh
```

El archivo excluye deliberadamente todo el estado vivo (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — el sitio realmente servido**...) — extraer sobre una instalación existente nunca toca tus datos, certificados, ajustes o contenido servido, solo se reemplaza el código de la aplicación. `install.sh` reutiliza el `.venv` existente y simplemente reinstala las dependencias en él.

### Dependencias

El nucleo del servidor (parser HTTP/1.1, cliente FastCGI, hash de contraseñas via `hashlib.scrypt`) permanece en Python puro/stdlib, y todo lo que toca certificados TLS pasa por el binario `openssl` como subproceso en lugar de una biblioteca criptografica de Python — **ninguna dependencia externa para eso**. Solo la interfaz interactiva (§3) introduce alguna: `omega-lib` (temas, deteccion de terminal — biblioteca compartida de la suite, no publicada en PyPI, empaquetada en el archivo distribuible), `textual` y `pyte` (emulacion de terminal para el renderizado de `lnav` fusionado en la interfaz), `jinja2` (exportaciones HTML tematizadas) y `psutil` (pantalla Estado y Recursos — CPU/RAM/disco/red). Dependencia opcional de desarrollo/pruebas (`pip install -e ".[test]"`): `hypothesis` (pruebas basadas en propiedades del parser HTTP y del resolvedor de rutas, nunca en produccion). Herramientas de calidad (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`.

### Herramientas opcionales recomendadas

La interfaz funciona en modo degradado si estas herramientas estan ausentes:

- `openssl` — necesario para todo lo relacionado con certificados TLS (autofirmado, CA local, importacion); sin el, los comandos `certs *` fallan pero el resto del servidor funciona normalmente (vease §9).
- `certbot` — necesario solo para el asistente **Let's Encrypt** y su renovacion automatica (§9c/9d); TLS autofirmado/CA local nunca lo requiere.
- `lnav` — analisis avanzado de logs fusionado en la pantalla **Gestion de logs** (§3); mensaje de error claro y explicito si el ejecutable no se encuentra, sin caida, el resto de la pantalla (ver/seguir/rotacion/estadisticas) funciona normalmente sin el.
- `python-psutil` (paquete del sistema equivalente al `psutil` de PyPI) — instalado automaticamente por `pip install -e .` en todos los casos (dependencia obligatoria del paquete, la pantalla **Estado y Recursos** siempre lo necesita), pero preinstalarlo via el gestor del sistema evita que `pip` tenga que compilar su wheel localmente.

```bash
# Arch Linux y derivadas (Manjaro...)
sudo pacman -S openssl certbot lnav python-psutil

# Debian/Ubuntu y derivadas
sudo apt install openssl certbot lnav python3-psutil

# Fedora
sudo dnf install openssl certbot lnav python3-psutil
```

## 3. Uso

Dos interfaces estrictamente equivalentes funcionalmente, nunca logica duplicada entre ambas: CLI no interactiva (scriptable, usada a continuacion) e interfaz interactiva Textual (menus, formularios, tablas) — cada accion de una existe en el lado de la CLI, la interfaz solo reviste los mismos casos de uso.

### Modo interactivo (TUI)

Recomendado para el uso diario — lanzado sin argumentos:

```bash
./omega-serv.sh
```
si creaste el alias, simplemente escribe `serv` en la terminal:
```bash
serv
```

### Recorrido general

Pantalla de inicio (splash, se cierra con una tecla o un clic) → menu principal (Asistente de primer arranque / Registro de capacidades / Perfiles / Configuracion detallada / Active Sécurité / Gestion de logs / Servicio / Multi-instancia / Estado y Recursos / Auditoria / Copia de seguridad) → seleccion de una seccion y luego de una accion, cada formulario valida sus campos requeridos antes de continuar → confirmacion explicita antes de cualquier operacion sensible o destructiva (reinicio, eliminacion, restauracion...) → indicacion sistematica de lo que sigue (recarga en caliente automatica, o confirmacion de reinicio completo) tras cualquier guardado que modifique una configuracion ya servida. La adaptacion al terminal (colores, tamaño, degradacion estructural del perfil de renderizado) es automatica y sin flag manual — vease §4.

#### Atajos de teclado (interfaz interactiva)

| Tecla | Accion |
|---|---|
| `↑` / `↓` | Navegar entre los elementos de una pantalla |
| `Tab` / `Mayus+Tab` | Navegar entre los campos de un formulario |
| `Esc` | Volver a la pantalla anterior (confirmacion de salida en la pantalla de inicio) |
| `t` | Siguiente tema (aplicado inmediatamente, sin confirmacion) |
| `r` | Actualizar la deteccion del terminal |
| `F1` | Ayuda de la pantalla actual (ficha contextual — vease "Guia de ayuda" a continuacion) |
| `a` | Guia de ayuda completa (menu navegable + FAQ) |
| `o` | Ajustes de la aplicacion (tema, perfil de renderizado, rutas de exportacion/capturas — vease abajo) |
| `q` | Salir (con confirmacion) |
| `Ctrl+P` | Paleta de comandos (Tema, Captura de pantalla, Opciones...) |

#### Guia de ayuda (teclas `F1`/`a`)

Sistema de ayuda integrado, nunca un simple texto estatico: cada pantalla documentada (ficha definicion/campos a rellenar con ejemplos concretos/accion desencadenada/reaccion — recarga, reinicio o ninguna) es accesible directamente desde ella via `F1` ; la tecla `a` abre el menu completo (arbol identico a la navegacion real de la aplicacion) con acceso a la FAQ (trampas encontradas en uso real, ej. clases de ataque de Active Defense, permisos de servicio compartido) y una exportacion HTML autonoma (tema activo conservado) de la totalidad de la guia. Recurre a una pantalla de referencia generica mientras una ficha precisa aun no existe — cobertura actualmente exhaustiva, verificada por prueba.

#### Menu principal (interfaz interactiva)

- **Asistente de primer arranque** — recorrido guiado en 8 pasos (bienvenida → capacidades en solo lectura → eleccion de perfil → bind/puerto → TLS opcional → verificacion → resumen + escritura → propuesta de instalacion del servicio); permite generar una configuracion completa y poner en marcha el servidor sin conocer la CLI.
- **Registro de capacidades** — sonda del sistema en solo lectura (sistema de init, si el puerto configurado ya esta ocupado, presencia de `openssl`/`logrotate`/`tailscale`/`lnav`, espacio en disco, limite de descriptores...), exportacion JSON/HTML.
- **Perfiles** — mismo caso de uso que `profile` en la CLI (§5), siempre se muestra el diff antes de escribir.
- **Configuracion detallada del servidor** — CRUD completo sobre alias/redirecciones/reescrituras/listado de directorio/proxies de confianza/proxy inverso saliente/FastCGI/cache/autenticacion/control de acceso/paginas de error, ademas del submenu **TLS** (estado, generacion autofirmada, asistente de CA local, asistente Let's Encrypt/Certbot, renovacion automatica, revocacion, activar/desactivar — vease §9) ; un segundo marco, **OPCIONES Y VERIFICACION**, agrupa accesos directos a **Opciones** (`option` CLI, §7) y **Verificar la configuracion** (`config check` CLI, §10) — mismo recorrido que ajustar opciones y luego verificar, estas dos pantallas ya no son accesibles directamente desde el menu principal. El WAF ya no vive aqui (vease "Active Sécurité" mas abajo): expone sobre todo estado operacional que cambia continuamente, no un simple formulario de configuracion estatica. Cada guardado precisa sistematicamente lo que sigue: recarga en caliente automatica y silenciosa si hay un servicio activo (listado de directorio, acceso, alias/redirecciones/reescrituras, cache, paginas de error, proxies de confianza, zonas de proxy inverso/FastCGI, usuarios/zonas de autenticacion), o confirmacion explicita de reinicio completo cuando el cambio afecta al socket de escucha, TLS o Active Defense — ninguna pantalla deja ya adivinar si hay que relanzar el servidor.
- **Active Sécurité** — pantalla unica que agrupa dos bloques: **Active Defense** (Estado, Amenazas seguidas con puntuacion/nivel, Incidentes con cronologia/exportacion IoC/informe, asignaciones de Deception, Simular una decision en dry-run, **Ajustes** — configuracion integral sin editar jamas `config/omega-serve.json` a mano, vease §11) y **WAF** (Estado, Modulos — modo/paquetes de reglas/lista de bloqueo, Probar una peticion, Custom — creacion de regla personalizada) — vease §11.
- **Gestion de logs** — ver/seguir un archivo en vivo, `lnav` fusionado (renderizado real de terminal dentro de la interfaz), rotacion/archivado manual o automatico por umbral de tamaño, creacion de copia de seguridad inmediata, configuracion/gestion de automatizaciones planificadas (declarativo — vease la nota siguiente), restaurar/purgar un archivo, exportar la lista, estadisticas (top IPs, desglose por codigo de estado, histograma horario) con eliminacion de una IP del log de acceso.
- **Servicio** — mismas acciones que `service` en la CLI (§12), elevacion `sudo` puntual por accion, la aplicacion completa nunca se lanza como root.
- **Multi-instancia** — registro global (`~/.config/omega-serv/instances.json`, fuera de cualquier directorio de proyecto) de las instalaciones conocidas en esta maquina, con el estado systemd de cada una; creacion de una nueva instancia (copia del arbol, su propio entorno virtual y dependencias frescas, configuracion nueva con un puerto distinto, verificaciones de no-anidamiento y de conflicto de puerto) directamente desde la interfaz. El boton permanece invisible en la practica para una sola instalacion (la etiqueta "Multi-instancia" pasa a "Instancias (N)" a partir de 2 conocidas); el cambio completo hacia otra instancia tambien esta disponible (`os.execv`, confirmacion explicita, pantalla de bienvenida dedicada que anuncia el cambio al reiniciar); desinstalacion completa de una instancia (retira la unidad, la cuenta de sistema dedicada si ninguna otra instancia la usa ya, y opcionalmente el directorio, nunca por defecto).
- **Estado y Recursos** — vision de conjunto de un vistazo, actualizada cada 2 segundos: estado del servidor (proceso/PID, estado del servicio de sistema, perfil/opciones activas/TLS/puerto), flujo del log de acceso en vivo (rendimiento, desglose por codigo de estado, IPs unicas, tasa de error), recursos del sistema (CPU/RAM/disco/swap/carga/red, via `psutil`) ; agrupa tambien el acceso directo **Simular una peticion** (mismo caso de uso que el comando CLI correspondiente, §10).
- **Auditoria de seguridad** — mismo caso de uso que el comando CLI correspondiente (§10).
- **Copia de seguridad de la configuracion** — archivo tar.gz del archivo de configuracion y, mediante opcion explicita, de las reglas WAF/zonas de autenticacion/certificados (confirmacion obligatoria en cuanto se incluyen secretos reales)/base de Active Defense, restauracion, lista, eliminacion.

> Nota sobre las automatizaciones de rotacion planificadas: se registran (frecuencia + log objetivo) pero **nada las ejecuta automaticamente** — ni en la interfaz, ni como tarea en segundo plano. Es una eleccion deliberada de paridad con la pantalla equivalente de `omega-fire`, que tiene exactamente el mismo comportamiento declarativo. Una ejecucion periodica real (temporizador de systemd, tarea en segundo plano) seria un trabajo futuro separado, solo si se confirma la necesidad.

#### Ajustes de la aplicacion (tecla `o` o paleta de comandos)

Solo preferencias de interfaz — nunca confundidas con `config/omega-serve.json` (la configuracion propia del servidor): tema activo, perfil de renderizado (`complete`/`standard`/`reduced`/`mono`, requiere reinicio), ruta de exportacion (`var/exports/` por defecto), ruta de capturas de pantalla (`var/screenshots/` por defecto), purga de cualquiera de las dos carpetas (confirmacion obligatoria).

```bash
# Iniciar el servidor (primer plano, SIGTERM = apagado ordenado con periodo de gracia, SIGHUP = recarga en caliente WAF/Auth)
./omega-serv.sh serve

# Configuracion
./omega-serv.sh config init                # genera config/omega-serve.json (valores seguros por defecto)
./omega-serv.sh config check                # verifica sin arrancar (mismas puertas bloqueantes que al arrancar)
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

# Simular una peticion sin arrancar el servidor (util para validar una regla antes de activarla)
./omega-serv.sh simulate-request GET /index.html

# WAF (funciona aunque la opcion este desactivada, via --force implicito)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "escaneo detectado" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + modo guerra, opcion "active_defense" - vease §11)
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

# Certificados TLS - importacion (9c, ej. desde un hook de Certbot)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# Autenticacion HTTP Basic
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Auditoria de seguridad (nunca bloqueante, informativa)
./omega-serv.sh audit security --format text --min-severity medium

# Copia de seguridad de la configuracion (la config siempre se incluye;
# los secretos reales nunca se cifran por defecto, --confirm-secrets obligatorio para incluirlos)
./omega-serv.sh config backup --description "antes de la migracion"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "amenazas/incidentes"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Servicio del sistema (systemd/OpenRC/runit, deteccion automatica)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Codigos de salida notables

| Comando | Codigo | Significado |
|---|---:|---|
| `audit security` | `0` | Nada grave (ningun `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Al menos un hallazgo `CRITICAL` |
| `audit security` | `2` | Al menos un `HIGH` sin `CRITICAL` |
| `audit security` | `3` | Error de ejecucion (config no encontrada...) |
| `certs check-expiry` | `1` | Certificado expirado |
| cualquier otro comando | `0`/`1` | Exito / fallo de validacion |

## 4. Compatibilidad de terminales

La interfaz interactiva (Textual) detecta automaticamente las capacidades del terminal (emulador, tamaño) y adapta su hoja de estilo estructural en consecuencia (`complete`/`standard`/`reduced`/`mono`), sin necesidad de flag manual. El modo CLI permanece siempre en texto simple, independiente del terminal. Politica compartida por toda la suite `omega-` (`omega-lib`, `terminal/policies.py`) — identica a la de `omega-check`/`omega-fire`.

### Perfil segun el emulador detectado

| Emulador | Perfil inicial |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, SSH moderno | `reduced` |
| TTY Linux, SSH antiguo | `mono` |
| Emulador no reconocido | `reduced` (repliegue por defecto) |

### Perfil segun el tamaño del terminal

| Tamaño minimo (columnas × filas) | Techo de perfil |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| por debajo | `mono` |

El perfil final retenido es **el mas restrictivo de los dos** (emulador y tamaño) — un Ghostty en pantalla completa redimensionado a 70 columnas vuelve a `mono`, aunque su emulador permitiria `complete`. Actualizable en vivo con la tecla `r`, o sobrescribible manualmente desde los Ajustes de la aplicacion (tecla `o`, §3).

## 5. Perfiles

| Perfil | Uso previsto |
|---|---|
| `minimal` | Demostracion/local simple: solo estatico, ninguna opcion activada |
| `standard` | Sitio estatico o pequeña produccion: cabeceras habituales, CSP basica, dirlisting/CGI/FastCGI desactivados |
| `hardened` | Exposicion con minimo privilegio: bind local por defecto (proxy inverso recomendado para Internet), metodos limitados a GET/HEAD, CSP estricta, anti-slowloris — el WAF **nunca** se activa automaticamente, ni siquiera aqui |
| `development` | Solo desarrollo local, nunca presentado como apto para Internet: bind a loopback obligatorio, CSP en report-only, paginas de error detalladas |

Orden de fusion de la configuracion: valores seguros integrados → perfil seleccionado → opciones actualmente activas conservadas (sobreviven a un cambio de perfil) → overlay explicito del usuario. Siempre se muestra un diff completo antes de escribir (`profile apply`).

## 6. Arquitectura

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` es la raiz de composicion (equivalente al `app/` de las demas herramientas de la suite). Particularidad asumida de este proyecto, verificada por `import-linter` en lugar de supuesta: `application/server/start_server.py` (y `validate_config.py`, `run_audit.py`) actuan como **fabricas de construccion dependientes de la configuracion real** (que gestor de servicio, activar o no el WAF...) e instancian adaptadores `infrastructure/` concretos directamente — a diferencia del patron mas estricto de CHECK/TRACK donde `application/` solo consume `ports/`. La unica regla universal realmente impuesta: `domain/`/`core/` nunca dependen de las capas externas.

```text
src/omega_serv/
├── core/            Vocabulario transversal (platform_info, constantes)
├── domain/           Logica de negocio pura (HTTP, config, seguridad WAF/TLS/auth/audit, enrutamiento)
├── ports/            Contratos (Protocol) esperados por la aplicacion
├── application/      Casos de uso - algunas funciones (build_server...) tambien componen adaptadores concretos (vease arriba)
├── infrastructure/    Implementaciones reales (asyncio, openssl como subproceso, systemd/OpenRC/runit, archivos)
├── interfaces/cli/    CLI argparse no interactiva
├── interfaces/tui/    Interfaz interactiva Textual (mismos casos de uso, nunca logica duplicada)
└── bootstrap/         DependencyContainer, resolucion de la raiz del proyecto
```

Reglas verificadas por `import-linter` (7 contratos): `domain`/`core` nunca dependientes de las capas externas; `interfaces.tui` nunca directamente dependiente de `infrastructure`; `textual` confinado a `interfaces.tui`; `subprocess` confinado a `infrastructure/process/subprocess_runner.py` (y `infrastructure/lnav/`, flujo PTY interactivo); `ssl` confinado a `infrastructure/tls/ssl_context_builder.py`; `jinja2` confinado a `infrastructure/exporters/html_exporter.py`; `sqlite3` confinado a `infrastructure/persistence/sqlite_active_defense_connection.py` (unico almacenamiento relacional del proyecto, reservado a Active Defense — vease §11).

## 7. Modulos opcionales

Todos desactivados por defecto en todos los perfiles suministrados — la activacion siempre es explicita (`option enable <nombre>` o `config enable-tls`):

| Modulo | Rol |
|---|---|
| `waf` | Firmas (rutas sensibles, UA de escaner, SQLi/XSS/CMDi en el cuerpo), limitacion de tasa (token bucket), lista de bloqueo (CIDR + expiracion), reputacion/escalado — el modo `log-only` es estructuralmente incapaz de bloquear |
| TLS | Directo (autofirmado, CA local, o publico via Let's Encrypt/Certbot con renovacion automatica — vease §9), nunca mTLS/OCSP en V1 |
| Autenticacion | HTTP Basic por zona (`url_prefix`), `hashlib.scrypt` con defensa anti-temporizacion (tiempo constante incluso para un usuario desconocido) |
| FastCGI/PHP-FPM | Un unico `(url_prefix, script_root)`, `script_root` confinado fuera de `webroot/` por construccion (el manejador estatico nunca puede filtrar codigo fuente PHP) |
| Proxy inverso saliente | Omega-serv actua el mismo como proxy hacia un backend (sentido inverso de `server.tls.mode = "behind_proxy"`) — uno o varios upstreams HTTP/HTTPS por zona con balanceo de carga round-robin (verificacion TLS estricta por defecto, desactivable pero peligrosa), cabeceras hop-by-hop eliminadas, `X-Forwarded-*` siempre sobrescritas (nunca fusionadas con las del cliente), WebSocket (un unico upstream fijado durante toda la vida del tunel, sin timeout de aplicacion una vez establecido) |
| Subida | Zonas confinadas, cuotas por zona, nombres de archivo generados por el servidor — sin streaming en V1 (limitado por `server.max_request_size`) |
| `active_defense` | Deception + modo guerra a partir de las señales WAF ya calculadas (nunca una segunda puntuacion) : señuelos estaticos, ralentizacion/registro enriquecido/limitacion de tasa dirigidos, incidentes + exportacion IoC — vease §11 |

## 8. Endurecimiento HTTP (no desactivable)

- Linea de peticion/cabeceras acotadas **durante** la lectura (nunca a posteriori), plegado de cabecera obsoleto rechazado, `Transfer-Encoding` siempre rechazado (nunca adivinado).
- `Content-Length` duplicado rechazado; `Expect: 100-continue` rechazado limpiamente (417).
- Lista blanca explicita de metodos (405 + `Allow` en caso contrario), cabecera `Host` validada (ausente/vacia/duplicada-aunque-identica/caracter de control → 400).
- Cabeceras de seguridad y CSP basica (`enforce`/`report-only`) aplicadas a **toda** respuesta, incluidos los errores — no evitables por ninguna opcion.
- Direcciones IPv4 mapeadas a IPv6 (`::ffff:x.x.x.x`) normalizadas antes de cualquier comparacion (lista de bloqueo, proxy de confianza, limitacion de tasa) — de lo contrario, un bypass conocido.
- Verificado con pruebas basadas en propiedades (`hypothesis`, miles de ejemplos generados) contra el parser HTTP y el resolvedor de rutas, ademas de las pruebas clasicas unitarias/de integracion.

## 9. TLS

### 9a. Certificado autofirmado (minimo)

Cubre el uso realista local/laboratorio/VPN (Tailscale...): un unico listener, `ssl.SSLContext` directo, RSA 2048/4096 o ECDSA P-256/P-384.

### 9b. CA local

Para varios dispositivos cliente que deben confiar sin reimportar un certificado individualmente: una autoridad de certificacion local firma tantos certificados de servidor como sea necesario.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - el elemento mas sensible del proyecto
├── root-ca.pem    # 0644 - a importar en el almacen de confianza de los clientes
├── serial.txt     # 0600 - seguimiento del proximo numero de serie
└── index.txt      # 0600 - seguimiento del estado V(alido)/R(evocado) por certificado firmado
```

Flujo: `certs generate-ca` (passphrase de la clave CA **obligatoria**, solicitud interactiva de doble confirmacion si se omite `--password`) → `certs generate-csr` (clave + CSR del servidor) → `certs sign-csr` (firma con la CA, copia el SAN de la CSR, construye `fullchain.pem` si se solicita) → apuntar `tls.certificate.certificate_path` a ese `fullchain.pem`. Un certificado comprometido se retira via `certs revoke` (marca `index.txt`, primero verifica que el certificado realmente proviene de esta CA — si no, lo rechaza). Sin distribucion de CRL en V1, ni CA externa/CSR para una autoridad de terceros, ni mTLS (vease §15).

### 9c. Let's Encrypt / ACME (Certbot) — publico, autoalojado

Para un sitio realmente publico con un certificado reconocido por los navegadores, esquema autoalojado completo: DDNS (Dynu o equivalente, enteramente a cargo del operador) → Certbot → Omega-serv. Solo asistente TUI (`Configuracion detallada → TLS → Asistente Let's Encrypt`) — invoca `certbot certonly --webroot` como subproceso (**nunca** `--standalone`, el puerto 80 ya esta ocupado por Omega-serv; **nunca** un cliente ACME reimplementado) con `--config-dir`/`--work-dir`/`--logs-dir` apuntados bajo `secure/certificates/letsencrypt/` del proyecto — **nunca** `/etc/letsencrypt/` — lo que hace que Certbot mismo sea enteramente no privilegiado. El certificado obtenido se importa automaticamente (mismo mecanismo que `certs import`, vease los ejemplos de CLI mas arriba) y se escribe un script de hook de renovacion. El modo de prueba (staging) esta marcado por defecto — desmarquelo solo una vez verificado que el dominio/webroot funcionan, para evitar los limites de tasa reales de Let's Encrypt.

Requisitos enteramente fuera del alcance de Omega-serv: un dominio apuntado a la IP publica (DDNS), y los puertos 80/443 redirigidos hacia esta maquina.

### 9d. Renovacion automatica (Certbot)

`Configuracion detallada → TLS → Renovacion automatica` se adapta al gestor de servicio realmente detectado **para esta instancia** (nunca un mecanismo compartido entre varias instancias multi-instancia): systemd → genera e instala un timer (`<service>-certbot-renew.timer`, dos veces al dia mas un retraso aleatorio, `certbot renew` limitado al `--config-dir` de la instancia); si no → una linea de crontab (usuario actual, sin privilegios) si `crontab` esta disponible; si no → se muestran instrucciones manuales, sin ninguna escritura forzada. En algunas distribuciones (entre ellas Arch/Manjaro), el paquete Certbot no instala **ningun** timer por defecto, a diferencia de Debian/Ubuntu — de ahi esta pantalla en lugar de una simple verificacion de un mecanismo que se supone ya presente. Una vez configurado, la renovacion reimporta automaticamente cada certificado renovado y reinicia el servicio, sin mas intervencion manual.

## 10. Auditoria de seguridad

`audit security` es **no bloqueante**: vuelve a ejecutar las puertas ya bloqueantes de `config check` como `CRITICAL`, luego aplica reglas consultivas (TLS, CSP, metodos peligrosos, timeouts, higiene de subidas en logica pura; permisos de archivos, expiracion de certificados, unidad systemd instalada, tamaño de logs mediante I/O real). `WAF-001` (WAF permanece en `log-only`) se observa en el tiempo mediante un pequeño archivo de estado (`var/run/waf-mode-state.json`) — solo se dispara tras ≥14 dias observados en `log-only` en ejecuciones repetidas, no en la primera `audit`.

## 11. Active Defense (deception + modo guerra)

Modulo opcional (`option enable active_defense`, desactivado por defecto) que cualifica un comportamiento hostil a partir de las señales WAF ya calculadas (`WafDecision`/reputacion/lista de bloqueo — nunca un segundo calculo de puntuacion independiente), y puede desviar una fuente hacia un señuelo, ralentizar sus respuestas y registrar con mas detalle, construir un incidente explotable, y despues exportar indicadores de compromiso (IoC). Nunca bloquea el trafico por si mismo — el bloqueo de red sigue siendo responsabilidad de `omega-fire`; Active Defense observa, desvia, ralentiza y registra.

**Amenazas y puntuacion**: cada fuente (`IP + hash SHA-256 del User-Agent`) acumula una puntuacion (`WAF-001` bloqueante +10, escalado de reputacion +25, baneo conocido +25, POST sobre un señuelo ya asignado +30 — decrece -5 cada 15 minutos sin nuevo evento) cualificada en `normal`/`suspicious`/`hostile`/`contained` (`contained` exige ademas un baneo ya conocido). `mode: monitor` observa sin actuar; `mode: enforce` aplica realmente las acciones siguientes.

**Modo guerra** (`options.active_defense.settings.war_mode`): un `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) disparado por umbrales configurables, para toda fuente que no sea `normal`:
- `enrich_log` — log JSONL separado (`var/log/active-defense-enriched.jsonl`, nunca mezclado con el log WAF/produccion), cabeceras redactadas, cuerpo HTTP hasheado (SHA-256) o truncado segun `logging.capture_request_body`.
- `delay` — ralentizacion acotada y con jitter (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), nunca un bloqueo del bucle asyncio.
- `rate_limit` — limitacion de tasa dedicada por fuente (`war_mode.rate_limit.requests`/`window_seconds`), reutiliza el mismo mecanismo que el WAF bajo una clave distinta.
- `create_incident` — apertura/fusion automatica de un incidente al franquear `thresholds.incident_score`.

**Deception**: una fuente `hostile`/`contained` puede asignarse a un señuelo estatico (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — respuestas plausibles pero siempre fijas, nunca lectura real de archivo ni subproceso) seleccionado segun la clase de ataque observada (`deception.profiles.<nombre>.match_attack_classes`, una o varias entre `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Dos niveles de aislamiento, asumidos y documentados como tales:
- **Nivel 1** (fixture in-process, `isolation_level: "fixture"`, por defecto) — aislamiento DEBIL explicito: mismo proceso, mismo usuario del sistema operativo que produccion, aceptable solo porque la fixture nunca hace otra cosa que devolver una plantilla estatica. El NOMBRE del perfil debe coincidir exactamente con una de las 4 fixtures anteriores — de lo contrario se rechaza en la validacion (`validate_active_defense_config`), para evitar la trampa de un señuelo mal nombrado que entonces nunca se dispara silenciosamente.
- **Nivel 2** (backend realmente aislado, `isolation_level: "proxy"`) — retransmitido hacia un proceso separado via `options.active_defense.settings.deception.decoy_zones.<nombre>` (upstream `host`/`port` de un servidor ya en ejecucion, nunca creado automaticamente ; nunca leido desde `options.reverse_proxy` — un señuelo nunca puede apuntar accidentalmente a una zona de produccion, verificado en `config check`), reutilizando el mismo mecanismo de proxy inverso saliente que produccion (`serve_proxy()` — upstream inalcanzable en el momento de una peticion real: se devuelve 502 al atacante, nunca un fallo).

**Pantalla Ajustes** (TUI, Active Sécurité → Active Defense → Ajustes): configuracion integral de todo lo anterior — modo, activacion del modo guerra, alcance/acciones/umbrales/ralentizacion/limite de peticiones, deception (comportamiento por defecto, CRUD de los perfiles de señuelo y de las zonas de señuelo con ejemplos de valores mostrados en cada campo), IoC, almacenamiento y registro — validada por las mismas reglas que la CLI antes de cualquier guardado, sin necesitar jamas editar manualmente `config/omega-serve.json`. Reinicio completo sistematicamente requerido tras cualquier cambio (Active Defense nunca se recarga en caliente).

**Incidentes e IoC**: cronologia completa por incidente, extraccion de indicadores (IP, User-Agent hasheado), exportacion JSON versionada/CSV limitada a los IoC compartibles/informe Markdown — cada exportacion acompañada de un archivo `<export>.sha256` (formato `sha256sum` estandar). Exportacion automatica al cerrar un incidente si `ioc.auto_export_on_close` (verdadero por defecto). `active-defense purge` cierra los incidentes vueltos silenciosos y retira los estados de amenaza expirados.

**Simulacion**: `active-defense simulate` (CLI) y el boton "Simular" (TUI, pantalla Active Sécurité) proyectan la puntuacion/nivel y explican cada accion que se dispararia — dry-run estricto, ninguna escritura real, ningun impacto de red.

Copia de seguridad/restauracion: `config backup --include-active-defense` incluye la base sqlite (amenazas/incidentes/asignaciones) en el archivo — nunca un secreto en claro, por lo que no requiere `--confirm-secrets` a diferencia de `--include-auth`.

## 12. Servicios y operacion

Deteccion automatica de systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). La unidad systemd generada aplica un endurecimiento no negociable por defecto: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` limitado a `var/`, usuario/grupo dedicados obligatorios, `UMask=0077`, `Restart=on-failure`. Apagado ordenado con SIGTERM (drena las conexiones en curso, periodo de gracia configurable y luego cierre forzado); recarga en caliente con SIGHUP (solo reglas WAF y zonas Auth — bind/puerto/TLS y Active Defense nunca modificables sin un reinicio completo).

## 13. Registros

`var/log/access.log` (formato Apache combined + `request_id`, escape anti-inyeccion de logs), `var/log/error.log`. Rotacion por tamaño/numero de archivos conservados (`logs.rotation`).

## 14. Pruebas

```bash
source .venv/bin/activate
lint-imports        # verifica los 7 contratos de capas
pytest -q           # 1763 pruebas
ruff check .
mypy src
```

Estructura: `tests/unit/` (dominio/aplicacion, dobles de prueba), `tests/integration/` (un servidor asyncio real sobre sockets TCP reales, `openssl` real como subproceso, comandos CLI reales contra un proyecto temporal completo, la interfaz interactiva via la API `Pilot` de Textual — nunca una captura de pantalla), `tests/security/` (pruebas basadas en propiedades de `hypothesis` contra el parser HTTP y el resolvedor de rutas).

## 15. Fuera de alcance

- CGI puro (solo FastCGI/PHP-FPM)
- mTLS (autenticacion de cliente por certificado), OCSP stapling
- CA externa / CSR para una autoridad de terceros, distribucion completa de CRL
- Modo por lotes/monitorizacion recurrente — cada comando es una accion explicita
- Extraccion del modulo WAF a un proyecto independiente `omega-waf` (planificada, nunca iniciada — ya diseñada con separacion limpia de cara a esta extraccion, sin desarrollo paralelo)
- Integracion en `omega-suite` (actua sobre la maquina local, no sobre un objetivo remoto — misma excepcion que `omega-fire`)
- Active Defense: exportacion STIX 2.1/MISP, pruebas de carga dedicadas, integracion real con los eventos de baneo de `omega-fire` (bloqueada del lado de `omega-fire`, que hoy no expone ninguna superficie de lectura)

---

> Omega-serv — Un servidor web potente, completo, seguro y defensivo.

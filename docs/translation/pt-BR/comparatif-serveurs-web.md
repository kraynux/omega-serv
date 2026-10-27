<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv diante dos servidores web do mercado

**Comparativo medido: nginx · lighttpd · Caddy · Apache · Traefik · omega-serv 2.0**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · **Português (Brasil)** · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Este documento situa o omega-serv entre os servidores web mais difundidos. Ele não pretende apontar um "melhor servidor": cada ferramenta atende a necessidades diferentes. Ele oferece três coisas:

1. **medições reais**, feitas na mesma máquina, com o mesmo cliente e os mesmos arquivos, e reproduzíveis;
2. um **comparativo de funções**, cada uma verificada na documentação oficial de cada servidor (links no fim do documento), distinguindo o que é integrado do que exige um módulo ou um plugin;
3. o que o omega-serv **realmente traz a mais**, e o que os outros fazem **melhor do que ele**.

Todos os números abaixo foram medidos em 26 de outubro de 2026. Nenhum número foi tirado de outro site nem estimado.

---

## Sumário

1. [Em resumo](#1-em-resumo)
2. [Método de medição](#2-método-de-medição)
3. [Desempenho: omega-serv diante de nginx, lighttpd e Caddy](#3-desempenho-omega-serv-diante-de-nginx-lighttpd-e-caddy)
4. [omega-serv 1.0 → 2.0: o que mudou, medido](#4-omega-serv-10--20-o-que-mudou-medido)
5. [Comparativo de funções](#5-comparativo-de-funções)
6. [Administração e ergonomia](#6-administração-e-ergonomia)
7. [O que o omega-serv traz a mais](#7-o-que-o-omega-serv-traz-a-mais)
8. [O que os outros fazem melhor](#8-o-que-os-outros-fazem-melhor)
9. [Qual servidor para qual uso](#9-qual-servidor-para-qual-uso)
10. [Reproduzir as medições](#10-reproduzir-as-medições)
11. [Fontes](#11-fontes)

---

## 1. Em resumo

- **Vazão bruta com arquivos pequenos**: nginx e lighttpd, escritos em C, atendem **de 10 a 20 vezes mais** requisições por segundo que o omega-serv, escrito em Python. O Caddy, escrito em Go, fica no meio. É uma diferença de natureza, não de ajuste: o omega-serv não mira esse terreno.
- **Arquivos grandes**: desde a 2.0, o omega-serv entrega o envio ao kernel (`sendfile`). Ele alcança então **a mesma ordem de vazão** que nginx, lighttpd e Caddy nesta máquina: 2,1 GB/s contra 2,0 a 2,4 GB/s.
- **Memória**: lighttpd (1 MB) e nginx (4 a 5 MB) continuam fora de alcance. O omega-serv fica abaixo de 30 MB sob carga com 1 processo, o Caddy em torno de 55 MB.
- **Da 1.0 para a 2.0**: vazão com arquivos grandes multiplicada por 2,8; memória durante downloads grandes dividida por 45; até +50% com arquivos pequenos usando 2 processos (modo boost); custo do Active Defense dividido por 12.
- **O que o omega-serv tem a mais**: administração completa por uma interface de terminal (TUI), em 17 idiomas; um WAF e uma defesa ativa integrados; limites de segurança que continuam exatos com vários processos; importação de scripts mod_magnet do lighttpd; gerenciamento de várias instâncias.
- **O que ele não tem**: HTTP/2 e HTTP/3, descoberta de serviços Docker/Kubernetes, um cliente ACME integrado (ele passa pelo Certbot), a vazão de um servidor escrito em C.

---

## 2. Método de medição

### Máquina e softwares

| Item | Valor |
|---|---|
| Processador | Intel Core i5 M480 a 2,67 GHz (2010): 2 núcleos físicos, 4 threads |
| Memória | 8 GB |
| Sistema | Manjaro Linux, kernel 6.18 |
| Rede | loopback (127.0.0.1) |
| Cliente de carga | [oha](https://github.com/hatoo/oha) 1.16.0 (escrito em Rust) |
| nginx | 1.30.4 (pacote do Manjaro) |
| lighttpd | 1.4.85 (pacote do Manjaro) |
| Caddy | 2.11.4 (pacote do Manjaro) |
| omega-serv | 1.0.0 (arquivo publicado) e 2.0.0, com Python 3.14.7 |

Apache e Traefik não foram medidos, por não estarem instalados nesta máquina. Aliás, o Traefik não é um servidor de arquivos (ver §5). Esses dois servidores aparecem apenas no comparativo de funções.

### Protocolo

- **Isolamento do processador**: cada servidor é fixado no núcleo físico 0 (threads 0 e 2) e o cliente no núcleo físico 1 (threads 1 e 3). Assim o cliente não rouba tempo do servidor, e todos os servidores dispõem exatamente dos mesmos recursos.
- **Os mesmos arquivos para todos**: `small.html` (1 KB), `medium.png` (100 KB) e `large.bin` (5 MB), servidos da mesma pasta.
- **Log de acesso ativo em todos**, porque um servidor em produção registra.
- **HTTP/1.1 sem criptografia, conexões persistentes (keep-alive)**. A concorrência é de 32 conexões para os arquivos de 1 KB e 100 KB, e de 8 para o de 5 MB.
- **Duração**: 10 segundos por arquivo e por configuração.
- **Repetições**: 3 rodadas completas, intercaladas (todos os servidores na rodada 1, depois todos na rodada 2, etc.). As tabelas dão a **mediana** das três rodadas.
- **Memória**: PSS (*Proportional Set Size*) somada de todos os processos do servidor. Ao contrário do RSS, uma página compartilhada entre processos é contada uma única vez. Ela é medida em repouso e depois da carga.
- **Configurações**: nginx, lighttpd e Caddy em sua configuração básica (arquivos estáticos, log de acesso). O omega-serv usa o perfil `standard`, com o WAF desativado e depois ativado com todas as regras fornecidas.
- **Número de processos**: cada servidor é medido com 1 e depois com 2 processos (nginx `worker_processes`, lighttpd `server.max-worker`, Caddy `GOMAXPROCS`, omega-serv `server.workers`).

### Limites a conhecer

- **Máquina modesta e antiga.** Os valores absolutos seriam bem mais altos em um servidor recente. O que faz sentido são as **proporções** entre servidores medidos na mesma sessão.
- **Variabilidade de uma sessão para outra**: cerca de 10 a 30% conforme a carga de fundo da máquina. As rodadas de uma mesma sessão são coerentes: menos de 5% de diferença para omega-serv e Caddy, mais para nginx e lighttpd, cuja vazão muito alta é mais sensível ao resto da máquina.
- **Loopback**: a medição não passa por uma rede real. Em uma rede real, a vazão com arquivos grandes quase sempre é limitada pela largura de banda, não pelo servidor.
- **Sem TLS** nestas medições. Com HTTPS, o omega-serv não pode usar `sendfile` e envia os arquivos em blocos.
- **Números brutos**: são publicados com este documento em [`docs/benchmarks/2026-10-26-campagne-brute.txt`](../../benchmarks/2026-10-26-campagne-brute.txt).

---

## 3. Desempenho: omega-serv diante de nginx, lighttpd e Caddy

### Arquivos pequenos (1 KB): requisições por segundo

| Servidor | 1 processo | 2 processos | Latência p99 (1 proc.) |
|---|---:|---:|---:|
| lighttpd 1.4.85 | 25.521 | 29.700 | 4,5 ms |
| nginx 1.30.4 | 14.054 | 18.315 | 4,7 ms |
| Caddy 2.11.4 | 3.697 | 5.345 | 25,3 ms |
| **omega-serv 2.0** | **1.358** | **1.953** | **37,5 ms** |
| omega-serv 2.0 + WAF | 1.130 | 1.617 | 48,5 ms |
| omega-serv 1.0 | 1.304 | — | 41,2 ms |

### Arquivos médios (100 KB): requisições por segundo

| Servidor | 1 processo | 2 processos |
|---|---:|---:|
| lighttpd | 11.635 | 13.037 |
| nginx | 8.024 | 9.555 |
| Caddy | 3.280 | 4.344 |
| **omega-serv 2.0** | **1.247** | **1.629** |
| omega-serv 2.0 + WAF | 1.012 | 1.347 |
| omega-serv 1.0 | 1.064 | — |

### Arquivo grande (5 MB): vazão

| Servidor | 1 processo | 2 processos |
|---|---:|---:|
| lighttpd | 2.379 MB/s | 2.407 MB/s |
| nginx | 2.242 MB/s | 1.981 MB/s |
| Caddy | 2.165 MB/s | 2.229 MB/s |
| **omega-serv 2.0** | **1.658 MB/s** | **2.115 MB/s** |
| omega-serv 1.0 | 584 MB/s | — |

### Memória (PSS, todos os processos do servidor)

| Servidor | Em repouso | Após a carga |
|---|---:|---:|
| lighttpd (1 ou 2 proc.) | 1 MB | 1 MB |
| nginx (1 ou 2 proc.) | 4 a 5 MB | 4 a 5 MB |
| **omega-serv 2.0 (1 proc.)** | **26 MB** | **30 MB** |
| omega-serv 2.0 (2 proc.) | 39 MB | 48 MB |
| Caddy | 50 MB | 56 MB |
| omega-serv 1.0 | 22 MB | 100 MB |

### Leitura

- **Com arquivos pequenos e médios**, a diferença para nginx e lighttpd é de uma ordem de grandeza (×10 a ×20). É o custo de um servidor escrito em Python: cada requisição passa pelo interpretador, enquanto nginx e lighttpd a processam em C compilado. O modo boost reduz a distância, sem eliminá-la.
- **Com arquivos grandes**, os servidores se igualam, porque é o kernel que copia os dados (`sendfile`). Com 2 processos, o omega-serv 2.0 chega a 2,1 GB/s, na mesma faixa dos outros (2,0 a 2,4 GB/s).
- **O WAF do omega-serv custa cerca de 17%** com arquivos pequenos: ele inspeciona cada requisição. nginx, lighttpd e Caddy foram medidos sem WAF; um WAF adicionado a esses servidores (ModSecurity, Coraza) também tem um custo, não medido aqui.
- **Para situar esses números**: 1.300 requisições por segundo são mais de 110 milhões de requisições por dia nesta máquina de 2010. Isso está muito além das necessidades de um site pessoal, de um serviço interno ou de um laboratório, que são os usos visados pelo omega-serv.

---

## 4. omega-serv 1.0 → 2.0: o que mudou, medido

### Desempenho

As duas versões foram medidas na mesma sessão, na mesma máquina e com o mesmo protocolo.

| Medição | 1.0.0 | 2.0.0 | Evolução |
|---|---:|---:|---:|
| Arquivos pequenos (1 KB), 1 processo | 1.304 req/s | 1.358 req/s | +4% |
| Arquivos pequenos (1 KB), modo boost 2 processos | — | 1.953 req/s | **+50%** vs 1.0 |
| Arquivos pequenos com WAF, 1 processo | 1.097 req/s | 1.130 req/s | +3% |
| Arquivos pequenos com WAF, 2 processos | — | 1.617 req/s | **+47%** vs 1.0 |
| Arquivos de 100 KB, 1 processo | 1.064 req/s | 1.247 req/s | +17% |
| Arquivo grande (5 MB), 1 processo | 584 MB/s | 1.658 MB/s | **×2,8** |
| Arquivo grande (5 MB), 2 processos | — | 2.115 MB/s | **×3,6** vs 1.0 |
| Memória após a carga, 1 processo | 100 MB | 30 MB | **÷3** |

### Downloads grandes simultâneos

Teste: 3 downloads simultâneos de um arquivo de 300 MB, enquanto uma página pequena é pedida continuamente. Duas execuções dão resultados idênticos.

| Medição | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Pico de memória do servidor | 1.835 MB | 40 MB |
| Página pequena durante os downloads: mediana | 3 a 4 ms | 2 ms |
| Página pequena durante os downloads: pior caso | 1,7 a 1,8 s | 5 ms |

A 1.0 carregava cada arquivo inteiro na memória antes de enviá-lo. A 2.0 o envia em blocos, ou o entrega ao kernel: a memória não depende mais do tamanho dos arquivos, e o servidor continua responsivo durante os downloads.

### Custo da defesa ativa

Custo de uma observação de ameaça pelo Active Defense, para cada requisição suspeita, medido em disco (ext4) sobre 2.000 observações:

| Medição | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediana | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Máximo | 18 a 20 ms | 37 a 46 ms |

A mediana é dividida por 12. O máximo, por outro lado, é mais alto na 2.0: alguns picos isolados, causados pela gravação periódica do journal SQLite em disco.

### Funções que chegaram com a 2.0

**Atualização aos padrões do mercado**: nginx, lighttpd, Caddy e Apache já fazem tudo isso. O omega-serv os alcança.

- Requisições condicionais (ETag, Last-Modified, respostas 304): ao recarregar uma página, só é baixado de novo o que mudou.
- Requisições parciais (Range, 206/416): retomar um download, avançar em um vídeo.
- Envio dos arquivos por `sendfile` ou em blocos, com memória estável.
- Arquivos pré-comprimidos (`.gz`, `.br`) colocados ao lado do original.
- Cache-Control padrão por tipo de arquivo (imagens, fontes, CSS/JS), ajustável.
- Vários processos de servidor (modo boost, `server.workers`).

**Funções mais amplas:**

- **Proxy reverso completo.** A 1.0 só tinha um repasse simples (rodízio, TLS para o servidor de origem, WebSocket). A 2.0 acrescenta:
  - 6 estratégias de distribuição, 7 no total;
  - afinidade de sessão e roteamento por cabeçalho;
  - verificação de saúde passiva e ativa dos servidores de origem;
  - um cache de respostas;
  - proteção contra sobrecarga e contra loops;
  - controle a quente.
- **Limite de taxa por pasta e por endereço ou rede**, além do limite global.
- **Contadores de segurança compartilhados entre processos** (ver §7).
- **Listas de caminhos sensíveis** prontas para uso, com um modo observação e um editor integrado.
- **Importação de scripts mod_magnet do lighttpd** (ver §7).
- **Interface em 17 idiomas**, com um idioma separado para as páginas vistas pelos visitantes e para as exportações.
- **Logs totalmente reformulados**:
  - uma biblioteca de logs;
  - três visualizadores, entre eles o lnav;
  - a obtenção de logs remotos por SSH.

---

## 5. Comparativo de funções

Legenda:
- ✅ integrado;
- 🧩 módulo oficial do projeto, a ativar ou instalar;
- 🔌 módulo ou plugin de terceiros;
- ⚙️ por meio de uma ferramenta externa;
- ❌ ausente.

"Comercial" designa uma função reservada à edição paga.

### Serviço HTTP

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Servir arquivos estáticos | ✅ | ✅ | ✅ | ✅ | ❌ (somente proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Arquivos pré-comprimidos `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 receita mod_rewrite | — | ✅ |
| Compressão em tempo real | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP via FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Vários processos ou núcleos | ✅ workers | ⚠️ `max-worker`, desaconselhado pela documentação | ✅ (Go, todos os núcleos) | ✅ MPM | ✅ (Go) | ✅ `server.workers` |

### Proxy reverso

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Distribuição de carga | ✅ rodízio, menos conexões, hash | ✅ fair, round-robin, hash, sticky | ✅ cerca de uma dúzia de estratégias | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 estratégias, entre elas a carga real |
| Saúde passiva (afastar um servidor com falha) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Saúde ativa (sonda periódica) | Comercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache de respostas | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Comercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Descoberta de serviços (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (núcleo do projeto) | ❌ |

### TLS

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Certificados automáticos (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ por padrão | 🧩 mod_md | ✅ | ⚙️ Certbot, com assistente integrado e renovação agendada |
| CA local | ❌ | ❌ | ✅ CA interna (emissão automática) | ❌ | ❌ | ✅ geração, assinatura de CSR, revogação |

### Segurança

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Limite de taxa por cliente | ✅ `limit_req` | ⚠️ mod_evasive (somente conexões simultâneas) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limite compartilhado entre processos | ✅ zona de memória compartilhada | ❌ contado por processo | — (um único processo) | depende do módulo | 1 instância; várias com Redis | ✅ memória compartilhada |
| WAF (assinaturas SQLi/XSS, scanners…) | 🔌 ModSecurity, Comercial (App Protect) | ❌ (scripts Lua a escrever) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ integrado |
| Lista de bloqueio com expiração, reincidência | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ integrado |
| Iscas, modo de guerra, incidentes, exportação de IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Auditoria de segurança da configuração | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Modo observação (registrar sem bloquear) | depende do módulo | — | depende do plugin | ✅ ModSecurity `DetectionOnly` | depende do plugin | ✅ |

### Extensibilidade

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.0 |
|---|---|---|---|---|---|---|
| Linguagem de script | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | módulos Go (recompilação) | 🧩 mod_lua | plugins Go ou WebAssembly | 🔌 importação de scripts mod_magnet (opção `magnet`) |
| Ecossistema de módulos | muito amplo | específico | amplo | muito amplo | amplo | nenhum: tudo é integrado |

---

## 6. Administração e ergonomia

| Servidor | Modo principal de administração | Interface | Recarga sem interrupção |
|---|---|---|---|
| nginx | arquivos de configuração | nenhuma (painel: NGINX Plus, comercial) | ✅ `nginx -s reload` |
| lighttpd | arquivo de configuração | nenhuma (mod_status, somente leitura) | ✅ reinício gracioso |
| Caddy | Caddyfile ou JSON | API REST de administração | ✅ via API |
| Apache | arquivos de configuração e `.htaccess` | nenhuma (mod_status, somente leitura) | ✅ `graceful` |
| Traefik | rótulos de contêineres, arquivos ou Kubernetes | painel web (somente leitura) | ✅ configuração dinâmica |
| omega-serv | interface de terminal (TUI) e linha de comando (CLI); o arquivo JSON não precisa ser editado | **TUI completa com teclado e mouse, 17 idiomas, ajuda integrada** | ✅ para a maioria dos ajustes; reinício anunciado para a porta, o TLS e o número de processos |

Na prática, com o omega-serv, a configuração, a segurança, os logs, os serviços do sistema, os backups e as instâncias são gerenciados a partir de uma única interface. Cada ajuste é explicado e verificado antes de ser gravado. Com os outros servidores, editam-se arquivos de texto e depois recorre-se a ferramentas separadas (Certbot, fail2ban, logrotate, ModSecurity, uma ferramenta de monitoramento…).

Em contrapartida, a abordagem de "arquivo de configuração" de nginx, Apache e Caddy se automatiza muito bem (Ansible, contêineres, controle de versão). O omega-serv tem uma CLI programável, mas seu ecossistema de automação ainda é limitado.

---

## 7. O que o omega-serv traz a mais

Esta seção só considera o que nenhum dos servidores comparados oferece tal como está, sem módulo de terceiros nem ferramenta externa.

1. **Administração completa por uma interface de terminal.**
   - A interface cobre todo o servidor: o site, a segurança, os logs, os serviços, os backups e as instâncias.
   - Ela funciona com teclado e mouse, em um servidor sem ambiente gráfico, até por SSH.
   - Ela está disponível em 17 idiomas e explica cada ajuste.
   - Os outros servidores não têm interface de administração (nginx, lighttpd, Apache), ou só uma API (Caddy) ou um painel somente leitura (Traefik).
2. **Segurança ativa integrada, sem módulos a montar.**
   - O WAF inclui assinaturas, listas de caminhos editáveis, reincidência, uma lista de bloqueio com expiração, reputação e um modo observação.
   - O Active Defense acrescenta iscas, um modo de guerra, acompanhamento de incidentes, exportação de indicadores de comprometimento e uma simulação a seco.
   - Em outros servidores, essas funções exigem montar ModSecurity ou Coraza, conjuntos de regras e fail2ban.
3. **Limites de segurança exatos com vários processos.**
   - No modo boost, o limite de taxa e a reincidência do WAF são compartilhados em memória entre os processos. Um atacante não consegue, portanto, multiplicar seu limite pelo número de processos.
   - O lighttpd documenta o caso inverso: com `server.max-worker`, `mod_evasive` e `mod_status` contam separadamente em cada processo.
   - O nginx também compartilha seus contadores (zonas `limit_req`), mas não tem WAF integrado.
4. **Importação de scripts mod_magnet do lighttpd.**
   - Um script de proteção Lua já escrito para o lighttpd é importado sem ser reescrito.
   - Ele se soma à proteção integrada sem nunca poder enfraquecê-la, e sua compatibilidade é verificada antes da ativação.
5. **Gerenciamento de várias instâncias.**
   - Um registro reúne todas as instâncias, e a interface alterna de uma para outra.
   - Ela também sabe desinstalar completamente uma instância.
6. **Uma auditoria de segurança da configuração**: o comando `audit security` é informativo, nunca bloqueia e retorna códigos de saída utilizáveis em um script.
7. **Fontes de logs remotas.**
   - A interface obtém por SSH o log de outro servidor, sob demanda, sem senha armazenada.
   - Ela pode lê-lo com o lnav, mesclado aos logs locais.
8. **Um endurecimento HTTP que não pode ser desativado**, ativo desde a instalação, qualquer que seja o perfil:
   - validação estrita do cabeçalho Host;
   - rejeição das ambiguidades Content-Length / Transfer-Encoding;
   - cabeçalhos de segurança e CSP, até nas páginas de erro;
   - leitura segura de X-Forwarded-For;
   - recusa de iniciar como root.

---

## 8. O que os outros fazem melhor

- **Vazão e latência**: nginx e lighttpd atendem de 10 a 20 vezes mais requisições pequenas, com latência de 8 a 10 vezes menor. Para um site de alto tráfego, uma API pública ou uma CDN, são eles que devem ser escolhidos.
- **Memória**: lighttpd (1 MB) e nginx (4 a 5 MB) servem para máquinas muito limitadas (embarcado, Raspberry Pi de entrada, contêineres pequenos).
- **Protocolos**: HTTP/2 em todos os outros, HTTP/3 em nginx, Caddy e Traefik. O omega-serv só fala HTTP/1.1.
- **HTTPS automático**: Caddy e Traefik o integram por padrão, e nginx (`ngx_http_acme_module`) e Apache (`mod_md`) por meio de um módulo oficial. O omega-serv delega ao Certbot, com um assistente e renovação agendada.
- **Ambientes de contêineres**: a descoberta automática de serviços do Traefik (Docker, Kubernetes) não tem equivalente no omega-serv.
- **Ecossistema**: nginx e Apache oferecem milhares de módulos, guias e integrações. O Caddy oferece um sistema de módulos em Go. O omega-serv é um projeto jovem, mantido por uma única pessoa.
- **Compressão em tempo real**: o omega-serv só serve arquivos já comprimidos.

---

## 9. Qual servidor para qual uso

| Necessidade | Escolha recomendada |
|---|---|
| Site de alto tráfego, API pública, CDN, vazão máxima | **nginx** |
| Máquina muito limitada, embarcado, arquivos estáticos | **lighttpd** |
| Início rápido com HTTPS automático, configuração curta | **Caddy** |
| Aplicação PHP legada, `.htaccess`, hospedagem compartilhada | **Apache** |
| Docker, Kubernetes, microsserviços | **Traefik** |
| Site pequeno, serviço interno, laboratório, VPN, administração sem editar arquivos | **omega-serv** |
| Servidor exposto em que se quer ver e controlar a segurança (WAF, banimentos, iscas) a partir de uma única interface | **omega-serv** |
| Proxy reverso interno com distribuição, saúde e cache, gerenciado a partir de uma interface | **omega-serv** |
| Aprender o endurecimento HTTP e a defesa ativa | **omega-serv** |

Essas ferramentas também se combinam. Por exemplo:
- nginx ou Traefik na frente, voltado para a Internet, com o omega-serv atrás para um serviço interno, sua segurança e sua administração;
- omega-serv como proxy reverso interno na frente de vários servidores de aplicação.

---

## 10. Reproduzir as medições

As ferramentas vêm no repositório, em `tools/bench/`. É preciso ter nginx, lighttpd, Caddy e oha instalados, além do ambiente de desenvolvimento do omega-serv (`.venv`).

```sh
# 1. preparar uma pasta de medição (arquivos de teste, configurações, omega-serv 1.0 e 2.0)
tools/bench/compare/setup.sh /caminho/medicao omega-serv-1.0.0.tar.gz

# 2. as 12 configurações, 3 repetições intercaladas (cerca de 22 minutos)
tools/bench/compare/campaign.sh /caminho/medicao > resultados.txt

# 3. medianas
python3 tools/bench/compare/summarize.py resultados.txt

# downloads grandes (memória e capacidade de resposta), 2.0 e depois 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/caminho/medicao/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/caminho/medicao/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# medir qualquer outro servidor já em execução, sem oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-de-teste
python3 tools/bench/bench_any.py --port 8080
```

Por padrão, o servidor é fixado nas threads 0 e 2, e o cliente nas threads 1 e 3, o que corresponde à máquina de medição. Adapte essa divisão ao seu processador (`lscpu -e` mostra a topologia) com as variáveis `SRV_CPUS` e `CLI_CPUS`.

Para publicar seus próprios resultados, informe a máquina, as versões, a divisão dos processadores e as três repetições.

---

## 11. Fontes

Funções dos outros servidores, segundo a documentação oficial deles (consultada em 26 de outubro de 2026).

**nginx**
- [Limite de taxa `limit_req` (zona de memória compartilhada)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Arquivos pré-comprimidos `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Módulo ACME oficial `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Distribuição de carga (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Conector ModSecurity para nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: desaconselhado, contadores por processo para mod_status e mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (scripts Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (compressão, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (distribuição, saúde passiva, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
- [mod_evasive (conexões simultâneas por endereço)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModEvasive)

**Caddy**
- [HTTPS automático](https://caddyserver.com/docs/automatic-https)
- [`file_server` e `precompressed`](https://caddyserver.com/docs/caddyfile/directives/file_server)
- [`reverse_proxy` (estratégias, saúde ativa e passiva)](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [API de administração](https://caddyserver.com/docs/api)
- [Plugin de limite de taxa caddy-ratelimit](https://github.com/mholt/caddy-ratelimit)
- [WAF Coraza para Caddy](https://github.com/corazawaf/coraza-caddy)
- [caddy-docker-proxy](https://github.com/lucaslorentz/caddy-docker-proxy)

**Apache HTTP Server**
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, conteúdo pré-comprimido](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (em memória por instância, Redis opcional)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**Ferramenta de medição**
- [oha](https://github.com/hatoo/oha)

---

*Comparativo feito por kraynux para o omega-serv 2.0.0: medições de 26 de outubro de 2026. As medições se referem a uma única máquina. Para qualquer decisão de capacidade, meça no seu próprio hardware com as ferramentas fornecidas.*

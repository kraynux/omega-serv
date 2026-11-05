<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->

# omega-serv frente aos servidores web do mercado

**Comparativo medido: nginx · lighttpd · Apache · Caddy · Traefik · omega-serv 2.5**

🌐 [Français](../../comparatif-serveurs-web.md) · [English](../en/comparatif-serveurs-web.md) · [Español](../es/comparatif-serveurs-web.md) · **Português (Brasil)** · [Italiano](../it/comparatif-serveurs-web.md) · [Deutsch](../de/comparatif-serveurs-web.md) · [Nederlands](../nl/comparatif-serveurs-web.md) · [Polski](../pl/comparatif-serveurs-web.md) · [Русский](../ru/comparatif-serveurs-web.md) · [中文](../zh-CN/comparatif-serveurs-web.md) · [Tiếng Việt](../vi/comparatif-serveurs-web.md) · [ไทย](../th/comparatif-serveurs-web.md) · [Bahasa Indonesia](../id/comparatif-serveurs-web.md) · [日本語](../ja/comparatif-serveurs-web.md) · [한국어](../ko/comparatif-serveurs-web.md) · [हिन्दी](../hi/comparatif-serveurs-web.md) · [العربية](../ar/comparatif-serveurs-web.md)

Este documento situa o omega-serv entre os servidores web mais difundidos. Ele não procura apontar um “melhor servidor”: cada ferramenta atende a necessidades diferentes, e cada uma tem seus pontos fortes. Ele traz três coisas:

1. **medições reais**, feitas em **três máquinas** muito diferentes, com o mesmo cliente, os mesmos arquivos e o mesmo protocolo, e reproduzíveis;
2. um **comparativo de funções**, cada uma verificada na documentação oficial de cada servidor (links no fim do documento), distinguindo o que é integrado do que exige um módulo ou plugin;
3. o que o omega-serv **traz realmente a mais**, e o que os outros fazem **melhor do que ele**.

Todas as medições de desempenho foram feitas em 3 e 4 de novembro de 2026. Nenhum número foi tirado de outro site ou estimado. Os números brutos são publicados com este documento.

---

## Sumário

1. [Em resumo](#1-em-resumo)
2. [Como ler este comparativo](#2-como-ler-este-comparativo)
3. [Método de medição](#3-método-de-medição)
4. [Desempenho: omega-serv frente ao nginx, lighttpd, Apache e Caddy](#4-desempenho-omega-serv-frente-ao-nginx-lighttpd-apache-e-caddy)
5. [As versões do omega-serv: 1.0 → 2.0 → 2.5](#5-as-versões-do-omega-serv-10--20--25)
6. [Comparativo de funções](#6-comparativo-de-funções)
7. [Administração e ergonomia](#7-administração-e-ergonomia)
8. [O que o omega-serv traz a mais](#8-o-que-o-omega-serv-traz-a-mais)
9. [O que os outros fazem melhor](#9-o-que-os-outros-fazem-melhor)
10. [Qual servidor para qual uso](#10-qual-servidor-para-qual-uso)
11. [Reproduzir as medições](#11-reproduzir-as-medições)
12. [Fontes](#12-fontes)

---

## 1. Em resumo

- **O omega-serv tem dois motores.** O **motor Python** trata tudo sozinho. O **motor nativo**, escrito em C++ e lançado com a 2.5, serve as requisições ele mesmo; o Python mantém a configuração e as decisões de segurança, e o nativo reconhece sozinho as requisições às quais nenhuma regra do WAF corresponde.
- **Com o motor nativo, sem WAF**, o omega-serv serve arquivos pequenos a **cerca de 0,7 vez a velocidade do nginx**, nas três máquinas. Ele fica assim **à frente do Apache e do Caddy, atrás do nginx e do lighttpd**.
- **Com o motor Python**, o omega-serv fica bem atrás de todos os outros: **de 3 a 11 % da velocidade do nginx**.
- **Com o WAF ativo**, o omega-serv inspeciona cada requisição, o que os outros servidores medidos não fazem. Com o motor nativo, ele serve então **de 0,53 a 0,56 vez** a velocidade do nginx (sem WAF) nas máquinas A e B, e 1,07 vez na máquina C (4 núcleos contra 2): o WAF tira dele só de 5 a 22 % da vazão. Ele continua à frente do Apache e do Caddy medidos sem WAF.
- **Arquivos médios (100 KB)**: é o ponto fraco atual do motor nativo, com **de 0,3 a 0,6 vez** o nginx, atrás do Apache.
- **Arquivos grandes (5 MB)**: nginx, lighttpd, Apache e omega-serv nativo alcançam a mesma ordem de vazão. O Caddy é nitidamente mais lento na máquina mais rápida.
- **Memória**: lighttpd (1 MB), nginx (4 a 5 MB) e Apache (4 a 9 MB) são muito econômicos. O omega-serv ocupa **de 30 a 65 MB** conforme o modo, o Caddy **de 50 a 67 MB**.
- **O que o omega-serv tem a mais**: uma administração completa em interface de terminal, em 17 idiomas; um WAF e uma defesa ativa integrados; limites de segurança exatos com vários processos; a importação de scripts mod_magnet do lighttpd; a gestão de várias instâncias.
- **O que ele não tem**: HTTP/2 e HTTP/3, a compressão em tempo real, a descoberta de serviços Docker/Kubernetes, um cliente ACME integrado (ele passa pelo Certbot), um ecossistema de módulos.

---

## 2. Como ler este comparativo

Algumas noções voltam ao longo do documento.

- **Requisições por segundo (req/s)**: o número de arquivos que um servidor envia em um segundo. Quanto maior, melhor.
- **Diferença em relação ao nginx**: os valores absolutos dependem enormemente da máquina. Nas nossas três máquinas, o nginx vai de 22.000 a 440.000 req/s. O que se mantém estável é **a relação entre servidores**. As tabelas dão portanto, ao lado de cada valor, sua relação com o nginx medido na mesma sessão: **1,00 = tão rápido quanto o nginx**, 0,50 = metade, 1,50 = uma vez e meia.
- **Latência p99**: o tempo de resposta que 99 % das requisições não ultrapassam. Ela mostra os “maus momentos” que uma média esconde.
- **PSS (*Proportional Set Size*)**: a memória realmente ocupada por todos os processos do servidor. Uma página compartilhada entre vários processos só é contada uma vez.
- **Processos e núcleos**: um servidor pode usar vários núcleos do processador. Cada um faz isso à sua maneira. nginx, lighttpd, Apache e omega-serv no modo Python iniciam vários processos. O Caddy, em Go, distribui seu trabalho pelos núcleos. O motor nativo do omega-serv inicia uma thread por núcleo disponível. Para comparar em pé de igualdade, damos a cada servidor **os mesmos núcleos**.
- **WAF (*Web Application Firewall*)**: um filtro que inspeciona cada requisição para bloquear ataques (injeções, scanners…). O omega-serv o integra. Os outros servidores podem receber um como módulo (ModSecurity, Coraza), mas **foram medidos sem ele**, na configuração básica.

**O reflexo certo**: comparar as relações, não os valores absolutos, e sempre verificar se o WAF está ativo.

---

## 3. Método de medição

### As três máquinas

| | Máquina A | Máquina B | Máquina C |
|---|---|---|---|
| Processador | Intel Core i5 M480, 2,67 GHz (2010) | Intel Celeron J3455, 1,5 GHz (2016) | AMD Ryzen AI 9 365 (2024) |
| Núcleos | 2 núcleos físicos, 4 threads | 4 núcleos, sem hyperthreading | 10 núcleos (4 Zen 5 + 6 Zen 5c), 20 threads |
| Memória | 8 GB | 8 GB | 32 GB |
| Sistema | Mabox Linux (base Manjaro), kernel 6.18 | EndeavourOS, kernel 7.2 | Arch Linux, kernel 7.2 (CachyOS) |
| Núcleos do servidor | 1 núcleo físico (threads 0 e 2) | 2 núcleos (0 e 1) | 4 núcleos Zen 5, uma thread cada (0 a 3) |
| Núcleos do cliente | 1 núcleo físico (threads 1 e 3) | 2 núcleos (2 e 3) | 6 núcleos Zen 5c (4 a 9) |

A máquina A é um notebook antigo, a máquina B um mini PC de baixo consumo, a máquina C um notebook recente, ligado na tomada, no perfil de energia “equilibrado”. Elas cobrem uma faixa que vai de um pequeno servidor doméstico a uma máquina atual.

### Software

| Software | Versão |
|---|---|
| nginx | 1.30.4 (A), 1.30.5 (B, C) |
| lighttpd | 1.4.85 |
| Apache HTTP Server | 2.4.69, MPM `event` |
| Caddy | 2.11.4 (A, B), 2.11.7 (C) |
| omega-serv | 1.0.0 e 2.0.0 (arquivos publicados) e 2.5, com Python 3.14 |
| Cliente de carga | [oha](https://github.com/hatoo/oha) 1.16.0 (escrito em Rust) |

O Traefik não foi medido: ele não é um servidor de arquivos (ver §6). Ele só aparece no comparativo de funções.

### Protocolo

- **Isolamento do processador**: o servidor e o cliente estão fixados em núcleos separados (tabela acima). O cliente não rouba tempo do servidor, e todos os servidores dispõem exatamente dos mesmos recursos.
- **Mesmos arquivos para todos**: `small.html` (1 KB), `medium.png` (100 KB) e `large.bin` (5 MB), servidos a partir da mesma pasta.
- **Log de acesso ativo em todos**, porque um servidor em produção registra.
- **HTTP/1.1 em claro, conexões persistentes (keep-alive)**. A concorrência é de 32 conexões para os arquivos de 1 KB e 100 KB, e de 8 para o arquivo de 5 MB.
- **Duração**: 10 segundos por arquivo e por configuração.
- **Repetições**: 3 rodadas completas, intercaladas (todas as configurações na rodada 1, depois todas na rodada 2 etc.). As tabelas dão a **mediana** das três rodadas. De uma rodada para outra, a diferença fica quase sempre abaixo de 5 %.
- **Memória**: PSS de todos os processos do servidor, medida em repouso e depois da carga.
- **Configurações**:
  - nginx, lighttpd, Apache e Caddy na configuração básica: arquivos estáticos e log de acesso;
  - omega-serv com o perfil `standard`, o WAF desativado e depois ativado com todas as regras fornecidas (sem limite de taxa).
- **Número de processos**: cada servidor é medido com 1 e depois 2 processos: nginx `worker_processes`, lighttpd `server.max-worker`, Apache `StartServers`/`ServerLimit`, Caddy `GOMAXPROCS`, omega-serv `server.workers`. Para o motor nativo do omega-serv, `server.workers` conta os processos Python de segurança; o motor nativo, por sua vez, usa sempre todos os núcleos que lhe são dados.
- **Nenhum erro**: todas as respostas de todas as medições são 200.

### Limites a conhecer

- **O que comparamos são as relações.** Os valores absolutos seriam diferentes no seu hardware, ou num servidor dedicado.
- **Loopback (127.0.0.1)**: a medição não passa por uma rede real. Numa rede real, a vazão dos arquivos grandes é quase sempre limitada pela banda, não pelo servidor. As vazões de várias dezenas de GB/s da máquina C só são possíveis em loopback.
- **Sem TLS** nestas medições.
- **Máquina A**: o serviço omega-serv de produção desta máquina rodava em segundo plano, sem receber tráfego.
- **Máquina C**: processador híbrido (núcleos Zen 5 e Zen 5c). O servidor recebeu os 4 núcleos rápidos, o cliente os outros 6.
- **Configurações básicas**: nenhum servidor foi otimizado. Um administrador experiente sem dúvida tiraria mais de cada um, omega-serv incluído.
- **Números brutos**: [`docs/benchmarks/`](../../benchmarks/) (um arquivo por máquina).

---

## 4. Desempenho: omega-serv frente ao nginx, lighttpd, Apache e Caddy

Em todas as tabelas, o valor de referência é **o nginx com 2 processos** (= 1,00), medido na mesma sessão na mesma máquina. Nas máquinas A e B, é a configuração que ocupa todos os núcleos dados ao servidor.

### Arquivos pequenos (1 KB): requisições por segundo

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd, 2 processos | 33.138 (**1,52**) | 31.125 (**1,26**) | 378.590 (**1,53**) |
| nginx, 2 processos | 21.801 (1,00) | 24.705 (1,00) | 248.184 (1,00) |
| **omega-serv, motor nativo** | **15.222 (0,70)** | **16.542 (0,67)** | **285.213 (1,15 \*)** |
| omega-serv, nativo + WAF † | 11.990 (0,56) | 12.998 (0,53) | 264.484 (1,07 \*) |
| omega-serv, nativo + WAF, 2 processos de segurança † | 11.746 (0,55) | 12.718 (0,52) | 253.527 (1,02 \*) |
| Apache, 2 processos | 9.192 (0,42) | 8.634 (0,35) | 188.335 (0,76) |
| Caddy, 2 processos | 5.749 (0,26) | 4.116 (0,17) | 52.897 (0,21) |
| omega-serv, motor Python, 2 processos | 2.354 (0,11) | 1.312 (0,05) | 19.911 (0,08) |
| omega-serv, Python + WAF, 2 processos | 1.901 (0,09) | 1.104 (0,04) | 15.783 (0,06) |
| omega-serv, motor Python | 1.507 (0,07) | 663 (0,03) | 10.553 (0,04) |
| omega-serv, Python + WAF | 1.561 (0,07) | 564 (0,02) | 8.365 (0,03) |

\* Na máquina C, o motor nativo usa seus 4 núcleos, enquanto o nginx só usa 2 com 2 processos. A comparação com o mesmo número de núcleos é dada mais abaixo: a relação volta ali a **0,67 a 0,71**, como nas outras máquinas.

† Medido em 4 de novembro, após a otimização do WAF, numa campanha separada com o mesmo protocolo. A relação é calculada com o nginx (2 processos) dessa campanha: 21 439, 24.424 e 248.127 req/s nos arquivos pequenos, 11 545, 11.004 e 157.491 nos arquivos de 100 KB. Antes dessa otimização, o motor nativo com WAF servia 3 495, 2.622 e 39.000 req/s (de 0,11 a 0,16 vez o nginx), porque cada requisição passava pelo Python. Números brutos: arquivos `*-waf-natif-brut.txt`.

Com um só processo, o nginx faz de 0,52 a 0,73, o lighttpd de 0,81 a 1,43, o Apache de 0,33 a 0,74 e o Caddy de 0,09 a 0,17 (números brutos).

### Latência p99 nos arquivos pequenos

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd, 2 processos | 4,4 ms | 4,1 ms | 0,2 ms |
| nginx, 2 processos | 4,9 ms | 5,2 ms | 0,2 ms |
| **omega-serv, motor nativo** | **6,1 ms** | **6,2 ms** | **0,3 ms** |
| omega-serv, nativo + WAF † | 7,2 ms | 6,7 ms | 0,3 ms |
| Apache, 2 processos | 18,8 ms | 20,6 ms | 0,8 ms |
| Caddy, 2 processos | 24,1 ms | 30,5 ms | 2,8 ms |
| omega-serv, motor Python, 2 processos | 22,6 ms | 28,1 ms | 3,3 ms |
| omega-serv, motor Python | 32,0 ms | 51,6 ms | 4,4 ms |

### Arquivos médios (100 KB): requisições por segundo

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd, 2 processos | 13.561 (**1,08**) | 12.126 (**1,07**) | 197.905 (**1,26**) |
| nginx, 2 processos | 12.513 (1,00) | 11.303 (1,00) | 157.224 (1,00) |
| Apache, 2 processos | 6.939 (0,55) | 7.035 (0,62) | 153.265 (0,97) |
| Caddy, 2 processos | 5.059 (0,40) | 3.744 (0,33) | 22.094 (0,14) |
| **omega-serv, motor nativo** | **4.738 (0,38)** | **3.115 (0,28)** | **96.277 (0,61)** |
| omega-serv, nativo + WAF † | 4.229 (0,37) | 2.926 (0,27) | 98.185 (0,62) |
| omega-serv, motor Python, 2 processos | 1.741 (0,14) | 1.154 (0,10) | 18.806 (0,12) |
| omega-serv, motor Python | 1.329 (0,11) | 611 (0,05) | 9.805 (0,06) |

### Arquivo grande (5 MB): vazão

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd, 2 processos | 2.440 MB/s (1,05) | 2.110 MB/s (0,99) | 28.011 MB/s (0,81) |
| nginx, 2 processos | 2.322 MB/s (1,00) | 2.124 MB/s (1,00) | 34.651 MB/s (1,00) |
| Apache, 2 processos | 2.355 MB/s (1,01) | 2.134 MB/s (1,00) | 41.153 MB/s (**1,19**) |
| **omega-serv, motor nativo** | **2.294 MB/s (0,99)** | **1.936 MB/s (0,91)** | **37.918 MB/s (1,09)** |
| Caddy, 2 processos | 2.205 MB/s (0,95) | 1.996 MB/s (0,94) | 3.811 MB/s (0,11) |
| omega-serv, motor Python, 2 processos | 2.145 MB/s (0,92) | 1.931 MB/s (0,91) | 25.829 MB/s (0,75) |
| omega-serv, motor Python | 1.686 MB/s (0,73) | 1.472 MB/s (0,69) | 14.227 MB/s (0,41) |

### Memória (PSS, todos os processos do servidor): em repouso → após a carga

| Servidor | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| lighttpd | 1 → 1 MB | 1 → 1 MB | 1 → 1 MB |
| nginx | 4 → 5 MB | 5 → 5 MB | 4 → 4 MB |
| Apache | 4 → 7 MB | 4 → 7 MB | 4 → 7 MB |
| omega-serv, motor Python | 28 → 32 MB | 29 → 33 MB | 30 → 34 MB |
| **omega-serv, motor nativo** | **33 → 34 MB** | **34 → 35 MB** | **35 → 39 MB** |
| omega-serv, nativo + WAF † | 45 → 47 MB | 43 → 44 MB | 44 → 48 MB |
| omega-serv, motor Python, 2 processos | 40 → 50 MB | 43 → 51 MB | 42 → 51 MB |
| omega-serv, nativo + WAF, 2 processos de segurança † | 45 → 47 MB | 43 → 44 MB | 55 → 57 MB |
| Caddy, 2 processos | 50 → 57 MB | 46 → 54 MB | 48 → 62 MB |

### Com o mesmo número de núcleos: máquina C com 4 processos

Campanha separada de 3 de novembro, mesmo protocolo, na máquina C: cada servidor recebe 4 processos (ou 4 núcleos para o Caddy e o motor nativo). Referência: nginx com 4 processos. O motor nativo com WAF não aparece mais aqui: medido antes da otimização do WAF, ele ainda não foi medido de novo com 4 processos.

| Servidor | 1 KB | 100 KB | 5 MB | Memória |
|---|---:|---:|---:|---:|
| lighttpd, 4 processos | 638.907 (**1,46**) | 312.402 (**1,21**) | 41.982 MB/s (0,93) | 1 → 2 MB |
| nginx, 4 processos | 438.496 (1,00) | 258.242 (1,00) | 45.162 MB/s (1,00) | 5 → 5 MB |
| **omega-serv, motor nativo** | **294.083 a 310.972 (0,67 a 0,71)** | **108.991 a 109.955 (0,42)** | **40.137 a 40.463 MB/s (0,89 a 0,90)** | **35 → 38 MB** |
| Apache, 4 processos | 200.592 (0,46) | 162.607 (0,63) | 39.664 MB/s (0,88) | 6 → 9 MB |
| Caddy, 4 núcleos | 97.085 (0,22) | 35.900 (0,14) | 5.998 MB/s (0,13) | 52 → 67 MB |
| omega-serv, motor Python, 4 processos | 37.697 (0,09) | 35.064 (0,14) | 37.123 MB/s (0,82) | 48 → 66 MB |

### Leitura

- **O motor nativo muda o lugar do omega-serv.**
  - Nos arquivos pequenos, ele passa de 0,03-0,11 vez o nginx (motor Python) para cerca de **0,7 vez o nginx**, seja qual for a máquina.
  - Ele fica à frente do Apache e do Caddy, e atrás do nginx e do lighttpd, que continuam os mais rápidos.
  - Sua latência p99 é próxima da do nginx.
- **O lighttpd é o mais rápido nos arquivos pequenos e médios**, nas três máquinas, e o mais econômico em memória. Sua documentação desaconselha no entanto `server.max-worker` (vários processos), que usamos para comparar com o mesmo número de processos.
- **Os arquivos médios são o ponto fraco atual do motor nativo**: de 0,28 a 0,61 vez o nginx, atrás do Apache, e não melhor com mais núcleos. É uma via de melhoria identificada.
- **Nos arquivos grandes**, os servidores se igualam, porque é o kernel que copia os dados (`sendfile`). O Caddy é a exceção na máquina C: não tentamos otimizar sua configuração básica.
- **O WAF custa pouco ao motor nativo, e é preciso lê-lo com justiça.**
  - O motor nativo procura ele mesmo as regras do WAF: uma requisição à qual nenhuma corresponde é servida sem passar pelo Python. À menor dúvida (correspondência, texto não ASCII, origem vigiada pelo Active Defense, zona de autenticação…), quem decide é o Python. Com o WAF, o motor nativo conserva assim de 78 a 95 % da sua vazão nos arquivos pequenos, e de 93 a 99 % nos arquivos de 100 KB. Antes dessa otimização, sua vazão era dividida por 4 a 7.
  - A limitação de taxa é contada pelo motor nativo: ativá-la não muda esses números (máquina A: 11.391 req/s com ela, 11.330 sem). Se o magnet estiver ativo, todas as requisições ainda passam pelo Python, e o custo volta a ser o de antes.
  - O omega-serv com WAF continua à frente do Apache e do Caddy **sem** WAF.
  - nginx, lighttpd, Apache e Caddy foram medidos **sem** WAF. Um WAF acrescentado a esses servidores (ModSecurity, Coraza) também tem um custo, que não medimos. A comparação “com WAF” não é feita portanto em pé de igualdade, e não afirmamos que o omega-serv seria mais rápido do que outro servidor equipado com um WAF.
- **Vários processos de segurança não ajudam mais o tráfego comum**: ele não passa mais por eles, e a vazão continua a mesma com 2 processos (−2 a −4 %, dentro do ruído de medição). Eles só servem quando muitas requisições passam pelo Python (magnet ativo, ataque): medido antes da otimização, quando todas as requisições passavam por ali, 2 processos de segurança multiplicavam a vazão com WAF por 1,5 a 1,7 em 4 núcleos, mas só traziam de 5 a 12 % em 2 núcleos.
- **O motor Python progride com os processos** (×1,6 a ×2 com 2 processos, cerca de ×3,5 com 4), mas fica em 5-11 % do nginx.
- **Memória**: o omega-serv ocupa várias dezenas de MB a mais que o nginx, o lighttpd ou o Apache, sobretudo por causa do Python, e tanto quanto o Caddy. Com o motor nativo sem WAF, a memória fica quase estável durante a carga.
- **Para situar esses números**: mesmo o caso mais lento, o motor Python com WAF na máquina B (564 req/s), representa quase 50 milhões de requisições por dia. É muito além das necessidades de um site pessoal, de um serviço interno ou de um laboratório. A velocidade só é realmente decisiva para um site de tráfego alto.

---

## 5. As versões do omega-serv: 1.0 → 2.0 → 2.5

As três versões foram medidas na mesma sessão do §4, nas três máquinas, com o mesmo protocolo. Entre parênteses: a relação com o nginx (2 processos) da mesma sessão. †: campanha de 4 de novembro após a otimização do WAF (ver §4).

### Arquivos pequenos (1 KB): requisições por segundo

| Versão e modo | Máquina A | Máquina B | Máquina C |
|---|---:|---:|---:|
| 1.0.0 | 1.547 (0,07) | 645 (0,03) | 8.870 (0,04) |
| 1.0.0 + WAF | 1.453 (0,07) | 561 (0,02) | 7.687 (0,03) |
| 2.0.0 | 1.740 (0,08) | 650 (0,03) | 10.245 (0,04) |
| 2.0.0 + WAF | 1.456 (0,07) | 565 (0,02) | 8.371 (0,03) |
| 2.0.0, 2 processos | 2.153 (0,10) | 1.277 (0,05) | 19.192 (0,08) |
| 2.0.0 + WAF, 2 processos | 1.775 (0,08) | 1.113 (0,05) | 15.351 (0,06) |
| 2.5, motor Python | 1.507 (0,07) | 663 (0,03) | 10.553 (0,04) |
| 2.5, motor Python + WAF | 1.561 (0,07) | 564 (0,02) | 8.365 (0,03) |
| 2.5, motor Python, 2 processos | 2.354 (0,11) | 1.312 (0,05) | 19.911 (0,08) |
| 2.5, motor Python + WAF, 2 processos | 1.901 (0,09) | 1.104 (0,04) | 15.783 (0,06) |
| **2.5, motor nativo** | **15.222 (0,70)** | **16.542 (0,67)** | **285.213 (1,15)** |
| **2.5, motor nativo + WAF †** | **11.990 (0,56)** | **12.998 (0,53)** | **264.484 (1,07)** |
| **2.5, motor nativo + WAF, 2 processos de segurança †** | **11.746 (0,55)** | **12.718 (0,52)** | **253.527 (1,02)** |

### Arquivos médios, arquivo grande e memória (1 processo, sem WAF)

| Versão | 100 KB, req/s (A / B / C) | 5 MB, MB/s (A / B / C) | Memória em repouso → após a carga (A / B / C) |
|---|---|---|---|
| 1.0.0 | 1.071 / 563 / 7.625 | 578 / 549 / 3.640 | 21 → **98** / 22 → **98** / 23 → **73** MB |
| 2.0.0 | 1.570 / 603 / 9.469 | 1.665 / 1.470 / 14.058 | 26 → 30 / 27 → 31 / 28 → 32 MB |
| 2.5, motor Python | 1.329 / 611 / 9.805 | 1.686 / 1.472 / 14.227 | 28 → 32 / 29 → 33 / 30 → 34 MB |
| **2.5, motor nativo** | **4.738 / 3.115 / 96.277** | **2.294 / 1.936 / 37.918** | **33 → 34 / 34 → 35 / 35 → 39 MB** |

### Grandes downloads simultâneos

Teste: 3 downloads simultâneos de um arquivo de 300 MB, enquanto uma página pequena é pedida continuamente. Duas passagens por versão e por máquina, com resultados quase idênticos. A memória aqui é a **RSS** de todos os processos do servidor, como no teste original: ela conta várias vezes a memória compartilhada, o que dá valores mais altos que a PSS das outras tabelas.

| Versão | Pico de memória | Página pequena, pior caso: A / B / C |
|---|---:|---|
| 1.0.0 | **1.833 a 1.836 MB** | **1,4 a 1,9 s** / **1,4 a 1,7 s** / 0,16 s |
| 2.0.0 | 39 a 42 MB | 3 ms / 4 a 6 ms / 1 ms |
| 2.5, motor Python | 41 a 44 MB | 2 ms / 4 ms / 1 ms |
| 2.5, motor nativo | 49 a 55 MB | 1 a 2 ms / 2 a 4 ms / menos de 1 ms |

### Custo da defesa ativa (1.0 → 2.0)

Medição de 26 de outubro de 2026 na máquina A, não refeita desde então: custo de uma observação de ameaça pelo Active Defense, para cada requisição suspeita, medido em disco (ext4) sobre 2.000 observações.

| Medida | 1.0.0 | 2.0.0 |
|---|---:|---:|
| Mediana | 2,84 ms | 0,23 ms |
| p99 | 11,6 ms | 2,3 ms |
| Máximo | 18 a 20 ms | 37 a 46 ms |

A mediana é dividida por 12. O máximo, por outro lado, é mais alto na 2.0: alguns picos isolados, ligados à escrita periódica do journal SQLite em disco.

### Leitura

- **Da 1.0 para a 2.0**, o progresso está na memória e nos arquivos grandes, não na velocidade das páginas pequenas:
  - a memória após a carga passa de 73-98 MB para 30-32 MB;
  - durante grandes downloads, ela passa de mais de 1,8 GB para cerca de 40 MB, e o servidor continua responsivo (alguns milissegundos em vez de quase 2 segundos);
  - a vazão dos arquivos grandes é multiplicada por 2,7 a 3,9;
  - a 2.0 acrescenta vários processos, que aumentam de 25 % a quase 100 % a vazão das páginas pequenas conforme a máquina.
  A 1.0 carregava cada arquivo inteiro na memória antes de enviá-lo. A 2.0 o envia em blocos, ou o confia ao kernel.
- **Da 2.0 para a 2.5, o motor Python não muda de velocidade**: as diferenças ficam abaixo de 4 % nas máquinas B e C, e dentro do ruído de medição da máquina A (−13 % a +9 %), a mais sensível à carga de fundo. Todo o ganho da 2.5 vem do **motor nativo**: cerca de ×10 a ×27 nos arquivos pequenos em relação ao motor Python, e a latência dividida por 5 a 15.
- **O motor nativo ocupa cerca de 5 MB a mais** em repouso que o motor Python (PSS): é o preço do segundo programa. Com o WAF, ele ocupa ainda cerca de 8 MB a mais: as regras carregadas no nativo.

### O que saber sobre o motor nativo

- Ele é **opcional**: o motor Python continua sendo o motor padrão, e o motor de reserva.
- Ele serve ele mesmo o conteúdo estático, os redirecionamentos, as reescritas, os aliases, o cache, as páginas de erro, os cabeçalhos de segurança e o TLS.
- Ele procura ele mesmo as regras do WAF e serve sozinho uma requisição à qual nenhuma corresponde. Qualquer outra requisição (correspondência ou dúvida do WAF, Active Defense, autenticação) é decidida pelo Python, com exatamente os mesmos controles e os mesmos logs. Um controle ajustável ainda envia ao Python uma requisição limpa a cada N, para verificar que os dois dão o mesmo veredito.
- A listagem de diretórios e as páginas internas são pedidas ao Python; o proxy reverso, o FastCGI, o envio de arquivos e o WebSocket lhe são confiados durante toda a conexão. Essas funções mantêm portanto a velocidade do motor Python.
- Com TLS direto, o proxy reverso, o FastCGI e o envio de arquivos não são suportados pelo nativo: quem serve então é o motor Python, e a interface indica isso.
- Ele exige glibc 2.38 ou mais recente e OpenSSL 3. Se ele não iniciar, a instalação o recompila no local, e na falta disso o omega-serv fica no motor Python.

---

## 6. Comparativo de funções

Legenda:
- ✅ integrado;
- 🧩 módulo oficial do projeto, a ativar ou instalar;
- 🔌 módulo ou plugin de terceiros;
- ⚙️ por meio de uma ferramenta externa;
- ❌ ausente.

“Commercial” designa uma função reservada à edição paga.

### Serviço HTTP

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Linguagem do servidor | C | C | Go | C | Go | Python, com um motor nativo C++ opcional |
| Servir arquivos estáticos | ✅ | ✅ | ✅ | ✅ | ❌ (só proxy) | ✅ |
| ETag / 304 / Range | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Arquivos pré-compactados `.gz` / `.br` | ✅ `gzip_static` (`.br`: 🔌) | 🔌 script Lua (mod_magnet) | ✅ `precompressed` | 🧩 receita mod_rewrite | — | ✅ |
| Compressão em tempo real | ✅ | ✅ mod_deflate | ✅ | 🧩 mod_deflate | ✅ middleware | ❌ |
| HTTP/2 | ✅ | ✅ | ✅ | 🧩 mod_http2 | ✅ | ❌ |
| HTTP/3 (QUIC) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| PHP via FastCGI | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Vários processos ou núcleos | ✅ workers | ⚠️ `max-worker`, desaconselhado pela documentação | ✅ (Go, todos os núcleos) | ✅ MPM | ✅ (Go) | ✅ `server.workers`; motor nativo: todos os núcleos |

### Proxy reverso

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Balanceamento de carga | ✅ rodízio, menos conexões, hash | ✅ fair, round-robin, hash, sticky | ✅ uma dúzia de estratégias | 🧩 mod_proxy_balancer | ✅ wrr, p2c, hrw, least-time | ✅ 7 estratégias, entre elas a carga real |
| Saúde passiva (afastar um servidor com falha) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Saúde ativa (sonda periódica) | Commercial (NGINX Plus) | ❌ | ✅ | 🧩 mod_proxy_hcheck | ✅ | ✅ |
| Cache de respostas | ✅ `proxy_cache` | ❌ | 🔌 | 🧩 mod_cache | Commercial | ✅ |
| WebSocket | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Descoberta de serviços (Docker, Kubernetes) | 🔌 | ❌ | 🔌 | ❌ | ✅ (núcleo do projeto) | ❌ |

### TLS

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Certificados automáticos (ACME, Let's Encrypt) | 🧩 `ngx_http_acme_module` | ⚙️ Certbot | ✅ por padrão | 🧩 mod_md | ✅ | ⚙️ Certbot, com assistente integrado e renovação programada |
| CA local | ❌ | ❌ | ✅ CA interna (emissão automática) | ❌ | ❌ | ✅ geração, assinatura de CSR, revogação |

### Segurança

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Limite de taxa por cliente | ✅ `limit_req` | ⚠️ mod_evasive (só conexões simultâneas) | 🔌 caddy-ratelimit | 🔌 mod_evasive, mod_qos | ✅ middleware | ✅ |
| Limite compartilhado entre processos | ✅ zona de memória compartilhada | ❌ contado por processo | — (um só processo) | conforme o módulo | 1 instância; várias com Redis | ✅ memória compartilhada |
| WAF (assinaturas SQLi/XSS, scanners…) | 🔌 ModSecurity, Commercial (App Protect) | ❌ (scripts Lua a escrever) | 🔌 Coraza | 🔌 ModSecurity | 🔌 plugins | ✅ integrado |
| Lista de bloqueio com expiração, reincidência | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ integrado |
| Iscas, modo guerra, incidentes, exportação de IoC | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ Active Defense |
| Banimentos graduais ao longo do tempo | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ fail2ban | ⚙️ | ✅ RIPOSTE |
| Auditoria de segurança da configuração | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ `audit security` |
| Modo observação (registrar sem bloquear) | conforme o módulo | — | conforme o plugin | ✅ ModSecurity `DetectionOnly` | conforme o plugin | ✅ |

Banimentos graduais: banimentos cada vez mais longos para os endereços que voltam, ao longo de semanas, localmente ou no nível da rede. O fail2ban os obtém com sua opção `bantime.increment`; o RIPOSTE acrescenta políticas medidas nos logs e simuladas antes da ativação, a revogação de uma ação e uma parada de emergência.

### Extensibilidade

| Função | nginx | lighttpd | Caddy | Apache | Traefik | omega-serv 2.5 |
|---|---|---|---|---|---|---|
| Linguagem de script | 🧩 njs (JavaScript); 🔌 Lua (OpenResty) | ✅ Lua (mod_magnet) | módulos Go (recompilação) | 🧩 mod_lua | plugins Go ou WebAssembly | 🔌 importação de scripts mod_magnet (opção `magnet`) |
| Ecossistema de módulos | muito amplo | focado | amplo | muito amplo | amplo | nenhum: tudo é integrado |

---

## 7. Administração e ergonomia

| Servidor | Modo de administração principal | Interface | Recarga sem interrupção |
|---|---|---|---|
| nginx | arquivos de configuração | nenhuma (painel: NGINX Plus, comercial) | ✅ `nginx -s reload` |
| lighttpd | arquivo de configuração | nenhuma (mod_status somente leitura) | ✅ reinício suave |
| Caddy | Caddyfile ou JSON | API REST de administração | ✅ pela API |
| Apache | arquivos de configuração e `.htaccess` | nenhuma (mod_status somente leitura) | ✅ `graceful` |
| Traefik | rótulos de contêineres, arquivos ou Kubernetes | painel web (somente leitura) | ✅ configuração dinâmica |
| omega-serv | interface de terminal (TUI) e linha de comando (CLI); o arquivo JSON não precisa ser editado | **TUI completa com teclado e mouse, 17 idiomas, ajuda integrada** | ✅ para a maioria das configurações; reinício anunciado para a porta, o TLS, o motor e o número de processos |

Na prática, com o omega-serv, a configuração, a segurança, os logs, os serviços do sistema, os backups e as instâncias são geridos a partir de uma única interface. Cada configuração é explicada e verificada antes de ser gravada. Com os outros servidores, editam-se arquivos de texto e depois recorre-se a ferramentas separadas (Certbot, fail2ban, logrotate, ModSecurity, uma ferramenta de monitoramento…).

Em contrapartida, a abordagem “arquivo de configuração” do nginx, do Apache e do Caddy se automatiza muito bem (Ansible, contêineres, controle de versão). O omega-serv tem uma CLI programável, mas seu ecossistema de automação continua limitado.

---

## 8. O que o omega-serv traz a mais

Esta seção só considera o que nenhum dos servidores comparados oferece tal como está, sem módulo de terceiros nem ferramenta externa.

1. **Uma administração completa em interface de terminal.**
   - A interface cobre todo o servidor: o site, a segurança, os logs, os serviços, os backups e as instâncias.
   - Ela se usa com teclado e mouse, num servidor sem tela gráfica, até mesmo por SSH.
   - Ela está disponível em 17 idiomas e explica cada configuração.
   - Os outros servidores não têm interface de administração (nginx, lighttpd, Apache), ou só uma API (Caddy) ou um painel somente leitura (Traefik).
2. **Uma segurança ativa integrada, sem módulos a montar.**
   - O WAF inclui assinaturas, listas de caminhos editáveis, a reincidência, uma lista de bloqueio com expiração, a reputação e um modo observação.
   - O Active Defense acrescenta iscas, um modo guerra, o acompanhamento de incidentes, a exportação de indicadores de comprometimento e uma simulação sem efeito.
   - O RIPOSTE responde ao longo do tempo: ele guarda a memória dos endereços que voltam e lhes aplica respostas graduais, banimentos cada vez mais longos (1 h, 6 h, 24 h, 7 dias por padrão), locais na lista de bloqueio ou de rede via fail2ban (omega-jail), ou uma isca prolongada. Cada política pode ser medida nos logs reais e simulada antes de ser ativada; cada ação continua visível e pode ser revogada, com uma parada de emergência.
   - Em outros servidores, essas funções exigem montar ModSecurity ou Coraza, conjuntos de regras e fail2ban.
3. **Limites de segurança exatos com vários processos.**
   - Com vários processos, a limitação de taxa e a reincidência do WAF são compartilhadas na memória entre eles. Um atacante não pode assim multiplicar seu limite pelo número de processos.
   - O lighttpd documenta o caso contrário: com `server.max-worker`, `mod_evasive` e `mod_status` contam separadamente em cada processo.
   - O nginx também compartilha seus contadores (zonas `limit_req`), mas não tem WAF integrado.
4. **Dois motores, um só comportamento.** O motor nativo e o motor Python produzem as mesmas respostas e os mesmos logs, verificados automaticamente numa bancada de comparação. As ferramentas que leem os logs (fail2ban, por exemplo) não veem nenhuma diferença.
5. **A importação de scripts mod_magnet do lighttpd.**
   - Um script de proteção Lua já escrito para o lighttpd é importado sem ser reescrito.
   - Ele se soma à proteção integrada sem nunca poder enfraquecê-la, e sua compatibilidade é verificada antes da ativação.
6. **A gestão de várias instâncias.**
   - Um registro lista todas as instâncias, e a interface passa de uma para outra.
   - Ela também sabe desinstalar completamente uma instância.
7. **Uma auditoria de segurança da configuração**: o comando `audit security` é informativo, nunca bloqueia e retorna códigos de saída utilizáveis num script.
8. **Fontes de logs remotas.**
   - A interface busca por SSH o log de outro servidor, sob demanda, sem senha gravada.
   - Ela pode lê-lo com o lnav, mesclando-o com os logs locais.
9. **Um endurecimento HTTP que não pode ser desativado**, ativo desde a instalação, seja qual for o perfil e o motor:
   - validação estrita do cabeçalho Host;
   - rejeição das ambiguidades Content-Length / Transfer-Encoding;
   - cabeçalhos de segurança e CSP nas respostas do site, inclusive em suas páginas de erro;
   - leitura segura de X-Forwarded-For;
   - recusa de iniciar como root.

---

## 9. O que os outros fazem melhor

- **Vazão**: lighttpd e nginx continuam os mais rápidos nos arquivos pequenos e médios, nas três máquinas. Mesmo com o motor nativo, o omega-serv serve cerca de 0,7 vez o nginx e 0,5 vez o lighttpd nos arquivos pequenos, e de 0,3 a 0,6 vez o nginx nos arquivos de 100 KB. Para um site de tráfego alto, uma API pública ou uma CDN, são eles que se deve escolher.
- **Arquivos médios**: o Apache serve os arquivos de 100 KB mais rápido que o motor nativo do omega-serv, nas três máquinas.
- **Memória**: lighttpd (1 MB), nginx (4 a 5 MB) e Apache (4 a 9 MB) convêm a máquinas muito limitadas (embarcados, pequenos contêineres). O omega-serv precisa de 30 a 65.
- **Custo da segurança**: o WAF ainda tem um custo. Com o motor nativo, ele tira de 5 a 22 % da vazão nos arquivos pequenos, limitação de taxa incluída: o omega-serv com WAF serve de 0,53 a 0,56 vez o nginx sem WAF nas máquinas A e B. Uma requisição suspeita ou duvidosa (correspondência de uma regra, texto não ASCII, origem vigiada pelo Active Defense) sempre passa pelo Python, e é servida na velocidade do motor Python. Com o magnet ativo, todas as requisições passam pelo Python, e o WAF divide então a vazão do motor nativo por 4 a 7, como antes da otimização.
- **Protocolos**: HTTP/2 em todos os outros, HTTP/3 no nginx, no Caddy e no Traefik. O omega-serv só fala HTTP/1.1.
- **HTTPS automático**: Caddy e Traefik o integram por padrão, e nginx (`ngx_http_acme_module`) e Apache (`mod_md`) com um módulo oficial. O omega-serv delega ao Certbot, com um assistente e uma renovação programada.
- **Ambientes de contêineres**: a descoberta automática de serviços do Traefik (Docker, Kubernetes) não tem equivalente no omega-serv.
- **Ecossistema e maturidade**: nginx e Apache oferecem milhares de módulos, guias e integrações, e décadas de uso em produção. O Caddy oferece um sistema de módulos em Go. O omega-serv é um projeto jovem, mantido por uma só pessoa, e seu motor nativo é recente.
- **Compressão em tempo real**: o omega-serv só serve arquivos já compactados.

---

## 10. Qual servidor para qual uso

| Necessidade | Escolha recomendada |
|---|---|
| Site de tráfego alto, API pública, CDN, vazão máxima | **nginx** ou **lighttpd** |
| Máquina muito limitada, embarcado, arquivos estáticos | **lighttpd** |
| Início rápido com HTTPS automático, configuração curta | **Caddy** |
| Aplicação PHP histórica, `.htaccess`, hospedagem compartilhada | **Apache** |
| Docker, Kubernetes, microsserviços | **Traefik** |
| Site pequeno ou médio, serviço interno, laboratório, VPN, administração sem editar arquivos | **omega-serv** (motor nativo se possível) |
| Servidor exposto em que se quer ver e controlar a segurança (WAF, banimentos graduais, iscas) a partir de uma única interface | **omega-serv** |
| Proxy reverso interno com balanceamento, saúde e cache, gerido a partir de uma interface | **omega-serv** |
| Aprender o endurecimento HTTP e a defesa ativa | **omega-serv** |

Essas ferramentas também se combinam. Por exemplo:
- nginx ou Traefik na frente na Internet, com o omega-serv atrás para um serviço interno, sua segurança e sua administração;
- omega-serv como proxy reverso interno na frente de vários servidores de aplicação.

---

## 11. Reproduzir as medições

As ferramentas são fornecidas no repositório, em `tools/bench/`. É preciso ter nginx, lighttpd, Apache, Caddy e oha instalados, o ambiente de desenvolvimento do omega-serv (`.venv`) e, para o motor nativo, o binário compilado em `native/omega-http-core/build-release`.

```sh
# 1. preparar uma pasta de medição (arquivos de teste, configurações, omega-serv 1.0, 2.0 e versão atual)
tools/bench/compare/setup.sh /caminho/medicao omega-serv-1.0.0.tar.gz omega-serv-2.0.0.tar.gz

# 2. as 21 configurações, 3 repetições intercaladas (40 a 60 minutos)
#    SRV_CPUS / CLI_CPUS: núcleos do servidor e do cliente (lscpu -e mostra a topologia)
SRV_CPUS=0,1 CLI_CPUS=2,3 tools/bench/compare/campaign.sh /caminho/medicao > resultados.txt

# 3. medianas
python3 tools/bench/compare/summarize.py resultados.txt

# outra lista de configurações, por exemplo 4 processos
CONFIGS="nginx-4 lighttpd-4 caddy-4 apache-4 omega-v2-1-0-native omega-v2-4-1-native" \
  tools/bench/compare/campaign.sh /caminho/medicao > resultados-4.txt

# grandes downloads (memória e reatividade): versão atual, motor Python e depois nativo, e depois 1.0
.venv/bin/python tools/bench/bigfile.py
BENCH_ENGINE=native .venv/bin/python tools/bench/bigfile.py
BENCH_SRC=/caminho/medicao/v1-archive/omega-serv/src \
BENCH_EXTRA_PATH=/caminho/medicao/v1-archive/omega-serv/vendor/omega-lib/src \
  .venv/bin/python tools/bench/bigfile.py

# medir qualquer outro servidor já em execução, sem oha
python3 tools/bench/bench_any.py --make-files /srv/webroot-de-teste
python3 tools/bench/bench_any.py --port 8080
```

Nomes das configurações: `nginx-N`, `lighttpd-N`, `apache-N`, `caddy-N` (N processos, ou N núcleos para o Caddy); `omega-vX-N-W` para o omega-serv (versão `v1`, `v20` ou `v2` para a versão atual, N processos, W = 0 sem WAF ou 1 com), seguido de `-native` para o motor nativo.

Para publicar seus próprios resultados, informe a máquina, as versões, a distribuição dos núcleos e as três repetições.

---

## 12. Fontes

Funções dos outros servidores, segundo sua documentação oficial (consultada em 26 de outubro de 2026).

**nginx**
- [Limite de taxa `limit_req` (zona de memória compartilhada)](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Arquivos pré-compactados `gzip_static`](https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html)
- [Módulo ACME oficial `ngx_http_acme_module`](https://nginx.org/en/docs/http/ngx_http_acme_module.html)
- [Balanceamento de carga (`upstream`)](https://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [HTTP/3](https://nginx.org/en/docs/http/ngx_http_v3_module.html)
- [Conector ModSecurity para nginx](https://github.com/owasp-modsecurity/ModSecurity-nginx)

**lighttpd**
- [`server.max-worker`: desaconselhado, contadores por processo para mod_status e mod_evasive](https://redmine.lighttpd.net/projects/lighttpd/wiki/Server_max-workerDetails)
- [mod_magnet (scripts Lua)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModMagnet)
- [mod_deflate (compressão, cache)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Mod_deflate)
- [mod_proxy (balanceamento, saúde passiva, WebSocket)](https://redmine.lighttpd.net/projects/lighttpd/wiki/Docs_ModProxy)
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
- [MPM event](https://httpd.apache.org/docs/2.4/mod/event.html)
- [mod_md (ACME)](https://httpd.apache.org/docs/2.4/mod/mod_md.html)
- [mod_proxy_balancer](https://httpd.apache.org/docs/2.4/mod/mod_proxy_balancer.html)
- [mod_proxy_hcheck](https://httpd.apache.org/docs/2.4/mod/mod_proxy_hcheck.html)
- [mod_http2](https://httpd.apache.org/docs/2.4/mod/mod_http2.html)
- [mod_deflate, conteúdo pré-compactado](https://httpd.apache.org/docs/2.4/mod/mod_deflate.html)
- [ModSecurity](https://github.com/owasp-modsecurity/ModSecurity)

**Traefik**
- [Middleware `ratelimit` (em memória por instância, Redis como opção)](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/ratelimit/)
- [ACME](https://doc.traefik.io/traefik/https/acme/)
- [Providers (Docker, Kubernetes…)](https://doc.traefik.io/traefik/providers/overview/)

**fail2ban**
- [`jail.conf`: `bantime.increment`, `bantime.factor`, `bantime.multipliers`, `bantime.maxtime` (banimentos mais longos para reincidentes)](https://github.com/fail2ban/fail2ban/blob/master/config/jail.conf) (consultado em 4 de novembro de 2026)

**Ferramenta de medição**
- [oha](https://github.com/hatoo/oha)

---

*Comparativo feito por kraynux para o omega-serv 2.5: medições de 3 e 4 de novembro de 2026 em três máquinas (defesa ativa: 26 de outubro de 2026). Para qualquer decisão de capacidade, meça no seu próprio hardware com as ferramentas fornecidas.*

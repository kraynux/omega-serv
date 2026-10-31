<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-serv.png" alt="Omega-Serv" width="384">
</div>

# 🔒 OMEGA-SERV

**Servidor web HTTP autônomo, portátil e reforçado por padrão**

> Desenvolvido por [kraynux](https://github.com/kraynux) para [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Página oficial: [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/pt-BR/) &nbsp; Referência, uso, Ajuda e FAQ: [Guia completo](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/pt-BR/guide.html)  
Prévia: [Capturas de tela](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp; Demonstração [Servidor de demonstração](https://craftdark.snake-mackarel.ts.net) &nbsp; [Comparativo/testes de servidores web](comparatif-serveurs-web.md)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Lua](https://img.shields.io/badge/Lua-5.4%2B-2C2D72.svg)](https://www.lua.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES2020%2B-F7DF1E.svg)](https://developer.mozilla.org/docs/Web/JavaScript)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20TUI-cyan.svg)](#3-uso)
[![Textual](https://img.shields.io/badge/Textual-TUI-5A5AFB.svg)](https://textual.textualize.io/)

🌐 Documentação, exportações e interface disponíveis em **17 idiomas** — veja [Idiomas da interface](#idiomas-da-interface).  
**Idiomas:**
<img src="https://flagcdn.com/w20/fr.png" alt="France" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**OMEGA-SERV** é um servidor HTTP/1.1 escrito em Python puro (apenas a biblioteca padrão no núcleo do servidor), pensado para servir conteúdo estático e, opcionalmente, PHP-FPM, com um endurecimento do protocolo que não pode ser desativado e módulos de segurança (WAF, TLS, autenticação) que se sobrepõem em vez de serem impostos. Sétima ferramenta da suíte `omega-`, mas deliberadamente **fora da futura integração `omega-suite`** (atua sobre a máquina local que o hospeda, não sobre alvos remotos — mesma família do `omega-fire`); estruturado em Clean Architecture, com `bootstrap/` como raiz de composição.

## 1. Visão e escopo

A prioridade declarada é **a solidez/segurança do núcleo HTTP em primeiro lugar** — WAF e TLS são módulos opcionais colocados por cima, nunca pré-requisitos. Um servidor que faz uma só coisa (servir arquivos, eventualmente PHP), mas a faz corretamente, com um endurecimento de protocolo real e impossível de contornar, em vez de um servidor que faz muitas coisas pela metade.

### O que o OMEGA-SERV faz

- Serve conteúdo estático (arquivos, listagem de diretório opcional, aliases, redirecionamentos, reescritas, cache) com resolução de caminhos segura (traversal, dupla codificação, links simbólicos). Os arquivos grandes saem em blocos direto do disco, nunca carregados na memória; cada arquivo traz um `ETag` e um `Last-Modified` (recarregar = resposta 304 vazia) e aceita requisições parciais `Range` (retomar um download, vídeo); imagens, mídias, fontes, CSS e JS recebem um `Cache-Control` padrão, ajustável na tela Cache. Arquivos de texto pré-comprimidos: se `site.css.br` ou `site.css.gz` existir ao lado de `site.css` (criados com `brotli -k site.css` ou `gzip -k site.css`) e o navegador os aceitar, eles são enviados no lugar, nunca uma versão mais antiga que o original.
- Endurece o protocolo HTTP por padrão, sem opção para desativá-lo: métodos permitidos explícitos, validação do cabeçalho `Host`, rejeição da ambiguidade `Content-Length`/`Transfer-Encoding`, cabeçalhos de segurança e CSP básica impossíveis de contornar.
- Opcionalmente: filtragem WAF (assinaturas, limitação de taxa, lista de bloqueio), TLS direto (certificado autoassinado, assinado por uma CA local, ou público via Let's Encrypt/Certbot com renovação automática — veja §9), autenticação HTTP Basic por zona, PHP via FastCGI/PHP-FPM, zonas de upload confinadas.
- Modo « boost »: vários processos de servidor, no máximo um por CPU disponível na máquina (tela Resistência e limites); os contadores de segurança (limite de taxa, reincidência) são compartilhados entre eles e continuam exatos.
- Audita sua própria configuração (`audit security`) e se instala como serviço do sistema (systemd/OpenRC/runit).
- CLI não interativa programável de ponta a ponta, **e interface interativa (Textual)** que reveste exatamente os mesmos casos de uso — veja §3. Roteiro da interface (`OMEGA-SERV_PLAN-DETAILLE_INTERFACE.md`, §12) **totalmente entregue**: registro de capacidades, perfis/opções, configuração detalhada (aliases/redirecionamentos/reescritas/FastCGI/listagem de diretório/autenticação/cache/WAF/proxies confiáveis/reverse proxy de saída/TLS), gerenciamento de logs (Biblioteca/Favoritos, 3 visualizadores — simples/clássico/lnav mesclado —, Ver e tratar IP, origens remotas SSH, rotação/backup/automação/restauração/limpeza/exportação), serviço do sistema, multi-instância (registro, criação), verificação/simulação/auditoria, backup/restauração da configuração, assistente de primeira execução, configurações do aplicativo (tema, perfil de renderização, caminhos de exportação/capturas), guia de ajuda contextual (ficha por tela com exemplos concretos, FAQ, exportação HTML, cobertura exaustiva verificada por teste), indicação sistemática de recarga/reinício após cada salvamento, configuração completa do Active Defense sem edição manual de arquivos.

### O que o OMEGA-SERV não faz

- CGI bruto (removido do escopo da V1 — apenas FastCGI/PHP-FPM é suportado).
- Autenticação TLS mútua (mTLS), OCSP stapling — fora do escopo da V1, veja §15. (ACME/Let's Encrypt via Certbot está disponível, veja §9c/9d.)
- Cache HTTP compartilhado entre processos.
- Varredura/auditoria de um alvo remoto (veja `omega-check`/`omega-scan`/`omega-deep` para isso — o Omega-serv só audita a si mesmo, nunca a terceiros).

### OMEGA-SERV diante dos servidores web do mercado

Veja [Medições e comparativo](comparatif-serveurs-web.md)  
Comparativo medido entre: [Nginx](https://nginx.org/) · [Lighttpd](https://www.lighttpd.net/) · [Caddy](https://caddyserver.com/) · [Apache](https://www.apache.org) · [Traefik](https://traefik.io/) · [Omega-Serv](https://kraynux.snake-mackarel.ts.net/omega-serv/translation/pt-BR/)

### Aviso de uso

O Omega-serv **se recusa a iniciar como root**. Nenhum módulo de segurança (WAF, TLS, autenticação) vem ativado por padrão em nenhum dos perfis fornecidos, inclusive o `hardened` — ativá-los é sempre um gesto explícito (`config enable-tls`, `option enable waf`...). O próprio perfil `hardened` recomenda um reverse proxy para uma exposição real à Internet, em vez de substituí-lo.

## 2. Instalação

### Pré-requisitos

- Python 3.10+
- `openssl` (o binário, não uma biblioteca Python) para tudo o que envolve certificados TLS — as demais funções funcionam sem ele.

### Download

Arquivo da versão mais recente e somas SHA-256 de cada versão: [omega-serv-2.0.1.tar.gz](https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz) · [sha.txt](https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt)

```bash
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/omega-serv-2.0.1.tar.gz
wget https://kraynux.snake-mackarel.ts.net/omega-serv/download/sha.txt
sha256sum -c --ignore-missing sha.txt
```

### Instalação

> ⚠️ **Você está atualizando uma instalação existente?** O comando abaixo **pula silenciosamente a extração** se `omega-serv/` já existir (ele supõe que se trata de uma primeira instalação interrompida, não de uma atualização) — você reinstalaria então as dependências sobre o **código antigo inalterado**, sem a menor mensagem de erro. Use em vez disso a seção [Atualização](#atualização) abaixo.

```bash
[ -d omega-serv ] && echo "ℹ️ Já extraído aqui, etapa ignorada." || tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

`install.sh`:

1. Cria o ambiente virtual `.venv` se ele ainda não existir.
2. Instala o pacote (`pip install -e .`) — **nenhuma dependência externa** (veja §6).
3. Torna `omega-serv.sh` e `install.sh` executáveis.
4. Adiciona o alias `serv` a `~/.bashrc` e `~/.zshrc` (sem duplicar se já estiver presente).

### Atualização

Se `omega-serv/` já existir (instalação anterior), **nunca execute `tar` de dentro dessa pasta**: ele tentaria criar um `omega-serv/omega-serv/` aninhado e falharia. Ao contrário do omega-fire, o `install.sh` nunca mexe nas permissões da pasta (nenhuma etapa pede `sudo`) — portanto não há risco de uma pasta pertencente ao `root` aqui, e extrair diretamente por cima da instalação existente é seguro.

```bash
# A partir da pasta PAI de omega-serv/ (nunca de dentro dela)
tar -xzf omega-serv-2.0.1.tar.gz
cd omega-serv/
./install.sh
```

O arquivo exclui deliberadamente todo o estado vivo (`var/db/`, `var/log/`, `var/backups/`, `secure/secrets/`, `secure/certificates/*.key`, `config/omega-serve.json`, **`webroot/` — o site realmente servido**...) — uma extração por cima nunca mexe nos seus dados, certificados, configurações ou conteúdo servido; apenas o código do aplicativo é substituído. O `install.sh` reutiliza o `.venv` existente e simplesmente reinstala as dependências por cima.

Desde 2026-10-18, `var/` e `secure/auth/` não fazem mais parte do arquivo de forma alguma, nem vazios: uma extração por cima não redefine mais suas permissões (compartilhadas com a conta do serviço systemd) — não é mais necessário « Serviço → Reparar as permissões » após uma atualização. O `install.sh` cria essas pastas se estiverem faltando, sem nunca mexer nas que já existem.

> ⚠️ **Se um serviço já estiver ativo, a etapa acima não basta.** Ela substitui o código em disco, mas o processo já em execução continua rodando com o código antigo carregado na memória — um **reinício completo** é sempre necessário em seguida:
> ```bash
> sudo systemctl restart <nome-do-serviço>
> ```
> **Nunca uma simples recarga** (`systemctl reload`, ou tela SERVIÇO → *Recarregar*): ela só relê algumas opções de configuração (regras WAF, zonas de autenticação...), **nunca o próprio código Python**. Um `systemctl status <nome-do-serviço>` mostrando uma data de início anterior à sua atualização confirma que ele ainda roda o código antigo. Se você sempre atualiza sobrescrevendo a mesma pasta (caso padrão acima), esse reinício é a única etapa que falta — não é necessário reinstalar o serviço.

> ⚠️ **Se o serviço entrar depois em loop de reinício** (`systemctl status` alternando ativo/inativo, `journalctl -u <nome-do-serviço>` mostrando um `PermissionError` ao gravar um arquivo em `var/`): a extração com `tar` restaura as permissões das pastas tal como foram capturadas no arquivo, o que pode apagar o compartilhamento de permissões definido para a conta de sistema dedicada durante a instalação inicial — mesmo que o próprio `install.sh` nunca mexa nelas. Não é preciso reinstalar a unidade: tela SERVIÇO → **Reparar as permissões** (reaplica o compartilhamento em `var/` e `secure/auth/`, sem mexer na unidade systemd).

### Dependências

O núcleo do servidor (parser HTTP/1.1, cliente FastCGI, hash de senhas via `hashlib.scrypt`) continua em Python puro/stdlib, e tudo o que envolve certificados TLS passa pelo binário `openssl` como subprocesso em vez de uma biblioteca criptográfica Python — **nenhuma dependência externa para isso**. Apenas a interface interativa (§3) introduz algumas: `omega-lib` (temas, detecção de terminal — biblioteca compartilhada da suíte, não publicada no PyPI, incluída no arquivo distribuído), `textual` e `pyte` (emulação de terminal para a renderização do `lnav` mesclada na interface), `jinja2` (exportações HTML com tema) e `psutil` (tela Status e recursos — CPU/RAM/disco/rede). Dependência opcional de desenvolvimento/testes (`pip install -e ".[test]"`): `hypothesis` (testes baseados em propriedades do parser HTTP e do resolvedor de caminhos, nunca em produção). Ferramentas de qualidade (`pip install -e ".[dev]"`): `pytest`, `ruff`, `mypy`, `import-linter`. Extra opcional adicional (`pip install -e ".[magnet]"`): `lupa` (binding Lua embutido, wheel pré-compilada, nenhum interpretador `lua` do sistema necessário), apenas para o script WAF complementar « magnet » (§7) — nunca instalado por padrão; sua ausência é sinalizada (capacidade `waf-magnet`, tela **Capacidades**) com o comando de instalação exato, sem bloquear o restante do servidor.

### Ferramentas opcionais recomendadas

A interface funciona em modo degradado se estas ferramentas estiverem ausentes:

- `openssl` — necessário para tudo o que envolve certificados TLS (autoassinado, CA local, importação); sem ele, os comandos `certs *` falham, mas o restante do servidor funciona normalmente (veja §9).
- `certbot` — necessário apenas para o assistente **Let's Encrypt** e sua renovação automática (§9c/9d); o TLS autoassinado/CA local não precisa dele.
- `lnav` — análise avançada de logs mesclada na tela **Gerenciamento de logs** (§3); mensagem de erro clara e explícita se o executável não for encontrado, nenhuma falha, o restante da tela (ver/acompanhar/rotação/estatísticas) funciona normalmente sem ele.
- `scp` (pacote `openssh`/`openssh-clients`, quase sempre já presente) — necessário apenas para as **Origens remotas (SSH)** (§13a); sem ele, a recuperação falha com uma mensagem clara, o restante da Biblioteca funciona normalmente.
- `python-psutil` (pacote do sistema equivalente ao `psutil` do PyPI) — instalado automaticamente por `pip install -e .` em todos os casos (dependência obrigatória do pacote, a tela **Status e recursos** sempre precisa dele), mas pré-instalá-lo pelo gerenciador do sistema evita que o `pip` tenha de compilar sua wheel localmente.

```bash
# Arch Linux e derivadas
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu e derivadas
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

## 3. Uso

Duas interfaces estritamente equivalentes em funcionalidade, nunca lógica duplicada entre elas: CLI não interativa (programável, usada abaixo) e interface interativa Textual (menus, formulários, tabelas) — cada ação de uma existe do lado da CLI, a interface apenas reveste os mesmos casos de uso.

### Modo interativo (TUI)

Recomendado para o uso diário — iniciado sem argumentos:

```bash
./omega-serv.sh
```
se você criou o alias, basta digitar `serv` no terminal:
```bash
serv
```

### Idiomas da interface

17 idiomas: francês, inglês, espanhol, português (Brasil), italiano, alemão, neerlandês, polonês, russo, chinês, vietnamita, tailandês, indonésio, japonês, coreano, hindi, árabe. Escolha nas Configurações (tecla `o`, « Langue / Language », rótulo que nunca é traduzido), ou pontualmente com `OMEGA_SERV_LANG=pt_BR serv`. No console de texto do Linux (TTY), os idiomas cuja escrita não existe nas fontes de console (vietnamita, chinês, tailandês, japonês, coreano, hindi, árabe) aparecem em inglês durante a sessão. Em hindi, os terminais que compõem eles mesmos as letras ligadas (Kitty, Ghostty, Konsole) deslocam quadros e colunas, de forma variável conforme a fonte: um aviso aparece na inicialização; Terminator, GNOME Terminal, Xfce Terminal e Alacritty exibem o hindi alinhado. Duas configurações à parte: o **idioma das páginas para visitantes** (páginas de erro, listagem de diretório — tela Páginas de erro, francês por padrão) e o **idioma das exportações** (HTML e relatório de incidente — Configurações, « Como a interface » por padrão). Os registros do servidor (`journalctl`) permanecem em francês.

### Percurso geral

Tela de abertura (splash, fecha com uma tecla ou um clique) → menu principal (Assistente de primeira execução / Registro de capacidades / Perfis / Configuração detalhada / Segurança ativa / Gerenciamento de logs / Serviço / Multi-instância / Status e recursos / Auditoria / Backup) → seleção de uma seção e depois de uma ação, cada formulário validando seus campos obrigatórios antes de continuar → confirmação explícita antes de qualquer operação sensível ou destrutiva (reinício, exclusão, restauração...) → indicação sistemática do que vem a seguir (recarga a quente automática, ou confirmação de reinício completo) após qualquer salvamento que modifique uma configuração já servida. A adaptação ao terminal (cores, tamanho, degradação estrutural do perfil de renderização) é automática e sem flag manual — veja §4.

#### Atalhos de teclado (interface interativa)

| Tecla | Ação |
|---|---|
| `↑` / `↓` | Navegar entre os elementos de uma tela |
| `Tab` / `Shift+Tab` | Navegar entre os campos de um formulário |
| `Esc` | Voltar à tela anterior (confirmação de saída na tela inicial) |
| `t` | Próximo tema (aplicado imediatamente, sem confirmação) |
| `r` | Atualizar a detecção do terminal |
| `F1` | Ajuda da tela ativa (ficha contextual — veja "Guia de ajuda" abaixo) |
| `a` | Guia de ajuda completo (menu navegável + FAQ) |
| `o` | Configurações do aplicativo (tema, perfil de renderização, caminhos de exportação/capturas — veja abaixo) |
| `q` | Sair (com confirmação) |
| `Ctrl+P` | Paleta de comandos (Tema, Captura de tela, Opções...) |

> **Exceção — editor de listas (WAF → Custom)**: nenhum atalho, tudo se faz com o mouse; o teclado serve apenas para digitar (caracteres, Enter, setas, Home/End, Page Up/Down, Backspace, Delete). `Esc`, `F1` e `Ctrl+P` ficam inativos ali (botão **Ajuda**); apenas `Ctrl+Q` continua ativo, com confirmação das alterações não salvas.

#### Guia de ajuda (teclas `F1`/`a`)

Sistema de ajuda integrado, nunca um simples texto estático: cada tela documentada (ficha com definição/campos a preencher com exemplos concretos/ação disparada/reação — recarga, reinício ou nenhuma) é acessível diretamente a partir dela via `F1`; a tecla `a` abre o menu completo (árvore idêntica à navegação real do aplicativo) com acesso à FAQ (armadilhas encontradas no uso real, p. ex. classes de ataque do Active Defense, permissões de serviço compartilhado) e uma exportação HTML autônoma (mantendo o tema ativo) do guia inteiro. Recorre a uma tela de referência genérica enquanto não existir uma ficha específica — cobertura atualmente exaustiva, verificada por teste.

#### Menu principal (interface interativa)

- **Assistente de primeira execução** — percurso guiado em 8 etapas (boas-vindas → capacidades em somente leitura → escolha do perfil → bind/porta → TLS opcional → verificação → resumo + gravação → proposta de instalação do serviço); permite gerar uma configuração completa e colocar o servidor em funcionamento sem conhecer a CLI.
- **Registro de capacidades** — sonda do sistema em somente leitura (sistema de init, porta configurada já ocupada ou não, presença de `openssl`/`logrotate`/`tailscale`/`lnav`, espaço em disco, limite de descritores...), exportação JSON/HTML.
- **Perfis** — mesmo caso de uso que `profile` na CLI (§5), diff sempre exibido antes da gravação.
- **Configuração detalhada do servidor** — CRUD completo sobre aliases/redirecionamentos/reescritas/listagem de diretório/proxies confiáveis/reverse proxy de saída/FastCGI/cache/autenticação/controle de acesso/páginas de erro, além do submenu **TLS** (status, geração autoassinada, assistente de CA local, assistente Let's Encrypt/Certbot, renovação automática, revogação, ativar/desativar — veja §9); um segundo quadro, **OPÇÕES E VERIFICAÇÃO**, agrupa os atalhos para **Opções** (`option` CLI, §7) e **Verificar a configuração** (`config check` CLI, §10) — o mesmo percurso de ajustar e depois verificar; essas duas telas não são mais acessíveis diretamente pelo menu principal. O WAF não fica mais ali (veja "Segurança ativa" abaixo): ele expõe sobretudo um estado operacional que muda continuamente, não um simples formulário de configuração estático. Cada salvamento indica sistematicamente o que vem a seguir: recarga a quente automática e silenciosa se houver um serviço ativo (listagem de diretório, acesso, aliases/redirecionamentos/reescritas, cache, páginas de erro, proxies confiáveis, zonas de reverse proxy/FastCGI, usuários/zonas de autenticação), ou confirmação explícita de reinício completo quando a mudança afeta o socket de escuta, o TLS ou o Active Defense — nenhuma tela deixa mais você adivinhando se é preciso reiniciar o servidor.
- **Segurança ativa** — tela única que agrupa dois blocos lado a lado: **Active Defense** (Status, Ameaças monitoradas com pontuação/nível, Incidentes com cronologia/exportação IoC/relatório, atribuições de Deception, Simular uma decisão em dry-run, **Configurações** — configuração completa sem nunca editar `config/omega-serve.json` à mão, veja §11) e **WAF** (Status, Módulos — modo/pacotes de regras/lista de bloqueio, Testar uma requisição, Custom — criação de regras personalizadas e carregamento de listas de caminhos/palavras-chave editáveis com o mouse (veja §11b), Magnet — importar um script `mod_magnet` externo com verificação de compatibilidade antes da ativação) — veja §11.
- **Gerenciamento de logs** — menu em duas colunas. Coluna **Biblioteca**: central que referencia todo log a tratar (alimentação manual, um clique adiciona de ofício os logs próprios da instância — access/error/WAF nativo, + script magnet §7 se ativo —, ou uma **origem remota** recuperada via SSH, veja abaixo); **Favoritos** (combinação logs + visualizador salva com um nome, abertura direta); **Ver os logs** com 3 visualizadores à escolha conforme o número de logs selecionados — Simples (tail ao vivo + estatísticas genéricas IP/erros/códigos HTTP em qualquer formato), Clássico (leitura + acompanhamento), `lnav` mesclado (renderização de terminal real dentro da interface, logs magnet incluídos de ofício + caminhos manuais **fixados** para mantê-los entre sessões); **Ver e tratar IP** (top IPs em um ou vários logs à escolha, período 24 h/7 d/30 d/tudo, remoção de um IP). Coluna **Manutenção** (sem alterações): rotação/arquivamento manual ou automático por limite de tamanho, criação imediata de backup, configuração/gerenciamento de automações agendadas (declarativas — veja a nota abaixo), restaurar/limpar um arquivo, exportação da lista.
- **Serviço** — mesmas ações que `service` na CLI (§12), elevação `sudo` pontual por ação, nunca o aplicativo inteiro executado como root.
- **Multi-instância** — registro global (`~/.config/omega-serv/instances.json`, fora de qualquer diretório de projeto) das instalações conhecidas na máquina, com o status systemd de cada uma; criação de uma nova instância (cópia da árvore, ambiente virtual e dependências próprios, configuração nova com porta distinta, verificação de não aninhamento e de conflito de porta) diretamente pela interface. Botão praticamente invisível para uma instalação única (o rótulo "Multi-instância" passa a "Instâncias (N)" assim que 2 forem conhecidas); troca completa para outra instância (`os.execv`, confirmação explícita, splash dedicado anunciando a troca no reinício); desinstalação completa de uma instância (remoção da unidade, da conta de sistema dedicada se nenhuma outra instância a usar, e exclusão opcional do diretório, nunca por padrão).
- **Status e recursos** — visão geral de relance, atualizada a cada 2 segundos: estado do servidor (processo/PID, status do serviço do sistema, perfil/opções ativas/TLS/porta), fluxo do log de acesso ao vivo (vazão, distribuição por código de status, IPs únicos, taxa de erros), recursos do sistema (CPU/RAM/disco/swap/carga/rede, via `psutil`); agrupa também o atalho **Simular uma requisição** (mesmo caso de uso que o comando CLI correspondente, §10).
- **Auditoria de segurança** — mesmo caso de uso que o comando CLI correspondente (§10).
- **Backup da configuração** — arquivo tar.gz do arquivo de configuração e, por opção explícita, das regras WAF/zonas de autenticação/certificados (confirmação obrigatória assim que segredos reais são incluídos)/base do Active Defense, restauração, lista, exclusão.

> Nota sobre as automações de rotação agendadas: elas são registradas (frequência + log alvo), mas **nada as executa automaticamente** — nem na interface, nem como tarefa em segundo plano. É uma escolha deliberada de paridade com a tela equivalente do `omega-fire`, que tem o mesmo comportamento declarativo. Uma execução periódica real (timer systemd, tarefa em segundo plano) ainda precisa ser construída separadamente, se a necessidade for confirmada.

#### Configurações do aplicativo (tecla `o` ou paleta de comandos)

Apenas preferências da interface — nunca confundidas com `config/omega-serve.json` (configuração do servidor): tema ativo, perfil de renderização (`complete`/`standard`/`reduced`/`mono`, reinício necessário), caminho das exportações (`var/exports/` por padrão), caminho das capturas de tela (`var/screenshots/` por padrão), limpeza de uma ou outra pasta (confirmação obrigatória).

```bash
# Iniciar o servidor (primeiro plano, SIGTERM = parada limpa com período de carência, SIGHUP = recarga a quente WAF/Auth)
./omega-serv.sh serve

# Configuração
./omega-serv.sh config init                # gera config/omega-serve.json (valores seguros por padrão)
./omega-serv.sh config check                # verifica sem iniciar (mesmas barreiras bloqueantes da inicialização)
./omega-serv.sh config show
./omega-serv.sh config enable-tls --cert ... --key ... --mode direct
./omega-serv.sh config disable-tls

# Perfis (minimal / standard / hardened / development)
./omega-serv.sh profile list
./omega-serv.sh profile show hardened
./omega-serv.sh profile apply hardened --dry-run   # diff antes de aplicar, sempre

# Opções (aliases, redirects, rewrites, dirlisting, cache, waf, upload, fastcgi, reverse_proxy...)
./omega-serv.sh option list
./omega-serv.sh option enable waf
./omega-serv.sh option disable waf

# Simular uma requisição sem iniciar o servidor (útil para validar uma regra antes de ativá-la)
./omega-serv.sh simulate-request GET /index.html

# WAF (funciona mesmo com a opção desativada, via --force implícito)
./omega-serv.sh waf test --method GET --path /admin --remote-ip 203.0.113.1
./omega-serv.sh blocklist list
./omega-serv.sh blocklist add --network 203.0.113.0/24 --reason "varredura detectada" --duration-seconds 3600
./omega-serv.sh blocklist remove --network 203.0.113.0/24

# Active Defense (deception + modo guerra, opção "active_defense" - veja §11)
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

# Certificados TLS - autoassinado (9a)
./omega-serv.sh certs generate-self-signed --cn localhost --san-dns localhost --san-ip 127.0.0.1
./omega-serv.sh certs show
./omega-serv.sh certs check-expiry --warn-days 30

# Certificados TLS - CA local (9b)
./omega-serv.sh certs generate-ca --cn "Minha CA local" --days 3650
./omega-serv.sh certs generate-csr --cn servidor.local --san-dns servidor.local --key-out server.key --csr-out server.csr
./omega-serv.sh certs sign-csr --csr server.csr --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem --out server.pem --fullchain-out fullchain.pem
./omega-serv.sh certs revoke --cert server.pem --ca-key secure/certificates/ca/root-ca.key --ca-cert secure/certificates/ca/root-ca.pem

# Certificados TLS - importação (9c, p. ex. a partir de um hook do Certbot)
./omega-serv.sh certs import --key privkey.pem --cert fullchain.pem

# Autenticação HTTP Basic
./omega-serv.sh auth add-user --username alice
./omega-serv.sh auth create-zone --url-prefix /admin/ --allowed-users alice
./omega-serv.sh auth list

# Auditoria de segurança (nunca bloqueia, informativa)
./omega-serv.sh audit security --format text --min-severity medium

# Backup da configuração (config sempre incluída; segredos reais
# nunca criptografados por padrão, --confirm-secrets obrigatório para incluí-los)
./omega-serv.sh config backup --description "antes da migração"
./omega-serv.sh config backup --include-auth --include-certificates --confirm-secrets
./omega-serv.sh config backup --include-active-defense --description "ameaças/incidentes"
./omega-serv.sh config list-backups
./omega-serv.sh config restore --snapshot-id snapshot_20260908_170003_762484

# Serviço do sistema (systemd/OpenRC/runit, detecção automática)
./omega-serv.sh service install --user omega-serv --group omega-serv
./omega-serv.sh service start
./omega-serv.sh service status
```

### Códigos de saída relevantes

| Comando | Código | Significado |
|---|---:|---|
| `audit security` | `0` | Nada grave (nenhum `CRITICAL`/`HIGH`) |
| `audit security` | `1` | Pelo menos um achado `CRITICAL` |
| `audit security` | `2` | Pelo menos um `HIGH` sem `CRITICAL` |
| `audit security` | `3` | Erro de execução (config não encontrada...) |
| `certs check-expiry` | `1` | Certificado expirado |
| qualquer outro comando | `0`/`1` | Sucesso / falha de validação |

## 4. Compatibilidade com terminais

A interface interativa ([Textual](https://textual.textualize.io/), construída sobre o [Rich](https://rich.readthedocs.io/)) detecta automaticamente as capacidades do terminal (emulador, tamanho) e adapta sua folha de estilo estrutural de acordo (`complete`/`standard`/`reduced`/`mono`), sem flag manual. O modo CLI permanece sempre em texto simples, independente do terminal. Política compartilhada por toda a suíte `omega-` (`omega-lib`, `terminal/policies.py`) — idêntica à do `omega-check`/`omega-fire`.

### Perfil conforme o emulador detectado

| Emulador | Perfil inicial |
|---|---|
| Ghostty, Alacritty, WezTerm, Kitty | `complete` |
| Konsole, GNOME Terminal, Terminator, Xfce4 Terminal | `standard` |
| xterm, urxvt, SSH moderno | `reduced` |
| TTY do Linux, SSH antigo | `mono` |
| Emulador não reconhecido | `reduced` (alternativa padrão) |

### Perfil conforme o tamanho do terminal

| Tamanho mínimo (colunas × linhas) | Teto de perfil |
|---|---|
| 120 × 32 | `complete` |
| 100 × 28 | `standard` |
| 80 × 24 | `reduced` |
| abaixo disso | `mono` |

O perfil final escolhido é **o mais restritivo dos dois** (emulador e tamanho) — um Ghostty em tela cheia redimensionado para 70 colunas cai para `mono`, mesmo que seu emulador permitisse `complete`. Pode ser atualizado ao vivo com a tecla `r`, ou forçado manualmente nas Configurações do aplicativo (tecla `o`, §3).

## 5. Perfis

| Perfil | Uso previsto |
|---|---|
| `minimal` | Demonstração/local simples: apenas estático, nenhuma opção ativada |
| `standard` | Site estático ou pequena produção: cabeçalhos usuais, CSP básica, dirlisting/CGI/FastCGI desativados |
| `hardened` | Exposição com privilégio mínimo: bind local por padrão (reverse proxy recomendado para a Internet), métodos limitados a GET/HEAD, CSP estrita, anti-slowloris — o WAF **nunca** é ativado automaticamente, nem mesmo aqui |
| `development` | Apenas desenvolvimento local, nunca apresentado como adequado à Internet: bind loopback obrigatório, CSP em report-only, páginas de erro detalhadas |

Ordem de mesclagem da configuração: valores seguros integrados → perfil selecionado → opções atualmente ativas mantidas (sobrevivem a uma troca de perfil) → camada explícita do usuário. Um diff completo é sempre exibido antes da gravação (`profile apply`).

## 6. Arquitetura

Clean Architecture (`core / domain / ports / application / infrastructure / interfaces / bootstrap`) — `bootstrap/` é a raiz de composição (equivalente ao `app/` das outras ferramentas da suíte). Particularidade assumida deste projeto, verificada pelo `import-linter` em vez de suposta: `application/server/start_server.py` (e `validate_config.py`, `run_audit.py`) desempenham o papel de **fábrica de construção dependente da configuração real** (qual gerenciador de serviços, ativar ou não o WAF...) e instanciam diretamente adaptadores concretos de `infrastructure/` — ao contrário do padrão mais estrito do CHECK/TRACK, em que `application/` só consome `ports/`. A única regra universal realmente imposta: `domain/`/`core/` nunca dependem das camadas externas.

```text
src/omega_serv/
├── core/            Vocabulário transversal (platform_info, constantes)
├── domain/           Lógica de negócio pura (HTTP, config, segurança WAF/TLS/auth/auditoria, roteamento)
├── ports/            Contratos (Protocol) esperados pelo aplicativo
├── application/      Casos de uso - algumas funções (build_server...) também compõem adaptadores concretos (veja acima)
├── infrastructure/    Implementações reais (asyncio, openssl como subprocesso, systemd/OpenRC/runit, arquivos)
├── interfaces/cli/    CLI argparse não interativa
├── interfaces/tui/    Interface interativa Textual (mesmos casos de uso, nunca lógica duplicada)
└── bootstrap/         DependencyContainer, resolução da raiz do projeto
```

Regras verificadas pelo `import-linter` (8 contratos): `domain`/`core` nunca dependem das camadas externas; `interfaces.tui` nunca depende diretamente de `infrastructure`; `textual` confinado a `interfaces.tui`; `subprocess` confinado a `infrastructure/process/subprocess_runner.py` (e `infrastructure/lnav/`, fluxo PTY interativo); `ssl` confinado a `infrastructure/tls/ssl_context_builder.py`; `jinja2` confinado a `infrastructure/exporters/html_exporter.py`; `sqlite3` confinado a `infrastructure/persistence/sqlite_active_defense_connection.py` (único armazenamento relacional do projeto, reservado ao Active Defense — veja §11); `lupa` confinado a `infrastructure/waf/lua_waf_adapter.py` (script WAF complementar « magnet », §7).

## 7. Módulos opcionais

Todos desativados por padrão em todos os perfis fornecidos — ativação sempre explícita (`option enable <nome>` ou `config enable-tls`):

| Módulo | Função |
|---|---|
| `waf` | Assinaturas (caminhos sensíveis, UA/Referer de scanner, SQLi/XSS/CMDi no corpo), listas editáveis em arquivo de texto (palavras-chave, ou caminhos sensíveis com exceções `!`, modo Observação e reincidência própria de cada lista — duas referências fornecidas, carregamento explícito, veja §11b), limitação de taxa (balde de fichas, regras por pasta e por IP/rede, veja §11c), lista de bloqueio (CIDR + expiração), reputação/escalonamento, importação de um script WAF `mod_magnet` do Lighttpd existente como reforço opcional do tipo « magnet » (sem reescrevê-lo, extra `pip install -e ".[magnet]"` — aditivo, nunca pode suspender um bloqueio nativo; verificação de compatibilidade no momento da importação, tela TUI dedicada) — modo `log-only` estruturalmente incapaz de bloquear |
| TLS | Direto (autoassinado, CA local, ou público via Let's Encrypt/Certbot com renovação automática — veja §9), nunca mTLS/OCSP na V1 |
| Autenticação | HTTP Basic por zona (`url_prefix`), `hashlib.scrypt` com defesa contra ataques de tempo (tempo constante mesmo para um usuário desconhecido) |
| FastCGI/PHP-FPM | Um único `(url_prefix, script_root)`, `script_root` confinado fora de `webroot/` por construção (o manipulador estático nunca pode expor código-fonte PHP) |
| Reverse proxy de saída | O Omega-serv atua ele mesmo como proxy para um ou vários backends (sentido inverso de `server.tls.mode = "behind_proxy"`) — balanceamento de carga (round-robin, ponderado, least-connections, ip-hash, least-response-time, carga real), afinidade de sessão e regras de roteamento por cabeçalho, saúde passiva e ativa, cache de respostas (multivariante `Vary`), backpressure, proteção contra loops, API de administração a quente — veja §7a para o detalhamento completo |
| Upload | Zonas confinadas, cotas por zona, nomes de arquivo gerados no servidor — sem streaming na V1 (limitado por `server.max_request_size`) |
| `active_defense` | Deception + modo guerra a partir dos sinais WAF já calculados (nunca uma segunda pontuação): iscas estáticas, desaceleração/registro enriquecido/limitação de taxa direcionados, incidentes + exportação IoC — veja §11 |

### 7a. Reverse proxy de saída — detalhes

O OMEGA-SERV pode atuar ele mesmo como reverse proxy para um ou vários backends HTTP/HTTPS — nunca confundir com `server.tls.mode = "behind_proxy"` (o OMEGA-SERV **atrás** de um proxy, mecanismo inverso). Zonas configuráveis com CRUD completo (TUI: *Configuração detalhada → Reverse Proxy*), um ou vários upstreams por zona.

- **Balanceamento de carga** — `round_robin` (padrão), `weighted_round_robin`/`weighted_least_connections`/`ip_hash` (ponderados), `least_connections`, `least_response_time`, `real_load` (carga real). Modo `real_load` nativo (sonda `/.omega-serv-load/`, reutiliza a mesma leitura do `psutil` da tela « Status e recursos », nunca uma segunda chamada) ou declarativo (sonda HTTP de terceiros, formato mínimo `{"load_percent": ...}` ou número simples) — granularidade por upstream, uma mesma zona pode misturar os dois.
- **Afinidade de sessão e roteamento condicional** — cookie sticky opaco (nunca expõe ao cliente o host:porta real) e regras por cabeçalho (igualdade ou prefixo), ambas filtradas pela elegibilidade do upstream alvo (voltam de forma limpa à estratégia ativa se o upstream visado estiver indisponível).
- **Saúde** — passiva (falhas/sucessos consecutivos, limites de transição down/up distintos para limitar o flapping) **e** ativa (sonda periódica independente do tráfego real, opcional por upstream, reutiliza o mesmo mecanismo de tarefa em segundo plano da carga real). Estados `DOWN` (sempre automático), `DRAINING`/`MAINTENANCE` (sempre manuais, explicitamente efêmeros, nunca persistidos) — um upstream acionado manualmente fica excluído das novas escolhas sem jamais interromper uma conexão já estabelecida. Nova tentativa automática em outro upstream, apenas para os métodos idempotentes (GET/HEAD/OPTIONS) e apenas em caso de erro de conexão.
- **Backpressure** — limite de conexões ativas configurável por upstream; um upstream saturado recusa de forma limpa com 503, distinto de um upstream com falha (502, nova tentativa mesmo assim).
- **Cache de respostas** — apenas GET/HEAD, nunca uma resposta de erro, nunca `Set-Cookie` salvo opt-in explícito por zona; respeita `Cache-Control`/`Vary` do upstream (opção desativável, mas perigosa, mesma filosofia da verificação TLS). Várias variantes de um mesmo recurso (`Vary`) coexistem de fato no disco, nunca um simples « o último a chegar vence ». Trava anti-stampede (uma única requisição concorrente reconstrói de fato o cache). Cabeçalho de diagnóstico `X-Omega-Cache: HIT`/`MISS`/`BYPASS` em cada resposta. Supervisão/limpeza em uma tela TUI dedicada (*Cache do reverse proxy*).
- **Proteção contra loops** — cabeçalhos hop-by-hop removidos, `X-Forwarded-*` sempre sobrescritos (nunca mesclados com os do cliente), contador `X-Omega-Proxy-Hops` incrementado a cada repasse (recusa limpa acima de 5 saltos — detecta um loop indireto entre duas instâncias, que uma simples validação da configuração local nunca consegue ver).
- **WebSocket** — upgrade permitido por zona, um único upstream fixado durante toda a vida do túnel depois de estabelecido, sem timeout de aplicação.
- **Administração a quente** — pequena API HTTP local (`/.omega-serv-admin/`, protegida por `trusted_proxy` como a sonda de carga nativa) que permite à TUI ler/forçar o estado DRAINING/MAINTENANCE de um backend e ler a taxa hits/miss do cache **do servidor realmente em execução** (tela dedicada *Status ao vivo dos backends*) — como a TUI e o servidor continuam sendo dois processos separados sem memória compartilhada, esse canal HTTP local é a única ponte entre os dois.

## 8. Endurecimento HTTP (não desativável)

- Cabeçalho/linha de requisição limitados **durante** a leitura (nunca depois), dobra de cabeçalho obsoleta recusada, `Transfer-Encoding` sempre recusado (nunca adivinhado).
- `Content-Length` duplicado rejeitado; `Expect: 100-continue` rejeitado de forma limpa (417).
- Lista branca explícita de métodos (405 + `Allow` caso contrário), cabeçalho `Host` validado (ausente/vazio/duplicado-mesmo-idêntico/caractere de controle → 400).
- Cabeçalhos de segurança e CSP básica (`enforce`/`report-only`) aplicados a **toda** resposta, inclusive os erros — impossíveis de contornar por uma opção. `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy` sempre `same-origin`, sem risco real de quebrar um site. `Cross-Origin-Embedder-Policy` sempre emitido explicitamente (nunca ausente — um scanner externo distingue « não considerado » de « permissivo por escolha »), padrão `unsafe-none` em **todos** os perfis, inclusive `hardened`: ao contrário dos dois anteriores, `require-corp`/`credentialless` podem bloquear recursos cross-origin (fontes, imagens, iframes de terceiros) próprios do site realmente servido — ajustável (`security.coep_mode`). Zonas CSP (`security.csp_zones`): exceções **explícitas** por prefixo de caminho (p. ex. `unsafe-inline` apenas sob `/uma-pasta/` que realmente precisa disso), cada uma substituindo inteiramente a política padrão para seu prefixo — nunca uma mesclagem, nunca um relaxamento global; toda exceção continua visível em `audit security` (CSP-001/CSP-002 também analisam as zonas), mesmo que deliberada. Criação guiada por um assistente diretiva por diretiva (tela **Segurança genérica**), cada campo pré-preenchido com o valor **atual** da política global — para alterar apenas o que deve mudar, em vez de partir de um campo vazio que sacrificaria as outras diretivas sem querer; uma confirmação explícita adicional é pedida se a zona montada relaxar `unsafe-inline`/`unsafe-eval`/uma origem genérica `*`.
- Endereços IPv4 mapeados em IPv6 (`::ffff:x.x.x.x`) normalizados antes de qualquer comparação (lista de bloqueio, proxy confiável, limitação de taxa) — caso contrário, um contorno conhecido.
- Verificado por testes baseados em propriedades (`hypothesis`, milhares de exemplos gerados) contra o parser HTTP e o resolvedor de caminhos, além dos testes unitários/de integração clássicos.

## 9. TLS

### 9a. Certificado autoassinado (mínimo)

Cobre o uso realista local/laboratório/VPN (Tailscale...): um único listener, `ssl.SSLContext` direto, RSA 2048/4096 ou ECDSA P-256/P-384.

### 9b. CA local

Para vários dispositivos clientes que precisam confiar sem reimportar um certificado individualmente: uma autoridade certificadora local assina quantos certificados de servidor forem necessários.

```text
secure/certificates/ca/
├── root-ca.key    # 0600 - o elemento mais sensível do projeto
├── root-ca.pem    # 0644 - a importar no repositório de confiança dos clientes
├── serial.txt     # 0600 - acompanhamento do próximo número de série
└── index.txt      # 0600 - acompanhamento do status V(álido)/R(evogado) por certificado assinado
```

Fluxo: `certs generate-ca` (senha da chave da CA **obrigatória**, digitação interativa com dupla confirmação se `--password` for omitido) → `certs generate-csr` (chave + CSR do servidor) → `certs sign-csr` (assina com a CA, copia o SAN da CSR, monta `fullchain.pem` se solicitado) → apontar `tls.certificate.certificate_path` para esse `fullchain.pem`. Um certificado comprometido é retirado com `certs revoke` (marca `index.txt`, verifica antes se o certificado vem de fato desta CA — recusa caso contrário). Sem distribuição de CRL na V1, nem CA externa/CSR para autoridade de terceiros, nem mTLS (veja §15).

### 9c. Let's Encrypt / ACME (Certbot) — público, auto-hospedado

Para um site realmente público com um certificado reconhecido pelos navegadores, esquema auto-hospedado completo: DDNS (Dynu ou equivalente, inteiramente a cargo do operador) → Certbot → Omega-serv. Apenas assistente TUI (`Configuração detalhada → TLS → Assistente Let's Encrypt`) — invoca `certbot certonly --webroot` como subprocesso (**nunca** `--standalone`, a porta 80 já está ocupada pelo Omega-serv; **nunca** um cliente ACME reimplementado) com `--config-dir`/`--work-dir`/`--logs-dir` apontados para `secure/certificates/letsencrypt/` do projeto — **nunca** `/etc/letsencrypt/` — o que torna o próprio Certbot totalmente sem privilégios. O certificado obtido é importado automaticamente (mesmo mecanismo de `certs import`, veja os exemplos de CLI acima) e um script de hook de renovação é gravado. Modo de teste (staging) marcado por padrão — desmarque-o depois de verificar que o domínio/webroot funcionam, para evitar os limites de taxa reais do Let's Encrypt.

Pré-requisitos totalmente fora do escopo do Omega-serv: um domínio apontado para o IP público (DDNS), e as portas 80/443 redirecionadas para esta máquina.

### 9d. Renovação automática (Certbot)

`Configuração detalhada → TLS → Renovação automática` se adapta ao gerenciador de serviços realmente detectado **para esta instância** (nunca um mecanismo compartilhado entre várias instâncias multi-instância): systemd → gera e instala um timer (`<serviço>-certbot-renew.timer`, duas vezes por dia + atraso aleatório, `certbot renew` restrito ao `--config-dir` da instância); senão → linha de crontab (usuário atual, sem privilégios) se o `crontab` estiver disponível; senão → instruções manuais exibidas, sem gravação forçada. Em algumas distribuições (entre elas Arch/Manjaro), o pacote Certbot não instala **nenhum** timer por padrão, ao contrário do Debian/Ubuntu — daí esta tela em vez de uma simples verificação de um mecanismo supostamente já presente. Uma vez configurada, a renovação reimporta automaticamente cada certificado renovado (`certs import`) e depois reinicia o serviço, sem nunca mais exigir intervenção manual.

## 10. Auditoria de segurança

`audit security` é **não bloqueante**: ele reexecuta as barreiras já bloqueantes do `config check` como `CRITICAL` e depois aplica regras consultivas (TLS, CSP, métodos perigosos, timeouts, higiene de upload, de forma pura; permissões de arquivos, expiração de certificado, unidade systemd instalada, tamanho dos logs com E/S real). `WAF-001` (WAF que ficou em `log-only`) é observado ao longo do tempo por meio de um pequeno arquivo de estado (`var/run/waf-mode-state.json`) — só dispara após ≥14 dias observados em `log-only` em execuções repetidas, não na primeira `audit`.

## 11. Active Defense (deception + modo guerra)

Módulo opcional (`option enable active_defense`, desativado por padrão) que qualifica um comportamento hostil a partir dos sinais WAF já calculados (`WafDecision`/reputação/lista de bloqueio — nunca um segundo cálculo de pontuação independente) e pode desviar uma origem para uma isca, desacelerar suas respostas e registrá-la com mais detalhes, montar um incidente aproveitável e depois exportar indicadores de comprometimento (IoC). Nunca bloqueia o tráfego por conta própria — o bloqueio de rede continua sendo responsabilidade do `omega-fire`; o Active Defense observa, desvia, desacelera e registra.

**Ameaças e pontuação**: cada origem (`IP + hash SHA-256 do User-Agent`) acumula uma pontuação (`WAF-001` bloqueante +10, escalonamento de reputação +25, banimento conhecido +25, POST em uma isca já atribuída +30 — redução de -5 a cada 15 minutos sem novo evento) qualificada como `normal`/`suspicious`/`hostile`/`contained` (`contained` exige, além disso, um banimento já conhecido). `mode: monitor` observa sem agir; `mode: enforce` aplica de fato as ações abaixo.

**Modo guerra** (`options.active_defense.settings.war_mode`): um `DefensePlaybook` (`actions: ["redirect_to_decoy", "enrich_log", "delay", "rate_limit", "create_incident", "export_ioc"]`) disparado por limites configuráveis, para toda origem que não seja `normal`:
- `enrich_log` — registro JSONL separado (`var/log/active-defense-enriched.jsonl`, nunca misturado ao log WAF/de produção), cabeçalhos ocultados, corpo HTTP com hash (SHA-256) ou truncado conforme `logging.capture_request_body`.
- `delay` — desaceleração limitada e com jitter (`war_mode.slowdown.minimum_ms`/`maximum_ms`/`jitter_ms`), nunca um bloqueio do loop asyncio.
- `rate_limit` — limitação de taxa dedicada por origem (`war_mode.rate_limit.requests`/`window_seconds`), reutiliza o mesmo mecanismo do WAF com uma chave distinta.
- `create_incident` — abertura/mesclagem automática de um incidente ao ultrapassar `thresholds.incident_score`.

**Deception**: uma origem `hostile`/`contained` pode ser atribuída a uma isca estática (`fake_admin`, `fake_cms`, `fake_api`, `fake_secrets` — respostas plausíveis, mas sempre fixas, nunca uma leitura real de arquivo nem um subprocesso) escolhida conforme a classe de ataque observada (`deception.profiles.<nome>.match_attack_classes`, uma ou várias entre `scan`/`credential_stuffing`/`sqli`/`xss`/`path_traversal`/`upload_probe`/`api_probe`/`unknown`). Dois níveis de isolamento, assumidos e documentados como tais:
- **Nível 1** (fixture no processo, `isolation_level: "fixture"`, padrão) — isolamento FRACO explícito: mesmo processo, mesmo usuário do sistema que a produção, aceitável apenas porque a fixture nunca faz outra coisa além de devolver um modelo estático. O NOME do perfil deve corresponder exatamente a uma das 4 fixtures acima — senão é rejeitado na validação (`validate_active_defense_config`), para evitar a armadilha de uma isca com nome errado que então nunca dispararia, silenciosamente.
- **Nível 2** (backend realmente isolado, `isolation_level: "proxy"`) — repassado a um processo separado via `options.active_defense.settings.deception.decoy_zones.<nome>` (upstream `host`/`port` de um servidor já em execução, nunca criado automaticamente; nunca lido de `options.reverse_proxy` — uma isca nunca pode apontar por acidente para uma zona de produção, verificado pelo `config check`), reutilizando o mesmo mecanismo de reverse proxy de saída da produção (`serve_proxy()` — upstream inacessível no momento de uma requisição real: 502 devolvido ao atacante, nunca uma falha do servidor).

**Tela Configurações** (TUI, Segurança ativa → Active Defense → Configurações): configuração completa de tudo o que foi descrito acima — modo, ativação do modo guerra, escopo/ações/limites/desaceleração/limite de requisições, deception (comportamento padrão, CRUD dos perfis de isca e das zonas de isca com exemplos de valores exibidos em cada campo), IoC, armazenamento e registro — validada pelas mesmas regras da CLI antes de qualquer gravação, sem jamais exigir edição manual de `config/omega-serve.json`. Um reinício completo é sempre necessário após qualquer alteração (o Active Defense nunca é recarregado a quente).

**Incidentes e IoC**: cronologia completa por incidente, extração de indicadores (IP, User-Agent com hash), exportação JSON versionada/CSV limitada aos IoC compartilháveis/relatório Markdown, e formatos de troca **STIX 2.1** (bundle para carregar no OpenCTI, em um SIEM…) e **MISP** (evento a importar pela interface do MISP), marcados TLP:AMBER por padrão — arquivos locais, nunca enviados; cada exportação acompanhada de um arquivo `<export>.sha256` (formato `sha256sum` padrão). Exportação automática ao fechar um incidente se `ioc.auto_export_on_close` (verdadeiro por padrão). Os estados expirados e o log de auditoria são purgados automaticamente e a base é limitada (proteção contra o enchimento do disco); `active-defense purge` também fecha os incidentes que voltaram a ficar silenciosos.

**Simulação**: `active-defense simulate` (CLI) e o botão "Simular" (TUI, tela Segurança ativa) projetam a pontuação/nível e explicam cada ação que seria disparada — dry-run estrito, nenhuma gravação real, nenhum impacto na rede.

Backup/restauração: `config backup --include-active-defense` inclui a base sqlite (ameaças/incidentes/atribuições) no arquivo — nunca um segredo em texto claro, portanto não é necessário `--confirm-secrets`, ao contrário de `--include-auth`.

## 11b. Listas de caminhos sensíveis (WAF)

O WAF pode carregar **listas editáveis** em arquivo de texto, um caminho (ou uma palavra-chave) por linha, a partir de **Segurança ativa → Custom → Adicionar → « CARREGAR uma lista »**. Nada é carregado por padrão: é uma ação explícita.

- **Referências fornecidas**: `sensitive-paths-hostile` (298 caminhos sem uso legítimo: segredos, backups, VCS, consoles…) e `sensitive-paths-probe` (132 caminhos de sondagem, às vezes servidos por um site real: `/admin`, `/api`, monitoramento…). No carregamento, uma **cópia local** é criada em `secure/waf/rules/keywords/`: é ela que você edita, e uma atualização do omega-serv nunca a sobrescreve (« Novidades da referência » propõe depois, item por item, as novas entradas).
- **Sintaxe**: `/admin` (→ `/admin` e `/admin/xxx`, nunca `/administrator`), `/.git/` (tudo o que está abaixo), `/*.bak` (extensão), `!/api/v1` (exceção, sempre prioritária). Caminhos decodificados como no motor (`%2e`, dupla codificação, caracteres de largura total).
- **Gravidade**: *Observação* (apenas registro, recomendado no primeiro carregamento), depois Média (nunca bloqueia sozinha) ou Alta (403 já no primeiro acesso).
- **Reincidência própria de cada lista**: 1º acesso = informação ou recusa; N acessos em M minutos = banimento temporário da aplicação (resposta 451, mesmo via Tailscale); bloqueios repetidos = banimento de rede pelo omega-jail. Referências: hostile 2 acessos em 10 min → 24 h, sondagem 5 em 10 min → 1 h.
- **Nunca um banimento automático** para o host local, o Tailscale (`100.64.0.0/10`) e a rede local (`options.waf.reputation.never_auto_block`): apenas o tráfego externo pode ser banido. Atrás de um proxy local, a isenção de `127.0.0.1` exige `trusted_proxy` ativo. `X-Forwarded-For` é lido da direita para a esquerda: um cliente não pode se declarar local.
- **Salvaguardas**: caminhos vitais protegidos (`/`, `robots.txt`, `sitemap.xml`, `/.well-known/acme-challenge/`…), recusa de uma lista bloqueante que atingiria uma rota realmente servida (alias, reverse proxy, zona Auth, webroot), **« Verificar contra meus logs »** no editor (linhas que teriam atingido requisições bem-sucedidas, exceção em um clique).
- **Editor integrado**: diagnósticos ao vivo com número de linha, « Testar » um caminho, gravação segura (permissões e grupo mantidos, links simbólicos recusados, modificação externa detectada), legibilidade pela conta do serviço verificada (« Corrigir permissões »), e recarga **honesta**: recusada com o motivo se a lista não passar na verificação, e o servidor mantém então suas regras atuais.

## 11c. Limite de taxa por pasta e por IP/rede (WAF)

O limite de taxa do WAF (balde de fichas, `options.waf.rate_limit`, 60 requisições / 60 s por IP por padrão) pode ser refinado em **Segurança ativa → Exclusões e limite de taxa** (ou à mão, `rate_limit.path_policies` / `rate_limit.source_policies`):

- **Regra por pasta** (`prefix`, `requests`, `window_seconds`): ela **substitui** o limite global para essa pasta, com seu próprio contador (`requests: 0` = ilimitado). O prefixo mais longo vence; `/images` cobre `/images/a.png`, nunca `/images2`. Tipicamente uma página pesada (galeria de imagens) que retorna 429.
- **Regra por IP/rede** (`network`, `requests`, `window_seconds`, `trusted`): mesmo princípio; a rede mais precisa vence. Prioridade: pasta, depois IP/rede, depois o limite global.
- **Banimento inalterado para o público**: um excesso de um IP público continua registrado `"action": "block"` em `waf-alerts.log`, portanto pode ser banido pelo omega-jail (3 rejeições em 10 min → 12 h). Uma **fonte segura** — rede `never_auto_block` ou regra marcada `trusted: true` — continua recebendo o 429, mas é registrada `"action": "throttle"`, que a jail nunca conta.
- **Script magnet**: o próprio limite de taxa dele (resposta 429) nunca conta como detecção, portanto nunca leva ao auto-ban; em uma requisição coberta por uma regra de pasta ou de IP/rede, a regra nativa prevalece e o 429 do magnet é ignorado (as assinaturas de ataque dele continuam aplicadas).
- Uma regra de taxa **nunca** desativa a inspeção do WAF; inversamente, uma exclusão de inspeção (`exclusions.path_prefixes`) nunca suspende o limite de taxa. Sem `trusted_proxy` ativo, uma regra que cubra `127.0.0.1`/`::1` é ignorada (a mesma salvaguarda de `never_auto_block`).

## 12. Serviços e operação

Detecção automática de systemd/OpenRC/runit (`service install/status/start/stop/restart/enable/disable/uninstall`). A unidade systemd gerada aplica por padrão um endurecimento não negociável: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths` limitado a `var/`, usuário/grupo dedicados obrigatórios, `UMask=0077`, `Restart=on-failure`. Parada limpa com SIGTERM (drenagem das conexões em curso, período de carência configurável e depois fechamento forçado); recarga a quente com SIGHUP (apenas regras WAF e zonas Auth — bind/porta/TLS e Active Defense nunca alteráveis sem reinício completo).

## 13. Registros

`var/log/access.log` (formato Apache combined + `request_id`, escape contra injeção nos logs), `var/log/error.log`. Rotação por tamanho/número de arquivos mantidos (`logs.rotation`). WAF nativo: `var/log/waf-alerts.log` (`options.waf.logging.path`). Script magnet (§7): `options.waf.magnet.paths.alerts_log`/`.blocklist_log`, padrões `var/log/waf-magnet-alerts.log`/`var/log/waf-magnet-blocklist.log` — adicionados de ofício à Biblioteca (botão *Adicionar os logs conhecidos do Omega-Serv*) apenas se o magnet estiver ativo; o `lnav`, por outro lado, sempre os propõe (um arquivo ausente é simplesmente ignorado na abertura).

### 13a. Origens remotas (SSH)

Centraliza, mediante pedido explícito, o log de um servidor backend situado na mesma rede local atrás do reverse proxy (tela **Gerenciamento de logs → Biblioteca → Origens remotas (SSH)**). Um « fetch » é uma ação manual e pontual, nunca um fluxo ao vivo nem uma consulta automática: uma **cópia** é recuperada via `scp` no momento do clique em *Recuperar agora*, gravada em `var/log/remote/` e depois adicionada à Biblioteca como um log comum (coluna *Acesso* = `ssh`, coluna *Modificado* = data **desta** recuperação — nunca a do arquivo remoto); uma nova recuperação simplesmente substitui a cópia anterior por uma mais recente.

Salvaguardas deliberadas (veja `OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md` para o estudo completo): nenhuma varredura de rede automática, nenhuma conexão sem configuração explícita (rótulo/host/caminho remoto, usuário/porta/chave privada opcionais — vazios, deixam o `ssh`/`~/.ssh/config` decidir como se o comando fosse digitado à mão), nenhuma senha jamais pedida nem armazenada (uma chave privada é referenciada apenas pelo seu caminho, nunca lida nem armazenada pelo Omega-serv), nenhuma verificação de tamanho antes da transferência. Capacidade `scp` detectada localmente no **Registro de capacidades** (apenas a presença do binário, nunca um teste de acessibilidade de um host); Samba deixado de lado explicitamente (YAGNI, enquanto nenhuma necessidade real for confirmada).

## 14. Testes

```bash
source .venv/bin/activate
lint-imports        # verifica os 8 contratos de camadas
pytest -q           # 2485 testes
ruff check .
mypy src
```

Estrutura: `tests/unit/` (domínio/aplicação, dublês de teste), `tests/integration/` (servidor asyncio real sobre sockets TCP reais, `openssl` real como subprocesso, comandos CLI reais contra um projeto temporário completo, interface interativa via a API `Pilot` do Textual - nunca uma captura de tela), `tests/security/` (testes baseados em propriedades `hypothesis` sobre o parser HTTP e o resolvedor de caminhos).

## 15. Fora do escopo

- CGI bruto (apenas FastCGI/PHP-FPM)
- mTLS (autenticação de cliente por certificado), OCSP stapling
- CA externa / CSR para autoridade de terceiros, distribuição completa de CRL
- Active Defense: integração real com os eventos de banimento do `omega-fire` (bloqueada do lado do `omega-fire`, que hoje não expõe nenhuma superfície de leitura)

---

> 🔒 OMEGA-SERV — Um servidor web sólido, completo, seguro e defensivo.

# omega-serv diante dos servidores web do mercado — versão gráfica

**omega-serv diante de nginx · lighttpd · Apache · Caddy · Traefik — medições em três máquinas (nov. 2026).**

🌐 [Français](../../comparatif-server-web-graphique.md) · [English](../en/comparatif-server-web-graphique.md) · [Español](../es/comparatif-server-web-graphique.md) · **Português (Brasil)** · [Italiano](../it/comparatif-server-web-graphique.md) · [Deutsch](../de/comparatif-server-web-graphique.md) · [Nederlands](../nl/comparatif-server-web-graphique.md) · [Polski](../pl/comparatif-server-web-graphique.md) · [Русский](../ru/comparatif-server-web-graphique.md) · [中文](../zh-CN/comparatif-server-web-graphique.md) · [Tiếng Việt](../vi/comparatif-server-web-graphique.md) · [ไทย](../th/comparatif-server-web-graphique.md) · [Bahasa Indonesia](../id/comparatif-server-web-graphique.md) · [日本語](../ja/comparatif-server-web-graphique.md) · [한국어](../ko/comparatif-server-web-graphique.md) · [हिन्दी](../hi/comparatif-server-web-graphique.md) · [العربية](../ar/comparatif-server-web-graphique.md)

> **Leitura:** quanto mais longa a barra, mais rápido o servidor. A referência é **nginx = 1,00**.

## Legenda das cores

<!-- 🖼️ IMAGE : legende-couleurs -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-1.png" alt="Légende des couleurs" width="1024">
</div>

---

## 📊 Arquivos de 1 KB — vazão (requisições/s)

Máquinas A (i5 2010), B (Celeron 2016) e C (Ryzen 2024). As barras são normalizadas em relação ao nginx (1,00) na mesma máquina.

<!-- 🖼️ IMAGE : 1ko-banner — 3 colonnes côte à côte (Machine A · 2 cœurs | Machine B · 4 cœurs | Machine C · 10 cœurs), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-2.png" alt="Fichiers 1 Ko — machines A, B et C" width="1024">
</div>

> \* Máquina C: o motor nativo usa 4 núcleos, o nginx 2 processos (2 núcleos). Com o mesmo número de núcleos, a razão cai para ~0,70.
---

## 📦 Arquivos médios (100 KB) — modo web normal

Aqui o Apache surpreende: muitas vezes ultrapassa o motor nativo do omega-serv. O lighttpd continua sendo o mais rápido. Referência: nginx = 1,00.

<!-- 🖼️ IMAGE : 100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-3.png" alt="Fichiers 100 Ko — machines A, B et C" width="1024">
</div>

---

## 💿 Arquivos grandes (5 MB) — modo web normal

Nos arquivos grandes, os servidores se equiparam: é o kernel que copia os dados (sendfile). O Caddy é a exceção na máquina C. Vazão em MB/s.

<!-- 🖼️ IMAGE : 5mo-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-4.png" alt="Fichiers 5Mo — machines A, B et C" width="1024">
</div>

---

## 🔄 Proxy reverso — respostas pequenas (1 KB)

Cada proxy repassa para um backend nginx. Referência: nginx = 1,00. Máquina C: 4 processos.

<!-- 🖼️ IMAGE : proxy-1ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-5.png" alt="Proxy 1 Ko — machines A, B et C" width="1024">
</div>

---

## 🔄 Proxy reverso — respostas de 100 KB

Nas respostas médias, o omega-serv nativo empata com o nginx ou o ultrapassa.

<!-- 🖼️ IMAGE : proxy-100ko-banner.png — 3 colonnes côte à côte (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-6.png" alt="Proxy 100 Ko — machines A, B et C" width="1024">
</div>

---

## 💾 Memória (PSS) — em repouso → após a carga

Quanto mais curta a barra, mais econômico o servidor. lighttpd, nginx e Apache são os mais sóbrios; omega-serv 3.0.0 (medido novamente em 19 de novembro) vem em seguida, com 10 a 16 MB para o motor nativo.

<!-- 🖼️ IMAGE : memoire-banner.png — 3 colonnes côte à côte de jauges (A | B | C), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-7.png" alt="Mémoire — machines A, B et C" width="1024">
</div>

---

## 🏆 Classificação web normal — quem é o mais rápido?

Síntese das três máquinas servindo arquivos estáticos.

<!-- 🖼️ IMAGE : classement-web.png -->
<!-- Contenu : 1. 🥇 lighttpd — meilleur en petits & moyens fichiers · 2. 🥈 nginx — référence, excellent partout · 3. 🥉 Apache — bon, robuste, écosystème · 4. omega-serv natif — très bon, 2ᵉ en reverse proxy · 5. Caddy — simple, HTTPS auto · 6. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-8.png" alt="Classement web normal" width="1024">
</div>

---

## 🔄 Classificação proxy reverso — quem é o melhor?

O nginx continua sendo a referência; o omega-serv nativo é o seu vice mais próximo, bem à frente dos demais.

<!-- 🖼️ IMAGE : classement-proxy.png -->
<!-- Contenu : 1. 🥇 nginx · 2. 🥈 omega-serv natif — 0,82 à 0,91× nginx en 1 Ko · 3. 🥉 omega-serv + WAF — toujours devant lighttpd/Apache · 4. lighttpd — 0,53 à 0,61× · 5. Apache — 0,50 à 0,59× · 6. Traefik — 0,29 à 0,35× · 7. Caddy — 0,23 à 0,32× · 8. omega-serv Python — moteur de repli -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-9.png" alt="Classement reverse proxy" width="1024">
</div>

---

## 🆚 Frente a frente — classificações web e proxy reverso lado a lado

Dois usos, duas classificações. Um servidor pode brilhar em uma e decepcionar na outra: o Apache surpreende no repasse, o Caddy decepciona em tudo, exceto pela simplicidade.

<!-- 🖼️ IMAGE : face-a-face.png — 2 colonnes côte à côte (web | proxy), largeur totale -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/pt-BR/omega-serv/stats-10.png" alt="Face à face web vs reverse proxy" width="1024">
</div>

### Síntese cruzada

| Servidor | Posicionamento |
|---|---|
| 🟢 **omega-serv nativo** | O mais versátil: 4º em web, **2º em proxy reverso**. Único servidor com WAF integrado que continua à frente de lighttpd e Apache no repasse. O melhor compromisso para uma única ferramenta que cubra os dois usos, com segurança a mais. |
| 🔵 **nginx** | O mais regular: 2º em web, **1º em proxy reverso**. Sempre no topo da classificação, sem ponto fraco marcante. A escolha padrão sem exigência particular. |
| 🟢 **lighttpd** | O velocista do estático: **1º em web**, mas 4º no repasse. Melhor escolha para estático puro, cede lugar ao omega-serv ou ao nginx assim que se acrescenta proxy reverso. |
| 🔴 **Apache** | O contraexemplo: 3º em web, 5º no repasse. Nos arquivos grandes, surpreende até o nginx (máquina C). Nem o mais rápido nem o mais leve: seu trunfo continua sendo o ecossistema PHP. |
| 🟠 **Caddy** | A simplicidade antes da velocidade: 5º em web, **7º no repasse**. Não foi feito para vazão: HTTPS automático e configuração curta. Para reservar a projetos pequenos. |
| 🟣 **Traefik** | Fora da categoria web: não é servidor de arquivos, 6º no repasse. Seu terreno continua sendo Docker e Kubernetes, não o desempenho bruto. |

---

## 📋 Tabela recapitulativa completa — razões em relação ao nginx (1,00)

Visão geral de **todas** as métricas: modo web normal (1 KB, 100 KB, 5 MB) e proxy reverso (1 KB, 100 KB), mais a memória. Quanto mais o valor se aproxima de 1,00 ou o supera, melhor.

| Servidor | Web 1 KB (A/B/C) | Web 100 KB (A/B/C) | Web 5 MB (A/B/C) | Proxy 1 KB (A/B/C) | Proxy 100 KB (A/B/C) | Memória (A/B/C) |
|---|---|---|---|---|---|---|
| **lighttpd** | 1,52 / 1,26 / 1,53 | 1,08 / 1,07 / 1,26 | 1,05 / 0,99 / 0,81 | 0,61 / 0,56 / 0,53 | 0,74 / 0,62 / 0,96 | 1 MB |
| **nginx** | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 1,00 / 1,00 / 1,00 | 4–5 MB |
| **omega-serv (nativo)** | **0,70 / 0,67 / 1,15\*** | **0,38 / 0,28 / 0,61** | **0,99 / 0,91 / 1,09** | **0,85 / 0,91 / 0,82** | **1,11 / 0,97 / 1,43** | 10–16 MB |
| **omega-serv + WAF** | 0,56 / 0,53 / 1,07\* | 0,37 / 0,27 / 0,62 | — | 0,81 / 0,89 / 0,77 | 1,10 / 0,93 / 1,30 | 28–33 MB |
| **Apache** | 0,42 / 0,35 / 0,76 | 0,55 / 0,62 / 0,97 | 1,01 / 1,00 / 1,19 | 0,59 / 0,53 / 0,50 | 0,62 / 0,65 / 0,71 | 4–9 MB |
| **Caddy** | 0,26 / 0,17 / 0,21 | 0,40 / 0,33 / 0,14 | 0,95 / 0,94 / 0,11 | 0,32 / 0,28 / 0,23 | 0,60 / 0,54 / 0,59 | 46–67 MB |
| **Traefik** | — | — | — | 0,35 / 0,35 / 0,29 | 0,64 / 0,60 / 0,70 | 93–131 MB |
| **omega-serv (Python)** | 0,11 / 0,05 / 0,08 | 0,14 / 0,10 / 0,12 | 0,92 / 0,91 / 0,75 | 0,09 / 0,08 / 0,07 | 0,21 / 0,19 / — | 20–48 MB |

> \* Máquina C: 4 núcleos para o nativo contra 2 para o nginx; com o mesmo número de núcleos, razão ~0,67–0,71.
> Os três valores por célula correspondem às máquinas **A / B / C**. «—»: não medido ou não aplicável.

---

## ⚖️ Pontos fortes e fracos — todos os servidores

Cada servidor tem seus trunfos e seus limites. Eis a visão completa, sem favoritismo.

### 🟢 omega-serv (nativo)

**Pontos fortes**
- ✅ Administração completa no terminal (TUI, 17 idiomas)
- ✅ WAF + Active Defense + RIPOSTE integrados
- ✅ Motor nativo C++: ~0,7× nginx em estático
- ✅ 2º em proxy reverso, atrás do nginx
- ✅ Limites compartilhados entre processos (segurança exata)
- ✅ Importação de scripts lighttpd mod_magnet
- ✅ Gerenciamento de várias instâncias
- ✅ Administração web


**Pontos fracos**
- ❌ Sem HTTP/2 nem HTTP/3
- ❌ Sem compressão em tempo real
- ❌ Sem descoberta Docker/Kubernetes
- ❌ ACME via Certbot (não integrado nativamente)
- ❌ Arquivos de 100 KB: 0,3–0,6× nginx
- ❌ Memória 10–55 MB conforme o modo (vs 1–5 MB nginx/lighttpd)
- ❌ Ecossistema jovem, mantido por uma pessoa

---

### 🔵 nginx

**Pontos fortes**
- ✅ Referência de desempenho e estabilidade
- ✅ HTTP/2, HTTP/3, compressão
- ✅ Ecossistema imenso (módulos, documentação, comunidade)
- ✅ Muito econômico em memória (4–5 MB)
- ✅ Excelente proxy reverso
- ✅ Módulo ACME oficial
- ✅ Configuração madura e comprovada

**Pontos fracos**
- ❌ Configuração verbosa, sintaxe própria a aprender
- ❌ Sem WAF integrado (exige ModSecurity ou equivalente)
- ❌ Sem interface de administração nativa
- ❌ Recarga de configuração às vezes delicada em produção
- ❌ Versão de código aberto limitada (algumas funções no Nginx Plus pago)
- ❌ Sem descoberta Docker/Kubernetes nativa (via templates)

---

### 🟢 lighttpd

**Pontos fortes**
- ✅ O mais rápido em arquivos pequenos/médios
- ✅ O mais econômico em memória (1 MB)
- ✅ Leve, adequado a sistemas restritos
- ✅ Bom proxy reverso
- ✅ Configuração simples e legível

**Pontos fracos**
- ❌ Sem HTTP/3 (HTTP/2 parcial conforme o build)
- ❌ Apenas 4º em proxy reverso (0,53–0,61× nginx)
- ❌ Ecossistema mais restrito que nginx/Apache
- ❌ Sem WAF integrado
- ❌ Sem descoberta Docker/Kubernetes
- ❌ Desenvolvimento menos ativo que no passado
- ❌ Fraco em arquivos grandes (0,81× nginx na máquina C)

---

### 🔴 Apache

**Pontos fortes**
- ✅ Ecossistema histórico imenso (módulos, `.htaccess`, PHP)
- ✅ Robusto e comprovado há décadas
- ✅ Excelente em arquivos grandes (ultrapassa o nginx na máquina C)
- ✅ Suporte a `.htaccess` sem reinicialização
- ✅ Compressão, HTTP/2, ACME disponíveis
- ✅ Documentação abundante

**Pontos fracos**
- ❌ Lento em arquivos pequenos (0,35–0,42× nginx)
- ❌ Exigente em memória no modo prefork (4–9 MB, sobe rápido sob carga)
- ❌ Modelo de processos menos eficiente que o orientado a eventos
- ❌ Configuração verbosa
- ❌ 5º em proxy reverso (0,50–0,59× nginx)
- ❌ Sem WAF integrado (ModSecurity em módulo separado)
- ❌ Superfície de ataque historicamente maior

---

### 🟠 Caddy

**Pontos fortes**
- ✅ HTTPS automático (ACME integrado, zero configuração)
- ✅ Configuração muito curta e legível (Caddyfile)
- ✅ HTTP/2 e HTTP/3 nativos
- ✅ Binário único, implantação simples
- ✅ Proxy reverso razoável em respostas médias

**Pontos fracos**
- ❌ Lento em vazão bruta (5º em web, 7º no repasse)
- ❌ Memória elevada (46–67 MB)
- ❌ Muito fraco em arquivos grandes na máquina C (0,11× nginx)
- ❌ Sem WAF integrado
- ❌ Ecossistema mais jovem que nginx/Apache
- ❌ Pouco adequado a vazões muito altas

---

### 🟣 Traefik

**Pontos fortes**
- ✅ Descoberta automática Docker/Kubernetes
- ✅ Ideal em ambiente de contêineres
- ✅ HTTPS automático (ACME integrado)
- ✅ Configuração dinâmica sem reinicialização
- ✅ Bom em proxy reverso em respostas médias (0,60–0,70× nginx)

**Pontos fracos**
- ❌ Não é servidor de arquivos (ausente da classificação web)
- ❌ 6º em proxy reverso (0,29–0,35× nginx em 1 KB)
- ❌ Memória muito elevada (93–131 MB)
- ❌ Complexidade de configuração fora do contexto de contêineres
- ❌ Sem WAF integrado
- ❌ Superdimensionado para um simples site estático

---

## 🎯 Qual servidor para qual uso?

| Uso | Servidor recomendado | Motivo |
|---|---|---|
| Site de alto tráfego | **nginx** ou **lighttpd** | Vazão máxima, HTTP/2-3 |
| Máquina restrita / embarcado | **lighttpd** | 1 MB de memória, o mais rápido e o menos exigente |
| HTTPS automático simples | **Caddy** | Certificados automáticos, configuração curta |
| Docker / Kubernetes | **Traefik** | Descoberta de serviços |
| Aplicação PHP / .htaccess | **Apache** | Ecossistema histórico |
| Proxy reverso | **nginx** ou **omega-serv (nativo)** | Melhor desempenho |
| Sites web + segurança + interface | **omega-serv (nativo)** | Infraestrutura completa: WAF, administração web, multi-instância, proxy reverso, gerenciador de logs, backups... |

---

Dados do comparativo omega-serv (novembro de 2026) — kraynux. Licença MIT.
[oha](https://github.com/hatoo/oha) para a medição · gráficos HTML/CSS autônomos.

> *Versão gráfica do comparativo medido do omega-serv (mesmos números do comparativo detalhado: medições de 3 e 4 de novembro de 2026 em três máquinas; proxy reverso: 14 de novembro de 2026; memória do omega-serv 3.0.0: 19 de novembro de 2026). Para qualquer decisão de capacidade, meça no seu próprio hardware.*
>
> Copyright © 2026 kraynux — kraynux@proton.me — Licença MIT (ver arquivo LICENSE).

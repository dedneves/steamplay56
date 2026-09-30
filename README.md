<div align="center">

# StemPlay Library — v13 (Steamplay 2)


[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=for-the-badge&logo=python&logoColor=white)]()
[![Platform](https://img.shields.io/badge/Plataforma-Linux%20%7C%20Windows-success?style=for-the-badge)]()
[![License](https://img.shields.io/badge/Licença-MIT-orange?style=for-the-badge)]()


</div>

---

##  Features

| Feature | Descrição |
|---------|-----------|
|  **Reader embutido "Steamplay 2"** | Leia o PDF dentro do próprio site, sem sair |
|  **Desenho no PDF** | Caneta, marca-texto, borracha, cores, espessura, desfazer, limpar página |
|  **Notas adesivas** | Arraste o botão "Nota" para a página: bloco que move, redimensiona, recolhe e anota |
|  **Sincronização de anotações** | Salva em nuvem por `userId` + SHA-256 do PDF (e local como fallback); idêntico no http/https |
|  **Acesso por ID** | Qualquer ID entra; só IDs autorizados veem os livros do professor (Teacher) |
|  **Zoom ajustável** | +/− e "Ajustar" (largura da tela) |
|  **Acessar Online** | Índice em tempo real do bucket S3 |
|  **Download** | Baixe o PDF com um clique (ou lote por curso) |
|  **Busca Inteligente** | Encontre por curso, aula, módulo ou unidade |
|  **Filtros** | Filtre por tipo: Padrão, Teacher, Workbook, Student |
|  **Favoritos** | Salve seus materiais favoritos (persiste no navegador) |
|  **Dark/Light Mode** | Alterne entre temas claro e escuro |
|  **Mobile-First** | Interface otimizada para celular com bottom nav |
|  **Rede Local** | Acesse de qualquer dispositivo no mesmo Wi-Fi |
|  **QR Code** | Escaneie e acesse instantaneamente pelo celular |
|  **Duas Portas** | Servidor local (8000) e de rede (8080) separados |
|  **Banimento (PC e Android)** | Bloqueia o IP e derruba a conexão na hora |
|  **Proxy seguro /pdf** | Leitura do S3 via servidor sem expor arquivos locais |

---

##  Segurança / Privacidade

- O servidor **não serve mais a pasta inteira**: só a biblioteca (`/`), o heartbeat
  (`/__hb`) e o proxy do bucket (`/pdf?key=...`, restrito ao bucket `stemplay-videos`).
- O bloqueio de IP agora é **imediato**: conexões abertas do IP banido são fechadas
  e o heartbeat (4 s) mostra a tela "Acesso bloqueado" para quem já estava dentro.

---

##  Início Rápido

###  Windows

> **Dica:** Basta dar **duplo clique** em `start.bat` — ele faz tudo sozinho!

1. Instale o [Python 3.8+](https://www.python.org/downloads/)
   -  **Marque "Add Python to PATH"** durante a instalação
2. Baixe/clone este repositório
3. Dê duplo clique em **`start.bat`**
4. O terminal vai mostrar:
   -  As etapas de inicialização
   -  URL local (porta `8000`)
   -  URL de rede (porta `8080`)
   -  **QR Code** para escanear com o celular
5. Acesse pelo navegador ou escaneie o QR Code

###  Comandos do launcher (PC/CLI)

Digite no terminal **enquanto o servidor roda**:

| Comando | Efeito |
|---------|--------|
| `ls` | Lista visitantes ativos (IP, página, nº de requests) |
| `ban <ip>` | **Banimento imediato**: bloqueia o IP e fecha as conexões dele |
| `unban <ip>` | Libera o IP |
| `bans` | Lista os IPs bloqueados |
| `ajuda` | Mostra os comandos |
| `sair` | Encerra os servidores |

###  Linux

```bash
# 1. Clone o repositório
git clone https://github.com/dedneves/stemplay-library.git
cd stemplay-library

# 2. Dê permissão de execução
chmod +x start.sh

# 3. Rode
./start.sh
```

###  Android (app servidor)

- Fonte em `stemplay-android/` — build: `build_apk.bat` (usa JDK 17 do
  Android Studio, se necessário) e `adb install -r app-debug.apk`.
- Correções desta versão:
  - não crasha mais ao iniciar (foreground service sobe a notificação antes,
    com `FOREGROUND_SERVICE_SPECIAL_USE` + subtipo declarados);
  - porta 8080 com fallback automático se estiver ocupada;
  - detecção de IP para mais interfaces (não só `wlan0`);
  - bloqueio derruba conexões na hora + heartbeat no reader;
  - proxy `/pdf` próprio, mesma interface web com o reader Steamplay 2.

---

##  Reader "Steamplay 2" (dentro do site)

- Topo com marca **Steamplay 2**, título do arquivo, status de sincronização (☁).
- Ferramentas: **Caneta**, **Marca-texto**, **Borracha**, **5 cores**, **espessura**,
  **Desfazer**, **Limpar página**. Não há mais botão "Mover" nem "PNG".
- Sem ferramenta ativa você apenas rola/na zera com **+/−** e **Ajustar**. Para
  parar de desenhar, toque de novo na ferramenta ativa (ela desliga).
- **Notas adesivas**: toque ou **arraste o botão "✚ Nota"** até a página → nasce um
  bloco que você **move** (pelo cabeçalho), **redimensiona** (canto inferior),
  **recolhe** (—) e **exclui** (✕). O texto fica salvo por página.
- Atalhos: `←`/`→` trocam página, `Ctrl+Z` desfaz traço, `Esc` fecha o reader.
- Persistência: local (`localStorage`) **e** nuvem (`Annotations/<userId>/<sha256>`),
  com chave SHA-256 **idêntica no http e no https** (fallback em JS puro quando o
  navegador não expõe `crypto.subtle` em contexto inseguro) — compatível com o
  backend que o reader.stemplay.io já usava.

---

##  Acesso por ID

**Qualquer ID entra** na biblioteca. Porém os **livros do professor** (tipo
`Teacher` de cada curso) só aparecem para os IDs da lista `IDS_PROFESSOR`
no template (padrão: `TIA ISA E A MELHOR` e `1A2B3C`, comparação sem
diferenciar maiúsculas). Para os demais, os Teacher somem das listas, da
busca, dos favoritos, do download em lote e do chip de filtro.

O ID atual fica num **chip "ID: ..." no topo** — toque nele para trocar de ID.

Para adicionar/remover professores, edite a linha
`const IDS_PROFESSOR=[...]` em `generate_library_premium.py` e regenere.

---

##  Terminal do launcher (PC)

O painel de visitantes agora é **por log** (só imprime quando alguém entra/sai ou
quando a lista de banidos muda) e não reposiciona o cursor — por isso digitar um
comando **não duplica mais** a lista de IPs.

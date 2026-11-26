<h1 align="center">🤖 Bit · Claude Pet</h1>

<p align="center">
  <strong>Um robozinho de pixel que mora nas bordas da sua tela e mostra o que o <a href="https://claude.com/claude-code">Claude Code</a> está fazendo.</strong><br>
  Pare de trocar de janela pra ver se o terminal terminou. É só olhar pro Bit.
</p>

<p align="center">
  <a href="README.md">🇺🇸 English</a> ·
  <strong>🇧🇷 Português</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white">
  <img alt="GTK" src="https://img.shields.io/badge/GTK-3-4A86CF?logo=gtk&logoColor=white">
  <img alt="X11" src="https://img.shields.io/badge/Linux-X11-FCC624?logo=linux&logoColor=black">
  <img alt="Windows" src="https://img.shields.io/badge/Windows-10%2F11%20(beta)-0078D6?logo=windows&logoColor=white">
  <img alt="Claude Code hooks" src="https://img.shields.io/badge/Claude%20Code-hooks-D97757">
  <img alt="Zero pip" src="https://img.shields.io/badge/pip%20install-nenhum-success">
</p>

<p align="center">
  <img src="docs/hero.gif" alt="Bit ocioso, pensando, trabalhando, pedindo atenção e comemorando" width="600">
</p>

---

## 💡 Por que usar

Você manda o prompt, o Claude Code começa a trabalhar e você vai fazer outra coisa. Aí começa o ciclo:

- 👀 Troca pro terminal pra ver se terminou
- ⏳ Ainda está pensando, você volta
- 🙋 Enquanto isso ele estava **esperando sua permissão** há 10 minutos
- 🔁 Repete, o dia inteiro

✨ **O Bit resolve isso.** Ele anda pelas bordas da tela, e a animação (e a cor da antena) mostra o status de relance:

| | Estado | O que o Bit faz |
|---|---|---|
| <img src="docs/states/idle.gif" width="72"> | **De boa** | Passeia pelo chão, paredes e teto. Senta, pisca, cochila depois de um tempo |
| <img src="docs/states/thinking.gif" width="72"> | **Pensando** (logo depois do seu prompt) | Mão no queixo, nuvem de pensamento em cima da cabeça 🔵 |
| <img src="docs/states/working.gif" width="72"> | **Trabalhando** (rodando uma ferramenta) | Senta e digita no notebookzinho 🟡 |
| <img src="docs/states/attention.gif" width="72"> | **Precisa de você** (pedido de permissão) | Pula, acena e mostra um balão com o que o Claude quer 🔴 |
| <img src="docs/states/done.gif" width="72"> | **Terminou** | Comemora e fica esperando com um ✓ até você passar o mouse ou clicar nele 🟢 |
| <img src="docs/states/sleeping.gif" width="72"> | **Dormindo** | 3 minutos sem atividade: zzz |
| <img src="docs/states/dragged.gif" width="72"> | **Agarrado** | Fica pendurado e balança como um pêndulo enquanto você arrasta |

> **Seu terminal não precisa mais estar na tela. O Bit está.**

### 🐾 Escolha seu bichinho

Não curtiu robô? Botão direito → **Personagem**. Todos fazem tudo que o Bit faz (andar no teto, pensar, digitar, pedir atenção, comemorar, dormir, balançar no arraste) e mostram o status pela cor de um detalhe:

| | Personagem | Onde fica a "luzinha" do status |
|---|---|---|
| <img src="docs/chars/robo.gif" width="300"> | **Bit**, o robô | Antena |
| <img src="docs/chars/lagartixa.gif" width="300"> | **Lagartixa**, a que mais combina com andar na parede | Pintinhas nas costas |
| <img src="docs/chars/gosminha.gif" width="300"> | **Gosminha**, pulinhos de gelatina | Bolhinha dentro da gosma |
| <img src="docs/chars/capivara.gif" width="300"> | **Capivara**, zen até o Claude precisar de você | Frutinha na cabeça |
| <img src="docs/chars/pato.gif" width="300"> | **Patinho**, gingando de cachecol | Cachecol no pescoço |
| <img src="docs/chars/dragao.gif" width="300"> | **Dragão**, levanta voo e fica voando pela tela enquanto o Claude trabalha | Brasa no peito (e o fogo) |
| <img src="docs/chars/pato_confuso.gif" width="300"> | **Pato Pistola**, sempre meio perdido, com um cacho em "?" que espeta num "!" quando o Claude precisa de você | Tela do notebook |
| <img src="docs/chars/pato_cachecol.gif" width="300"> | **Pato de Cachecol**, patinho dourado e gordinho de cachecol azul, feito a partir de uma folha de sprites; de vez em quando fica confuso, de olho em espiral | Sem luzinha: cada estado tem a sua cena |
| <img src="docs/chars/capivara_dev.gif" width="300"> | **Capivara Dev**, de fone, óculos e notebook, também de folha de sprites | Sem luzinha: cada estado tem a sua cena |

Os personagens de folha de sprites passam de um quadro pro outro com uma transição suave (crossfade). Prefere quadro a quadro? Botão direito → **Animação** → **Quadro a quadro** (a escolha é de cada personagem). Pra criar um a partir da sua própria folha, veja `tools/folha_para_pet.py`.

---

## ✨ Recursos

| | |
|---|---|
| 🎯 **Status ao vivo** | Vem dos hooks do Claude Code: prompt, ferramentas, pedidos de permissão, fim |
| 🖱️ **Clique pra voltar** | Quando ele pede algo ou termina, um clique traz a janela do terminal certo pra frente |
| 💬 **Balões de fala** | Balõezinhos em pixel art: *"Claude Code terminou. Clique em mim para abrir"* |
| 🧮 **Vários chats** | Mostra o mais urgente; passando o mouse, um resumo em uma linha (*"Bit: 1 chat trabalhando, 2 chats de boa"*) |
| 🧗 **Anda por tudo** | Chão, paredes e teto do monitor, respeitando a dock e a barra do topo |
| 🤹 **Física** | Arraste e arremesse, ele cai de volta no chão. Balança como pêndulo enquanto você segura. Jogado contra a borda que encosta em outro monitor, atravessa pra ele |
| 💤 **Humores** | Repara no seu cursor, gosta de carinho ❤, dorme quando nada está acontecendo |
| 😈 **Modo troll** | Desligado por padrão; liga pelo menu. De vez em quando ele rouba o cursor e sai correndo com ele, ou se pendura nele e deixa o mouse pesado. Nunca com botão do mouse apertado nem quando o Claude precisa de você, e um puxão forte faz ele largar |
| 👻 **Nunca atrapalha** | O clique atravessa tudo menos o próprio Bit. Dá pra esconder por 30 min ou 2 h no menu |
| 🧹 **Se limpa sozinho** | Sessões cujo processo `claude` morreu são esquecidas automaticamente |
| 🪶 **Leve** | Biblioteca padrão + o GTK que já vem no seu desktop. Só redesenha quando o quadro muda |

---

## 📦 Instalação

### ⚡ Jeito rápido (uma linha)

```bash
mkdir -p ~/.local/share && curl -fsSL https://github.com/krugerrgabriel/claude-pet/releases/latest/download/claude-pet.tar.gz | tar xz -C ~/.local/share && python3 ~/.local/share/claude-pet/install.py && ~/.local/bin/claude-pet &
```

Baixa a última [release](https://github.com/krugerrgabriel/claude-pet/releases/latest) em `~/.local/share/claude-pet`, instala os hooks e o atalho, e já chama o pet. **Pra atualizar, é o mesmo comando** (depois feche o pet pelo menu e chame `claude-pet` de novo). Pra remover: `python3 ~/.local/share/claude-pet/install.py --uninstall`.

### 🪟 No Windows (beta)

Precisa do Python 3 do [python.org](https://www.python.org/downloads/) ou do winget (`winget install Python.Python.3.12`), que já vem com o Tk. No PowerShell:

```powershell
$z="$env:TEMP\claude-pet.zip"; irm https://github.com/krugerrgabriel/claude-pet/releases/latest/download/claude-pet.zip -OutFile $z; Expand-Archive $z $env:LOCALAPPDATA -Force; py "$env:LOCALAPPDATA\claude-pet\install.py"
```

Baixa a última release em `%LOCALAPPDATA%\claude-pet`, instala os hooks, cria o atalho **Claude Pet** no Menu Iniciar e na Inicialização (abre sozinho quando você entra no Windows) e já abre o pet. **Pra atualizar, é o mesmo comando.** Pra remover: `py "$env:LOCALAPPDATA\claude-pet\install.py" --uninstall`.

No Windows a janela é feita com Tk em vez de GTK, mas o desenho, os personagens e o comportamento são os mesmos. Clicar no pet traz pra frente o Windows Terminal, o console ou o VS Code onde a sessão está.

### 🛠️ Ou pelo código-fonte

### 1️⃣ Clone o repositório

```bash
git clone https://github.com/krugerrgabriel/claude-pet.git
cd claude-pet
```

### 2️⃣ Rode o instalador

```bash
python3 install.py
```

Ele adiciona os hooks do Bit no `~/.claude/settings.json` (fazendo backup antes e sem mexer nos seus outros hooks), cria o comando `claude-pet` e faz o Bit abrir sozinho quando você faz login.

### 3️⃣ Chame o Bit

```bash
claude-pet &
```

Pronto. 🎉 Abra uma sessão nova do Claude Code e veja ele em ação.

> 💡 **Reinicie as sessões do Claude Code que já estavam abertas**: os hooks só são lidos quando a sessão começa.

> 💡 **Pré-requisitos:** Linux com **X11** (testado no Ubuntu/GNOME), com `python3-gi` e `python3-gi-cairo`, que a maioria dos desktops já tem. O `wmctrl` é opcional e habilita o clique pra focar o terminal: `sudo apt install wmctrl`.

---

## 🖱️ Interagindo com o Bit

| Ação | O que acontece |
|---|---|
| **Clique** (quando ele pede algo ou terminou) | Foca o terminal daquela sessão e limpa o ✓ |
| **Clique** (em qualquer outro momento) | Ele fica feliz |
| **Passar o mouse** | Status em uma linha: *"Bit está trabalhando (Bash)"* |
| **Passar o mouse** (mesmo rapidinho) pelo bichinho ou pelo balão, quando terminou | Dispensa o balão de "terminou" e o ✓ (um clique logo depois ainda abre o terminal) |
| **Deixar o mouse parado em cima** | Carinho ❤ |
| **Arrastar e soltar** | Pega ele, balança, arremessa (até pro outro monitor) |
| **Botão direito** | Lista de chats (clique pra focar), **Personagem**, **Mudar nome…**, **Idioma** (automático, português ou inglês), **Botar pra dormir** (dorme até o seu próximo prompt ou um pedido de permissão), esconder por 30 min / 2 h, sair |

---

## ⚙️ Configuração avançada

Só se quiser: tudo funciona sem configurar nada.

<details>
<summary><strong>Ajustar o Bit (<code>~/.config/claude-pet/config.json</code>)</strong></summary>

```json
{
  "skin": "robo",
  "pet_name": "",
  "language": "auto",
  "scale": 3,
  "body_color": "#5ec4b6",
  "walk_speed": 45,
  "climb_chance": 0.25,
  "sleep_after": 180,
  "done_linger": 900,
  "monitor": -1
}
```

| Chave | Significado |
|---|---|
| `skin` | Personagem: `robo`, `lagartixa`, `gosminha`, `capivara`, `pato`, `dragao`, `pato_confuso`, `pato_cachecol` ou `capivara_dev` (o menu grava aqui) |
| `smooth_anim` | Animação suave por personagem de folha de sprites: `{"pato_cachecol": false}` = quadro a quadro; o menu **Animação** grava aqui |
| `pet_name` | Nome usado nos balões (vazio = "Seu pet"; o menu **Mudar nome…** grava aqui) |
| `language` | `auto` (segue o idioma do sistema), `pt` ou `en`; o menu **Idioma** grava aqui |
| `scale` | Tamanho de cada pixel do sprite (3 ≈ 60 px de altura) |
| `body_color` | Qualquer cor pro corpo do Bit (só o robô) |
| `walk_speed` | Pixels por segundo |
| `climb_chance` | Frequência com que ele sobe paredes e teto (0 = nunca) |
| `sleep_after` | Segundos sem atividade até ele cochilar |
| `done_linger` | Segundos que o "terminou ✓" fica se você não clicar |
| `work_hold` | Segundos mínimos em "trabalhando" depois de uma ferramenta, pra não ficar piscando entre pensar e trabalhar (padrão 5) |
| `monitor` | Índice do monitor, `-1` = principal |
| `confused_every` | Personagens com animação de confuso (Pato de Cachecol): em média a cada tantos segundos ele larga o que está fazendo e fica confuso (padrão 80; nunca dormindo; `0` desliga) |

Todas as chaves são opcionais. Reinicie o Bit depois de editar.
</details>

<details>
<summary><strong>Desinstalar</strong></summary>

```bash
python3 install.py --uninstall
```

Remove só os hooks do Bit (com backup do `settings.json` antes), o comando `claude-pet` e a entrada de autostart.
</details>

---

## 🏗️ Como funciona por dentro

```
┌──────────────────┐   hook (JSON no stdin)   ┌──────────────────────────────┐
│   Claude Code    │ ───────────────────────▶ │  hooks/claude_pet_hook.py    │
│  (cada sessão)   │  prompt · tool · stop …  │  só stdlib, nunca falha      │
└──────────────────┘                          └──────────────┬───────────────┘
                                                             │ grava
                                                             ▼
                                   ~/.cache/claude-pet/sessions/<sessão>.json
                                                             │ lido a cada 250 ms
                                                             ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ claude_pet/                                                                │
│   state.py      resume todas as sessões, timeouts, prioridade              │
│   character.py  movimento, física, pêndulo, máquina de estados (sem GTK)   │
│   sprites.py    o Bit desenhado pixel a pixel, todas as animações          │
│   window.py     janela GTK transparente sempre por cima, balão, menu       │
│   focus.py      traz o terminal da sessão pra frente (wmctrl)              │
└────────────────────────────────────────────────────────────────────────────┘
```

| Evento do Claude Code | Bit |
|---|---|
| `SessionStart` | de boa |
| `UserPromptSubmit` | pensando |
| `PreToolUse` / `PostToolUse` | trabalhando / pensando |
| `Notification` (permissão) | precisa de você |
| `Stop` | terminou |
| `SessionEnd` | esquece a sessão |

### Stack

| Camada | Tecnologia | Por quê |
|---|---|---|
| **Hook** | Python 3 (stdlib) | Rápido, não quebra o Claude Code, silencioso no stdout |
| **Janela** | GTK 3 + Cairo (PyGObject) no Linux; Tk + ctypes no Windows | Transparente, clique atravessa, nada pra instalar além do Python |
| **Arte** | Pixel art desenhado em código (ou convertido de uma folha de sprites) | Cada pose é montada por partes, então braços e pernas se mexem de verdade |
| **Estado** | Um JSON por sessão | Fácil de inspecionar, sem daemon, sem socket |

### Estrutura do repositório

```
claude-pet/
├── claude_pet/          ← o pet (python3 -m claude_pet)
│   └── chars/           ← lagartixa, gosminha, capivara, pato, dragao, pato_confuso (um arquivo cada);
│                           pato_cachecol e capivara_dev com os quadros num .bin
├── hooks/               ← o hook do Claude Code
├── tests/               ← hook → estado → comportamento
├── tools/               ← prévias dos sprites, página de revisão, GIFs do README, conversor de folha de sprites
├── docs/                ← GIFs usados aqui
├── install.py           ← instalador / desinstalador
└── README.pt-BR.md      ← você está aqui
```

---

## 🔒 Privacidade

- Tudo fica na sua máquina. **Nenhuma chamada de rede.**
- O hook guarda só o status da sessão, o nome da ferramenta, a pasta de trabalho e o PID do `claude`. **Nunca seus prompts ou seu código.**
- O instalador faz backup do `settings.json` antes de mexer e só adiciona ou remove as entradas do próprio Bit.

---

## 🛠️ Desenvolvendo

```bash
python3 -m unittest discover tests            # hook → estado → comportamento
python3 tools/review_html.py                  # art/review.html: todas as animações, quadro a quadro
python3 tools/make_gifs.py                    # regera os GIFs de docs/
CLAUDE_PET_DEBUG=1 python3 -m claude_pet      # log de status e posição no stderr
CLAUDE_PET_HOME=/tmp/x python3 -m claude_pet  # pasta de estado isolada pra experimentar
```

---

## 🐛 Solução de problemas

<details>
<summary><strong>O Bit não aparece</strong></summary>

Veja o tipo de sessão:

```bash
echo $XDG_SESSION_TYPE
```

O Bit precisa de **X11**. No Wayland, o GNOME não deixa a janela se posicionar sozinha, então ele não consegue andar. Escolha "Ubuntu on Xorg" na tela de login.
</details>

<details>
<summary><strong>O Bit nunca sai do "de boa"</strong></summary>

- Reinicie as sessões do Claude Code: os hooks são carregados quando a sessão começa.
- Confira se os hooks estão lá: `grep claude_pet_hook ~/.claude/settings.json`
- Confira se os arquivos de estado estão sendo gravados: `ls ~/.cache/claude-pet/sessions/`
</details>

<details>
<summary><strong>Clicar no Bit não foca o terminal</strong></summary>

Instale o `wmctrl`: `sudo apt install wmctrl`. Em terminais com abas, ele foca a janela, não a aba exata.
</details>

<details>
<summary><strong>Windows: o pet não aparece ou não reage ao Claude Code</strong></summary>

- Rode `py -c "import tkinter"`: se der erro, seu Python não tem Tk. Instale pelo python.org ou `winget install Python.Python.3.12`.
- Abra o pet pelo atalho **Claude Pet** do Menu Iniciar.
- Reinicie as sessões do Claude Code e confira os hooks: `Select-String claude_pet_hook $HOME\.claude\settings.json`
- Os arquivos de estado ficam em `%USERPROFILE%\.cache\claude-pet\sessions`.
</details>

<details>
<summary><strong>"claude-pet já está rodando"</strong></summary>

Só um Bit por vez. Feche o atual pelo menu do botão direito, ou `pkill -f "python3 -m claude_pet"`.
</details>

---

## 📜 Licença

MIT, faça o que quiser.

---

<p align="center">
  Feito com Claude Code, sob a supervisão do Bit. 🤖
</p>

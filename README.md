# Claude Pet

Um robozinho que anda pelas bordas da tela e mostra o status do Claude Code.

| Claude Code | Robô | Antena |
|---|---|---|
| ocioso | anda pelo chão, paredes e teto, senta e dorme (zzz) após 3 min | verde |
| pensando (depois do prompt) | anda devagar com a mão no queixo e "…" | azul |
| rodando ferramenta | senta e digita num notebook | amarela |
| pede permissão | pula, acena e mostra "!" e um balão com a mensagem | vermelha piscando |
| terminou | comemora e depois fica sentado com ✓ até você clicar | verde forte |

**Mouse:** arraste e solte para jogar (ele cai até o chão). Com o cursor por perto, ele para e olha.
Cursor parado em cima dele: carinho ❤. **Clique**, quando ele estiver pedindo algo ou tiver terminado, foca o
terminal daquela sessão. **Botão direito** abre a lista de sessões, "esconder por 30 min / 2 h" e "Sair".

Com várias sessões abertas, ele mostra a mais urgente (atenção > terminou > trabalhando > pensando),
com "(+N)" no balão. Ao passar o mouse, ele mostra todas as sessões.

## Instalar

```sh
python3 ~/claude-pet/install.py      # hooks + comando `claude-pet` + autostart no login
claude-pet &                          # inicia agora
```

Sessões do Claude Code que já estavam abertas só passam a reportar depois de reiniciadas.
Para desinstalar: `python3 ~/claude-pet/install.py --uninstall`. O instalador faz backup do `settings.json`.

## Como funciona

```
Claude Code ──hook (stdin JSON)──▶ hooks/claude_pet_hook.py ──▶ ~/.cache/claude-pet/sessions/<id>.json
                                                                        │ (lido a cada 250 ms)
claude_pet/state.py  (resume sessões, timeouts, prioridade) ◀───────────┘
claude_pet/character.py (movimento, física, máquina de estados, sem GTK, testável)
claude_pet/sprites.py   (robô em pixel art montado por partes + animações)
claude_pet/window.py    (janela GTK3 transparente, clique atravessa, balão, menu)
claude_pet/focus.py     (foca o terminal da sessão via wmctrl)
```

- O hook usa só a stdlib, nunca falha e não escreve no stdout.
- Sessão cujo processo `claude` morreu é removida sozinha.
- Pressionar Esc não dispara `Stop`. Por isso, "pensando" sem eventos por 10 min volta a ocioso, e "ferramenta" sem eventos por 30 min também.

## Personagens

Botão direito → **Personagem** troca na hora: Pato, Capivara, Slime ou Robô. A escolha fica salva no `config.json`.

Os personagens PNG saem de uma folha de referência com 8 poses (veja `art/PROMPTS.md`):

```sh
python3 tools/extract_refs.py art/refs/capivara.png capivara --facing 1   # --facing 1 = desenho olha p/ direita
```

O extrator recorta cada pose, remove o fundo, a sombra e os efeitos, reduz para uma grade de pixel real e salva
`claude_pet/packs/<nome>/frames.png` + `pack.json`. O movimento (pulinho, estica e achata, espelhar)
e os balões (zzz, …, !, brilhos, ✓) são feitos pelo código, iguais para todos os personagens.

## Configurar

`~/.config/claude-pet/config.json` (todas as chaves são opcionais; veja `claude_pet/config.py`):

```json
{ "skin": "pato", "scale": 3, "body_color": "#5ec4b6", "walk_speed": 45, "climb_chance": 0.25,
  "sleep_after": 180, "done_linger": 900, "monitor": -1 }
```

## Desenvolvimento

```sh
python3 -m unittest discover tests          # hook → estado → comportamento
python3 tools/preview.py /tmp/sheet.png 4   # folha com todos os frames, para revisar a arte
CLAUDE_PET_DEBUG=1 python3 -m claude_pet    # log de status/posição no stderr
CLAUDE_PET_HOME=/tmp/x python3 -m claude_pet  # pasta de estado isolada, para testar sem mexer na real
```

Requer X11. No Wayland, o GNOME não deixa a janela se posicionar sozinha, e aí seria preciso uma extensão do GNOME Shell.

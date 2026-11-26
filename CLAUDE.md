# claude-pet

Pet de desktop que mostra o status das sessões do Claude Code (hooks → `~/.cache/claude-pet/` → janela).
Linux (GTK/X11) e Windows (Tk, beta). Python puro, sem dependências fora da biblioteca padrão (+ PyGObject no Linux).

- Testes: `python3 -m unittest discover -s tests` (todos precisam passar antes de commit).
- Código e comentários em português; textos visíveis passam por `claude_pet/i18n.py` (pt e en).
- Release: tag `vX.Y.Z`, assets `claude-pet.tar.gz` e `claude-pet.zip` feitos com
  `git archive --prefix=claude-pet/ <tag> claude_pet hooks install.py LICENSE README.md README.pt-BR.md CLAUDE.md`.
  Os links `releases/latest/download/...` são o que o instalador e a atualização automática baixam.
  Suba `__version__` em `claude_pet/__init__.py` antes de lançar (a atualização compara com ele).

## Personagens: o formato

**Todo personagem, embutido ou customizado, é uma pasta neste formato.** Não existe outro jeito de fazer um.

```
<id>/
  character.json   manifesto (obrigatório)
  character.py     o desenho (obrigatório)
  frames.bin       opcional: quadros prontos de folha de sprites (gerado por tools/folha_para_pet.py)
  ...              qualquer outro arquivo que o character.py leia pelo próprio caminho (Path(__file__).parent)
```

`character.json`:

```json
{
  "format": 1,
  "id": "meu_bicho",
  "name": {"pt": "Meu Bicho", "en": "My Critter"},
  "description": {"pt": "…", "en": "…"},
  "author": "quem fez",
  "version": "1.0"
}
```

- Obrigatórios: `format` (hoje sempre `1`), `id` e `name`. O `id` tem letras minúsculas, números e `_`,
  começa com letra, tem de 2 a 32 caracteres e **é igual ao nome da pasta**.
- `name` e `description` podem ser texto ou `{"pt": …, "en": …}`.

`character.py` (contrato completo na docstring de `claude_pet/skins.py`):

- Canvas de 30×30 pixels lógicos, pés na borda de baixo. Girar o canvas é o que faz ele andar na parede e no teto.
- Define `HIT`, `PIVOT`, `ANIMS` e `render(pen, anim, frame, look, light)`.
- `ANIMS` tem **todas** as animações de `skins.ANIM_NAMES`: stand, walk, sit, sleep, curious, happy, think,
  think_walk, work, attention, celebrate, waiting, dangle. `confused` e `cry` são opcionais.
- `light` é a cor do status: algum detalhe do personagem precisa mostrar essa cor (antena, cachecol, fruta, brasa…).
- Desenha só com `pen.px(...)` / `pen.sprite(...)`, ou seja, retângulos de cor sólida. É isso que mantém Linux
  (cairo) e Windows (raster.py) idênticos.
- Importa só da biblioteca padrão e de `claude_pet.*` com import absoluto (`from claude_pet.pixel import shade`),
  nunca relativo. A pasta pode ser carregada de fora do pacote.
- Opcionais: `SIDE_VIEW`, `PACE_THINKING`, `OVERLAYS`, `OVERLAY_AT`, `FLIES_WHEN_WORKING`, `REST_SITS`, `SELF_HOP`.
- Pra ver exemplos, olhe `claude_pet/characters/`. `pato/` é desenhado em código e `capivara_dev/` usa folha de sprites.

### Embutido x customizado

| | Embutido | Customizado |
|---|---|---|
| Onde fica | `claude_pet/characters/<id>/` (no repositório) | `~/.config/claude-pet/characters/<id>/` (fora da instalação) |
| Como chega | vem com o claude-pet | pacote `.pet` importado em Configurações → "Adicionar personagem" |
| Atualizar o claude-pet | troca junto com a versão | **não é tocado** |
| Vai pro GitHub | sim | **não** |

### Quando pedirem pra você (Claude) fazer um personagem

1. **Por padrão, ele é customizado.** Crie a pasta *fora do repositório*, por exemplo em
   `~/claude-pet-personagens/<id>/`, e gere o pacote. Rode os comandos de dentro da instalação do claude-pet
   (a pasta que contém `claude_pet/`):
   ```bash
   python3 -m claude_pet.charpack check ~/claude-pet-personagens/<id>    # carrega e desenha todo quadro
   python3 -m claude_pet.charpack pack  ~/claude-pet-personagens/<id> ~/claude-pet-personagens/<id>.pet
   python3 -m claude_pet.charpack install ~/claude-pet-personagens/<id>.pet   # ou pela janela de Configurações
   ```
   Não crie nada em `claude_pet/characters/`, não registre em `skins.ORDER` e não faça commit de personagem
   customizado. `*.pet` está no `.gitignore`.
2. **Só vira embutido se o dono do repositório pedir explicitamente** que ele faça parte do claude-pet.
   Aí a pasta vai pra `claude_pet/characters/<id>/`, entra em `skins.ORDER`, ganha GIF em `docs/chars/`
   (`tools/make_gifs.py`) e linha na tabela de personagens dos dois READMEs.
3. **Personagem original sempre.** Não recrie personagem de jogo, desenho, filme ou marca (Pokémon, Transformers,
   mascotes etc.), nem "parecido mas com outro nome". Se pedirem um, ofereça um original inspirado no clima.
4. **Qualidade:** julgue em tamanho real (escala 3) sobre fundo escuro, ao lado de um personagem aprovado.
   Contorno de 1 px, luz em cima, sombra embaixo. Props minúsculos viram mancha.
   `tools/sheet.py` monta uma folha com todas as animações pra revisar.
5. Confira com `charpack check` antes de entregar e diga onde ficou o `.pet`.

## Atualizações

`claude_pet/update.py` confere a última release no GitHub a cada 12 h (guarda em `~/.config/claude-pet/update.json`).
Quando tem versão nova, o pet avisa uma vez num balão, e aparecem "⬆ Atualizar" no menu e um botão em Configurações.
A atualização baixa o pacote da release, troca os arquivos da instalação, roda `install.py --update` e reinicia o pet.
Rodando de um clone do git, nada disso acontece: lá se atualiza com `git pull`.

"""Vampirinho Axolote: vampiro de capa preta e olhos vermelhos que, de vez em quando, vira um axolote cor-de-rosa.

Desenhado a partir de uma folha de sprites: os quadros vêm prontos de frames.bin (gerado por
`tools/folha_para_pet.py vampiro_axolote ...` a partir da folha de 11 animações x 9 quadros, usada inteira):
parado, andando, pensando (balão, reticências, lâmpada), trabalhando (mesa e notebook), dormindo (deitado, zz),
feliz, comemorando (faíscas), atenção ("!") e pendurado. E as duas linhas a mais: transformação (a névoa roxa
sobe e ele vira axolote) e axolote (nadando, com bolhinhas). De vez em quando ele se transforma, nada um pouco
pela tela, desce e volta ao normal (ver Pet._bat e bat_every; a animação do nado se chama "bat", o nome que o
pet dá pra forma transformada). Os efeitos já estão desenhados nos quadros, então nenhum efeito do pet vai por
cima. O desenho fica em claude_pet/folha.py.
"""
from __future__ import annotations

from pathlib import Path

from claude_pet.folha import Folha, run

SIDE_VIEW = True
PACE_THINKING = False    # pensa parado, com o balão da folha
SELF_HOP = True          # feliz/comemorando/atenção são de meio corpo na folha: pulando, o corpo ficaria no ar
HIT = (7, 9, 16, 21)
PIVOT = (15, 1)          # segurado pelas mãos (no "pendurado") / pelo alto da cabeça
OVERLAYS = {a: None for a in ("think", "think_walk", "sleep", "attention", "celebrate", "waiting", "happy")}

ALL = range(9)
SHEET = {   # animação -> (quadros por segundo, quadros da folha)
    "stand": (5, run("parado", ALL)),
    "sit": (5, run("parado", ALL)),
    "curious": (5, run("parado", ALL)),
    "waiting": (5, run("parado", ALL)),
    "walk": (9, run("andando", ALL)),
    "think_walk": (9, run("andando", ALL)),
    "think": (3, run("pensando", ALL)),
    "work": (5, run("trabalhando", ALL)),
    "sleep": (2, run("dormindo", ALL)),
    "happy": (8, run("feliz", ALL)),
    "celebrate": (8, run("comemorando", ALL)),
    "attention": (6, run("atencao", ALL)),
    "dangle": (6, run("pendurado", ALL)),
    "transform": (8, run("transformacao", ALL)),               # vira axolote
    "transform_back": (8, run("transformacao", reversed(ALL))),  # e volta
    "bat": (8, run("axolote", ALL)),                           # nadando (olhando pra direita; o pet espelha)
}

_FOLHA = Folha(Path(__file__).with_name("frames.bin"), SHEET)
ANIMS = _FOLHA.anims
render = _FOLHA.render

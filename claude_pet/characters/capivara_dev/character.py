"""Capivara Dev: capivara gordinha de fone roxo, óculos e camiseta preta, desenhada a partir de uma folha de sprites.

Os quadros vêm prontos de frames.bin (gerado por `tools/folha_para_pet.py capivara_dev ...` a partir
da folha de 9 animações x 8 quadros): parado, andando, pensando (balão, reticências, lâmpada), trabalhando
(cadeira, mesa e notebook), dormindo (deitada, zzz), feliz, comemorando (pulo com brilho), atenção ("!") e
pendurado (a mão segurando, olhos tontos). Os efeitos já estão desenhados nos quadros, então nenhum efeito
do pet vai por cima. O desenho fica em claude_pet/folha.py.
"""
from __future__ import annotations

from pathlib import Path

from claude_pet.folha import Folha, run

SIDE_VIEW = True
PACE_THINKING = False    # pensa parada, com o balão da folha
HIT = (5, 11, 22, 19)
PIVOT = (15, 1)          # segurada pela mão (no "pendurado") / pelo alto da cabeça
OVERLAYS = {a: None for a in ("think", "think_walk", "sleep", "attention", "celebrate", "waiting", "happy")}

ALL = range(8)
SHEET = {   # animação -> (quadros por segundo, quadros da folha)
    "stand": (5, run("parado", ALL)),
    "sit": (5, run("parado", ALL)),
    "walk": (8, run("andando", ALL)),
    "think_walk": (8, run("andando", ALL)),
    "curious": (4, run("pensando", (0, 1, 2, 1))),
    "think": (3, run("pensando", (*ALL, 7, 7))),               # segura a lâmpada um pouquinho
    "work": (5, run("trabalhando", ALL)),
    "sleep": (2, run("dormindo", (3, 4, 5, 6))),              # deitada: z, zz, zzz
    "happy": (8, run("feliz", ALL)),
    "celebrate": (8, run("comemorando", ALL)),
    "attention": (6, run("atencao", ALL)),
    "waiting": (2, run("feliz", (0, 0, 7, 7))),
    "dangle": (6, run("pendurado", ALL)),
}

_FOLHA = Folha(Path(__file__).with_name("frames.bin"), SHEET)
ANIMS = _FOLHA.anims
render = _FOLHA.render

"""Pato de Cachecol: patinho dourado e gordinho de cachecol azul, desenhado a partir de uma folha de sprites.

Os quadros vêm prontos de pato_cachecol.bin (gerado por `tools/folha_para_pet.py pato_cachecol folha.png ... confuso=tira.png`
a partir da folha de 9 animações x 9 quadros): parado, andando, pensando (balão, reticências, lâmpada),
trabalhando (cadeira, mesa e notebook com "</>"), dormindo (zzz), feliz, comemorando (pulo), atenção ("!")
e pendurado (a mão segurando, olhos tontos). E, de uma tira à parte, confuso (olho em espiral, tremendo):
de vez em quando ele larga o que está fazendo e fica confuso (ver Pet._confused). Os efeitos já estão
desenhados nos quadros, então nenhum efeito do pet vai por cima. O desenho e o crossfade ficam em claude_pet/folha.py.
"""
from __future__ import annotations

from pathlib import Path

from ..folha import Folha, run

LABEL = "Pato de Cachecol"
SIDE_VIEW = True
PACE_THINKING = False    # pensa parado, com o balão da folha
HIT = (7, 7, 20, 23)
PIVOT = (15, 1)          # segurado pela mão (no "pendurado") / pelo topete
OVERLAYS = {a: None for a in ("think", "think_walk", "sleep", "attention", "celebrate", "waiting", "happy")}
FADE = 3                 # quadros por quadro da folha: ele mesmo + 2 misturas com o próximo (1 = sem crossfade)

ALL = range(9)
# Alguns quadros da folha vieram com defeito e ficam de fora (o crossfade cobre o buraco):
#   parado 3 e 6: mancha branca na cabeça / cachecol marrom    feliz 2 a 6: o cachecol some
#   comemorando 3: topete cortado                             atenção 3: pedaço solto de cachecol
#   pendurado 3 e 4: borrão laranja / sem cachecol
# O andar usa os 9 quadros de propósito (preferência do dono); o pé a mais do andando2 é remendado no .bin.
STAND = (0, 1, 2, 4, 5, 7, 8)                                 # 5 = a piscada
SHEET = {   # animação -> (quadros por segundo, quadros da folha)
    "stand": (5, run("parado", STAND)),
    "sit": (5, run("parado", STAND)),
    "walk": (9, run("andando", ALL)),
    "think_walk": (9, run("andando", ALL)),
    "curious": (4, run("pensando", (0, 1, 2, 3, 2, 1))),
    "think": (3, run("pensando", (*ALL, 8, 8))),               # segura a lâmpada um pouquinho
    "work": (5, run("trabalhando", ALL)),
    "sleep": (2, run("dormindo", (3, 4, 5, 6))),              # cabeça caída: z, zz, zzz
    "happy": (4, run("feliz", (0, 1, 7, 8))),
    "celebrate": (8, run("comemorando", (0, 1, 2, 4, 5, 6, 7, 8))),
    "attention": (6, run("atencao", (0, 1, 2, 4, 5, 6, 7, 8))),
    "waiting": (2, run("feliz", (0, 0, 8, 8))),
    "dangle": (6, run("pendurado", (0, 1, 2, 5, 6, 7, 8))),
    "confused": (5, run("confuso", ALL)),                      # olho em espiral, treme e volta (tira à parte)
}

_FOLHA = Folha(Path(__file__).with_suffix(".bin"), SHEET, FADE)
ANIMS = _FOLHA.anims
render = _FOLHA.render
set_smooth = _FOLHA.set_smooth     # menu "Animação": suave (crossfade) ou quadro a quadro

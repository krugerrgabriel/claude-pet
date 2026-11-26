"""Robô Faísca: robozinho azul e vermelho, de olhos azul-claros, crista listrada e duas antenas laterais.

Os quadros vêm prontos de robo_faisca.bin, feito em dois passos a partir de uma folha de 9 animações x 9
quadros: `tools/repinta_faisca.py` redesenha o robô da folha (cores, mantendo a crista e as antenas da
folha, ">_" no notebook) e `tools/folha_para_pet.py robo_faisca ...` converte.
As animações: parado, andando, pensando
(balão, reticências, lâmpada), trabalhando (cadeira, mesa e notebook), dormindo (cabeça caída, zzz), feliz,
comemorando (pulo com brilho), atenção ("!") e pendurado (olhos tontos). Os efeitos já estão desenhados
nos quadros, então nenhum efeito do pet vai por cima. O desenho fica em claude_pet/folha.py.
"""
from __future__ import annotations

from pathlib import Path

from ..folha import Folha, run

LABEL = "Robô Faísca"
SIDE_VIEW = True
PACE_THINKING = False    # pensa parado, com o balão da folha
SELF_HOP = True          # comemorando já pula na folha e atenção é em pé: o pet não pula por cima
HIT = (5, 6, 20, 24)
PIVOT = (15, 2)          # segurado pelo alto do capacete
OVERLAYS = {a: None for a in ("think", "think_walk", "sleep", "attention", "celebrate", "waiting", "happy")}

ALL = range(9)
SHEET = {   # animação -> (quadros por segundo, quadros da folha): cada estado do pet com a linha dele
    "stand": (5, run("parado", ALL)),                         # parado (ocioso)
    "sit": (5, run("parado", ALL)),
    "curious": (5, run("parado", ALL)),                       # mouse perto: continua parado, olhando
    "walk": (9, run("andando", ALL)),                         # andando
    "think_walk": (9, run("andando", ALL)),
    "think": (3, run("pensando", ALL)),                       # pensando
    "work": (5, run("trabalhando", ALL)),                     # trabalhando
    "sleep": (2, run("dormindo", (3, 4, 5, 6))),              # dormindo: o trecho de cabeça caída (z, zz, zzz)
    "happy": (8, run("feliz", ALL)),                          # feliz (carinho)
    "celebrate": (8, run("comemorando", ALL)),                # comemorando (terminou)
    "waiting": (5, run("parado", ALL)),                       # depois de comemorar, esperando você: parado
    "attention": (6, run("atencao", ALL)),                    # atenção
    "dangle": (6, run("pendurado", ALL)),                     # pendurado (arrastando)
}

_FOLHA = Folha(Path(__file__).with_suffix(".bin"), SHEET)
ANIMS = _FOLHA.anims
render = _FOLHA.render

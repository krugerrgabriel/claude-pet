"""Capivara Dev: capivara gordinha de fone roxo, óculos e camiseta preta, desenhada a partir de uma folha de sprites.

Os quadros vêm prontos de frames.bin (gerado por `tools/folha_para_pet.py capivara_dev ...` a partir
da folha de 9 animações x 8 quadros e depois reduzido a poucos quadros alinhados por ação): parado, andando, pensando (balão, reticências, lâmpada), trabalhando
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

# Os quadros da folha original eram redesenhados um a um (contorno, textura e posição mudavam a cada quadro) e,
# tocados em sequência, a capivara "fervia". Aqui fica só o essencial: um quadro por ação parada e no máximo
# 2 ou 3 nas que precisam de movimento, alinhados ao quadro base (pés no mesmo chão; no pendurado, a mão).
SHEET = {   # animação -> (quadros por segundo, quadros)
    "stand": (1, run("parado", (0,))),
    "sit": (1, run("parado", (0,))),
    "walk": (4, run("andando", (0, 1))),
    "think_walk": (4, run("andando", (0, 1))),
    "curious": (1, run("pensando", (0,))),
    "think": (0.7, run("ideia", (0, 1))),                        # reticências, depois a lâmpada
    "work": (3, run("trabalhando", (0, 1))),
    "sleep": (1.2, run("dormindo", (0, 1, 2))),                  # z, zz, zzz
    "happy": (3, run("festa", (0, 1))),
    "celebrate": (1, run("comemorando", (0,))),                  # o pulo quem faz é o pet
    "attention": (2, run("atencao", (0, 1))),
    "waiting": (1, run("feliz", (0,))),
    "dangle": (3, run("pendurado", (0, 1))),
}

_FOLHA = Folha(Path(__file__).with_name("frames.bin"), SHEET)
ANIMS = _FOLHA.anims
render = _FOLHA.render

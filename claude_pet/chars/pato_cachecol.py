"""Pato de Cachecol: patinho dourado e gordinho de cachecol azul, desenhado a partir de uma folha de sprites.

Os quadros vêm prontos de pato_cachecol.bin (gerado por `tools/folha_para_pet.py pato_cachecol folha.png ... confuso=tira.png`
a partir da folha de 9 animações x 9 quadros): parado, andando, pensando (balão, reticências, lâmpada),
trabalhando (cadeira, mesa e notebook com "</>"), dormindo (zzz), feliz, comemorando (pulo), atenção ("!")
e pendurado (a mão segurando, olhos tontos). E, de uma tira à parte, confuso (olho em espiral, tremendo):
de vez em quando ele larga o que está fazendo e fica confuso (ver Pet._confused). E chorando, montado
aqui a partir do dormindo: de vez em quando, com o Claude parado ou esperando você, ele vai pro canto da tela e chora um
pouco (ver Pet._cry). Os efeitos já estão
desenhados nos quadros, então nenhum efeito do pet vai por cima. O desenho fica em claude_pet/folha.py.
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

ALL = range(9)
# Alguns quadros da folha vieram com defeito e ficam de fora:
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
    "cry": (6, run("chorando", range(8))),                     # no canto, chorando (montado aqui embaixo)
}

# Chorando (ver Pet._cry). A folha não tem, então os quadros são montados aqui a partir do "dormindo" 0 e 1
# (olhos fechados; alternar os dois dá o soluço): os olhos viram de cabeça pra baixo ("∪" de quem dorme
# vira "∩", triste) e as lágrimas são pintadas por cima. Do olho de trás escorre um fio pela bochecha,
# rente ao bico, que engorda e pinga; o da frente fica na beira da cabeça, então dele sai um jato em arco
# por cima da borda, que pinga na frente do bico.
TEAR, TEAR_EDGE, SHINE = 0x8fd3ff, 0x2a7bd1, 0xffffff
CRY_EYES = {   # quadro da folha: (caixas dos olhos a virar, alto do fio do olho de trás, deslocamento do jato)
    "dormindo0": (((40, 50, 51, 56), (59, 50, 69, 52)), (40, 55), (0, 0)),
    "dormindo1": (((38, 52, 50, 56), (57, 50, 67, 53)), (38, 56), (-2, 1)),
}
JET = ((67, 51), (69, 50), (71, 49), (73, 48), (75, 48), (77, 48), (79, 49), (81, 50), (82, 52), (83, 54),
       (84, 56), (84, 58))        # o jato do olho da frente (no "dormindo0"), do canto do olho pra fora
DROP = (".ee.", "eLLe", "eWLe", "eLLe", ".ee.")
SPLASH = ("e....e", ".e..e.")
BACK_FALL = (70, 76, 82)       # alto da gota do olho de trás caindo, um quadro cada (no 4º ela respinga)
JET_FALL = (61, 67, 74, 80)    # e das que pingam do jato


def _sprite(x0, y0, rows):
    ink = {"e": TEAR_EDGE, "L": TEAR, "W": SHINE}
    return {(x0 + i, y0 + j): ink[ch] for j, row in enumerate(rows) for i, ch in enumerate(row) if ch in ink}


def _stroke(points):
    """Traço de lágrima de 2 pixels de largura pelos pontos, contornado de azul mais escuro."""
    light = {(x + i, y + j) for x, y in points for i in (0, 1) for j in (0, 1)}
    edge = {(x + dx, y + dy) for x, y in light for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - light
    return {**{q: TEAR_EDGE for q in edge}, **{q: TEAR for q in light}}


def _tears(k):
    """O quadro k do choro: (quadro da folha, caixas a virar, o que pintar). Ciclo de 4 quadros: o fio do
    olho de trás enche, forma a gota e ela cai (no fim respinga); o jato da frente pinga fora de fase."""
    base = ("dormindo0", "dormindo1")[k // 2 % 2]
    flip, (ax, ay), (jx, jy) = CRY_EYES[base]
    c = k % 4
    n = (5, 7, 9, 10)[c]
    paint = _stroke([(ax, y) for y in range(ay, ay + n)])
    paint.update(_sprite(ax - 2, ay + n, ("eLLLLe", "eLWLLe", ".eeee.") if c == 3 else (".eLLe.", "..ee..")))
    paint.update(_sprite(37, BACK_FALL[c], DROP) if c < 3 else _sprite(36, 85, SPLASH))
    paint.update(_stroke([(x + jx, y + jy) for x, y in JET]))
    j = (k + 2) % 4
    paint.update(_sprite(83, JET_FALL[j], DROP))
    if j == 0:
        paint.update(_sprite(82, 86, SPLASH))
    return base, flip, paint


_FOLHA = Folha(Path(__file__).with_suffix(".bin"), SHEET)
for _k in range(8):
    _base, _flip, _paint = _tears(_k)
    _FOLHA.derive(f"chorando{_k}", _base, _paint, _flip)
ANIMS = _FOLHA.anims
render = _FOLHA.render

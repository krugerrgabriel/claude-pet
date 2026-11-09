"""Capivara: de perfil, zen, com a frutinha de status equilibrada na cabeça."""
from __future__ import annotations

from ..pixel import THOUGHT_CLOUD, THOUGHT_COLORS, Pen, draw_computer, overlay, shade

LABEL = "Capivara"
SIDE_VIEW = True
PACE_THINKING = False
HIT = (2, 6, 26, 24)
PIVOT = (15, 3)    # topo-centro da cabeça na pose pendurada (de frente)

ANIMS = {
    "stand": (4, 16),
    "walk": (5, 4),
    "sit": (4, 16),
    "sleep": (2, 4),
    "curious": (4, 10),
    "happy": (4, 4),
    "think": (3, 8),
    "think_walk": (4, 8),
    "work": (6, 12),
    "attention": (6, 4),
    "celebrate": (6, 2),
    "waiting": (2, 4),
    "dangle": (4, 4),
}
# efeitos desenhados aqui mesmo: seguem a cabeça quando ela vira pra esquerda
OVERLAYS = {a: None for a in ANIMS}

PAL = {
    "O": "#3b2416",   # contorno
    "B": "#b9804a",   # caramelo
    "L": "#d29b63",   # luz
    "H": "#e3b27c",   # brilho
    "D": "#97643a",   # sombra
    "d": "#7e5230",   # sombra funda
    "J": "#7a4e2d",   # perna (perto)
    "j": "#5e3b21",   # perna (lado de lá)
    "N": "#5a3622",   # narina / boca
    "K": "#8a5636",   # dentro da orelha
    "E": "#24160d",   # olho
    "W": "#ffffff",
    "P": "#e48a86",   # bochecha
    "G": "#2f7a34",   # folha (verde-escuro, separa da fruta)
    "g": "#1f5424",
    "s": "#6b4428",   # cabinho
    "V": "#3d8a3a",   # capim escuro
    "v": "#86cc5c",   # capim claro
    "C": "#ecd3a8",   # barriga creme
    "c": "#d9b98a",
    "M": "#c99a62",   # tampo da mesinha
    "m": "#9c6f40",   # madeira na sombra
    "T": "#7d9a3e",   # capim
    "t": "#b7d46a",
}

# ---------------------------------------------------------------- partes
BODY = [  # pão: 19 x 12, luz em cima/esquerda, sombra na barriga/direita
    "....OOOOOOOOOOO....",
    "..OOHHHHHHLLLLLOO..",
    ".OHHLLLLLLLLLLLBBO.",
    "OHLLLBBBBBBBBBBBBDO",
    "OLLBBBBBBBBBBBBBBDO",
    "OLBBBBBBBBBBBBBBBDO",
    "OLBBBBBBBBBBBBBBBDO",
    "OBBBBBBBBBBBBBBBDDO",
    "ODBBBBBBBBBBBBBBDDO",
    ".ODDDBBBBBBBBBDDDO.",
    "..OODDDDDDDDDDDOO..",
    "....OOOOOOOOOOO....",
]
BODY_LOW = [  # deitada de barriga: 19 x 9
    "....OOOOOOOOOOO....",
    "..OOHHHHHHLLLLLOO..",
    ".OHHLLLLLLLLLLLBBO.",
    "OHLLBBBBBBBBBBBBBDO",
    "OLBBBBBBBBBBBBBBBDO",
    "OLBBBBBBBBBBBBBBDDO",
    "ODBBBBBBBBBBBBBDDDO",
    ".ODDDDDDDDDDDDDDDO.",
    "..OOOOOOOOOOOOOOO..",
]
BODY_SIT = [  # sentada: traseiro no chão (coxa marcada), peito pra cima: 17 x 15
    "........OOOOOO...",
    "......OOHHHHLLO..",
    ".....OHHLLLLLBBO.",
    "....OHLLBBBBBBDO.",
    "...OHLBBBBBBBBDO.",
    "...OLBBBBBBBBBDO.",
    "..OHLBBBBBBBBBDO.",
    "..OLBBBBBBBBBBDO.",
    ".OHLBBBBBBBBBBDO.",
    ".OLBBBDDDDBBBDDO.",
    "OHLBBDBBBBDBBDO..",
    "OLBBDBBBBBBDBDO..",
    "OBBBDBBBBBBDDDO..",
    "ODDDDDDDDDDDDO...",
    ".OOOOOOOOOOOO....",
]

# cabeça: 14 x 12, quadradona, focinho comprido e rombudo pra direita, orelhinha atrás
HEAD = [  # 14 x 12, quadradona, focinho comprido e rombudo; luz em cima/esquerda
    "..............",
    "..............",
    "..OOOOOOOOO...",
    ".OHHHHHLLLLOO.",
    "OHHLLLLLLLLLLO",
    "OHLBBBBBBBBDDO",
    "OLBBBBBBBBBDNO",
    "OLBBBBBBBBBBDO",
    "OBBBBBBBBBBBDO",
    "OBBBBBBBBBBBDO",
    ".ODDDDDDDDDNNO",
    "..OOOOOOOOOOO.",
]
EARS = {
    "none": [],
    "normal": ["..OO", ".OKKO", ".OKO"],
    "flick": ["....", ".OOO", "OKKO"],   # orelhinha abaixada pra trás
}


def _head(pen: Pen, pal, x, y, eyes="open", mouth="calm", look=0, ear="normal", blush=True):
    pen.sprite(x, y, HEAD, pal)
    pen.sprite(x, y, EARS[ear], pal)
    ex, ey = x + 4, y + 6   # olho 2x2
    gx = ex + (0 if look < 0 else 1)          # brilho do lado pra onde olha
    if eyes in ("open", "wide"):
        pen.px(ex, ey, 2, 2, pal["E"])
        pen.px(gx, ey, 1, 1, pal["W"])
        if eyes == "open":                    # pálpebra de leve: cara de "de boa"
            pen.px(ex, ey - 1, 2, 1, pal["D"])
    elif eyes == "meh":                       # tanto faz: meio olho
        pen.px(ex, ey, 2, 1, pal["D"])
        pen.px(ex, ey + 1, 2, 1, pal["E"])
        pen.px(gx, ey + 1, 1, 1, pal["W"])
    elif eyes == "closed":
        pen.px(ex - 1, ey + 1, 3, 1, pal["E"])
    elif eyes == "happy":                     # ^
        pen.px(ex - 1, ey + 1, 1, 1, pal["E"])
        pen.px(ex, ey, 2, 1, pal["E"])
        pen.px(ex + 2, ey + 1, 1, 1, pal["E"])
    elif eyes == "down":                      # olhando pro notebook
        pen.px(ex, ey, 2, 1, pal["D"])
        pen.px(ex, ey + 1, 2, 1, pal["E"])
        pen.px(ex + 1, ey + 1, 1, 1, pal["W"])
    elif eyes == "up":                        # olhando pro alto
        pen.px(ex, ey - 1, 2, 2, pal["E"])
        pen.px(ex + 1, ey - 1, 1, 1, pal["W"])
    # bochecha logo abaixo/atrás do olho
    if blush:
        pen.px(ex - 2, ey + 2, 2, 1, pal["P"])
    if mouth == "open":
        pen.px(x + 10, y + 9, 3, 2, pal["N"])
        pen.px(x + 11, y + 10, 1, 1, "#d0606a")
    elif mouth == "flat":
        pen.px(x + 10, y + 10, 2, 1, pal["N"])
    elif mouth == "chew":
        pen.px(x + 11, y + 10, 2, 1, pal["D"])


def _fruit(pen: Pen, pal, x, y):
    """Frutinha 6x6 na cor do status: contorno escuro, brilho branco, cabinho e folhinha escura."""
    f = pal["F"]
    rows = [
        "..sgg.",
        ".OOsOO",
        "OFWFFO",
        "OFFFfO",
        "OFFffO",
        ".OOOO.",
    ]
    pen.sprite(x, y, rows, dict(pal, f=shade(f, 0.72), W="#ffffff"))


LEG_X = [(3, "j"), (6, "J"), (12, "j"), (15, "J")]   # trás longe, trás perto, frente longe, frente perto


def _legs(pen: Pen, pal, kind="stand", top=25, dx=0, skip=()):
    """Perninhas curtas e grossas quase escondidas sob o pão; pé em y=29. No passo, uma encolhe 1px."""
    for i, (x, c) in enumerate(LEG_X):
        if i in skip:
            continue
        x += dx
        lift = (kind == "walk1" and i in (0, 3)) or (kind == "walk2" and i in (1, 2))
        bottom = 29 - (1 if lift else 0)
        pen.px(x, top, 4, bottom - top + 1, pal["O"])
        pen.px(x + 1, top, 2, bottom - top, pal[c])


def _thought(pen: Pen, f, x=1, y=0):
    """Nuvem em cima à esquerda; as bolinhas descem até a cabeça."""
    step = f % 4
    pen.sprite(x, y, THOUGHT_CLOUD, THOUGHT_COLORS)
    for k in range(min(3, step + 1)):
        pen.px(x + 3 + k * 3, y + 3, 1, 1, THOUGHT_COLORS["d"])
    pen.px(x + 12, y + 6, 1, 1, THOUGHT_COLORS["W"])
    if step >= 1:
        pen.px(x + 13, y + 7, 2, 2, THOUGHT_COLORS["W"])


# posição base (esquerda, largura) de cada efeito no pixel.overlay, pra espelhar quando ela vira
_FX_BOX = {"zzz": (20, 9), "bang": (24, 2), "heart": (22, 5), "check": (23, 5), "sparkle": (0, 30)}


def _fx(pen: Pen, name, f, dx, dy=0):
    """Efeito por cima, sem espelhar o desenho, mas do lado da cabeça."""
    if pen.flip:
        left, w = _FX_BOX[name]
        dx = 30 - w - 2 * left - dx
    overlay(Pen(pen.cr, pen.s), name, f, dx, dy)


def _standing(pen, pal, *, legs="stand", bob=0, eyes="open", mouth="calm", look=0, ear="normal", fruit_hop=0,
              dx=0, skip_legs=()):
    _legs(pen, pal, legs, dx=dx, skip=skip_legs)
    pen.sprite(2 + dx, 15 + bob, BODY, pal)   # pão baixinho: barriga em y=26
    hy = 9 + bob
    _head(pen, pal, 14 + dx, hy, eyes=eyes, mouth=mouth, look=look, ear=ear)
    _fruit(pen, pal, 18 + dx, hy - 3 + fruit_hop)   # ancorada na cabeça; fruit_hop = pulinho de propósito
    return hy


def _paw_up(pen, pal, pts, c):
    """Pata da frente levantada até o teclado: blocos 2x2 com contorno, pezinho escuro na ponta."""
    for x, y in pts:
        pen.px(x - 1, y - 1, 4, 4, pal["O"])
    for x, y in pts:
        pen.px(x, y, 2, 2, pal[c] if c == "D" else pal["B"])
    x, y = pts[-1]
    pen.px(x, y, 2, 2, pal["J"])


def _table(pen, pal, x0, top, w):
    """Mesinha de madeira: tampo de 2 linhas com contorno + 2 perninhas finas até y=29."""
    pen.px(x0, top - 1, w, 4, pal["O"])
    pen.px(x0 - 1, top, w + 2, 2, pal["O"])
    pen.px(x0, top, w, 1, pal["M"])
    pen.px(x0, top + 1, w, 1, pal["m"])
    for lx in (x0 + 1, x0 + w - 3):
        pen.px(lx, top + 3, 3, 30 - (top + 3), pal["O"])     # até o chão (contorno em y=29)
        pen.px(lx + 1, top + 3, 1, 29 - (top + 3), pal["m"])


def _working(pen, pal, light, f, last):
    """Sentadinha ereta (como o sit) de frente pro computador da mesinha, digitando com uma
    patinha de cada vez; a outra fica apoiada. Mesma composição do work da lagartixa."""
    dx = -2
    hx = 5                                         # cabeça sobre o peito: focinho com folga do monitor
    typing = f != last
    near_up = typing and f % 2 == 0
    far_up = typing and f % 2 == 1
    if far_up:                                      # pata de lá esticada até o teclado (atrás)
        _paw_up(pen, pal, [(14, 22), (16, 21), (18, 20)], "D")
    else:
        _front_leg(pen, pal, 15 + dx, far=True)
    pen.sprite(2 + dx, 15, BODY_SIT, pal)
    pen.px(7 + dx, 27, 5, 3, pal["O"])              # pezinho de trás
    pen.px(8 + dx, 28, 3, 1, pal["J"])
    if not near_up:
        _front_leg(pen, pal, 19 + dx)
    _head(pen, pal, hx, 6, eyes="closed" if f == last else "open", look=1)
    _fruit(pen, pal, hx + 4, 3)
    _table(pen, pal, 17, 23, 12)
    draw_computer(pen, 20, 13, light, f, keyboard_at=(17, 20))
    if near_up:                                     # pata de cá no teclado
        _paw_up(pen, pal, [(15, 23), (17, 22), (19, 20)], "B")


def _front_leg(pen, pal, x, far=False):
    """Pata da frente retinha (sentada): cor do corpo com sombra, pezinho escuro na ponta."""
    pen.px(x, 21, 4, 9, pal["O"])
    pen.px(x + 1, 21, 2, 7, pal["D"] if far else pal["B"])
    if not far:
        pen.px(x + 1, 21, 1, 6, pal["L"])
    pen.px(x + 1, 28, 2, 1, pal["j"] if far else pal["J"])


def _sitting(pen, pal, eyes="open", dx=0, near_leg=True, mouth="calm"):
    """Traseiro no chão, patinhas da frente retinhas, peito pra cima."""
    _front_leg(pen, pal, 15 + dx, far=True)
    pen.sprite(2 + dx, 15, BODY_SIT, pal)
    pen.px(7 + dx, 27, 5, 3, pal["O"])        # pezinho de trás apoiado na frente da coxa
    pen.px(8 + dx, 28, 3, 1, pal["J"])
    if near_leg:
        _front_leg(pen, pal, 19 + dx)
    _head(pen, pal, 13 + dx, 6, eyes=eyes, mouth=mouth)
    _fruit(pen, pal, 17 + dx, 3)


def _lying(pen, pal, *, x=2, head_x=14, eyes="closed", breathe=0, mouth="calm"):
    pen.sprite(x, 21 - breathe, BODY_LOW, pal)
    pen.px(x + 2, 29, 15, 1, pal["O"])
    _head(pen, pal, head_x, 17, eyes=eyes, mouth=mouth)
    _fruit(pen, pal, head_x + 4, 14)


# ---------------------------------------------------------------- pendurada, de frente
HEAD_FRONT = [  # 16 x 13: orelhinhas nas laterais, focinho largo e rombudo com narinas
    "..OO........OO..",
    ".OKKOOOOOOOOKKO.",
    ".OKHHHHHLLLLLKO.",
    "OHHLLLLLLLLLLLDO",
    "OHLBBBBBBBBBBBDO",
    "OLBBBBBBBBBBBBDO",
    "OLBBBBBBBBBBBBDO",
    "OBBBLLLLLLLLBBDO",
    "OBBLLNLLLLNLLBDO",
    "OBBLLLLLLLLLLBDO",
    ".ODDLLLLLLLLDDO.",
    "..OODDDDDDDDOO..",
    "....OOOOOOOO....",
]
BODY_FRONT = [  # 14 x 11: pera gordinha pendendo, fina no pescoço e cheia embaixo, barriga creme
    "....OOOOOO....",
    "...OHLLLLBO...",
    "..OHLCCCCLDO..",
    ".OHLCCCCCCBDO.",
    ".OLCCCCCCCCDO.",
    "OHLCCCCCCCCBDO",
    "OLBCCCCCCCcBDO",
    "OBBCCCCCCccBDO",
    ".OBBcccccBBDO.",
    "..ODDDDDDDDO..",
    "...OOOOOOOO...",
]


def _hang_paw(pen, pal, x, y, n):
    """Patinha gordinha pendurada reta pra baixo: n px de comprimento, pontinha escura."""
    pen.px(x, y, 4, n + 1, pal["O"])
    pen.px(x + 1, y, 2, n, pal["B"])
    pen.px(x + 1, y, 1, n - 1, pal["L"])
    pen.px(x + 1, y + n - 1, 2, 1, pal["J"])


def _dangle(pen, pal, f):
    """Pendurada de frente, mole tipo pelúcia levantada: corpo em pera pendendo, bracinhos caídos
    colados na barriga, perninhas retinhas pra baixo; tudo oscila 1px de um lado pro outro."""
    sw = (0, 1, 0, -1)[f % 4]        # balanço sutil
    # perninhas de trás saindo da base, com vão no meio; uma 1px mais baixa que a outra
    _hang_paw(pen, pal, 10 - sw, 21, 3 + (f % 2))
    _hang_paw(pen, pal, 16 - sw, 21, 4 - (f % 2))
    pen.sprite(8, 13, BODY_FRONT, pal)
    # bracinhos moles caídos por cima da parte de cima da barriga
    _hang_paw(pen, pal, 9 + sw, 15, 4)
    _hang_paw(pen, pal, 17 + sw, 15, 4)
    pen.sprite(7, 3, HEAD_FRONT, pal)
    for ex in (10, 18):                    # olhos em tracinho com pálpebra pesada
        pen.px(ex, 8, 2, 1, pal["D"])
        pen.px(ex, 9, 2, 1, pal["E"])
    pen.px(9, 10, 2, 1, pal["P"])          # bochechas
    pen.px(19, 10, 2, 1, pal["P"])
    pen.px(14, 13, 2, 1, pal["N"])         # boquinha reta
    _fruit(pen, pal, 12 + sw, 0)
    if f % 4 in (1, 2):                    # gotinha de suor
        pen.px(24, 5, 1, 1, "#1d3a55")
        pen.px(23, 6, 3, 2, "#1d3a55")
        pen.px(24, 6, 1, 1, "#bfe6ff")
        pen.px(24, 7, 1, 1, "#7cc6f2")


def render(pen: Pen, anim: str, frame: int, look: int, light: str) -> None:
    pal = dict(PAL, F=light)
    f = frame
    last = ANIMS[anim][1] - 1

    if anim in ("stand", "curious"):
        chew = anim == "stand" and f % 4 in (1, 2)
        _standing(pen, pal, eyes="closed" if f == last else "open", mouth="chew" if chew else "calm",
                  look=look)
    elif anim == "walk":
        _standing(pen, pal, legs=("walk1", "stand", "walk2", "stand")[f], bob=(0, -1, 0, -1)[f])
    elif anim in ("think", "think_walk"):
        if anim == "think":
            _standing(pen, pal, eyes="up", mouth="chew" if f % 2 else "calm")
            _thought(pen, f)
        else:
            _standing(pen, pal, legs=("walk1", "stand", "walk2", "stand")[f % 4],
                      bob=(0, -1, 0, -1)[f % 4], eyes="up", mouth="chew" if f % 2 else "calm")
            _thought(pen, f // 2)
    elif anim == "happy":
        _standing(pen, pal, eyes="happy", ear="flick" if f % 2 else "normal", fruit_hop=-(f % 2))
        _fx(pen, "heart", f, 3)
    elif anim == "attention":
        _standing(pen, pal, legs="walk1" if f % 2 else "walk2", eyes="wide", mouth="open",
                  fruit_hop=(0, -2, -3, -1)[f])
        _fx(pen, "bang", f, 2)
    elif anim == "celebrate":
        _standing(pen, pal, legs="walk1" if f % 2 else "walk2", eyes="happy", mouth="open",
                  fruit_hop=-2 * (f % 2), ear="flick" if f % 2 else "normal")
        _fx(pen, "sparkle", f, 0)
    elif anim == "sit":
        _sitting(pen, pal, eyes="closed" if f == last else "open")
    elif anim == "waiting":
        _sitting(pen, pal, eyes="happy")
        _fx(pen, "check", f, 2)
    elif anim == "sleep":
        _lying(pen, pal, eyes="closed", breathe=f // 2 % 2)
        _fx(pen, "zzz", f, -1, 4)
    elif anim == "work":
        _working(pen, pal, light, f, last)
    elif anim == "dangle":
        _dangle(pen, pal, f)

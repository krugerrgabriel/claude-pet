"""Dragão: escamas pretas, asas vermelhas e chifres de osso, de perfil olhando pra direita.

É o único que voa: com o Claude trabalhando ele levanta voo e fica rodando pela tela
(ver FLIES_WHEN_WORKING e Pet._fly), batendo as asas e soltando fogo de vez em quando.
A luz do status é a brasa no peito (e o fogo, que sai na mesma cor).

Desenhado por máscaras, como o patinho: cada pose monta corpo, pescoço, cabeça, cauda e asas
como formas; contorno de 1px, luz em cima e sombra embaixo saem sozinhos.
"""
from __future__ import annotations

import math

from ..pixel import shade

LABEL = "Dragão"
SIDE_VIEW = True
PACE_THINKING = True
FLIES_WHEN_WORKING = True
HIT = (1, 5, 28, 25)
PIVOT = (14, 12)        # segurado pela nuca
OVERLAY_AT = {"thought": (2, 0), "zzz": (2, 6), "bang": (1, 1), "heart": (2, 0), "check": (2, 2)}

ANIMS = {
    "stand": (4, 12),
    "walk": (8, 4),
    "sit": (3, 8),
    "sleep": (2, 4),
    "curious": (5, 10),
    "happy": (8, 4),
    "think": (3, 8),
    "think_walk": (6, 8),
    "work": (9, 16),       # voando
    "attention": (10, 4),
    "celebrate": (10, 4),
    "waiting": (3, 4),
    "dangle": (12, 4),     # batendo as asas desesperado (segurado ou caindo do voo)
}

# ---------------------------------------------------------------- cores
OUT = "#0b0a0e"
BASE = "#2c2a33"
HI = "#4a4656"
SH = "#1b1a20"
FAR = "#1f1d25"
BELLY = "#5b4640"
BELLY_SH = "#43332f"
MEM = "#a8242a"
MEM_HI = "#d0433c"
MEM_SH = "#74161b"
MEM_FAR = "#5e1216"
BONE = "#d8c8a8"
BONE_SH = "#9c8c70"
EYE = "#ffc23a"
WHITE = "#ffffff"
FIRE_EDGE = "#ff5a1f"
FIRE_TIP = "#ffb03a"

N = 30
GROUND = 29


# ---------------------------------------------------------------- máscaras
def _ellipse(m, cx, cy, rx, ry, ang=0.0):
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    r = int(max(rx, ry)) + 2
    for y in range(int(cy) - r, int(cy) + r + 1):
        for x in range(int(cx) - r, int(cx) + r + 1):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            u, v = dx * ca + dy * sa, -dx * sa + dy * ca
            if (u / rx) ** 2 + (v / ry) ** 2 <= 1:
                m.add((x, y))


def _tube(m, pts):
    for (x0, y0, r0), (x1, y1, r1) in zip(pts, pts[1:]):
        steps = max(2, int(math.hypot(x1 - x0, y1 - y0) * 3))
        for i in range(steps + 1):
            t = i / steps
            r = r0 + (r1 - r0) * t
            _ellipse(m, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r, r)


def _poly(m, pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    for y in range(int(min(ys)) - 1, int(max(ys)) + 2):
        for x in range(int(min(xs)) - 1, int(max(xs)) + 2):
            px, py, inside = x + 0.5, y + 0.5, False
            for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
                if (y0 > py) != (y1 > py) and px < x0 + (py - y0) * (x1 - x0) / (y1 - y0):
                    inside = not inside
            if inside:
                m.add((x, y))


def _line(img, a, b, color):
    (x0, y0), (x1, y1) = a, b
    n = max(1, int(max(abs(x1 - x0), abs(y1 - y0))))
    for i in range(n + 1):
        t = i / n
        img[(round(x0 + (x1 - x0) * t - 0.5), round(y0 + (y1 - y0) * t - 0.5))] = color


def _stamp(img, mask, base=BASE, hi=HI, sh=SH, out=OUT):
    for (x, y) in mask:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in mask:
                img[(x + dx, y + dy)] = out
    for (x, y) in mask:
        if (x, y - 1) not in mask:
            img[(x, y)] = hi
        elif (x, y + 1) not in mask:
            img[(x, y)] = sh
        else:
            img[(x, y)] = base


# ---------------------------------------------------------------- partes
WINGS = {  # (cotovelo, [pontas dos dedos, da frente pra trás]) relativos ao ombro
    "fold": ((-3, -4), [(-7, -6), (-9, -1)]),
    "up": ((2, -8), [(-2, -14), (-7, -12), (-11, -6)]),
    "mid": ((2, -5), [(-4, -10), (-9, -7), (-12, -2)]),
    "level": ((1, -2), [(-6, -5), (-10, -3), (-12, 1)]),
    "down": ((1, 3), [(-2, 10), (-6, 9), (-9, 5)]),
}


def _wing(img, sx, sy, kind, far=False):
    """Asa de morcego: osso ombro→cotovelo, dedos até as pontas e membrana recortada entre eles."""
    (ex, ey), tips = WINGS[kind]
    if far:  # a asa de lá aparece um pouco mais alta e pra frente, escura
        sx, sy = sx + 2, sy - 1
    S, E = (sx, sy), (sx + ex, sy + ey)
    T = [(sx + tx, sy + ty) for tx, ty in tips]
    back = (sx - 6, sy + 1)
    outline = [S, E, T[0]]
    for a, b in zip(T, T[1:]):  # recorte: a borda entre dois dedos puxa pra dentro, em direção ao cotovelo
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        outline += [(mx + (E[0] - mx) * 0.3, my + (E[1] - my) * 0.3), b]
    outline.append(back)
    m = set()
    _poly(m, outline)
    if far:
        _stamp(img, m, MEM_FAR, MEM_FAR, MEM_FAR)
        _line(img, S, E, FAR)
        _line(img, E, T[0], FAR)
        return
    _stamp(img, m, MEM, MEM_HI, MEM_SH)
    _line(img, S, E, BASE)
    _line(img, E, T[0], BASE)
    if kind != "fold":
        for t in T[1:]:
            _line(img, E, t, MEM_SH)
    img[(round(E[0] - 0.5), round(E[1] - 0.5) - 1)] = BONE  # garrinha no cotovelo


def _horns(img, hx, hy):
    for (x, y, c) in ((hx - 2, hy - 3, BONE_SH), (hx - 3, hy - 4, BONE), (hx - 4, hy - 4, BONE),
                      (hx, hy - 3, BONE_SH), (hx - 1, hy - 4, BONE)):
        img[(int(x), int(y))] = c


def _eye(img, hx, hy, kind, look):
    ex, ey = int(hx) + (1 if look >= 0 else 0), int(hy) - 1
    if kind == "open":
        img[(ex, ey)] = EYE
        img[(ex + 1, ey)] = OUT                  # pupila de fenda
        img[(ex - 1, ey - 1)] = OUT              # sobrancelha brava
        img[(ex, ey - 1)] = OUT
    elif kind == "wide":
        img[(ex, ey)] = EYE
        img[(ex + 1, ey)] = EYE
        img[(ex, ey - 1)] = WHITE
        img[(ex + 1, ey - 1)] = EYE
    elif kind == "up":
        img[(ex, ey - 1)] = EYE
        img[(ex + 1, ey - 1)] = OUT
    elif kind == "happy":
        img[(ex - 1, ey)] = EYE
        img[(ex, ey - 1)] = EYE
        img[(ex + 1, ey)] = EYE
    elif kind == "closed":
        img[(ex - 1, ey)] = HI
        img[(ex, ey)] = HI
        img[(ex + 1, ey)] = HI


def _fire(img, x, y, light, length, up=False):
    """Baforada saindo da boca (x, y) pra frente (ou pra cima), miolo na cor do status."""
    for i in range(length):
        spread = min(i // 2, 2)
        for j in range(-spread, spread + 1):
            p = (x + j, y - i) if up else (x + i, y + j)
            edge = abs(j) == spread and spread > 0
            img[p] = FIRE_EDGE if edge else (FIRE_TIP if i == length - 1 else light)
    tip = (x, y - length) if up else (x + length, y)
    img[tip] = FIRE_TIP


def _ember(img, x, y, light):
    """Brasa no peito: a luz do status, com brilhinho."""
    img[(x, y)] = shade(light, 1.3)
    img[(x + 1, y)] = light
    img[(x, y + 1)] = light
    img[(x + 1, y + 1)] = shade(light, 0.7)


# ---------------------------------------------------------------- dragão inteiro
def _dragon(img, light, *, y=0, hx=22, hy=12, body=(13, 22, 7, 4), legs="stand", wing="fold",
            eyes="open", look=0, jaw=False, tail=0, fly=False, fire=0, fire_up=False):
    bx, by, brx, bry = body
    by += y
    hy += y
    sx, sy = bx + 2, by - bry + 1            # ombro
    if wing != "fold":
        _wing(img, sx, sy, wing, far=True)

    m = set()
    # pernas: as de lá primeiro (mais escuras), depois as de cá
    leg_pts = {
        "stand": [((bx - 3, 0), (bx + 4, 0))],
        "walkA": [((bx - 4, -1), (bx + 5, 1))],
        "walkB": [((bx - 2, 1), (bx + 3, -1))],
    }
    if legs in leg_pts:
        far = set()
        for (x0, d0), (x1, d1) in leg_pts[legs]:
            _tube(far, [(x0 + 2, by + 2, 1.2), (x0 + 2 + d0, GROUND - 1, 0.9)])
            _tube(far, [(x1 + 2, by + 2, 1.2), (x1 + 2 + d1, GROUND - 1, 0.9)])
        _stamp(img, far, FAR, FAR, FAR)
        for (x0, d0), (x1, d1) in leg_pts[legs]:
            _tube(m, [(x0, by + 2, 1.5), (x0 + d0, GROUND - 1, 1.0)])
            _tube(m, [(x1, by + 2, 1.5), (x1 + d1, GROUND - 1, 1.0)])
    elif legs == "tuck":
        _tube(m, [(bx - 3, by + 2, 1.3), (bx - 5, by + 4, 0.8)])
        _tube(m, [(bx + 4, by + 2, 1.3), (bx + 2, by + 4, 0.8)])
    elif legs == "hang":
        _tube(m, [(bx - 3, by + 2, 1.3), (bx - 3, by + 6, 0.8)])
        _tube(m, [(bx + 4, by + 2, 1.3), (bx + 4, by + 6, 0.8)])

    _ellipse(m, bx, by, brx, bry)
    # cauda: afina até a ponta, que balança
    tx0 = bx - brx + 1
    if fly:
        _tube(m, [(tx0, by, 2.2), (tx0 - 4, by + 2, 1.4), (1.5, by - 1 + tail, 0.7)])
        tip = (1, int(by - 1 + tail))
    else:
        _tube(m, [(tx0, by + 1, 2.2), (tx0 - 4, by + 3, 1.4), (1.5, by - 1 + tail, 0.7)])
        tip = (1, int(by - 1 + tail))
    # pescoço e cabeça
    _tube(m, [(bx + brx - 2, by - 1, 2.6), (hx - 1, hy + 1, 1.8)])
    _ellipse(m, hx, hy, 3.0, 2.3)
    _ellipse(m, hx + 3.2, hy + 0.7, 2.3, 1.4)
    if jaw:
        _ellipse(m, hx + 2.6, hy + 2.6, 2.0, 0.9)
    _stamp(img, m)

    # barriga clara por baixo do corpo e do pescoço
    for (x, yy) in m:
        if (x, yy + 1) not in m and img.get((x, yy)) == SH and bx - brx + 2 <= x <= hx:
            img[(x, yy)] = BELLY_SH
        if (x, yy + 2) not in m and (x, yy + 1) in m and bx - brx + 2 <= x <= hx - 1:
            img[(x, yy)] = BELLY
    # espinhos de osso ao longo das costas
    for x in range(tx0, bx + brx - 1, 2):
        top = min((yy for (xx, yy) in m if xx == x), default=None)
        if top is not None:
            img[(x, top - 1)] = BONE_SH
    # pontinha da cauda em lança
    img[(tip[0] - 1, tip[1])] = BONE
    img[(tip[0], tip[1] - 1)] = BONE
    img[tip] = BONE

    if jaw:  # boca aberta: risco vermelho entre as mandíbulas
        for x in range(int(hx + 1), int(hx + 5)):
            img[(x, int(hy + 2))] = MEM
    else:
        img[(int(hx + 3), int(hy + 1))] = OUT
        img[(int(hx + 4), int(hy + 1))] = OUT
    img[(int(hx + 5), int(hy))] = OUT            # narina
    _horns(img, hx, hy)
    _eye(img, hx, hy, eyes, look)
    _ember(img, int(bx + brx - 3), int(by), light)

    if wing == "fold":
        _wing(img, sx, sy, "fold")
    else:
        _wing(img, sx, sy, wing)
    if fire:
        if fire_up:
            _fire(img, int(hx + 3), int(hy - 2), light, fire, up=True)
        else:
            _fire(img, int(hx + 6), int(hy + 1 + (1 if jaw else 0)), light, fire)


def _blit(pen, img):
    for (x, y), c in img.items():
        if 0 <= x < N and 0 <= y < N:
            pen.px(x, y, 1, 1, c)


FLAP = ["up", "mid", "level", "down", "level", "mid"]


# ---------------------------------------------------------------- animações
def render(pen, anim: str, f: int, look: int, light: str) -> None:
    img: dict = {}
    if anim == "stand":
        breathe = 1 if f in (4, 5, 6) else 0
        _dragon(img, light, body=(13, 22, 7, 4), hy=12 - breathe, tail=(0, 0, 1, 1, 0, 0)[f % 6],
                eyes="closed" if f == 11 else "open", look=look)
    elif anim == "walk":
        _dragon(img, light, y=-(f % 2), legs="walkA" if f < 2 else "walkB", tail=(0, 1, 0, -1)[f], look=look)
    elif anim == "sit":
        _dragon(img, light, y=2, legs="sit", hy=13, tail=(0, 0, 1, 1, 0, 0, 0, 0)[f],
                eyes="closed" if f == 7 else "open", look=look)
    elif anim == "sleep":
        # enrolado no chão, cabeça apoiada na frente, fumacinha saindo da narina
        _dragon(img, light, y=3, legs="sit", hx=22, hy=21, tail=2, eyes="closed")
        if f % 2:
            img[(28, 20 + 3 - f)] = "#8a8f99"
    elif anim == "curious":
        _dragon(img, light, hx=23 if look > 0 else 21, hy=10, look=look, eyes="wide" if f < 8 else "open")
    elif anim == "happy":
        _dragon(img, light, y=-(f % 2) * 2, wing=FLAP[f % 4 * 3 // 2 % len(FLAP)], eyes="happy", jaw=True, look=1)
    elif anim == "think":
        _dragon(img, light, hy=11, hx=21, eyes="up", tail=(0, 1, 2, 1, 0, -1, 0, 0)[f])
        if f % 4 in (1, 2):  # fiapinho de fumaça pensando
            img[(26, 9 - f % 4)] = "#8a8f99"
    elif anim == "think_walk":
        _dragon(img, light, y=-(f % 2), hx=21, hy=11, legs="walkA" if f % 4 < 2 else "walkB",
                eyes="up", tail=(0, 1, 0, -1)[f % 4], look=look)
    elif anim == "work":
        # voando: corpo deitado, pernas encolhidas, asas batendo, sobe e desce no ritmo da batida
        wing = FLAP[f % len(FLAP)]
        bob = {"up": 1, "mid": 0, "level": 0, "down": -1}[wing]
        fire = (0,) * 9 + (2, 3, 5, 6, 6, 4, 0)
        _dragon(img, light, y=bob, hx=19, hy=13, body=(11, 17, 7, 3), legs="tuck", wing=wing, fly=True,
                tail=(f % 4) - 1, jaw=fire[f] > 0, fire=fire[f], look=1)
    elif anim == "attention":
        _dragon(img, light, wing=("up", "mid")[f % 2], eyes="wide", jaw=True, hy=10, look=1)
    elif anim == "celebrate":
        _dragon(img, light, y=-2, wing=("up", "level", "down", "level")[f], eyes="happy", jaw=True, hx=21, hy=9,
                fire=(3, 5, 5, 0)[f], fire_up=True, look=1)
    elif anim == "waiting":
        _dragon(img, light, y=2, legs="sit", hy=13, eyes="happy", tail=(0, 1, 2, 1)[f], look=1)
    elif anim == "dangle":
        wing = ("up", "level", "down", "level")[f]
        _dragon(img, light, hx=21, hy=12, body=(12, 17, 6, 3), legs="hang", wing=wing, fly=True,
                eyes="wide", jaw=True, tail=(1, 0, -1, 0)[f])
    _blit(pen, img)

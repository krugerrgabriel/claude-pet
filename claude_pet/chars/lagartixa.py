"""Lagartixa (gecko) de perfil, olhando pra direita.

Desenhada por "formas": cada pose monta máscaras (elipses, discos ao longo do rabo, patinhas)
e o contorno de 1px, a luz em cima e a sombra embaixo saem automaticamente da máscara.
Por cima vêm os detalhes (olho, boca, bochecha, pintinhas de status, notebook).
"""
from __future__ import annotations

import math

from ..pixel import THOUGHT_CLOUD, THOUGHT_COLORS, draw_computer

LABEL = "Lagartixa"
SIDE_VIEW = True
PACE_THINKING = True
HIT = (1, 12, 28, 18)          # simétrico na horizontal: vale virada pros dois lados
PIVOT = (15, 0)                # agarrada pela ponta do rabo
OVERLAY_AT = {"heart": (0, 2)}
# o balão de pensamento ela desenha sozinha, ancorado no topo da cabeça (que muda de pose pra pose)
OVERLAYS = {"think": None, "think_walk": None}

ANIMS = {
    "stand": (5, 14),
    "walk": (8, 4),
    "sit": (5, 14),
    "sleep": (2, 4),
    "curious": (5, 10),
    "happy": (6, 4),
    "think": (3, 8),
    "think_walk": (6, 8),
    "work": (6, 8),
    "attention": (5, 2),
    "celebrate": (6, 2),
    "waiting": (2, 4),
    "dangle": (4, 2),
}

# ---------------------------------------------------------------- cores
OUT = "#2b5236"
BASE = "#9adf80"
HI = "#c8f3ab"
SH = "#74bf63"
BELLY = "#eef9d2"
BELLY_SH = "#d3ebb0"
FAR = "#7cc56a"
TOE = "#d9f8c4"
EYE = "#1d2b3a"
EYE_HI = "#ffffff"
EYE_HI2 = "#5b7a8c"
BLUSH = "#f5a3b8"
TONGUE = "#ff7aa2"
LAPTOP = "#aab4be"
LAPTOP_DARK = "#3b4652"

N = 30


# ---------------------------------------------------------------- máscaras
def _ellipse(m, cx, cy, rx, ry, ang=0.0, belly=None):
    """Elipse (girada `ang` graus); `belly` = fração de baixo (no eixo local) que vira barriga."""
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    r = int(max(rx, ry)) + 2
    for y in range(int(cy) - r, int(cy) + r + 1):
        for x in range(int(cx) - r, int(cx) + r + 1):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            u = dx * ca + dy * sa
            v = -dx * sa + dy * ca
            if (u / rx) ** 2 + (v / ry) ** 2 <= 1:
                kind = "u" if belly is not None and v > ry * belly else "b"
                if kind == "u":
                    m[(x, y)] = "u"
                else:
                    m.setdefault((x, y), "b")


def _disc(m, cx, cy, r, kind="b"):
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= r * r:
                m.setdefault((x, y), kind)


def _tube(m, pts, kind="b"):
    """Rabo/perna: discos ao longo de [(x, y, raio), ...]."""
    for (x0, y0, r0), (x1, y1, r1) in zip(pts, pts[1:]):
        steps = max(2, int(math.hypot(x1 - x0, y1 - y0) * 3))
        for i in range(steps + 1):
            t = i / steps
            _disc(m, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r0 + (r1 - r0) * t, kind)


def _foot(m, x, y, toes, kind="b"):
    """Pé com dedinhos: pontas ('t') redondinhas."""
    for dx in range(-1, 2):
        m.setdefault((x + dx, y), kind)
    if toes:
        m[(x + 1, y)] = "t"
        m[(x - 1, y)] = "t" if kind != "f" else "f"


def _leg(m, hip, foot, kind="b", toes=True):
    (hx, hy), (fx, fy) = hip, foot
    _tube(m, [(hx, hy, 1.0), (fx + 0.5, fy, 0.75)], kind)
    _foot(m, int(fx), int(fy), toes, kind)


# ---------------------------------------------------------------- composição
def _stamp(img, mask, shade=True):
    for (x, y) in mask:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in mask:
                img[n] = OUT
    for (x, y), kind in mask.items():
        up, down = (x, y - 1) in mask, (x, y + 1) in mask
        if kind == "u":
            c = BELLY if down else BELLY_SH
        elif kind == "t":
            c = TOE
        elif kind == "f":
            c = FAR
        elif not shade:
            c = BASE
        elif not up:
            c = HI
        elif not down:
            c = SH
        else:
            c = BASE
        img[(x, y)] = c


def _spot(img, x, y, light):
    """Pintinha 2x2 com aro escuro em volta (onde for corpo), pra ler em qualquer cor de status."""
    for dx in range(-1, 3):
        for dy in range(-1, 3):
            q = (x + dx, y + dy)
            if 0 <= dx <= 1 and 0 <= dy <= 1:
                img[q] = light
            elif img.get(q) in (BASE, HI) and (dx in (0, 1) or dy in (0, 1)):
                img[q] = SH


def _spots(img, mask, cols, light, vertical=False):
    """Pintinhas de status no dorso: 2x2 logo abaixo da borda de cima do corpo (ou da esquerda)."""
    for c in cols:
        if vertical:
            xs = [x for (x, y) in mask if y == c and mask[(x, y)] == "b"]
            if not xs:
                continue
            _spot(img, min(xs) + 1, c, light)
        else:
            ys = [y for (x, y) in mask if x == c and mask[(x, y)] == "b"]
            if not ys:
                continue
            _spot(img, c, min(ys) + 1, light)


def _head(img, hx, hy, eye="open", look=0, gaze=0, mouth="smile", tongue=False, blush=True):
    """Detalhes do rosto. (hx, hy) = centro da cabeça; o focinho fica pra direita."""
    ex, ey = int(hx) - 2 + look, int(hy) - 3 + gaze
    p = img.__setitem__

    def grid(rows, pal):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch in pal:
                    p((ex + i, ey + j), pal[ch])

    if eye == "open":
        grid([".EEE.", "EWWEE", "EWEEE", "EEEgE", ".EEE."], {"E": EYE, "W": EYE_HI, "g": EYE_HI2})
    elif eye == "wide":
        grid([".OOO.", "OWWWO", "WWEEW", "WWEWW", ".WWW."], {"O": OUT, "W": EYE_HI, "E": EYE})
        p((ex + 3, ey + 3), EYE)
        p((ex + 2, ey + 3), EYE_HI)
    elif eye == "happy":  # arco ^
        grid(["..E..", ".E.E.", "E...E"], {"E": EYE})
    elif eye == "closed":  # arco pra baixo, dormindo
        grid(["", "", "E...E", ".EEE."], {"E": EYE})
    if blush:
        p((int(hx) - 3, int(hy) + 2), BLUSH)
        p((int(hx) - 2, int(hy) + 2), BLUSH)
    mx, my = int(hx) + 3, int(hy) + 2
    p((mx + 3, my - 3), OUT)  # narina
    if mouth == "smile":
        p((mx, my), OUT)
        p((mx + 1, my + 1), OUT)
        p((mx + 2, my + 1), OUT)
        p((mx + 3, my), OUT)
    elif mouth == "o":
        p((mx + 1, my), OUT)
        p((mx + 2, my), OUT)
        p((mx + 1, my + 1), TONGUE)
        p((mx + 2, my + 1), OUT)
    elif mouth == "open":
        for dx in range(0, 4):
            p((mx + dx, my), OUT)
        p((mx + 1, my + 1), TONGUE)
        p((mx + 2, my + 1), TONGUE)
        p((mx, my + 1), OUT)
        p((mx + 3, my + 1), OUT)
        p((mx + 1, my + 2), OUT)
        p((mx + 2, my + 2), OUT)
    if tongue:
        p((mx + 4, my), TONGUE)
        p((mx + 5, my), TONGUE)
        p((mx + 6, my - 1), TONGUE)


# ---------------------------------------------------------------- poses
def _tail(base_x, base_y, wag=0.0, curl=1.0):
    """Rabo grosso na base afinando, com curvinha na ponta. `wag` mexe a ponta pra cima/baixo."""
    return [(base_x, base_y, 1.9), (base_x - 3, base_y + 1.0, 1.55), (base_x - 5.5, base_y + 0.6 - wag * 0.4, 1.2),
            (base_x - 6.6, base_y - 1.2 - wag, 0.95), (base_x - 6.0, base_y - 2.8 * curl - wag, 0.75),
            (base_x - 4.8, base_y - 3.3 * curl - wag, 0.55)]


def _build(p, light):
    """Monta a imagem de uma pose (dict) → {(x, y): cor}."""
    img = {}
    far, main = {}, {}
    ox, oy = p.get("dx", 0), p.get("dy", 0)

    for leg in p.get("far_legs", []):
        hip, foot = leg
        _leg(far, (hip[0] + ox, hip[1] + oy), (foot[0] + ox, foot[1]), "f", toes=False)

    bx, by, brx, bry, bang = p["body"]
    _ellipse(main, bx + ox, by + oy, brx, bry, bang, belly=0.35)
    hx, hy, hrx, hry = p["head"]
    hx, hy = hx + ox, hy + oy
    head = {} if p.get("head_on_top") else main
    _ellipse(head, hx, hy, hrx, hry, p.get("head_ang", 0), belly=0.55)
    sx, sy = p.get("snout", (3.2, 1.0))
    _ellipse(head, hx + sx, hy + sy, 3.0, 2.8, belly=0.45)
    _tube(main, [(x + ox, y + oy, r) for x, y, r in p["tail"]])
    for hip, foot in p.get("legs", []):
        _leg(main, (hip[0] + ox, hip[1] + oy), (foot[0] + ox, foot[1] + (oy if p.get("legs_follow") else 0)))

    _stamp(img, far)
    _stamp(img, main)
    if p.get("front_tail"):
        front = {}
        _tube(front, [(x + ox, y + oy, rr) for x, y, rr in p["front_tail"]])
        _stamp(img, front)
    for hip, foot in p.get("tucked", []):  # patinhas dobradas, por cima do corpo
        paw = {}
        _tube(paw, [(hip[0], hip[1], 0.9), (foot[0], foot[1], 0.8)])
        _disc(paw, foot[0] + 0.5, foot[1], 0.9, "t")
        _stamp(img, paw)
    if head is not main:
        _stamp(img, head)
    if p.get("table"):
        _table(img, *p["table"])
    if p.get("laptop_back"):
        _laptop_back(img, p["laptop_back"], light, p.get("paws_up", 0), paws=not p.get("table"))
    if not p.get("no_spots"):
        _spots(img, main, [c + ox for c in p.get("spot_cols", [])], light, vertical=p.get("spots_vertical", False))
    if p.get("spot_rows") and not p.get("no_spots"):
        _spots(img, main, [r + oy for r in p["spot_rows"]], light, vertical=True)

    if p.get("laptop"):
        _laptop(img, p["laptop"], light)
    for (x, y, c) in p.get("extra", []):
        img[(x + ox, y + oy)] = {"O": OUT, "B": BASE, "T": TOE, "H": HI}.get(c, c)

    _head(img, hx, hy, p.get("eye", "open"), p.get("look", 0), p.get("gaze", 0), p.get("mouth", "smile"),
          p.get("tongue", False))
    return {k: v for k, v in img.items() if 0 <= k[0] < N and 0 <= k[1] < N}


WOOD_OUT = "#4a2c1d"
WOOD = "#c98f5a"
WOOD_HI = "#e0ad78"
WOOD_SH = "#a06a3d"


def _table(img, x0, top, w):
    """Mesinha: tampo de 2 linhas com contorno + 2 perninhas finas até o chão (contorno em y=29)."""
    for x in range(x0, x0 + w):
        img[(x, top - 1)] = WOOD_OUT
        img[(x, top)] = WOOD_HI
        img[(x, top + 1)] = WOOD_SH
        img[(x, top + 2)] = WOOD_OUT
    for y in range(top - 1, top + 3):
        img[(x0 - 1, y)] = WOOD_OUT
        img[(x0 + w, y)] = WOOD_OUT
    img.pop((x0 - 1, top - 1), None)              # cantos arredondados
    img.pop((x0 + w, top - 1), None)
    for lx in (x0 + 1, x0 + w - 3):
        for y in range(top + 3, 29):
            img[(lx, y)] = WOOD_OUT
            img[(lx + 1, y)] = WOOD
            img[(lx + 2, y)] = WOOD_OUT
        for x in (lx, lx + 1, lx + 2):
            img[(x, 29)] = WOOD_OUT


def _laptop_back(img, at, light, up, paws=True):
    """Notebook visto de trás: tampa escura com borda e logo aceso; patinhas digitando por cima."""
    x0, y0 = at
    w, h = 7, 5
    for x in range(x0 - 1, x0 + w + 1):          # base (teclado) aparecendo embaixo
        img[(x, y0 + h)] = LAPTOP
        img[(x, y0 + h + 1)] = LAPTOP_DARK
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            edge = x in (x0, x0 + w - 1) or y in (y0, y0 + h - 1)
            img[(x, y)] = "#252c35" if edge else "#3b4652"
    for x in range(x0 + 1, x0 + w - 1):
        img[(x, y0 + 1)] = "#4f5b68"              # brilho na beirada de cima
    cx, cy = x0 + w // 2 - 1, y0 + 2
    for dx in (0, 1):
        for dy in (0, 1):
            img[(cx + dx, cy + dy)] = light       # logo na cor do status
    # patinhas da frente na beirada de cima, alternando
    for i, px in enumerate((x0 + 4,) if paws else ()):
        py = y0 - 2 - (0 if up else 1)
        for dx, dy in ((-1, 0), (2, 0), (-1, 1), (2, 1), (0, -1), (1, -1)):
            img[(px + dx, py + dy)] = OUT
        img[(px, py)] = FAR
        img[(px + 1, py)] = FAR
        img[(px, py + 1)] = FAR
        img[(px + 1, py + 1)] = FAR
        img[(px, py + 2)] = FAR if py + 2 < y0 else img[(px, py + 2)]
        img[(px + 1, py + 2)] = FAR if py + 2 < y0 else img[(px + 1, py + 2)]
        if py + 2 < y0:
            img[(px - 1, py + 2)] = OUT
            img[(px + 2, py + 2)] = OUT


def _laptop(img, x0, light):
    """Notebookzinho de perfil (tampa aberta pra ela): base com teclinhas e tela acesa na cor do status."""
    for x in range(x0, x0 + 7):
        img[(x, 28)] = LAPTOP_DARK
        img[(x, 27)] = LAPTOP
        img[(x, 26)] = LAPTOP_DARK
    for x in range(x0 + 1, x0 + 5, 2):
        img[(x, 27)] = "#c9d1d9"
    # tampa: inclinada pra trás, 3px (contorno, tela, costas)
    for i, y in enumerate(range(25, 18, -1)):
        x = x0 + 5 + (i + 1) // 3
        img[(x - 1, y)] = LAPTOP_DARK
        img[(x, y)] = light if 19 < y < 25 else LAPTOP_DARK
        img[(x + 1, y)] = LAPTOP_DARK
    img[(x0 + 8, 18)] = LAPTOP_DARK
    img[(x0 + 7, 18)] = LAPTOP_DARK


# pose base, em pé, virada pra direita
STAND = {
    "body": (13.5, 24.3, 6.8, 3.3, 0),
    "head": (22.0, 19.6, 5.4, 4.8),
    "tail": _tail(8.5, 24.6),
    "legs": [((9.5, 25.5), (9, 28)), ((18, 25.5), (19, 28))],
    "far_legs": [((11.5, 25), (12, 28)), ((19.5, 25), (21, 28))],
    "spot_cols": [8, 12, 16],
}


def _walk_legs(phase):
    """Patas em diagonal alternada: fase 0 / 2 = passos opostos, 1 / 3 = meio."""
    s = {0: 1.5, 1: 0, 2: -1.5, 3: 0}[phase]
    return ([((9.5, 25.5), (9 + s, 28)), ((18, 25.5), (19 - s, 28))],
            [((11.5, 25), (12 - s, 28)), ((19.5, 25), (21 + s, 28))])


def _walk(phase, **kw):
    legs, far = _walk_legs(phase)
    bob = -1 if phase in (1, 3) else 0
    wag = {0: 0.6, 1: 0, 2: -0.6, 3: 0}[phase]
    return dict(STAND, legs=legs, far_legs=far, dy=bob, tail=_tail(8.5, 24.6, wag=wag), **kw)


SIT = {
    "body": (13.5, 23.2, 6.0, 3.4, -28),
    "head": (20.5, 15.0, 5.4, 4.8),
    "tail": [(9, 26.5, 1.9), (6, 27.6, 1.5), (3.2, 27.4, 1.2), (1.6, 26.0, 0.95), (1.8, 24.2, 0.75),
             (3.0, 23.5, 0.55)],
    "legs": [((10.5, 26), (10, 28)), ((17.5, 22.5), (18.5, 28))],
    "far_legs": [((12, 26.5), (13, 28)), ((18.5, 22.5), (20.5, 28))],
    "spot_cols": [10, 13],
}

SLEEP = {
    # a mesma silhueta do stand, deitada: barriga no chão, queixo apoiado, rabo esticado
    # pra trás com a pontinha curvada pra cima; pernas dobradas, só os dedinhos aparecem
    "body": (13.5, 25.9, 6.8, 2.7, 0),
    "head": (21.8, 24.4, 5.2, 4.2),
    "snout": (3.2, 1.3),
    "tail": _tail(8.5, 26.4),
    "legs": [],
    "far_legs": [],
    "extra": [(9, 28, "T"), (10, 28, "T"), (18, 28, "T"), (19, 28, "T")],
    "no_spots": True,
}


WORK = {
    # sentada ereta (como no sit), mesinha na altura do peito com o notebook (visto de trás)
    "body": (8.5, 22.6, 6.0, 3.4, -42),
    "head": (14.0, 13.2, 5.4, 4.8),
    "tail": [(4.6, 26.6, 1.9), (2.4, 27.6, 1.5), (1.0, 26.8, 1.15), (0.9, 25.2, 0.85), (1.9, 24.2, 0.6)],
    "legs": [((5.6, 26), (5.0, 28))],
    "far_legs": [((7.2, 26.5), (8.2, 28))],
    "spot_cols": [4, 7],
    "table": (17, 23, 12),
    "computer": ((20, 13), (17, 20)),   # monitor (do lado oposto) e teclado (embaixo das patinhas)
}


def _work(frame):
    up = frame % 2
    near = ((12.0, 19.6), (19.4, 20.4 if up else 21.0))
    far = ((12.8, 18.8), (21.6, 21.0 if up else 20.4), "far")
    return dict(WORK, gaze=1, look=1, eye="closed" if frame == 7 else "open", arms=[far, near])


ATTN = {
    "body": (13, 22.5, 6.3, 3.4, -38),
    "head": (19.0, 14.6, 5.4, 4.8),
    "tail": [(9, 26.5, 1.9), (6, 27.6, 1.5), (3.2, 27.4, 1.2), (1.6, 26.0, 0.95), (1.8, 24.2, 0.75),
             (3.0, 23.5, 0.55)],
    "legs": [((10.5, 26), (10, 28))],
    "far_legs": [((12, 26.5), (13, 28))],
    "spot_cols": [10, 13],
}


def _attention(frame):
    # bracinho da frente acenando
    arm = [((17.0, 21.5), (22.5, 23.2 if frame == 0 else 21.6))]
    m = dict(ATTN, eye="wide", mouth="o")
    m["legs"] = ATTN["legs"]
    m["arms"] = arm
    return m


def _dangle(frame):
    """Pendurada pelo rabo: rabo sai do alto, corpo vertical, cabeça embaixo olhando pra frente."""
    sway = 0.5 if frame else -0.5
    return {
        "body": (14.5 + sway * 0.3, 15.2, 3.4, 6.0, 0),
        "head": (16.5 + sway * 0.5, 23.5, 4.8, 4.3),
        "snout": (3.0, 0.6),
        "tail": [(15, 0, 0.6), (15.3, 2.5, 0.9), (14.8, 5.5, 1.3), (14.5, 9.0, 1.8)],
        "legs": [],
        "far_legs": [],
        "arms": [((11.8, 11.5), (8.5 - sway, 14.0)), ((11.8, 17.5), (8.5 - sway, 20.0)),
                 ((17.2, 11.5), (20.5 + sway, 14.0)), ((17.2, 17.5), (20.5 + sway, 20.0))],
        "spot_rows": [11, 14],
        "eye": "wide",
        "mouth": "o",
    }


def _pose(anim, frame, look):
    if anim == "stand":
        return dict(STAND, eye="closed" if frame == 13 else "open",
                    tail=_tail(8.5, 24.6, wag=0.5 if 5 <= frame <= 7 else 0))
    if anim == "walk":
        return _walk(frame)
    if anim == "sit":
        return dict(SIT, eye="closed" if frame == 13 else "open")
    if anim == "sleep":
        b = 1.0 if frame >= 2 else 0.0   # respira: o dorso sobe 1px e volta
        return dict(SLEEP, eye="closed", mouth="smile", body=(13.5, 25.9 - b / 2, 6.8, 2.7 + b / 2, 0))
    if anim == "curious":
        lk = -1 if look < 0 else (1 if look > 0 else 0)
        return dict(STAND, head=(22.0, 18.8, 5.4, 4.8), look=lk, eye="closed" if frame == 9 else "open")
    if anim == "happy":
        wag = (1.2, -0.6, 1.2, -0.6)[frame]
        return dict(STAND, eye="happy", mouth="open", tail=_tail(8.5, 24.6, wag=wag))
    if anim == "think":
        lk = (0, 1, 1, 0, -1, -1, 0, 0)[frame]
        return dict(SIT, gaze=-1, look=lk, mouth="none", tongue=frame in (2, 3, 6))
    if anim == "think_walk":
        return _walk(frame % 4, gaze=-1, mouth="none", tongue=frame // 2 % 2 == 1, head=(21.6, 18.4, 5.4, 4.8))
    if anim == "work":
        return _work(frame)
    if anim == "attention":
        return _attention(frame)
    if anim == "celebrate":
        if frame == 0:
            return dict(STAND, eye="happy", mouth="open")
        legs = [((9.5, 25.5), (7.5, 27)), ((18, 25.5), (20.5, 27))]
        far = [((11.5, 25), (10.5, 27)), ((19.5, 25), (22.5, 27))]
        return dict(STAND, eye="happy", mouth="open", legs=legs, far_legs=far, tail=_tail(8.5, 24.6, wag=1.4))
    if anim == "waiting":
        m = dict(SIT, eye="happy", mouth="smile")
        if frame == 3:
            m["tail"] = [(9, 26.5, 1.9), (6, 27.6, 1.5), (3.2, 27.0, 1.2), (1.8, 25.0, 0.95), (2.4, 22.8, 0.75),
                         (3.8, 22.0, 0.55)]
        return m
    if anim == "dangle":
        return _dangle(frame)
    return dict(STAND)


_CACHE: dict = {}
_ARMS: dict = {}   # (camada das patinhas, posição do computador) das poses com computador


def _image(anim, frame, look, light):
    key = (anim, frame, look, light)
    img = _CACHE.get(key)
    if img is None:
        pose = _pose(anim, frame, look)
        img = _build(pose, light)
        arms_img = {} if pose.get("computer") else img
        for arm_spec in pose.get("arms", []):  # braço levantado, por cima do corpo
            hip, hand = arm_spec[0], arm_spec[1]
            behind = len(arm_spec) > 2
            arm = {}
            _tube(arm, [(hip[0], hip[1], 1.0), (hand[0], hand[1], 0.85)])
            _disc(arm, hand[0] + 0.5, hand[1], 1.0, "t")
            for (x, y) in arm:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (x + dx, y + dy)
                    if n not in arm and math.hypot(n[0] + 0.5 - hip[0], n[1] + 0.5 - hip[1]) > 1.6:
                        arms_img[n] = OUT
            for (x, y), v in arm.items():
                if behind:
                    arms_img[(x, y)] = FAR
                else:
                    arms_img[(x, y)] = HI if v == "t" else (HI if (x, y - 1) not in arm else BASE)
        if arms_img is not img:
            _ARMS[key] = (pose["computer"], arms_img)
        if len(_CACHE) > 600:
            _CACHE.clear()
            _ARMS.clear()
        _CACHE[key] = img
    return img


def _thought_anchor(anim, frame, look):
    """(col, topo): coluna da bolinha menor e a linha de cima da cabeça nessa coluna."""
    pose = _pose(anim, frame, look)
    img = _image(anim, frame, look, "#000000")
    hx = pose["head"][0] + pose.get("dx", 0)
    col = min(int(hx) - 3, 16)                 # nuvem (12px) começa em col+2: cabe até a borda
    return col, min(y for (x, y) in img if x == col)


def _bubble(pen, x, y, size):
    """Bolinha de pensamento com contorno (cantos abertos = redondinha)."""
    o, w = THOUGHT_COLORS["O"], THOUGHT_COLORS["W"]
    pen.px(x, y - 1, size, 1, o)
    pen.px(x, y + size, size, 1, o)
    pen.px(x - 1, y, 1, size, o)
    pen.px(x + size, y, 1, size, o)
    pen.px(x, y, size, size, w)


def _thought(pen, anim, frame, look):
    """Balão saindo da cabeça: bolinha 1x1 encostada nela, 2x2 em diagonal, nuvem em cima."""
    col, top = _thought_anchor(anim, frame, look)
    f = frame if anim == "think" else frame // 2
    step = f % 4
    _bubble(pen, col, top - 2, 1)
    if step >= 1:
        _bubble(pen, col + 2, top - 5, 2)
    cx, cy = col + 2, top - 11                 # think: topo da nuvem em y=0
    pen.sprite(cx, cy, THOUGHT_CLOUD, THOUGHT_COLORS)
    for k in range(min(3, step + 1)):
        pen.px(cx + 3 + k * 3, cy + 3, 1, 1, THOUGHT_COLORS["d"])


def _blit(pen, img):
    for y in range(N):
        x = 0
        while x < N:
            c = img.get((x, y))
            if c is None:
                x += 1
                continue
            k = x
            while k < N and img.get((k, y)) == c:
                k += 1
            pen.px(x, y, k - x, 1, c)
            x = k


def render(pen, anim, frame, look, light):
    img = _image(anim, frame, look, light)
    _blit(pen, img)
    extra = _ARMS.get((anim, frame, look, light))
    if extra:
        (mon, kb), arms_img = extra
        draw_computer(pen, mon[0], mon[1], light, frame, keyboard_at=kb)
        _blit(pen, arms_img)
    if anim in ("think", "think_walk"):
        _thought(pen, anim, frame, look)

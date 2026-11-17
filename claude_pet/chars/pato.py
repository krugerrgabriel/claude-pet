"""Patinho amarelo de perfil, olhando pra direita, com cachecol na cor do status.

Desenhado por formas, como a lagartixa: cada pose monta máscaras (círculos, elipses, tubos) e o
contorno de 1px, a luz em cima e a sombra embaixo saem sozinhos. Por cima vêm bico, olho e bochecha.
"""
from __future__ import annotations

import math

from ..pixel import THOUGHT_CLOUD, THOUGHT_COLORS, draw_computer, shade

LABEL = "Patinho"
SIDE_VIEW = True
PACE_THINKING = True
HIT = (3, 6, 24, 24)
PIVOT = (15, 3)          # segurado pelo topetinho (pose pendurada, de frente)
OVERLAYS = {"think": None, "think_walk": None}   # o balão ele desenha sozinho, saindo da cabeça
OVERLAY_AT = {"zzz": (1, 2), "heart": (1, 0), "check": (1, 2)}

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
    "attention": (6, 4),
    "celebrate": (6, 2),
    "waiting": (2, 4),
    "dangle": (4, 4),
}

# ---------------------------------------------------------------- cores
OUT = "#5c3a12"
BASE = "#ffd94a"
HI = "#fff1a0"
SH = "#f0b232"
WING = "#f9c53c"
WING_HI = "#ffe27a"
WING_SH = "#e8a62a"
WING_OUT = "#c97f16"
BEAK = "#ff9a3c"
BEAK_HI = "#ffc07a"
BEAK_SH = "#e2681e"
FOOT = "#ff9a3c"
FOOT_FAR = "#d9692a"
EYE = "#2a1a10"
EYE_HI = "#ffffff"
BLUSH = "#ff8fa3"
MOUTH = "#a8401a"

N = 30


# ---------------------------------------------------------------- máscaras
def _ellipse(m, cx, cy, rx, ry, ang=0.0, kind="b"):
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    r = int(max(rx, ry)) + 2
    for y in range(int(cy) - r, int(cy) + r + 1):
        for x in range(int(cx) - r, int(cx) + r + 1):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            u, v = dx * ca + dy * sa, -dx * sa + dy * ca
            if (u / rx) ** 2 + (v / ry) ** 2 <= 1:
                m.setdefault((x, y), kind)


def _disc(m, cx, cy, r, kind="b"):
    _ellipse(m, cx, cy, r, r, 0, kind)


def _tube(m, pts, kind="b"):
    for (x0, y0, r0), (x1, y1, r1) in zip(pts, pts[1:]):
        steps = max(2, int(math.hypot(x1 - x0, y1 - y0) * 3))
        for i in range(steps + 1):
            t = i / steps
            _disc(m, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r0 + (r1 - r0) * t, kind)


def _stamp(img, mask, base=BASE, hi=HI, sh=SH, low=None, out=OUT):
    """Contorno + preenchimento: borda de cima clara, borda de baixo (e abaixo de `low`) na sombra."""
    for (x, y) in mask:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in mask:
                # por cima do corpo o contorno é suave (dobra de pena); fora dele, contorno normal
                img[q] = out if img.get(q) in (BASE, HI, SH, out) else OUT
    for (x, y) in mask:
        if (x, y - 1) not in mask:
            c = hi
        elif (x, y + 1) not in mask or (low is not None and y >= low):
            c = sh
        else:
            c = base
        img[(x, y)] = c


# ---------------------------------------------------------------- partes
def _foot(img, x, y, far=False):
    """Pezinho de pato: chato, 4px pra frente, com contorno; (x, y) = calcanhar, y = linha do pé."""
    c = FOOT_FAR if far else FOOT
    for i in range(4):
        img[(x + i, y)] = c
        img[(x + i, y + 1)] = OUT
    img[(x - 1, y)] = OUT
    img[(x + 4, y)] = OUT
    img[(x + 1, y - 1)] = c                      # perninha
    img[(x, y - 1)] = OUT
    img[(x + 2, y - 1)] = OUT


def _beak(img, hx, hy, kind="closed", down=0):
    """Bico chato saindo da cabeça (centro hx, hy) pra direita."""
    bx, by = hx + 4, hy + 1 + down
    m = {}
    if kind == "open":
        _ellipse(m, bx + 2.0, by - 0.6, 2.6, 1.1)
        _ellipse(m, bx + 1.6, by + 1.6, 2.1, 0.9)
    else:
        _ellipse(m, bx + 1.8, by + 0.5, 2.5, 1.6)
    for (x, y) in m:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in m and img.get((x + dx, y + dy)) not in (BASE, HI, SH) or \
                    ((x + dx, y + dy) not in m and dx > 0):
                img[(x + dx, y + dy)] = OUT
    for (x, y) in m:
        img[(x, y)] = BEAK_HI if (x, y - 1) not in m else (BEAK_SH if (x, y + 1) not in m else BEAK)
    if kind == "open":                           # bocão aberto: "quack!"
        xs = sorted({x for (x, y) in m})
        for x in xs[1:-1]:
            img[(x, int(by + 0.5))] = MOUTH
    else:                                        # risquinho da boca
        img[(int(bx) + 2, int(by + 1))] = BEAK_SH
        img[(int(bx) + 3, int(by + 1))] = BEAK_SH


def _eye(img, hx, hy, kind="open", look=0, gaze=0):
    ex, ey = int(hx) + 1 + (1 if look > 0 else 0) - (1 if look < 0 else 0), int(hy) - 2 + gaze
    p = img.__setitem__
    if kind == "open":
        for dx in (0, 1):
            for dy in (0, 1, 2):
                p((ex + dx, ey + dy), EYE)
        p((ex, ey), EYE_HI)
    elif kind == "wide":                         # arregalado: olho redondo maior com brilho
        for dx in (-1, 0, 1):
            for dy in (0, 1, 2):
                p((ex + dx, ey + dy), EYE)
        p((ex - 1, ey), EYE_HI)
    elif kind == "happy":                        # ^
        p((ex - 1, ey + 2), EYE)
        p((ex, ey + 1), EYE)
        p((ex + 1, ey + 1), EYE)
        p((ex + 2, ey + 2), EYE)
    elif kind == "closed":                       # risquinho (‿ aqui parecia boca sorrindo)
        p((ex - 1, ey + 2), EYE)
        p((ex, ey + 2), EYE)
        p((ex + 1, ey + 2), EYE)
    elif kind == "up":
        for dx in (0, 1):
            for dy in (-1, 0, 1):
                p((ex + dx, ey + dy), EYE)
        p((ex + 1, ey - 1), EYE_HI)


def _scarf_color(light):
    """Cor do cachecol: a do status; se for amarela demais (some no corpo), escurece pra mostarda."""
    r, g, b = (int(light[i:i + 2], 16) for i in (1, 3, 5))
    R, G, B = (int(BASE[i:i + 2], 16) for i in (1, 3, 5))
    if abs(r - R) + abs(g - G) + abs(b - B) < 90:
        return shade(light, 0.78)
    return light


def _scarf(img, mask, y0, x_min, x_max, light, tails=0, knot_x=None):
    """Cachecol: faixa de 2px no pescoço, com contorno, e uma pontinha que voa quando ele anda."""
    light = _scarf_color(light)
    sh = shade(light, 0.72)
    band = [(x, y) for (x, y) in mask if y in (y0, y0 + 1) and x_min <= x <= x_max]
    for (x, y) in band:
        img[(x, y)] = light if y == y0 else sh
    xs = [x for (x, y) in band]
    if not xs:
        return
    for x in range(min(xs), max(xs) + 1):
        for y in (y0 - 1, y0 + 2):
            if (x, y) in mask:
                img[(x, y)] = OUT
    kx = knot_x if knot_x is not None else min(xs)
    # uma pontinha só, saindo da nuca: caída parada, voando pra trás quando anda
    tail = {0: [], 1: [(-1, 0), (-2, 1)], 2: [(-1, 1), (-2, 0)]}[tails]
    pts = [(kx + dx, y0 + dy) for dx, dy in tail]
    for (x, y) in pts:
        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + ddx, y + ddy)
            if q not in pts and q not in band:
                img[q] = OUT
    for q in pts:
        img[q] = sh


def _wing(img, kind, cx, cy, frame=0):
    """Asinha por cima do corpo. kind: rest, up (levantada), flap (alterna), type (pra frente)."""
    m = {}
    if kind == "rest":
        _ellipse(m, cx, cy, 3.4, 1.9, -15)
        _disc(m, cx - 3.0, cy - 1.0, 0.8)               # pontinha virada pra trás
    elif kind == "up":       # levantada, aberta em leque
        _ellipse(m, cx - 1.5, cy - 3.2, 3.6, 1.9, -58)
        _disc(m, cx + 0.5, cy - 0.5, 1.6)
    elif kind == "out":      # meio aberta, pra trás
        _ellipse(m, cx - 2.2, cy - 1.4, 4.0, 1.9, -22)
        _disc(m, cx + 0.5, cy - 0.2, 1.6)
    elif kind == "type":     # asinha esticada pra frente até o teclado, batucando
        _ellipse(m, cx, cy - (1 if frame % 2 else 0), 3.2, 1.5, -12 if frame % 2 else -4)
    _stamp(img, m, WING, WING_HI, WING_SH, out=OUT if kind == "type" else WING_OUT)


# ---------------------------------------------------------------- pose base
def _duck(p, light):
    img = {}
    dx, dy = p.get("dx", 0), p.get("dy", 0)
    bx, by, brx, bry = p.get("body", (13.0, 23.0, 7.0, 4.6))
    hx, hy = p.get("head", (19.5 + 0.5, 13.5))
    bx, by, hx, hy = bx + dx, by + dy, hx + dx, hy + dy
    hr = p.get("hr", 5.6)

    feet = p.get("feet", "stand")
    fy = 28
    if feet == "stand":
        _foot(img, 10 + dx, fy, far=True)
    elif feet.startswith("walk"):
        ph = int(feet[-1])
        s = (1, 0, -1, 0)[ph]
        _foot(img, 11 - s + dx, fy - (1 if ph == 2 else 0), far=True)

    m = {}
    _ellipse(m, bx, by, brx, bry)
    _disc(m, hx, hy, hr)
    tail = p.get("tail", 0)
    _tube(m, [(bx - brx + 2.5, by - 0.8, 1.8), (bx - brx + 0.8, by - 2.8 - tail, 1.0), (bx - brx + 0.2, by - 4.4 - tail, 0.5)])
    if p.get("tuft", True):
        tx, ty = int(hx) - 1, int(hy - hr)
        m[(tx, ty)] = "b"
        m[(tx + 1, ty - 1)] = "b"
    _stamp(img, m)

    if feet == "stand":
        _foot(img, 15 + dx, fy)
    elif feet.startswith("walk"):
        ph = int(feet[-1])
        s = (1, 0, -1, 0)[ph]
        _foot(img, 15 + s + dx, fy - (1 if ph == 0 else 0))
    elif feet == "toes":                          # sentadinho: só as pontinhas aparecem
        for x in (int(bx) + 3, int(bx) + 4, int(bx) + 5):
            img[(x, 28)] = FOOT
        img[(int(bx) + 6, 28)] = OUT

    neck = int(hy + hr) - 1 + p.get("neck_dy", 0)
    if p.get("scarf") != "off":
        _scarf(img, m, neck, int(hx - hr), int(hx + p.get("scarf_front", hr)), light, p.get("scarf", 0))

    wing = p.get("wing", "rest")
    if wing != "none":
        _wing(img, wing, bx - 0.5 + p.get("wing_dx", 0), by + 0.2 + p.get("wing_dy", 0), p.get("frame", 0))

    _beak(img, hx, hy, p.get("mouth", "closed"), p.get("beak_down", 0))
    _eye(img, hx, hy, p.get("eye", "open"), p.get("look", 0), p.get("gaze", 0))
    if p.get("blush", True):
        bxx, byy = int(hx) - 1, int(hy) + 2
        img[(bxx, byy)] = BLUSH
        img[(bxx + 1, byy)] = BLUSH
    return img


SIT = {"body": (13.5, 24.0, 7.6, 4.4), "head": (19.0, 14.6), "feet": "toes", "wing_dy": 0.3}


# ---------------------------------------------------------------- pendurado, de frente
def _dangle(frame, light):
    img = {}
    sw = (0, 0.6, 0, -0.6)[frame % 4]
    # perninhas caídas com os pezinhos pendurados
    for k, lx in enumerate((12, 17)):
        n = 2 + ((frame + k) % 2)
        x = int(lx + sw)
        for y in range(25, 25 + n):
            img[(x, y)] = FOOT
            img[(x - 1, y)] = OUT
            img[(x + 1, y)] = OUT
        fy = 25 + n
        for i, (a, b) in enumerate(((-1, 2), (-1, 2))):
            pass
        for ddx in (-1, 0, 1):
            img[(x + ddx, fy)] = FOOT
        img[(x - 2, fy)] = OUT
        img[(x + 2, fy)] = OUT
        for ddx in (-1, 0, 1):
            img[(x + ddx, fy + 1)] = OUT
        img[(x - 1, fy)] = FOOT_FAR
        img[(x + 1, fy)] = FOOT_FAR
    m = {}
    _ellipse(m, 15 + sw * 0.5, 20.0, 5.0, 5.2)
    _ellipse(m, 15 + sw * 0.5, 22.0, 5.6, 3.2)
    _disc(m, 15, 9.8, 5.6)
    _tube(m, [(15, 4.6, 0.8), (15.5, 3.4, 0.6)])
    _stamp(img, m, low=23)
    # cachecol
    _scarf_front(img, m, 15, light)
    # asinhas moles caídas dos lados
    for side in (-1, 1):
        w = {}
        cx = 15 + side * 5.4 + sw * 0.5
        _tube(w, [(cx, 17.2, 1.1), (cx + side * 0.5, 21.0, 0.8)])
        _stamp(img, w, WING, WING_HI, WING_SH)
    # rosto
    for ex in (12, 17):
        img[(ex, 8)] = EYE_HI
        img[(ex + 1, 8)] = EYE
        img[(ex, 9)] = EYE
        img[(ex + 1, 9)] = EYE
    bm = {}
    _ellipse(bm, 15.0, 12.0, 2.4, 1.2)
    for (x, y) in bm:
        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + ddx, y + ddy) not in bm:
                img[(x + ddx, y + ddy)] = OUT
    for (x, y) in bm:
        img[(x, y)] = BEAK_HI if (x, y - 1) not in bm else BEAK
    img[(10, 11)] = BLUSH
    img[(11, 11)] = BLUSH
    img[(19, 11)] = BLUSH
    img[(20, 11)] = BLUSH
    if frame % 4 in (1, 2):                      # gotinha de suor
        for (x, y, c) in ((22, 5, "#1d3a55"), (21, 6, "#1d3a55"), (22, 6, "#bfe6ff"), (23, 6, "#1d3a55"),
                          (21, 7, "#1d3a55"), (22, 7, "#7cc6f2"), (23, 7, "#1d3a55"), (22, 8, "#1d3a55")):
            img[(x, y)] = c
    return img


def _scarf_front(img, mask, cx, light):
    light = _scarf_color(light)
    sh = shade(light, 0.72)
    y0 = 15
    for (x, y) in mask:
        if y in (y0, y0 + 1):
            img[(x, y)] = light if y == y0 else sh
    xs = [x for (x, y) in mask if y == y0]
    for x in range(min(xs), max(xs) + 1):
        if (x, y0 - 1) in mask:
            img[(x, y0 - 1)] = OUT
        if (x, y0 + 2) in mask:
            img[(x, y0 + 2)] = OUT
    # nozinho e pontinha caindo do lado
    for (x, y) in ((cx + 3, y0 + 2), (cx + 3, y0 + 3), (cx + 4, y0 + 4)):
        img[(x, y)] = sh
    for (x, y) in ((cx + 2, y0 + 2), (cx + 2, y0 + 3), (cx + 3, y0 + 4), (cx + 4, y0 + 5), (cx + 5, y0 + 4),
                   (cx + 4, y0 + 2), (cx + 4, y0 + 3), (cx + 5, y0 + 3)):
        if img.get((x, y)) not in (sh, light):
            img[(x, y)] = OUT


# ---------------------------------------------------------------- poses
def _pose(anim, f, look):
    if anim == "stand":
        return {"eye": "closed" if f == 13 else "open", "tail": 0.6 if 5 <= f <= 6 else 0}
    if anim == "walk":
        return {"feet": f"walk{f}", "dy": -1 if f in (1, 3) else 0, "scarf": 1 + f % 2,
                "tail": 0.6 if f in (0, 2) else 0}
    if anim == "sit":
        return dict(SIT, eye="closed" if f == 13 else "open")
    if anim == "sleep":
        # aninhado: pãozinho redondo, cabeça recolhida em cima do peito, bico apoiado; sem cachecol
        # (a cor de "dormindo" é escura e virava um bloquinho estranho no peito)
        b = 0.5 if f >= 2 else 0.0
        return {"body": (13.0, 24.6 - b, 8.0, 4.0 + b), "head": (18.5, 19.5), "hr": 5.2, "feet": "none",
                "eye": "closed", "scarf": "off", "wing_dx": -0.5}
    if anim == "curious":
        return {"head": (20.5, 13.0), "look": -1 if look < 0 else (1 if look > 0 else 0),
                "eye": "closed" if f == 9 else "open"}
    if anim == "happy":
        return {"eye": "happy", "wing": "up" if f % 2 else "rest", "dy": -(f % 2), "tail": 0.8 * (f % 2)}
    if anim == "think":
        return dict(SIT, eye="up", gaze=0, look=0, beak_down=0)
    if anim == "think_walk":
        g = f % 4
        return {"feet": f"walk{g}", "dy": -1 if g in (1, 3) else 0, "scarf": 1 + g % 2, "eye": "up"}
    if anim == "attention":
        return {"eye": "wide", "mouth": "open" if f % 2 == 0 else "closed", "wing": "up" if f % 2 == 0 else "rest",
                "dy": -(f % 2), "feet": "stand"}
    if anim == "celebrate":
        return {"eye": "happy", "mouth": "open", "wing": "up", "dy": -2 if f else 0, "tail": 1.0,
                "feet": "walk0" if f else "stand", "scarf": 2 if f else 0}
    if anim == "waiting":
        return dict(SIT, eye="happy", tail=0.8 if f == 3 else 0)
    if anim == "work":
        return {"body": (8.2, 24.6, 6.3, 4.0), "head": (11.0, 15.6), "hr": 5.2, "feet": "none", "wing": "type",
                "wing_dx": 8.3, "wing_dy": -2.4, "frame": f, "gaze": 1, "look": 1,
                "eye": "closed" if f == 7 else "open"}
    return {}


def _thought(pen, anim, f, img, hx):
    """Balão saindo de cima da cabeça, pra trás: bolinha 1x1, 2x2 e a nuvem."""
    col = int(hx) - 4
    top = min((y for (x, y) in img if x == col), default=10)
    step = f % 4
    o, w = THOUGHT_COLORS["O"], THOUGHT_COLORS["W"]

    def bub(x, y, s):
        pen.px(x, y - 1, s, 1, o)
        pen.px(x, y + s, s, 1, o)
        pen.px(x - 1, y, 1, s, o)
        pen.px(x + s, y, 1, s, o)
        pen.px(x, y, s, s, w)

    bub(col, top - 2, 1)
    if step >= 1:
        bub(col - 3, top - 5, 2)
    cx, cy = max(0, col - 13), max(0, top - 11)
    pen.sprite(cx, cy, THOUGHT_CLOUD, THOUGHT_COLORS)
    for k in range(min(3, step + 1)):
        pen.px(cx + 3 + k * 3, cy + 3, 1, 1, THOUGHT_COLORS["d"])


_CACHE: dict = {}


def _image(anim, frame, look, light):
    key = (anim, frame, look, light)
    img = _CACHE.get(key)
    if img is None:
        if anim == "dangle":
            img = _dangle(frame, light)
        else:
            img = _duck(_pose(anim, frame, look), light)
        img = {k: v for k, v in img.items() if 0 <= k[0] < N and 0 <= k[1] < N}
        if len(_CACHE) > 600:
            _CACHE.clear()
        _CACHE[key] = img
    return img


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
    if anim == "work":
        # mesinha + computador atrás; o patinho sentado na frente, asinha no teclado
        # mesinha baixa (do tamanho de um patinho)
        _table(pen, 17, 25, 12)
        draw_computer(pen, 20, 15, light, frame, keyboard_at=(17, 22))
    img = _image(anim, frame, look, light)
    _blit(pen, img)
    if anim in ("think", "think_walk"):
        p = _pose(anim, frame, look)
        hx = p.get("head", (19.5, 12.8))[0] + p.get("dx", 0)
        _thought(pen, anim, frame if anim == "think" else frame // 2, img, hx)


WOOD_OUT = "#4a2c1d"
WOOD = "#c98f5a"
WOOD_HI = "#e0ad78"
WOOD_SH = "#a06a3d"


def _table(pen, x0, top, w):
    pen.px(x0, top - 1, w, 1, WOOD_OUT)
    pen.px(x0 - 1, top, 1, 2, WOOD_OUT)
    pen.px(x0 + w, top, 1, 2, WOOD_OUT)
    pen.px(x0, top, w, 1, WOOD_HI)
    pen.px(x0, top + 1, w, 1, WOOD_SH)
    pen.px(x0, top + 2, w, 1, WOOD_OUT)
    for lx in (x0 + 1, x0 + w - 3):
        pen.px(lx, top + 3, 3, 29 - (top + 3), WOOD_OUT)
        pen.px(lx + 1, top + 3, 1, 29 - (top + 3), WOOD)
        pen.px(lx, 29, 3, 1, WOOD_OUT)

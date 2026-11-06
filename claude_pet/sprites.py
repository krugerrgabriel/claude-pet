"""Personagem em pixel art montado por partes ("marionete").

Canvas quadrado de CANVAS x CANVAS pixels lógicos; os pés tocam a borda de baixo,
então girar o canvas 90/180/270° faz o bichinho "andar" nas paredes e no teto.
Cada pose é um dict; as animações são listas de poses.
"""
from __future__ import annotations

import colorsys

CANVAS = 30
OX, OY = 5, 7  # deslocamento do sprite (20x23) dentro do canvas — pés em y=29

STATUS_COLORS = {
    "idle": "#6fcf97",
    "thinking": "#56ccf2",
    "working": "#f2c94c",
    "attention": "#eb5757",
    "done": "#2ecc71",
    "sleep": "#466b60",
}

OUTLINE = "#1d2b3a"
SCREEN = "#0f1a24"
EYE = "#7df9ff"
LEG = "#2a3d4a"
HAND = "#d8f3ee"
LAPTOP = "#aab4be"
LAPTOP_DARK = "#3b4652"


def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def shade(h: str, factor: float) -> str:
    r, g, b = hex_rgb(h)
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(hh, max(0, min(1, ll * factor)), ss)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def mirror(rect):
    x, y, w, h = rect
    return (20 - x - w, y, w, h)


# ---------------------------------------------------------------- partes
ARMS = {
    "down": [(3, 14, 2, 4)],
    "up": [(3, 12, 2, 2), (2, 10, 2, 2)],
    "dangle": [(3, 12, 2, 2), (1, 10, 2, 2)],
    "type1": [(3, 16, 2, 3)],
    "type2": [(3, 16, 2, 2)],
}
HANDS = {
    "down": (3, 18, 2, 1),
    "up": (2, 8, 2, 2),
    "dangle": (0, 8, 2, 2),
    "type1": (4, 19, 2, 1),
    "type2": (4, 18, 2, 1),
}
LEGS = {
    "stand": ([(6, 19, 2, 3)], [(5, 22, 4, 1)]),
    "lift": ([(6, 19, 2, 2)], [(5, 21, 4, 1)]),
    "sit": ([], [(4, 21, 3, 2)]),
    "dangle": ([(7, 19, 2, 3)], [(7, 22, 2, 1)]),
}

GLYPHS = {
    "z": ["###", "..#", ".#.", "#..", "###"],
    "bang": ["##", "##", "##", "##", "..", "##"],
    "heart": [".#.#.", "#####", "#####", ".###.", "..#.."],
    "spark": [".#.", "###", ".#."],
    "check": ["....#", "...#.", "#.#..", ".#..."],
    "dot": ["##", "##"],
}


def _side_parts(arms: str, side: str):
    """Retorna (retângulos do braço, mão) de um lado; o direito é espelhado do esquerdo."""
    key = arms
    if arms in ("wave1", "wave2"):
        key = "down" if side == "L" else "up"
    if arms == "chin":
        key = "down" if side == "L" else "chin"
    if arms in ("type1", "type2") and side == "R":
        key = "type2" if arms == "type1" else "type1"  # mãos alternadas = digitando

    if key == "chin":
        rects, hand = [(15, 14, 2, 2), (14, 13, 2, 1)], (13, 12, 2, 1)
        return rects, hand
    rects, hand = list(ARMS[key]), HANDS[key]
    if arms == "wave2" and side == "R":
        rects, hand = [(3, 12, 2, 2), (1, 10, 2, 2)], (0, 8, 2, 2)
    if side == "R":
        rects = [mirror(r) for r in rects]
        hand = mirror(hand)
    return rects, hand


def _legs(legs: str, side: str):
    key = legs
    if legs == "walk1":
        key = "lift" if side == "L" else "stand"
    elif legs == "walk2":
        key = "lift" if side == "R" else "stand"
    rects, feet = LEGS[key]
    if side == "R":
        rects, feet = [mirror(r) for r in rects], [mirror(f) for f in feet]
    return rects, feet


# ---------------------------------------------------------------- desenho
def render(cr, pose: dict, scale: int, body_color: str) -> None:
    """Desenha a pose no contexto cairo, origem (0,0), tamanho CANVAS*scale."""

    def px(x, y, w, h, color, ox=OX, oy=OY):
        cr.set_source_rgb(*hex_rgb(color))
        cr.rectangle((x + ox) * scale, (y + oy) * scale, w * scale, h * scale)
        cr.fill()

    def boxed(x, y, w, h, fill, dy):
        px(x, y + dy, w, h, OUTLINE)
        px(x + 1, y + 1 + dy, w - 2, h - 2, fill)

    body = body_color
    arm_c = shade(body, 0.7)
    antenna = pose.get("antenna", STATUS_COLORS["idle"])
    legs = pose.get("legs", "stand")
    up = (2 if legs == "sit" else 0) + pose.get("bob", 0)  # parte de cima desce ao sentar

    # pernas e pés (absolutos)
    for side in "LR":
        rects, feet = _legs(legs, side)
        for r in rects:
            px(*r, LEG)
        for f in feet:
            px(*f, OUTLINE)

    # antena
    px(9, 2 + up, 2, 2, OUTLINE)
    px(8, 0 + up, 4, 2, antenna)
    px(8, 0 + up, 1, 1, shade(antenna, 1.35))

    # cabeça + tela
    boxed(4, 4, 12, 8, body, up)
    px(5, 5 + up, 10, 1, shade(body, 1.2))           # brilho
    px(6, 6 + up, 8, 5, SCREEN)
    px(3, 7 + up, 1, 2, OUTLINE)                      # parafusos
    px(16, 7 + up, 1, 2, OUTLINE)

    # olhos
    eyes = pose.get("eyes", "open")
    dx = max(-1, min(1, int(pose.get("look", 0))))
    dy = {"up": -1, "down": 1}.get(pose.get("gaze", ""), 0)
    for ex in (7, 11):
        x, y = ex + dx, 7 + dy + up
        if eyes == "closed":
            px(x, y + 1, 2, 1, EYE)
        elif eyes == "happy":
            px(x - 1, y + 1, 1, 1, EYE)
            px(x, y, 2, 1, EYE)
            px(x + 2, y + 1, 1, 1, EYE)
        elif eyes == "wide":
            px(x, 6 + up, 2, 4, EYE)
        else:
            px(x, y, 2, 2, EYE)

    # pescoço + corpo
    px(8, 12 + up, 4, 1, OUTLINE)
    boxed(5, 13, 10, 6, body, up)
    px(8, 14 + up, 4, 3, shade(body, 0.6))
    px(9, 15 + up, 2, 1, antenna)

    # notebook (na frente do corpo, atrás das mãos)
    if pose.get("prop") == "laptop":
        px(5, 15, 10, 5, LAPTOP_DARK)
        px(6, 16, 8, 3, LAPTOP)
        px(9, 17, 2, 1, antenna)
        px(3, 20, 14, 1, LAPTOP_DARK)

    # braços
    arms = pose.get("arms", "down")
    arm_up = up if arms not in ("type1", "type2") else 0
    for side in "LR":
        rects, hand = _side_parts(arms, side)
        for (x, y, w, h) in rects:
            px(x, y + arm_up, w, h, arm_c)
        hx, hy, hw, hh = hand
        px(hx, hy + arm_up, hw, hh, HAND)

    _overlay(px, pose.get("overlay"), pose.get("oframe", 0))


def _glyph(px, name, x, y, color):
    for j, row in enumerate(GLYPHS[name]):
        for i, ch in enumerate(row):
            if ch == "#":
                px(x + i, y + j, 1, 1, color, ox=0, oy=0)


def _overlay(px, overlay, f):
    if not overlay:
        return
    if overlay == "zzz":
        for k in range(3):
            step = (f + k) % 4
            if step < 3:
                _glyph(px, "z", 20 + k * 3, 6 - step * 2 - k, "#c9d6df")
    elif overlay == "dots":
        for k in range(f % 4):
            _glyph(px, "dot", 19 + k * 3, 4 - k, "#e0f7fa")
    elif overlay == "bang":
        if f % 2 == 0:
            _glyph(px, "bang", 24, 0, STATUS_COLORS["attention"])
    elif overlay == "sparkle":
        spots = [(1, 6), (26, 9), (23, 1), (4, 1), (27, 3)]
        for k, (x, y) in enumerate(spots):
            if (k + f) % 2 == 0:
                _glyph(px, "spark", x, y, "#ffe66d")
    elif overlay == "heart":
        _glyph(px, "heart", 22, 4 - (f % 4), "#ff6b9a")
    elif overlay == "check":
        if f % 3 != 2:
            _glyph(px, "check", 23, 2, STATUS_COLORS["done"])


# ---------------------------------------------------------------- animações
def _blinking(base: dict, n: int = 14) -> list[dict]:
    return [dict(base) for _ in range(n - 1)] + [dict(base, eyes="closed")]


ANIMATIONS: dict[str, tuple[float, list[dict]]] = {
    "stand": (5, _blinking({"legs": "stand", "arms": "down"})),
    "walk": (8, [{"legs": l, "arms": "down", "bob": b} for l, b in
                 (("walk1", 0), ("stand", 1), ("walk2", 0), ("stand", 1))]),
    "sit": (5, _blinking({"legs": "sit", "arms": "down"})),
    "sleep": (2, [{"legs": "sit", "arms": "down", "eyes": "closed", "overlay": "zzz", "oframe": i,
                   "bob": i % 2} for i in range(4)]),
    "think": (3, [{"legs": "stand", "arms": "chin", "gaze": "up", "look": lk, "overlay": "dots", "oframe": i}
                  for i, lk in enumerate((0, 1, 1, 0, -1, -1, 0, 0))]),
    "think_walk": (6, [{"legs": l, "arms": "chin", "gaze": "up", "overlay": "dots", "oframe": i // 2}
                       for i, l in enumerate(("walk1", "stand", "walk2", "stand") * 2)]),
    "work": (6, [{"legs": "sit", "arms": a, "gaze": "down", "prop": "laptop", "eyes": e}
                 for a, e in (("type1", "open"), ("type2", "open")) * 6 + (("type1", "closed"),)]),
    "attention": (5, [{"legs": "stand", "arms": a, "eyes": "wide", "overlay": "bang", "oframe": i}
                      for i, a in enumerate(("wave1", "wave2"))]),
    "celebrate": (6, [{"legs": l, "arms": "up", "eyes": "happy", "overlay": "sparkle", "oframe": i}
                      for i, l in enumerate(("stand", "dangle"))]),
    "waiting": (2, [{"legs": "sit", "arms": "down", "eyes": "happy", "overlay": "check", "oframe": i}
                    for i in range(3)] + [{"legs": "sit", "arms": "wave1", "eyes": "happy", "overlay": "check"}]),
    "dangle": (4, [{"legs": "dangle", "arms": "dangle", "eyes": "wide", "bob": b} for b in (0, 1)]),
    "happy": (4, [{"legs": "stand", "arms": a, "eyes": "happy", "overlay": "heart", "oframe": i}
                  for i, a in enumerate(("up", "down", "up", "down"))]),
    "curious": (5, _blinking({"legs": "stand", "arms": "down"}, 10)),
}

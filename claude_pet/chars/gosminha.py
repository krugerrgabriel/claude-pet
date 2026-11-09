"""Gosminha: gelatina lilás de frente, com um núcleo que acende na cor do status.

O corpo é gerado por função (gota/pudim parametrizada em largura e altura), então
squash & stretch saem de graça: cada quadro só diz w, h, quanto está no ar e a inclinação.
"""
from __future__ import annotations

import math

from ..pixel import shade

LABEL = "Gosminha"
SIDE_VIEW = False
PACE_THINKING = True
HIT = (5, 11, 20, 19)
PIVOT = (15, 3)

CX = 15        # centro entre os pixels 14 e 15
GROUND = 29    # última linha do canvas

LILAC = {"base": "#d2a8f2", "light": "#ecd6ff", "shadow": "#a77ed6", "line": "#5a3a86"}
BLUSH = {"base": "#ff9eb6", "light": "#ffd0dc", "shadow": "#e06d8c", "line": "#8a2d4c"}
INK = "#3b2652"
WHITE = "#ffffff"
CHEEK = "#ff86b0"
TONGUE = "#ff6f91"
LAPTOP = "#aab4be"
LAPTOP_DARK = "#3b4652"

ANIMS = {
    "stand": (4, 10),
    "walk": (9, 6),
    "sit": (3, 8),
    "sleep": (2, 4),
    "curious": (5, 10),
    "happy": (5, 4),
    "think": (3, 8),
    "think_walk": (6, 8),
    "work": (6, 8),
    "attention": (10, 4),
    "celebrate": (7, 4),
    "waiting": (3, 4),
    "dangle": (5, 4),
}

OVERLAY_AT = {"thought": (0, 4), "zzz": (0, 10), "bang": (0, 6), "heart": (1, 5), "check": (1, 6)}


# ---------------------------------------------------------------- forma
def _even(v: float) -> int:
    return max(2, 2 * round(v / 2))


def _widths(w: int, h: int, kind: str) -> list[int]:
    out = []
    for i in range(h):
        t = (i + 0.5) / h
        if kind == "hang":  # segurada pelo topo: fininha em cima, cai e arredonda embaixo
            if t < 0.72:
                frac = 0.22 + 0.78 * math.sin(t / 0.72 * math.pi / 2) ** 1.4
            else:
                u = (t - 0.72) / 0.28
                frac = math.sqrt(max(0.0, 1 - u * u)) * 0.9 + 0.1
            out.append(_even(w * frac))
            continue
        cap = 0.62 if kind == "dome" else 1.0
        if t < cap:
            u = (cap - t) / cap
            frac = math.sqrt(max(0.0, 1 - u * u))
        else:
            frac = 1.0
        out.append(_even(max(w * frac, w * 0.42)))
    if kind != "hang":
        out[-1] = max(2, out[-1] - 2)  # cantinhos de baixo arredondados
    return out


class Blob:
    """Máscara do corpo: linha y → (x0, x1) inclusivo."""

    def __init__(self, w: int, h: int, bottom: int, skew: float = 0.0, kind: str = "dome", dx: int = 0):
        self.w, self.h, self.bottom = w, h, bottom
        self.top = bottom - h + 1
        self.rows: dict[int, tuple[int, int]] = {}
        for i, width in enumerate(_widths(w, h, kind)):
            y = self.top + i
            off = round(skew * (bottom - y) / max(1, h)) + dx
            self.rows[y] = (CX - width // 2 + off, CX + width // 2 - 1 + off)
        self.skew, self.dx = skew, dx
        if kind == "dome" and h >= 12:  # pontinha de gota em cima, levemente torta
            off = round(skew) + dx
            self.rows[self.top - 1] = (CX + off, CX + 1 + off)  # biquinho torto pra direita
            self.tip = self.top - 1
        else:
            self.tip = self.top

    def inside(self, x: int, y: int) -> bool:
        r = self.rows.get(y)
        return r is not None and r[0] <= x <= r[1]

    def shift_at(self, y: int) -> int:
        """Deslocamento horizontal do corpo naquela altura (para o rosto acompanhar a inclinação)."""
        return round(self.skew * (self.bottom - y) / max(1, self.h)) + self.dx


def _draw_body(pen, b: Blob, pal: dict) -> None:
    for y, (x0, x1) in b.rows.items():
        for x in range(x0, x1 + 1):
            edge = not (b.inside(x - 1, y) and b.inside(x + 1, y) and b.inside(x, y - 1) and b.inside(x, y + 1))
            if edge:
                c = pal["line"]
            elif y >= b.bottom - 2 or (x >= x1 - 1 and y > b.top + b.h // 2):
                c = pal["shadow"]  # sombra embaixo e no lado direito
            elif not b.inside(x, y - 2):
                c = pal["light"]   # borda de luz logo abaixo do contorno de cima
            else:
                c = pal["base"]
            pen.px(x, y, 1, 1, c)


def _shine(pen, b: Blob, small: bool = False) -> None:
    """Brilho de gelatina: arco branco em cima/esquerda + pontinho."""
    y = b.top + 2
    if y not in b.rows or y + 2 not in b.rows:
        return
    x0 = b.rows[y][0]
    if small:
        pen.px(x0 + 2, y, 2, 1, WHITE)
        return
    pen.px(x0 + 2, y, 3, 1, WHITE)
    pen.px(b.rows[y + 1][0] + 1, y + 1, 1, 2, WHITE)
    if y + 4 in b.rows and b.h >= 13:
        pen.px(b.rows[y + 4][0] + 1, y + 4, 1, 1, WHITE)


def _core(pen, b: Blob, light: str, y: int | None = None, x: int | None = None) -> None:
    """Núcleo/bolhinha dentro da gelatina: a luz do status."""
    y = b.top + max(2, round(b.h * 0.2)) if y is None else y
    x = (b.rows.get(y + 2, (0, CX + 8))[1] - 6) if x is None else x
    ring = shade(light, 0.62)
    pen.px(x + 1, y, 2, 1, ring)
    pen.px(x + 1, y + 3, 2, 1, ring)
    pen.px(x, y + 1, 1, 2, ring)
    pen.px(x + 3, y + 1, 1, 2, ring)
    pen.px(x + 1, y + 1, 2, 2, light)
    pen.px(x + 1, y + 1, 1, 1, WHITE)


# ---------------------------------------------------------------- rosto
def _face(pen, b: Blob, eyes: str = "open", mouth: str = "smile", look: int = 0, gaze: int = 0,
          ey: int | None = None, glasses: str | None = None, cheeks: bool = True) -> None:
    ey = b.top + round(b.h * 0.47) if ey is None else ey
    off = b.shift_at(ey) + max(-1, min(1, look))
    lx, rx = CX - 5 + off, CX + 3 + off      # olho esquerdo ocupa lx..lx+1, direito rx..rx+1
    y = ey + gaze
    for ex in (lx, rx):
        if eyes == "open":
            pen.px(ex, y, 2, 3, INK)
            pen.px(ex, y, 1, 1, WHITE)
        elif eyes == "dot":
            pen.px(ex, y + 1, 2, 2, INK)
        elif eyes == "wide":
            pen.px(ex, y - 1, 2, 4, INK)
            pen.px(ex, y - 1, 1, 2, WHITE)
        elif eyes == "closed":
            pen.px(ex, y + 2, 2, 1, INK)
            pen.px(ex - 1 if ex == lx else ex + 2, y + 1, 1, 1, INK)
        elif eyes == "sleepy":  # fechado em "u" pra baixo, dormindo
            pen.px(ex - 1, y + 1, 1, 1, INK)
            pen.px(ex, y + 2, 2, 1, INK)
            pen.px(ex + 2, y + 1, 1, 1, INK)
        elif eyes == "happy":  # ^
            pen.px(ex - 1, y + 1, 1, 1, INK)
            pen.px(ex, y, 2, 1, INK)
            pen.px(ex + 2, y + 1, 1, 1, INK)
    if glasses:  # aro redondo fino; a lente reflete a tela (cor do status)
        for ex in (lx, rx):
            pen.px(ex, y - 1, 2, 1, INK)
            pen.px(ex, y + 4, 2, 1, INK)
            pen.px(ex - 1, y, 1, 4, INK)
            pen.px(ex + 2, y, 1, 4, INK)
            pen.px(ex, y, 1, 1, glasses)
        pen.px(lx + 3, y + 1, rx - lx - 4, 1, INK)
    if cheeks:
        cy = y + (4 if glasses else 3)
        pen.px(lx - (3 if glasses else 2), cy, 2, 1, CHEEK)
        pen.px(rx + (3 if glasses else 2), cy, 2, 1, CHEEK)
    my = y + 3
    mx = CX + off
    if mouth == "smile":
        pen.px(mx - 2, my, 1, 1, INK)
        pen.px(mx - 1, my + 1, 2, 1, INK)
        pen.px(mx + 1, my, 1, 1, INK)
    elif mouth == "grin":
        pen.px(mx - 2, my, 4, 1, INK)
        pen.px(mx - 1, my + 1, 2, 1, TONGUE)
        pen.px(mx - 2, my + 1, 1, 1, INK)
        pen.px(mx + 1, my + 1, 1, 1, INK)
        pen.px(mx - 1, my + 2, 2, 1, INK)
    elif mouth == "o":
        pen.px(mx - 1, my, 2, 2, INK)
        pen.px(mx - 1, my + 1, 2, 1, TONGUE)
    elif mouth == "flat":
        pen.px(mx - 1, my + 1, 2, 1, INK)


def _bubbles(pen, b: Blob, f: int) -> None:
    """Bolhinhas subindo por dentro (pensando)."""
    for k, (bx, period) in enumerate(((-6, 4), (-2, 3))):
        y = b.bottom - 3 - ((f + k * 2) % period) * 3
        if b.top + 3 < y < b.bottom - 1:
            x = CX + bx + b.shift_at(y)
            pen.px(x, y, 1, 1, "#f7ecff")


# ---------------------------------------------------------------- animações
def render(pen, anim: str, f: int, look: int, light: str) -> None:
    pal = LILAC
    if anim == "stand":
        breathe = (0, 0, 0, 1, 1, 1, 0, 0, 0, 0)[f]
        b = Blob(20 + breathe * 2, 15 - breathe, GROUND)
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _core(pen, b, light)
        _face(pen, b, eyes="closed" if f == 9 else "open", look=look)

    elif anim == "walk":
        w, h, lift = ((22, 12, 0), (16, 18, 0), (18, 16, 4), (18, 16, 5), (17, 17, 2), (22, 12, 0))[f]
        b = Blob(w, h, GROUND - lift)
        if lift:  # sombrinha no chão enquanto está no ar
            pen.px(CX - 4, GROUND, 8, 1, "#8f86a3")
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _core(pen, b, light)
        _face(pen, b, look=look, mouth="smile" if lift else "flat" if h < 14 else "smile")

    elif anim == "sit":
        b = Blob(24, 12, GROUND)
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _core(pen, b, light)
        _face(pen, b, eyes="closed" if f == 7 else "open", look=look)

    elif anim == "sleep":
        w, h = ((26, 10), (26, 10), (26, 9), (26, 9))[f]
        b = Blob(w, h, GROUND, kind="puddle")
        _draw_body(pen, b, pal)
        _shine(pen, b, small=True)
        _face(pen, b, eyes="sleepy", mouth="none", ey=b.top + 3)

    elif anim == "curious":
        side = look or 1
        b = Blob(20, 16, GROUND, skew=2 * side)
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _core(pen, b, light)
        _face(pen, b, eyes="closed" if f == 9 else "open", mouth="o", look=side)

    elif anim == "happy":
        skew = (-2, 0, 2, 0)[f]
        b = Blob(20, 15 + (f % 2), GROUND, skew=skew)
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _core(pen, b, light)
        _face(pen, b, eyes="happy", mouth="grin")

    elif anim == "think":
        b = Blob(20, 15 + (1 if f % 4 in (1, 2) else 0), GROUND)
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _core(pen, b, light)
        _bubbles(pen, b, f)
        _face(pen, b, gaze=-1, mouth="flat", look=(0, 1, 1, 0, -1, -1, 0, 0)[f])

    elif anim == "think_walk":
        w, h, lift = ((21, 13, 0), (18, 16, 2), (18, 16, 3), (20, 14, 0))[f % 4]
        b = Blob(w, h, GROUND - lift)
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _core(pen, b, light)
        _bubbles(pen, b, f // 2)
        _face(pen, b, gaze=-1, mouth="flat", look=look)

    elif anim == "work":
        b = Blob(20, 16 + (f % 2), GROUND)
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _face(pen, b, mouth="none", eyes="closed" if f == 7 else "open", gaze=1, ey=b.top + 3)
        _laptop(pen, light, f)

    elif anim == "attention":
        jit = (-1, 1, -1, 1)[f]
        b = Blob(18, 17, GROUND, dx=jit)
        _draw_body(pen, b, BLUSH)
        _shine(pen, b)
        _core(pen, b, light)
        _face(pen, b, eyes="wide", mouth="o")
        # gotinha de suor
        sx = b.rows[b.top + 3][1] + 1
        pen.px(sx, b.top + 3 + (f % 2), 1, 2, "#8fd3ff")

    elif anim == "celebrate":
        w, h = ((16, 19), (22, 13), (16, 19), (20, 15))[f]
        b = Blob(w, h, GROUND)
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _core(pen, b, light)
        _face(pen, b, eyes="happy", mouth="grin")

    elif anim == "waiting":
        skew = (-1, 0, 1, 0)[f]
        b = Blob(22, 13, GROUND, skew=skew)
        _draw_body(pen, b, pal)
        _shine(pen, b)
        _core(pen, b, light)
        _face(pen, b, eyes="happy", mouth="smile")

    elif anim == "dangle":
        w, h = ((16, 24), (15, 25), (16, 24), (17, 23))[f]
        b = Blob(w, h, 3 + h - 1, kind="hang")
        _draw_body(pen, b, pal)
        _shine(pen, b, small=True)
        _core(pen, b, light, y=b.top + round(h * 0.4))
        _face(pen, b, eyes="wide", mouth="o", ey=b.top + round(h * 0.55))
        # pingo caindo
        dy = (0, 1, 2, -9)[f]
        if dy >= 0:
            pen.px(CX + 2, b.bottom + 1 + dy, 1, 1, pal["shadow"])


def _laptop(pen, light: str, f: int) -> None:
    """Notebook de costas pra gente, no chão na frente da gosma; logo na cor do status."""
    # tampa 12 px: borda escura, face clara, logo 2x2 na cor do status
    pen.px(9, 22, 12, 6, LAPTOP_DARK)
    pen.px(10, 23, 10, 4, LAPTOP)
    pen.px(10, 23, 10, 1, "#c4ccd6")
    pen.px(14, 24, 2, 2, light)
    # base/teclado mais larga que a tampa
    pen.px(6, 28, 18, 2, LAPTOP_DARK)
    pen.px(7, 28, 16, 1, "#6b7682")
    # bracinhos de gosma digitando (alternados), nas laterais da tampa
    up = f % 2
    for x, dy in ((6, up), (22, 1 - up)):
        pen.px(x - 1, 25 + dy, 4, 3, LILAC["line"])
        pen.px(x, 25 + dy, 2, 2, LILAC["base"])
        pen.px(x, 25 + dy, 2, 1, LILAC["light"])

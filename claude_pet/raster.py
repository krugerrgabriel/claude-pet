"""Desenho sem cairo: os personagens só usam "cor + retângulo + preencher", então dá pra
desenhar num buffer de pixels em Python puro. É o que o Windows usa (lá não tem cairo/GTK).

    pixels = render(skin, anim, frame, look, status, scale, body_color, lean, facing, rotation)
    → lista n*n com "#rrggbb" ou None (transparente), linha por linha
"""
from __future__ import annotations

import math


class RasterCtx:
    """Imita o pedaço do contexto cairo que os desenhos usam."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.buf: list[str | None] = [None] * (w * h)
        self._color = "#000000"
        self._rect = None

    def set_source_rgb(self, r: float, g: float, b: float) -> None:
        self._color = "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))

    def rectangle(self, x: float, y: float, w: float, h: float) -> None:
        self._rect = (x, y, w, h)

    def fill(self) -> None:
        if self._rect is None:
            return
        x, y, w, h = self._rect
        self._rect = None
        x0, y0 = max(0, round(x)), max(0, round(y))
        x1, y1 = min(self.w, round(x + w)), min(self.h, round(y + h))
        if x1 <= x0:
            return
        c = self._color
        row = [c] * (x1 - x0)
        for yy in range(y0, y1):
            i = yy * self.w
            self.buf[i + x0:i + x1] = row


def _rotate(buf: list, n: int, angle: float, cx: float, cy: float) -> list:
    """Gira a imagem n x n por `angle` rad (horário, como o cairo com y pra baixo) em volta de (cx, cy),
    pegando o pixel mais próximo (pixel art continua nítido)."""
    ca, sa = math.cos(angle), math.sin(angle)
    if abs(ca) < 1e-9:
        ca = 0.0
    if abs(sa) < 1e-9:
        sa = 0.0
    out: list = [None] * (n * n)
    for y in range(n):
        dy = y + 0.5 - cy
        for x in range(n):
            dx = x + 0.5 - cx
            # inversa: ponto de origem = R(-angle) * (destino - centro) + centro
            sx = math.floor(ca * dx + sa * dy + cx)
            sy = math.floor(-sa * dx + ca * dy + cy)
            if 0 <= sx < n and 0 <= sy < n:
                out[y * n + x] = buf[sy * n + sx]
    return out


def render(skin, anim: str, frame: int, look: int, status: str, scale: int, body_color: str,
           lean: float = 0.0, facing: int = 1, rotation: int = 0) -> list:
    n = skin.canvas * scale
    ctx = RasterCtx(n, n)
    skin._render(ctx, anim, frame, look, status, scale, body_color, facing)
    buf = ctx.buf
    if abs(lean) >= 0.02:   # mesmo pêndulo do Skin.draw (cairo)
        px_ = skin.canvas - skin.pivot[0] if (skin.side_view and facing < 0) else skin.pivot[0]
        buf = _rotate(buf, n, -math.atan(lean), px_ * scale, skin.pivot[1] * scale)
    if rotation % 360:
        buf = _rotate(buf, n, math.radians(rotation % 360), n / 2, n / 2)
    return buf

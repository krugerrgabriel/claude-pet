"""O desenho do Bit (robô) na tela: animação, inclinação de pêndulo e nuvem de pensamento."""
from __future__ import annotations

import math
import time

import cairo

from . import sprites

ROBOT = "robo"

THOUGHT_CLOUD = [
    "..OOO.OOO...",
    ".OWWWOWWWOO.",
    "OWWWWWWWWWWO",
    "OWWWWWWWWWGO",
    ".OGWWWWWWGO.",
    "..OOOOOOOO..",
]
THOUGHT_COLORS = {"O": "#5d6b7e", "W": "#ffffff", "G": "#d5dce6", "d": "#5d6b7e"}


def available() -> list[str]:
    return [ROBOT]


def load(_name: str = ROBOT) -> "RobotSkin":
    return RobotSkin()


class RobotSkin:
    name = ROBOT
    pace_thinking = True
    self_hop = False

    def __init__(self):
        self.canvas = sprites.CANVAS
        self.hit = (sprites.OX, sprites.OY, 20, sprites.CANVAS - sprites.OY)

    @staticmethod
    def pixel_scale(scale: int) -> int:
        return scale

    def anim_info(self, anim: str) -> tuple[float, int]:
        fps, frames = sprites.ANIMATIONS[anim]
        return fps, len(frames)

    def _pose(self, anim: str, frame: int, look: int, status: str) -> dict:
        _fps, frames = sprites.ANIMATIONS[anim]
        pose = dict(frames[frame % len(frames)])
        pose.setdefault("look", look)
        pose["antenna"] = sprites.STATUS_COLORS.get(status, sprites.STATUS_COLORS["idle"])
        if status == "attention" and int(time.monotonic() * 4) % 2:
            pose["antenna"] = "#ffffff"
        return pose

    def draw(self, cr, anim: str, frame: int, look: int, status: str, scale: int, body_color: str,
             lean: float = 0.0) -> None:
        pose = self._pose(anim, frame, look, status)
        if abs(lean) < 0.02:
            sprites.render(cr, pose, scale, body_color)
            return
        # pêndulo: gira o robô inteiro em volta da antena (onde o mouse "segura").
        # Desenha fora da tela e gira a imagem com filtro "pixel mais próximo": nítido, sem frestas.
        n = self.canvas * scale
        off = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
        sprites.render(cairo.Context(off), pose, scale, body_color)
        angle = -math.atan(lean)  # corpo fica pra trás do movimento
        pivot_x, pivot_y = (sprites.OX + 10) * scale, sprites.OY * scale
        cr.save()
        cr.translate(pivot_x, pivot_y)
        cr.rotate(angle)
        cr.translate(-pivot_x, -pivot_y)
        cr.set_source_surface(off, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_NEAREST)
        cr.paint()
        cr.restore()

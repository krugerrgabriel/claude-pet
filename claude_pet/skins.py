"""Personagens: o Bit (robô) e os bichinhos em claude_pet/chars/.

Todo personagem usa o mesmo canvas de CANVAS x CANVAS pixels lógicos com os pés na borda
de baixo (girar o canvas = andar na parede/teto) e tem as mesmas animações (ver ANIM_NAMES).

Um módulo de personagem em chars/ define:
  LABEL         nome no menu
  SIDE_VIEW     True = desenhado de perfil olhando pra direita; espelha ao andar pra esquerda
  PACE_THINKING anda de um lado pro outro enquanto pensa
  HIT           (x, y, w, h) área clicável, em pixels lógicos
  PIVOT         (x, y) ponto por onde o mouse "segura" (pêndulo ao arrastar)
  ANIMS         {animação: (fps, nº de quadros)}
  OVERLAYS      {animação: nome do efeito}            (opcional; padrão em DEFAULT_OVERLAYS)
  OVERLAY_AT    {efeito: (dx, dy)}                    (opcional; desloca o efeito)
  render(pen, anim, frame, look, light)  desenha; `light` é a cor do status (a "luzinha")
"""
from __future__ import annotations

import importlib
import importlib.util
import math
import time

import cairo

from . import sprites
from .pixel import CANVAS, STATUS_COLORS, Pen, overlay

ROBOT = "robo"
ORDER = [ROBOT, "lagartixa", "gosminha", "capivara"]

ANIM_NAMES = ["stand", "walk", "sit", "sleep", "curious", "happy", "think", "think_walk", "work",
              "attention", "celebrate", "waiting", "dangle"]

DEFAULT_OVERLAYS = {"think": "thought", "think_walk": "thought", "sleep": "zzz", "attention": "bang",
                    "celebrate": "sparkle", "waiting": "check", "happy": "heart"}


def available() -> list[str]:
    """Personagens instalados (os de chars/ só entram se o módulo existir)."""
    return [n for n in ORDER if n == ROBOT or importlib.util.find_spec(f"{__package__}.chars.{n}") is not None]


def label(name: str) -> str:
    return "Robô" if name == ROBOT else importlib.import_module(f".chars.{name}", __package__).LABEL


def load(name: str = ROBOT) -> "Skin":
    if name == ROBOT or name not in available():
        return RobotSkin()
    return CharSkin(name)


def status_light(status: str) -> str:
    """Cor da 'luzinha' do status; pedindo atenção, pisca em branco."""
    color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
    if status == "attention" and int(time.monotonic() * 4) % 2:
        return "#ffffff"
    return color


class Skin:
    name = ""
    canvas = CANVAS
    hit = (0, 0, CANVAS, CANVAS)
    pivot = (CANVAS // 2, 0)
    pace_thinking = True
    self_hop = False
    side_view = False

    @staticmethod
    def pixel_scale(scale: int) -> int:
        return scale

    def anim_info(self, anim: str) -> tuple[float, int]:
        raise NotImplementedError

    def _render(self, cr, anim, frame, look, status, scale, body_color, facing) -> None:
        raise NotImplementedError

    def draw(self, cr, anim: str, frame: int, look: int, status: str, scale: int, body_color: str,
             lean: float = 0.0, facing: int = 1) -> None:
        if abs(lean) < 0.02:
            self._render(cr, anim, frame, look, status, scale, body_color, facing)
            return
        # pêndulo: gira o personagem inteiro em volta do ponto onde o mouse segura.
        # Desenha fora da tela e gira a imagem com filtro "pixel mais próximo": nítido, sem frestas.
        n = self.canvas * scale
        off = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
        self._render(cairo.Context(off), anim, frame, look, status, scale, body_color, facing)
        angle = -math.atan(lean)  # corpo fica pra trás do movimento
        px_ = self.canvas - self.pivot[0] if (self.side_view and facing < 0) else self.pivot[0]
        pivot_x, pivot_y = px_ * scale, self.pivot[1] * scale
        cr.save()
        cr.translate(pivot_x, pivot_y)
        cr.rotate(angle)
        cr.translate(-pivot_x, -pivot_y)
        cr.set_source_surface(off, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_NEAREST)
        cr.paint()
        cr.restore()


class RobotSkin(Skin):
    name = ROBOT
    hit = (sprites.OX, sprites.OY, 20, CANVAS - sprites.OY)
    pivot = (sprites.OX + 10, sprites.OY)

    def anim_info(self, anim: str) -> tuple[float, int]:
        fps, frames = sprites.ANIMATIONS[anim]
        return fps, len(frames)

    def _render(self, cr, anim, frame, look, status, scale, body_color, facing) -> None:
        _fps, frames = sprites.ANIMATIONS[anim]
        pose = dict(frames[frame % len(frames)])
        pose.setdefault("look", look)
        pose["antenna"] = status_light(status)
        sprites.render(cr, pose, scale, body_color)


class CharSkin(Skin):
    def __init__(self, name: str):
        self.name = name
        self.mod = importlib.import_module(f".chars.{name}", __package__)
        m = self.mod
        self.hit = m.HIT
        self.pivot = m.PIVOT
        self.pace_thinking = getattr(m, "PACE_THINKING", True)
        self.side_view = getattr(m, "SIDE_VIEW", False)
        self.overlays = {**DEFAULT_OVERLAYS, **getattr(m, "OVERLAYS", {})}
        self.overlay_at = getattr(m, "OVERLAY_AT", {})

    def anim_info(self, anim: str) -> tuple[float, int]:
        return self.mod.ANIMS[anim]

    def _render(self, cr, anim, frame, look, status, scale, body_color, facing) -> None:
        _fps, n = self.mod.ANIMS[anim]
        frame %= n
        flip = self.side_view and facing < 0
        # de perfil, "olhar" é relativo ao lado pra onde ele está virado
        rel_look = look * (-1 if flip else 1) if self.side_view else look
        self.mod.render(Pen(cr, scale, flip=flip), anim, frame, rel_look, status_light(status))
        fx = self.overlays.get(anim)
        if fx:
            dx, dy = self.overlay_at.get(fx, (0, 0))
            overlay(Pen(cr, scale), fx, frame, dx, dy, mirror=flip)

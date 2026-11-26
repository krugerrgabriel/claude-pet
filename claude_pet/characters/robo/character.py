"""Bit: o robozinho padrão, de frente, com a antena na cor do status.

O desenho mora em claude_pet/sprites.py (poses por animação); este arquivo só liga ele ao formato de
personagem. A cor do corpo vem da config (`body_color`), em `pen.body`.
"""
from __future__ import annotations

from claude_pet import sprites
from claude_pet.pixel import CANVAS

HIT = (sprites.OX, sprites.OY, 20, CANVAS - sprites.OY)
PIVOT = (sprites.OX + 10, sprites.OY)
ANIMS = {anim: (fps, len(frames)) for anim, (fps, frames) in sprites.ANIMATIONS.items()}
OVERLAYS = {anim: None for anim in ANIMS}   # os efeitos do Bit já fazem parte das poses


def render(pen, anim, frame, look, light):
    _fps, frames = sprites.ANIMATIONS[anim]
    pose = dict(frames[frame % len(frames)])
    pose.setdefault("look", look)
    pose["antenna"] = light
    sprites.render(pen.cr, pose, pen.s, pen.body)

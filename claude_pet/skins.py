"""Skins: o robô desenhado por código e os pacotes PNG (claude_pet/packs/<nome>/).

Um pacote tem frames.png (tira com 8 poses, cada uma num quadrado `canvas` x `canvas`,
pés na borda de baixo) e pack.json (índice + bbox de cada pose). Como cada pose é um
desenho só, o movimento (pulinho, estica-e-achata, espelhar) é feito aqui, por transformação.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import cairo

from . import sprites

PACKS_DIR = Path(__file__).resolve().parent / "packs"
ROBOT = "robo"


def available() -> list[str]:
    packs = sorted(p.name for p in PACKS_DIR.glob("*") if (p / "anims.json").exists())
    return packs + [ROBOT]


def load(name: str):
    if name != ROBOT and (PACKS_DIR / name / "anims.json").exists():
        return PackSkin(name)
    return RobotSkin()


class RobotSkin:
    name = ROBOT
    pace_thinking = True
    self_hop = False

    @staticmethod
    def pixel_scale(scale: int) -> int:
        return scale

    def __init__(self):
        self.canvas = sprites.CANVAS
        self.hit = (sprites.OX, sprites.OY, 20, sprites.CANVAS - sprites.OY)

    def anim_info(self, anim: str) -> tuple[float, int]:
        fps, frames = sprites.ANIMATIONS[anim]
        return fps, len(frames)

    def draw(self, cr, anim: str, frame: int, look: int, status: str, scale: int, body_color: str,
             lean: float = 0.0) -> None:
        _fps, frames = sprites.ANIMATIONS[anim]
        pose = dict(frames[frame % len(frames)])
        pose.setdefault("look", look)
        pose["antenna"] = sprites.STATUS_COLORS.get(status, sprites.STATUS_COLORS["idle"])
        if status == "attention" and int(time.monotonic() * 4) % 2:
            pose["antenna"] = "#ffffff"
        sprites.render(cr, pose, scale, body_color)


def _glyph(cr, scale, name, x, y, color):
    cr.set_source_rgb(*sprites.hex_rgb(color))
    for j, row in enumerate(sprites.GLYPHS[name]):
        for i, ch in enumerate(row):
            if ch == "#":
                cr.rectangle((x + i) * scale, (y + j) * scale, scale, scale)
    cr.fill()


def draw_overlay(cr, scale, overlay, f, bbox, canvas):
    """Efeitos colados no contorno do desenho atual (não num canto fixo)."""
    bx, by, bw, bh = bbox
    r = bx + bw  # borda direita
    clamp = lambda x, w: max(0, min(canvas - w, x))  # noqa: E731
    if overlay == "zzz":
        for k in range(3):
            step = (f + k) % 4
            if step < 3:
                _glyph(cr, scale, "z", clamp(r - 2 + k * 3, 3), max(0, by - 3 - step * 2 - k), "#c9d6df")
    elif overlay == "dots":
        for k in range(f % 4):
            _glyph(cr, scale, "dot", clamp(r - 1 + k * 3, 2), max(0, by - 1 - k), "#e0f7fa")
    elif overlay == "bang":
        if f % 2 == 0:
            _glyph(cr, scale, "bang", clamp(r, 2), max(0, by - 4), sprites.STATUS_COLORS["attention"])
    elif overlay == "heart":
        _glyph(cr, scale, "heart", clamp(r - 2, 5), max(0, by - 4 - (f % 3)), "#ff6b9a")
    elif overlay == "check":
        if f % 3 != 2:
            _glyph(cr, scale, "check", clamp(r - 1, 5), max(0, by - 4), sprites.STATUS_COLORS["done"])
    elif overlay == "sparkle":
        spots = [(bx - 4, by + bh // 3), (r + 1, by + bh // 4), (r - 4, by - 4),
                 (bx + 1, by - 3), (r + 1, by + bh // 2 + 2), (bx - 3, by + bh // 2 + 3)]
        for k, (x, y) in enumerate(spots):
            if (k + f) % 2 == 0:
                _glyph(cr, scale, "spark", clamp(x, 3), max(0, y), "#ffe66d")


class PackSkin:
    """Personagem PNG com animações já montadas por tools/rig.py (anims.png + anims.json)."""

    def __init__(self, name: str):
        self.name = name
        folder = PACKS_DIR / name
        meta = json.loads((folder / "anims.json").read_text())
        self.canvas = int(meta["canvas"])
        self.anims = meta["anims"]
        self.pace_thinking = bool(meta.get("pace_thinking", True))
        self.self_hop = bool(meta.get("self_hop", True))
        self.sheet = cairo.ImageSurface.create_from_png(str(folder / "anims.png"))
        # pack.json/frames.png = poses originais (usadas só na página de revisão)
        base = json.loads((folder / "pack.json").read_text())
        self.frames = base["frames"]
        self.base_canvas = int(base["canvas"])
        self.base_sheet = cairo.ImageSurface.create_from_png(str(folder / "frames.png"))
        boxes = [e["bbox"] for a in self.anims.values() for e in a["frames"]]
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes)
        self.hit = (x0, y0, x1 - x0, self.canvas - y0)

    @staticmethod
    def pixel_scale(scale: int) -> int:
        """Os desenhos PNG têm ~1,5x mais pixels que o robô; escala menor deixa do mesmo tamanho."""
        return max(1, round(scale * 2 / 3))

    def anim_info(self, anim: str) -> tuple[float, int]:
        a = self.anims[anim]
        return a["fps"], len(a["frames"])

    def draw(self, cr, anim: str, frame: int, look: int, status: str, scale: int, body_color: str,
             lean: float = 0.0) -> None:
        a = self.anims[anim]
        e = a["frames"][frame % len(a["frames"])]
        n = self.canvas
        bx, by, bw, bh = e["bbox"]
        src_x = -e["i"] * n

        cr.save()
        cr.scale(scale, scale)
        if look < 0:  # espelha em torno do centro do desenho
            cx = bx + bw / 2
            cr.translate(cx, 0)
            cr.scale(-1, 1)
            cr.translate(-cx, 0)
        if abs(lean) < 0.02:
            cr.rectangle(0, 0, n, n)
            cr.clip()
            cr.set_source_surface(self.sheet, src_x, 0)
            cr.get_source().set_filter(cairo.FILTER_NEAREST)
            cr.paint()
        else:
            # pêndulo: segurado pelo topo, cada linha desliza proporcional à distância do topo
            for y in range(by, by + bh):
                off = round(lean * (y - by))
                cr.save()
                cr.rectangle(off, y, n, 1)
                cr.clip()
                cr.set_source_surface(self.sheet, src_x + off, 0)
                cr.get_source().set_filter(cairo.FILTER_NEAREST)
                cr.paint()
                cr.restore()
        cr.restore()

        if e.get("o"):
            draw_overlay(cr, scale, e["o"], e.get("of", 0), e["bbox"], n)

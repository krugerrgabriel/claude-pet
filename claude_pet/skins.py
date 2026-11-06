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
    packs = sorted(p.name for p in PACKS_DIR.glob("*") if (p / "pack.json").exists())
    return packs + [ROBOT]


def load(name: str):
    if name != ROBOT and (PACKS_DIR / name / "pack.json").exists():
        return PackSkin(name)
    return RobotSkin()


class RobotSkin:
    name = ROBOT

    def __init__(self):
        self.canvas = sprites.CANVAS
        self.hit = (sprites.OX, sprites.OY, 20, sprites.CANVAS - sprites.OY)

    def anim_info(self, anim: str) -> tuple[float, int]:
        fps, frames = sprites.ANIMATIONS[anim]
        return fps, len(frames)

    def draw(self, cr, anim: str, frame: int, look: int, status: str, scale: int, body_color: str) -> None:
        _fps, frames = sprites.ANIMATIONS[anim]
        pose = dict(frames[frame % len(frames)])
        pose.setdefault("look", look)
        pose["antenna"] = sprites.STATUS_COLORS.get(status, sprites.STATUS_COLORS["idle"])
        if status == "attention" and int(time.monotonic() * 4) % 2:
            pose["antenna"] = "#ffffff"
        sprites.render(cr, pose, scale, body_color)


def _hop(pose: str, n: int, extra: dict | None = None, height: int = 2) -> list:
    """Pulinho genérico: sobe, desce e achata ao tocar o chão."""
    seq = [{"dy": 0, "sx": 1.05, "sy": 0.94}, {"dy": -1}, {"dy": -height, "sx": 0.97, "sy": 1.03}, {"dy": -1}]
    return [(pose, dict(seq[i % 4], **(extra or {}))) for i in range(n)]


PACK_ANIMS: dict[str, tuple[float, list]] = {
    "stand": (2, [("idle", {}), ("idle", {"sx": 1.02, "sy": 0.97})]),
    "curious": (2, [("idle", {}), ("idle", {"sy": 0.98})]),
    "walk": (8, _hop("idle", 4)),
    "sit": (1.5, [("sit", {}), ("sit", {"sx": 1.01, "sy": 0.98})]),
    "sleep": (2, [("sleep", {"overlay": "zzz", "oframe": i, "sy": 0.97 if i % 2 else 1.0}) for i in range(4)]),
    "think": (3, [("thinking", {"overlay": "dots", "oframe": i}) for i in range(4)]),
    "think_walk": (6, [(p, dict(t, overlay="dots", oframe=i // 2)) for i, (p, t) in enumerate(_hop("thinking", 8, height=1))]),
    "work": (6, [("working", {}), ("working", {"dy": -1})] * 3 + [("working", {"sx": 1.02, "sy": 0.98})]),
    "attention": (5, [("alert", {"overlay": "bang", "oframe": 0, "sx": 0.97, "sy": 1.04}),
                      ("alert", {"overlay": "bang", "oframe": 1})]),
    "celebrate": (6, [("done", {"overlay": "sparkle", "oframe": i, "sy": 1.03 if i else 0.97}) for i in range(2)]),
    "waiting": (2, [("done", {"overlay": "check", "oframe": i}) for i in range(3)]),
    "dangle": (4, [("grabbed", {"dx": -1}), ("grabbed", {"dx": 1})]),
    "happy": (4, [("idle", {"overlay": "heart", "oframe": i, "dy": -2 if i % 2 else 0}) for i in range(4)]),
}


class PackSkin:
    def __init__(self, name: str):
        self.name = name
        folder = PACKS_DIR / name
        meta = json.loads((folder / "pack.json").read_text())
        self.canvas = int(meta["canvas"])
        self.facing = int(meta.get("facing", 0))
        self.frames = meta["frames"]
        self.sheet = cairo.ImageSurface.create_from_png(str(folder / "frames.png"))
        boxes = [f["bbox"] for f in self.frames.values()]
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes)
        self.hit = (x0, y0, x1 - x0, self.canvas - y0)

    def anim_info(self, anim: str) -> tuple[float, int]:
        fps, frames = PACK_ANIMS[anim]
        return fps, len(frames)

    def draw(self, cr, anim: str, frame: int, look: int, status: str, scale: int, body_color: str) -> None:
        _fps, frames = PACK_ANIMS[anim]
        pose, t = frames[frame % len(frames)]
        info = self.frames.get(pose) or self.frames["idle"]
        bx, by, bw, bh = info["bbox"]
        n = self.canvas

        cr.save()
        cr.scale(scale, scale)
        cx, cy = bx + bw / 2, by + bh   # âncora: centro dos pés
        cr.translate(cx + t.get("dx", 0), cy + t.get("dy", 0))
        flip = -1 if look < 0 else 1
        cr.scale(t.get("sx", 1.0) * flip, t.get("sy", 1.0))
        cr.translate(-cx, -cy)
        cr.rectangle(0, 0, n, n)
        cr.clip()
        cr.set_source_surface(self.sheet, -info["index"] * n, 0)
        cr.get_source().set_filter(cairo.FILTER_NEAREST)
        cr.paint()
        cr.restore()

        overlay = t.get("overlay")
        if overlay:
            # os balões do robô foram desenhados em torno de (22, 4); aqui vão para o canto
            # de cima/direita do desenho atual
            dx = min(bx + bw - 21, n - 30)
            dy = max(by - 8, 0)

            def px(x, y, w, h, color, ox=0, oy=0):
                cr.set_source_rgb(*sprites.hex_rgb(color))
                cr.rectangle((x + dx) * scale, (y + dy) * scale, w * scale, h * scale)
                cr.fill()

            sprites._overlay(px, overlay, t.get("oframe", 0))

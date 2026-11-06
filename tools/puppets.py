"""Personagens desenhados pixel a pixel e montados por partes (como o robô), animados quadro a quadro.

    python3 tools/puppets.py [pato]

Gera claude_pet/packs/<nome>/anims.png + anims.json (o mesmo formato que o pet toca).
Cada parte é uma grade de letras; cada letra é uma cor da paleta do personagem.
Princípios: paleta curta com sombra puxando para o laranja (não só escurecer), contorno marrom
(não preto), luz de cima/esquerda, proporção chibi, olhos com brilho, bochechas.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rig import bbox, shear, shift, stretch_rows  # noqa: E402

PACKS = Path(__file__).resolve().parents[1] / "claude_pet" / "packs"
CLEAR = (0, 0, 0, 0)


def rgba(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def stamp(img, grid, pal, x, y, flip=False):
    w = len(grid[0])
    px = img.load()
    W, H = img.size
    for j, row in enumerate(grid):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            xx = x + (w - 1 - i if flip else i)
            yy = y + j
            if 0 <= xx < W and 0 <= yy < H:
                px[xx, yy] = pal[ch]


def mirror_x(grid):
    return [row[::-1] for row in grid]


# ====================================================================== PATO
DUCK_PAL = {k: rgba(v) for k, v in {
    "O": "#6b3e1f",   # contorno marrom
    "o": "#8a5426",   # contorno suave (dentro)
    "H": "#fffbe3",   # brilho
    "L": "#ffec7a",   # luz
    "Y": "#ffd23c",   # base
    "S": "#f6a92e",   # sombra (puxa pro laranja)
    "D": "#d9802a",   # sombra funda
    "B": "#ff9a3c",   # bico/pés
    "b": "#e0672a",   # bico/pés sombra
    "R": "#b83a3a",   # boca aberta
    "E": "#2a1a12",   # olho
    "W": "#ffffff",   # brilho do olho
    "C": "#ffab8f",   # bochecha
    "G": "#9aa6bd",   # notebook claro
    "g": "#77839b",   # notebook
    "K": "#ffe066",   # logo aceso
    "k": "#4a5263",   # base do notebook
}.items()}

DUCK_BODY = [
    "......OOOO......",
    "....OOLLLLOO....",
    "...OLLHHLLLLO...",
    "..OLHHLLLYYYYO..",
    ".OLHLLYYYYYYYYO.",
    ".OLLYYYYYYYYYYO.",
    "OLLYYYYYYYYYYYSO",
    "OLYYYYYYYYYYYYSO",
    "OYYYYYYYYYYYYYSO",
    "OYYYYYYYYYYYYSSO",
    "OYYYYYYYYYYYYSSO",
    ".OSYYYYYYYYYSSO.",
    ".OSSYYYYYYYSSDO.",
    "..ODSSSSSSSSDO..",
    "...OODDDDDDOO...",
    ".....OOOOOO.....",
]
DUCK_TUFT = [
    "..OO",
    ".OLO",
    "OLO.",
    ".O..",
]
DUCK_WINGS = {  # asa esquerda (x, y relativos ao corpo); a direita é espelhada
    "down": ([
        "..O",
        ".OY",
        "OYS",
        "OYS",
        "OSO",
        ".O.",
    ], -2, 7),
    "up": ([
        ".OO.",
        "OYYO",
        "OYSO",
        "OYSO",
        ".OSO",
        "..OO",
    ], -3, 1),
    "out": ([
        ".OO.",
        "OYYO",
        "OSSO",
        ".OO.",
    ], -4, 7),
    "type": ([
        ".OO.",
        "OYSO",
        ".OO.",
    ], 2, 10),
    "type_up": ([
        ".OO.",
        "OYSO",
        ".OO.",
    ], 2, 9),
    "chin": ([
        ".OO.",
        "OYYO",
        "OSSO",
        ".OO.",
    ], 1, 9),
}
DUCK_FOOT = ["OBBO", "ObbbO"]
EYES = {  # (grade, dx, dy) relativo à posição do olho (x, 6)
    "open": (["WE", "EE", "EE"], 0, 0),
    "up": (["WE", "EE"], 0, -1),
    "down": (["EE", "EE"], 0, 1),
    "closed": (["EE"], 0, 2),
    "happy": ([".E.", "E.E"], -0, 1),
    "wide": (["WWE", "WEE", "EEE"], 0, -1),
}
BEAKS = {
    "closed": [".BBBB.", "Obbbb O".replace(" ", "")[:6]],
    "open": [".BBBB.", ".bRRb.", "..bb.."],
}
BEAKS["closed"] = [".BBBB.", "..bb.."]


def duck_frame(pose: dict) -> Image.Image:
    """Monta um quadro do pato a partir de uma pose (dict)."""
    size = 30
    img = Image.new("RGBA", (size, size), CLEAR)
    sit = pose.get("sit", False)
    bx = 7
    by = size - len(DUCK_BODY) - (0 if sit else 2) + pose.get("dy", 0)

    # pés (atrás do corpo quando sentado: aparecem na frente, apontando pra gente)
    feet = pose.get("feet", "stand")
    if sit:
        stamp(img, ["OBBO", ".OO."], DUCK_PAL, bx + 2, by + 13)
        stamp(img, ["OBBO", ".OO."], DUCK_PAL, bx + 10, by + 13)
    elif feet != "none":
        lift_l = {"stepL": 1, "dangle": 0}.get(feet, 0)
        lift_r = {"stepR": 1}.get(feet, 0)
        fy = by + len(DUCK_BODY) - 1
        if feet == "dangle":
            stamp(img, ["OBO", "ObO", ".O."], DUCK_PAL, bx + 4, fy)
            stamp(img, ["OBO", "ObO", ".O."], DUCK_PAL, bx + 9, fy + 1)
        else:
            stamp(img, DUCK_FOOT, DUCK_PAL, bx + 3, fy - lift_l)
            stamp(img, DUCK_FOOT, DUCK_PAL, bx + 9, fy - lift_r)

    stamp(img, DUCK_TUFT, DUCK_PAL, bx + 6, by - 3)
    stamp(img, DUCK_BODY, DUCK_PAL, bx, by)

    # rosto
    look = pose.get("look", 0)
    eyes = pose.get("eyes", "open")
    grid, edx, edy = EYES[eyes]
    for ex in (4, 10):
        stamp(img, grid, DUCK_PAL, bx + ex + look + edx - (1 if eyes == "happy" else 0)
              - (0 if ex == 4 or eyes not in ("wide",) else 0), by + 6 + edy)
    if pose.get("blush", True):
        stamp(img, ["CC"], DUCK_PAL, bx + 2, by + 9)
        stamp(img, ["CC"], DUCK_PAL, bx + 12, by + 9)
    beak = BEAKS[pose.get("beak", "closed")]
    stamp(img, beak, DUCK_PAL, bx + 5 + look, by + 9)

    # notebook na frente (tampa virada pra gente), atrás das mãos
    if pose.get("laptop"):
        lap = [
            "OOOOOOOOOOOO",
            "OGGGGGGGGGGO",
            "OGggggKgggggO"[:12],
            "OGgggKKKgggO",
            "OOOOOOOOOOOO",
        ]
        stamp(img, lap, DUCK_PAL, bx + 2, by + 10)
        stamp(img, ["kkkkkkkkkkkkkk", ".OOOOOOOOOOOO."], DUCK_PAL, bx + 1, by + 15)

    # asas
    wl, wr = pose.get("wings", ("down", "down"))
    for side, kind in (("L", wl), ("R", wr)):
        grid, wx, wy = DUCK_WINGS[kind]
        w = len(grid[0])
        if side == "L":
            stamp(img, grid, DUCK_PAL, bx + wx, by + wy)
        else:
            stamp(img, mirror_x(grid), DUCK_PAL, bx + 16 - wx - w, by + wy)
    return img


def duck_anims():
    F = duck_frame
    cut = lambda img, n: stretch_rows(img, 21, n)  # noqa: E731  linha da barriga: estica sem mexer no rosto

    def blinky(pose, n=12, breath=True):
        base = F(pose)
        frames = [base] * (n - 4)
        if breath:
            frames += [cut(base, 1), cut(base, 1)]
        frames += [base, F(dict(pose, eyes="closed"))]
        return frames

    walk = lambda extra: [  # noqa: E731
        shift(shear(F(dict(extra, feet="stepL", wings=extra.get("wings", ("out", "down")))), 1 / 22), 0, -1),
        cut(F(dict(extra, feet="stand")), -1),
        shift(shear(F(dict(extra, feet="stepR", wings=extra.get("wings2", ("down", "out")))), -1 / 22), 0, -1),
        cut(F(dict(extra, feet="stand")), -1),
    ]
    think_pose = {"eyes": "up", "wings": ("down", "chin"), "look": 1}
    hop = lambda pose, alt, h: [  # noqa: E731
        cut(F(pose), -2),
        shift(cut(F(alt), 1), 0, -h // 2),
        shift(F(pose), 0, -h),
        shift(F(alt), 0, -h),
        shift(cut(F(pose), 1), 0, -h // 2),
        cut(F(alt), -2),
    ]
    alert = {"eyes": "wide", "beak": "open", "wings": ("up", "up")}
    alert2 = dict(alert, wings=("out", "out"))
    party = {"eyes": "happy", "beak": "open", "wings": ("up", "up")}
    party2 = dict(party, wings=("out", "out"))
    sit = {"sit": True}
    work = {"sit": True, "laptop": True, "eyes": "down"}
    happy = {"eyes": "happy", "wings": ("out", "down")}

    def c(frames, overlay=None, count=None):
        count = count or len(frames)
        return [(frames[i % len(frames)], overlay, i) for i in range(count)]

    return {
        "stand": (4, c(blinky({}))),
        "curious": (4, c([shear(f, 1 / 26) for f in blinky({"look": 1}, 10, False)])),
        "walk": (8, c(walk({"look": 1}))),
        "sit": (3, c(blinky(sit))),
        "sleep": (2, c([F(dict(sit, eyes="closed")), cut(F(dict(sit, eyes="closed")), 1)], "zzz", 4)),
        "think": (3, c([F(think_pose), shear(F(think_pose), 1 / 30), F(think_pose), shear(F(think_pose), -1 / 30)],
                       "thought")),
        "think_walk": (7, c(walk(dict(think_pose, wings=("down", "chin"), wings2=("down", "chin"))), "thought", 8)),
        "work": (8, c([F(dict(work, wings=("type_up", "type"))), F(dict(work, wings=("type", "type_up"))),
                       F(dict(work, wings=("type_up", "type"))), cut(F(dict(work, wings=("type", "type"))), 1)])),
        "attention": (10, c(hop(alert, alert2, 6), "bang")),
        "celebrate": (10, c(hop(party, party2, 8), "sparkle")),
        "waiting": (3, c([F(dict(sit, eyes="happy"))] * 4 + [F(dict(sit, eyes="happy", wings=("down", "up"))),
                          F(dict(sit, eyes="happy", wings=("down", "out")))] * 2 + [F(dict(sit, eyes="happy"))],
                         "check")),
        "happy": (6, c([cut(F(happy), -1), F(dict(happy, wings=("down", "out"))), cut(F(happy), 1),
                        F(dict(happy, wings=("down", "out")))], "heart")),
        "dangle": (6, c([F({"feet": "dangle", "eyes": "wide", "beak": "open", "wings": ("out", "up")}),
                         F({"feet": "dangle", "eyes": "wide", "beak": "open", "wings": ("up", "out")})])),
    }


def build(name, anims, meta):
    frames, index, out = [], {}, {}
    size = None
    for anim_name, (fps, entries) in anims.items():
        lst = []
        for img, overlay, k in entries:
            size = img.width
            key = hashlib.md5(img.tobytes()).hexdigest()
            if key not in index:
                index[key] = len(frames)
                frames.append(img)
            x0, y0, x1, y1 = bbox(img)
            e = {"i": index[key], "bbox": [x0, y0, x1 - x0, y1 - y0]}
            if overlay:
                e["o"], e["of"] = overlay, k
            lst.append(e)
        out[anim_name] = {"fps": fps, "frames": lst}
    strip = Image.new("RGBA", (size * len(frames), size), CLEAR)
    for i, f in enumerate(frames):
        strip.paste(f, (i * size, 0))
    folder = PACKS / name
    folder.mkdir(parents=True, exist_ok=True)
    strip.save(folder / "anims.png")
    (folder / "anims.json").write_text(json.dumps({"canvas": size, **meta, "anims": out}, indent=1))
    print(f"{name}: {len(frames)} quadros únicos, canvas {size}")


PUPPETS = {"pato": (duck_anims, {"pace_thinking": True, "self_hop": True, "scale_ratio": 1.0})}

if __name__ == "__main__":
    for n in sys.argv[1:] or PUPPETS:
        fn, meta = PUPPETS[n]
        build(n, fn(), meta)

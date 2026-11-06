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


# ====================================================================== PATO (perfil)
# Desenho geométrico em pixel: cada parte é uma elipse; silhueta = união → contorno automático;
# sombreamento pela posição dentro da elipse (luz de cima/esquerda).
DUCK = {k: rgba(v) for k, v in {
    "out": "#7a4318", "wing_out": "#e39a2c",
    "hi": "#fffbe0", "light": "#ffef8a", "base": "#ffd43b", "shade": "#f5a524", "deep": "#de8420",
    "bill": "#ff9b3d", "bill_hi": "#ffc07a", "bill_lo": "#e8682a", "bill_out": "#9c3f14",
    "eye": "#2a1a12", "shine": "#ffffff", "cheek": "#ff9c86", "mouth": "#c4413a",
    "lap": "#8d99b3", "lap_d": "#6a758e", "lap_hi": "#b4bfd4", "lap_logo": "#ffe066", "lap_base": "#4a5263",
    "screen": "#8ff0ff",
}.items()}
SIZE = 34


def ellipse(cx, cy, rx, ry):
    pts = set()
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0:
                pts.add((x, y))
    return pts


def tone(nx, ny, levels=("hi", "light", "base", "shade", "deep")):
    """Tom pela posição normalizada dentro da forma (-1..1). Luz de cima/esquerda."""
    l = -0.55 * nx - 0.85 * ny
    if l > 0.95:
        return levels[0]
    if l > 0.35:
        return levels[1]
    if l > -0.45:
        return levels[2]
    if l > -0.95:
        return levels[3]
    return levels[4]


def paint_shape(px, pts, cx, cy, rx, ry, levels=None):
    for (x, y) in pts:
        if 0 <= x < SIZE and 0 <= y < SIZE:
            px[x, y] = DUCK[tone((x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry, *( [levels] if levels else []))]


def outline(img, mask, color):
    px = img.load()
    for (x, y) in mask:
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in mask and 0 <= n[0] < SIZE and 0 <= n[1] < SIZE and px[n][3] == 0:
                px[n] = color


def duck_frame(pose: dict) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), CLEAR)
    px = img.load()
    sit = pose.get("sit", False)
    bob = pose.get("dy", 0)
    ground = SIZE - 1

    # ---- geometria
    body = (14.0, ground - 8.4 + (3 if sit else 0) + bob, 8.5, 5.6)
    tail = (5.6, body[1] - 4.2, 2.6, 2.2)
    hdx, hdy = pose.get("head", (0, 0))
    head = (19.5 + hdx, body[1] - 8.6 + hdy, 5.6, 5.2)

    # ---- pés (atrás do corpo): perninha + pé de pato achatado apontando pra frente
    def put(x, y, c):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            px[x, y] = DUCK[c]

    feet = pose.get("feet", "stand")
    if not sit:
        top = int(body[1] + body[3]) - 1
        spots = {"stand": [(11, 0), (16, 0)], "stepA": [(10, 0), (17, 2)], "stepB": [(12, 2), (15, 0)],
                 "dangle": [(11, 0), (16, 1)]}[feet]
        for fx, lift in spots:
            foot_y = (top + 3 + lift) if feet == "dangle" else (ground - 1 - lift)
            for y in range(top, foot_y):
                put(fx, y, "bill_lo")
            for dx in range(-1, 3):
                put(fx + dx, foot_y, "bill" if dx < 2 else "bill_lo")
                put(fx + dx, foot_y + 1, "bill_out")
            put(fx - 2, foot_y, "bill_out")
            put(fx + 3, foot_y, "bill_out")

    # ---- silhueta: rabo + corpo + cabeça
    shapes = [(tail, ellipse(*tail)), (body, ellipse(*body)), (head, ellipse(*head))]
    sil = set().union(*(pts for _, pts in shapes))
    for geo, pts in shapes:
        paint_shape(px, pts, *geo)
    outline(img, sil, DUCK["out"])

    # ---- bico (achatado, apontando pra frente)
    hx, hy = head[0], head[1]
    bx0 = int(hx + head[2]) - 1
    by0 = int(hy + 0.5)
    open_bill = pose.get("bill", "closed") == "open"
    upper = [(bx0 + i, by0) for i in range(5)] + [(bx0 + i, by0 + 1) for i in range(5)]
    lower = [(bx0 + i, by0 + 2 + (1 if open_bill else 0)) for i in range(4)]
    for (x, y) in upper:
        px[x, y] = DUCK["bill_hi"] if y == by0 and x < bx0 + 4 else DUCK["bill"]
    for (x, y) in lower:
        px[x, y] = DUCK["bill_lo"]
    if open_bill:
        for i in range(3):
            px[bx0 + i, by0 + 2] = DUCK["mouth"]
    bill_mask = set(upper) | set(lower) | ({(bx0 + i, by0 + 2) for i in range(3)} if open_bill else set())
    for (x, y) in bill_mask:
        for n in ((x + 1, y), (x, y - 1), (x, y + 1)):
            if n not in bill_mask and n not in sil and 0 <= n[0] < SIZE and px[n][3] == 0:
                px[n] = DUCK["bill_out"]
    px[bx0 + 5, by0 + 1] = DUCK["bill_out"]

    # ---- olho, bochecha
    ex, ey = int(hx + 1.5), int(hy - 2.5)
    look_up = pose.get("eyes") == "up"
    eyes = pose.get("eyes", "open")
    if eyes in ("open", "up", "down"):
        oy = -1 if look_up else (1 if eyes == "down" else 0)
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2)):
            px[ex + dx, ey + dy + oy] = DUCK["eye"]
        px[ex, ey + oy] = DUCK["shine"]
    elif eyes == "wide":
        for dx in range(3):
            for dy in range(3):
                px[ex - 1 + dx, ey - 1 + dy] = DUCK["eye"]
        px[ex - 1, ey - 1] = DUCK["shine"]
        px[ex, ey - 1] = DUCK["shine"]
        for dx in range(3):
            px[ex - 1 + dx, ey + 2] = DUCK["eye"]
    elif eyes == "closed":
        px[ex - 1, ey + 1] = DUCK["eye"]
        px[ex, ey + 2] = DUCK["eye"]
        px[ex + 1, ey + 2] = DUCK["eye"]
        px[ex + 2, ey + 1] = DUCK["eye"]
    elif eyes == "happy":
        px[ex - 1, ey + 2] = DUCK["eye"]
        px[ex, ey + 1] = DUCK["eye"]
        px[ex + 1, ey + 1] = DUCK["eye"]
        px[ex + 2, ey + 2] = DUCK["eye"]
    px[ex - 1, ey + 4] = DUCK["cheek"]
    px[ex, ey + 4] = DUCK["cheek"]
    if pose.get("blush"):
        px[ex + 1, ey + 4] = DUCK["cheek"]

    # ---- notebook na frente: base no chão + tela inclinada virada pro pato (com brilho)
    if pose.get("laptop"):
        lx = int(hx + 3)
        for x in range(lx - 3, lx + 6):
            put(x, ground - 1, "lap")
            put(x, ground - 2, "lap_hi" if x < lx + 5 else "lap")
            put(x, ground, "out")
        put(lx - 4, ground - 1, "out")
        put(lx - 4, ground - 2, "out")
        for k in range(7):  # tela: sobe inclinada pra direita
            x, y = lx + 5 + k // 3, ground - 3 - k
            put(x - 1, y, "screen")
            put(x, y, "lap_d")
            put(x + 1, y, "out")
            put(x - 2, y, "out") if k in (0, 6) else None
        put(lx + 4, ground - 3 - 7, "out")
        put(lx + 5, ground - 3 - 7, "out")

    # ---- asa (no flanco, com contorno próprio mais suave)
    wing = pose.get("wing", "fold")
    wgeo = {
        "fold": (12.5, body[1] - 0.2, 4.0, 2.5),
        "up": (11.5, body[1] - 4.5, 2.8, 4.4),
        "out": (10.0, body[1] - 1.5, 5.4, 2.4),
        "type": (19.0, body[1] - 0.5, 3.6, 2.2),
        "type_up": (19.0, body[1] - 1.5, 3.6, 2.2),
        "chin": (19.5, body[1] - 3.5, 2.6, 3.2),
    }[wing]
    wpts = ellipse(*wgeo)
    for (x, y) in wpts:
        if 0 <= x < SIZE and 0 <= y < SIZE:
            px[x, y] = DUCK[tone((x + 0.5 - wgeo[0]) / wgeo[2], (y + 0.5 - wgeo[1]) / wgeo[3],
                                 ("light", "light", "base", "shade", "deep"))]
    for (x, y) in wpts:
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in wpts and 0 <= n[0] < SIZE and 0 <= n[1] < SIZE:
                px[n] = DUCK["out"] if n not in sil else DUCK["wing_out"]
    if wing == "fold":  # penas: duas marquinhas
        px[int(wgeo[0] - 2), int(wgeo[1] + 1)] = DUCK["wing_out"]
        px[int(wgeo[0]), int(wgeo[1] + 1)] = DUCK["wing_out"]
    return img


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


def duck_anims():
    F = duck_frame
    cut = lambda img, n: stretch_rows(img, SIZE - 7, n)  # noqa: E731  barriga: estica sem mexer na cabeça

    def c(frames, overlay=None, count=None):
        count = count or len(frames)
        return [(frames[i % len(frames)], overlay, i) for i in range(count)]

    def idle(pose, n=14):
        base = F(pose)
        return [base] * (n - 5) + [F(dict(pose, head=(0, 1))), F(dict(pose, head=(0, 1))), base, base,
                                   F(dict(pose, eyes="closed"))]

    def walk(pose):
        return [
            F(dict(pose, feet="stepA", dy=-1, head=(1, -1), wing=pose.get("wing", "fold"))),
            F(dict(pose, feet="stand", dy=0, head=(0, 0))),
            F(dict(pose, feet="stepB", dy=-1, head=(1, -1), wing=pose.get("wing2", pose.get("wing", "fold")))),
            F(dict(pose, feet="stand", dy=0, head=(0, 0))),
        ]

    def hop(a, b, h):
        return [
            cut(F(dict(a, head=(0, 1))), -1),
            shift(F(dict(b, head=(0, -1))), 0, -h // 2),
            shift(F(dict(a, head=(0, -1))), 0, -h),
            shift(F(dict(b, head=(0, -1))), 0, -h),
            shift(F(dict(a, head=(0, 0))), 0, -h // 2),
            cut(F(dict(b, head=(0, 1))), -1),
        ]

    think = {"eyes": "up", "wing": "chin", "head": (0, -1)}
    sit = {"sit": True}
    work = {"sit": True, "laptop": True, "eyes": "down"}
    alert = {"eyes": "wide", "bill": "open", "wing": "up"}
    party = {"eyes": "happy", "bill": "open", "wing": "up", "blush": True}
    happy = {"eyes": "happy", "blush": True}
    return {
        "stand": (4, c(idle({}))),
        "curious": (4, c(idle({"head": (1, 0)}, 10))),
        "walk": (8, c(walk({}))),
        "sit": (3, c(idle(sit))),
        "sleep": (2, c([F(dict(sit, eyes="closed", head=(-1, 2))), F(dict(sit, eyes="closed", head=(-1, 3)))],
                       "zzz", 4)),
        "think": (3, c([F(think), F(dict(think, head=(1, -1))), F(think), F(dict(think, head=(0, 0)))], "thought")),
        "think_walk": (7, c(walk(dict(think, wing="chin", wing2="chin")), "thought", 8)),
        "work": (8, c([F(dict(work, wing="type")), F(dict(work, wing="type_up")),
                       F(dict(work, wing="type", head=(0, 1))), F(dict(work, wing="type_up"))])),
        "attention": (10, c(hop(alert, dict(alert, wing="out"), 6), "bang")),
        "celebrate": (10, c(hop(party, dict(party, wing="out"), 8), "sparkle")),
        "waiting": (3, c([F(dict(sit, eyes="happy"))] * 4 + [F(dict(sit, eyes="happy", wing="up")),
                          F(dict(sit, eyes="happy", wing="out"))] * 2, "check")),
        "happy": (6, c([F(dict(happy, head=(0, 1))), F(dict(happy, wing="out")), F(dict(happy, head=(1, 0))),
                        F(dict(happy, wing="up"))], "heart")),
        "dangle": (6, c([F({"feet": "dangle", "eyes": "wide", "bill": "open", "wing": "out"}),
                         F({"feet": "dangle", "eyes": "wide", "bill": "open", "wing": "up"})])),
    }


PUPPETS = {"pato": (duck_anims, {"pace_thinking": True, "self_hop": True, "scale_ratio": 1.0})}

if __name__ == "__main__":
    for n in sys.argv[1:] or PUPPETS:
        fn, meta = PUPPETS[n]
        build(n, fn(), meta)

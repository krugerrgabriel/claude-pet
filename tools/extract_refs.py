"""Converte uma folha de referência (8 poses em grade 4x2, estilo PROMPTS.md) num pacote de sprites.

    python3 tools/extract_refs.py art/refs/pato.png pato [--block 8] [--flip]

Gera claude_pet/packs/<nome>/frames.png (tira horizontal) + pack.json.
Passos por pose: recorta a célula → remove fundo/sombra por flood fill → (grabbed) remove a mão →
reduz para a grade de pixel real (bloco N px, voto de maioria numa paleta limitada) →
mantém só o corpo principal (tira zzz, "?", "!", brilhos, rótulo).
Só PIL, sem numpy (ferramenta de desenvolvimento; o pet em si não precisa disso).
"""
from __future__ import annotations

import argparse
import colorsys
import json
from collections import Counter, deque
from pathlib import Path

from PIL import Image, ImageDraw

POSES = ["idle", "sit", "sleep", "thinking", "working", "alert", "done", "grabbed"]
ROOT = Path(__file__).resolve().parents[1]


def background_mask(cell: Image.Image) -> Image.Image:
    """255 = fundo (cinza claro, sombra, rótulo creme) ligado à borda; 0 = personagem."""
    hsv = cell.convert("HSV")
    w, h = cell.size
    hs, ss, vs = hsv.split()
    s_px, v_px = ss.load(), vs.load()
    mask = Image.new("L", (w, h), 0)
    m = mask.load()
    for y in range(h):
        for x in range(w):
            if s_px[x, y] < 45 and v_px[x, y] > 95:
                m[x, y] = 255
    for x in range(0, w, 4):
        for y in (0, h - 1):
            if m[x, y] == 255:
                ImageDraw.floodfill(mask, (x, y), 128)
    for y in range(0, h, 4):
        for x in (0, w - 1):
            if m[x, y] == 255:
                ImageDraw.floodfill(mask, (x, y), 128)
    return mask.point(lambda v: 255 if v == 128 else 0)


def remove_skin(cell: Image.Image, bg: Image.Image) -> None:
    """Na pose 'grabbed' a mão que segura o bicho é cor de pele: marca como fundo."""
    px, b = cell.load(), bg.load()
    w, h = cell.size
    for y in range(h):
        for x in range(w):
            r, g, bl = (c / 255 for c in px[x, y])
            hh, s, v = colorsys.rgb_to_hsv(r, g, bl)
            if 0.02 < hh < 0.12 and 0.12 < s < 0.45 and v > 0.75:
                b[x, y] = 255


def downscale(cell: Image.Image, bg: Image.Image, block: int, colors: int):
    w, h = cell.size
    q = cell.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    qp, bp = q.load(), bg.load()

    def ambiguity(ox, oy):
        bad = 0
        for gy in range(oy, h - block, block):
            for gx in range(ox, w - block, block):
                n = sum(1 for y in range(gy, gy + block, 2) for x in range(gx, gx + block, 2) if bp[x, y] == 0)
                tot = ((block + 1) // 2) ** 2
                if 0.2 * tot < n < 0.8 * tot:
                    bad += 1
        return bad

    ox, oy = min(((x, y) for x in range(block) for y in range(block)), key=lambda o: ambiguity(*o))
    gw, gh = (w - ox) // block, (h - oy) // block
    grid = [[None] * gw for _ in range(gh)]
    for j in range(gh):
        for i in range(gw):
            votes = Counter()
            fg = 0
            for y in range(oy + j * block, oy + (j + 1) * block):
                for x in range(ox + i * block, ox + (i + 1) * block):
                    if bp[x, y] == 0:
                        fg += 1
                        votes[qp[x, y]] += 1
            if fg >= block * block * 0.5:
                idx = votes.most_common(1)[0][0]
                grid[j][i] = tuple(pal[idx * 3: idx * 3 + 3])
    return grid


def main_body(grid):
    """Só o maior componente conexo (o corpo; olhos e detalhes encostam nele)."""
    gh, gw = len(grid), len(grid[0])
    comp = [[-1] * gw for _ in range(gh)]
    comps = []
    for j in range(gh):
        for i in range(gw):
            if grid[j][i] is None or comp[j][i] >= 0:
                continue
            cells, dq = [], deque([(j, i)])
            comp[j][i] = len(comps)
            while dq:
                a, b = dq.popleft()
                cells.append((a, b))
                for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    na, nb = a + da, b + db
                    if 0 <= na < gh and 0 <= nb < gw and grid[na][nb] is not None and comp[na][nb] < 0:
                        comp[na][nb] = len(comps)
                        dq.append((na, nb))
            comps.append(cells)
    if not comps:
        return []
    main = max(comps, key=len)
    return [(a, b, grid[a][b]) for a, b in main]


def trim_top(grid, ratio: float = 0.3) -> None:
    """Corta linhas do topo bem mais estreitas que o corpo (sobras da mão na pose 'grabbed')."""
    widths = [sum(1 for v in row if v is not None) for row in grid]
    widest = max(widths) or 1
    for j, w in enumerate(widths):
        if w >= widest * ratio:
            break
        grid[j] = [None] * len(grid[j])


def prune_strands(grid, rounds: int = 8) -> None:
    """Apaga fios de 1 pixel (resto do contorno da mão): remove pontas repetidamente."""
    gh, gw = len(grid), len(grid[0])
    for _ in range(rounds):
        kill = []
        for j in range(gh):
            for i in range(gw):
                if grid[j][i] is None:
                    continue
                n = sum(1 for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        if 0 <= j + dj < gh and 0 <= i + di < gw and grid[j + dj][i + di] is not None)
                if n <= 1:
                    kill.append((j, i))
        if not kill:
            break
        for j, i in kill:
            grid[j][i] = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("name")
    ap.add_argument("--block", type=int, default=8)
    ap.add_argument("--colors", type=int, default=40)
    ap.add_argument("--facing", type=int, default=0, help="1 = desenho olha para a direita (vira ao andar p/ esquerda)")
    args = ap.parse_args()

    img = Image.open(args.ref).convert("RGB")
    W, H = img.size
    sprites = []
    for k, pose in enumerate(POSES):
        r, c = divmod(k, 4)
        # corta a faixa do rótulo (parte de baixo de cada linha)
        cell = img.crop((c * W // 4, r * H // 2, (c + 1) * W // 4, r * H // 2 + int(H / 2 * 0.95)))  # o rótulo vira componente separado e é descartado
        bg = background_mask(cell)
        if pose == "grabbed":
            remove_skin(cell, bg)
        grid = downscale(cell, bg, args.block, args.colors)
        if pose == "grabbed":
            prune_strands(grid)
            trim_top(grid)
        body = main_body(grid)
        ys = [p[0] for p in body]
        xs = [p[1] for p in body]
        sprites.append((pose, body, min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1))

    side = max(max(s[4] for s in sprites), max(s[5] for s in sprites))
    canvas = side + 10  # margem p/ balões (zzz, !, brilhos) e para girar nas paredes
    sheet = Image.new("RGBA", (canvas * len(sprites), canvas), (0, 0, 0, 0))
    meta = {}
    for n, (pose, body, x0, y0, bw, bh) in enumerate(sprites):
        left = n * canvas + (canvas - bw) // 2
        top = canvas - bh
        for (a, b, rgb) in body:
            sheet.putpixel((left + b - x0, top + a - y0), (*rgb, 255))
        meta[pose] = {"index": n, "bbox": [(canvas - bw) // 2, top, bw, bh]}

    out = ROOT / "claude_pet" / "packs" / args.name
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / "frames.png")
    (out / "pack.json").write_text(json.dumps(
        {"name": args.name, "canvas": canvas, "facing": args.facing, "frames": meta}, indent=1))
    print(out, f"canvas={canvas}", {p: m["bbox"][2:] for p, m in meta.items()})


if __name__ == "__main__":
    main()

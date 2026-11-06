"""Monta o personagem "pato" a partir do sprite CC0 da pale-tale (art/third_party/pale-tale-duck).

    python3 tools/import_pale_duck.py

Linhas da folha (32x32 por quadro, 10 fps): 0 parado, 1 pulo, 2 correndo de costas,
3 correndo de lado, 4 de frente. O último quadro dos GIFs é sobra (20 ms) e é descartado.
O desenho é todo do artista; aqui só entram: notebook (mesmo contorno), olho fechado
(dormir/piscar) e o encaixe de cada animação nos estados do pet.
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from puppets import build  # noqa: E402

SHEET = ROOT / "art" / "third_party" / "pale-tale-duck" / "duck-Sheet.png"
CELL, CANVAS = 32, 40
OUTLINE = (45, 21, 34, 255)
ROWS = {"idle": (0, 23), "jump": (1, 9), "back": (2, 7), "run": (3, 12), "front": (4, 10)}


def cells(sheet, row, count):
    out = []
    for c in range(count):
        tile = sheet.crop((c * CELL, row * CELL, c * CELL + CELL, row * CELL + CELL))
        canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        canvas.paste(tile, (4, CANVAS - 25))  # base dos pés (linha 24) na última linha do canvas
        out.append(canvas)
    return out


def close_eyes(img):
    """Olho = pixels de contorno cercados de corpo na metade de cima; fecha virando um risco."""
    img = img.copy()
    px = img.load()
    x0, y0, x1, y1 = img.getbbox()
    W, H = img.size
    eye = [(x, y) for y in range(y0, y0 + 9) for x in range(x0, x1)
           if px[x, y] == OUTLINE and all(0 <= x + dx < W and 0 <= y + dy < H and px[x + dx, y + dy][3]
                                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    if not eye:
        return img
    top = min(y for _, y in eye)
    for x, y in eye:
        if y == top:
            px[x, y] = px[x, y - 1]
    return img


def laptop(img):
    """Notebook aberto à frente do bico, tela virada pro pato, no mesmo contorno do sprite."""
    img = img.copy()
    K, S, s, G, g = OUTLINE, (143, 236, 255, 255), (96, 196, 230, 255), (154, 163, 181, 255), (112, 120, 140, 255)
    art = [
        "......KK",
        ".....KSK",
        "....KSsK",
        "...KSsK.",
        "..KSsK..",
        "KKKKKKKK",
        "KGGGGGgK",
        "KKKKKKKK",
    ]
    pal = {"K": K, "S": S, "s": s, "G": G, "g": g}
    for j, row in enumerate(art):
        for i, c in enumerate(row):
            if c != ".":
                img.putpixel((CANVAS - 9 + i, CANVAS - 8 + j), pal[c])
    return img


def main():
    sheet = Image.open(SHEET).convert("RGBA")
    R = {k: cells(sheet, *v) for k, v in ROWS.items()}
    idle, jump, run, front = R["idle"], R["jump"], R["run"], R["front"]

    def c(frames, overlay=None, count=None):
        count = count or len(frames)
        return [(frames[i % len(frames)], overlay, i) for i in range(count)]

    sleepy = [close_eyes(f) for f in idle]
    anims = {
        "stand": (10, c(idle)),
        "curious": (10, c(front)),
        "walk": (12, c(run)),
        "sit": (6, c(idle)),
        "sleep": (5, c(sleepy, "zzz")),
        "think": (8, c(idle, "thought")),
        "think_walk": (9, c(run, "thought")),
        "work": (10, c([laptop(f) for f in idle])),
        "attention": (12, c(jump, "bang")),
        "celebrate": (12, c(jump, "sparkle")),
        "waiting": (8, c([f if i % 12 else close_eyes(f) for i, f in enumerate(front)] + front, "check")),
        "happy": (10, c(jump, "heart")),
        "dangle": (1, c([front[0]])),
    }
    build("pato", anims, {"pace_thinking": True, "self_hop": True, "scale_ratio": 1.0})


if __name__ == "__main__":
    main()

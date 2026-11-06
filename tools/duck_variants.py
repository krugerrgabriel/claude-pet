"""Variações de design do pato (só a pose parada), para escolher a direção antes de animar."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402

import puppets as P  # noqa: E402

S = 36


def draw(spec):
    P.SIZE = S
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    px = img.load()

    def put(x, y, c):
        if 0 <= x < S and 0 <= y < S:
            px[x, y] = P.DUCK[c]

    # pés atrás
    for fx, fy in spec["feet"]:
        for dx in range(-2, 2):
            put(fx + dx, fy, "bill")
            put(fx + dx, fy + 1, "bill_out")
        put(fx - 3, fy, "bill_out")
        put(fx + 2, fy, "bill_out")
        put(fx - 2, fy - 1, "bill_lo")
        put(fx, fy - 1, "bill_lo")
    shapes = [(g, P.ellipse(*g)) for g in spec["sil"]]
    sil = set().union(*(p for _, p in shapes))
    for g, pts in shapes:
        P.paint_shape(px, pts, *g)
    P.outline(img, sil, P.DUCK["out"])
    # tufo
    for x, y in spec.get("tuft", []):
        put(x, y, "out")
    # asas
    for g in spec["wings"]:
        pts = P.ellipse(*g)
        for (x, y) in pts:
            put(x, y, P.tone((x + .5 - g[0]) / g[2], (y + .5 - g[1]) / g[3], ("light", "light", "base", "shade", "deep")))
        for (x, y) in pts:
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n not in pts:
                    put(*n, "out" if n not in sil else "wing_out")
    # bico: lábio de cima (claro) + de baixo (escuro), com contorno
    up, lo = spec["bill"]
    bp = P.ellipse(*up) | P.ellipse(*lo)
    for (x, y) in P.ellipse(*lo):
        put(x, y, "bill_lo")
    for (x, y) in P.ellipse(*up):
        put(x, y, "bill_hi" if y < up[1] - 0.3 else "bill")
    for (x, y) in bp:
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in bp:
                put(*n, "bill_out")
    # olhos
    for ex, ey, w, h in spec["eyes"]:
        for dx in range(w):
            for dy in range(h):
                put(ex + dx, ey + dy, "eye")
        put(ex, ey, "shine")
        if w >= 3:
            put(ex + 1, ey, "shine")
    for cx, cy in spec["cheeks"]:
        put(cx, cy, "cheek")
        put(cx + 1, cy, "cheek")
    return img


VARIANTS = {
    "A · 3/4 cabeção": {
        "sil": [(10, 23, 3, 2.4), (16, 26, 8, 6), (18.5, 14, 7.5, 7)],
        "feet": [(13, 33), (20, 33)],
        "wings": [(13, 26.5, 3.6, 2.8)],
        "bill": ((25.5, 16.2, 4.2, 1.9), (25, 17.8, 3.3, 1.3)),
        "eyes": [(15, 12, 2, 3), (20, 11, 2, 3)],
        "cheeks": [(14, 16), (21, 16)],
        "tuft": [(18, 6), (19, 6), (17, 5), (19, 5)],
    },
    "B · frente, bico largo": {
        "sil": [(18, 26.5, 8, 6), (18, 14.5, 7.5, 7)],
        "feet": [(14, 33), (23, 33)],
        "wings": [(10.5, 25.5, 2.4, 3.6), (25.5, 25.5, 2.4, 3.6)],
        "bill": ((18, 17.6, 4.6, 1.9), (18, 19.2, 3.4, 1.2)),
        "eyes": [(13, 12, 2, 3), (21, 12, 2, 3)],
        "cheeks": [(11, 16), (24, 16)],
        "tuft": [(18, 7), (19, 6), (17, 6), (18, 5)],
    },
    "C · 3/4 bebê gordinho": {
        "sil": [(9, 24, 3.2, 2.6), (17, 26, 8.5, 6.5), (19, 15.5, 6.8, 6.3)],
        "feet": [(14, 33), (21, 33)],
        "wings": [(14, 26.5, 4, 3)],
        "bill": ((25, 17.2, 3.6, 1.7), (24.6, 18.6, 2.8, 1.1)),
        "eyes": [(16, 13, 2, 2), (21, 12, 3, 3)],
        "cheeks": [(15, 17), (21, 17)],
        "tuft": [(19, 8), (20, 7), (18, 7)],
    },
}

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "art" / "variants"
    for name, spec in VARIANTS.items():
        img = draw(spec)
        key = name.split(" ")[0]
        img.save(out / f"pato_{key}.png")
        img.resize((S * 8, S * 8), Image.NEAREST).save(out / f"pato_{key}_8x.png")
    print(out)

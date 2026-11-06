"""Pato em pixel art de verdade: baixa resolução, contorno preto, cores chapadas (estilo das referências)."""
from PIL import Image

PAL = {
    "K": (27, 20, 32), "Y": (255, 236, 92), "y": (255, 199, 38), "o": (245, 158, 18),
    "B": (255, 128, 31), "b": (214, 78, 18), "W": (255, 255, 255), "C": (255, 150, 140),
    "R": (196, 52, 44),
}

BASE = [
    "..........KKKKK.....",
    "........KKYYYYYK....",
    ".......KYYYYYYYYK...",
    ".......KYYYYYYYYYK..",
    ".......KYYYYYWKYYK..",
    ".......KYYYYYKKYBBK.",
    ".......KYYYYYCYBBBBK",
    "..KK...KYYYYYYYbbbK.",
    ".KYYK..KyYYYYYYKKK..",
    "KYYYYKKyyYYYYYYK....",
    "KYYYYYYKKYYYYYyyK...",
    "KYYYYYYYYKKYYyyyyK..",
    ".KYYYYYYYYYKyyyyyK..",
    ".KyYYYYYYYyyyyyyoK..",
    "..KyyyyyyyyyyyooK...",
    "...KKKKKKKKKKKKK....",
    ".....KBK...KBK......",
    ".....KKKK..KKKK.....",
]


CANVAS = 28
OX, GROUND = 3, CANVAS - 1   # pato começa em x=3; pés tocam a última linha

# remendos: (x, y, linhas); "_" = mantém, "." = apaga
EYES = {
    "open": [],
    "closed": [(13, 4, ["YY"]), (13, 5, ["KK"])],
    "up": [(13, 3, ["WK"]), (13, 4, ["KK"]), (13, 5, ["YY"])],
    "down": [(13, 4, ["YY"]), (13, 5, ["WK"]), (13, 6, ["KK"])],
    "happy": [(12, 4, ["_KK_"]), (12, 5, ["K__K"]), (13, 4, ["KK"]), (13, 5, ["YY"])],
    "wide": [(12, 3, ["WWK"]), (12, 4, ["WKK"]), (12, 5, ["KKK"])],
}
BEAK = {
    "closed": [],
    "open": [(15, 5, ["BBK"]), (15, 6, ["KRRRK"]), (15, 7, ["bbbK"]), (15, 8, ["KKK_"])],
}
ERASE_STROKES = [(5, 9, ["YY"]), (7, 10, ["YY"]), (9, 11, ["YY"]), (11, 12, ["y"])]
WING = {  # asa em riscos (fechada), levantada das costas, aberta pra trás, digitando
    "fold": [],
    "up": ERASE_STROKES + [(3, 2, ["..KK", ".KYK", "KYYK", "KYYK", "KYK_", "_KK_"])],
    "out": ERASE_STROKES + [(0, 6, ["KKK__", "KYYKK", "KYYYK", "_KKK_"])],
    "type": ERASE_STROKES + [(14, 11, ["KKKK", "KYYYK", "_KKK"])],
    "type2": ERASE_STROKES + [(14, 10, ["KKKK", "KYYYK", "_KKK"])],
}
FEET = {  # (x, dy) de cada pé; dy<0 = levantado
    "stand": [(5, 0), (11, 0)],
    "stepA": [(4, -1), (12, 0)],
    "stepB": [(6, 0), (10, -1)],
    "dangle": [(6, 2), (11, 2)],
}
FOOT = ["KBK", "KKKK"]


def _patch(grid, patches):
    for x, y, rows in patches:
        for j, row in enumerate(rows):
            for i, c in enumerate(row):
                if c == "_":
                    continue
                if 0 <= y + j < len(grid) and 0 <= x + i < len(grid[0]):
                    grid[y + j][x + i] = c


def frame(pose):
    global OX
    OX = 0 if pose.get("laptop") else 3
    grid = [list(r) for r in BASE]
    grid[16] = list("." * 20)
    grid[17] = list("." * 20)
    _patch(grid, EYES[pose.get("eyes", "open")])
    _patch(grid, BEAK[pose.get("beak", "closed")])
    _patch(grid, WING[pose.get("wing", "fold")])
    body = grid[:16]
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    sit = pose.get("sit", False)
    top = GROUND - 15 - (0 if sit else 2) + pose.get("dy", 0)
    if pose.get("feet") == "dangle":
        top -= 2
    # pés (atrás do corpo)
    if not sit:
        for fx, dy in FEET[pose.get("feet", "stand")]:
            for j, row in enumerate(FOOT):  # noqa
                for i, c in enumerate(row):
                    if c != ".":
                        yy = top + 16 + j + dy - (0 if pose.get("feet") != "dangle" else 0)
                        if pose.get("feet") == "dangle":
                            yy = top + 15 + j + dy
                            img.putpixel((OX + fx + i, yy - 1), PAL["B"] + (255,)) if j == 0 else None
                        img.putpixel((OX + fx + i, yy), PAL[c] + (255,))
    for y, row in enumerate(body):
        for x, c in enumerate(row):
            if c != ".":
                img.putpixel((OX + x, top + y), PAL[c] + (255,))
    if pose.get("laptop"):
        lap = [
            "......KK",
            ".....KGK",
            "....KGgK",
            "...KGgK.",
            "..KGgK..",
            "KKKKKKKK",
            "KhhhhhhK",
            "KKKKKKKK",
        ]
        LP = {"K": (27, 20, 32), "G": (143, 240, 255), "g": (92, 104, 128), "h": (150, 160, 182)}
        for j, row in enumerate(lap):
            for i, c in enumerate(row):
                if c != ".":
                    img.putpixel((CANVAS - 8 + i, GROUND - 7 + j), LP[c] + (255,))
    return img


if __name__ == "__main__":
    import sys
    h, w = len(BASE), len(BASE[0])
    assert all(len(r) == w for r in BASE), [len(r) for r in BASE]
    img = Image.new("RGBA", (w, h))
    for y, row in enumerate(BASE):
        for x, c in enumerate(row):
            if c != ".":
                img.putpixel((x, y), PAL[c] + (255,))
    bg = Image.new("RGBA", (w + 4, h + 4), (52, 58, 70, 255)); bg.alpha_composite(img, (2, 2))
    bg.resize((bg.width * 16, bg.height * 16), Image.NEAREST).save(sys.argv[1])


def anims():
    import sys as _s
    from pathlib import Path as _P
    _s.path.insert(0, str(_P(__file__).resolve().parent))
    from rig import shift, stretch_rows

    F = frame
    belly = lambda img, n: stretch_rows(img, GROUND - 5, n)  # noqa: E731  respira pela barriga

    def c(frames, overlay=None, count=None):
        count = count or len(frames)
        return [(frames[i % len(frames)], overlay, i) for i in range(count)]

    def idle(p, n=14):
        b = F(p)
        return [b] * (n - 4) + [belly(b, 1), belly(b, 1), b, F(dict(p, eyes="closed"))]

    def walk(p, wings=("fold", "fold")):
        return [F(dict(p, feet="stepA", dy=-1, wing=wings[0])), F(dict(p, wing=wings[1])),
                F(dict(p, feet="stepB", dy=-1, wing=wings[0])), F(dict(p, wing=wings[1]))]

    def hop(a, b, h):
        return [belly(F(a), -1), shift(F(b), 0, -h // 2), shift(F(a), 0, -h), shift(F(b), 0, -h),
                shift(F(a), 0, -h // 2), belly(F(b), -1)]

    sit = {"sit": True}
    think = {"eyes": "up"}
    work = {"sit": True, "laptop": True, "eyes": "down"}
    alert = {"eyes": "wide", "beak": "open", "wing": "up"}
    party = {"eyes": "happy", "beak": "open", "wing": "up"}
    return {
        "stand": (4, c(idle({}))),
        "curious": (4, c(idle({"eyes": "wide"}, 10))),
        "walk": (8, c(walk({}))),
        "sit": (3, c(idle(sit))),
        "sleep": (2, c([F(dict(sit, eyes="closed")), belly(F(dict(sit, eyes="closed")), 1)], "zzz", 4)),
        "think": (3, c([F(think), F(think), F(dict(think, eyes="open")), F(think)], "thought")),
        "think_walk": (6, c(walk(think), "thought", 8)),
        "work": (8, c([F(dict(work, wing="type")), F(dict(work, wing="type2"))] * 3
                      + [F(dict(work, wing="type", eyes="open")), F(dict(work, wing="type2"))])),
        "attention": (10, c(hop(alert, dict(alert, wing="out"), 5), "bang")),
        "celebrate": (10, c(hop(party, dict(party, wing="out"), 7), "sparkle")),
        "waiting": (3, c([F(dict(sit, eyes="happy"))] * 4 + [F(dict(sit, eyes="happy", wing="up")),
                         F(dict(sit, eyes="happy"))] * 2, "check")),
        "happy": (6, c([F({"eyes": "happy"}), belly(F({"eyes": "happy", "wing": "out"}), -1),
                        F({"eyes": "happy", "wing": "up"}), F({"eyes": "happy"})], "heart")),
        "dangle": (6, c([F({"feet": "dangle", "eyes": "wide", "beak": "open", "wing": "up"}),
                         F({"feet": "dangle", "eyes": "wide", "beak": "open", "wing": "out"})])),
    }

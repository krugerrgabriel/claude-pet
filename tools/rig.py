"""Monta ("assa") as animações de cada personagem PNG, quadro a quadro, com operações de pixel art.

    python3 tools/rig.py [pato capivara slime]

Entrada:  claude_pet/packs/<nome>/frames.png + pack.json   (poses extraídas por extract_refs.py)
Saída:    claude_pet/packs/<nome>/anims.png  + anims.json  (o que o pet toca na tela)

Por que assim: cada pose é um desenho só. Em vez de recortar retângulos (que deixa buraco e
corta o corpo), cada quadro é gerado com operações que preservam o pixel art:
  - stretch_rows/cols: duplica/remove linhas ou colunas no meio do corpo (estica/achata sem
    deformar rosto e pés)
  - shear: desloca cada linha 1px a cada N linhas (inclinar, gingado)
  - wave: ondulação por linha (gelatina)
  - legs: acha as pernas como blocos separados na base do desenho e move só elas
  - move: move um conjunto de pixels e preenche o buraco com a cor vizinha (ex.: mão no teclado)
Cada personagem tem a sua receita em RECIPES, no fim do arquivo.
"""
from __future__ import annotations

import colorsys
import hashlib
import json
import math
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw

PACKS = Path(__file__).resolve().parents[1] / "claude_pet" / "packs"
CLEAR = (0, 0, 0, 0)


# ------------------------------------------------------------------ operações de pixel
def bbox(img):
    return img.getchannel("A").getbbox()  # (x0, y0, x1, y1), x1/y1 exclusivos


def blank(img):
    return Image.new("RGBA", img.size, CLEAR)


def shift(img, dx=0, dy=0):
    out = blank(img)
    out.paste(img, (dx, dy))
    return out


def stretch_rows(img, y, n):
    """n>0: duplica a linha y n vezes (tudo acima sobe n). n<0: remove |n| linhas acima de y."""
    if n == 0:
        return img
    W, H = img.size
    out = blank(img)
    if n > 0:
        out.paste(img.crop((0, y, W, H)), (0, y))
        out.paste(img.crop((0, 0, W, y + 1)), (0, -n))
        row = img.crop((0, y, W, y + 1))
        for k in range(1, n):
            out.paste(row, (0, y - k))
    else:
        m = -n
        out.paste(img.crop((0, y + 1, W, H)), (0, y + 1))
        out.paste(img.crop((0, 0, W, y - m + 1)), (0, m))
    return out


def stretch_cols(img, x, n):
    """Alarga (n>0) ou estreita (n<0) duplicando/removendo colunas em x, mantendo o centro."""
    if n == 0:
        return img
    W, H = img.size
    out = blank(img)
    if n > 0:
        out.paste(img.crop((0, 0, x + 1, H)), (0, 0))
        out.paste(img.crop((x, 0, W, H)), (x + n, 0))
        col = img.crop((x, 0, x + 1, H))
        for k in range(1, n):
            out.paste(col, (x + k, 0))
        return shift(out, -(n // 2), 0)
    m = -n
    out.paste(img.crop((0, 0, x, H)), (0, 0))
    out.paste(img.crop((x + m, 0, W, H)), (x, 0))
    return shift(out, m // 2, 0)


def _dark_count(img, line, horizontal=True):
    src = img.load()
    W, H = img.size
    rng = range(W) if horizontal else range(H)
    n = 0
    for i in rng:
        c = src[i, line] if horizontal else src[line, i]
        if c[3] and hsv(c)[2] < 0.3:
            n += 1
    return n


def clean_line(img, target, horizontal=True, radius=3):
    """Linha/coluna perto do alvo com menos contorno: duplicar ela não cria riscos pretos."""
    return min(range(target - radius, target + radius + 1),
               key=lambda l: (_dark_count(img, l, horizontal), abs(l - target)))


def squash(img, rows=0, cols=0, at=0.55):
    """Estica/achata pelo meio do corpo; pés continuam no chão."""
    x0, y0, x1, y1 = bbox(img)
    out = img
    if rows:
        out = stretch_rows(out, clean_line(out, y0 + int((y1 - y0) * at)), rows)
    if cols:
        out = stretch_cols(out, clean_line(out, (x0 + x1) // 2, horizontal=False, radius=max(3, (x1 - x0) // 3)), cols)
    return out


def shear(img, k, pivot="bottom"):
    """Inclina: cada linha anda round(k * distância até o pivô) pixels. k>0 = topo vai pra direita."""
    x0, y0, x1, y1 = bbox(img)
    W, H = img.size
    out = blank(img)
    for y in range(H):
        d = (y1 - 1 - y) if pivot == "bottom" else -(y - y0)
        out.paste(img.crop((0, y, W, y + 1)), (round(k * d), y))
    return out


def wave(img, amp, phase, wavelength=10.0):
    """Ondulação de gelatina: mais forte em cima, base parada."""
    x0, y0, x1, y1 = bbox(img)
    W, H = img.size
    out = blank(img)
    h = max(1, y1 - y0)
    for y in range(H):
        weight = max(0.0, min(1.0, (y1 - 1 - y) / h))
        s = round(amp * weight * math.sin(phase + y * 2 * math.pi / wavelength))
        out.paste(img.crop((0, y, W, y + 1)), (s, y))
    return out


def components(pixels):
    pixels = set(pixels)
    comps = []
    while pixels:
        start = pixels.pop()
        comp, dq = [start], deque([start])
        while dq:
            x, y = dq.popleft()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in pixels:
                    pixels.remove(n)
                    comp.append(n)
                    dq.append(n)
        comps.append(comp)
    return comps


def opaque_pixels(img, region=None):
    W, H = img.size
    x0, y0, x1, y1 = region or (0, 0, W, H)
    a = img.getchannel("A").load()
    return [(x, y) for y in range(y0, y1) for x in range(x0, x1) if a[x, y] > 0]


def legs(img, band=4, min_size=3):
    """Pernas = blocos separados na faixa de baixo do desenho, da esquerda pra direita."""
    x0, y0, x1, y1 = bbox(img)
    comps = [c for c in components(opaque_pixels(img, (x0, y1 - band, x1, y1))) if len(c) >= min_size]
    return sorted(comps, key=lambda c: min(p[0] for p in c))


def move(img, pixels, dx, dy, fill_from=None):
    """Move pixels; o buraco vira transparente ou a cor do vizinho (fill_from = deslocamento)."""
    src = img.load()
    out = img.copy()
    o = out.load()
    W, H = img.size
    moving = set(pixels)
    for x, y in pixels:
        color = CLEAR
        if fill_from:
            fx, fy = x + fill_from[0], y + fill_from[1]
            if 0 <= fx < W and 0 <= fy < H and (fx, fy) not in moving:
                color = src[fx, fy]
        o[x, y] = color
    for x, y in pixels:
        nx, ny = x + dx, y + dy
        if 0 <= nx < W and 0 <= ny < H:
            o[nx, ny] = src[x, y]
    return out


def hsv(c):
    return colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)


def pick(img, test, region=None):
    """Pixels opacos cuja cor passa no teste (h, s, v)."""
    src = img.load()
    return [(x, y) for (x, y) in opaque_pixels(img, region) if test(*hsv(src[x, y]))]


def with_outline(img, pixels):
    """Inclui o contorno escuro colado nos pixels (para mover a parte inteira, com borda)."""
    src = img.load()
    W, H = img.size
    sel = set(pixels)
    for x, y in list(pixels):
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= n[0] < W and 0 <= n[1] < H and n not in sel:
                c = src[n]
                if c[3] and hsv(c)[2] < 0.3:
                    sel.add(n)
    return list(sel)


def recolor_family(img, ref, test):
    """Troca as cores de uma família (ex.: laranja do bico) pelas da pose de referência,
    casando pela luminosidade. Deixa o bico/pés com a mesma cor em todas as poses."""
    ref_px = ref.load()
    palette = sorted({ref_px[p] for p in pick(ref, test)}, key=lambda c: hsv(c)[2])
    if not palette:
        return img
    out = img.copy()
    o = out.load()
    for p in pick(img, test):
        v = hsv(o[p])[2]
        o[p] = min(palette, key=lambda c: abs(hsv(c)[2] - v))
    return out


def laptop_prop(width=15):
    """Notebook visto de trás (tampa virada pra gente), no estilo das referências."""
    h = 10
    img = Image.new("RGBA", (width + 4, h + 1), CLEAR)
    d = ImageDraw.Draw(img)
    ink, lid, lid_hi, base = (22, 24, 30, 255), (110, 117, 134, 255), (141, 149, 168, 255), (70, 75, 88, 255)
    d.rectangle((2, 0, width + 1, h - 2), fill=ink)
    d.rectangle((3, 1, width, h - 3), fill=lid)
    d.line((3, 1, width, 1), fill=lid_hi)
    cx = (width + 4) // 2
    d.rectangle((cx - 1, 4, cx, 5), fill=(222, 226, 234, 255))
    d.rectangle((0, h - 2, width + 3, h), fill=ink)
    d.line((1, h - 1, width + 2, h - 1), fill=base)
    return img


def put_front(img, prop, x_frac=0.5):
    """Coloca um objeto na frente do personagem, apoiado no chão."""
    x0, y0, x1, y1 = bbox(img)
    out = img.copy()
    px = x0 + int((x1 - x0) * x_frac) - prop.width // 2
    out.alpha_composite(prop, (px, y1 - prop.height))
    return out


# ------------------------------------------------------------------ receitas
def breathe(img, at=0.6):
    return [img, squash(img, rows=1, at=at), squash(img, rows=1, at=at), img]


def hop(img, height=5, lean=0.0, squish=2):
    """Pulo com antecipação, esticada no ar e achatada na aterrissagem."""
    return [
        squash(img, rows=-squish, cols=squish),
        shift(shear(squash(img, rows=squish, cols=-1), lean), 0, -height // 2),
        shift(shear(squash(img, rows=1), lean), 0, -height),
        shift(shear(squash(img, rows=1), -lean), 0, -height),
        shift(shear(squash(img, rows=squish, cols=-1), -lean), 0, -height // 2),
        squash(img, rows=-squish, cols=squish),
    ]


def waddle(img, leg_band=4, lift=2, lean=1 / 22):
    """Andar de bípede: levanta um pé, inclina pro outro lado, apoia, troca."""
    ls = legs(img, leg_band)
    left, right = (ls[0], ls[-1]) if len(ls) >= 2 else ([], [])
    return [
        shift(shear(move(img, left, 0, -lift), lean), 0, -1),
        squash(img, rows=-1, cols=1),
        shift(shear(move(img, right, 0, -lift), -lean), 0, -1),
        squash(img, rows=-1, cols=1),
    ]


def trot(img, leg_band=4):
    """Andar de quadrúpede (vista de lado): pares de patas alternados + corpo sobe e desce."""
    ls = legs(img, leg_band)
    even = [p for c in ls[0::2] for p in c]
    odd = [p for c in ls[1::2] for p in c]
    return [
        shift(move(img, even, 0, -1), 0, -1),
        img,
        shift(move(img, odd, 0, -1), 0, -1),
        img,
    ]


def cycle(frames, overlay=None, count=None):
    count = count or len(frames)
    return [(frames[i % len(frames)], overlay, i) for i in range(count)]


def anim(fps, entries):
    return {"fps": fps, "entries": entries}


def is_orange(h, s, v):
    return (h < 0.105 or h > 0.97) and s > 0.45 and v > 0.25


def rig_pato(P):
    ref = P["idle"]
    P = {k: recolor_family(v, ref, is_orange) for k, v in P.items()}
    idle, think, work, alert, done = P["idle"], P["thinking"], P["working"], P["alert"], P["done"]

    # mão no teclado: amarelo que encosta no notebook (cinza) + o contorno dela
    laptop = pick(work, lambda h, s, v: s < 0.22 and 0.25 < v < 0.85)
    lx0, ly0 = min(p[0] for p in laptop), min(p[1] for p in laptop)
    lx1, ly1 = max(p[0] for p in laptop), max(p[1] for p in laptop)
    yellow = pick(work, lambda h, s, v: 0.1 < h < 0.2 and s > 0.4, (lx0, ly0 - 2, lx1 + 3, ly1 + 1))
    hand = with_outline(work, yellow)
    head_cut = ly0 - 3
    typing = [
        move(work, hand, 0, -1, fill_from=(0, 1)),
        stretch_rows(work, head_cut, 1),
        move(work, hand, 0, -1, fill_from=(0, 1)),
        work,
    ]
    return {
        "stand": anim(3, cycle(breathe(idle))),
        "curious": anim(3, cycle(breathe(shear(idle, 1 / 30)))),
        "walk": anim(8, cycle(waddle(idle))),
        "sit": anim(2.5, cycle(breathe(P["sit"]))),
        "sleep": anim(2, cycle(breathe(P["sleep"], at=0.5), "zzz")),
        "think": anim(3, cycle(breathe(think), "dots")),
        "think_walk": anim(7, cycle(waddle(think), "dots", 8)),
        "work": anim(8, cycle(typing)),
        "attention": anim(11, cycle(hop(alert, 6, 1 / 26), "bang")),
        "celebrate": anim(11, cycle(hop(done, 7, 0), "sparkle")),
        "waiting": anim(2.5, cycle(breathe(done), "check")),
        "happy": anim(7, cycle([squash(done, -1, 1), done, squash(done, 1, -1), done], "heart")),
        "dangle": anim(1, cycle([alert])),
        "_meta": {"pace_thinking": True, "self_hop": True},
    }


def rig_capivara(P):
    idle, think, alert, done = P["idle"], P["thinking"], P["alert"], P["done"]
    x0, y0, x1, y1 = bbox(think)
    grass = with_outline(think, pick(think, lambda h, s, v: 0.18 < h < 0.45 and s > 0.3))
    chew = [think, move(think, grass, 0, 1), think, move(think, grass, 0, 1)]
    chew = [c if i % 2 else squash(c, rows=1) for i, c in enumerate(chew)]

    ax0, ay0, ax1, ay1 = bbox(alert)
    head_top = ay0
    src = alert.load()
    for y in range(ay0, ay1):  # primeira linha com bastante marrom = topo da cabeça
        browns = sum(1 for x in range(ax0, ax1) if src[x, y][3] and 0.04 < hsv(src[x, y])[0] < 0.11
                     and 0.35 < hsv(src[x, y])[1] < 0.75 and 0.4 < hsv(src[x, y])[2] < 0.8)
        if browns >= 5:
            head_top = y
            break
    orange = opaque_pixels(alert, (ax0, ay0, ax1, head_top - 1))
    sway = [
        shear(move(alert, orange, 0, -1), 1 / 34),
        move(alert, orange, 0, -2),
        shear(move(alert, orange, 0, -1), -1 / 34),
        alert,
    ]

    dx0, dy0, dx1, dy1 = bbox(done)
    rim = dy0 + int((dy1 - dy0) * 0.45)
    bath = [done, stretch_rows(done, rim, 1), stretch_rows(done, rim, 2), stretch_rows(done, rim, 1)]
    return {
        "stand": anim(2.5, cycle(breathe(idle))),
        "curious": anim(2.5, cycle(breathe(idle))),
        "walk": anim(7, cycle(trot(idle))),
        "sit": anim(2, cycle(breathe(P["sit"]))),
        "sleep": anim(1.6, cycle(breathe(P["sleep"], at=0.5), "zzz")),
        "think": anim(4, cycle(chew, "dots")),
        "think_walk": anim(4, cycle(chew, "dots")),
        "work": anim(4, cycle(breathe(P["working"], at=0.5))),
        "attention": anim(5, cycle(sway, "bang")),
        "celebrate": anim(5, cycle(bath, "sparkle")),
        "waiting": anim(2, cycle(breathe(done, at=0.3), "check")),
        "happy": anim(6, cycle([squash(idle, -1, 1), idle, squash(idle, 1), idle], "heart")),
        "dangle": anim(1, cycle([P["grabbed"]])),
        "_meta": {"pace_thinking": False, "self_hop": True},
    }


def rig_slime(P):
    idle, sit, think, alert, done = P["idle"], P["sit"], P["thinking"], P["alert"], P["done"]

    LOW = 0.82  # linha de corte abaixo dos olhos/boca: o rosto nunca deforma

    def jelly(img, n=4):
        # respira como gelatina: alterna mais alto/estreito e mais baixo/largo, rosto intacto
        return [squash(img, rows=1, cols=-1, at=LOW) if i % 2 else squash(img, rows=0, cols=1, at=LOW)
                for i in range(n)]

    def slime_hop(img, height=5):
        sq = lambda r, c=0: squash(img, rows=r, cols=c, at=LOW)  # noqa: E731
        return [
            sq(-2, 3),
            shift(sq(3, -2), 0, -height // 2),
            shift(sq(2, -1), 0, -height),
            shift(sq(1), 0, -height),
            shift(sq(2, -1), 0, -height // 2),
            sq(-2, 3),
            sq(-1, 2),
            img,
        ]

    typing = put_front(idle, laptop_prop(11), 0.3)
    work = [squash(typing, rows=1, at=0.3), typing, shift(typing, 0, 0), squash(typing, rows=1, cols=1, at=0.3)]
    taffy = squash(idle, rows=7, at=LOW)
    return {
        "stand": anim(3, cycle(jelly(idle))),
        "curious": anim(3, cycle(jelly(idle))),
        "walk": anim(10, cycle(slime_hop(idle))),
        "sit": anim(2.5, cycle(jelly(sit))),
        "sleep": anim(1.6, cycle(breathe(P["sleep"], at=LOW), "zzz")),
        "think": anim(3, cycle(jelly(think), "dots")),
        "think_walk": anim(8, cycle(slime_hop(think, 3), "dots")),
        "work": anim(6, cycle(work)),
        "attention": anim(12, cycle(slime_hop(alert, 8), "bang")),
        "celebrate": anim(6, cycle([squash(done, 1, 1, LOW), done, squash(done, -1, -1, LOW), done], "sparkle")),
        "waiting": anim(2.5, cycle(breathe(done, at=LOW), "check")),
        "happy": anim(6, cycle([squash(done, 1, 1, LOW), done, squash(done, -1, -1, LOW), done], "heart")),
        "dangle": anim(1, cycle([taffy])),
        "_meta": {"pace_thinking": True, "self_hop": True},
    }


RECIPES = {"pato": rig_pato, "capivara": rig_capivara, "slime": rig_slime}


# ------------------------------------------------------------------ montagem
def load_poses(name, margin):
    folder = PACKS / name
    meta = json.loads((folder / "pack.json").read_text())
    sheet = Image.open(folder / "frames.png").convert("RGBA")
    n = meta["canvas"]
    size = n + 2 * margin
    poses = {}
    for pose, info in meta["frames"].items():
        tile = sheet.crop((info["index"] * n, 0, info["index"] * n + n, n))
        canvas = Image.new("RGBA", (size, size), CLEAR)
        canvas.paste(tile, (margin, 2 * margin))  # margem extra em cima (pulos) e nos lados
        poses[pose] = canvas
    return poses, size


def build(name):
    poses, size = load_poses(name, margin=6)
    anims = RECIPES[name](poses)
    meta = anims.pop("_meta")

    frames, index = [], {}
    out_anims = {}
    for anim_name, spec in anims.items():
        entries = []
        for img, overlay, k in spec["entries"]:
            key = hashlib.md5(img.tobytes()).hexdigest()
            if key not in index:
                index[key] = len(frames)
                frames.append(img)
            bx0, by0, bx1, by1 = bbox(img)
            e = {"i": index[key], "bbox": [bx0, by0, bx1 - bx0, by1 - by0]}
            if overlay:
                e["o"], e["of"] = overlay, k
            entries.append(e)
        out_anims[anim_name] = {"fps": spec["fps"], "frames": entries}

    strip = Image.new("RGBA", (size * len(frames), size), CLEAR)
    for i, f in enumerate(frames):
        strip.paste(f, (i * size, 0))
    folder = PACKS / name
    strip.save(folder / "anims.png")
    (folder / "anims.json").write_text(json.dumps({"canvas": size, **meta, "anims": out_anims}, indent=1))
    print(f"{name}: {len(frames)} quadros únicos, canvas {size}")


if __name__ == "__main__":
    for n in sys.argv[1:] or RECIPES:
        build(n)

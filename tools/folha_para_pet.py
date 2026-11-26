"""Converte uma folha de sprites (9 animações, uma por linha) nos quadros de um personagem do pet.

    python3 tools/folha_para_pet.py <personagem> folha.png claude_pet/characters/<personagem>/frames.bin [previa.png] [nome=tira.png ...]

As linhas da folha, nesta ordem: parado, andando, pensando, trabalhando, dormindo, feliz, comemorando,
atenção, pendurado. Cada personagem tem a sua configuração em SHEETS (grade da folha e consertos).

Para cada célula: tira o fundo (preenche a partir da borda por pixels parecidos com o fundo, ou que
mudam devagar, pra atravessar o brilho/degradê; depois some com bolsões fechados de fundo), fica com os
pedaços cujo centro cai na célula (o balão e o pulo às vezes passam da borda), alinha a linha pelo chão
(os pés na borda de baixo do quadro; o "pendurado" pela mão, em cima), reduz pra SIZE x SIZE com o mesmo
fator em tudo e reduz as cores pra uma paleta só. Pixel ou é opaco ou é transparente (o pet desenha só
retângulos de cor sólida, igual no Linux e no Windows).

Saída: zlib( cabeçalho JSON + b"\\0" + um byte por pixel de cada quadro ), 0 = transparente.
Precisa do Pillow (só pra gerar; o pet não precisa).
"""
import json
import sys
import zlib
from collections import deque

from PIL import Image

SIZE = 90                        # lado do quadro: canvas de 30 x 3 (1 pixel da imagem por pixel de tela na escala 3)
COLORS = 250                     # a paleta cabe num byte (0 = transparente)
NAMES = ["parado", "andando", "pensando", "trabalhando", "dormindo", "feliz", "comemorando", "atencao",
         "pendurado"]
HANG = 8                         # a linha do "pendurado": alinha pela mão, em cima

# Configuração de cada folha. Obrigatórios: cols (x onde começa cada coluna), rows (y das bordas das
# linhas, 10 valores) e src (lado do pedaço da folha que vira o quadro: maior = personagem menor, mas
# cabe mais coisa). O resto é opcional:
#   feet / cx / hand_top   linha do chão de cada linha, meio do personagem, alto da mão (senão: medianas)
#   fixed                  linhas que não são realinhadas (cena do notebook, mão segurando)
#   center_fixed           as linhas fixas ficam centradas no próprio conteúdo (e não no personagem)
#   bill, no_feet, feet_reach   repinta os pés com a cor `bill` (fora das linhas no_feet)
#   patch                  (linha, coluna) com defeito -> vizinho de onde copiar a parte de baixo
#   cuts                   (linha, coluna) -> y onde o de baixo encosta no de cima: corta ali
#   bg_warm                fundo quente: só tom avermelhado conta como fundo (salva roupa cinza/preta)
#   extra                  tiras de uma linha feitas depois (uma animação a mais): nome -> {cols, src};
#                          na linha de comando, `nome=tira.png`. Cada quadro fica com os pés no chão e
#                          centrado no personagem; src é na escala da tira (pra ele sair do mesmo tamanho).
SHEETS = {
    "capivara_dev": {
        "cols": [178 + 168 * k for k in range(8)],
        "rows": [0, 115, 225, 345, 460, 562, 657, 756, 862, 1024],
        "src": 150,
        "fixed": (3, 8), "center_fixed": True,
        "bg_warm": 3,
        "cuts": {(7, k): 863 for k in range(8)},     # a mão do "pendurado" encosta nos pés da "atenção"
    },
}
MARGIN = 45                      # quanto além da célula procurar pedaços dela (balão, pulo)


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def bg_like(c, ref, warm=None):
    """Parecido com o fundo. `warm`: o fundo é quente (vermelho passa o azul em pelo menos `warm`); cinza
    neutro ou azulado (camiseta preta, por exemplo) nunca é fundo."""
    return dist(c, ref) < 38 and max(c) - min(c) < 60 and (warm is None or c[0] - c[2] >= warm)


def _flood(w, h, start, ok):
    """Componente conectado (vizinhança de 4) a partir de `start`, andando enquanto ok(x, y)."""
    comp, q = [start], deque([start])
    seen = {start}
    while q:
        x, y = q.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= n[0] < w and 0 <= n[1] < h and n not in seen and ok(*n):
                seen.add(n)
                comp.append(n)
                q.append(n)
    return comp


def cutout(im, box, warm=None):
    """Recorte RGBA da caixa, sem o fundo. Devolve (imagem, componentes 8-conectados do que sobrou)."""
    cell = im.crop(box)
    w, h = cell.size
    p = cell.load()
    border = [p[x, 0] for x in range(w)] + [p[x, h - 1] for x in range(w)] + \
             [p[0, y] for y in range(h)] + [p[w - 1, y] for y in range(h)]
    ref = tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))
    bg = [[False] * w for _ in range(h)]
    q = deque((x, y) for x in range(w) for y in (0, h - 1))
    q.extend((x, y) for y in range(h) for x in (0, w - 1))
    for (x, y) in q:
        bg[y][x] = True
    while q:
        x, y = q.popleft()
        c = p[x, y]
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny][nx]:
                n = p[nx, ny]
                if bg_like(n, ref, warm) or (dist(n, c) < 9 and dist(n, ref) < 90 and min(n) > 35
                                             and (warm is None or n[0] - n[2] >= warm)):
                    bg[ny][nx] = True
                    q.append((nx, ny))
    seen = set()                                    # bolsões fechados de fundo (vão da cadeira etc.)
    for y in range(h):
        for x in range(w):
            if bg[y][x] or (x, y) in seen or not bg_like(p[x, y], ref, warm):
                continue
            comp = _flood(w, h, (x, y), lambda a, b: not bg[b][a] and bg_like(p[a, b], ref, warm))
            seen.update(comp)
            if len(comp) >= 10:
                for (a, b) in comp:
                    bg[b][a] = True
    out = Image.new("RGBA", (w, h))
    o = out.load()
    for y in range(h):
        for x in range(w):
            o[x, y] = (0, 0, 0, 0) if bg[y][x] else p[x, y] + (255,)
    comps, done = [], set()
    for y in range(h):
        for x in range(w):
            if bg[y][x] or (x, y) in done:
                continue
            comp, qq = [(x, y)], deque([(x, y)])
            done.add((x, y))
            while qq:
                cx, cy = qq.popleft()
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        n = (cx + dx, cy + dy)
                        if 0 <= n[0] < w and 0 <= n[1] < h and not bg[n[1]][n[0]] and n not in done:
                            done.add(n)
                            comp.append(n)
                            qq.append(n)
            comps.append(comp)
    return out, comps


def _light(p):
    """Pixel claro e quente (corpo amarelo, pé, bico): não é contorno, nem fundo, nem cachecol."""
    def ok(x, y):
        r, g, b, a = p[x, y]
        return a > 0 and r > 120 and r >= g >= b and r + g + b > 180
    return ok


def _feet(layer, bottom, x0, x1, reach):
    """Manchas claras pequenas, fechadas pelo contorno, a até `reach` px acima do chão: os pés."""
    p = layer.load()
    w, h = layer.size
    light = _light(p)
    seen, feet = set(), []
    for y in range(max(0, bottom - reach), min(h, bottom + 1)):
        for x in range(max(0, x0), min(w, x1)):
            if (x, y) in seen or not light(x, y):
                continue
            comp = _flood(w, h, (x, y), light)
            seen.update(comp)
            if min(q[1] for q in comp) >= bottom - reach and 20 <= len(comp) <= 300:
                feet.append(comp)
    return feet


def feet_like(layer, bottom, x0, x1, reach, color):
    """Repinta os pés com `color` (manchas claras e pequenas encostadas no chão do personagem).
    Mantém luz e sombra (cada pixel guarda o quanto era mais claro/escuro)."""
    p = layer.load()
    for comp in _feet(layer, bottom, x0, x1, reach):
        tones = sorted(sum(p[q][:3]) for q in comp)
        ref = tones[len(tones) * 3 // 4]                                      # tom base do pé
        for q in comp:
            t = sum(p[q][:3]) / ref
            p[q] = tuple(min(255, round(c * t)) for c in color) + (255,)


def to_canvas(layer, x0, y0, src):
    """Pega o quadrado src x src com canto em (x0, y0) (coordenadas da camada; pode sair dela) e reduz
    pra SIZE x SIZE. Alfa vira 0 ou 255."""
    pad = Image.new("RGBA", (layer.width + 2 * src, layer.height + 2 * src))
    pad.paste(layer, (src, src))
    sq = pad.crop((x0 + src, y0 + src, x0 + 2 * src, y0 + 2 * src))
    small = sq.convert("RGBa").resize((SIZE, SIZE), Image.LANCZOS).convert("RGBA")
    px = small.load()
    for y in range(SIZE):
        for x in range(SIZE):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 255) if a >= 128 else (0, 0, 0, 0)
    return small


def _median(values):
    v = sorted(values)
    return v[len(v) // 2]


def frames(im, cfg):
    """Cada célula, com o que é dela; depois alinha o personagem de todos os quadros no mesmo x (a folha
    às vezes o empurra pro lado) e traz pra dentro do quadro os efeitos soltos que ficariam pra fora."""
    W, H = im.size
    cols, rows, src = cfg["cols"], cfg["rows"], cfg["src"]
    cuts, fixed = cfg.get("cuts", {}), cfg.get("fixed", ())
    cells = {}
    for r in range(len(NAMES)):
        for k in range(len(cols)):
            x0, x1 = cols[k], (cols[k + 1] if k + 1 < len(cols) else W)
            y0, y1 = rows[r], rows[r + 1]
            bx0, by0, bx1, by1 = max(0, x0 - MARGIN), max(0, y0 - MARGIN), min(W, x1 + MARGIN), min(H, y1 + MARGIN)
            img, comps = cutout(im, (bx0, by0, bx1, by1), cfg.get("bg_warm"))
            lo = cuts.get((r - 1, k), -1) - by0          # cortes com a célula de cima / de baixo
            hi = cuts.get((r, k), H + 1) - by0
            mine = []
            for c in comps:
                ys = [y for _, y in c]
                if not x0 <= bx0 + sum(x for x, _ in c) / len(c) < x1:      # é da coluna do lado
                    continue
                if min(ys) < lo <= max(ys) or min(ys) < hi <= max(ys):     # atravessa o corte: só a parte daqui
                    mine.append([q for q in c if lo <= q[1] < hi])
                elif y0 <= by0 + sum(ys) / len(c) < y1:
                    mine.append(c)
            mine = [c for c in mine if c]
            main = max(mine, key=len)
            ox, oy = x0 - bx0, y0 - by0
            cells[(r, k)] = (img, mine, main, ox, oy, sum(x for x, _ in main) / len(main) - ox)
    for (r, k), donor in cfg.get("patch", {}).items():   # pé a mais: copia o pedaço de baixo do vizinho
        img, mine, main, ox, oy, cx = cells[(r, k)]
        ground = max(y for _, y in main)
        raised = min(_feet(img, ground, 0, img.width, cfg.get("feet_reach", {}).get(r, 18)),
                     key=lambda c: max(y for _, y in c))
        xs, ys = [x for x, _ in raised], [y for _, y in raised]
        box = (min(xs) - 14, min(ys) - 4, max(xs) + 5, ground + 3)     # o pé levantado e o pé de baixo dele
        img.paste(cells[donor][0].crop(box), box[:2])
        main.extend((x, y) for x in range(box[0], box[2]) for y in range(box[1], box[3]))

    def row_cells(r):
        return [cells[(r, k)] for k in range(len(cols))]

    # medidas que a configuração não deu: medianas dos quadros (dentro da célula)
    feet = cfg.get("feet") or [None if r == HANG else _median(max(y for _, y in c[2]) - c[4] for c in row_cells(r))
                               for r in range(len(NAMES))]
    hand_top = cfg.get("hand_top")
    if hand_top is None:
        hand_top = _median(min(y for comp in c[1] for _, y in comp) - c[4] for c in row_cells(HANG))
    ref = _median(v[-1] for (r, k), v in cells.items() if r not in fixed)   # x do personagem
    cx = cfg.get("cx", round(ref))
    row_x = {}                                       # linhas fixas centradas no próprio conteúdo
    if cfg.get("center_fixed"):
        for r in fixed:
            row_x[r] = round(_median((min(x for x, _ in c[2]) + max(x for x, _ in c[2])) / 2 - c[3]
                                     for c in row_cells(r)))
    out = {}
    for (r, k), (img, mine, main, ox, oy, mcx) in cells.items():
        dx = round(ref - mcx) if r not in fixed and abs(ref - mcx) > 4 else 0   # só desvio grande
        left = ox + row_x.get(r, cx) - src // 2
        top = oy + (hand_top if feet[r] is None else feet[r] - (src - 1))
        right = left + src
        sp, layer = img.load(), Image.new("RGBA", img.size)
        dst = layer.load()
        for c in mine:
            sx, sy = dx, 0
            if c is not main:                    # efeito solto: não deixa sair do quadro
                cxs, ys = [x + dx for x, _ in c], [y for _, y in c]
                sx += max(0, left + 2 - min(cxs)) - max(0, max(cxs) - (right - 3))
                sy += max(0, top + 2 - min(ys))
            for (x, y) in c:
                if 0 <= x + sx < img.width and 0 <= y + sy < img.height:
                    dst[x + sx, y + sy] = sp[x, y]
        if cfg.get("bill") and r not in cfg.get("no_feet", ()):
            ground, xa, xb = max(y for _, y in main), min(x for x, _ in main) + dx, max(x for x, _ in main) + dx + 1
            feet_like(layer, ground, xa, xb, cfg.get("feet_reach", {}).get(r, 18), cfg["bill"])
        out[f"{NAMES[r]}{k}"] = to_canvas(layer, left, top, src)
    return out


def strip_frames(im, ecfg, bill=None):
    """Tira de uma linha: cada célula sem o fundo, com os pés na borda de baixo do quadro e o personagem
    no meio (a tira não tem espaçamento regular). Efeitos soltos (tremidinha) ficam dentro do quadro."""
    W, H = im.size
    cols, src = ecfg["cols"], ecfg["src"]
    if ecfg.get("erase"):                    # defeitos da tira: pinta com a cor do fundo do lado
        from PIL import ImageDraw
        im = im.copy()
        draw = ImageDraw.Draw(im)
        for poly in ecfg["erase"]:
            x, y = min(p[0] for p in poly), min(p[1] for p in poly)
            draw.polygon(poly, fill=im.getpixel((max(0, x - 4), y)))
    out = []
    for k, x0 in enumerate(cols):
        x1 = cols[k + 1] if k + 1 < len(cols) else W
        img, comps = cutout(im, (x0, 0, x1, H), ecfg.get("bg_warm"))
        main = max(comps, key=len)
        ground = max(y for _, y in main)
        left = round(sum(x for x, _ in main) / len(main)) - src // 2
        top, right = ground - (src - 1), left + src
        sp, layer = img.load(), Image.new("RGBA", img.size)
        dst = layer.load()
        for c in comps:
            sx = 0
            if c is not main:
                xs = [x for x, _ in c]
                sx = max(0, left + 2 - min(xs)) - max(0, max(xs) - (right - 3))
            for (x, y) in c:
                if 0 <= x + sx < img.width:
                    dst[x + sx, y] = sp[x, y]
        if bill:
            feet_like(layer, ground, min(x for x, _ in main), max(x for x, _ in main) + 1,
                      round(18 * src / 133), bill)
        out.append(to_canvas(layer, left, top, src))
    return out


def main():
    args = [a for a in sys.argv[1:] if "=" not in a]
    extras = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)       # nome=tira.png
    sys.argv[1:] = args
    name, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    cfg = SHEETS[name]
    ncols = len(cfg["cols"])
    im = Image.open(src).convert("RGB")
    fr = frames(im, cfg)
    names = [f"{n}{k}" for n in NAMES for k in range(ncols)]
    for ename, path in extras.items():
        for k, f in enumerate(strip_frames(Image.open(path).convert("RGB"), cfg["extra"][ename], cfg.get("bill"))):
            fr[f"{ename}{k}"] = f
            names.append(f"{ename}{k}")
    mosaic = Image.new("RGB", (SIZE, SIZE * len(names)))
    for i, n in enumerate(names):
        mosaic.paste(fr[n].convert("RGB"), (0, i * SIZE))
    pal_img = mosaic.quantize(COLORS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = pal_img.getpalette()[:COLORS * 3]
    idx = pal_img.load()
    data = bytearray()
    for i, n in enumerate(names):
        a = fr[n].load()
        for y in range(SIZE):
            for x in range(SIZE):
                data.append(0 if a[x, y][3] == 0 else idx[x, i * SIZE + y] + 1)
    header = {"size": SIZE, "frames": names,
              "palette": ["#%02x%02x%02x" % tuple(pal[i:i + 3]) for i in range(0, len(pal), 3)]}
    with open(dst, "wb") as f:
        f.write(zlib.compress(json.dumps(header).encode() + b"\0" + bytes(data), 9))
    print(dst, len(names), "quadros")
    if len(sys.argv) > 4:                            # prévia: todos os quadros numa grade, fundo verde
        prev = Image.new("RGBA", (ncols * (SIZE + 4), -(-len(names) // ncols) * (SIZE + 4)), (40, 200, 90, 255))
        for i, n in enumerate(names):
            prev.alpha_composite(fr[n], ((i % ncols) * (SIZE + 4), (i // ncols) * (SIZE + 4)))
        prev.save(sys.argv[4])


if __name__ == "__main__":
    main()

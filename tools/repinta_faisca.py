"""Redesenha a folha de base do Robô Faísca; depois ela passa pelo conversor de sempre.

    python3 tools/repinta_faisca.py base.png faisca.png [ampliada.png]
    python3 tools/folha_para_pet.py robo_faisca faisca.png claude_pet/chars/robo_faisca.bin [previa.png]

Da folha de base vêm as poses e a animação (9 linhas x 9 quadros, a ordem de sempre). O robô é
redesenhado aqui:
  - paleta: azul -> HELMET (capacete e antenas), vermelho -> BODY (corpo), luzes ciano (olhos, painel)
    -> EYES, cinza claro -> creme (menos a crista listrada do capacete, que fica prata como na folha);
  - a tampa do notebook (linha "trabalhando") ganha um ">_" no lugar do símbolo;
  - sai a peça cinza que a folha desenhou embaixo dos pés na linha "atenção".
Os efeitos soltos (balões, "!", zzz, brilhos) não mudam. `ampliada.png` é a folha nova em 2x, pra conferir.
"""
import colorsys
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from folha_para_pet import MARGIN, cutout  # noqa: E402

COLS = [163, 312, 473, 623, 786, 955, 1116, 1274, 1423]       # mesma grade do SHEETS["robo_faisca"]
ROWS = [0, 115, 228, 343, 457, 560, 658, 761, 882, 1024]
WORK, ATTN = 3, 7
PEDESTAL = (864, 900)            # faixa da peça cinza embaixo dos pés da "atenção"

OUTLINE = (0, 0, 0)              # preto: (6, 6, 9) ainda passava por fundo no conversor (distância < 38)
AMBER, CREAM = 42, 40                                            # matizes: ">_" do notebook, rosto
HELMET = (48, 76, 211)           # RGB: o azul típico do capacete vira exatamente esta cor; os tons em volta seguem
BODY = (239, 43, 13)             # RGB: idem pro corpo (peito e braços, o vermelho da folha)
EYES = (89, 252, 255)            # RGB: idem pros olhos (e as luzes do peito, o ciano da folha)
BLUE_MID = (226, 0.81, 0.765)    # matiz, saturação e brilho medianos do azul da folha original
RED_MID = (2.8, 0.887, 0.847)    # e do vermelho
CYAN_MID = (188.6, 0.859, 0.965)  # e do ciano dos olhos
CREST_BAND = 34                  # a crista fica até essa altura abaixo do alto da cabeça (cabeça tombada: mais)
EYE_MIN = 12                     # grupo ciano desse tamanho, mais largo que alto, é olho; o resto é brilho do capacete
POCKET_BELOW_EYES = 14           # até onde (abaixo do alto dos olhos) os bolsões fechados contam como visor
POCKET_SMALL = 60                # bolsão fechado menor que isso é sombra, não buraco (o conversor furaria)
HOLE_DARK = 60                   # furo do conversor com soma RGB abaixo disso é sombra (o fundo soma ~80)


def hsv(c):
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c[:3]))
    return h * 360, s, v


def rgb(h, s, v):
    return tuple(round(x * 255) for x in colorsys.hsv_to_rgb((h % 360) / 360, min(1, max(0, s)), min(1, max(0, v))))


def kind(c):
    """Classe da cor: contorno, cinza claro/escuro, vermelho, ciano (luz), azul ou outra (madeira, amarelo)."""
    h, s, v = hsv(c)
    if v < 0.3:
        return "dark"
    if s < 0.22:
        return "light" if v >= 0.5 else "gray"
    if h >= 338 or h <= 14:
        return "red" if s >= 0.4 else "other"
    if 175 <= h < 205 and v >= 0.6:
        return "cyan"
    if 205 <= h <= 262 and (s >= 0.45 or (v >= 0.75 and s >= 0.2)):
        return "blue"                # a tampa do notebook (azul-acinzentado, pouco saturado) fica de fora
    return "other"


def recolor(c, k):
    h, s, v = hsv(c)
    if k == "blue":
        hh, hs, hv = hsv(HELMET)
        return rgb(hh + (h - BLUE_MID[0]) * 0.25, s * hs / BLUE_MID[1], v * hv / BLUE_MID[2])
    if k == "red":
        bh, bs, bv = hsv(BODY)
        return rgb(bh + ((h - 360 if h > 180 else h) - RED_MID[0]) * 0.5, s * bs / RED_MID[1], v * bv / RED_MID[2])
    if k == "cyan":
        eh, es, ev = hsv(EYES)
        return rgb(eh + (h - CYAN_MID[0]) * 0.5, s * es / CYAN_MID[1], v * ev / CYAN_MID[2])
    if k == "light":
        return rgb(CREAM, s * 0.5 + 0.1, v)
    return c[:3]


def subject(im, box):
    """O robô da célula: (recorte, pixels dele, classe de cada pixel, alto da cabeça)."""
    img, comps = cutout(im, box)
    px = img.load()
    big = max(comps, key=len)
    main = set(big)
    for c in comps:          # pedaço azul solto (antena que o recorte separou da cabeça) entra junto
        if c is not big and sum(kind(px[q]) == "blue" for q in c) >= 0.3 * len(c):
            main.update(c)
    kinds = {q: kind(px[q]) for q in main}
    blues = [y for q, k in kinds.items() if k == "blue" for y in (q[1],)]
    top = (min(blues) if blues else min(y for _, y in main)) - 3     # alto da cabeça (o balão às vezes encosta)
    return img, main, kinds, top


def eyes_of(kinds):
    """Os olhos acesos: grupos ciano grandes e mais largos que altos. O brilho azul-claro do capacete e das
    antenas também cai em "ciano", mas em pontinhos ou fios em pé; com ele o fim da crista pulava de quadro
    pra quadro. Vazio quando o robô pisca."""
    cyan = {q for q, k in kinds.items() if k == "cyan"}
    eyes, seen = set(), set()
    for q0 in cyan:
        if q0 in seen:
            continue
        comp, todo = {q0}, [q0]
        seen.add(q0)
        while todo:
            x, y = todo.pop()
            for n in ((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                if n in cyan and n not in seen:
                    seen.add(n)
                    comp.add(n)
                    todo.append(n)
        xs, ys = [x for x, _ in comp], [y for _, y in comp]
        if len(comp) >= EYE_MIN and max(xs) - min(xs) >= max(ys) - min(ys):
            eyes |= comp
    return eyes


def head_drop(im, box):
    """Distância do alto da cabeça ao alto dos olhos, ou None se o robô está piscando nesse quadro: a
    medida que vira a mediana da linha pra fechar o quadro de olhos fechados."""
    _, _, kinds, top = subject(im, box)
    eyes = eyes_of(kinds)
    return min(y for _, y in eyes) - top if eyes else None


def _median(values):
    v = sorted(x for x in values if x is not None)
    return v[len(v) // 2] if v else None


def repaint_cell(im, out, box, r, drop):
    """Redesenha o personagem de uma célula da folha (in place em `out`). `drop`: a distância mediana da
    linha entre o alto da cabeça e os olhos, pros quadros em que eles estão fechados."""
    bx, by = box[:2]
    img, main, kinds, top = subject(im, box)
    px = img.load()

    eyes = eyes_of(kinds)
    eye_top = min(y for _, y in eyes) if eyes else top + (drop if drop is not None else CREST_BAND)

    def near(q, ks, r):
        return any(kinds.get((q[0] + dx, q[1] + dy)) in ks for dx in range(-r, r + 1) for dy in range(-r, r + 1))

    # crista: o cinza do alto do capacete (dentro do azul, longe do braço), juntando listras a até 3 px;
    # o maior grupo fica com o prata da folha (senão vira creme, como o rosto)
    cands = {q for q in main if kinds[q] in ("light", "gray") and top <= q[1] <= top + CREST_BAND
             and q[1] < eye_top - 1 and near(q, ("blue",), 3) and not near(q, ("red",), 3)}
    crest, seen = set(), set()
    for q0 in cands:
        if q0 in seen:
            continue
        group, todo = {q0}, [q0]
        seen.add(q0)
        while todo:
            x, y = todo.pop()
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    n = (x + dx, y + dy)
                    if n in cands and n not in seen:
                        seen.add(n)
                        group.add(n)
                        todo.append(n)
        if len(group) > len(crest):
            crest = group

    # creme só no cinza claro do corpo (grupos encostados em cor do robô); balão e brilho soltos ficam brancos
    body_light, seen = set(), set()
    for q0 in (q for q in main if kinds[q] == "light"):
        if q0 in seen:
            continue
        group, todo, touch = {q0}, [q0], False
        seen.add(q0)
        while todo:
            x, y = todo.pop()
            touch = touch or near((x, y), ("blue", "red", "cyan"), 1)
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in main and kinds[n] == "light" and n not in seen:
                    seen.add(n)
                    group.add(n)
                    todo.append(n)
        if touch:
            body_light |= group

    po = out.load()
    bg = im.getpixel((5, 5))
    # bolsões fechados de "fundo" na cabeça são o visor (azul-marinho quase da cor do fundo): escurece,
    # senão o conversor os fura
    closed = _enclosed(img)
    while closed:                                    # pequenos em qualquer lugar; na cabeça, de qualquer tamanho
        q0 = closed.pop()
        pocket, todo = {q0}, [q0]
        while todo:
            x, y = todo.pop()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in closed:
                    closed.discard(n)
                    pocket.add(n)
                    todo.append(n)
        cy = sum(y for _, y in pocket) / len(pocket)
        if len(pocket) <= POCKET_SMALL or cy < eye_top + POCKET_BELOW_EYES:
            for x, y in pocket:
                po[bx + x, by + y] = tuple(round(c * 0.35) for c in im.getpixel((bx + x, by + y)))
    for q in main:
        X, Y = bx + q[0], by + q[1]
        k = kinds[q]
        if q in crest:
            po[X, Y] = px[q][:3]
        elif k == "dark":
            po[X, Y] = tuple(round(c * 0.35) for c in px[q][:3])     # contorno bem escuro: não some no fundo
        elif k == "light" and q not in body_light:
            po[X, Y] = px[q][:3]
        elif k == "cyan" and q not in eyes and q[1] < eye_top:
            po[X, Y] = recolor(px[q], "blue")                             # brilho do capacete, não luz
        else:
            po[X, Y] = recolor(px[q], k)

    if r == WORK:
        prompt_on_lid(out, img, main, kinds, box)


def _enclosed(img):
    """Pixels transparentes de um recorte do conversor que não chegam à borda: os bolsões que ele furou."""
    w, h = img.size
    a = img.load()
    todo = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    todo = [q for q in todo if a[q][3] == 0]
    open_ = set(todo)
    while todo:
        x, y = todo.pop()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= n[0] < w and 0 <= n[1] < h and n not in open_ and a[n][3] == 0:
                open_.add(n)
                todo.append(n)
    return {(x, y) for x in range(w) for y in range(h) if a[x, y][3] == 0 and (x, y) not in open_}


def fill_holes(out):
    """Sombra azul-marinho quase da cor do fundo, fechada dentro do desenho, o conversor recorta como buraco
    (furinhos no capacete e no rosto). Com as mesmas caixas dele, pinta de contorno o que ele furaria e é
    mais escuro que o fundo; fundo de verdade (vão da cadeira, entre braço e corpo) tem a cor do fundo e fica."""
    W, H = out.size
    po = out.load()
    for r in range(len(ROWS) - 1):
        for k, x0 in enumerate(COLS):
            x1 = COLS[k + 1] if k + 1 < len(COLS) else W
            box = (max(0, x0 - MARGIN), max(0, ROWS[r] - MARGIN), min(W, x1 + MARGIN), min(H, ROWS[r + 1] + MARGIN))
            img, _ = cutout(out, box)
            for x, y in _enclosed(img):
                q = (box[0] + x, box[1] + y)
                if sum(po[q]) < HOLE_DARK:
                    po[q] = OUTLINE


def prompt_on_lid(out, img, main, kinds, box):
    """Tampa do notebook: apaga o símbolo (o claro dentro da tampa) e desenha um ">_" âmbar."""
    bx, by = box[:2]
    w, h = box[2] - bx, box[3] - by
    logo = [q for q in main if kinds[q] in ("light", "gray") and q[0] >= 0.62 * w and 0.5 * h <= q[1] <= 0.76 * h]
    if not logo:
        return
    x0, x1 = min(x for x, _ in logo), max(x for x, _ in logo)
    y0, y1 = min(y for _, y in logo), max(y for _, y in logo)
    lid = [img.getpixel(q)[:3] for q in main if kinds[q] == "gray" and abs(q[1] - (y0 + y1) / 2) < 14
           and x0 - 8 <= q[0] <= x1 + 8 and not (x0 <= q[0] <= x1 and y0 <= q[1] <= y1)]
    fill = tuple(sorted(c[i] for c in lid)[len(lid) // 2] for i in range(3)) if lid else (60, 64, 82)
    draw = ImageDraw.Draw(out)
    draw.rectangle((bx + x0 - 1, by + y0 - 1, bx + x1 + 1, by + y1 + 1), fill=fill)
    cx, cy = bx + (x0 + x1) // 2, by + (y0 + y1) // 2
    amber = rgb(AMBER, 0.75, 1.0)
    draw.line([(cx - 9, cy - 6), (cx - 3, cy), (cx - 9, cy + 6)], fill=amber, width=3)      # ">"
    draw.rectangle((cx + 0, cy + 5, cx + 9, cy + 7), fill=amber)                           # "_"


def main():
    src, dst = sys.argv[1], sys.argv[2]
    im = Image.open(src).convert("RGB")
    W, H = im.size
    bg = im.getpixel((5, 5))
    ImageDraw.Draw(im).rectangle((COLS[0], PEDESTAL[0], W - 1, PEDESTAL[1] - 1), fill=bg)
    out = im.copy()
    for r in range(len(ROWS) - 1):
        boxes = [(x0, ROWS[r], COLS[k + 1] if k + 1 < len(COLS) else W, ROWS[r + 1]) for k, x0 in enumerate(COLS)]
        drop = _median(head_drop(im, b) for b in boxes)
        for b in boxes:
            repaint_cell(im, out, b, r, drop)
    fill_holes(out)
    out.save(dst)
    print(dst)
    if len(sys.argv) > 3:
        out.resize((W * 2, H * 2), Image.NEAREST).save(sys.argv[3])


if __name__ == "__main__":
    main()

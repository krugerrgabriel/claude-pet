"""Personagens feitos de folha de sprites: quadros prontos num .bin gerado por tools/folha_para_pet.py.

Cada quadro tem SIZE x SIZE (90: 3 x 3 por pixel lógico do canvas de 30). Na escala 3 é 1 pixel da imagem
por pixel de tela; nas outras escalas os quadros são reamostrados (pixel mais próximo). O desenho é só
"cor + retângulo + preencher", igual aos outros personagens, então funciona igual no Linux e no Windows.

Crossfade: entre um quadro da folha e o próximo entram `fade - 1` quadros misturados (o próximo aparecendo
aos poucos) e a animação roda `fade` vezes mais rápido, então o movimento fica mais fluido sem mudar de
ritmo. Onde os dois quadros têm desenho, as cores se misturam; onde só um tem, a meia transparência vira
um pontilhado fino (Bayer 4x4), porque o pet só desenha retângulos de cor sólida.

O crossfade pode ser desligado (`set_smooth(False)`, menu "Animação" > "Quadro a quadro"): aí cada quadro
da folha aparece puro durante as suas `fade` vezes, então o ritmo é o mesmo, só sem as misturas.

Uso, no módulo do personagem:

    _FOLHA = Folha(Path(__file__).with_suffix(".bin"), {"stand": (5, run("parado", (0, 1, 2))), ...})
    ANIMS = _FOLHA.anims
    render = _FOLHA.render
    set_smooth = _FOLHA.set_smooth
"""
from __future__ import annotations

import json
import zlib
from pathlib import Path

N = 30                   # canvas lógico (igual aos outros personagens)
BAYER = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)


def run(name, frames):
    """Nomes dos quadros: run("parado", (0, 1, 2)) -> ["parado0", "parado1", "parado2"]."""
    return [f"{name}{k}" for k in frames]


class Folha:
    def __init__(self, path, sheet, fade=3):
        """sheet: animação -> (quadros por segundo, nomes dos quadros da folha)."""
        raw = zlib.decompress(Path(path).read_bytes())
        head, _, self._pixels = raw.partition(b"\0")
        meta = json.loads(head)
        self.size = meta["size"]
        self._index = {name: i for i, name in enumerate(meta["frames"])}
        self._pal = [int(c[1:], 16) for c in meta["palette"]]          # 0xRRGGBB
        self.fade = fade
        self.smooth = True       # False = sem crossfade (quadro a quadro)
        self._base: dict = {}
        self._cache: dict = {}
        self.seq = {a: self._crossfade(fps, names) for a, (fps, names) in sheet.items()}
        self.anims = {a: (fps, len(keys)) for a, (fps, keys) in self.seq.items()}

    def _crossfade(self, fps, names):
        """Cada quadro vira `fade`: (este, próximo, quanto do próximo) com 0, 1/fade, 2/fade...
        O quadro puro é sempre (este, este, 0.0), o mesmo que o modo sem crossfade usa (cache em comum)."""
        keys = []
        for i, a in enumerate(names):
            b = names[(i + 1) % len(names)]
            keys += [(a, b, s / self.fade) if s and b != a else (a, a, 0.0) for s in range(self.fade)]
        return fps * self.fade, keys

    def set_smooth(self, on):
        """Liga (padrão) ou desliga o crossfade. O número de quadros e o ritmo não mudam."""
        self.smooth = bool(on)

    def derive(self, name, base, paint, flip=()):
        """Quadro novo `name`, feito em código: o quadro `base` da folha com as caixas `flip` ((x0, y0, x1, y1),
        inclusivas) viradas de cabeça pra baixo e `paint` ({(x, y): 0xRRGGBB}, em pixels do quadro) por cima.
        Pra animação que a folha não tem, montada a partir de um quadro dela."""
        src = self._frame(base)
        pixels, n = list(src), self.size
        for x0, y0, x1, y1 in flip:
            for y in range(y0, y1 + 1):
                pixels[y * n + x0:y * n + x1 + 1] = src[(y0 + y1 - y) * n + x0:(y0 + y1 - y) * n + x1 + 1]
        for (x, y), c in paint.items():
            if 0 <= x < self.size and 0 <= y < self.size:
                pixels[y * self.size + x] = c
        self._base[name] = pixels
        self._cache.clear()

    def _frame(self, name):
        """Cor de cada pixel do quadro da folha, 0xRRGGBB, ou -1 (transparente)."""
        got = self._base.get(name)
        if got is None:
            n = self.size * self.size
            i = self._index[name] * n
            got = self._base[name] = [self._pal[v - 1] if v else -1 for v in self._pixels[i:i + n]]
        return got

    def _mixed(self, a, b, t):
        """Quadro `a` com `t` do quadro `b` por cima: cores misturadas onde os dois têm desenho; onde só um
        tem, ele aparece no pontilhado (Bayer) na proporção da sua transparência."""
        pa = self._frame(a)
        if t == 0:
            return pa
        pb, size, u = self._frame(b), self.size, 1 - t
        out = []
        for i in range(size * size):
            ca, cb = pa[i], pb[i]
            if ca >= 0 and cb >= 0:
                out.append((round((ca >> 16) * u + (cb >> 16) * t) << 16)
                           | (round((ca >> 8 & 255) * u + (cb >> 8 & 255) * t) << 8)
                           | round((ca & 255) * u + (cb & 255) * t))
            elif ca >= 0 or cb >= 0:
                alpha = u if ca >= 0 else t
                y, x = divmod(i, size)
                out.append(max(ca, cb) if alpha * 16 > BAYER[(y & 3) * 4 + (x & 3)] + 0.5 else -1)
            else:
                out.append(-1)
        return out

    def _rects(self, key, px):
        """Retângulos do quadro em `px` pixels de tela por pixel lógico, juntos por cor:
        [(rgb, [(x, y, w, h), ...]), ...]. Faixas iguais em linhas seguidas viram um retângulo só."""
        got = self._cache.get((key, px))
        if got is not None:
            return got
        pixels, size = self._mixed(*key), self.size
        side = N * px
        src = [min(size - 1, (2 * i + 1) * size // (2 * side)) for i in range(side)]   # pixel mais próximo
        open_: dict = {}        # (x, w, cor) -> [x, y, w, h] ainda crescendo pra baixo
        done = []
        for y in range(side):
            row = pixels[src[y] * size: (src[y] + 1) * size]
            runs, x = {}, 0
            while x < side:
                c = row[src[x]]
                k = x + 1
                while k < side and row[src[k]] == c:
                    k += 1
                if c >= 0:
                    runs[(x, k - x, c)] = True
                x = k
            for run_, r in list(open_.items()):
                if run_ in runs:
                    r[3] += 1
                    del runs[run_]
                else:
                    done.append((run_[2], r))
                    del open_[run_]
            for run_ in runs:
                open_[run_] = [run_[0], y, run_[1], 1]
        done.extend((run_[2], r) for run_, r in open_.items())
        by_color: dict = {}
        for c, r in done:
            by_color.setdefault(c, []).append(tuple(r))
        got = [(((c >> 16) / 255, (c >> 8 & 255) / 255, (c & 255) / 255), rects) for c, rects in by_color.items()]
        if len(self._cache) > 1200:
            self._cache.clear()
        self._cache[(key, px)] = got
        return got

    def render(self, pen, anim, frame, look, light):
        cr, px = pen.cr, round(pen.s)
        side = N * px
        key = self.seq[anim][1][frame]
        if not self.smooth:
            key = (key[0], key[0], 0.0)      # só o quadro da folha, sem mistura com o próximo
        for rgb, rects in self._rects(key, px):
            cr.set_source_rgb(*rgb)
            for (x, y, w, h) in rects:
                cr.rectangle(side - x - w if pen.flip else x, y, w, h)
                cr.fill()

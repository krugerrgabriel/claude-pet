"""Ferramentas de desenho pixel art compartilhadas pelos personagens.

`Pen` desenha em coordenadas lógicas do canvas (CANVAS x CANVAS), já multiplicadas pela escala,
e pode espelhar na horizontal (personagens de perfil virados pra esquerda).
`overlay()` desenha os efeitos por cima (nuvem de pensamento, zzz, !, ✓, brilhos, coração),
que nunca são espelhados.
"""
from __future__ import annotations

import colorsys

CANVAS = 30

STATUS_COLORS = {
    "idle": "#6fcf97",
    "thinking": "#56ccf2",
    "working": "#f2c94c",
    "attention": "#eb5757",
    "done": "#2ecc71",
    "sleep": "#466b60",
}


def hex_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def shade(h: str, factor: float) -> str:
    """Clareia (>1) ou escurece (<1) mantendo matiz e saturação."""
    r, g, b = hex_rgb(h)
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(hh, max(0, min(1, ll * factor)), ss)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


class Pen:
    def __init__(self, cr, scale: int, flip: bool = False, canvas: int = CANVAS):
        self.cr, self.s, self.flip, self.canvas = cr, scale, flip, canvas

    def px(self, x: float, y: float, w: float = 1, h: float = 1, color: str = "#000000") -> None:
        if self.flip:
            x = self.canvas - x - w
        self.cr.set_source_rgb(*hex_rgb(color))
        self.cr.rectangle(x * self.s, y * self.s, w * self.s, h * self.s)
        self.cr.fill()

    def sprite(self, x: int, y: int, rows: list[str], palette: dict[str, str]) -> None:
        """Desenha uma grade de caracteres; '.' e ' ' são transparentes. Junta pixels iguais em linha."""
        for j, row in enumerate(rows):
            i = 0
            while i < len(row):
                c = row[i]
                if c in ". " or c not in palette:
                    i += 1
                    continue
                k = i
                while k < len(row) and row[k] == c:
                    k += 1
                self.px(x + i, y + j, k - i, 1, palette[c])
                i = k


def hmirror(rows: list[str]) -> list[str]:
    return [r[::-1] for r in rows]


# ---------------------------------------------------------------- efeitos por cima
THOUGHT_CLOUD = [
    "..OOO.OOO...",
    ".OWWWOWWWOO.",
    "OWWWWWWWWWWO",
    "OWWWWWWWWWGO",
    ".OGWWWWWWGO.",
    "..OOOOOOOO..",
]
THOUGHT_COLORS = {"O": "#5d6b7e", "W": "#ffffff", "G": "#d5dce6", "d": "#5d6b7e"}

GLYPHS = {
    "z": ["###", "..#", ".#.", "#..", "###"],
    "bang": ["##", "##", "##", "##", "..", "##"],
    "heart": [".#.#.", "#####", "#####", ".###.", "..#.."],
    "spark": [".#.", "###", ".#."],
    "check": ["....#", "...#.", "#.#..", ".#..."],
    "dot": ["##", "##"],
}


def _glyph(pen: Pen, name: str, x: int, y: int, color: str, mirror: bool = False) -> None:
    rows = GLYPHS[name]
    if mirror:  # muda de lado, mas a letra não espelha (z continua z)
        x = pen.canvas - x - len(rows[0])
    pen.sprite(x, y, [r.replace("#", "g") for r in rows], {"g": color})


def overlay(pen: Pen, name: str | None, f: int, dx: int = 0, dy: int = 0, mirror: bool = False) -> None:
    """Efeito por cima do personagem. (dx, dy) desloca tudo (cada personagem tem a cabeça num lugar).

    mirror=True: personagem de perfil virado pra esquerda; o efeito vai pro outro lado sem espelhar o desenho.
    """
    if not name:
        return
    m = mirror

    def mx(x: int, w: int) -> int:
        return pen.canvas - x - w if m else x

    if name == "thought":
        x, y = 17 + dx, 0 + dy
        step = f % 4
        pen.px(mx(x - 1, 1), y + 8, 1, 1, THOUGHT_COLORS["W"])
        if step >= 1:
            pen.px(mx(x, 2), y + 6, 2, 2, THOUGHT_COLORS["W"])
        pen.sprite(mx(x, len(THOUGHT_CLOUD[0])), y, THOUGHT_CLOUD, THOUGHT_COLORS)
        for k in range(min(3, step + 1)):
            pen.px(mx(x + 3 + k * 3, 1), y + 3, 1, 1, THOUGHT_COLORS["d"])
    elif name == "zzz":
        for k in range(3):
            step = (f + k) % 4
            if step < 3:
                _glyph(pen, "z", 20 + k * 3 + dx, 6 - step * 2 - k + dy, "#8fa6c2", m)
    elif name == "dots":
        for k in range(f % 4):
            _glyph(pen, "dot", 19 + k * 3 + dx, 4 - k + dy, "#e0f7fa", m)
    elif name == "bang":
        if f % 2 == 0:
            _glyph(pen, "bang", 24 + dx, 0 + dy, STATUS_COLORS["attention"], m)
    elif name == "sparkle":
        for k, (x, y) in enumerate([(1, 6), (26, 9), (23, 1), (4, 1), (27, 3)]):
            if (k + f) % 2 == 0:
                _glyph(pen, "spark", x, y + dy, "#ffe66d", m)
    elif name == "heart":
        _glyph(pen, "heart", 22 + dx, 4 - (f % 4) + dy, "#ff6b9a", m)
    elif name == "check":
        if f % 3 != 2:
            _glyph(pen, "check", 23 + dx, 2 + dy, STATUS_COLORS["done"], m)


# ---------------------------------------------------------------- computadorzinho (compartilhado)
MONITOR = [
    "OOOOOOOOOO",
    "OSSSSSSSSO",
    "OSdddddSSO",
    "OSSSSSSSSO",
    "OSSddddSSO",
    "OSSSSSSSSO",
    "OOOOOOOOOO",
    "....FF....",
    "...FFFF...",
]
MONITOR_TYPING = [  # quadro alternado: as linhas de "código" mudam de tamanho (digitando)
    "OOOOOOOOOO",
    "OSSSSSSSSO",
    "OSdddSSSSO",
    "OSSSSSSSSO",
    "OSSdddddSO",
    "OSSSSSSSSO",
    "OOOOOOOOOO",
    "....FF....",
    "...FFFF...",
]
KEYBOARD = [
    "hhhhhhh",
    "KkKkKkK",
]


def draw_computer(pen: Pen, x: int, y: int, light: str, frame: int = 0, keyboard_at: tuple[int, int] | None = None) -> None:
    """Monitor 10x9 com a tela acesa na cor do status e "linhas de código" (que mudam com o quadro).

    (x, y) = canto de cima do monitor. keyboard_at = (x, y) do teclado 7x2, se quiser um na frente.
    """
    rows = MONITOR if frame % 2 == 0 else MONITOR_TYPING
    pen.sprite(x, y, rows, {"O": "#56657a", "S": shade(light, 1.25), "d": shade(light, 0.55), "F": "#56657a"})
    pen.px(x + 1, y + 1, 2, 1, "#ffffff")  # reflexo no vidro
    if keyboard_at:
        kx, ky = keyboard_at
        pen.sprite(kx, ky, KEYBOARD, {"h": "#c4ccd6", "K": "#aab4be", "k": "#3b4652"})

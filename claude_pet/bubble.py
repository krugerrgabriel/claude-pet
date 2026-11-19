"""Balão de fala em estilo pixel art.

`shape()` é só geometria (retângulos coloridos) e serve pro GTK e pro Tk; o texto no Linux sai pelo
Pango (importado só quando usado, pra este arquivo também carregar no Windows).
"""
from __future__ import annotations

PX = 2          # tamanho do "pixel" da borda
PAD_X, PAD_Y = 7, 4
TAIL = 6        # altura do rabinho (em px de tela)
FILL = (1.0, 0.98, 0.93)
INK = (0.11, 0.13, 0.17)
FONT = "Sans Bold 8"


def box_size(text_w: int, text_h: int) -> tuple[int, int]:
    w = text_w + 2 * (PAD_X + PX)
    h = text_h + 2 * (PAD_Y + PX) + TAIL
    return w + w % 2, h + h % 2


def text_origin(tail_down: bool) -> tuple[int, int]:
    """Canto de cima/esquerda do texto dentro do balão."""
    return PX + PAD_X, (0 if tail_down else TAIL) + PX + PAD_Y


def shape(w: int, h: int, tail_x: int, tail_down: bool = True) -> list[tuple[int, int, int, int, tuple]]:
    """Corpo com cantos em degrau + rabinho em escada apontando para o bicho: [(x, y, w, h, cor)]."""
    body_y = 0 if tail_down else TAIL
    bh = h - TAIL
    out = [
        # contorno (desenhado como "cruz" para dar canto em degrau) e preenchimento
        (PX, body_y, w - 2 * PX, bh, INK),
        (0, body_y + PX, w, bh - 2 * PX, INK),
        (2 * PX, body_y + PX, w - 4 * PX, bh - 2 * PX, FILL),
        (PX, body_y + 2 * PX, w - 2 * PX, bh - 4 * PX, FILL),
    ]
    # rabinho em escada: cada linha 1 "pixel" mais estreita, contorno nas pontas
    n = TAIL // PX
    tx = max((n + 2) * PX, min(w - (n + 2) * PX, tail_x))
    for i in range(n + 1):
        half = (n - i) * PX + PX
        y = (body_y + bh - PX + i * PX) if tail_down else (body_y - i * PX)
        out.append((tx - half, y, 2 * half, PX, INK))
        if i < n:
            out.append((tx - half + PX, y, 2 * half - 2 * PX, PX, FILL))
    return out


# ---------------------------------------------------------------- Linux (Pango/cairo)
def make_layout(ctx_or_widget, text: str):
    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import GLib, Pango, PangoCairo

    if hasattr(ctx_or_widget, "create_pango_layout"):
        layout = ctx_or_widget.create_pango_layout("")
    else:
        layout = PangoCairo.create_layout(ctx_or_widget)
    layout.set_font_description(Pango.FontDescription(FONT))
    layout.set_alignment(Pango.Alignment.CENTER)
    layout.set_markup(GLib.markup_escape_text(text), -1)
    return layout


def size_for(layout) -> tuple[int, int]:
    return box_size(*layout.get_pixel_size())


def draw(cr, layout, w: int, h: int, tail_x: int, tail_down: bool = True) -> None:
    from gi.repository import PangoCairo

    for x, y, rw, rh, color in shape(w, h, tail_x, tail_down):
        cr.set_source_rgb(*color)
        cr.rectangle(x, y, rw, rh)
        cr.fill()
    cr.set_source_rgb(*INK)
    cr.move_to(*text_origin(tail_down))
    PangoCairo.show_layout(cr, layout)

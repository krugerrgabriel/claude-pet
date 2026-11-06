"""Balão de fala em estilo pixel art (desenho separado da janela para dar para gerar prévia)."""
from __future__ import annotations

import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import GLib, Pango, PangoCairo  # noqa: E402

PX = 2          # tamanho do "pixel" da borda
PAD_X, PAD_Y = 7, 4
TAIL = 6        # altura do rabinho (em px de tela)
FILL = (1.0, 0.98, 0.93)
INK = (0.11, 0.13, 0.17)
FONT = "Sans Bold 8"

def markup(text: str, status: str = "") -> str:
    return GLib.markup_escape_text(text)


def make_layout(ctx_or_widget, text: str, status: str) -> Pango.Layout:
    if hasattr(ctx_or_widget, "create_pango_layout"):
        layout = ctx_or_widget.create_pango_layout("")
    else:
        layout = PangoCairo.create_layout(ctx_or_widget)
    layout.set_font_description(Pango.FontDescription(FONT))
    layout.set_alignment(Pango.Alignment.CENTER)
    layout.set_markup(markup(text, status), -1)
    return layout


def size_for(layout: Pango.Layout) -> tuple[int, int]:
    tw, th = layout.get_pixel_size()
    w = tw + 2 * (PAD_X + PX)
    h = th + 2 * (PAD_Y + PX) + TAIL
    return w + w % 2, h + h % 2


def draw(cr, layout: Pango.Layout, w: int, h: int, tail_x: int, tail_down: bool = True) -> None:
    """Corpo com cantos em degrau + rabinho em escada apontando para o bicho."""
    body_y = 0 if tail_down else TAIL
    bh = h - TAIL

    def rect(x, y, rw, rh, color):
        cr.set_source_rgb(*color)
        cr.rectangle(x, y, rw, rh)
        cr.fill()

    # contorno (desenhado como "cruz" para dar canto em degrau) e preenchimento
    rect(PX, body_y, w - 2 * PX, bh, INK)
    rect(0, body_y + PX, w, bh - 2 * PX, INK)
    rect(2 * PX, body_y + PX, w - 4 * PX, bh - 2 * PX, FILL)
    rect(PX, body_y + 2 * PX, w - 2 * PX, bh - 4 * PX, FILL)

    # rabinho em escada: cada linha 1 "pixel" mais estreita, contorno nas pontas
    n = TAIL // PX
    tx = max((n + 2) * PX, min(w - (n + 2) * PX, tail_x))
    for i in range(n + 1):
        half = (n - i) * PX + PX
        y = (body_y + bh - PX + i * PX) if tail_down else (body_y - i * PX)
        rect(tx - half, y, 2 * half, PX, INK)
        if i < n:
            rect(tx - half + PX, y, 2 * half - 2 * PX, PX, FILL)

    cr.set_source_rgb(*INK)
    cr.move_to(PX + PAD_X, body_y + PX + PAD_Y)
    PangoCairo.show_layout(cr, layout)

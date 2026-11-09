"""Folha de revisão de um personagem: todos os quadros ampliados + tira em tamanho real.

    python3 tools/sheet.py lagartixa saida.png [escala]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cairo  # noqa: E402

from claude_pet import skins  # noqa: E402

STATUS_FOR = {"think": "thinking", "think_walk": "thinking", "work": "working", "attention": "attention",
              "celebrate": "done", "waiting": "done", "sleep": "sleep"}

name = sys.argv[1]
out = sys.argv[2]
scale = int(sys.argv[3]) if len(sys.argv) > 3 else 6
skin = skins.load(name)
n = skin.canvas
anims = skins.ANIM_NAMES
cols = max(skin.anim_info(a)[1] for a in anims)
cell = n * scale + 4
label_w = 90
real = 3
strip_h = n * real + 10
W = label_w + cols * cell
H = len(anims) * cell + 2 * strip_h + 20
surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
cr = cairo.Context(surf)
cr.set_source_rgb(0.93, 0.94, 0.96)
cr.paint()
for row, anim in enumerate(anims):
    _fps, count = skin.anim_info(anim)
    cr.set_source_rgb(0.2, 0.2, 0.25)
    cr.move_to(4, row * cell + cell / 2)
    cr.set_font_size(12)
    cr.show_text(anim)
    for col in range(count):
        cr.save()
        cr.translate(label_w + col * cell, row * cell)
        cr.set_source_rgb(0.84, 0.86, 0.9)
        cr.rectangle(0, 0, n * scale, n * scale)
        cr.fill()
        hx, hy, hw, hh = skin.hit
        cr.set_source_rgba(1, 0, 0, 0.35)
        cr.set_line_width(1)
        cr.rectangle(hx * scale + 0.5, hy * scale + 0.5, hw * scale - 1, hh * scale - 1)
        cr.stroke()
        skin.draw(cr, anim, col, 1, STATUS_FOR.get(anim, "idle"), scale, "#5ec4b6")
        cr.restore()

# tiras em tamanho real (escala 3): fundo claro e escuro, virado pros dois lados
y0 = len(anims) * cell + 10
for k, bg in enumerate([(0.95, 0.95, 0.95), (0.12, 0.13, 0.16)]):
    y = y0 + k * strip_h
    cr.set_source_rgb(*bg)
    cr.rectangle(0, y, W, strip_h)
    cr.fill()
    x = 4
    for anim in anims:
        for facing in (1, -1) if anim == "walk" else (1,):
            cr.save()
            cr.translate(x, y + 5)
            skin.draw(cr, anim, 0, facing, STATUS_FOR.get(anim, "idle"), real, "#5ec4b6", facing=facing)
            cr.restore()
            x += n * real + 2
surf.write_to_png(out)
print(out)

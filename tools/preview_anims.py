"""Folha com todos os frames de todas as animações de uma skin, já com movimento de membros.

    python3 tools/preview_anims.py pato /tmp/pato.png [escala]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cairo  # noqa: E402

from claude_pet import skins  # noqa: E402

STATUS = {"think": "thinking", "think_walk": "thinking", "work": "working", "attention": "attention",
          "celebrate": "done", "waiting": "done"}
name, out = sys.argv[1], sys.argv[2]
scale = int(sys.argv[3]) if len(sys.argv) > 3 else 4
skin = skins.load(name)
anims = ["walk", "work", "attention", "celebrate", "think_walk", "dangle", "happy"]
cell = skin.canvas * scale + 4
cols = max(skin.anim_info(a)[1] for a in anims)
surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100 + cols * cell, len(anims) * cell)
cr = cairo.Context(surf)
cr.set_source_rgb(0.16, 0.18, 0.22)
cr.paint()
for r, anim in enumerate(anims):
    cr.set_source_rgb(0.9, 0.9, 0.9)
    cr.move_to(4, r * cell + cell / 2)
    cr.set_font_size(13)
    cr.show_text(anim)
    for c in range(skin.anim_info(anim)[1]):
        cr.save()
        cr.translate(100 + c * cell, r * cell)
        skin.draw(cr, anim, c, 1, STATUS.get(anim, "idle"), scale, "#5ec4b6")
        cr.restore()
surf.write_to_png(out)
print(out)

"""Gera uma folha PNG com todos os frames de todas as animações (para revisar a arte)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cairo
from claude_pet.sprites import ANIMATIONS, CANVAS, STATUS_COLORS, render

STATUS_FOR = {"think": "thinking", "think_walk": "thinking", "work": "working", "attention": "attention",
              "celebrate": "done", "waiting": "done", "sleep": "sleep"}
scale = int(sys.argv[2]) if len(sys.argv) > 2 else 4
out = sys.argv[1] if len(sys.argv) > 1 else "preview.png"
cols = max(len(f) for _, f in ANIMATIONS.values())
cell = CANVAS * scale + 6
surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, cols * cell + 110, len(ANIMATIONS) * cell)
cr = cairo.Context(surf)
cr.set_source_rgb(0.93, 0.94, 0.96); cr.paint()
for row, (name, (_, frames)) in enumerate(ANIMATIONS.items()):
    cr.set_source_rgb(0.2, 0.2, 0.25); cr.move_to(4, row * cell + cell / 2); cr.set_font_size(13); cr.show_text(name)
    for col, pose in enumerate(frames):
        pose = dict(pose, antenna=STATUS_COLORS[STATUS_FOR.get(name, "idle")])
        cr.save(); cr.translate(110 + col * cell, row * cell)
        cr.set_source_rgb(0.85, 0.87, 0.9); cr.rectangle(0, 0, CANVAS * scale, CANVAS * scale); cr.fill()
        render(cr, pose, scale, "#5ec4b6"); cr.restore()
surf.write_to_png(out)
print(out)

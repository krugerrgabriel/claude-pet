"""Gera os GIFs do README (docs/): o Bit em cada estado, desenhado pelo mesmo código do pet."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cairo  # noqa: E402
from PIL import Image  # noqa: E402

from claude_pet import skins  # noqa: E402

SCALE = 4
BG = (22, 27, 34)  # fundo escuro do GitHub
STATES = [  # (arquivo, animação, status da antena, segundos)
    ("idle", "walk", "idle", 1.0),
    ("thinking", "think", "thinking", 2.7),
    ("working", "work", "working", 2.2),
    ("attention", "attention", "attention", 1.6),
    ("done", "celebrate", "done", 1.4),
    ("sleeping", "sleep", "sleep", 2.0),
    ("dragged", "dangle", "idle", 1.0),
]
SKIN = skins.load()


def frames(anim, status, seconds, lean_wave=False):
    fps, n = SKIN.anim_info(anim)
    total = max(n, round(seconds * fps))
    out = []
    size = SKIN.canvas * SCALE
    for i in range(total):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surf)
        cr.set_source_rgb(*(c / 255 for c in BG))
        cr.paint()
        lean = 0.0
        if lean_wave:
            import math
            lean = 0.3 * math.sin(i / total * 2 * math.pi)
        SKIN.draw(cr, anim, i, 1, status, SCALE, "#5ec4b6", lean)
        img = Image.frombuffer("RGBA", (size, size), bytes(surf.get_data()), "raw", "BGRA", 0, 1).convert("RGB")
        out.append(img)
    return out, int(1000 / fps)


def save(path, imgs, ms):
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=ms, loop=0, optimize=True)


if __name__ == "__main__":
    strip_frames = []
    for name, anim, status, secs in STATES:
        imgs, ms = frames(anim, status, secs, lean_wave=(name == "dragged"))
        save(ROOT / "docs" / "states" / f"{name}.gif", imgs, ms)
    # herói: os 5 estados principais lado a lado, sincronizados a ~8 fps
    main = [s for s in STATES if s[0] in ("idle", "thinking", "working", "attention", "done")]
    seqs = [frames(a, st, 3.0)[0] for _, a, st, _ in main]
    n = 24
    size = SKIN.canvas * SCALE
    for k in range(n):
        canvas = Image.new("RGB", (size * len(seqs), size), BG)
        for j, seq in enumerate(seqs):
            canvas.paste(seq[(k * len(seq)) // n], (j * size, 0))
        strip_frames.append(canvas)
    save(ROOT / "docs" / "hero.gif", strip_frames, 125)
    print("ok")

"""Gera art/review.html: todos os personagens, poses separadas e animações rodando, para revisão.

    python3 tools/review_html.py [escala]     →  abre art/review.html no navegador
"""
import base64
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cairo  # noqa: E402

from claude_pet import skins  # noqa: E402
from claude_pet.sprites import ANIMATIONS  # noqa: E402

SCALE = int(sys.argv[1]) if len(sys.argv) > 1 else 4
OUT = ROOT / "art" / "review.html"

ANIM_INFO = {  # nome interno → (rótulo, quando aparece, status da antena)
    "stand": ("Parado", "ocioso, entre uma caminhada e outra", "idle"),
    "walk": ("Andando", "ocioso, passeando pelas bordas", "idle"),
    "sit": ("Sentado", "ocioso, descansando", "idle"),
    "sleep": ("Dormindo", "3 min sem atividade", "sleep"),
    "curious": ("Curioso", "mouse chegou perto", "idle"),
    "happy": ("Carinho", "mouse parado em cima dele", "idle"),
    "think": ("Pensando", "depois do seu prompt", "thinking"),
    "think_walk": ("Pensando andando", "depois do seu prompt, andando de um lado pro outro", "thinking"),
    "work": ("Trabalhando", "Claude rodando uma ferramenta", "working"),
    "attention": ("Pedindo atenção", "Claude pediu permissão", "attention"),
    "celebrate": ("Comemorando", "Claude terminou (primeiros segundos)", "done"),
    "waiting": ("Esperando você", "Claude terminou, até você clicar", "done"),
    "dangle": ("Agarrado", "você está arrastando ele", "idle"),
}
POSE_LABEL = {"idle": "Parado", "sit": "Sentado", "sleep": "Dormindo", "thinking": "Pensando",
              "working": "Trabalhando", "alert": "Alerta", "done": "Terminou", "grabbed": "Agarrado"}
PART_COLORS = {"footL": (0.2, 0.6, 1), "footR": (0.1, 0.9, 0.9), "armL": (1, 0.3, 0.6), "armR": (1, 0.6, 0.1)}


def png_b64(surf) -> str:
    buf = io.BytesIO()
    surf.write_to_png(buf)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def render_frame(skin, anim, i, look=1):
    ps = SCALE if skin.name == skins.ROBOT else max(1, round(SCALE * 2 / 3))
    n = skin.canvas * ps
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
    skin.draw(cairo.Context(surf), anim, i, look, ANIM_INFO[anim][2], ps, "#5ec4b6")
    return png_b64(surf)


def render_pose(skin, pose, with_parts: bool):
    info = skin.frames[pose]
    n = skin.canvas
    s = SCALE
    bx, by, bw, bh = info["bbox"]
    pad = 2
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, (bw + 2 * pad) * s, (bh + 2 * pad) * s)
    cr = cairo.Context(surf)
    cr.scale(s, s)
    cr.translate(pad - bx, pad - by)
    cr.set_source_surface(skin.sheet, -info["index"] * n, 0)
    cr.get_source().set_filter(cairo.FILTER_NEAREST)
    cr.rectangle(bx, by, bw, bh)
    cr.fill()
    if with_parts:
        cr.set_line_width(0.35)
        for key, (x, y, w, h) in info.get("parts", {}).items():
            cr.set_source_rgba(*PART_COLORS[key], 0.95)
            cr.rectangle(x + 0.2, y + 0.2, w - 0.4, h - 0.4)
            cr.stroke()
    return png_b64(surf), f"{bw}×{bh}"


def build():
    sections, tabs, data = [], [], {}
    for k, name in enumerate(skins.available()):
        skin = skins.load(name)
        sid = f"s{k}"
        tabs.append(f'<button class="tab{" on" if k == 0 else ""}" data-t="{sid}">{name.capitalize()}</button>')
        html = [f'<section id="{sid}" class="skin{" on" if k == 0 else ""}">']

        ref = ROOT / "art" / "refs" / f"{name}.png"
        if ref.exists():
            html.append(f'<details class="ref"><summary>Referência original (ChatGPT)</summary>'
                        f'<img src="refs/{name}.png" alt="referência {name}"></details>')

        if hasattr(skin, "frames"):
            html.append('<h2>Poses <span>cada desenho extraído, sem movimento</span></h2>'
                        '<label class="chk"><input type="checkbox" class="parts-toggle"> '
                        'mostrar regiões que se mexem '
                        '<i style="--c:#39f">pé esq.</i><i style="--c:#1ee">pé dir.</i>'
                        '<i style="--c:#f59">braço esq.</i><i style="--c:#f91">braço dir.</i></label>'
                        '<div class="poses">')
            for pose in skin.frames:
                plain, size = render_pose(skin, pose, False)
                parts, _ = render_pose(skin, pose, True)
                html.append(f'<figure class="pose"><div class="stage">'
                            f'<img class="plain" src="{plain}"><img class="parts" src="{parts}"></div>'
                            f'<figcaption>{POSE_LABEL.get(pose, pose)}<small>{pose} · {size} px</small>'
                            f'</figcaption></figure>')
            html.append("</div>")

        html.append('<h2>Animações <span>como aparecem na tela; os quadros embaixo estão separados</span></h2>'
                    '<div class="anims">')
        for anim in ANIMATIONS:
            label, when, _ = ANIM_INFO[anim]
            fps, count = skin.anim_info(anim)
            frames = [render_frame(skin, anim, i) for i in range(count)]
            key = f"{sid}-{anim}"
            data[key] = {"fps": fps, "frames": frames}
            thumbs = "".join(f'<img src="{f}" title="quadro {i + 1}">' for i, f in enumerate(frames))
            html.append(f'<article class="anim"><div class="stage big"><img class="player" data-k="{key}" '
                        f'src="{frames[0]}"></div><div class="meta"><b>{label}</b><small>{when}</small>'
                        f'<small class="dim">{anim} · {count} quadros · {fps:g} fps</small></div>'
                        f'<div class="strip">{thumbs}</div></article>')
        html.append("</div></section>")
        sections.append("\n".join(html))

    page = TEMPLATE.replace("{{TABS}}", "".join(tabs)).replace("{{SECTIONS}}", "\n".join(sections))
    page = page.replace("{{DATA}}", json.dumps(data))
    OUT.write_text(page)
    print(OUT)


TEMPLATE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claude Pet: revisão de sprites</title>
<style>
:root{--bg:#14171c;--panel:#1d2128;--line:#2c323c;--ink:#e8ebef;--dim:#8b94a3;--acc:#5ec4b6;
 --check-a:#232831;--check-b:#1b1f26}
body.light{--bg:#eef0f3;--panel:#fff;--line:#d9dde3;--ink:#1b1f26;--dim:#667085;--check-a:#f1f3f6;--check-b:#e4e7ec}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);
 padding:14px 24px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
h1{font-size:17px;margin:0 12px 0 0}
.tab{background:none;border:1px solid var(--line);color:var(--ink);padding:6px 14px;border-radius:999px;cursor:pointer;font:inherit}
.tab.on{background:var(--acc);border-color:var(--acc);color:#0d1a18;font-weight:600}
.ctl{margin-left:auto;display:flex;gap:14px;align-items:center;color:var(--dim)}
.ctl button{background:var(--panel);border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:5px 10px;cursor:pointer;font:inherit}
main{padding:8px 24px 60px;max-width:1400px;margin:auto}
.skin{display:none}.skin.on{display:block}
h2{font-size:15px;margin:28px 0 12px}h2 span{color:var(--dim);font-weight:400;margin-left:8px;font-size:13px}
.stage{background:repeating-conic-gradient(var(--check-a) 0 25%,var(--check-b) 0 50%) 0 0/16px 16px;
 border-radius:10px;display:flex;align-items:center;justify-content:center;padding:10px}
img{image-rendering:pixelated}
.poses{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
.pose{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px}
.pose .stage{height:190px}.pose .parts{display:none}
.show-parts .pose .parts{display:block}.show-parts .pose .plain{display:none}
figcaption{margin-top:8px;font-weight:600}figcaption small,.meta small{display:block;color:var(--dim);font-weight:400}
.chk{display:flex;gap:10px;align-items:center;color:var(--dim);margin-bottom:10px;flex-wrap:wrap}
.chk i{font-style:normal;border-left:3px solid var(--c);padding-left:5px}
.anims{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:12px}
.anim{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;display:grid;
 grid-template-columns:150px 1fr;gap:12px;align-items:center}
.anim .stage.big{height:150px;padding:0}.anim .stage.big img{max-width:100%}
.meta b{font-size:15px}.dim{opacity:.75}
.strip{grid-column:1/-1;display:flex;gap:4px;overflow-x:auto;padding-top:4px}
.strip img{height:64px;background:var(--check-b);border-radius:6px;flex:none}
.ref summary{cursor:pointer;color:var(--dim);margin-top:16px}.ref img{max-width:100%;border-radius:10px;margin-top:8px;image-rendering:auto}
@media (max-width:600px){header,main{padding-left:16px;padding-right:16px}.ctl{margin-left:0}}
</style></head>
<body>
<header><h1>Claude Pet · revisão de sprites</h1>{{TABS}}
<div class="ctl"><button id="pause">⏸ pausar</button><button id="slow">velocidade 1x</button><button id="theme">tema claro</button></div></header>
<main>{{SECTIONS}}</main>
<script>
const DATA={{DATA}};
let paused=false,speed=1,t0=performance.now();
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{
 document.querySelectorAll('.tab,.skin').forEach(e=>e.classList.remove('on'));
 b.classList.add('on');document.getElementById(b.dataset.t).classList.add('on')});
document.querySelectorAll('.parts-toggle').forEach(c=>c.onchange=()=>c.closest('.skin').classList.toggle('show-parts',c.checked));
pause.onclick=()=>{paused=!paused;pause.textContent=paused?'▶ continuar':'⏸ pausar'};
slow.onclick=()=>{speed=speed===1?0.25:1;slow.textContent='velocidade '+(speed===1?'1x':'¼x')};
theme.onclick=()=>{document.body.classList.toggle('light');theme.textContent=document.body.classList.contains('light')?'tema escuro':'tema claro'};
const players=[...document.querySelectorAll('.player')];
let last=0;
function tick(now){
 if(!paused){last+=(now-t0)*speed}
 t0=now;
 for(const p of players){
  if(!p.closest('.skin.on'))continue;
  const d=DATA[p.dataset.k];const i=Math.floor(last/1000*d.fps)%d.frames.length;
  if(p._i!==i){p._i=i;p.src=d.frames[i]}
 }
 requestAnimationFrame(tick)}
requestAnimationFrame(tick);
</script></body></html>
"""

if __name__ == "__main__":
    build()

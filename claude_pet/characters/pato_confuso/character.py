"""Pato Pistola: patinho amarelo-claro de perfil, olhando pra direita, sempre meio perdido.

No alto da cabeça tem um cacho de cabelo preto em forma de "?". Quando o Claude Code precisa de
você, o cacho espeta reto, que nem um "!". O olho é grandão, de sobrancelha arqueada ("hã?"), e a
pupila passeia (ele olha pra trás, pra cima, pra frente, sem entender nada). Pensando, coça a
cabeça com a asa e o balão sai com um "?". Arrastado, fica tonto, com cada pupila rodando pra um lado.

Desenhado por formas, como o patinho e a lagartixa: cada pose monta máscaras (círculos, elipses,
tubos) e o contorno de 1px, a luz em cima e a sombra embaixo saem sozinhos.
"""
from __future__ import annotations

import math

from claude_pet.pixel import THOUGHT_COLORS, draw_computer, hmirror

SIDE_VIEW = True
PACE_THINKING = True
REST_SITS = True         # descansando no chão, fica sentadinho (nunca parado em pé)
HIT = (4, 3, 23, 26)
PIVOT = (15, 2)          # segurado pelo cacho (pose pendurada, de frente)
OVERLAYS = {"think": None, "think_walk": None}   # o balão (com "?") ele desenha sozinho
OVERLAY_AT = {"zzz": (1, 3), "heart": (2, 0), "check": (2, 1), "bang": (2, 1)}

ANIMS = {
    "stand": (5, 14),
    "walk": (8, 8),
    "sit": (5, 14),
    "sleep": (2, 4),
    "curious": (5, 10),
    "happy": (6, 4),
    "think": (4, 8),
    "think_walk": (6, 8),
    "work": (6, 8),
    "attention": (6, 4),
    "celebrate": (6, 2),
    "waiting": (2, 4),
    "dangle": (4, 4),
}

# ---------------------------------------------------------------- cores
OUT = "#5b3916"
HAIR = "#2d2d2d"
HAIR_HI = "#5a5a5a"
BASE = "#ffdc81"
HI = "#fff0c4"
SH = "#efb85a"
WING = "#fbcf6c"
WING_HI = "#ffe6a6"
WING_SH = "#e2a64a"
WING_OUT = "#b67f2e"
BEAK = "##f9f0e1"
BEAK_HI = "##f9f0e1"
BEAK_SH = "##f9f0e1"
MOUTH = "#3f7d6f"
FOOT = "##f9f0e1"
FOOT_FAR = "##f9f0e1"
EYE_W = "#ffffff"
PUPIL = "#191c31"
SWEAT_OUT = "#1d3a55"
SWEAT = "#7cc6f2"
SWEAT_HI = "#bfe6ff"

BODY = {BASE, HI, SH}
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
N = 30


# ---------------------------------------------------------------- máscaras
def _ellipse(m, cx, cy, rx, ry, ang=0.0):
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    r = int(max(rx, ry)) + 2
    for y in range(int(cy) - r, int(cy) + r + 1):
        for x in range(int(cx) - r, int(cx) + r + 1):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            u, v = dx * ca + dy * sa, -dx * sa + dy * ca
            if (u / rx) ** 2 + (v / ry) ** 2 <= 1:
                m.add((x, y))


def _disc(m, cx, cy, r):
    _ellipse(m, cx, cy, r, r)


def _tube(m, pts):
    for (x0, y0, r0), (x1, y1, r1) in zip(pts, pts[1:]):
        steps = max(2, int(math.hypot(x1 - x0, y1 - y0) * 3))
        for i in range(steps + 1):
            t = i / steps
            _disc(m, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r0 + (r1 - r0) * t)


def _stamp(img, mask, base=BASE, hi=HI, sh=SH, low=None, soft=None):
    """Contorno + preenchimento: borda de cima clara, borda de baixo (e abaixo de `low`) na sombra.
    `soft`: cor do contorno onde a forma passa por cima do corpo (dobra de pena, mais suave)."""
    for (x, y) in mask:
        for dx, dy in N4:
            q = (x + dx, y + dy)
            if q not in mask:
                img[q] = soft if soft and img.get(q) in BODY | {soft} else OUT
    for (x, y) in mask:
        if (x, y - 1) not in mask:
            c = hi
        elif (x, y + 1) not in mask or (low is not None and y >= low):
            c = sh
        else:
            c = base
        img[(x, y)] = c


# ---------------------------------------------------------------- partes
def _foot(img, x, y, far=False):
    """Pezinho chato, 4px pra frente, com contorno; (x, y) = calcanhar, y = linha do pé."""
    c = FOOT_FAR if far else FOOT
    for i in range(4):
        img[(x + i, y)] = c
        img[(x + i, y + 1)] = OUT
    img[(x - 1, y)] = OUT
    img[(x + 4, y)] = OUT
    img[(x + 1, y - 1)] = c                      # perninha
    img[(x, y - 1)] = OUT
    img[(x + 2, y - 1)] = OUT


# cacho do topete, a partir do alto da cabeça (0, 0 = primeiro pixel da cabeça; y negativo = pra cima)
CURLS = {
    "q": [(0, -1), (0, -2), (1, -3), (2, -4), (2, -5), (1, -6), (0, -6), (-1, -5)],
    "q_up": [(0, -1), (0, -2), (0, -3), (1, -4), (2, -5), (2, -6), (1, -7), (0, -7), (-1, -6)],
    "bang": [(0, -1), (0, -2), (0, -3), (0, -4), (0, -5), (0, -6), (0, -7)],
    "bang_sway": [(0, -1), (0, -2), (0, -3), (1, -4), (1, -5), (1, -6), (1, -7)],
    "droop": [(0, -1), (1, -2), (2, -2), (3, -1), (4, 0)],
}


def _hair(img, pts):
    """Fio de cabelo preto de 1px, sem contorno (ele mesmo já é a linha), com um brilho no alto."""
    top = min(y for (x, y) in pts)
    for (x, y) in pts:
        img[(x, y)] = HAIR_HI if y == top else HAIR


def _curl(img, ax, ay, kind):
    _hair(img, [(ax + dx, ay + dy) for dx, dy in CURLS[kind]])


def _bill(img, hx, hy, kind="closed", down=0.0):
    """Bico chato e meio caidinho saindo da frente da cabeça (centro hx, hy)."""
    bx, by = hx + 6.6, hy + 2.2 + down
    m = set()
    if kind == "open":                           # bocão aberto: "quack?!"
        _ellipse(m, bx, by - 0.8, 2.6, 1.1, 8)
        _ellipse(m, bx - 0.4, by + 1.6, 2.0, 0.9, 8)
    else:
        _ellipse(m, bx, by, 2.5, 1.3, 10)
    for (x, y) in m:
        for dx, dy in N4:
            q = (x + dx, y + dy)
            if q not in m:
                img[q] = OUT
    for (x, y) in m:
        img[(x, y)] = BEAK_HI if (x, y - 1) not in m else (BEAK_SH if (x, y + 1) not in m else BEAK)
    if kind == "open":
        ys = sorted({y for (x, y) in m})
        gap = [y for y in range(ys[0], ys[-1] + 1) if not any((x, y) in m for x in range(N))]
        for y in gap:
            xs = [x for (x, yy) in m if yy in (y - 1, y + 1)]
            for x in range(min(xs) + 1, max(xs)):
                img[(x, y)] = MOUTH
    else:                                        # risquinho da boca, torto
        y = int(by + 0.6)
        img[(int(bx) - 1, y)] = BEAK_SH
        img[(int(bx), y)] = BEAK_SH
        img[(int(bx) + 1, y + 1)] = BEAK_SH


EYE_SHAPE = (".WW.", "WWWW", "WWWW", "WWWW", ".WW.")   # branco 4x5
EYE_CELLS = {(x, y) for y, row in enumerate(EYE_SHAPE) for x, c in enumerate(row) if c == "W"}
BROWS = {                                        # sobrancelha arqueada, subindo pra frente: "hã?"
    "puzzled": ((0, -2), (1, -2), (2, -3), (3, -3)),
    "high": ((0, -3), (1, -3), (2, -4), (3, -4)),   # arregalado: sobe mais
}


def _eye(img, ex, ey, kind="open", pupil=(2, 2), brow="puzzled"):
    """Olho grandão; (ex, ey) = canto de cima do branco 4x5.

    kind: open, happy (^), closed. pupil: posição (dx, dy) da pupila 2x2 dentro do branco.
    brow: puzzled, high ou None.
    """
    p = img.__setitem__
    if kind == "happy":
        for (x, y) in ((0, 3), (1, 2), (2, 2), (3, 3)):
            p((ex + x, ey + y), PUPIL)
        return
    if kind == "closed":
        for (x, y) in ((0, 3), (1, 3), (2, 3), (3, 2)):    # risquinho, meio torto
            p((ex + x, ey + y), PUPIL)
        return
    for (x, y) in EYE_CELLS:
        for dx, dy in N4:
            if (x + dx, y + dy) not in EYE_CELLS:
                p((ex + x + dx, ey + y + dy), OUT)
    for (x, y) in EYE_CELLS:
        p((ex + x, ey + y), EYE_W)
    px, py = pupil
    for dx in (0, 1):
        for dy in (0, 1):
            if (px + dx, py + dy) in EYE_CELLS:
                p((ex + px + dx, ey + py + dy), PUPIL)
    for (x, y) in BROWS.get(brow, ()):
        p((ex + x, ey + y), OUT)


def _sweat(img, x, y):
    """Gotinha de suor (x, y = ponta de cima)."""
    for (dx, dy, c) in ((0, 0, SWEAT_OUT), (-1, 1, SWEAT_OUT), (0, 1, SWEAT_HI), (1, 1, SWEAT_OUT),
                        (-1, 2, SWEAT_OUT), (0, 2, SWEAT), (1, 2, SWEAT_OUT), (0, 3, SWEAT_OUT)):
        img[(x + dx, y + dy)] = c


def _wing(img, kind, cx, cy, frame=0, head=(0.0, 0.0)):
    """Asinha por cima do corpo. kind: rest (caída do lado), fold (dobrada, deitado), up (levantada),
    scratch (coçando a cabeça), type (no teclado)."""
    m = set()
    if kind == "rest":       # de pé: asinha saindo do ombro em diagonal, com a pontinha na frente da barriga
        sx, sy = cx + 0.2, cy - 3.0
        tx, ty = cx + 5.4, cy + 0.5
        ang = math.degrees(math.atan2(ty - sy, tx - sx))
        _ellipse(m, (sx + tx) / 2, (sy + ty) / 2, math.hypot(tx - sx, ty - sy) / 2 + 0.9, 2.0, ang)
        _disc(m, tx + 0.2, ty + 0.1, 1.1)               # mãozinha
    elif kind == "fold":     # deitado: asinha dobrada na horizontal
        _ellipse(m, cx, cy, 3.6, 2.0, -12)
        _disc(m, cx - 3.2, cy - 1.0, 0.8)               # pontinha virada pra trás
    elif kind == "up":       # levantada, aberta em leque ("ué?!")
        _ellipse(m, cx - 1.5, cy - 3.2, 3.6, 1.9, -58)
        _disc(m, cx + 0.5, cy - 0.5, 1.6)
    elif kind == "scratch":  # asinha levantada do ombro até o alto da cabeça, coçando (sobe e desce)
        hx, hy = head
        sx, sy = cx + 1.2, cy - 1.2
        tx, ty = hx - 2.4, hy - 4.4 - (frame % 2) * 0.9
        ang = math.degrees(math.atan2(ty - sy, tx - sx))
        _ellipse(m, (sx + tx) / 2, (sy + ty) / 2, math.hypot(tx - sx, ty - sy) / 2 + 0.8, 2.0, ang)
        _disc(m, tx - 0.6, ty + 0.4, 1.3)        # pontinha das penas, na cabeça
    elif kind == "type":     # asinha esticada pra frente até o teclado, batucando
        _ellipse(m, cx, cy - (1 if frame % 2 else 0), 3.2, 1.5, -12 if frame % 2 else -4)
    _stamp(img, m, WING, WING_HI, WING_SH, soft=None if kind == "type" else WING_OUT)


# ---------------------------------------------------------------- pose base (de perfil)
def _duck(p):
    img = {}
    dx, dy = p.get("dx", 0), p.get("dy", 0)
    bx, by, brx, bry = p.get("body", BODY_AT)
    hx, hy = p.get("head", HEAD_AT)
    hx += p.get("head_dx", 0)
    hy += p.get("head_dy", 0)
    bx, by, hx, hy = bx + dx, by + dy, hx + dx, hy + dy
    hr = p.get("hr", 5.8)

    feet = p.get("feet", "stand")
    fy = 28
    if feet == "stand":
        _foot(img, 9 + dx, fy, far=True)
    elif feet.startswith("walk"):
        ph = int(feet[-1])
        s = (1, 0, -1, 0)[ph]
        _foot(img, 10 - s + dx, fy - (1 if ph == 2 else 0), far=True)

    m = set()
    _ellipse(m, bx, by, brx, bry, p.get("tilt", 0))
    _disc(m, hx, hy, hr)
    _tube(m, [(hx - 1.2, hy + 3.0, 3.4), (bx + 0.8, by - bry + 2.6, 3.8)])   # pescoço curto e gordinho
    tail = p.get("tail", 0)
    if p.get("lying"):       # deitado: rabinho pra cima, atrás
        _tube(m, [(bx - brx + 2.5, by - 0.8, 1.8), (bx - brx + 0.8, by - 2.6 - tail, 1.0),
                  (bx - brx + 0.2, by - 4.2 - tail, 0.5)])
    else:                    # de pé: rabinho embaixo, atrás, arrebitado
        _tube(m, [(bx - brx + 2.0, by + 2.0, 1.8), (bx - brx + 0.2, by + 2.4 - tail, 1.0),
                  (bx - brx - 0.8, by + 1.8 - 1.5 * tail, 0.5)])
    _stamp(img, m)

    if feet == "stand":
        _foot(img, 14 + dx, fy)
    elif feet.startswith("walk"):
        ph = int(feet[-1])
        s = (1, 0, -1, 0)[ph]
        _foot(img, 14 + s + dx, fy - (1 if ph == 0 else 0))
    elif feet == "toes":                          # sentadinho: só as pontinhas aparecem
        for x in (int(bx) + 3, int(bx) + 4, int(bx) + 5):
            img[(x, 28)] = FOOT
        img[(int(bx) + 6, 28)] = OUT

    curl = p.get("curl", "q")
    if curl != "none":
        ax = int(hx) - 1
        ay = min(y for (x, y) in m if x == ax)
        _curl(img, ax, ay, curl)

    wing = p.get("wing", "rest")
    if wing != "none":
        _wing(img, wing, bx - 0.5 + p.get("wing_dx", 0), by + 0.2 + p.get("wing_dy", 0), p.get("frame", 0),
              (hx, hy))

    _bill(img, hx, hy, p.get("mouth", "closed"), p.get("bill_down", 0))
    _eye(img, int(hx), int(hy) - 2, p.get("eye", "open"), p.get("pupil", (2, 2)), p.get("brow", "puzzled"))
    if p.get("sweat"):
        _sweat(img, int(hx - hr) - 1, int(hy) - 4)
    return img


BODY_AT = (13.8, 22.4, 5.8, 5.9)      # de pé: corpo em pé, cabeça em cima
HEAD_AT = (17.2, 14.0)
SIT = {"body": (13.8, 23.4, 6.3, 4.9), "head": (17.0, 14.8), "feet": "toes"}

# andar cambaleando: passos irregulares (o corpo adianta e atrasa 1px), tropeça pra frente,
# corrige demais pra trás e se reequilibra; a pupila não para quieta.
# (pé, sobe, inclinação, cabeça dx, cabeça dy, corpo dx, pupila)
STAGGER = [
    (0, 0, -3, 0.0, 0.0, 0, (2, 2)),
    (1, -1, 3, 0.5, 0.0, 0, (2, 1)),
    (2, 0, 9, 1.4, 0.6, 1, (1, 1)),     # tropeço: tomba pra frente, cabeça vai junto
    (3, -1, 5, 0.8, 0.3, 1, (0, 2)),
    (0, 0, -7, -1.0, -0.3, 0, (1, 2)),  # corrige demais: joga o corpo pra trás
    (1, -1, -4, -0.6, 0.0, -1, (2, 2)),
    (2, 0, 1, 0.0, 0.0, -1, (2, 1)),
    (3, -1, -1, 0.0, 0.0, 0, (1, 2)),
]

# pupila passeando: frente, pra trás (sem entender), pra cima, frente de novo
LOOK_AROUND = {4: (0, 2), 5: (0, 2), 6: (0, 2), 9: (1, 1), 10: (2, 1)}


# ---------------------------------------------------------------- pendurado, de frente
def _dangle(frame):
    img = {}
    sw = (0, 0.6, 0, -0.6)[frame % 4]
    for k, lx in enumerate((12, 18)):            # perninhas caídas com os pezinhos pendurados
        n = 2 + ((frame + k) % 2)
        x = int(lx + sw)
        for y in range(26, 26 + n):
            img[(x, y)] = FOOT
            img[(x - 1, y)] = OUT
            img[(x + 1, y)] = OUT
        fy = 26 + n
        for ddx in (-1, 0, 1):
            img[(x + ddx, fy)] = FOOT_FAR if ddx else FOOT
            img[(x + ddx, fy + 1)] = OUT
        img[(x - 2, fy)] = OUT
        img[(x + 2, fy)] = OUT
    m = set()
    _ellipse(m, 15 + sw * 0.5, 21.0, 5.6, 5.0)
    _ellipse(m, 15 + sw * 0.5, 23.0, 6.0, 3.0)
    _disc(m, 15, 11.0, 6.0)
    _stamp(img, m, low=24)
    # cacho esticado (é por ele que o mouse segura)
    ay = min(y for (x, y) in m if x == 15)
    _hair(img, [(15, y) for y in range(1, ay)] + [(16, 1), (17, 2)])
    # asinhas moles caídas dos lados
    for side in (-1, 1):
        w = set()
        cx = 15 + side * 5.8 + sw * 0.5
        _tube(w, [(cx, 17.6, 1.2), (cx + side * 0.6, 21.6, 0.8)])
        _stamp(img, w, WING, WING_HI, WING_SH)
    # tontinho: cada pupila rodando pra um lado, sobrancelhas lá em cima; e o bico pequeno
    roll = ((1, 0), (2, 1), (1, 3), (0, 1))
    _eye(img, 10, 9, pupil=roll[frame % 4])
    _eye(img, 17, 9, pupil=roll[(frame + 2) % 4])
    bm = set()
    _ellipse(bm, 15.5, 15.5, 2.4, 1.4)
    for (x, y) in bm:
        for ddx, ddy in N4:
            if (x + ddx, y + ddy) not in bm:
                img[(x + ddx, y + ddy)] = OUT
    for (x, y) in bm:
        img[(x, y)] = BEAK_HI if (x, y - 1) not in bm else BEAK
    if frame % 4 in (1, 2):
        _sweat(img, 23, 4)
    return img


# ---------------------------------------------------------------- poses
def _pose(anim, f, look):
    if anim in ("stand", "sit"):
        base = dict(SIT) if anim == "sit" else {}
        return dict(base, pupil=LOOK_AROUND.get(f, (2, 2)), eye="closed" if f == 13 else "open",
                    head_dx=-0.5 if f in (4, 5, 6) else 0, curl="q_up" if f in (9, 10) else "q",
                    tail=0.6 if 5 <= f <= 6 else 0)
    if anim == "walk":
        pe, dy, tilt, hdx, hdy, ddx, pupil = STAGGER[f]
        return {"feet": f"walk{pe}", "dy": dy, "tilt": tilt, "head_dx": hdx, "head_dy": hdy, "dx": ddx,
                "pupil": pupil, "brow": "high" if f in (2, 3) else "puzzled", "sweat": f in (3, 4),
                "curl": "q_up" if dy == 0 else "q", "tail": 0.9 if tilt < -4 else 0}
    if anim == "sleep":
        # aninhado: pãozinho redondo, cabeça recolhida em cima do peito, cacho caído pra frente
        b = 0.5 if f >= 2 else 0.0
        return {"body": (13.0, 24.6 - b, 8.0, 4.0 + b), "head": (18.0, 19.6), "hr": 5.0, "feet": "none",
                "eye": "closed", "curl": "droop", "wing": "fold", "wing_dx": -0.5, "lying": True}
    if anim == "curious":
        side = (0, 2) if look < 0 else (2, 1)
        return {"head": (19.2, 13.4), "eye": "closed" if f == 9 else "open", "brow": "high",
                "pupil": side if (f // 3) % 2 == 0 else (1, 1), "curl": "q_up" if f % 2 else "q"}
    if anim == "happy":
        return {"eye": "happy", "wing": "up" if f % 2 else "rest", "dy": -(f % 2), "tail": 0.8 * (f % 2),
                "curl": "q_up" if f % 2 else "q"}
    if anim == "think":
        return dict(SIT, pupil=(0, 0), brow="high", wing="scratch", frame=f, sweat=f % 4 in (2, 3))
    if anim == "think_walk":
        g = f % 4
        return {"feet": f"walk{g}", "dy": -1 if g in (1, 3) else 0, "pupil": (1, 0),
                "curl": "q_up" if g in (0, 2) else "q", "tilt": (-5, 0, 5, 0)[g]}
    if anim == "attention":
        return {"pupil": (1, 1), "brow": "high", "mouth": "open" if f % 2 == 0 else "closed",
                "wing": "up" if f % 2 == 0 else "rest", "dy": -(f % 2), "feet": "stand",
                "curl": "bang" if f % 2 == 0 else "bang_sway"}
    if anim == "celebrate":
        return {"eye": "happy", "mouth": "open", "wing": "up", "dy": -2 if f else 0, "tail": 1.0,
                "feet": "walk0" if f else "stand"}
    if anim == "waiting":
        return dict(SIT, eye="happy", tail=0.8 if f == 3 else 0)
    if anim == "work":
        # sentado na frente do computador; de vez em quando para e coça a cabeça olhando a tela
        puzzled = f >= 6
        return {"body": (8.6, 23.2, 5.2, 5.4), "head": (10.8, 15.0), "hr": 5.2, "feet": "none",
                "wing": "scratch" if puzzled else "type", "wing_dx": 0 if puzzled else 8.3,
                "wing_dy": 0 if puzzled else -1.8, "frame": f, "brow": "high" if puzzled else "puzzled",
                "pupil": (2, 0) if puzzled else (2, 2), "sweat": f == 7, "curl": "q_up" if f == 7 else "q"}
    return {}


QCLOUD = [
    "..OOOOO..",
    ".OWWWWWO.",
    "OWWWWWWWO",
    "OWWWWWWWO",
    "OWWWWWWWO",
    "OWWWWWWGO",
    ".OGWWWGO.",
    "..OOOOO..",
]
QMARK = ["##.", "..#", ".#.", "...", ".#."]


def _thought(pen, f, img, hx):
    """Balão saindo de trás da cabeça: bolinha 1x1, 2x2 e a nuvem com um "?" que pula."""
    col = int(hx) - 5
    top = min((y for (x, y) in img if x == col), default=10)
    step = f % 4
    o, w = THOUGHT_COLORS["O"], THOUGHT_COLORS["W"]

    def bub(x, y, s):
        pen.px(x, y - 1, s, 1, o)
        pen.px(x, y + s, s, 1, o)
        pen.px(x - 1, y, 1, s, o)
        pen.px(x + s, y, 1, s, o)
        pen.px(x, y, s, s, w)

    bub(col, top - 2, 1)
    if step >= 1:
        bub(col - 3, top - 5, 2)
    cx, cy = max(0, col - 12), max(0, top - 13)
    pen.sprite(cx, cy, QCLOUD, THOUGHT_COLORS)
    if step >= 2:   # o "?" aparece e fica pulando
        glyph = hmirror(QMARK) if pen.flip else QMARK   # espelhado duas vezes = continua "?"
        pen.sprite(cx + 3, cy + 1 + (step == 3), [r.replace("#", "d") for r in glyph], THOUGHT_COLORS)


_CACHE: dict = {}


def _image(anim, frame, look):
    key = (anim, frame, look)
    img = _CACHE.get(key)
    if img is None:
        if anim == "dangle":
            img = _dangle(frame)
        else:
            img = _duck(_pose(anim, frame, look))
        img = {k: v for k, v in img.items() if 0 <= k[0] < N and 0 <= k[1] < N}
        if len(_CACHE) > 600:
            _CACHE.clear()
        _CACHE[key] = img
    return img


def _blit(pen, img):
    for y in range(N):
        x = 0
        while x < N:
            c = img.get((x, y))
            if c is None:
                x += 1
                continue
            k = x
            while k < N and img.get((k, y)) == c:
                k += 1
            pen.px(x, y, k - x, 1, c)
            x = k


WOOD_OUT = "#4a2c1d"
WOOD = "#c98f5a"
WOOD_HI = "#e0ad78"
WOOD_SH = "#a06a3d"


def _table(pen, x0, top, w):
    pen.px(x0, top - 1, w, 1, WOOD_OUT)
    pen.px(x0 - 1, top, 1, 2, WOOD_OUT)
    pen.px(x0 + w, top, 1, 2, WOOD_OUT)
    pen.px(x0, top, w, 1, WOOD_HI)
    pen.px(x0, top + 1, w, 1, WOOD_SH)
    pen.px(x0, top + 2, w, 1, WOOD_OUT)
    for lx in (x0 + 1, x0 + w - 3):
        pen.px(lx, top + 3, 3, 29 - (top + 3), WOOD_OUT)
        pen.px(lx + 1, top + 3, 1, 29 - (top + 3), WOOD)
        pen.px(lx, 29, 3, 1, WOOD_OUT)


def render(pen, anim, frame, look, light):
    if anim == "work":           # mesinha + computador atrás; o pato sentado na frente
        _table(pen, 17, 25, 12)
        draw_computer(pen, 20, 15, light, frame, keyboard_at=(17, 22))
    img = _image(anim, frame, look)
    _blit(pen, img)
    if anim in ("think", "think_walk"):
        p = _pose(anim, frame, look)
        hx = p.get("head", (18.6, 13.4))[0] + p.get("dx", 0)
        _thought(pen, frame if anim == "think" else frame // 2, img, hx)

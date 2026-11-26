"""Janela de Configurações: galeria de personagens animados, nome, idioma e modo troll.

Feita em Tk pra ser a mesma no Linux e no Windows, e roda num processo próprio
(`python -m claude_pet.settings`, aberto pelo menu do pet). Cada mudança é gravada no config.json
na hora; o pet percebe o arquivo mudar e aplica sozinho.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
import tkinter.font as tkfont

from . import __version__, i18n, raster, skins
from .config import Config
from .i18n import t

WINDOWS = os.name == "nt"

# cores (tema escuro, combinando com o pixel art)
BG = "#17191f"
PANEL = "#1f2229"
CARD = "#262a33"
CARD_HOVER = "#2f3440"
LINE = "#343946"
TEXT = "#eceae6"
MUTED = "#9299a6"
ACCENT = "#5ec4b6"
ACCENT_INK = "#0f2b27"

COLS = 4
PREVIEW_CYCLE = ("stand", "walk", "happy", "think", "work", "celebrate", "sleep")
CYCLE_SECONDS = 2.6


def _font_family(root) -> str:
    have = set(tkfont.families(root))
    for name in ("Segoe UI", "Inter", "Cantarell", "Ubuntu", "Noto Sans", "DejaVu Sans"):
        if name in have:
            return name
    return "TkDefaultFont"


def round_rect(c: tk.Canvas, x0, y0, x1, y1, r, **kw):
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
           x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


class Sprites:
    """Quadros dos personagens já no formato do PhotoImage.put, guardados em cache."""

    def __init__(self, body_color: str):
        self.body_color = body_color
        self.skins: dict = {}
        self.cache: dict = {}

    def skin(self, name: str):
        if name not in self.skins:
            self.skins[name] = skins.load(name)
        return self.skins[name]

    def frame_count(self, name: str, anim: str) -> tuple[float, int]:
        return self.skin(name).anim_info(anim)

    def data(self, name: str, anim: str, frame: int, px: int, bg: str) -> str:
        key = (name, anim, frame, px, bg)
        got = self.cache.get(key)
        if got is None:
            skin = self.skin(name)
            scale = px
            n = skin.canvas * scale
            pixels = raster.render(skin, anim, frame, 0, "idle", scale, self.body_color)
            got = " ".join("{" + " ".join(c or bg for c in pixels[y * n:(y + 1) * n]) + "}" for y in range(n))
            if len(self.cache) > 1500:
                self.cache.clear()
            self.cache[key] = got
        return got


class CharCard:
    """Card da galeria: personagem animado + nome. Parado ele respira; com o mouse em cima, comemora."""

    W, H = 132, 150

    def __init__(self, app: "SettingsApp", parent, name: str):
        self.app, self.name = app, name
        s = app.ui
        self.w, self.h = int(self.W * s), int(self.H * s)
        self.px = app.sprite_px
        self.c = tk.Canvas(parent, width=self.w, height=self.h, bg=PANEL, highlightthickness=0, bd=0,
                           cursor="hand2")
        self.hover = False
        self.bg_item = round_rect(self.c, 1, 1, self.w - 1, self.h - 1, int(16 * s), fill=CARD, outline=CARD, width=2)
        side = 30 * self.px
        self.photo = tk.PhotoImage(width=side, height=side)
        self.c.create_image(self.w // 2, int(10 * s) + side // 2, image=self.photo)
        self.c.create_text(self.w // 2, self.h - int(20 * s), text=skins.label(name), fill=TEXT,
                           font=app.font_card, width=self.w - 12, justify="center")
        self.badge = []
        self.c.bind("<Enter>", lambda _e: self._set_hover(True))
        self.c.bind("<Leave>", lambda _e: self._set_hover(False))
        self.c.bind("<Button-1>", lambda _e: app.choose_skin(name))
        self.last = None

    def _set_hover(self, on: bool) -> None:
        self.hover = on
        self.app.hover_started = self.app.now()
        self.refresh()

    @property
    def selected(self) -> bool:
        return self.app.cfg.skin == self.name

    def bg(self) -> str:
        return CARD_HOVER if self.hover else CARD

    def refresh(self) -> None:
        sel = self.selected
        self.c.itemconfigure(self.bg_item, fill=self.bg(), outline=ACCENT if sel else self.bg())
        for item in self.badge:
            self.c.delete(item)
        self.badge = []
        if sel:
            s = self.app.ui
            r, cx, cy = int(11 * s), self.w - int(18 * s), int(18 * s)
            self.badge.append(self.c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=ACCENT, outline=ACCENT))
            self.badge.append(self.c.create_text(cx, cy, text="✓", fill=ACCENT_INK, font=self.app.font_badge))
        self.last = None
        self.animate(self.app.now())

    def animate(self, now: float) -> None:
        anim = "happy" if self.hover else "stand"
        fps, count = self.app.sprites.frame_count(self.name, anim)
        t0 = self.app.hover_started if self.hover else 0.0
        frame = int((now - t0) * fps) % count
        key = (anim, frame, self.bg())
        if key == self.last:
            return
        self.last = key
        self.photo.put(self.app.sprites.data(self.name, anim, frame, self.px, self.bg()), to=(0, 0))


class Segmented:
    """Botões lado a lado, um escolhido (idioma)."""

    def __init__(self, app: "SettingsApp", parent, options, chosen, on_pick):
        s = app.ui
        self.app, self.options, self.chosen, self.on_pick = app, options, chosen, on_pick
        self.h = int(34 * s)
        self.w = int(236 * s)
        self.c = tk.Canvas(parent, width=self.w, height=self.h, bg=PANEL, highlightthickness=0, bd=0, cursor="hand2")
        self.c.bind("<Button-1>", self._click)
        self.draw()

    def draw(self) -> None:
        c, s = self.c, self.app.ui
        c.delete("all")
        round_rect(c, 1, 1, self.w - 1, self.h - 1, int(12 * s), fill=CARD, outline=LINE)
        seg = (self.w - 8) / len(self.options)
        for i, (code, label) in enumerate(self.options):
            x0 = 4 + i * seg
            if code == self.chosen:
                round_rect(c, x0, 4, x0 + seg, self.h - 4, int(9 * s), fill=ACCENT, outline=ACCENT)
            c.create_text(x0 + seg / 2, self.h / 2, text=label, font=self.app.font_small,
                          fill=ACCENT_INK if code == self.chosen else TEXT)

    def _click(self, ev) -> None:
        seg = (self.w - 8) / len(self.options)
        i = min(len(self.options) - 1, max(0, int((ev.x - 4) // seg)))
        code = self.options[i][0]
        if code != self.chosen:
            self.chosen = code
            self.draw()
            self.on_pick(code)


class Toggle:
    """Interruptor liga/desliga."""

    def __init__(self, app: "SettingsApp", parent, on: bool, on_change):
        s = app.ui
        self.app, self.on, self.on_change = app, on, on_change
        self.w, self.h = int(48 * s), int(26 * s)
        self.c = tk.Canvas(parent, width=self.w, height=self.h, bg=PANEL, highlightthickness=0, bd=0, cursor="hand2")
        self.c.bind("<Button-1>", lambda _e: self.flip())
        self.draw()

    def draw(self) -> None:
        c, h, w = self.c, self.h, self.w
        c.delete("all")
        track = ACCENT if self.on else LINE
        round_rect(c, 1, 1, w - 1, h - 1, h // 2, fill=track, outline=track)
        r = h // 2 - 4
        cx = w - h // 2 if self.on else h // 2
        c.create_oval(cx - r, h // 2 - r, cx + r, h // 2 + r, fill=TEXT if not self.on else "#ffffff", outline="")

    def flip(self) -> None:
        self.on = not self.on
        self.draw()
        self.on_change(self.on)


class SettingsApp:
    def __init__(self):
        self.cfg = Config.load()
        i18n.set_language(self.cfg.language)
        self.root = tk.Tk()
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        try:
            self.ui = max(1.0, self.root.winfo_fpixels("1i") / 96)
        except tk.TclError:
            self.ui = 1.0
        self.sprite_px = max(3, round(3 * self.ui))
        family = _font_family(self.root)
        s = self.ui
        self.font_title = tkfont.Font(family=family, size=17, weight="bold")
        self.font_h = tkfont.Font(family=family, size=11, weight="bold")
        self.font_body = tkfont.Font(family=family, size=10)
        self.font_small = tkfont.Font(family=family, size=9)
        self.font_card = tkfont.Font(family=family, size=9, weight="bold")
        self.font_badge = tkfont.Font(family=family, size=9, weight="bold")
        self.font_name = tkfont.Font(family=family, size=14, weight="bold")
        self.sprites = Sprites(self.cfg.body_color)
        self.cards: list[CharCard] = []
        self.hover_started = 0.0
        self._name_job = None
        self.big_px = max(5, round(5 * s))
        self.started = self.now()
        self.build()
        self._center()
        self.tick()

    @staticmethod
    def now() -> float:
        import time
        return time.monotonic()

    # ------------------------------------------------------------ montagem
    def build(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()
        self.root.title(t("settings.title") + " · Claude Pet")
        s = self.ui
        pad = int(22 * s)
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=pad, pady=(int(18 * s), pad))

        head = tk.Frame(wrap, bg=BG)
        head.pack(fill="x", pady=(0, int(14 * s)))
        tk.Label(head, text=t("settings.title"), font=self.font_title, fg=TEXT, bg=BG).pack(side="left")
        tk.Label(head, text=f"Claude Pet {__version__}", font=self.font_small, fg=MUTED, bg=BG).pack(
            side="left", padx=(int(10 * s), 0), pady=(int(6 * s), 0))

        body = tk.Frame(wrap, bg=BG)
        body.pack(fill="both", expand=True)
        left = self._panel(body)
        left.pack(side="left", fill="y", padx=(0, int(16 * s)))
        right = self._panel(body)
        right.pack(side="left", fill="both", expand=True)
        self._build_left(left.inner)
        self._build_right(right.inner)

        foot = tk.Frame(wrap, bg=BG)
        foot.pack(fill="x", pady=(int(14 * s), 0))
        tk.Label(foot, text=t("settings.live"), font=self.font_small, fg=MUTED, bg=BG).pack(side="left")
        btn = tk.Label(foot, text=t("settings.close"), font=self.font_h, fg=ACCENT_INK, bg=ACCENT,
                       padx=int(18 * s), pady=int(6 * s), cursor="hand2")
        btn.pack(side="right")
        btn.bind("<Button-1>", lambda _e: self.root.destroy())
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    def _panel(self, parent):
        s = self.ui
        outer = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        outer.inner = tk.Frame(outer, bg=PANEL)
        outer.inner.pack(fill="both", expand=True, padx=int(18 * s), pady=int(16 * s))
        return outer

    def _section(self, parent, title: str, hint: str = "", top: int = 18, wrap: int = 236):
        s = self.ui
        tk.Label(parent, text=title, font=self.font_h, fg=TEXT, bg=PANEL, anchor="w").pack(
            fill="x", pady=(int(top * s), 0))
        if hint:
            tk.Label(parent, text=hint, font=self.font_small, fg=MUTED, bg=PANEL, anchor="w", justify="left",
                     wraplength=int(wrap * s)).pack(fill="x", pady=(int(2 * s), 0))

    def _build_left(self, p) -> None:
        s = self.ui
        side = 30 * self.big_px
        box = tk.Canvas(p, width=int(236 * s), height=side + int(70 * s), bg=PANEL, highlightthickness=0, bd=0)
        box.pack()
        w = int(236 * s)
        round_rect(box, 1, 1, w - 1, side + int(68 * s), int(18 * s), fill=CARD, outline=CARD)
        self.big = tk.PhotoImage(width=side, height=side)
        box.create_image(w // 2, int(6 * s) + side // 2, image=self.big)
        self.big_name = box.create_text(w // 2, side + int(22 * s), text=self.cfg.display_name, fill=TEXT,
                                        font=self.font_name)
        self.big_state = box.create_text(w // 2, side + int(46 * s), text="", fill=MUTED, font=self.font_small)
        self.big_canvas = box
        self.big_last = None

        self._section(p, t("settings.name"), t("settings.name_hint"))
        frame = tk.Frame(p, bg=CARD, highlightthickness=1, highlightbackground=LINE, highlightcolor=ACCENT)
        frame.pack(fill="x", pady=(int(8 * s), 0))
        self.name_var = tk.StringVar(value=self.cfg.pet_name or "")
        entry = tk.Entry(frame, textvariable=self.name_var, font=self.font_body, bg=CARD, fg=TEXT, bd=0,
                         insertbackground=TEXT, relief="flat", highlightthickness=0)
        entry.pack(fill="x", padx=int(10 * s), pady=int(8 * s))
        self.name_var.trace_add("write", lambda *_: self._name_changed())

        self._section(p, t("settings.language"))
        langs = [("auto", t("settings.lang_auto"))] + [(c, i18n.LANGUAGE_NAMES[c]) for c in i18n.LANGUAGES]
        seg = Segmented(self, p, langs, (self.cfg.language or "auto").lower(), self.choose_language)
        seg.c.pack(anchor="w", pady=(int(8 * s), 0))

        self._section(p, t("settings.fun"))
        row = tk.Frame(p, bg=PANEL)
        row.pack(fill="x", pady=(int(8 * s), 0))
        text = tk.Frame(row, bg=PANEL)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=t("settings.troll"), font=self.font_body, fg=TEXT, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(text, text=t("settings.troll_hint"), font=self.font_small, fg=MUTED, bg=PANEL, anchor="w",
                 justify="left", wraplength=int(170 * s)).pack(fill="x")
        Toggle(self, row, bool(self.cfg.troll), self.choose_troll).c.pack(side="right", anchor="n")

    def _build_right(self, p) -> None:
        s = self.ui
        self._section(p, t("settings.character"), t("settings.character_hint"), top=0, wrap=560)
        grid = tk.Frame(p, bg=PANEL)
        grid.pack(anchor="nw", pady=(int(12 * s), 0))
        self.cards = []
        gap = int(10 * s)
        for i, name in enumerate(skins.available()):
            card = CharCard(self, grid, name)
            card.c.grid(row=i // COLS, column=i % COLS, padx=(0, gap if i % COLS < COLS - 1 else 0),
                        pady=(0, gap))
            self.cards.append(card)
        for card in self.cards:
            card.refresh()

    def _center(self) -> None:
        self.root.update_idletasks()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        self.root.attributes("-topmost", True)
        self.root.after(600, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

    # ------------------------------------------------------------ ações (gravam na hora)
    def _save(self, key: str, value) -> None:
        fresh = Config.load()          # o pet pode ter mudado alguma outra chave enquanto a janela estava aberta
        fresh.save_key(key, value)
        setattr(self.cfg, key, value)

    def choose_skin(self, name: str) -> None:
        if name == self.cfg.skin:
            return
        self._save("skin", name)
        self.big_last = None
        self.started = self.now()
        for card in self.cards:
            card.refresh()

    def choose_language(self, code: str) -> None:
        self._save("language", code)
        i18n.set_language(code)
        self.root.after(80, self.build)   # textos no idioma novo

    def choose_troll(self, on: bool) -> None:
        self._save("troll", on)

    def _name_changed(self) -> None:
        name = self.name_var.get()[:24]
        self.cfg.pet_name = name
        self.big_canvas.itemconfigure(self.big_name, text=self.cfg.display_name)
        if self._name_job:
            self.root.after_cancel(self._name_job)
        self._name_job = self.root.after(400, lambda: self._save("pet_name", name.strip()))

    # ------------------------------------------------------------ animação
    def tick(self) -> None:
        now = self.now()
        try:
            for card in self.cards:
                card.animate(now)
            self._animate_big(now)
        except tk.TclError:
            return
        self.root.after(60, self.tick)

    def _animate_big(self, now: float) -> None:
        el = now - self.started
        anim = PREVIEW_CYCLE[int(el / CYCLE_SECONDS) % len(PREVIEW_CYCLE)]
        fps, count = self.sprites.frame_count(self.cfg.skin, anim)
        frame = int(el * fps) % count
        key = (self.cfg.skin, anim, frame)
        if key == self.big_last:
            return
        self.big_last = key
        self.big.put(self.sprites.data(self.cfg.skin, anim, frame, self.big_px, CARD), to=(0, 0))
        self.big_canvas.itemconfigure(self.big_state, text=t(f"settings.anim.{anim}"))

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    if WINDOWS:
        try:
            from . import winsys
            winsys.set_dpi_aware()
        except Exception:
            pass
    SettingsApp().run()


if __name__ == "__main__":
    sys.exit(main())

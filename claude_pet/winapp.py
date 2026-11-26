"""Janelas em Tk (o que o Windows usa no lugar do GTK): o pet, o balão, o menu e a janelinha do nome.

Tk vem junto com o Python do python.org, então no Windows não precisa instalar mais nada.
A transparência é por "cor-chave": os pixels nessa cor somem e o clique atravessa por eles,
então só o desenho do pet recebe o mouse. O desenho em si é o mesmo do Linux (raster.py).
Também roda no Linux pra desenvolver (sem transparência; o fundo fica na cor-chave).
"""
from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import font as tkfont

from . import bubble, raster, skins
from .character import Frame, Pet, Rect
from .config import Config
from .core import PetCore
from .i18n import t
from .state import StateStore

WINDOWS = os.name == "nt"
if WINDOWS:
    from . import winsys

KEY = "#ff00fe"   # cor-chave da transparência (nenhum personagem usa)


def _hex(color) -> str:
    return "#%02x%02x%02x" % tuple(round(c * 255) for c in color)


def _borderless(win: tk.Misc, click_through: bool = False) -> None:
    win.overrideredirect(True)
    win.configure(bg=KEY)
    win.attributes("-topmost", True)
    try:
        win.attributes("-transparentcolor", KEY)
    except tk.TclError:   # só existe no Windows
        pass
    if WINDOWS:
        win.update_idletasks()
        winsys.style_window(win.winfo_id(), click_through)


class TkBubble:
    """Balão de fala; o mouse atravessa ele (WS_EX_TRANSPARENT)."""

    def __init__(self, root: tk.Tk):
        self.win = tk.Toplevel(root)
        _borderless(self.win, click_through=True)
        self.canvas = tk.Canvas(self.win, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.font = tkfont.Font(family="Segoe UI" if WINDOWS else "DejaVu Sans", size=8, weight="bold")
        self.key = None
        self.rect = None   # (x, y, w, h) na tela quando visível
        self.size = (0, 0)
        self.tail = (0, True)
        self.win.withdraw()

    def hide(self) -> None:
        if self.key is not None:
            self.win.withdraw()
        self.key = None
        self.rect = None

    def show_text(self, text: str, anchor_x: int, anchor_y: int, area: Rect) -> None:
        if not text:
            self.hide()
            return
        lines = text.split("\n")
        tw = max(self.font.measure(line) for line in lines)
        th = self.font.metrics("linespace") * len(lines)
        w, h = bubble.box_size(tw, th)
        x = min(max(anchor_x - w // 2, area.x), area.x + area.w - w)
        y = anchor_y - h
        tail_down = y >= area.y
        if not tail_down:
            y = anchor_y + 4
        tail = (anchor_x - x, tail_down)
        if text != self.key or tail != self.tail or (w, h) != self.size:
            self.key, self.tail, self.size = text, tail, (w, h)
            self._draw(text, w, h, *tail)
        self.win.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
        self.rect = (int(x), int(y), w, h)
        if self.win.state() == "withdrawn":
            self.win.deiconify()
            self.win.lift()

    def _draw(self, text: str, w: int, h: int, tail_x: int, tail_down: bool) -> None:
        c = self.canvas
        c.delete("all")
        c.configure(width=w, height=h)
        for x, y, rw, rh, color in bubble.shape(w, h, tail_x, tail_down):
            c.create_rectangle(x, y, x + rw, y + rh, fill=_hex(color), outline="")
        tx, ty = bubble.text_origin(tail_down)
        c.create_text(w / 2, ty, text=text, anchor="n", justify="center", font=self.font, fill=_hex(bubble.INK))


class TkPetApp(PetCore):
    def __init__(self, cfg: Config, store: StateStore):
        self.cfg = cfg
        self.store = store
        self.root = tk.Tk()
        self.root.title("Claude Pet")
        _borderless(self.root)
        self.skin = skins.load(cfg.skin, cfg.smooth_for(cfg.skin))
        self.size = self.skin.canvas * self.skin.pixel_scale(cfg.scale)
        self.photo = tk.PhotoImage(width=self.size, height=self.size)
        self.label = tk.Label(self.root, image=self.photo, bd=0, highlightthickness=0, bg=KEY)
        self.label.pack()

        self._monitors: list[tuple[Rect, Rect, bool]] = []
        self._monitors_at = 0.0
        self.pet = Pet(cfg, self._primary_area(), self._area_at, skin=self.skin, neighbor=self._neighbor)
        self.bubble = TkBubble(self.root)
        self._init_core()
        self._drawn_key = None
        self._images: dict = {}
        self._rename_win = None

        for w in (self.root, self.label):
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_motion)
            w.bind("<ButtonRelease-1>", self._on_release)
            w.bind("<ButtonPress-3>", self._on_menu)
        self.root.after(int(1000 / cfg.fps), self._tick)

    def run(self) -> None:
        self.root.mainloop()

    # ------------------------------------------------------------ monitores
    def _monitor_list(self) -> list[tuple[Rect, Rect, bool]]:
        """[(geometria, área de trabalho, principal)]; relido a cada 5 s (monitor plugado/desplugado)."""
        now = time.monotonic()
        if not self._monitors or now - self._monitors_at > 5:
            self._monitors_at = now
            if WINDOWS:
                mons = [(Rect(*g), Rect(*w), p) for g, w, p in winsys.monitors()]
            else:
                full = Rect(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
                mons = [(full, full, True)]
            self._monitors = mons or self._monitors
        return self._monitors

    def _primary_area(self) -> Rect:
        mons = self._monitor_list()
        if 0 <= self.cfg.monitor < len(mons):
            return mons[self.cfg.monitor][1]
        return next((w for _g, w, p in mons if p), mons[0][1])

    def _area_at(self, x: float, y: float) -> Rect:
        mons = self._monitor_list()
        for g, w, _p in mons:
            if g.x <= x < g.x + g.w and g.y <= y < g.y + g.h:
                return w

        def dist(g: Rect) -> float:   # fora de todos: o mais próximo (como o GDK faz)
            dx = max(g.x - x, 0, x - (g.x + g.w))
            dy = max(g.y - y, 0, y - (g.y + g.h))
            return dx * dx + dy * dy

        return min(mons, key=lambda m: dist(m[0]))[1]

    def _neighbor(self, area: Rect, side: int, y: float) -> Rect | None:
        """Monitor encostado do lado `side` do monitor dessa área (olha além da borda física, não da área útil)."""
        mons = self._monitor_list()
        here = next((g for g, w, _p in mons if w == area), None)
        if here is None:
            return None
        px = here.x - 1 if side < 0 else here.x + here.w
        for g, w, _p in mons:
            if g != here and g.x <= px < g.x + g.w and g.y <= y < g.y + g.h:
                return w
        return None

    def _pointer(self) -> tuple[float, float] | None:
        try:
            x, y = self.root.winfo_pointerxy()
        except tk.TclError:
            return None
        return float(x), float(y)

    def _keys_down(self) -> int | None:
        try:
            return winsys.typing_keys_down()
        except OSError:
            return None

    # ------------------------------------------------------------ loop
    def _tick(self) -> None:
        try:
            self._step()
        finally:
            self.root.after(int(1000 / self.cfg.fps), self._tick)

    def _step(self) -> None:
        now = time.monotonic()
        dt, self.last_tick = now - self.last_tick, now
        self._poll(now)

        if now < self.hidden_until:
            return
        if self.hidden_until:
            self.hidden_until = 0.0
            self.root.deiconify()

        pointer = self._pointer()
        self._dismiss_done_on_hover(pointer, now)
        status = self._pet_status(now)
        frame = self.pet.tick(dt, status, pointer)

        if self.frame is None or (frame.x, frame.y) != (self.frame.x, self.frame.y):
            self.root.geometry(f"{self.size}x{self.size}+{frame.x}+{frame.y}")
        self._redraw(frame)
        self.frame = frame

        text = self._bubble_text(frame) if frame.rotation == 0 else ""
        self.bubble.show_text(text, *self._bubble_anchor(frame), self.pet.area)

        if now - self.last_raise > 3:
            self.last_raise = now
            self.root.attributes("-topmost", True)
            self.root.lift()

    def _redraw(self, f: Frame) -> None:
        scale = self.skin.pixel_scale(self.cfg.scale)
        key = (self.skin.name, scale, f.anim, f.frame, f.look, skins.status_light(f.status), f.facing,
               f.rotation, round(f.lean, 2))
        if key == self._drawn_key:
            return
        data = self._images.get(key)
        if data is None:
            pixels = raster.render(self.skin, f.anim, f.frame, f.look, f.status, scale, self.cfg.body_color,
                                   f.lean, f.facing, f.rotation)
            n = self.size
            rows = []
            for y in range(n):
                row = pixels[y * n:(y + 1) * n]
                rows.append("{" + " ".join(c or KEY for c in row) + "}")
            data = " ".join(rows)
            if len(self._images) > 400:
                self._images.clear()
            self._images[key] = data
        self.photo.put(data, to=(0, 0))
        self._drawn_key = key

    # ------------------------------------------------------------ mouse
    def _on_press(self, ev) -> None:
        self.pressed = True
        self.pet.press(ev.x_root, ev.y_root)

    def _on_motion(self, ev) -> None:
        if self.pressed:
            self.pet.motion(ev.x_root, ev.y_root)

    def _on_release(self, _ev) -> None:
        if not self.pressed:
            return
        self.pressed = False
        if self.pet.release():
            self._click()

    def _on_menu(self, ev) -> None:
        menu = self._build_menu(self.menu_model())
        try:
            menu.tk_popup(ev.x_root, ev.y_root)
        finally:
            menu.grab_release()

    def _build_menu(self, model) -> tk.Menu:
        menu = tk.Menu(self.root, tearoff=0)
        for entry in model:
            if entry[0] == "sep":
                menu.add_separator()
            elif entry[0] == "item":
                _kind, label, action, enabled = entry
                menu.add_command(label=label, command=action or (lambda: None),
                                 state="normal" if enabled else "disabled")
            else:
                _kind, label, options = entry
                sub = tk.Menu(menu, tearoff=0)
                var = tk.IntVar(master=sub, value=next((i for i, o in enumerate(options) if o[1]), -1))
                sub._var = var   # mantém viva enquanto o menu existir
                for i, (opt_label, _checked, action) in enumerate(options):
                    sub.add_radiobutton(label=opt_label, variable=var, value=i, command=action)
                menu.add_cascade(label=label, menu=sub)
        return menu

    # ------------------------------------------------------------ ações
    def _rename(self) -> None:
        """Janelinha pra escolher o nome do pet. Vazio = "Seu pet"."""
        if self._rename_win is not None:
            self._rename_win.lift()
            return
        win = tk.Toplevel(self.root)
        self._rename_win = win
        win.title(t("rename.title"))
        win.attributes("-topmost", True)
        win.resizable(False, False)
        frame = tk.Frame(win, padx=12, pady=10)
        frame.pack()
        tk.Label(frame, text=t("rename.question"), anchor="w").pack(fill="x")
        entry = tk.Entry(frame, width=28)
        entry.insert(0, self.cfg.pet_name or "")
        entry.pack(fill="x", pady=(6, 10))
        buttons = tk.Frame(frame)
        buttons.pack(anchor="e")

        def close() -> None:
            self._rename_win = None
            win.destroy()

        def save(_ev=None) -> None:
            self._set_name(entry.get()[:24])
            close()

        tk.Button(buttons, text=t("rename.cancel"), command=close).pack(side="left", padx=(0, 6))
        tk.Button(buttons, text=t("rename.save"), command=save, default="active").pack(side="left")
        entry.bind("<Return>", save)
        win.bind("<Escape>", lambda _e: close())
        win.protocol("WM_DELETE_WINDOW", close)
        px, py = self._pointer() or (200, 200)
        win.geometry(f"+{int(px) - 120}+{int(py) - 60}")
        win.after(50, lambda: (win.focus_force(), entry.focus_set(), entry.select_range(0, "end")))

    def _apply_skin(self) -> None:
        self.photo = tk.PhotoImage(width=self.size, height=self.size)
        self.label.configure(image=self.photo)
        self._drawn_key = None
        self._images.clear()

    def _hide_for(self, minutes: int) -> None:
        self.hidden_until = time.monotonic() + minutes * 60
        self.root.withdraw()
        self.bubble.hide()

    def _quit(self) -> None:
        self.root.destroy()


def run(cfg: Config, store: StateStore) -> int:
    if WINDOWS:
        winsys.set_dpi_aware()   # antes de criar qualquer janela
        # pixels de 3 em tela 150% ficariam miúdos: acompanha a escala do Windows
        cfg.scale = max(1, round(cfg.scale * winsys.dpi_factor()))
    app = TkPetApp(cfg, store)
    app.run()
    return 0

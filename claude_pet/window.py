"""Janelas GTK: o bichinho (transparente, sempre por cima, clique atravessa fora dele) e o balão de fala."""
from __future__ import annotations

import math
import os
import sys
import time

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402

from . import bubble, skins  # noqa: E402
from .character import Frame, Pet, Rect  # noqa: E402
from .config import Config  # noqa: E402
from .core import PetCore, _crosses  # noqa: E402,F401  (_crosses: usado pelos testes)
from .i18n import t  # noqa: E402
from .state import StateStore  # noqa: E402

DEBUG = bool(os.environ.get("CLAUDE_PET_DEBUG"))


class _XKeys:
    """Tem tecla apertada agora? (X11, XQueryKeymap numa conexão só nossa; nunca dá erro de X).

    Devolve só a máscara de bits do momento: o pet compara com a anterior pra contar teclas novas e
    joga fora. Não guarda, não registra e não traduz em letras."""

    def __init__(self):
        self._dpy = None
        try:
            import ctypes
            import ctypes.util
            lib = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
            lib.XOpenDisplay.restype = ctypes.c_void_p
            lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            lib.XQueryKeymap.argtypes = [ctypes.c_void_p, ctypes.c_char * 32]
            self._buf = (ctypes.c_char * 32)()
            self._lib = lib
            self._dpy = lib.XOpenDisplay(None)
        except (OSError, AttributeError):
            self._dpy = None

    def down(self) -> int | None:
        if not self._dpy:
            return None
        self._lib.XQueryKeymap(self._dpy, self._buf)
        return int.from_bytes(bytes(self._buf), "little")


def _transparent(win: Gtk.Window) -> None:
    screen = win.get_screen()
    visual = screen.get_rgba_visual()
    if visual is not None and screen.is_composited():
        win.set_visual(visual)
    win.set_app_paintable(True)
    win.set_decorated(False)
    win.set_skip_taskbar_hint(True)
    win.set_skip_pager_hint(True)
    win.set_keep_above(True)
    win.set_accept_focus(False)


class Bubble(Gtk.Window):
    """Balão de fala pixel art; não recebe cliques."""

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        _transparent(self)
        self.key = None
        self.layout = None
        self.rect = None  # (x, y, w, h) na tela quando visível
        self.tail_x = 0
        self.tail_down = True
        self.connect("draw", self._draw)
        self.connect("realize", lambda w: w.input_shape_combine_region(cairo.Region()))

    def show_text(self, text: str, anchor_x: int, anchor_y: int, area: Rect) -> None:
        if not text:
            self.hide()
            self.key = None
            self.rect = None
            return
        if text != self.key:
            self.key = text
            self.layout = bubble.make_layout(self, text)
            self.resize(*bubble.size_for(self.layout))
            self.queue_draw()
        w, h = bubble.size_for(self.layout)
        x = min(max(anchor_x - w // 2, area.x), area.x + area.w - w)
        y = anchor_y - h
        tail_down = y >= area.y
        if not tail_down:
            y = anchor_y + 4
        tail_x = anchor_x - x
        if (tail_x, tail_down) != (self.tail_x, self.tail_down):
            self.tail_x, self.tail_down = tail_x, tail_down
            self.queue_draw()
        self.move(int(x), int(y))
        self.rect = (int(x), int(y), w, h)
        if not self.get_visible():
            self.show()

    def _draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        if self.layout is not None:
            w, h = self.get_size()
            bubble.draw(cr, self.layout, w, h, self.tail_x, self.tail_down)
        return True


class PetWindow(PetCore, Gtk.Window):
    def __init__(self, cfg: Config, store: StateStore):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.cfg = cfg
        self.store = store
        self.skin = skins.load(cfg.skin, cfg.smooth_for(cfg.skin))
        self.size = self.skin.canvas * self.skin.pixel_scale(cfg.scale)
        _transparent(self)
        self.set_default_size(self.size, self.size)
        self.resize(self.size, self.size)

        self.display = Gdk.Display.get_default()
        self.pet = Pet(cfg, self._primary_area(), self._area_at, skin=self.skin, neighbor=self._neighbor)
        self.bubble = Bubble()

        self._init_core()
        self._shape_rot = None
        self._last_dbg = 0.0
        self._xkeys = _XKeys() if cfg.type_along else None

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("draw", self._draw)
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("motion-notify-event", self._on_motion)

        GLib.timeout_add(int(1000 / cfg.fps), self._tick)

    # ------------------------------------------------------------ monitores
    def _monitor_rect(self, mon: Gdk.Monitor) -> Rect:
        g = mon.get_workarea()
        return Rect(g.x, g.y, g.width, g.height)

    def _primary_area(self) -> Rect:
        mon = None
        if self.cfg.monitor >= 0:
            mon = self.display.get_monitor(self.cfg.monitor)
        mon = mon or self.display.get_primary_monitor() or self.display.get_monitor(0)
        return self._monitor_rect(mon)

    def _area_at(self, x: float, y: float) -> Rect:
        mon = self.display.get_monitor_at_point(int(x), int(y))
        return self._monitor_rect(mon) if mon else self._primary_area()

    def _neighbor(self, area: Rect, side: int, y: float) -> Rect | None:
        """Monitor encostado do lado `side` (-1 esquerda, +1 direita) do monitor dessa área, na altura y.

        Olha além da borda física do monitor (não da área de trabalho): um dock na beirada entre dois
        monitores não vira parede. O get_monitor_at_point devolve o mais próximo, por isso a busca manual.
        """
        mons = [self.display.get_monitor(i) for i in range(self.display.get_n_monitors())]
        here = next((m for m in mons if self._monitor_rect(m) == area), None)
        if here is None:
            return None
        g = here.get_geometry()
        px = g.x - 1 if side < 0 else g.x + g.width
        for mon in mons:
            o = mon.get_geometry()
            if mon is not here and o.x <= px < o.x + o.width and o.y <= y < o.y + o.height:
                return self._monitor_rect(mon)
        return None

    def _keys_down(self) -> int | None:
        return self._xkeys.down() if self._xkeys else None

    def _pointer(self) -> tuple[float, float] | None:
        seat = self.display.get_default_seat()
        if not seat:
            return None
        _screen, x, y = seat.get_pointer().get_position()
        return float(x), float(y)

    # ------------------------------------------------------------ loop
    def _tick(self) -> bool:
        now = time.monotonic()
        dt, self.last_tick = now - self.last_tick, now

        self._poll(now)

        if now < self.hidden_until:
            return True
        if self.hidden_until and not self.get_visible():
            self.hidden_until = 0.0
            self.show_all()

        pointer = self._pointer()
        self._dismiss_done_on_hover(pointer, now)
        status = self._pet_status(now)
        frame = self.pet.tick(dt, status, pointer)

        if self.frame is None or (frame.x, frame.y) != (self.frame.x, self.frame.y):
            self.move(frame.x, frame.y)
        if self.frame is None or (frame.anim, frame.frame, frame.look, frame.rotation, frame.status, frame.facing,
                                  round(frame.lean, 2)) != (
                self.frame.anim, self.frame.frame, self.frame.look, self.frame.rotation, self.frame.status,
                self.frame.facing, round(self.frame.lean, 2)):
            self.queue_draw()
        if (frame.rotation, frame.facing) != self._shape_rot:
            self._update_input_shape(frame.rotation, frame.facing)
        self.frame = frame

        self._update_bubble(frame)
        if DEBUG and now - self._last_dbg > 0.5:
            self._last_dbg = now
            print(f"[pet] status={status} anim={frame.anim} mode={self.pet.mode} x={frame.x} y={frame.y} "
                  f"rot={frame.rotation} idle_action={self.pet.idle_action}", file=sys.stderr, flush=True)

        if now - self.last_raise > 3:
            self.last_raise = now
            gdk_win = self.get_window()
            if gdk_win:
                gdk_win.raise_()
        return True

    # ------------------------------------------------------------ desenho
    def _draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        f = self.frame
        if f is None:
            return True
        half = self.size / 2
        cr.translate(half, half)
        cr.rotate(math.radians(f.rotation))
        cr.translate(-half, -half)
        look = f.look
        self.skin.draw(cr, f.anim, f.frame, look, f.status, self.skin.pixel_scale(self.cfg.scale),
                       self.cfg.body_color, f.lean, f.facing)
        return True

    def _update_input_shape(self, rotation: int, facing: int = 1) -> None:
        """Só a área do robô recebe clique; o resto da janela deixa o mouse passar."""
        gdk_win = self.get_window()
        if not gdk_win:
            return
        s = self.skin.pixel_scale(self.cfg.scale)
        hx, hy, hw, hh = self.skin.hit
        if getattr(self.skin, "side_view", False) and facing < 0:  # virado pra esquerda: área espelhada
            hx = self.skin.canvas - hx - hw
        x, y, w, h = hx * s, hy * s, hw * s, hh * s
        n = self.size
        for _ in range((rotation // 90) % 4):  # gira o retângulo 90° horário dentro do canvas
            x, y, w, h = n - y - h, x, h, w
        self.input_shape_combine_region(cairo.Region(cairo.RectangleInt(int(x), int(y), int(w), int(h))))
        self._shape_rot = (rotation, facing)

    # ------------------------------------------------------------ balão
    def _update_bubble(self, frame: Frame) -> None:
        text = self._bubble_text(frame) if frame.rotation == 0 else ""
        self.bubble.show_text(text, *self._bubble_anchor(frame), self.pet.area)

    # ------------------------------------------------------------ mouse
    def _on_press(self, _w, ev):
        if ev.button == 1 and ev.type == Gdk.EventType.BUTTON_PRESS:
            self.pressed = True
            self.pet.press(ev.x_root, ev.y_root)
        elif ev.button == 3:
            self._menu(ev)
        return True

    def _on_motion(self, _w, ev):
        if self.pressed:
            self.pet.motion(ev.x_root, ev.y_root)
        return True

    def _on_release(self, _w, ev):
        if ev.button != 1 or not self.pressed:
            return True
        self.pressed = False
        if self.pet.release():
            self._click()
        return True

    def _menu(self, ev) -> None:
        self._build_menu(self.menu_model()).popup_at_pointer(ev)

    def _build_menu(self, model) -> Gtk.Menu:
        menu = Gtk.Menu()
        for entry in model:
            if entry[0] == "sep":
                menu.append(Gtk.SeparatorMenuItem())
            elif entry[0] == "item":
                _kind, label, action, enabled = entry
                item = Gtk.MenuItem(label=label)
                item.set_sensitive(enabled)
                if action:
                    item.connect("activate", lambda _i, a=action: a())
                menu.append(item)
            else:
                _kind, label, options = entry
                sub, group = Gtk.Menu(), None
                for opt_label, checked, action in options:
                    item = Gtk.RadioMenuItem.new_with_label_from_widget(group, opt_label)
                    group = group or item
                    item.set_active(checked)
                    item.connect("toggled", lambda i, a=action: i.get_active() and a())
                    sub.append(item)
                root = Gtk.MenuItem(label=label)
                root.set_submenu(sub)
                menu.append(root)
        menu.show_all()
        return menu

    def _quit(self) -> None:
        Gtk.main_quit()

    def _rename(self) -> None:
        """Janelinha pra escolher o nome do pet. Vazio = "Seu pet"."""
        dlg = Gtk.Dialog(title=t("rename.title"))
        dlg.add_buttons(t("rename.cancel"), Gtk.ResponseType.CANCEL, t("rename.save"), Gtk.ResponseType.OK)
        dlg.set_default_response(Gtk.ResponseType.OK)
        dlg.set_keep_above(True)
        dlg.set_position(Gtk.WindowPosition.MOUSE)
        dlg.set_resizable(False)
        box = dlg.get_content_area()
        box.set_border_width(12)
        box.set_spacing(8)
        box.add(Gtk.Label(label=t("rename.question"), xalign=0))
        entry = Gtk.Entry(text=self.cfg.pet_name or "", placeholder_text=t("default_name"), max_length=24,
                          activates_default=True)
        box.add(entry)
        dlg.show_all()
        response = dlg.run()   # o loop do pet continua rodando enquanto a janelinha está aberta
        name = entry.get_text().strip()
        dlg.destroy()
        if response == Gtk.ResponseType.OK:
            self._set_name(name)

    def _apply_skin(self) -> None:
        self.resize(self.size, self.size)
        self._shape_rot = None         # recalcula a área clicável no próximo tick
        self.queue_draw()

    def _hide_for(self, minutes: int) -> None:
        self.hidden_until = time.monotonic() + minutes * 60
        self.hide()
        self.bubble.hide()

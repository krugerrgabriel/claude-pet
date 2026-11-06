"""Janelas GTK: o bichinho (transparente, sempre por cima, clique atravessa fora dele) e o balão de fala."""
from __future__ import annotations

import math
import os
import re
import sys
import time

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402

from . import focus, skins  # noqa: E402
from .character import Frame, Pet, Rect  # noqa: E402
from .config import Config  # noqa: E402
from .sprites import STATUS_COLORS  # noqa: E402
from .state import Session, StateStore  # noqa: E402

DEBUG = bool(os.environ.get("CLAUDE_PET_DEBUG"))

STATUS_LABEL = {
    "idle": "ocioso",
    "thinking": "pensando…",
    "working": "trabalhando",
    "attention": "precisa de você",
    "done": "terminou",
}


_PERMISSAO = re.compile(r"Claude needs your permission to use (.+)", re.I)


def _traduz(msg: str) -> str:
    """Mensagens do Claude Code vêm em inglês; traduz as comuns."""
    if not msg:
        return ""
    m = _PERMISSAO.search(msg)
    if m:
        return f"Quer permissão para usar {m.group(1)}"
    if "waiting for your input" in msg.lower():
        return "Esperando sua resposta"
    return msg


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
    """Balão de texto; não recebe cliques."""

    PAD = 8

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        _transparent(self)
        self.text = ""
        self.accent = STATUS_COLORS["idle"]
        self.connect("draw", self._draw)
        self.connect("realize", lambda w: w.input_shape_combine_region(cairo.Region()))
        self._layout = None

    def show_text(self, text: str, accent: str, anchor_x: int, anchor_y: int, area: Rect) -> None:
        if not text:
            self.hide()
            return
        if text != self.text or self._layout is None:
            self.text, self.accent = text, accent
            self._layout = self.create_pango_layout("")
            self._layout.set_font_description(Pango.FontDescription("Sans 9"))
            self._layout.set_text(text, -1)
            self._layout.set_width(360 * Pango.SCALE)
            self._layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            tw, th = self._layout.get_pixel_size()
            self.resize(tw + 2 * self.PAD + 6, th + 2 * self.PAD)
            self.queue_draw()
        self.accent = accent
        w, h = self.get_size()
        x = min(max(anchor_x - w // 2, area.x), area.x + area.w - w)
        y = anchor_y - h - 4
        if y < area.y:
            y = anchor_y + 4
        self.move(int(x), int(y))
        if not self.get_visible():
            self.show()

    def _draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        w, h = self.get_size()
        r = 8
        cr.new_sub_path()
        cr.arc(w - r - 1, r + 1, r, -math.pi / 2, 0)
        cr.arc(w - r - 1, h - r - 1, r, 0, math.pi / 2)
        cr.arc(r + 1, h - r - 1, r, math.pi / 2, math.pi)
        cr.arc(r + 1, r + 1, r, math.pi, 1.5 * math.pi)
        cr.close_path()
        cr.set_source_rgba(0.09, 0.12, 0.16, 0.93)
        cr.fill_preserve()
        rr, gg, bb = (int(self.accent[i:i + 2], 16) / 255 for i in (1, 3, 5))
        cr.set_source_rgb(rr, gg, bb)
        cr.set_line_width(1.5)
        cr.stroke()
        cr.rectangle(1, 4, 4, h - 8)
        cr.fill()
        cr.set_source_rgb(0.92, 0.95, 0.97)
        cr.move_to(self.PAD + 4, self.PAD)
        PangoCairo.show_layout(cr, self._layout)
        return True


class PetWindow(Gtk.Window):
    def __init__(self, cfg: Config, store: StateStore):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.cfg = cfg
        self.store = store
        self.skin = skins.load(cfg.skin)
        self.size = self.skin.canvas * cfg.scale
        _transparent(self)
        self.set_default_size(self.size, self.size)
        self.resize(self.size, self.size)

        self.display = Gdk.Display.get_default()
        self.pet = Pet(cfg, self._primary_area(), self._area_at, skin=self.skin)
        self.bubble = Bubble()

        self.frame: Frame | None = None
        self.sessions: list[Session] = []
        self.top: Session | None = None
        self.last_poll = 0.0
        self.last_raise = 0.0
        self.last_tick = time.monotonic()
        self.hidden_until = 0.0
        self.pressed = False
        self._shape_rot = None
        self._last_dbg = 0.0

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

        if now - self.last_poll > 0.25:
            self.last_poll = now
            self.sessions = self.store.sessions()
            self.top = self.sessions[0] if self.sessions else None

        if now < self.hidden_until:
            return True
        if self.hidden_until and not self.get_visible():
            self.hidden_until = 0.0
            self.show_all()

        status = self.top.status if self.top else "idle"
        frame = self.pet.tick(dt, status, self._pointer())

        if self.frame is None or (frame.x, frame.y) != (self.frame.x, self.frame.y):
            self.move(frame.x, frame.y)
        if self.frame is None or (frame.anim, frame.frame, frame.look, frame.rotation, frame.status) != (
                self.frame.anim, self.frame.frame, self.frame.look, self.frame.rotation, self.frame.status):
            self.queue_draw()
        if frame.rotation != self._shape_rot:
            self._update_input_shape(frame.rotation)
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
        look = f.look if self.skin.name == skins.ROBOT else f.facing
        self.skin.draw(cr, f.anim, f.frame, look, f.status, self.cfg.scale, self.cfg.body_color)
        return True

    def _update_input_shape(self, rotation: int) -> None:
        """Só a área do robô recebe clique; o resto da janela deixa o mouse passar."""
        gdk_win = self.get_window()
        if not gdk_win:
            return
        s = self.cfg.scale
        hx, hy, hw, hh = self.skin.hit
        x, y, w, h = hx * s, hy * s, hw * s, hh * s
        n = self.size
        for _ in range((rotation // 90) % 4):  # gira o retângulo 90° horário dentro do canvas
            x, y, w, h = n - y - h, x, h, w
        self.input_shape_combine_region(cairo.Region(cairo.RectangleInt(int(x), int(y), int(w), int(h))))
        self._shape_rot = rotation

    # ------------------------------------------------------------ balão
    def _bubble_text(self, frame: Frame) -> str:
        top = self.top
        busy = [s for s in self.sessions if s.status != "idle"]
        extra = f"\n+{len(busy) - 1} outra(s) sessão(ões) ativa(s)" if len(busy) > 1 else ""
        pointer = self._pointer()
        hovering = pointer is not None and self.pet.contains(*pointer)

        if top and top.status == "attention":
            msg = _traduz(top.message)
            body = f"⚠ {top.name} precisa de você"
            return body + (f"\n{msg}" if msg else "") + "\nClique em mim para abrir" + extra
        if top and top.status == "done" and frame.anim in ("waiting", "celebrate"):
            return f"✓ {top.name} terminou\nClique em mim para abrir{extra}"
        if not hovering or self.pressed:
            return ""
        if not self.sessions:
            return "Nenhuma sessão do Claude Code aberta"
        lines = []
        for s in self.sessions[:6]:
            detail = STATUS_LABEL.get(s.status, s.status)
            if s.status == "working" and s.tool:
                detail = f"{detail}: {s.tool}"
            lines.append(f"● {s.name}: {detail}")
        return "\n".join(lines)

    def _update_bubble(self, frame: Frame) -> None:
        text = self._bubble_text(frame) if frame.rotation == 0 else ""
        s = self.cfg.scale
        self.bubble.show_text(text, STATUS_COLORS.get(frame.status, STATUS_COLORS["idle"]),
                              frame.x + self.size // 2, frame.y + (self.skin.hit[1] - 1) * s, self.pet.area)

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

    def _click(self) -> None:
        top = self.top
        if top and top.status in ("attention", "done"):
            focus.focus_session(top.claude_pid, top.project)
            self.store.acknowledge(top)
        else:
            self.pet.cheer()

    def _menu(self, ev) -> None:
        menu = Gtk.Menu()
        if self.sessions:
            for s in self.sessions[:8]:
                item = Gtk.MenuItem(label=f"{s.name}: {STATUS_LABEL.get(s.status, s.status)}")
                item.connect("activate", lambda _i, sess=s: (focus.focus_session(sess.claude_pid, sess.project),
                                                              self.store.acknowledge(sess)))
                menu.append(item)
        else:
            item = Gtk.MenuItem(label="Nenhuma sessão aberta")
            item.set_sensitive(False)
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        skin_item = Gtk.MenuItem(label="Personagem")
        sub = Gtk.Menu()
        group = None
        for name in skins.available():
            radio = Gtk.RadioMenuItem.new_with_label_from_widget(group, name.capitalize())
            group = group or radio
            radio.set_active(name == self.skin.name)
            radio.connect("toggled", lambda r, n=name: r.get_active() and self._set_skin(n))
            sub.append(radio)
        skin_item.set_submenu(sub)
        menu.append(skin_item)
        for label, minutes in (("Esconder por 30 min", 30), ("Esconder por 2 h", 120)):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _i, m=minutes: self._hide_for(m))
            menu.append(item)
        quit_item = Gtk.MenuItem(label="Sair")
        quit_item.connect("activate", lambda _i: Gtk.main_quit())
        menu.append(quit_item)
        menu.show_all()
        menu.popup_at_pointer(ev)

    def _set_skin(self, name: str) -> None:
        if name == self.skin.name:
            return
        self.skin = skins.load(name)
        self.size = self.skin.canvas * self.cfg.scale
        self.resize(self.size, self.size)
        self.pet.set_skin(self.skin)
        self._shape_rot = None
        self.frame = None
        self.cfg.save_key("skin", name)

    def _hide_for(self, minutes: int) -> None:
        self.hidden_until = time.monotonic() + minutes * 60
        self.hide()
        self.bubble.hide()

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

from . import bubble, focus, skins  # noqa: E402
from .character import Frame, Pet, Rect  # noqa: E402
from .config import Config  # noqa: E402
from .sprites import STATUS_COLORS  # noqa: E402
from .state import Session, StateStore  # noqa: E402

DEBUG = bool(os.environ.get("CLAUDE_PET_DEBUG"))

STATUS_LABEL = {
    "idle": "de boa",
    "thinking": "pensando…",
    "working": "trabalhando",
    "attention": "precisando de você",
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
    """Balão de fala pixel art; não recebe cliques."""

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        _transparent(self)
        self.key = None
        self.layout = None
        self.tail_x = 0
        self.tail_down = True
        self.connect("draw", self._draw)
        self.connect("realize", lambda w: w.input_shape_combine_region(cairo.Region()))

    def show_text(self, text: str, status: str, anchor_x: int, anchor_y: int, area: Rect) -> None:
        if not text:
            self.hide()
            self.key = None
            return
        if (text, status) != self.key:
            self.key = (text, status)
            self.layout = bubble.make_layout(self, text, status)
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


class PetWindow(Gtk.Window):
    def __init__(self, cfg: Config, store: StateStore):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.cfg = cfg
        self.store = store
        self.skin = skins.load()
        self.size = self.skin.canvas * self.skin.pixel_scale(cfg.scale)
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
        if self.frame is None or (frame.anim, frame.frame, frame.look, frame.rotation, frame.status, frame.facing,
                                  round(frame.lean, 2)) != (
                self.frame.anim, self.frame.frame, self.frame.look, self.frame.rotation, self.frame.status,
                self.frame.facing, round(self.frame.lean, 2)):
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
        look = f.look
        self.skin.draw(cr, f.anim, f.frame, look, f.status, self.skin.pixel_scale(self.cfg.scale),
                       self.cfg.body_color, f.lean)
        return True

    def _update_input_shape(self, rotation: int) -> None:
        """Só a área do robô recebe clique; o resto da janela deixa o mouse passar."""
        gdk_win = self.get_window()
        if not gdk_win:
            return
        s = self.skin.pixel_scale(self.cfg.scale)
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
        extra = f" (+{len(busy) - 1})" if len(busy) > 1 else ""
        pointer = self._pointer()
        hovering = pointer is not None and self.pet.contains(*pointer)

        if top and top.status == "attention":
            msg = _traduz(top.message)
            return f"{msg or 'Claude Code precisa de você'}{extra}.\nClique em mim para abrir"
        if top and top.status == "done" and frame.anim in ("waiting", "celebrate"):
            return f"Claude Code terminou{extra}.\nClique em mim para abrir"
        if not hovering or self.pressed:
            return ""
        name = self.cfg.pet_name
        if not self.sessions:
            return f"{name}: nenhuma sessão aberta"
        if len(self.sessions) == 1:
            sess = self.sessions[0]
            detail = STATUS_LABEL.get(sess.status, sess.status)
            if sess.status == "working" and sess.tool:
                detail = f"{detail} ({sess.tool})"
            return f"{name} está {detail}"
        counts: dict[str, int] = {}
        for sess in self.sessions:  # já vêm do mais urgente pro menos
            counts[sess.status] = counts.get(sess.status, 0) + 1
        return f"{name}: " + ", ".join(f"{n} {'chat' if n == 1 else 'chats'} {STATUS_LABEL.get(st, st)}"
                                     for st, n in counts.items())

    def _update_bubble(self, frame: Frame) -> None:
        text = self._bubble_text(frame) if frame.rotation == 0 else ""
        s = self.skin.pixel_scale(self.cfg.scale)
        status = self.top.status if (self.top and text) else "idle"
        self.bubble.show_text(text, status if status in ("done", "attention") else "idle",
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
                item = Gtk.MenuItem(label=f"{s.project}: {STATUS_LABEL.get(s.status, s.status)}")
                item.connect("activate", lambda _i, sess=s: (focus.focus_session(sess.claude_pid, sess.project),
                                                              self.store.acknowledge(sess)))
                menu.append(item)
        else:
            item = Gtk.MenuItem(label="Nenhuma sessão aberta")
            item.set_sensitive(False)
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        for label, minutes in (("Esconder por 30 min", 30), ("Esconder por 2 h", 120)):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _i, m=minutes: self._hide_for(m))
            menu.append(item)
        quit_item = Gtk.MenuItem(label="Sair")
        quit_item.connect("activate", lambda _i: Gtk.main_quit())
        menu.append(quit_item)
        menu.show_all()
        menu.popup_at_pointer(ev)

    def _hide_for(self, minutes: int) -> None:
        self.hidden_until = time.monotonic() + minutes * 60
        self.hide()
        self.bubble.hide()

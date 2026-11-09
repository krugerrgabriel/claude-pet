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

from . import bubble, focus, i18n, skins  # noqa: E402
from .i18n import t  # noqa: E402
from .character import Frame, Pet, Rect  # noqa: E402
from .config import Config  # noqa: E402
from .sprites import STATUS_COLORS  # noqa: E402
from .state import Session, StateStore  # noqa: E402

DEBUG = bool(os.environ.get("CLAUDE_PET_DEBUG"))

def _status(st: str) -> str:
    return t(f"status.{st}") if f"status.{st}" in i18n.STRINGS else st


def _crosses(p0, p1, rect) -> bool:
    """O mouse passou por dentro de rect = (x, y, w, h) entre um tick e outro?

    Amostra o segmento p0→p1 a cada ~3 px, então uma passada rápida por cima também conta.
    """
    if p1 is None or rect is None:
        return False
    x, y, w, h = rect
    p0 = p0 or p1
    steps = max(1, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 3))
    for i in range(steps + 1):
        t = i / steps
        px, py = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
        if x <= px <= x + w and y <= py <= y + h:
            return True
    return False


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


class PetWindow(Gtk.Window):
    def __init__(self, cfg: Config, store: StateStore):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.cfg = cfg
        self.store = store
        self.skin = skins.load(cfg.skin)
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
        self._last_pointer = None
        self._just_seen = None      # (sessão, monotonic) do "terminou" dispensado no hover: o clique ainda abre
        self._quiet_hover = False   # acabou de dispensar o "terminou": sem balão até o mouse sair
        self.sleep_since = 0.0      # time.time() de quando foi botado pra dormir

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
            self._maybe_wake()

        if now < self.hidden_until:
            return True
        if self.hidden_until and not self.get_visible():
            self.hidden_until = 0.0
            self.show_all()

        pointer = self._pointer()
        self._dismiss_done_on_hover(pointer, now)
        status = self.top.status if self.top else "idle"
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

    def _dismiss_done_on_hover(self, pointer, now: float) -> None:
        """Mouse passou (mesmo rapidinho) pelo Bit ou pelo balão = "vi que terminou": some o balão e o ✓."""
        prev, self._last_pointer = self._last_pointer, pointer
        x, y = self.pet.position()
        pet_rect = (x, y, self.size, self.size)
        if self._quiet_hover and not (pointer and self.pet.contains(*pointer)):
            self._quiet_hover = False
        if self.pressed or not (self.top and self.top.status == "done"):
            return
        if not (_crosses(prev, pointer, pet_rect) or _crosses(prev, pointer, self.bubble.rect)):
            return
        self._just_seen = (self.top, now)
        for sess in self.sessions:
            if sess.status == "done":
                self.store.acknowledge(sess)
        self.sessions = self.store.sessions()
        self.top = self.sessions[0] if self.sessions else None
        self._quiet_hover = True

    # ------------------------------------------------------------ dormir
    def _sleep(self) -> None:
        self.sleep_since = time.time()
        self.pet.sleep_now()

    def _wake(self) -> None:
        self.sleep_since = 0.0
        self.pet.wake()

    def _maybe_wake(self) -> None:
        """Acorda com um prompt novo seu ou quando o Claude pede permissão (aí ele precisa de você)."""
        if not self.sleep_since:
            return
        for sess in self.sessions:
            if sess.prompt_ts > self.sleep_since or (sess.status == "attention" and sess.since > self.sleep_since):
                self._wake()
                return

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
    def _bubble_text(self, frame: Frame) -> str:
        top = self.top
        busy = [s for s in self.sessions if s.status != "idle"]
        extra = f" (+{len(busy) - 1})" if len(busy) > 1 else ""
        pointer = self._pointer()
        hovering = pointer is not None and self.pet.contains(*pointer)

        if top and top.status == "attention":
            msg = i18n.claude_message(top.message)
            return f"{msg or t('bubble.needs_you')}{extra}.\n{t('bubble.click')}"
        if top and top.status == "done" and frame.anim in ("waiting", "celebrate"):
            return f"{t('bubble.done')}{extra}.\n{t('bubble.click')}"
        if not hovering or self.pressed or self._quiet_hover:
            return ""
        name = self.cfg.display_name
        if self.pet.forced_sleep:
            return t("bubble.sleeping", name=name)
        if not self.sessions:
            return t("bubble.no_sessions", name=name)
        if len(self.sessions) == 1:
            sess = self.sessions[0]
            detail = _status(sess.status)
            if sess.status == "working" and sess.tool:
                detail = f"{detail} ({sess.tool})"
            return t("bubble.one", name=name, status=detail)
        counts: dict[str, int] = {}
        for sess in self.sessions:  # já vêm do mais urgente pro menos
            counts[sess.status] = counts.get(sess.status, 0) + 1
        return f"{name}: " + ", ".join(t("bubble.chats_one" if n == 1 else "bubble.chats_many", n=n,
                                         status=_status(st)) for st, n in counts.items())

    def _update_bubble(self, frame: Frame) -> None:
        text = self._bubble_text(frame) if frame.rotation == 0 else ""
        s = self.skin.pixel_scale(self.cfg.scale)
        self.bubble.show_text(text, frame.x + self.size // 2, frame.y + (self.skin.hit[1] - 1) * s, self.pet.area)

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
        seen = self._just_seen
        if top and top.status in ("attention", "done"):
            focus.focus_session(top.claude_pid, top.project)
            self.store.acknowledge(top)
        elif seen and time.monotonic() - seen[1] < 8:  # passou o mouse e já clicou: abre o terminal mesmo assim
            self._just_seen = None
            focus.focus_session(seen[0].claude_pid, seen[0].project)
        else:
            self.pet.cheer()

    def _menu(self, ev) -> None:
        menu = Gtk.Menu()
        if self.sessions:
            for s in self.sessions[:8]:
                item = Gtk.MenuItem(label=f"{s.project}: {_status(s.status)}")
                item.connect("activate", lambda _i, sess=s: (focus.focus_session(sess.claude_pid, sess.project),
                                                              self.store.acknowledge(sess)))
                menu.append(item)
        else:
            item = Gtk.MenuItem(label=t("menu.no_sessions"))
            item.set_sensitive(False)
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(self._skin_menu())
        rename = Gtk.MenuItem(label=t("menu.rename"))
        rename.connect("activate", lambda _i: self._rename())
        menu.append(rename)
        menu.append(self._language_menu())
        if self.pet.forced_sleep:
            item = Gtk.MenuItem(label=t("menu.wake"))
            item.connect("activate", lambda _i: self._wake())
        else:
            item = Gtk.MenuItem(label=t("menu.sleep"))
            item.connect("activate", lambda _i: self._sleep())
        menu.append(item)
        for label, minutes in ((t("menu.hide_30"), 30), (t("menu.hide_2h"), 120)):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda _i, m=minutes: self._hide_for(m))
            menu.append(item)
        quit_item = Gtk.MenuItem(label=t("menu.quit"))
        quit_item.connect("activate", lambda _i: Gtk.main_quit())
        menu.append(quit_item)
        menu.show_all()
        menu.popup_at_pointer(ev)

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
            self.cfg.save_key("pet_name", name)

    def _skin_menu(self) -> Gtk.MenuItem:
        sub = Gtk.Menu()
        group = None
        for name in skins.available():
            item = Gtk.RadioMenuItem.new_with_label_from_widget(group, skins.label(name))
            group = group or item
            item.set_active(name == self.skin.name)
            item.connect("toggled", lambda i, n=name: i.get_active() and self._set_skin(n))
            sub.append(item)
        root = Gtk.MenuItem(label=t("menu.character"))
        root.set_submenu(sub)
        return root

    def _language_menu(self) -> Gtk.MenuItem:
        sub = Gtk.Menu()
        group = None
        options = [("auto", t("menu.lang_auto"))] + [(code, i18n.LANGUAGE_NAMES[code]) for code in i18n.LANGUAGES]
        chosen = (self.cfg.language or "auto").lower()
        for code, label in options:
            item = Gtk.RadioMenuItem.new_with_label_from_widget(group, label)
            group = group or item
            item.set_active(code == chosen)
            item.connect("toggled", lambda i, c=code: i.get_active() and self._set_language(c))
            sub.append(item)
        root = Gtk.MenuItem(label=t("menu.language"))
        root.set_submenu(sub)
        return root

    def _set_language(self, code: str) -> None:
        self.cfg.save_key("language", code)
        i18n.set_language(code)   # balão e menu já saem no idioma novo

    def _set_skin(self, name: str) -> None:
        if name == self.skin.name:
            return
        self.skin = skins.load(name)
        self.cfg.save_key("skin", name)
        self.size = self.skin.canvas * self.skin.pixel_scale(self.cfg.scale)
        self.resize(self.size, self.size)
        self.pet.set_skin(self.skin)   # solta e cai de novo no chão
        self._shape_rot = None         # recalcula a área clicável no próximo tick
        self.queue_draw()

    def _hide_for(self, minutes: int) -> None:
        self.hidden_until = time.monotonic() + minutes * 60
        self.hide()
        self.bubble.hide()

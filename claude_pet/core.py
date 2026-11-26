"""O que a janela do pet faz e que não depende de toolkit (GTK no Linux, Tk no Windows):
ler as sessões, dispensar o "terminou" no hover, dormir/acordar, texto do balão, clique e menu.

A janela concreta herda `PetCore` e fornece: self.cfg, self.store, self.pet, self.bubble (com `.rect`),
self.skin, self.size, `_pointer()`, `_apply_skin()`, `_hide_for(min)` e `_quit()`; pro modo troll,
`_warp_pointer(x, y)` e `_buttons_down()`.
"""
from __future__ import annotations

import math
import time

from . import focus, i18n, skins
from .character import Frame
from .i18n import t
from .state import Session
from .troll import Troll


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
        k = i / steps
        px, py = p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k
        if x <= px <= x + w and y <= py <= y + h:
            return True
    return False


class PetCore:
    def _init_core(self) -> None:
        self.frame: Frame | None = None
        self.sessions: list[Session] = []
        self.top: Session | None = None
        self.last_poll = 0.0
        self.last_raise = 0.0
        self.last_tick = time.monotonic()
        self.hidden_until = 0.0
        self.pressed = False
        self._last_pointer = None
        self._just_seen = None      # (sessão, monotonic) do "terminou" dispensado no hover: o clique ainda abre
        self._quiet_hover = False   # acabou de dispensar o "terminou": sem balão até o mouse sair
        self.sleep_since = 0.0      # time.time() de quando foi botado pra dormir
        self._troll: Troll | None = None

    # ------------------------------------------------------------ sessões
    def _poll(self, now: float) -> None:
        if now - self.last_poll > 0.25:
            self.last_poll = now
            self.sessions = self.store.sessions()
            self.top = self.sessions[0] if self.sessions else None
            self._maybe_wake()

    def _dismiss_done_on_hover(self, pointer, now: float) -> None:
        """Mouse passou (mesmo rapidinho) pelo pet ou pelo balão = "vi que terminou": some o balão e o ✓."""
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

    # ------------------------------------------------------------ modo troll
    @property
    def troll(self) -> Troll:
        if getattr(self, "_troll", None) is None or self._troll.pet is not self.pet:
            self._troll = Troll(self.pet)
        return self._troll

    def _troll_step(self, now: float, dt: float, pointer, status: str):
        """Roda a pegadinha da vez (se o modo estiver ligado) e devolve o ponteiro já com o cursor movido."""
        if not self.troll.on:
            return pointer
        try:
            buttons = self._buttons_down()
        except Exception:
            buttons = True   # sem saber se tem botão apertado, não apronta
        want = self.troll.tick(now, dt, pointer, status, buttons, self.pressed)
        if want is None:
            return pointer
        x, y = int(round(want[0])), int(round(want[1]))
        self._warp_pointer(x, y)
        return float(x), float(y)

    def _toggle_troll(self) -> None:
        self.troll.enable(not self.troll.on, time.monotonic())

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

    # ------------------------------------------------------------ balão
    def _bubble_text(self, frame: Frame) -> str:
        top = self.top
        busy = [s for s in self.sessions if s.status != "idle"]
        extra = f" (+{len(busy) - 1})" if len(busy) > 1 else ""
        pointer = self._pointer()
        hovering = pointer is not None and self.pet.contains(*pointer)

        if self.troll.active and self.troll.phase == "hold":
            return t("troll.steal" if self.troll.prank == "steal" else "troll.heavy")
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

    def _bubble_anchor(self, frame: Frame) -> tuple[int, int]:
        s = self.skin.pixel_scale(self.cfg.scale)
        return frame.x + self.size // 2, frame.y + (self.skin.hit[1] - 1) * s

    # ------------------------------------------------------------ clique
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

    def _open_session(self, sess: Session) -> None:
        focus.focus_session(sess.claude_pid, sess.project)
        self.store.acknowledge(sess)

    # ------------------------------------------------------------ menu
    def menu_model(self) -> list:
        """Itens do menu do botão direito, independentes de toolkit:
          ("item", rótulo, ação, habilitado) | ("sep",) | ("radio", rótulo, [(rótulo, marcado, ação), ...])
        """
        items: list = []
        if self.sessions:
            for s in self.sessions[:8]:
                items.append(("item", f"{s.project}: {_status(s.status)}", lambda sess=s: self._open_session(sess), True))
        else:
            items.append(("item", t("menu.no_sessions"), None, False))
        items.append(("sep",))
        items.append(("radio", t("menu.character"),
                      [(skins.label(n), n == self.skin.name, lambda n=n: self._set_skin(n)) for n in skins.available()]))
        if self.skin.smoothable:
            smooth = self.cfg.smooth_for(self.skin.name)
            items.append(("radio", t("menu.animation"),
                          [(t("menu.anim_smooth"), smooth, lambda: self._set_smooth(True)),
                           (t("menu.anim_frames"), not smooth, lambda: self._set_smooth(False))]))
        items.append(("item", t("menu.rename"), self._rename, True))
        chosen = (self.cfg.language or "auto").lower()
        langs = [("auto", t("menu.lang_auto"))] + [(c, i18n.LANGUAGE_NAMES[c]) for c in i18n.LANGUAGES]
        items.append(("radio", t("menu.language"),
                      [(label, code == chosen, lambda c=code: self._set_language(c)) for code, label in langs]))
        if self.pet.forced_sleep:
            items.append(("item", t("menu.wake"), self._wake, True))
        else:
            items.append(("item", t("menu.sleep"), self._sleep, True))
        items.append(("item", t("menu.troll_off" if self.troll.on else "menu.troll_on"), self._toggle_troll, True))
        items.append(("item", t("menu.hide_30"), lambda: self._hide_for(30), True))
        items.append(("item", t("menu.hide_2h"), lambda: self._hide_for(120), True))
        items.append(("item", t("menu.quit"), self._quit, True))
        return items

    def _set_language(self, code: str) -> None:
        self.cfg.save_key("language", code)
        i18n.set_language(code)   # balão e menu já saem no idioma novo

    def _set_name(self, name: str) -> None:
        self.cfg.save_key("pet_name", name.strip())

    def _set_smooth(self, on: bool) -> None:
        """Animação suave (crossfade) ou quadro a quadro, guardada por personagem."""
        self.cfg.save_key("smooth_anim", {**(self.cfg.smooth_anim or {}), self.skin.name: on})
        self.skin.set_smooth(on)   # vale já no próximo quadro

    def _set_skin(self, name: str) -> None:
        if name == self.skin.name:
            return
        self.skin = skins.load(name, self.cfg.smooth_for(name))
        self.cfg.save_key("skin", name)
        self.size = self.skin.canvas * self.skin.pixel_scale(self.cfg.scale)
        self.pet.set_skin(self.skin)   # solta e cai de novo no chão
        self._apply_skin()

    # ------------------------------------------------------------ cada toolkit implementa
    def _pointer(self):
        raise NotImplementedError

    def _rename(self) -> None:
        raise NotImplementedError

    def _apply_skin(self) -> None:
        raise NotImplementedError

    def _hide_for(self, minutes: int) -> None:
        raise NotImplementedError

    def _quit(self) -> None:
        raise NotImplementedError

    def _warp_pointer(self, x: int, y: int) -> None:
        raise NotImplementedError

    def _buttons_down(self) -> bool:
        raise NotImplementedError

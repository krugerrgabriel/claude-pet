"""O que a janela do pet faz e que não depende de toolkit (GTK no Linux, Tk no Windows):
ler as sessões, dispensar o "terminou" no hover, dormir/acordar, texto do balão, clique e menu.
Com o Claude parado, você digitando faz o pet digitar junto.

A janela concreta herda `PetCore` e fornece: self.cfg, self.store, self.pet, self.bubble (com `.rect`),
self.skin, self.size, `_pointer()`, `_apply_skin()`, `_hide_for(min)` e `_quit()`; opcionalmente
`_keys_down()` (digitar junto) e, pro modo troll, `_warp_pointer(x, y)` e `_buttons_down()`.
"""
from __future__ import annotations

import math
import subprocess
import sys
import threading
import time
from dataclasses import fields
from pathlib import Path

from . import focus, i18n, skins
from .character import Frame
from .config import CONFIG_FILE, Config
from .i18n import t
from .state import Session
from .troll import Troll

# Você digitando (sem o Claude fazendo nada): TYPE_KEYS teclas novas em TYPE_WINDOW segundos, e o pet
# continua digitando até TYPE_HOLD segundos depois da última (pausa entre palavras não para ele).
TYPE_KEYS = 4
TYPE_WINDOW = 2.0
TYPE_HOLD = 4.0


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
        self.typing = False         # você está digitando
        self._keys = 0              # máscara de "tem tecla apertada" da leitura anterior (nunca guardada)
        self._presses: list[float] = []
        self._typing_until = 0.0
        self._troll: Troll | None = None
        # atualização (ver update.py): conferida em segundo plano; o resultado volta pela thread principal
        self.update_available: str | None = None
        self.updating = False
        self.update_notice = ""
        self.update_notice_until = 0.0
        self._update_found = None
        self._update_result = None
        self._update_checked_at = -1e9
        self._update_thread = None

    # ------------------------------------------------------------ sem o Claude: você digitando
    def _pet_status(self, now: float) -> str:
        """O status que o pet mostra: o do Claude. Com o Claude parado e você digitando = "working"
        (o pet digita junto)."""
        self._watch_user(now)
        status = self.top.status if self.top else "idle"
        if status == "idle" and self.typing:
            return "working"
        return status

    def _watch_user(self, now: float) -> None:
        keys = self._keys_down() if self.cfg.type_along else None
        if keys is not None:
            new = bin(keys & ~self._keys).count("1")   # teclas que desceram desde a última olhada
            self._keys = keys
            if new:
                self._presses = [p for p in self._presses if now - p < TYPE_WINDOW] + [now] * new
                if len(self._presses) >= TYPE_KEYS:
                    self._typing_until = now + TYPE_HOLD
        self.typing = bool(self.cfg.type_along) and now < self._typing_until

    def _keys_down(self) -> int | None:
        """Máscara de bits das teclas apertadas agora (só pra contar teclas novas; o que cada bit é não
        importa), ou None se não dá pra saber. Cada toolkit implementa."""
        return None

    # ------------------------------------------------------------ sessões
    def _poll(self, now: float) -> None:
        if now - self.last_poll > 0.25:
            self.last_poll = now
            self.sessions = self.store.sessions()
            self.top = self.sessions[0] if self.sessions else None
            self._maybe_wake()
        self._watch_config(now)
        self._update_tick(now)

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

        if self.updating:
            return t("update.working")
        if time.monotonic() < self.update_notice_until and not self.pressed:
            return self.update_notice
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
        if self.typing and not any(s.status != "idle" for s in self.sessions):
            return t("bubble.with_you", name=name)
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
        if self.update_available and not self.updating:
            items.append(("item", t("menu.update", version=self.update_available), self._start_update, True))
        items.append(("item", t("menu.settings"), self._open_settings, True))
        if self.pet.forced_sleep:
            items.append(("item", t("menu.wake"), self._wake, True))
        else:
            items.append(("item", t("menu.sleep"), self._sleep, True))
        items.append(("item", t("menu.hide_30"), lambda: self._hide_for(30), True))
        items.append(("item", t("menu.hide_2h"), lambda: self._hide_for(120), True))
        items.append(("item", t("menu.quit"), self._quit, True))
        return items

    def _open_settings(self) -> None:
        """Abre a janela de Configurações (processo próprio, em Tk). Já aberta: não abre outra."""
        proc = getattr(self, "_settings_proc", None)
        if proc is not None and proc.poll() is None:
            return
        root = Path(__file__).resolve().parent.parent
        try:
            self._settings_proc = subprocess.Popen([sys.executable, "-m", "claude_pet.settings"], cwd=str(root))
        except OSError:
            self._settings_proc = None

    # ------------------------------------------------------------ atualização
    def _update_tick(self, now: float) -> None:
        from . import update
        if self._update_result is not None:            # a thread de atualizar terminou
            kind, value = self._update_result
            self._update_result, self.updating = None, False
            if kind == "ok":
                update.restart()
                self._quit()
                return
            self.update_notice, self.update_notice_until = t("update.failed", error=value), now + 12
        if update.REQUEST.exists():                    # pedido da janela de Configurações
            try:
                update.REQUEST.unlink()
            except OSError:
                pass
            self._start_update()
        found, self._update_found = self._update_found, None
        if found:
            self.update_available = found
            if update.read_state().get("notified") != found:   # avisa uma vez por versão
                update.write_state(notified=found)
                self.update_notice = t("update.bubble", version=found)
                self.update_notice_until = now + 15
        if not self.cfg.check_updates or not update.can_update():
            return
        thread = self._update_thread
        if now - self._update_checked_at > 3600 and not (thread and thread.is_alive()):
            self._update_checked_at = now          # check() só vai à rede a cada 12 h; aqui é só ler o update.json
            self._update_thread = threading.Thread(target=self._check_update_bg, daemon=True)
            self._update_thread.start()

    def _check_update_bg(self) -> None:
        from . import update
        try:
            self._update_found = update.check()
        except Exception:
            self._update_found = None

    def _start_update(self) -> None:
        from . import update
        if self.updating or not update.can_update():
            return
        self.updating = True

        def work():
            try:
                self._update_result = ("ok", update.apply())
            except Exception as e:   # sem rede, sem permissão...: avisa e segue na versão atual
                self._update_result = ("error", str(e) or e.__class__.__name__)

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ config.json mudou (janela de Configurações)
    def _watch_config(self, now: float) -> None:
        if now - getattr(self, "_cfg_checked", 0.0) < 0.5:
            return
        self._cfg_checked = now
        try:
            mtime = CONFIG_FILE.stat().st_mtime
        except OSError:
            mtime = None
        first = not hasattr(self, "_cfg_mtime")
        if not first and mtime == self._cfg_mtime:
            return
        self._cfg_mtime = mtime
        if not first:
            fresh = Config.load()
            for f in fields(Config):
                setattr(self.cfg, f.name, getattr(fresh, f.name))
        self._apply_config()

    def _apply_config(self) -> None:
        """Aplica no pet o que pode ter mudado: personagem, idioma e modo troll (o nome é lido na hora)."""
        i18n.set_language(self.cfg.language)
        self._use_skin(self.cfg.skin)
        if bool(self.cfg.troll) != self.troll.on:
            self.troll.enable(bool(self.cfg.troll), time.monotonic())

    def _use_skin(self, name: str) -> None:
        if name not in skins.available() or name == self.skin.name:
            return
        self.skin = skins.load(name)
        self.size = self.skin.canvas * self.skin.pixel_scale(self.cfg.scale)
        self.pet.set_skin(self.skin)   # solta e cai de novo no chão
        self._apply_skin()

    # ------------------------------------------------------------ cada toolkit implementa
    def _pointer(self):
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

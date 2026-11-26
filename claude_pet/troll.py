"""Modo troll: de vez em quando o pet apronta com o mouse. Só funciona com o modo ligado pelo menu, e
nunca quando o Claude precisa de você.

Pegadinhas:
  - "steal": pula no cursor, segura ele em cima da cabeça e sai correndo pelo chão.
  - "heavy": se pendura no cursor; o mouse fica pesado (anda devagar e é puxado pra baixo).

Segurança: a pegadinha não começa e é interrompida na hora se algum botão do mouse estiver apertado
(arrastando, selecionando texto...), se o Claude pedir atenção ou terminar, ou se você clicar no pet.
Um puxão forte no mouse durante o "steal" faz o pet largar o cursor. Cada uma dura poucos segundos.

Não depende de toolkit: `tick()` devolve onde o cursor deve ficar (ou None) e a janela move o cursor.
"""
from __future__ import annotations

import math
import random

PRANKS = ("steal", "heavy")
FIRST_DELAY = 4.0              # ao ligar o modo, a primeira pegadinha vem logo
EVERY = (35.0, 100.0)          # intervalo entre pegadinhas (s)
STEAL_TIME = 2.6
HEAVY_TIME = 5.0
RUN_SPEED = 470.0
HEAVY_DRAG = 0.3               # quanto do movimento do mouse passa (1 = normal)
HEAVY_PULL = 90.0              # px/s pra baixo enquanto ele está pendurado
YANK = 160.0                   # puxão que faz ele largar o cursor no "steal"


class Troll:
    def __init__(self, pet, rng: random.Random | None = None):
        self.pet = pet
        self.rng = rng or random.Random()
        self.on = False
        self.prank: str | None = None
        self.phase = ""
        self.next_at = 0.0
        self.until = 0.0
        self.cursor: tuple[float, float] | None = None   # onde a gente deixou o cursor no último tick
        self.leap = None                                  # (início, duração, x0, y0)
        self.dir = 1

    # ------------------------------------------------------------ liga/desliga
    def enable(self, on: bool, now: float) -> None:
        self.on = on
        if on:
            self.next_at = now + FIRST_DELAY
        else:
            self.stop()

    @property
    def active(self) -> bool:
        return self.prank is not None

    def stop(self) -> None:
        """Acaba a pegadinha e devolve o pet pra física normal."""
        pet = self.pet
        if self.prank == "heavy" and pet.mode == "drag":
            pet.release()
        elif pet.mode == "troll":
            pet.mode, pet.vx, pet.vy = "free", 0.0, 0.0
        if self.prank:
            pet.cheer(1.8)   # ri da cara de quem caiu
        self.prank = None
        self.cursor = None

    # ------------------------------------------------------------ geometria
    def _head(self) -> tuple[float, float]:
        """Onde fica o cursor "nas mãos" do pet: em cima da cabeça."""
        pet = self.pet
        s = pet.skin.pixel_scale(pet.cfg.scale)
        return pet.x + pet.size / 2, pet.y + max(0, pet.skin.hit[1] - 2) * s

    def _grip(self) -> tuple[float, float]:
        """Ponto do pet que fica preso no cursor quando ele se pendura (o pivô do "pendurado")."""
        pet, skin = self.pet, self.pet.skin
        s = skin.pixel_scale(pet.cfg.scale)
        px = skin.canvas - skin.pivot[0] if (skin.side_view and pet.direction < 0) else skin.pivot[0]
        return px * s, skin.pivot[1] * s

    def _clamp(self, x: float, y: float) -> tuple[float, float]:
        a = self.pet.area
        return min(max(x, a.x + 1), a.x + a.w - 2), min(max(y, a.y + 1), a.y + a.h - 2)

    # ------------------------------------------------------------ loop
    def tick(self, now: float, dt: float, pointer, status: str, buttons: bool, pressed: bool):
        """Chamado antes do pet.tick. Devolve (x, y) pra onde mover o cursor, ou None."""
        if not self.on:
            return None
        pet = self.pet
        blocked = buttons or pressed or status in ("attention", "done") or pet.forced_sleep or pointer is None
        if self.prank:
            if blocked or (pressed and pet.mode == "drag"):
                if pressed and self.prank == "heavy":
                    self.prank, self.cursor = None, None   # você pegou ele: o arraste é seu agora
                else:
                    self.stop()
                self.next_at = now + self.rng.uniform(*EVERY)
                return None
            return self._step(now, dt, pointer)
        if blocked or now < self.next_at or pet.mode != "edge" or not pet.on_floor:
            return None
        if pet.area_at(*pointer) != pet.area:   # cursor em outro monitor: deixa quieto
            return None
        self._start(self.rng.choice(PRANKS), now, pointer)
        return None

    def _start(self, prank: str, now: float, pointer) -> None:
        pet = self.pet
        pet.x, pet.y = pet.position()
        pet.mode = "troll"
        pet.troll_anim = ("walk", 1)
        self.prank, self.phase = prank, "leap"
        dist = math.hypot(pointer[0] - pet.x, pointer[1] - pet.y)
        self.leap = (now, min(0.9, max(0.35, dist / 1400)), pet.x, pet.y)
        self.cursor = None

    def _step(self, now: float, dt: float, pointer):
        pet = self.pet
        if self.phase == "leap":
            return self._leap(now, pointer)
        if self.prank == "steal":
            # puxão forte = largou
            if self.cursor and math.hypot(pointer[0] - self.cursor[0], pointer[1] - self.cursor[1]) > YANK:
                self.stop()
                self.next_at = now + self.rng.uniform(*EVERY)
                return None
            a = pet.area
            pet.vy = min(pet.vy + 1600 * dt, 900)
            pet.x += self.dir * RUN_SPEED * dt
            pet.y = min(pet.y + pet.vy * dt, pet.floor_y)
            if pet.x <= a.x or pet.x >= a.x + a.w - pet.size:   # bateu na borda: volta correndo
                pet.x = min(max(pet.x, a.x), a.x + a.w - pet.size)
                self.dir = -self.dir
            pet.direction = self.dir
            pet.troll_anim = ("walk", self.dir)
            if now > self.until:
                self.stop()
                self.next_at = now + self.rng.uniform(*EVERY)
                return None
            self.cursor = self._clamp(*self._head())
            return self.cursor
        # heavy: o movimento passa só em parte e ainda é puxado pra baixo
        last = self.cursor or pointer
        x = last[0] + (pointer[0] - last[0]) * HEAVY_DRAG
        y = last[1] + (pointer[1] - last[1]) * HEAVY_DRAG + HEAVY_PULL * dt
        self.cursor = self._clamp(x, y)
        pet.motion(*self.cursor)
        if now > self.until:
            self.stop()
            self.next_at = now + self.rng.uniform(*EVERY)
            return None
        return self.cursor

    def _leap(self, now: float, pointer):
        """Pulo em arco até o cursor (o alvo acompanha o cursor enquanto ele pula)."""
        pet = self.pet
        t0, dur, x0, y0 = self.leap
        k = min(1.0, (now - t0) / dur)
        if self.prank == "steal":
            gx, gy = pet.size / 2, self._head()[1] - pet.y
        else:
            gx, gy = self._grip()
        tx, ty = pointer[0] - gx, pointer[1] - gy
        pet.x = x0 + (tx - x0) * k
        pet.y = y0 + (ty - y0) * k - math.sin(math.pi * k) * 70
        pet.direction = 1 if tx >= x0 else -1
        pet.troll_anim = ("walk", pet.direction)
        if k < 1.0:
            return None
        # pegou!
        self.phase = "hold"
        if self.prank == "steal":
            a = pet.area
            self.dir = 1 if pointer[0] < a.x + a.w / 2 else -1   # corre pro lado mais longe
            pet.vy = 0.0
            self.until = now + STEAL_TIME
            self.cursor = self._clamp(*self._head())
            return self.cursor
        self.until = now + HEAVY_TIME
        pet.press(*pointer)
        pet.drag_offset = (gx, gy)
        pet.x, pet.y = pointer[0] - gx, pointer[1] - gy
        self.cursor = pointer
        return None

"""Comportamento do bichinho: onde ele está, o que está fazendo, qual animação tocar.

Sem GTK: recebe a área do monitor, o status do Claude e o mouse; devolve um Frame.

Movimento:
  - "edge": preso ao perímetro da área de trabalho do monitor, parametrizado por `s`
    (base esquerda→direita, parede direita subindo, teto direita→esquerda, parede esquerda descendo).
  - "free": solto (caindo/arremessado) até tocar o chão.
  - "drag": segurado pelo mouse.
Quando o Claude não está ocioso, ele desce para o chão (se estiver em parede/teto, solta e cai).
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Callable

from .config import Config
from .sprites import ANIMATIONS, CANVAS

GRAVITY = 2200.0


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass
class Frame:
    x: int
    y: int
    rotation: int        # graus: 0 chão, 270 parede direita, 180 teto, 90 parede esquerda
    anim: str
    frame: int
    look: int            # -1/0/1, para onde os olhos apontam
    status: str          # status visual (cor da antena)


class Pet:
    def __init__(self, cfg: Config, area: Rect, area_at: Callable[[float, float], Rect] | None = None,
                 rng: random.Random | None = None):
        self.cfg = cfg
        self.size = CANVAS * cfg.scale
        self.area = area
        self.area_at = area_at or (lambda x, y: self.area)
        self.rng = rng or random.Random()

        self.mode = "free"
        self.s = 0.0
        self.x = float(area.x + area.w * 0.7)
        self.y = float(area.y + area.h * 0.3)   # nasce caindo do meio da tela
        self.vx = self.vy = 0.0
        self.direction = 1

        self.status = "idle"
        self.prev_status = "idle"
        self.idle_action = "pause"
        self.action_until = 0.0
        self.target_s = 0.0
        self.anchor_s = 0.0
        self.celebrate_until = 0.0
        self.happy_until = 0.0
        self.last_activity = time.monotonic()

        self.anim = "dangle"
        self.anim_started = time.monotonic()
        self.look = 0
        self.jump = 0.0

        self.drag_offset = (0.0, 0.0)
        self.drag_trail: list[tuple[float, float, float]] = []
        self.hover_since: float | None = None

    # ------------------------------------------------------------ perímetro
    @property
    def seg(self) -> tuple[float, float]:
        return max(1.0, self.area.w - self.size), max(1.0, self.area.h - self.size)

    @property
    def perimeter(self) -> float:
        w, h = self.seg
        return 2 * (w + h)

    def edge_pos(self, s: float) -> tuple[float, float, int]:
        a, (w, h) = self.area, self.seg
        s %= self.perimeter
        if s < w:
            return a.x + s, a.y + h, 0
        s -= w
        if s < h:
            return a.x + w, a.y + h - s, 270
        s -= h
        if s < w:
            return a.x + w - s, a.y, 180
        s -= w
        return a.x, a.y + s, 90

    @property
    def on_floor(self) -> bool:
        return self.mode == "edge" and (self.s % self.perimeter) < self.seg[0]

    @property
    def floor_y(self) -> float:
        return self.area.y + self.area.h - self.size

    def _attach_floor(self) -> None:
        self.area = self.area_at(self.x + self.size / 2, self.y + self.size / 2)
        self.mode = "edge"
        self.s = min(max(self.x - self.area.x, 0.0), self.seg[0] - 0.5)  # canto direito ainda é chão
        self.vx = self.vy = 0.0
        self.y = self.floor_y

    def _let_go(self) -> None:
        self.x, self.y, _ = self.edge_pos(self.s)
        self.mode = "free"
        self.vx, self.vy = 0.0, 0.0

    # ------------------------------------------------------------ mouse
    def contains(self, px: float, py: float) -> bool:
        x, y = self.position()
        return x <= px <= x + self.size and y <= py <= y + self.size

    def press(self, px: float, py: float) -> None:
        x, y = self.position()
        self.mode = "drag"
        self.drag_offset = (px - x, py - y)
        self.drag_trail = [(time.monotonic(), px, py)]
        self.x, self.y = x, y

    def motion(self, px: float, py: float) -> None:
        if self.mode != "drag":
            return
        self.x, self.y = px - self.drag_offset[0], py - self.drag_offset[1]
        now = time.monotonic()
        self.drag_trail = [p for p in self.drag_trail if now - p[0] < 0.12] + [(now, px, py)]

    def release(self) -> bool:
        """Solta. Retorna True se foi um clique (quase não mexeu)."""
        if self.mode != "drag":
            return False
        t0, x0, y0 = self.drag_trail[0]
        t1, x1, y1 = self.drag_trail[-1]
        moved = math.hypot(x1 - x0, y1 - y0)
        dt = max(t1 - t0, 1e-3)
        self.mode = "free"
        self.vx = max(-1500.0, min(1500.0, (x1 - x0) / dt))
        self.vy = max(-1500.0, min(1500.0, (y1 - y0) / dt))
        self.last_activity = time.monotonic()
        if moved < 5:
            self.vx = self.vy = 0.0
            if abs(self.y - self.floor_y) < 2:
                self._attach_floor()
            return True
        return False

    def cheer(self, seconds: float = 2.5) -> None:
        self.happy_until = time.monotonic() + seconds
        self.last_activity = time.monotonic()

    # ------------------------------------------------------------ tick
    def position(self) -> tuple[float, float]:
        if self.mode == "edge":
            x, y, _ = self.edge_pos(self.s)
            return x, y
        return self.x, self.y

    def tick(self, dt: float, status: str, pointer: tuple[float, float] | None) -> Frame:
        now = time.monotonic()
        dt = min(dt, 0.1)
        self._update_status(status, now)
        self.jump = 0.0
        look = self.direction

        if self.mode == "drag":
            anim = "dangle"
        elif self.mode == "free":
            anim = self._physics(dt)
        else:
            if self.status != "idle" and not self.on_floor:
                self._let_go()
                anim = "dangle"
            else:
                anim, look = self._behave(dt, now, pointer)

        if anim != self.anim:
            self.anim, self.anim_started = anim, now
        fps, frames = ANIMATIONS[self.anim]
        frame = int((now - self.anim_started) * fps) % len(frames)

        x, y = self.position()
        rot = self.edge_pos(self.s)[2] if self.mode == "edge" else 0
        visual = "sleep" if self.anim == "sleep" else self.status
        return Frame(int(x), int(y - self.jump), rot, self.anim, frame, look, visual)

    def _update_status(self, status: str, now: float) -> None:
        if status != self.status:
            self.prev_status = self.status
            self.status = status
            self.last_activity = now
            self.idle_action, self.action_until = "pause", now + 1.0
            if status == "done":
                self.celebrate_until = now + self.cfg.celebrate_for
            if status == "thinking" and self.mode == "edge":
                self.anchor_s = min(self.s, self.seg[0] - 1)
        if status != "idle":
            self.last_activity = now

    def _physics(self, dt: float) -> str:
        self.vy += GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.995
        a = self.area_at(self.x + self.size / 2, self.y + self.size / 2)
        if self.x < a.x:
            self.x, self.vx = a.x, abs(self.vx) * 0.4
        if self.x > a.x + a.w - self.size:
            self.x, self.vx = a.x + a.w - self.size, -abs(self.vx) * 0.4
        if self.y < a.y:
            self.y, self.vy = a.y, 0.0
        self.area = a
        if self.y >= self.floor_y and self.vy >= 0:
            self._attach_floor()
            return "stand"
        return "dangle"

    def _walk_towards(self, target: float, dt: float, speed: float) -> bool:
        p = self.perimeter
        diff = (target - self.s) % p
        if diff > p / 2:
            diff -= p  # caminho mais curto ao redor do perímetro
        if abs(diff) < 1:
            self.s = target % p
            return True
        self.direction = 1 if diff > 0 else -1
        self.s = (self.s + self.direction * min(abs(diff), speed * dt)) % p
        return False

    def _behave(self, dt: float, now: float, pointer) -> tuple[str, int]:
        cfg = self.cfg
        cx, cy = self.position()
        cx += self.size / 2
        cy += self.size / 2

        # hover em cima = carinho
        if pointer and self.contains(*pointer):
            self.hover_since = self.hover_since or now
            if now - self.hover_since > cfg.hover_pet_time and now > self.happy_until:
                self.cheer()
        else:
            self.hover_since = None

        if now < self.happy_until and self.on_floor:
            return "happy", 0

        st = self.status
        if st == "attention":
            self.jump = abs(math.sin(now * 7)) * 10
            return "attention", 0
        if st == "done":
            if now < self.celebrate_until:
                self.jump = abs(math.sin(now * 9)) * 14
                return "celebrate", 0
            return "waiting", 0
        if st == "working":
            return "work", 0
        if st == "thinking":
            if now > self.action_until:
                self.idle_action = self.rng.choice(["pace", "pace", "stand"])
                self.action_until = now + self.rng.uniform(2.5, 5)
                self.target_s = min(max(self.anchor_s + self.rng.uniform(-60, 60), 0), self.seg[0] - 1)
            if self.idle_action == "pace" and not self._walk_towards(self.target_s, dt, cfg.walk_speed * 0.5):
                return "think_walk", self.direction
            return "think", 0

        # ---- ocioso ----
        near = pointer and math.hypot(pointer[0] - cx, pointer[1] - cy) < cfg.notice_radius
        if near:
            self.last_activity = now
            if self.idle_action == "sleep":
                self.idle_action, self.action_until = "pause", now + 2
            if self.on_floor:
                return "curious", (1 if pointer[0] > cx else -1)

        if self.on_floor and now - self.last_activity > cfg.sleep_after:
            self.idle_action = "sleep"
            return "sleep", 0

        if self.idle_action == "walk":
            if self._walk_towards(self.target_s, dt, cfg.walk_speed):
                self.idle_action, self.action_until = "pause", now + self.rng.uniform(1, 3)
            return "walk", self.direction

        if now > self.action_until:
            self._pick_idle_action(now)
        if self.idle_action == "sit" and self.on_floor:
            return "sit", 0
        return "stand", 0

    def _pick_idle_action(self, now: float) -> None:
        r = self.rng.random()
        if r < 0.55:
            self.idle_action = "walk"
            if self.rng.random() < self.cfg.climb_chance:
                self.target_s = self.rng.uniform(0, self.perimeter - 1)
            else:
                self.target_s = self.rng.uniform(0, self.seg[0] - 1)
        elif r < 0.8 and self.on_floor:
            self.idle_action, self.action_until = "sit", now + self.rng.uniform(4, 10)
        else:
            self.idle_action, self.action_until = "pause", now + self.rng.uniform(1.5, 4)

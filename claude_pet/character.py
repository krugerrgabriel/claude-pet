"""Comportamento do bichinho: onde ele está, o que está fazendo, qual animação tocar.

Sem GTK: recebe a área do monitor, o status do Claude e o mouse; devolve um Frame.

Movimento:
  - "edge": preso ao perímetro da área de trabalho do monitor, parametrizado por `s`
    (base esquerda→direita, parede direita subindo, teto direita→esquerda, parede esquerda descendo).
  - "free": solto (caindo/arremessado) até tocar o chão.
  - "drag": segurado pelo mouse.
  - "troll": controlado pelo modo troll (troll.py) durante uma pegadinha.
  - "fly": voando pela tela (só personagens com `flies`, enquanto o Claude trabalha).
Quando o Claude não está ocioso, ele desce para o chão (se estiver em parede/teto, solta e cai).
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Callable

from .config import Config

GRAVITY = 2200.0
CRY_TIME = (6.0, 9.0)   # segundos que chora no canto (sorteado entre os dois)


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
    facing: int = 1      # lado para onde o corpo está virado (skins PNG espelham)
    lean: float = 0.0    # inclinação de pêndulo enquanto é arrastado (px por linha)


class Pet:
    def __init__(self, cfg: Config, area: Rect, area_at: Callable[[float, float], Rect] | None = None,
                 rng: random.Random | None = None, skin=None,
                 neighbor: Callable[[Rect, int, float], Rect | None] | None = None):
        from .skins import RobotSkin
        self.cfg = cfg
        self.skin = skin or RobotSkin()
        self.size = self.skin.canvas * self.skin.pixel_scale(cfg.scale)
        self.area = area
        self.area_at = area_at or (lambda x, y: self.area)
        # neighbor(área, lado -1/+1, y): o monitor encostado nessa borda da área, nessa altura (ou None).
        # Arremessado contra uma borda com outro monitor do lado, ele atravessa em vez de quicar.
        self.neighbor = neighbor or (lambda area, side, y: None)
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
        self.forced_sleep = False   # "botar pra dormir": fica dormindo até o próximo prompt
        self.confused_until = 0.0   # tocando a animação "confused" (personagens que têm) até aqui
        self.next_confused = 0.0    # quando fica confuso de novo (0 = ainda não sorteou)
        # quando vai pro canto chorar (sorteado já na partida: o tempo do Claude trabalhando também conta,
        # e ele chora no primeiro momento parado ou esperando depois disso)
        self.next_cry = time.monotonic() + self.rng.uniform(0.5, 1.5) * cfg.cry_every if cfg.cry_every else 0.0
        self.cry_side = 1           # canto onde chora: -1 esquerdo, 1 direito (virado pra parede)

        self.anim = "dangle"
        self.anim_started = time.monotonic()
        self.look = 0
        self.jump = 0.0

        self.drag_offset = (0.0, 0.0)
        self.drag_trail: list[tuple[float, float, float]] = []
        self.hover_since: float | None = None
        self.lean = 0.0
        self.lean_v = 0.0
        self.troll_anim = ("walk", 1)   # (animação, olhar) que o modo troll pede no modo "troll"

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
        self.press_point = (px, py)
        self.x, self.y = x, y

    def motion(self, px: float, py: float) -> None:
        if self.mode != "drag":
            return
        self.x, self.y = px - self.drag_offset[0], py - self.drag_offset[1]
        now = time.monotonic()
        self.drag_trail = [p for p in self.drag_trail if now - p[0] < 0.12] + [(now, px, py)]

    def _recent_trail(self, window: float = 0.1):
        """Pontos do arraste nos últimos `window` s. Mouse parado = só o último ponto (velocidade 0)."""
        now = time.monotonic()
        recent = [p for p in self.drag_trail if now - p[0] <= window]
        return recent or self.drag_trail[-1:]

    def release(self) -> bool:
        """Solta. Retorna True se foi um clique (quase não mexeu)."""
        if self.mode != "drag":
            return False
        moved_total = math.hypot(self.drag_trail[-1][1] - self.press_point[0],
                                 self.drag_trail[-1][2] - self.press_point[1])
        self.drag_trail = self._recent_trail()
        t0, x0, y0 = self.drag_trail[0]
        t1, x1, y1 = self.drag_trail[-1]
        moved = moved_total
        dt = max(t1 - t0, 1e-3)
        if len(self.drag_trail) < 2:
            x1, y1 = x0, y0  # mouse estava parado: solta sem arremessar
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
        if self.forced_sleep:
            return
        if self.idle_action in ("to_corner", "cry"):       # chorando no canto: o carinho consola
            self.idle_action, self.action_until = "pause", time.monotonic() + seconds
        self.happy_until = time.monotonic() + seconds
        self.last_activity = time.monotonic()

    def sleep_now(self) -> None:
        """Para de passear e dorme no chão até wake()."""
        self.forced_sleep = True
        self.happy_until = 0.0
        self.idle_action = "sleep"

    def wake(self) -> None:
        if not self.forced_sleep:
            return
        self.forced_sleep = False
        now = time.monotonic()
        self.last_activity = now
        self.idle_action, self.action_until = "pause", now + 1.5

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

        self._swing(dt)
        wants_fly = self.skin.flies and self.status == "working" and not self.forced_sleep
        if self.mode == "fly" and not wants_fly:
            self._land()
        elif wants_fly and self.mode in ("edge", "free"):
            self._take_off(now)
        if self.mode == "drag":
            anim = "dangle"
        elif self.mode == "troll":
            anim, look = self.troll_anim
        elif self.mode == "fly":
            anim, look = self._fly(dt, now)
        elif self.mode == "free":
            anim = self._physics(dt)
        else:
            if (self.status != "idle" or self.forced_sleep) and not self.on_floor:
                self._let_go()
                anim = "dangle"
            elif self.forced_sleep:
                anim, look = "sleep", 0
            elif self._confused(now):
                anim, look = "confused", 0      # para onde está (não anda) até a animação acabar
            else:
                anim, look = self._behave(dt, now, pointer)

        if anim != self.anim:
            self.anim, self.anim_started = anim, now
        fps, count = self.skin.anim_info(self.anim)
        frame = int((now - self.anim_started) * fps) % count

        x, y = self.position()
        rot = self.edge_pos(self.s)[2] if self.mode == "edge" else 0
        visual = "sleep" if self.anim == "sleep" else self.status
        if look:
            self.direction = look
        return Frame(int(x), int(y - self.jump), rot, self.anim, frame, look, visual, self.direction,
                     self.lean if self.mode in ("drag", "free") else 0.0)

    def _confused(self, now: float) -> bool:
        """De vez em quando, do nada, fica confuso: larga o que está fazendo (andar, pensar, trabalhar,
        até o carinho), toca "confused" uma vez e volta. Só nos personagens que têm essa animação, só
        parado numa borda (no colo do mouse, caindo ou voando não) e nunca dormindo."""
        every = self.cfg.confused_every
        if not every or not self.skin.has_anim("confused"):
            return False
        if now < self.confused_until:
            return True
        if not self.next_confused:
            self.next_confused = now + self.rng.uniform(0.5, 1.5) * every
        if now < self.next_confused:
            return False
        self.next_confused = now + self.rng.uniform(0.5, 1.5) * every
        if self.anim == "sleep":                 # dormindo: deixa pra próxima
            return False
        fps, count = self.skin.anim_info("confused")
        self.confused_until = now + count / fps
        return True

    def _swing(self, dt: float) -> None:
        """Pêndulo: arrastando pra direita, o corpo fica pra trás (inclina pra esquerda) e balança."""
        target = 0.0
        trail = self._recent_trail() if self.mode == "drag" else []
        if len(trail) >= 2:
            t0, x0, _ = trail[0]
            t1, x1, _ = trail[-1]
            if t1 - t0 > 1e-3:
                target = max(-0.45, min(0.45, -(x1 - x0) / (t1 - t0) / 1400))
        acc = 70 * (target - self.lean) - 6 * self.lean_v
        self.lean_v += acc * dt
        self.lean = max(-0.6, min(0.6, self.lean + self.lean_v * dt))

    def set_skin(self, skin) -> None:
        """Troca de personagem: o tamanho muda, então ele solta e cai de novo no chão."""
        x, y = self.position()
        self.skin = skin
        self.size = skin.canvas * skin.pixel_scale(self.cfg.scale)
        self.mode, self.x, self.y = "free", x, min(y, self.floor_y)
        self.vx = self.vy = 0.0

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
        cy = self.y + self.size / 2
        # bate e volta na borda da tela, a não ser que do outro lado tenha outro monitor: aí passa direto
        if self.x < a.x and not self.neighbor(a, -1, cy):
            self.x, self.vx = a.x, abs(self.vx) * 0.4
        if self.x > a.x + a.w - self.size and not self.neighbor(a, 1, cy):
            self.x, self.vx = a.x + a.w - self.size, -abs(self.vx) * 0.4
        if self.y < a.y:
            self.y, self.vy = a.y, 0.0
        self.area = a
        if self.y >= self.floor_y and self.vy >= 0:
            self._attach_floor()
            return "stand"
        return "dangle"

    # ------------------------------------------------------------ voo
    def _take_off(self, now: float) -> None:
        self.x, self.y = self.position()
        self.mode = "fly"
        self.vx, self.vy = 0.0, -260.0   # impulso pra cima
        self._pick_fly_target(now)

    def _pick_fly_target(self, now: float) -> None:
        a = self.area
        self.fly_target = (self.rng.uniform(a.x, a.x + a.w - self.size),
                           self.rng.uniform(a.y + a.h * 0.05, a.y + a.h * 0.6 - self.size / 2))
        self.fly_until = now + self.rng.uniform(3, 7)

    def _land(self) -> None:
        """Para de voar: plana até o chão (a física faz o resto)."""
        self.mode = "free"
        self.vx *= 0.5
        self.vy = min(self.vy, 0.0)

    def _fly(self, dt: float, now: float) -> tuple[str, int]:
        """Voa em direção a um ponto aleatório da metade de cima da tela, fazendo curva suave."""
        self.area = self.area_at(self.x + self.size / 2, self.y + self.size / 2)
        tx, ty = self.fly_target
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 30 or now > self.fly_until:
            self._pick_fly_target(now)
        speed = self.cfg.walk_speed * 3.5
        want_vx = dx / max(dist, 1) * speed
        want_vy = dy / max(dist, 1) * speed * 0.6
        k = min(1.0, dt * 1.6)   # inércia: faz curva em vez de virar na hora
        self.vx += (want_vx - self.vx) * k
        self.vy += (want_vy - self.vy) * k
        self.x += self.vx * dt
        self.y += self.vy * dt + math.sin(now * 3) * 12 * dt   # sobe e desce de leve
        a = self.area
        self.x = min(max(self.x, a.x), a.x + a.w - self.size)
        self.y = min(max(self.y, a.y), self.floor_y)
        if abs(self.vx) > 20:
            self.direction = 1 if self.vx > 0 else -1
        return "work", self.direction

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
            if not self.skin.self_hop:
                self.jump = abs(math.sin(now * 7)) * 10
            return "attention", 0
        if st == "done":
            if now < self.celebrate_until:
                if not self.skin.self_hop:
                    self.jump = abs(math.sin(now * 9)) * 14
                return "celebrate", 0
            return self._cry(dt, now) or ("waiting", 0)      # esperando você: pode ir chorar no canto
        if st == "working":
            return "work", 0
        if st == "thinking":
            if now > self.action_until:
                self.idle_action = self.rng.choice(["pace", "pace", "stand"]) if self.skin.pace_thinking else "stand"
                self.action_until = now + self.rng.uniform(2.5, 5)
                self.target_s = min(max(self.anchor_s + self.rng.uniform(-60, 60), 0), self.seg[0] - 1)
            if self.idle_action == "pace" and not self._walk_towards(self.target_s, dt, cfg.walk_speed * 0.5):
                return "think_walk", self.direction
            return "think", 0

        # ---- ocioso ----
        crying = self._cry(dt, now)
        if crying:
            return crying

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
        resting = self.idle_action == "sit" or (self.idle_action == "pause" and self.skin.rest_sits)
        if resting and self.on_floor:
            return "sit", 0
        return "stand", 0

    def _cry(self, dt: float, now: float) -> tuple[str, int] | None:
        """De vez em quando, com o Claude parado ou esperando você (terminou, depois da comemoração), vai pro
        canto da tela mais perto, vira pra parede e chora um pouco ("cry"). Só nos personagens que têm essa
        animação, só saindo do chão e acordado. O Claude mudar de status (ver _update_status) ou um carinho
        (ver cheer) acabam com o choro."""
        every = self.cfg.cry_every
        if not every or not self.skin.has_anim("cry"):
            return None
        if self.idle_action == "to_corner":
            self.last_activity = now
            corner = 0.0 if self.cry_side < 0 else self.seg[0] - 1
            if not self._walk_towards(corner, dt, self.cfg.walk_speed):
                return "walk", self.direction
            self.idle_action, self.action_until = "cry", now + self.rng.uniform(*CRY_TIME)
        if self.idle_action == "cry":
            if now < self.action_until:
                self.last_activity = now
                return "cry", self.cry_side
            self.idle_action, self.action_until = "pause", now + self.rng.uniform(1.5, 3)
            return None
        if not self.next_cry:
            self.next_cry = now + self.rng.uniform(0.5, 1.5) * every
        if now < self.next_cry or not self.on_floor or self.idle_action == "sleep":
            return None
        self.next_cry = now + self.rng.uniform(0.5, 1.5) * every
        self.cry_side = -1 if self.s < self.seg[0] / 2 else 1
        self.idle_action = "to_corner"
        return self._cry(dt, now)

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

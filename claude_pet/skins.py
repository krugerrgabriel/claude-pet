"""Personagens: todos (os embutidos e os customizados) no mesmo formato, uma pasta por personagem.

    <id>/
      character.json   manifesto: {"format": 1, "id": "<id>", "name": {"pt": ..., "en": ...},
                       "description": {...}, "author": "...", "version": "..."}   (só format, id e name obrigatórios)
      character.py     o desenho (contrato abaixo); importa só de `claude_pet.*` e da biblioteca padrão
      frames.bin       opcional: quadros prontos de uma folha de sprites (claude_pet/folha.py)

Embutidos ficam em claude_pet/characters/. Customizados ficam fora da instalação, em
~/.config/claude-pet/characters/ (ver custom_dir()), e chegam num pacote .pet (zip da pasta; ver
claude_pet/charpack.py). Atualizar o claude-pet não mexe neles. O formato completo está no CLAUDE.md.

Todo personagem usa o mesmo canvas de CANVAS x CANVAS pixels lógicos com os pés na borda
de baixo (girar o canvas = andar na parede/teto) e tem as mesmas animações (ver ANIM_NAMES).

O character.py define:
  HIT           (x, y, w, h) área clicável, em pixels lógicos
  PIVOT         (x, y) ponto por onde o mouse "segura" (pêndulo ao arrastar)
  ANIMS         {animação: (fps, nº de quadros)} com todas de ANIM_NAMES; "confused" e "cry" são opcionais:
                quem tem "confused", de vez em quando para o que está fazendo e toca ela (ver Pet._confused e
                confused_every); quem tem "cry", de vez em quando vai pro canto da tela e chora (Pet._cry, cry_every);
                quem tem "transform" e "bat", de vez em quando se transforma (toca "transform"), voa pela tela
                tocando "bat", pousa e volta ao normal (toca "transform_back" ou, se não tiver, "transform" de
                novo): ver Pet._bat e bat_every
  render(pen, anim, frame, look, light)  desenha; `light` é a cor do status (a "luzinha"); `pen.body` é a
                cor do corpo escolhida na config (só o Bit usa)
  SIDE_VIEW     True = desenhado de perfil olhando pra direita; espelha ao andar pra esquerda (opcional)
  PACE_THINKING anda de um lado pro outro enquanto pensa (opcional; padrão True)
  OVERLAYS      {animação: nome do efeito ou None}     (opcional; padrão em DEFAULT_OVERLAYS)
  OVERLAY_AT    {efeito: (dx, dy)}                    (opcional; desloca o efeito)
  FLIES_WHEN_WORKING  True = trabalhando, sai voando pela tela tocando "work" (opcional)
  REST_SITS     True = no chão, toda pausa é sentado em vez de em pé (opcional; padrão False)
  SELF_HOP      True = o pulo de "attention"/"celebrate" já está desenhado nos quadros; o pet não pula
                por conta própria (opcional; padrão False)
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .pixel import CANVAS, STATUS_COLORS, Pen, overlay

FORMAT = 1
ROBOT = "robo"
BUILTIN_DIR = Path(__file__).resolve().parent / "characters"
ORDER = [ROBOT, "lagartixa", "gosminha", "capivara", "pato", "dragao", "pato_confuso", "capivara_dev", "vampiro_axolote"]
ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

ANIM_NAMES = ["stand", "walk", "sit", "sleep", "curious", "happy", "think", "think_walk", "work",
              "attention", "celebrate", "waiting", "dangle"]

DEFAULT_OVERLAYS = {"think": "thought", "think_walk": "thought", "sleep": "zzz", "attention": "bang",
                    "celebrate": "sparkle", "waiting": "check", "happy": "heart"}


def custom_dir() -> Path:
    """Onde ficam os personagens customizados (fora da instalação: atualizar não apaga)."""
    from .config import CONFIG_FILE
    return CONFIG_FILE.parent / "characters"


@dataclass
class Info:
    id: str
    path: Path
    manifest: dict
    builtin: bool

    def label(self) -> str:
        from .i18n import current
        name = self.manifest.get("name") or self.id
        if isinstance(name, dict):
            return str(name.get(current()) or name.get("en") or next(iter(name.values()), self.id))
        return str(name)

    def text(self, key: str) -> str:
        from .i18n import current
        value = self.manifest.get(key) or ""
        if isinstance(value, dict):
            return str(value.get(current()) or value.get("en") or next(iter(value.values()), ""))
        return str(value)


def read_manifest(folder: Path) -> dict:
    """Lê e confere o character.json de uma pasta de personagem. ValueError se algo estiver errado."""
    try:
        data = json.loads((folder / "character.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError("falta o character.json") from None
    except (OSError, ValueError) as e:
        raise ValueError(f"character.json inválido: {e}") from None
    if not isinstance(data, dict):
        raise ValueError("character.json precisa ser um objeto")
    if data.get("format") != FORMAT:
        raise ValueError(f"formato {data.get('format')!r} não suportado (esta versão lê o formato {FORMAT})")
    cid = data.get("id")
    if not isinstance(cid, str) or not ID_RE.match(cid):
        raise ValueError("id inválido: use letras minúsculas, números e _ (2 a 32, começando por letra)")
    if not data.get("name"):
        raise ValueError("falta o name")
    if not (folder / "character.py").is_file():
        raise ValueError("falta o character.py")
    return data


def _scan(folder: Path, builtin: bool) -> list[Info]:
    out = []
    if not folder.is_dir():
        return out
    for sub in sorted(folder.iterdir()):
        if not sub.is_dir() or sub.name.startswith((".", "_")):
            continue
        try:
            manifest = read_manifest(sub)
        except ValueError:
            continue
        if manifest["id"] != sub.name:
            continue
        out.append(Info(sub.name, sub, manifest, builtin))
    return out


def characters() -> dict[str, Info]:
    """Todos os personagens: os embutidos (na ordem de ORDER) e depois os customizados."""
    found = {i.id: i for i in _scan(BUILTIN_DIR, True)}
    out = {cid: found.pop(cid) for cid in ORDER if cid in found}
    out.update(found)
    for info in sorted(_scan(custom_dir(), False), key=lambda i: i.label().lower()):
        out.setdefault(info.id, info)   # mesmo id de um embutido: vale o embutido
    return out


def available() -> list[str]:
    return list(characters())


def info(name: str) -> Info | None:
    return characters().get(name)


def label(name: str) -> str:
    got = info(name)
    return got.label() if got else name


_MODULES: dict = {}


def load_module(info: Info):
    """Importa o character.py da pasta (com cache; recarrega se o arquivo mudar)."""
    path = info.path / "character.py"
    key = (str(path), path.stat().st_mtime)
    mod = _MODULES.get(key)
    if mod is None:
        name = f"claude_pet_character_{'b' if info.builtin else 'c'}_{info.id}"
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        _MODULES[key] = mod
    return mod


def check(info: Info) -> None:
    """Importa e desenha um quadro de cada animação. ValueError com o motivo se não der."""
    try:
        mod = load_module(info)
    except Exception as e:  # código do personagem: qualquer erro vira "personagem quebrado"
        raise ValueError(f"erro ao carregar o character.py: {e}") from None
    for attr in ("HIT", "PIVOT", "ANIMS", "render"):
        if not hasattr(mod, attr):
            raise ValueError(f"o character.py não define {attr}")
    missing = [a for a in ANIM_NAMES if a not in mod.ANIMS]
    if missing:
        raise ValueError("faltam animações: " + ", ".join(missing))
    from .raster import render
    skin = CharSkin(info)
    for anim in mod.ANIMS:
        try:
            fps, n = skin.anim_info(anim)
            assert fps > 0 and n > 0, "fps e nº de quadros precisam ser positivos"
            for frame in range(n):
                render(skin, anim, frame, 0, "idle", 1, "#5ec4b6")
        except Exception as e:
            raise ValueError(f"erro desenhando \"{anim}\": {e}") from None


def load(name: str = ROBOT) -> "Skin":
    """O personagem pronto pra desenhar. Não existe ou quebrou: volta pro Bit."""
    got = info(name)
    if got is not None:
        try:
            return CharSkin(got)
        except Exception as e:
            print(f"claude-pet: personagem {name!r} não carregou ({e}); usando o Bit", file=sys.stderr)
    return CharSkin(info(ROBOT))


def status_light(status: str) -> str:
    """Cor da 'luzinha' do status; pedindo atenção, pisca em branco."""
    color = STATUS_COLORS.get(status, STATUS_COLORS["idle"])
    if status == "attention" and int(time.monotonic() * 4) % 2:
        return "#ffffff"
    return color


class Skin:
    name = ""
    canvas = CANVAS
    hit = (0, 0, CANVAS, CANVAS)
    pivot = (CANVAS // 2, 0)
    pace_thinking = True
    rest_sits = False
    self_hop = False
    side_view = False
    flies = False          # True = sai voando pela tela enquanto o Claude trabalha

    def has_anim(self, anim: str) -> bool:
        """Tem essa animação? (as de ANIM_NAMES todos têm; "confused" é opcional)"""
        try:
            self.anim_info(anim)
        except KeyError:
            return False
        return True

    @staticmethod
    def pixel_scale(scale: int) -> int:
        return scale

    def anim_info(self, anim: str) -> tuple[float, int]:
        raise NotImplementedError

    def _render(self, cr, anim, frame, look, status, scale, body_color, facing) -> None:
        raise NotImplementedError

    def draw(self, cr, anim: str, frame: int, look: int, status: str, scale: int, body_color: str,
             lean: float = 0.0, facing: int = 1) -> None:
        if abs(lean) < 0.02:
            self._render(cr, anim, frame, look, status, scale, body_color, facing)
            return
        # pêndulo: gira o personagem inteiro em volta do ponto onde o mouse segura.
        # Desenha fora da tela e gira a imagem com filtro "pixel mais próximo": nítido, sem frestas.
        import cairo   # só no Linux (GTK); no Windows o desenho passa pelo raster.py

        n = self.canvas * scale
        off = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
        self._render(cairo.Context(off), anim, frame, look, status, scale, body_color, facing)
        angle = -math.atan(lean)  # corpo fica pra trás do movimento
        px_ = self.canvas - self.pivot[0] if (self.side_view and facing < 0) else self.pivot[0]
        pivot_x, pivot_y = px_ * scale, self.pivot[1] * scale
        cr.save()
        cr.translate(pivot_x, pivot_y)
        cr.rotate(angle)
        cr.translate(-pivot_x, -pivot_y)
        cr.set_source_surface(off, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_NEAREST)
        cr.paint()
        cr.restore()


class CharSkin(Skin):
    def __init__(self, info: Info):
        self.name = info.id
        self.info = info
        self.builtin = info.builtin
        self.mod = load_module(info)
        m = self.mod
        self.hit = m.HIT
        self.pivot = m.PIVOT
        self.pace_thinking = getattr(m, "PACE_THINKING", True)
        self.rest_sits = getattr(m, "REST_SITS", False)
        self.self_hop = getattr(m, "SELF_HOP", False)
        self.side_view = getattr(m, "SIDE_VIEW", False)
        self.flies = getattr(m, "FLIES_WHEN_WORKING", False)
        self.overlays = {**DEFAULT_OVERLAYS, **getattr(m, "OVERLAYS", {})}
        self.overlay_at = getattr(m, "OVERLAY_AT", {})

    def anim_info(self, anim: str) -> tuple[float, int]:
        return self.mod.ANIMS[anim]

    def _render(self, cr, anim, frame, look, status, scale, body_color, facing) -> None:
        _fps, n = self.mod.ANIMS[anim]
        frame %= n
        flip = self.side_view and facing < 0
        # de perfil, "olhar" é relativo ao lado pra onde ele está virado
        rel_look = look * (-1 if flip else 1) if self.side_view else look
        self.mod.render(Pen(cr, scale, flip=flip, body=body_color), anim, frame, rel_look, status_light(status))
        fx = self.overlays.get(anim)
        if fx:
            dx, dy = self.overlay_at.get(fx, (0, 0))
            overlay(Pen(cr, scale), fx, frame, dx, dy, mirror=flip)

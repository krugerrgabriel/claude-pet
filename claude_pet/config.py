"""Caminhos e parâmetros do Claude Pet.

Tudo aqui pode ser sobrescrito em ~/.config/claude-pet/config.json
(mesmos nomes de chave, em minúsculas).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path

CACHE_DIR = Path(os.environ.get("CLAUDE_PET_HOME", Path.home() / ".cache" / "claude-pet"))
SESSIONS_DIR = CACHE_DIR / "sessions"
LOCK_FILE = CACHE_DIR / "pet.lock"
DEFAULT_NAME = "Seu pet"
CONFIG_FILE = Path(os.environ.get("CLAUDE_PET_CONFIG", Path.home() / ".config" / "claude-pet" / "config.json"))


@dataclass
class Config:
    # Visual
    pet_name: str = ""             # vazio = "Seu pet"; muda pelo menu "Mudar nome…"
    skin: str = "robo"             # personagem: robo, lagartixa, gosminha, capivara
    scale: int = 3                 # tamanho de cada "pixel" do sprite
    fps: int = 30                  # taxa de atualização (movimento); animação tem seu próprio ritmo
    body_color: str = "#5ec4b6"
    monitor: int = -1              # -1 = monitor primário

    # Movimento
    walk_speed: float = 45.0       # px/s
    climb_chance: float = 0.25     # chance de ir para as paredes/teto quando ocioso
    sleep_after: float = 180.0     # s sem atividade (Claude + mouse) até dormir

    # Estados do Claude (segundos)
    thinking_timeout: float = 600.0   # sem eventos depois do prompt → considera ocioso (ex.: Esc)
    tool_timeout: float = 1800.0      # ferramenta rodando sem PostToolUse
    work_hold: float = 5.0            # depois de uma ferramenta, segura "trabalhando" no mínimo isso antes de "pensando"
    done_linger: float = 900.0        # quanto tempo o "terminou, te esperando" fica visível
    celebrate_for: float = 3.5        # duração da comemoração ao terminar
    session_stale: float = 6 * 3600   # remove sessões sem eventos há esse tempo

    # Interação
    notice_radius: float = 110.0      # cursor perto → ele olha / para
    hover_pet_time: float = 1.2       # cursor parado em cima → carinho

    extra: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return (self.pet_name or "").strip() or DEFAULT_NAME

    def save_key(self, key: str, value) -> None:
        """Grava uma chave no config.json preservando as outras."""
        setattr(self, key, value)
        try:
            data = json.loads(CONFIG_FILE.read_text())
        except (OSError, ValueError):
            data = {}
        data[key] = value
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        try:
            data = json.loads(CONFIG_FILE.read_text())
        except (OSError, ValueError):
            return cfg
        names = {f.name for f in fields(cls)}
        for key, value in data.items():
            if key in names:
                setattr(cfg, key, value)
            else:
                cfg.extra[key] = value
        return cfg

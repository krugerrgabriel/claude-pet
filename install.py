#!/usr/bin/env python3
"""Instala/desinstala o Claude Pet.

  python3 install.py            # hooks no ~/.claude/settings.json + autostart + comando `claude-pet`
  python3 install.py --uninstall

Faz backup do settings.json antes de mexer e só adiciona/remove as entradas do pet
(identificadas pelo caminho do hook); os outros hooks ficam intactos.
"""
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOOK = ROOT / "hooks" / "claude_pet_hook.py"
SETTINGS = Path.home() / ".claude" / "settings.json"
AUTOSTART = Path.home() / ".config" / "autostart" / "claude-pet.desktop"
LAUNCHER = Path.home() / ".local" / "bin" / "claude-pet"

EVENTS = ["SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse",
          "Notification", "Stop", "SubagentStop", "PreCompact"]
COMMAND = f'python3 "{HOOK}"'
MARK = "claude_pet_hook.py"


def _is_ours(group: dict) -> bool:
    return any(MARK in h.get("command", "") for h in group.get("hooks", []))


def load_settings() -> dict:
    if not SETTINGS.exists():
        return {}
    return json.loads(SETTINGS.read_text())


def save_settings(data: dict) -> None:
    if SETTINGS.exists():
        backup = SETTINGS.with_name(f"settings.json.bak-claude-pet-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(SETTINGS, backup)
        print(f"backup: {backup}")
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(SETTINGS)


def remove_hooks(data: dict) -> int:
    removed = 0
    hooks = data.get("hooks", {})
    for event in list(hooks):
        before = len(hooks[event])
        hooks[event] = [g for g in hooks[event] if not _is_ours(g)]
        removed += before - len(hooks[event])
        if not hooks[event]:
            del hooks[event]
    if "hooks" in data and not data["hooks"]:
        del data["hooks"]
    return removed


def install() -> None:
    data = load_settings()
    remove_hooks(data)  # idempotente
    hooks = data.setdefault("hooks", {})
    for event in EVENTS:
        hooks.setdefault(event, []).append({"hooks": [{"type": "command", "command": COMMAND, "timeout": 5}]})
    save_settings(data)
    print(f"hooks adicionados em {SETTINGS} ({len(EVENTS)} eventos)")

    LAUNCHER.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHER.write_text(f'#!/bin/sh\ncd "{ROOT}" && exec python3 -m claude_pet "$@"\n')
    LAUNCHER.chmod(0o755)
    print(f"comando: {LAUNCHER}")

    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text(
        "[Desktop Entry]\nType=Application\nName=Claude Pet\n"
        "Comment=Bichinho que mostra o status do Claude Code\n"
        f"Exec={LAUNCHER}\nX-GNOME-Autostart-enabled=true\nX-GNOME-Autostart-Delay=5\nNoDisplay=false\n"
    )
    print(f"autostart: {AUTOSTART}")
    print("\nPronto. Rode `claude-pet` (ou faça logout/login). Sessões do Claude Code já abertas")
    print("só passam a reportar depois de reiniciadas (hooks são lidos na inicialização).")


def uninstall() -> None:
    data = load_settings()
    n = remove_hooks(data)
    if n:
        save_settings(data)
    print(f"{n} entradas de hook removidas")
    for p in (AUTOSTART, LAUNCHER):
        if p.exists():
            p.unlink()
            print(f"removido: {p}")


if __name__ == "__main__":
    uninstall() if "--uninstall" in sys.argv else install()

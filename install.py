#!/usr/bin/env python3
"""Instala/desinstala o Claude Pet.

  python3 install.py            # hooks no ~/.claude/settings.json + autostart + comando `claude-pet`
  python3 install.py --uninstall
  python3 install.py --update      # o que a atualização automática roda: refaz hooks/atalhos, não abre o pet

No Windows (py install.py): hooks + atalho no Menu Iniciar e na Inicialização, e já abre o pet.

Faz backup do settings.json antes de mexer e só adiciona/remove as entradas do pet
(identificadas pelo caminho do hook); os outros hooks ficam intactos.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WINDOWS = os.name == "nt"

ROOT = Path(__file__).resolve().parent
HOOK = ROOT / "hooks" / "claude_pet_hook.py"
SETTINGS = Path.home() / ".claude" / "settings.json"
AUTOSTART = Path.home() / ".config" / "autostart" / "claude-pet.desktop"
LAUNCHER = Path.home() / ".local" / "bin" / "claude-pet"

EVENTS = ["SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse",
          "PostToolUseFailure", "PermissionRequest", "Notification", "Stop", "SubagentStart", "SubagentStop", "PreCompact"]


def _hook_command() -> str:
    if not WINDOWS:
        return f'python3 "{HOOK}"'
    # python.exe (não o pythonw: o hook lê o evento pelo stdin). Caminho curto 8.3 com "/" e sem aspas
    # funciona igual no Git Bash, no cmd e no PowerShell, que é onde o Claude Code pode rodar o hook.
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        exe = exe.with_name("python.exe")
    sys.path.insert(0, str(ROOT))
    from claude_pet.winsys import short_path
    # só a pasta vira 8.3: o nome do arquivo fica inteiro (o uninstall acha o hook por ele)
    parts = [short_path(str(exe.parent)) + "/" + exe.name, short_path(str(HOOK.parent)) + "/" + HOOK.name]
    if any(" " in p for p in parts):   # sem nomes curtos no disco: aspas (Git Bash e cmd entendem)
        return " ".join(f'"{p}"'.replace("\\", "/") for p in parts)
    return " ".join(p.replace("\\", "/") for p in parts)


COMMAND = _hook_command()
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

    if WINDOWS:
        install_windows()
        return

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
    if "--update" in sys.argv:
        return
    print("\nPronto. Rode `claude-pet` (ou faça logout/login). Sessões do Claude Code já abertas")
    print("só passam a reportar depois de reiniciadas (hooks são lidos na inicialização).")


# ---------------------------------------------------------------- Windows
def _start_menu() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


WIN_SHORTCUTS = [_start_menu() / "Claude Pet.lnk", _start_menu() / "Startup" / "Claude Pet.lnk"]


def _pythonw() -> Path:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.exists() else exe


def _shortcut(path: Path) -> None:
    """Atalho .lnk via PowerShell (WScript.Shell): pythonw -m claude_pet, sem janela de console."""
    path.parent.mkdir(parents=True, exist_ok=True)

    def q(v) -> str:
        return "'" + str(v).replace("'", "''") + "'"

    script = (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({q(path)}); "
              f"$s.TargetPath = {q(_pythonw())}; $s.Arguments = '-m claude_pet'; "
              f"$s.WorkingDirectory = {q(ROOT)}; $s.Description = 'Claude Pet'; $s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def install_windows() -> None:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("\nAVISO: este Python não tem Tk (tkinter). Instale o Python do python.org ou pelo winget:")
        print("  winget install Python.Python.3.12")
    for lnk in WIN_SHORTCUTS:
        try:
            _shortcut(lnk)
            print(f"atalho: {lnk}")
        except (OSError, subprocess.SubprocessError) as e:
            print(f"não consegui criar o atalho {lnk}: {e}")
    if "--update" in sys.argv:
        return
    subprocess.Popen([str(_pythonw()), "-m", "claude_pet"], cwd=str(ROOT),
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     close_fds=True)
    print("\nPronto, o pet já abriu e vai abrir sozinho quando você entrar no Windows.")
    print("Sessões do Claude Code já abertas só passam a reportar depois de reiniciadas.")


def uninstall() -> None:
    data = load_settings()
    n = remove_hooks(data)
    if n:
        save_settings(data)
    print(f"{n} entradas de hook removidas")
    for p in (WIN_SHORTCUTS if WINDOWS else (AUTOSTART, LAUNCHER)):
        if p.exists():
            p.unlink()
            print(f"removido: {p}")


if __name__ == "__main__":
    uninstall() if "--uninstall" in sys.argv else install()

"""Traz para frente a janela do terminal onde a sessão do Claude Code está rodando (X11 + wmctrl)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _ancestors(pid: int) -> list[int]:
    chain = []
    while pid > 1 and len(chain) < 30:
        chain.append(pid)
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            pid = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return chain


def focus_session(claude_pid: int, project: str = "") -> bool:
    if not shutil.which("wmctrl") or claude_pid <= 0:
        return False
    try:
        out = subprocess.run(["wmctrl", "-lp"], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return False

    chain = _ancestors(claude_pid)
    rank = {pid: i for i, pid in enumerate(chain)}  # mais perto do claude = melhor
    candidates = []
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        win_id, _desk, pid_s = parts[0], parts[1], parts[2]
        title = parts[4] if len(parts) > 4 else ""
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        if pid in rank:
            title_bonus = 0 if project and project.lower() in title.lower() else 1
            candidates.append((rank[pid], title_bonus, win_id))
    if not candidates:
        return False
    candidates.sort()
    try:
        subprocess.run(["wmctrl", "-ia", candidates[0][2]], timeout=2)
        return True
    except (OSError, subprocess.SubprocessError):
        return False

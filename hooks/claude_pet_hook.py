#!/usr/bin/env python3
"""Hook do Claude Code → arquivo de estado do Claude Pet.

Recebe o JSON do evento no stdin e grava ~/.cache/claude-pet/sessions/<session_id>.json.
Regras: só stdlib, rápido, e NUNCA falha (sempre exit 0, nada no stdout) para não
interferir no Claude Code.
"""
import json
import os
import sys
import time
from pathlib import Path

SESSIONS_DIR = Path(os.environ.get("CLAUDE_PET_HOME", Path.home() / ".cache" / "claude-pet")) / "sessions"

# evento do Claude Code → status do pet
EVENT_STATUS = {
    "SessionStart": "idle",
    "UserPromptSubmit": "thinking",
    "PreToolUse": "working",
    "PostToolUse": "thinking",
    "PostToolUseFailure": "thinking",
    "PreCompact": "working",
    "SubagentStop": None,      # subagente terminou, a sessão principal continua: só atualiza o ts
    "Stop": "done",
    "Notification": "attention",
    "PermissionRequest": "attention",
}


def find_claude_pid() -> int:
    """Sobe na árvore de processos até achar o processo `claude`."""
    pid = os.getppid()
    for _ in range(8):
        try:
            comm = Path(f"/proc/{pid}/comm").read_text().strip()
            if comm == "claude" or "claude" in Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="ignore").split("\0")[0]:
                return pid
            stat = Path(f"/proc/{pid}/stat").read_text()
            pid = int(stat.rsplit(")", 1)[1].split()[1])
            if pid <= 1:
                break
        except (OSError, ValueError, IndexError):
            break
    return 0


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    session_id = str(payload.get("session_id") or "unknown")
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")[:80] or "unknown"
    event = payload.get("hook_event_name", "")
    path = SESSIONS_DIR / f"{safe_id}.json"

    if event == "SessionEnd":
        try:
            path.unlink()
        except OSError:
            pass
        return

    try:
        previous = json.loads(path.read_text())
    except (OSError, ValueError):
        previous = {}

    status = EVENT_STATUS.get(event, previous.get("status", "idle"))
    if status is None:
        status = previous.get("status", "thinking")

    # "idle_prompt" = Claude parado esperando você digitar (já terminou); não é pedido de permissão
    notification_type = payload.get("notification_type", "")
    message = payload.get("message", "")
    if event == "Notification" and notification_type == "idle_prompt":
        status = "done" if previous.get("status") in ("done", "idle", None) else previous.get("status")

    state = {
        "session_id": session_id,
        "status": status,
        "event": event,
        "tool": payload.get("tool_name", "") if event in ("PreToolUse", "PermissionRequest") else ("compact" if event == "PreCompact" else ""),
        "message": message if status == "attention" else "",
        "cwd": payload.get("cwd") or previous.get("cwd", ""),
        "claude_pid": previous.get("claude_pid") or find_claude_pid(),
        "ts": time.time(),
        "since": previous.get("since") if previous.get("status") == status else time.time(),
    }

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(state))
    os.replace(tmp, path)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — um hook quebrado não pode atrapalhar o Claude Code
        pass
    sys.exit(0)

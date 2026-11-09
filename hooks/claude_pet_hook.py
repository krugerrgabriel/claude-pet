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
    "SubagentStart": None,     # subagentes são tratados à parte (ver `agents` em main)
    "SubagentStop": None,
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


# mensagens que o próprio Claude Code injeta como "prompt" quando um subagente termina
SYSTEM_PROMPTS = ("<task-notification", "<agent-message")
WAKE_GRACE = 15.0   # s de "pensando" depois do último subagente, esperando o Claude ser acordado
AGENT_STALE = 1800  # s sem notícia de um subagente: considera que ele morreu (não segura o pet pra sempre)


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

    now = time.time()
    agent_id = str(payload.get("agent_id") or "")
    notification_type = payload.get("notification_type", "")
    message = payload.get("message", "")
    asks_you = event == "PermissionRequest" or (event == "Notification" and notification_type != "idle_prompt")

    # Subagentes mandam eventos com o MESMO session_id da conversa, mas com agent_id.
    # Guardamos quais estão rodando; enquanto houver algum, a conversa não "terminou".
    agents = {k: v for k, v in (previous.get("agents") or {}).items() if now - float(v) < AGENT_STALE}
    main_status = previous.get("main_status") or previous.get("status") or "idle"
    attention_from = previous.get("attention_from", "")
    waking_until = 0.0

    if agent_id:
        if event == "SubagentStop":
            agents.pop(agent_id, None)
            if not agents and main_status == "done":
                # a conversa já tinha parado esperando os subagentes; o Claude costuma ser acordado logo em
                # seguida. Mostra "pensando" só por uns segundos: se o aviso já tinha chegado antes deste
                # evento (corrida), ninguém mais escreve aqui e o pet volta sozinho pra "terminou".
                waking_until = now + WAKE_GRACE
        else:
            agents[agent_id] = now
        if asks_you:
            main_status, attention_from = "attention", agent_id
        elif main_status == "attention" and attention_from == agent_id and event != "SubagentStop":
            main_status = "thinking"  # você respondeu e o subagente seguiu
    else:
        new = EVENT_STATUS.get(event, main_status)
        if event == "Notification" and notification_type == "idle_prompt":
            # "idle_prompt" = Claude parado esperando você digitar (já terminou); não é pedido de permissão
            new = "done" if main_status in ("done", "idle") else main_status
        if new is not None:
            main_status = new
        if main_status == "attention":
            attention_from = "main"

    # o que o pet mostra: a conversa manda; subagentes só seguram "trabalhando" quando ela já parou
    # (senão aparece "terminou" com eles ainda rodando). Com a conversa ativa, pensando continua pensando.
    status = main_status
    if agents and status in ("idle", "done"):
        status = "working"
    elif waking_until:
        status = "thinking"

    # aviso de subagente terminado também chega como UserPromptSubmit; não é prompt seu
    prompt = str(payload.get("prompt") or "")
    is_your_prompt = event == "UserPromptSubmit" and not prompt.lstrip().startswith(SYSTEM_PROMPTS)

    state = {
        "session_id": session_id,
        "status": status,
        "main_status": main_status,
        "agents": agents,
        "attention_from": attention_from if main_status == "attention" else "",
        "waking_until": waking_until,
        # quando a conversa parou: o "já vi que terminou" fica preso a isso, não ao último evento qualquer
        "done_ts": (now if (event == "Stop" and not agent_id) or previous.get("main_status") != "done"
                    else previous.get("done_ts") or now) if main_status == "done" else 0,
        "event": event,
        "tool": payload.get("tool_name", "") if event in ("PreToolUse", "PermissionRequest") else ("compact" if event == "PreCompact" else ""),
        "message": message if status == "attention" else "",
        "cwd": payload.get("cwd") or previous.get("cwd", ""),
        "transcript_path": payload.get("transcript_path") or previous.get("transcript_path", ""),
        "claude_pid": previous.get("claude_pid") or find_claude_pid(),
        "ts": now,
        "since": previous.get("since") if previous.get("status") == status else now,
        # último prompt seu: acorda o pet do "botar pra dormir"
        "prompt_ts": now if is_your_prompt else previous.get("prompt_ts", 0),
        # última ferramenta iniciada (conversa ou subagente): o pet segura "trabalhando" uns segundos (debounce)
        "work_ts": now if event in ("PreToolUse", "PreCompact") else previous.get("work_ts", 0),
    }

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(state))
    os.replace(tmp, path)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001: um hook quebrado não pode atrapalhar o Claude Code
        pass
    sys.exit(0)

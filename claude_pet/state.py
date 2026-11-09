"""Lê os arquivos que o hook grava e resume o estado de todas as sessões.

Sem GTK aqui: dá pra testar isolado.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .config import SESSIONS_DIR, Config

# maior = mais urgente; é o que o bichinho mostra quando há várias sessões
PRIORITY = {"idle": 0, "thinking": 1, "working": 2, "done": 3, "attention": 4}


@dataclass
class Session:
    session_id: str
    status: str
    tool: str
    message: str
    cwd: str
    claude_pid: int
    ts: float
    since: float
    prompt_ts: float = 0.0
    done_ts: float = 0.0

    @property
    def ack_key(self) -> float:
        """Identifica "este terminou": o momento em que a conversa parou (cai pro ts em arquivos antigos)."""
        return self.done_ts or self.ts

    @property
    def project(self) -> str:
        return os.path.basename(self.cwd.rstrip("/")) or "~"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return True  # sem pid registrado: não dá pra saber, assume vivo
    return Path(f"/proc/{pid}").exists()


class StateStore:
    def __init__(self, cfg: Config, directory: Path = SESSIONS_DIR):
        self.cfg = cfg
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[float, dict]] = {}
        # session_id → ts do evento "done" já visto; fica em disco pra sobreviver a reinício do pet
        self._acked_file = self.dir.parent / "acked.json"
        self._acked: dict[str, float] = self._load_acked()

    def _load_acked(self) -> dict[str, float]:
        try:
            data = json.loads(self._acked_file.read_text())
            return {str(k): float(v) for k, v in data.items()}
        except (OSError, ValueError, AttributeError, TypeError):
            return {}

    def _save_acked(self) -> None:
        try:
            tmp = self._acked_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._acked))
            os.replace(tmp, self._acked_file)
        except OSError:
            pass

    # ---------- leitura ----------
    def _read_raw(self) -> list[dict]:
        seen = set()
        out = []
        try:
            entries = list(os.scandir(self.dir))
        except OSError:
            return out
        for entry in entries:
            if not entry.name.endswith(".json"):
                continue
            seen.add(entry.name)
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            cached = self._cache.get(entry.name)
            if cached and cached[0] == mtime:
                out.append(cached[1])
                continue
            try:
                data = json.loads(Path(entry.path).read_text())
            except (OSError, ValueError):
                continue
            self._cache[entry.name] = (mtime, data)
            out.append(data)
        for name in list(self._cache):
            if name not in seen:
                del self._cache[name]
        return out

    def _effective_status(self, d: dict, now: float) -> str:
        status = d.get("status", "idle")
        age = now - float(d.get("ts", 0))
        if status == "thinking" and d.get("main_status") == "done" and now > float(d.get("waking_until") or 0):
            status = "done"  # esperou o Claude ser acordado e ele não foi: terminou mesmo
        if status == "thinking" and age > self.cfg.thinking_timeout:
            return "idle"
        # debounce: o Claude alterna ferramenta/pensamento a cada segundo; sem isso o pet fica pisca-pisca
        if status == "thinking" and now - float(d.get("work_ts") or 0) < self.cfg.work_hold:
            return "working"
        if status == "working" and age > self.cfg.tool_timeout:
            return "idle"
        if status == "done":
            key = float(d.get("done_ts") or d.get("ts", 0))
            if now - key > self.cfg.done_linger or self._acked.get(d.get("session_id")) == key:
                return "idle"
        return status

    def sessions(self) -> list[Session]:
        now = time.time()
        result = []
        for d in self._read_raw():
            pid = int(d.get("claude_pid") or 0)
            age = now - float(d.get("ts", 0))
            if not _pid_alive(pid) or age > self.cfg.session_stale:
                self._remove(d.get("session_id", ""))
                continue
            result.append(Session(
                session_id=d.get("session_id", "?"),
                status=self._effective_status(d, now),
                tool=d.get("tool", ""),
                message=d.get("message", ""),
                cwd=d.get("cwd", ""),
                claude_pid=pid,
                ts=float(d.get("ts", 0)),
                since=float(d.get("since") or d.get("ts", 0)),
                prompt_ts=float(d.get("prompt_ts") or 0),
                done_ts=float(d.get("done_ts") or 0),
            ))
        live = {s.session_id for s in result}
        if any(sid not in live for sid in self._acked):  # sessões encerradas pelo SessionEnd
            self._acked = {sid: ts for sid, ts in self._acked.items() if sid in live}
            self._save_acked()
        result.sort(key=lambda s: (PRIORITY.get(s.status, 0), s.ts), reverse=True)
        return result

    def top(self) -> Session | None:
        sessions = self.sessions()
        return sessions[0] if sessions else None

    # ---------- ações ----------
    def acknowledge(self, session: Session) -> None:
        """Você viu o 'terminou': o bichinho volta a ficar ocioso para essa sessão."""
        if session.status == "done" and self._acked.get(session.session_id) != session.ack_key:
            self._acked[session.session_id] = session.ack_key
            self._save_acked()

    def _remove(self, session_id: str) -> None:
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:80]
        if safe:
            try:
                (self.dir / f"{safe}.json").unlink()
            except OSError:
                pass
        if self._acked.pop(session_id, None) is not None:
            self._save_acked()

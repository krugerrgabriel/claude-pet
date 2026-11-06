"""Lê os arquivos que o hook grava e resume o estado de todas as sessões.

Sem GTK aqui: dá pra testar isolado.
"""
from __future__ import annotations

import json
import os
import re
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
    title: str = ""

    @property
    def project(self) -> str:
        return os.path.basename(self.cwd.rstrip("/")) or "~"

    @property
    def name(self) -> str:
        """Nome da aba do Claude Code (título da sessão); sem título, o nome da pasta."""
        name = self.title or self.project
        return name if len(name) <= 40 else name[:39] + "…"


_TITLE_RE = re.compile(rb'"(customTitle|aiTitle)":\s*"((?:[^"\\]|\\.)*)"')


def read_title(path: str, tail_bytes: int = 512 * 1024, max_bytes: int = 64 * 1024 * 1024) -> str:
    """Último título gravado no transcript (.jsonl). Título manual vence o gerado pela IA."""
    try:
        with open(path, "rb") as fh:
            size = fh.seek(0, os.SEEK_END)
            for chunk in (tail_bytes, max_bytes):
                fh.seek(max(0, size - chunk))
                found = {k: v for k, v in _TITLE_RE.findall(fh.read(chunk))}
                if found or chunk >= size:
                    break
    except OSError:
        return ""
    raw = found.get(b"customTitle") or found.get(b"aiTitle")
    if not raw:
        return ""
    try:
        return json.loads(b'"' + raw + b'"')
    except ValueError:
        return ""


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
        self._acked: dict[str, float] = {}  # session_id → ts do evento "done" já visto
        self._titles: dict[str, tuple[float, str]] = {}  # session_id → (lido em, título)

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
        if status == "thinking" and age > self.cfg.thinking_timeout:
            return "idle"
        if status == "working" and age > self.cfg.tool_timeout:
            return "idle"
        if status == "done":
            if age > self.cfg.done_linger or self._acked.get(d.get("session_id")) == d.get("ts"):
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
                title=self._title(d, now),
            ))
        result.sort(key=lambda s: (PRIORITY.get(s.status, 0), s.ts), reverse=True)
        return result

    def _title(self, d: dict, now: float) -> str:
        sid, path = d.get("session_id", ""), d.get("transcript_path", "")
        cached = self._titles.get(sid)
        if cached and now - cached[0] < 30:
            return cached[1]
        title = read_title(path) if path else ""
        self._titles[sid] = (now, title)
        return title

    def top(self) -> Session | None:
        sessions = self.sessions()
        return sessions[0] if sessions else None

    # ---------- ações ----------
    def acknowledge(self, session: Session) -> None:
        """Você viu o 'terminou': o bichinho volta a ficar ocioso para essa sessão."""
        if session.status == "done":
            self._acked[session.session_id] = session.ts

    def _remove(self, session_id: str) -> None:
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:80]
        if safe:
            try:
                (self.dir / f"{safe}.json").unlink()
            except OSError:
                pass

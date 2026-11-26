"""Atualização: confere se tem versão nova na última release do GitHub e atualiza a instalação.

- `check()` pergunta pra API do GitHub no máximo a cada 12 h (guarda a resposta em update.json, do lado
  do config.json). Só manda o pedido HTTP com um User-Agent genérico do claude-pet, nada do usuário.
- `apply()` baixa o pacote da release (tar.gz no Linux, zip no Windows), troca os arquivos da instalação
  e roda `install.py --update` (refaz hooks e atalhos sem abrir outro pet). Os personagens customizados
  e a config ficam em ~/.config/claude-pet, fora da instalação: nada disso é tocado.
- Rodando de um clone do git (tem .git), não atualiza sozinho: lá é `git pull`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from . import __version__
from .config import CONFIG_FILE

REPO = "krugerrgabriel/claude-pet"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "claude-pet.zip" if os.name == "nt" else "claude-pet.tar.gz"
DOWNLOAD = f"https://github.com/{REPO}/releases/latest/download/{ASSET}"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ROOT = Path(__file__).resolve().parent.parent
STATE = CONFIG_FILE.parent / "update.json"
REQUEST = CONFIG_FILE.parent / "update-request"    # a janela de Configurações pede a atualização pro pet
EVERY = 12 * 3600
PARTS = ("claude_pet", "hooks", "install.py", "LICENSE", "README.md", "README.pt-BR.md", "CLAUDE.md")
USER_AGENT = f"claude-pet/{__version__}"


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def newer(a: str, b: str) -> bool:
    return version_tuple(a) > version_tuple(b)


def is_git_checkout(root: Path = ROOT) -> bool:
    return (root / ".git").exists()


def can_update(root: Path = ROOT) -> bool:
    return not is_git_checkout(root) and (root / "install.py").is_file() and os.access(root, os.W_OK)


def read_state() -> dict:
    try:
        data = json.loads(STATE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(**kw) -> None:
    data = {**read_state(), **kw}
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(data, indent=2) + "\n")
    except OSError:
        pass


def _get(url: str, timeout: float):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_latest(timeout: float = 6.0) -> str | None:
    try:
        with _get(LATEST_API, timeout) as resp:
            tag = json.loads(resp.read().decode("utf-8")).get("tag_name") or ""
    except (OSError, ValueError):
        return None
    return tag.lstrip("vV") or None


def check(force: bool = False, fetch=fetch_latest) -> str | None:
    """Versão nova disponível (ex.: "1.5.0") ou None. Pergunta pro GitHub no máximo a cada 12 h."""
    state = read_state()
    latest = state.get("latest")
    if force or time.time() - float(state.get("checked", 0)) > EVERY:
        got = fetch()
        if got:
            latest = got
        write_state(checked=time.time(), latest=latest)
    return latest if latest and newer(latest, __version__) else None


# ---------------------------------------------------------------- aplicar
def _extract(archive: Path, dest: Path) -> Path:
    """Descompacta sem deixar caminho escapar da pasta; devolve a pasta claude-pet/ de dentro."""
    dest = dest.resolve()

    def safe(name: str) -> bool:
        target = (dest / name).resolve()
        return target == dest or dest in target.parents

    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for m in z.infolist():
                if not safe(m.filename):
                    raise ValueError(f"caminho inválido no pacote: {m.filename}")
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            for m in t.getmembers():
                if not safe(m.name) or m.issym() or m.islnk() or m.isdev():
                    raise ValueError(f"entrada inválida no pacote: {m.name}")
            try:
                t.extractall(dest, filter="data")
            except TypeError:   # Python sem o filtro (antes do 3.12): as entradas já foram conferidas acima
                t.extractall(dest)
    root = dest / "claude-pet"
    if not (root / "claude_pet" / "__init__.py").is_file():
        raise ValueError("o pacote baixado não tem o claude-pet dentro")
    return root


def _version_in(root: Path) -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', (root / "claude_pet" / "__init__.py").read_text())
    return m.group(1) if m else "?"


def install_from(new_root: Path, root: Path = ROOT, run_installer: bool = True) -> str:
    """Troca os arquivos da instalação pelos de `new_root`. Se algo der errado no meio, desfaz."""
    stamp = str(int(time.time()))
    moved: list[tuple[Path, Path | None]] = []
    try:
        for name in PARTS:
            src = new_root / name
            if not src.exists():
                continue
            dst = root / name
            backup = None
            if dst.exists():
                backup = root / f".old-{name}-{stamp}"
                dst.rename(backup)
            moved.append((dst, backup))
            shutil.move(str(src), str(dst))
    except OSError:
        for dst, backup in reversed(moved):   # volta como estava
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True) if dst.is_dir() else dst.unlink(missing_ok=True)
            if backup is not None and backup.exists():
                backup.rename(dst)
        raise
    for _dst, backup in moved:
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True) if backup.is_dir() else backup.unlink(missing_ok=True)
    if run_installer:
        subprocess.run([sys.executable, str(root / "install.py"), "--update"], cwd=str(root),
                       capture_output=True, timeout=120)
    return _version_in(root)


def apply(root: Path = ROOT, url: str = DOWNLOAD) -> str:
    """Baixa a última release e instala por cima. Devolve a versão instalada."""
    if is_git_checkout(root):
        raise ValueError("instalado de um clone do git: atualize com git pull")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / ASSET
        with _get(url, 60) as resp, open(archive, "wb") as out:
            shutil.copyfileobj(resp, out)
        new_root = _extract(archive, Path(tmp) / "x")
        version = install_from(new_root, root)
    write_state(latest=version, checked=time.time())
    return version


def restart(root: Path = ROOT) -> None:
    """Abre um pet novo (que espera este fechar pra pegar o lugar)."""
    kw: dict = {"cwd": str(root), "close_fds": True}
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kw["start_new_session"] = True
    subprocess.Popen([sys.executable, "-m", "claude_pet", "--wait"], **kw)

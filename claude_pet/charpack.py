"""Pacotes de personagem (.pet): empacotar, conferir, instalar e remover personagens customizados.

Um .pet é um zip com a pasta do personagem (character.json + character.py + arquivos que ele usar,
como frames.bin). Pode estar na raiz do zip ou dentro de uma pasta só.

    python3 -m claude_pet.charpack check  <pasta>          # confere se carrega e desenha tudo
    python3 -m claude_pet.charpack pack   <pasta> [saída]   # gera <id>.pet
    python3 -m claude_pet.charpack install <arquivo.pet>    # instala em ~/.config/claude-pet/characters/
    python3 -m claude_pet.charpack list
    python3 -m claude_pet.charpack remove <id>

Os customizados ficam fora da instalação, então atualizar o claude-pet não apaga nem sobrescreve.
Atenção: um personagem é código Python e roda no seu computador. Só instale de quem você confia.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from . import skins

MAX_FILES = 64
MAX_BYTES = 20 * 1024 * 1024      # descompactado
SKIP = {"__pycache__", ".DS_Store"}


def check_folder(folder: Path, builtin: bool = False) -> skins.Info:
    """Confere uma pasta de personagem (manifesto + carrega + desenha). ValueError com o motivo."""
    folder = Path(folder)
    manifest = skins.read_manifest(folder)
    info = skins.Info(manifest["id"], folder, manifest, builtin)
    skins.check(info)
    return info


def pack(folder: Path, out: Path | None = None) -> Path:
    folder = Path(folder)
    info = check_folder(folder)
    out = Path(out) if out else Path.cwd() / f"{info.id}.pet"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file() and not (SKIP & set(f.relative_to(folder).parts)) and f.suffix != ".pyc":
                z.write(f, PurePosixPath(info.id, *f.relative_to(folder).parts))
    return out


def _safe_members(z: zipfile.ZipFile) -> tuple[list[zipfile.ZipInfo], str]:
    """Arquivos do zip (sem caminhos perigosos) e o prefixo da pasta do personagem dentro dele."""
    members = [m for m in z.infolist() if not m.is_dir()]
    if not members:
        raise ValueError("o pacote está vazio")
    if len(members) > MAX_FILES:
        raise ValueError(f"arquivos demais no pacote (máximo {MAX_FILES})")
    if sum(m.file_size for m in members) > MAX_BYTES:
        raise ValueError("pacote grande demais (máximo 20 MB descompactado)")
    for m in members:
        p = PurePosixPath(m.filename.replace("\\", "/"))
        if p.is_absolute() or ".." in p.parts or ":" in m.filename:
            raise ValueError(f"caminho inválido no pacote: {m.filename}")
    names = [PurePosixPath(m.filename.replace("\\", "/")) for m in members]
    if PurePosixPath("character.json") in names:
        return members, ""
    tops = {n.parts[0] for n in names if len(n.parts) > 1}
    if len(tops) == 1 and PurePosixPath(next(iter(tops)), "character.json") in names:
        return members, next(iter(tops)) + "/"
    raise ValueError("o pacote não tem um character.json")


def read_package(pet_file: Path) -> dict:
    """Só o manifesto do pacote (pra mostrar o nome antes de instalar), sem rodar nada."""
    import json
    with zipfile.ZipFile(pet_file) as z:
        _members, prefix = _safe_members(z)
        try:
            data = json.loads(z.read(prefix + "character.json").decode("utf-8"))
        except ValueError as e:
            raise ValueError(f"character.json inválido: {e}") from None
    if not isinstance(data, dict):
        raise ValueError("character.json precisa ser um objeto")
    return data


def install(pet_file: Path) -> skins.Info:
    """Instala (ou atualiza) um personagem customizado a partir de um .pet. ValueError com o motivo."""
    pet_file = Path(pet_file)
    try:
        z = zipfile.ZipFile(pet_file)
    except (OSError, zipfile.BadZipFile):
        raise ValueError("não é um pacote .pet válido (precisa ser um zip)") from None
    dest_root = skins.custom_dir()
    dest_root.mkdir(parents=True, exist_ok=True)
    with z, tempfile.TemporaryDirectory(dir=dest_root) as tmp:
        members, prefix = _safe_members(z)
        stage = Path(tmp) / "stage"
        for m in members:
            rel = m.filename.replace("\\", "/")[len(prefix):]
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        manifest = skins.read_manifest(stage)
        cid = manifest["id"]
        if (skins.BUILTIN_DIR / cid).exists():
            raise ValueError(f"já existe um personagem embutido com o id {cid!r}; troque o id")
        final = dest_root / cid
        # confere já no lugar definitivo (o character.py pode usar o próprio caminho pra achar arquivos)
        old = Path(tmp) / "old"
        if final.exists():
            final.rename(old)
        stage.rename(final)
        info = skins.Info(cid, final, manifest, False)
        try:
            skins.check(info)
        except ValueError:
            shutil.rmtree(final, ignore_errors=True)
            if old.exists():
                old.rename(final)
            raise
    return info


def remove(cid: str) -> bool:
    folder = skins.custom_dir() / cid
    if not skins.ID_RE.match(cid) or not folder.is_dir():
        return False
    shutil.rmtree(folder)
    return True


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == "check" and args:
            info = check_folder(Path(args[0]))
            print(f"ok: {info.id} ({info.label()})")
        elif cmd == "pack" and args:
            print(pack(Path(args[0]), Path(args[1]) if len(args) > 1 else None))
        elif cmd == "install" and args:
            info = install(Path(args[0]))
            print(f"instalado: {info.id} ({info.label()}) em {info.path}")
        elif cmd == "remove" and args:
            print("removido" if remove(args[0]) else "não achei esse personagem customizado")
        elif cmd == "list":
            for cid, info in skins.characters().items():
                print(f"{cid:16} {'embutido' if info.builtin else 'customizado':12} {info.label()}")
        else:
            print(__doc__)
            return 2
    except ValueError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

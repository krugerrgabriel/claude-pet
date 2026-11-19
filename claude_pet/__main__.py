"""python -m claude_pet: inicia o bichinho (uma instância só).

Linux: GTK. Windows: Tk (vem com o Python), ver winapp.py.
"""
import os
import sys

from .config import CACHE_DIR, LOCK_FILE, Config


def _single_instance(lock) -> bool:
    try:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def main() -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK_FILE, "a+")
    if not _single_instance(lock):
        print("claude-pet já está rodando.", file=sys.stderr)
        return 0

    from . import i18n
    from .state import StateStore

    cfg = Config.load()
    i18n.set_language(cfg.language)

    if os.name == "nt":
        from .winapp import run
        return run(cfg, StateStore(cfg))

    import signal

    from .window import PetWindow  # fixa GTK 3 antes de qualquer outro import do gi
    from gi.repository import GLib, Gtk

    win = PetWindow(cfg, StateStore(cfg))
    win.show_all()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, Gtk.main_quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, Gtk.main_quit)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())

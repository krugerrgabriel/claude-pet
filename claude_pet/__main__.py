"""python3 -m claude_pet: inicia o bichinho (uma instância só)."""
import fcntl
import signal
import sys

from .config import CACHE_DIR, LOCK_FILE, Config


def main() -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("claude-pet já está rodando.", file=sys.stderr)
        return 0

    from .state import StateStore
    from .window import PetWindow  # fixa GTK 3 antes de qualquer outro import do gi

    from gi.repository import GLib, Gtk

    cfg = Config.load()
    win = PetWindow(cfg, StateStore(cfg))
    win.show_all()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, Gtk.main_quit)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, Gtk.main_quit)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())

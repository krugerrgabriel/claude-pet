"""Chamadas do Windows via ctypes (só stdlib): DPI, monitores, processos, foco do terminal, idioma
e estilo das janelas (sem ícone na barra de tarefas, sem roubar o foco, balão que o clique atravessa).

Só é importado no Windows.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
kernel32.GetConsoleWindow.restype = wintypes.HWND
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.AttachConsole.argtypes = [wintypes.DWORD]
kernel32.GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
GA_ROOT, GA_ROOTOWNER = 2, 3
GW_OWNER = 4
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
TH32CS_SNAPPROCESS = 0x2
INVALID_HANDLE = ctypes.c_void_p(-1).value


# ---------------------------------------------------------------- DPI
def set_dpi_aware() -> None:
    """Coordenadas em pixels reais em todos os monitores (senão o Windows "estica" a janela e mente a posição)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # por monitor
        return
    except (AttributeError, OSError):
        pass
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def dpi_factor() -> float:
    try:
        return user32.GetDpiForSystem() / 96.0
    except (AttributeError, OSError):
        return 1.0


# ---------------------------------------------------------------- monitores
class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


def monitors() -> list[tuple[tuple[int, int, int, int], tuple[int, int, int, int], bool]]:
    """[(geometria, área de trabalho, é o principal)], cada retângulo como (x, y, w, h)."""
    out = []
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                   ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(hmon, _hdc, _rect, _data):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            m, w = info.rcMonitor, info.rcWork
            out.append(((m.left, m.top, m.right - m.left, m.bottom - m.top),
                        (w.left, w.top, w.right - w.left, w.bottom - w.top), bool(info.dwFlags & 1)))
        return True

    user32.EnumDisplayMonitors(None, None, proc_type(cb), 0)
    return out


# teclas de digitar: backspace, tab, enter, espaço, 0-9, A-Z, teclado numérico e pontuação (sem
# modificadores, setas nem botões do mouse)
TYPING_KEYS = ([0x08, 0x09, 0x0D, 0x20] + list(range(0x30, 0x3A)) + list(range(0x41, 0x5B))
               + list(range(0x60, 0x70)) + list(range(0xBA, 0xC1)) + list(range(0xDB, 0xE0)))


def typing_keys_down() -> int:
    """Máscara de bits de quais teclas de digitar estão apertadas agora. O pet só compara com a
    anterior pra contar teclas novas e joga fora: não guarda, não registra e não traduz em letras."""
    mask = 0
    for i, vk in enumerate(TYPING_KEYS):
        if user32.GetAsyncKeyState(vk) & 0x8000:
            mask |= 1 << i
    return mask


# ---------------------------------------------------------------- processos
def pid_alive(pid: int) -> bool:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ctypes.get_last_error() == 5   # acesso negado = existe
    try:
        code = wintypes.DWORD()
        return bool(kernel32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(h)


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]


def processes() -> dict[int, tuple[int, str]]:
    """pid → (pid do pai, nome do .exe em minúsculas)."""
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE:
        return {}
    out = {}
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            out[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile.lower())
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return out


def ancestors(pid: int, procs: dict | None = None) -> list[int]:
    procs = procs if procs is not None else processes()
    chain = []
    while pid and pid in procs and pid not in chain and len(chain) < 30:
        chain.append(pid)
        pid = procs[pid][0]
    return chain


# ---------------------------------------------------------------- foco do terminal
def _console_window_of(pid: int):
    """Janela do console do processo: se conecta ao console dele e pergunta. No Windows Terminal isso
    devolve a "pseudo janela" do ConPTY, cujo dono é a janela do terminal de verdade."""
    try:
        kernel32.FreeConsole()
        if not kernel32.AttachConsole(pid):
            return None
        try:
            hwnd = kernel32.GetConsoleWindow()
        finally:
            kernel32.FreeConsole()
    except OSError:
        return None
    if not hwnd:
        return None
    root = user32.GetAncestor(hwnd, GA_ROOTOWNER) or hwnd
    owner = user32.GetWindow(root, GW_OWNER)
    return owner or root


def _title(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _top_windows() -> list:
    found = []
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, GW_OWNER):
            found.append(hwnd)
        return True

    user32.EnumWindows(proc_type(cb), 0)
    return found


def _window_of_ancestors(pid: int, project: str):
    """Janela visível de algum ancestral do claude (o mais próximo ganha; título com o projeto desempata)."""
    procs = processes()
    rank = {p: i for i, p in enumerate(ancestors(pid, procs))}
    best = None
    for hwnd in _top_windows():
        owner_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
        if owner_pid.value in rank:
            bonus = 0 if project and project.lower() in _title(hwnd).lower() else 1
            key = (rank[owner_pid.value], bonus)
            if best is None or key < best[0]:
                best = (key, hwnd)
    return best[1] if best else None


def bring_to_front(hwnd) -> bool:
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    # o Windows só deixa trocar o foco quem recebeu a última entrada; um "Alt" de mentira libera
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    ok = bool(user32.SetForegroundWindow(hwnd))
    user32.BringWindowToTop(hwnd)
    return ok


def focus_session(claude_pid: int, project: str = "") -> bool:
    if claude_pid <= 0:
        return False
    hwnd = _console_window_of(claude_pid)
    if not (hwnd and user32.IsWindowVisible(hwnd)):   # ex.: terminal do VS Code: procura a janela de um ancestral
        hwnd = _window_of_ancestors(claude_pid, project)
    return bring_to_front(hwnd) if hwnd else False


# ---------------------------------------------------------------- mouse (modo troll)
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]


def set_cursor(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def mouse_buttons_down() -> bool:
    """Botão esquerdo, direito ou do meio apertado agora."""
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02, 0x04))


# ---------------------------------------------------------------- idioma
def ui_language() -> str:
    """Idioma da interface do Windows: 0x16 é o código primário do português."""
    try:
        return "pt" if (kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x16 else "en"
    except (AttributeError, OSError):
        return "en"


# ---------------------------------------------------------------- janelas
def toplevel_hwnd(widget_id: int):
    return user32.GetAncestor(widget_id, GA_ROOT) or widget_id


def style_window(widget_id: int, click_through: bool = False) -> None:
    """Sem ícone na barra de tarefas e sem roubar o foco ao clicar; `click_through` = o mouse atravessa."""
    hwnd = toplevel_hwnd(widget_id)
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex = (ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW
    if click_through:
        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)


def short_path(path: str) -> str:
    """Caminho 8.3 (sem espaços), pra usar sem aspas em qualquer shell."""
    buf = ctypes.create_unicode_buffer(1024)
    n = kernel32.GetShortPathNameW(os.fspath(path), buf, 1024)
    return buf.value if 0 < n < 1024 else os.fspath(path)

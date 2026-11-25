"""The Windows side of PR7-CB (ctypes): which program a copy came from, where the text cursor is, and pasting into
the program that was in front (focus back, then Ctrl+V), as Ditto does. Elsewhere these return nothing / do nothing,
so the rest of PR7-CB runs (and is tested) on any system."""

from __future__ import annotations

import os
import sys
import time

WIN = sys.platform == "win32"
if WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetClipboardOwner.restype = wintypes.HWND
    user32.GetForegroundWindow.restype = wintypes.HWND

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                    ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                    ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_V = 0x11, 0x10, 0x12, 0x5B, 0x56
KEYEVENTF_KEYUP = 0x2


def program_of(hwnd) -> str:
    """The program behind a window, as the list shows it: "PR7-W", "firefox", "Code"."""
    if not WIN or not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.splitext(os.path.basename(buf.value))[0]
    finally:
        kernel32.CloseHandle(h)
    return ""


def clipboard_source() -> str:
    """Who put the newest copy on the clipboard: its owner window's program, else the program in front."""
    if not WIN:
        return ""
    return program_of(user32.GetClipboardOwner()) or program_of(user32.GetForegroundWindow())


def foreground():
    return user32.GetForegroundWindow() if WIN else None


def caret(hwnd=None):
    """The text cursor of the window in front, in screen pixels (x, bottom), or None when it has none Windows knows."""
    if not WIN:
        return None
    hwnd = hwnd or user32.GetForegroundWindow()
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not user32.GetGUIThreadInfo(tid, ctypes.byref(info)) or not info.hwndCaret:
        return None
    pt = wintypes.POINT(info.rcCaret.left, info.rcCaret.bottom)
    user32.ClientToScreen(info.hwndCaret, ctypes.byref(pt))
    return pt.x, pt.y


def _keys(events: list[tuple[int, bool]]) -> None:
    arr = (INPUT * len(events))()
    for i, (vk, up) in enumerate(events):
        arr[i].type = 1                                            # INPUT_KEYBOARD
        arr[i].u.ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
    user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


def paste_into(hwnd) -> bool:
    """Bring `hwnd` to the front and press Ctrl+V there. Keys still held from the hotkey (Ctrl, Shift, Alt, Win) are
    let go first, so the program sees a clean Ctrl+V and not Ctrl+Shift+V."""
    if not WIN or not hwnd:
        return False
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    held = [(vk, True) for vk in (VK_SHIFT, VK_MENU, VK_LWIN) if user32.GetAsyncKeyState(vk) & 0x8000]
    _keys(held + [(VK_CONTROL, False), (VK_V, False), (VK_V, True), (VK_CONTROL, True)])
    return True

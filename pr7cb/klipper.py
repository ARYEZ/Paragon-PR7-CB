"""PR7-CB on Linux's Plasma (PR7-OS): Klipper feeds the history.

On Wayland only the window in front may read the clipboard, so a program in the background (PR7-CB's watcher) never
hears of copies made elsewhere. Klipper, Plasma's own clipboard keeper, does, and it answers on the session bus:
org.kde.klipper /klipper getClipboardHistoryMenu -> its history, newest first. `KlipperSource` asks once a second and
adds what's new to PR7-CB's store (text: Klipper's menu carries text), skipping what PR7-CB itself just put on the
clipboard. Copies marked private (PR7-PM's x-kde-passwordManagerHint) never reach Klipper, so never reach PR7-CB.

D-Bus through jeepney (PySide's QtDBus can't read every answer; PR7-Q's lesson); `address` lets tests use a private
bus with a stand-in Klipper.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from .store import Clip, Store

SERVICE, PATH, INTERFACE = "org.kde.klipper", "/klipper", "org.kde.klipper.klipper"


def history(address: str | None = None) -> list[str] | None:
    """Klipper's history, newest first; None when Klipper (or the session bus) isn't there."""
    try:
        from jeepney import DBusAddress, MessageType, new_method_call
        from jeepney.io.blocking import open_dbus_connection
    except ImportError:
        return None
    try:
        with open_dbus_connection(bus=address or "SESSION") as conn:
            reply = conn.send_and_get_reply(
                new_method_call(DBusAddress(PATH, bus_name=SERVICE, interface=INTERFACE), "getClipboardHistoryMenu"),
                timeout=2)
    except Exception:  # noqa: BLE001 - no bus, no Klipper, a timeout
        return None
    if reply.header.message_type == MessageType.error:
        return None
    return [s for s in reply.body[0] if isinstance(s, str)]


class KlipperSource(QObject):
    recorded = Signal(object)

    def __init__(self, store: Store, watcher=None, address: str | None = None, interval_ms: int = 1000, parent=None):
        super().__init__(parent)
        self.store = store
        self.watcher = watcher            # PR7-CB's own clipboard watcher: what it put there isn't recorded again
        self.address = address
        self.known: str | None = None     # Klipper's newest item when we last looked
        self.started = False
        self.paused = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(interval_ms)

    def stop(self):
        self.timer.stop()

    def _ours(self, text: str) -> bool:
        w = self.watcher
        if w is None:
            return False
        if getattr(w, "_plain_text", None) == text:
            return True
        ours = getattr(w, "_ours", None)
        return ours is not None and Clip(kind="text", text=text).digest() == ours

    def poll(self) -> int:
        """Look at Klipper once; how many clips were added."""
        items = history(self.address)
        if items is None or self.paused:
            return 0
        added = 0
        if not self.started:                 # the first look: Klipper's whole history, oldest first
            self.started = True
            for text in reversed(items):
                if text.strip() and not self._ours(text):
                    self._add(text)
                    added += 1
        elif items and items[0] != self.known and items[0].strip() and not self._ours(items[0]):
            self._add(items[0])
            added = 1
        self.known = items[0] if items else None
        return added

    def _add(self, text: str):
        clip = Clip(kind="text", text=text, source="Klipper")
        clip.id = self.store.add(clip)
        self.recorded.emit(clip)

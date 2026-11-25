"""Watching the clipboard: every copy becomes a clip, except private ones.

Private (never recorded), as Ditto and Windows' own clipboard history agree:
- copies marked by the program that made them: Windows' "ExcludeClipboardContentFromMonitorProcessing", a zero
  "CanIncludeInClipboardHistory", or the older "Clipboard Viewer Ignore" (password managers set these);
- copies from a program on the "never record" list (Options);
- anything while recording is paused (the tray menu);
- PR7-CB's own pastes (they only move the clip back to the top).

Files win over text, text over pictures: Office puts a picture of copied text on the clipboard too, and the text is
what was meant (Ditto keeps the same order)."""

from __future__ import annotations

import os

from PySide6.QtCore import QBuffer, QByteArray, QDir, QIODevice, QMimeData, QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QClipboard, QImage
from PySide6.QtWidgets import QApplication

from . import winclip
from .store import Clip, Store

PRIVATE = ("ExcludeClipboardContentFromMonitorProcessing", "Clipboard Viewer Ignore")
HISTORY_FLAG = "CanIncludeInClipboardHistory"


def _win_format(md: QMimeData, name: str) -> str | None:
    """A Windows clipboard format as Qt names it ('application/x-qt-windows-mime;value="NAME"'), or the bare name."""
    for f in md.formats():
        if f == name or f.endswith(f'value="{name}"'):
            return f
    return None


def private(md: QMimeData) -> bool:
    if any(_win_format(md, name) for name in PRIVATE):
        return True
    f = _win_format(md, HISTORY_FLAG)
    if f is not None:
        data = bytes(md.data(f))
        if data[:4] == b"\0\0\0\0":                                  # a DWORD 0: "keep me out of the history"
            return True
    return False


def clip_from(md: QMimeData, max_image: int = 20_000_000) -> Clip | None:
    """What a copy holds, as a clip; None for nothing PR7-CB keeps (or a picture over `max_image` bytes)."""
    if md is None:
        return None
    if md.hasUrls():
        files = [QDir.toNativeSeparators(u.toLocalFile()) for u in md.urls() if u.isLocalFile()]   # C:\\ on Windows
        if files and len(files) == len(md.urls()):
            return Clip("files", "\n".join(files), files=files)
    if md.hasText() and md.text().strip():
        return Clip("text", md.text(), html=md.html() if md.hasHtml() else "")
    if md.hasImage():
        img = QImage(md.imageData())
        if img.isNull():
            return None
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        png = bytes(ba)
        if max_image and len(png) > max_image:
            return None
        return Clip("image", f"Picture {img.width()} × {img.height()}", image=png, width=img.width(),
                    height=img.height())
    return None


def mime_of(clip: Clip, plain: bool = False) -> QMimeData:
    """A clip back onto the clipboard: text (with its HTML unless plain), a picture, or files."""
    md = QMimeData()
    if clip.kind == "files":
        md.setUrls([QUrl.fromLocalFile(p) for p in clip.files])
        md.setText("\n".join(clip.files))
    elif clip.kind == "image":
        img = QImage()
        img.loadFromData(clip.image, "PNG")
        md.setImageData(img)
    else:
        md.setText(clip.text)
        if clip.html and not plain:
            md.setHtml(clip.html)
    return md


class Watcher(QObject):
    recorded = Signal(object)          # the Clip just kept

    def __init__(self, store: Store, options=None, source=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.options = options or (lambda: {})        # -> {"ignore": [...], "max_image": int, "keep_images": bool}
        self.source = source or winclip.clipboard_source
        self.paused = False
        self.stopped = False
        self._ours: str | None = None
        self._plain_text: str | None = None
        self.clipboard: QClipboard = QApplication.clipboard()
        # Read the copy a moment after the signal: some programs announce a copy and then add their other formats
        # (HTML, pictures) to it, so reading at once can catch it half written.
        self._signal = lambda: QTimer.singleShot(0, self.changed)
        self.clipboard.dataChanged.connect(self._signal)

    def stop(self):
        """No more recording (closing, or a test done): reads already scheduled do nothing either."""
        if self.stopped:
            return
        self.stopped = True
        try:
            self.clipboard.dataChanged.disconnect(self._signal)
        except (RuntimeError, TypeError):
            pass

    def put(self, clip: Clip, plain: bool = False):
        """Put a clip on the clipboard without recording it again."""
        self._ours = clip.digest() if not plain else None
        self._plain_text = clip.text if plain else None
        self.clipboard.setMimeData(mime_of(clip, plain))

    def changed(self) -> Clip | None:
        if self.stopped:
            return None
        md = self.clipboard.mimeData()
        if self.paused or md is None or private(md):
            return None
        opts = self.options()
        clip = clip_from(md, opts.get("max_image", 20_000_000))
        if clip is None:
            return None
        if clip.kind == "image" and not opts.get("keep_images", True):
            return None
        if self._ours is not None and clip.digest() == self._ours:
            self._ours = None
            return None
        if self._plain_text is not None and clip.kind == "text" and clip.text == self._plain_text:
            self._plain_text = None
            return None
        source = self.source() or ""
        ignore = {os.path.splitext(n.strip().lower())[0] for n in opts.get("ignore", []) if n.strip()}
        if source and source.lower() in ignore:
            return None
        clip.source = source
        clip.id = self.store.add(clip)
        self.recorded.emit(clip)
        return clip

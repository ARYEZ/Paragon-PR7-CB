"""The popup Ditto opens with Ctrl+`: a search box over your clips, newest first, at the text cursor.

Typing searches (every word, any case). Up / Down choose, Enter pastes, Shift+Enter pastes plain text, Ctrl+1..9 pastes
that row, Ctrl+P pins or unpins, Delete forgets, Esc closes; it also closes when another window is clicked. The list is
a plain Python model drawn by `ClipDelegate` (number, picture thumbnail, one line with the search match in orange,
then kind / program / when, and PINNED)."""

from __future__ import annotations

import time

from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QStyle, QStyledItemDelegate,
                               QVBoxLayout)

from . import theme, widgets
from .store import Clip, Store

CLIP = Qt.ItemDataRole.UserRole + 1


def when_text(t: float, now: float | None = None) -> str:
    s = (now or time.time()) - t
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)} min ago"
    if s < 86400:
        h = int(s // 3600)
        return f"{h} hour{'s' if h > 1 else ''} ago"
    if s < 2 * 86400:
        return "yesterday"
    if s < 7 * 86400:
        return f"{int(s // 86400)} days ago"
    return time.strftime("%Y-%m-%d", time.localtime(t))


class ClipModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.clips: list[Clip] = []
        self.query = ""
        self._thumbs: dict[int, QImage] = {}

    def set(self, clips: list[Clip], query: str = ""):
        self.beginResetModel()
        self.clips = clips
        self.query = query
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.clips)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        c = self.clips[index.row()]
        if role == CLIP:
            return c
        if role == Qt.ItemDataRole.DisplayRole:
            return c.title()
        if role == Qt.ItemDataRole.ToolTipRole:
            return c.text[:2000] if c.kind != "image" else c.title()
        return None

    def thumb(self, c: Clip) -> QImage:
        img = self._thumbs.get(c.id)
        if img is None:
            img = QImage()
            img.loadFromData(c.image, "PNG")
            img = img.scaled(144, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._thumbs[c.id] = img
        return img


class ClipDelegate(QStyledItemDelegate):
    def __init__(self, model: ClipModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.body = QFont("Inter"); self.body.setPixelSize(13)
        self.meta = QFont("Inter"); self.meta.setPixelSize(11)
        self.num = QFont("Inter"); self.num.setPixelSize(11); self.num.setWeight(QFont.Weight.DemiBold)
        self.pill = QFont("Inter"); self.pill.setPixelSize(9); self.pill.setWeight(QFont.Weight.DemiBold)

    def sizeHint(self, option, index):
        c = index.data(CLIP)
        return QSize(option.rect.width(), 74 if c and c.kind == "image" else 58)

    def paint(self, p: QPainter, option, index):
        c: Clip = index.data(CLIP)
        r = QRectF(option.rect).adjusted(2, 1, -2, -1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected:
            path = QPainterPath(); path.addRoundedRect(r, 4, 4)
            p.fillPath(path, QColor(theme.ACCENT_DIM))
        ink = QColor("#FFFFFF") if selected else QColor(theme.TEXT)
        dim = QColor(255, 255, 255, 180) if selected else QColor(theme.TEXT_DIM)
        x = r.x() + 10
        row = index.row()
        p.setFont(self.num); p.setPen(dim)
        if row < 9:
            p.drawText(QRectF(x, r.y() + 8, 12, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, str(row + 1))
        x += 22
        if c.kind == "image":
            img = self.model.thumb(c)
            tw, th = img.width() / 2, img.height() / 2
            p.drawImage(QRectF(x, r.y() + (r.height() - th) / 2, tw, th), img)
            x += tw + 12
        width = r.right() - 10 - x
        fm = QFontMetrics(self.body)
        line = fm.elidedText(c.title(), Qt.TextElideMode.ElideRight, int(width))
        y = r.y() + 8
        p.setFont(self.body)
        self._text_with_match(p, line, QRectF(x, y, width, 18), ink, self.model.query)
        p.setFont(self.meta); p.setPen(dim)
        meta = f"{c.kind.upper()}  ·  {c.source or 'unknown program'}  ·  {when_text(c.created)}"
        mx = QRectF(x, y + 22, width, 16)
        p.drawText(mx, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, meta)
        if c.pinned:
            px = x + QFontMetrics(self.meta).horizontalAdvance(meta) + 8
            p.setFont(self.pill)
            pw = QFontMetrics(self.pill).horizontalAdvance("PINNED") + 12
            pill = QRectF(px, mx.y() + 1, pw, 14)
            p.setPen(QPen(QColor(theme.LED_ORANGE), 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(pill, 7, 7)
            p.drawText(pill, Qt.AlignmentFlag.AlignCenter, "PINNED")
        p.restore()

    @staticmethod
    def _text_with_match(p: QPainter, text: str, box: QRectF, ink: QColor, query: str):
        """The line, with the first search word's first match in the family's orange."""
        words = query.split()
        at = text.casefold().find(words[0].casefold()) if words else -1
        if at < 0:
            p.setPen(ink)
            p.drawText(box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            return
        fm = p.fontMetrics()
        n = len(words[0])
        x = box.x()
        for part, colour in ((text[:at], ink), (text[at:at + n], QColor(theme.LED_ORANGE)), (text[at + n:], ink)):
            p.setPen(colour)
            p.drawText(QRectF(x, box.y(), box.right() - x, box.height()),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, part)
            x += fm.horizontalAdvance(part)


def stylesheet() -> str:
    surface = theme.PANEL if theme.FINISH == "obsidian" else theme.BACKGROUND
    return theme.stylesheet() + f"""
QFrame#popup {{ background: {surface}; border: 1px solid {theme.PANEL_EDGE}; border-radius: 8px; }}
QListView {{ background: transparent; border: none; outline: none; }}
QListView::item:selected {{ background: transparent; }}
"""


class Popup(QFrame):
    chosen = Signal(object, bool)      # clip, plain text
    menu_wanted = Signal(QPoint)       # the ⋮ key: the owner shows its menu there

    def __init__(self, store: Store):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool)
        self.store = store
        self.setObjectName("popup")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.resize(440, 580)
        v = QVBoxLayout(self); v.setContentsMargins(10, 10, 10, 8); v.setSpacing(8)
        top = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Type to search your clips")
        self.search.textChanged.connect(self.refresh)
        self.search.installEventFilter(self)
        top.addWidget(self.search, 1)
        self.more = widgets.SmallKey("more", "Options")
        self.more.clicked.connect(lambda: self.menu_wanted.emit(self.more.mapToGlobal(self.more.rect().bottomLeft())))
        top.addWidget(self.more)
        v.addLayout(top)
        self.model = ClipModel()
        self.list = QListView()
        self.list.setModel(self.model)
        self.list.setItemDelegate(ClipDelegate(self.model, self.list))
        self.list.setUniformItemSizes(False)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.doubleClicked.connect(lambda idx: self.choose(idx.row()))
        self.list.installEventFilter(self)
        v.addWidget(self.list, 1)
        self.foot = QLabel("ENTER PASTE   ·   SHIFT+ENTER PLAIN TEXT   ·   CTRL+P PIN   ·   DEL FORGET")
        self.foot.setProperty("role", "dim")
        f = self.foot.font(); f.setPixelSize(10); self.foot.setFont(f)
        self.foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.foot)
        self.restyle()

    def restyle(self):
        self.setStyleSheet(stylesheet())

    # ---- filling
    def refresh(self, *_):
        q = self.search.text()
        self.model.set(self.store.list(q), q)
        if self.model.rowCount():
            self.list.setCurrentIndex(self.model.index(0, 0))

    def current(self) -> Clip | None:
        idx = self.list.currentIndex()
        return idx.data(CLIP) if idx.isValid() else None

    # ---- showing
    def show_at(self, point: QPoint | None):
        """Open just below `point` (the text cursor), kept inside its screen; the mouse when there's no cursor."""
        self.search.clear()
        self.refresh()
        at = point or QGuiApplication.primaryScreen().geometry().center()
        screen = QGuiApplication.screenAt(at) or QGuiApplication.primaryScreen()
        area: QRect = screen.availableGeometry()
        x = min(max(area.left(), at.x()), area.right() - self.width())
        y = at.y() + 6
        if y + self.height() > area.bottom():
            y = max(area.top(), at.y() - self.height() - 24)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    def changeEvent(self, e):
        if e.type() == QEvent.Type.ActivationChange and self.isVisible() and not self.isActiveWindow() \
                and not getattr(self, "keep_open", False):
            self.hide()
        super().changeEvent(e)

    # ---- keys
    def eventFilter(self, obj, e):
        if e.type() == QEvent.Type.KeyPress and self.handle_key(e):
            return True
        return super().eventFilter(obj, e)

    def keyPressEvent(self, e):
        if not self.handle_key(e):
            super().keyPressEvent(e)

    def handle_key(self, e) -> bool:
        k, mods = e.key(), e.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        if k == Qt.Key.Key_Escape:
            self.hide()
            return True
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.choose(self.list.currentIndex().row(), bool(mods & Qt.KeyboardModifier.ShiftModifier))
            return True
        if ctrl and Qt.Key.Key_1 <= k <= Qt.Key.Key_9:
            self.choose(k - Qt.Key.Key_1, bool(mods & Qt.KeyboardModifier.ShiftModifier))
            return True
        if k in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            n = self.model.rowCount()
            if n:
                step = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1, Qt.Key.Key_PageUp: -8, Qt.Key.Key_PageDown: 8}[k]
                row = min(n - 1, max(0, self.list.currentIndex().row() + step))
                self.list.setCurrentIndex(self.model.index(row, 0))
            return True
        if ctrl and k == Qt.Key.Key_P:
            self.toggle_pin()
            return True
        if k == Qt.Key.Key_Delete and (self.search.text() == "" or self.list.hasFocus()):
            self.forget()
            return True
        return False

    # ---- actions
    def choose(self, row: int, plain: bool = False):
        if 0 <= row < self.model.rowCount():
            clip = self.model.clips[row]
            self.hide()
            self.chosen.emit(clip, plain)

    def toggle_pin(self):
        c = self.current()
        if c is None:
            return
        self.store.pin(c.id, not c.pinned)
        row = self.list.currentIndex().row()
        self.refresh()
        self.list.setCurrentIndex(self.model.index(min(row, self.model.rowCount() - 1), 0))

    def forget(self):
        c = self.current()
        if c is None:
            return
        row = self.list.currentIndex().row()
        self.store.delete(c.id)
        self.refresh()
        if self.model.rowCount():
            self.list.setCurrentIndex(self.model.index(min(row, self.model.rowCount() - 1), 0))

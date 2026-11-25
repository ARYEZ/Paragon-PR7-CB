"""Mock-up pictures of PR7-CB, drawn offscreen with real Qt widgets: QT_SCALE_FACTOR=2 python tools/mockup.py OUT"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtCore import QRectF, QSize, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,  # noqa: E402
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from pr7cb import theme, widgets  # noqa: E402
import sample_images  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/mockup")
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
theme.load_fonts()
W, H = 1280, 800
EDITOR = QImage("/home/user/paragon-pr7-w/docs/screenshots/main_window.png")
PHOTO = sample_images.photo(2, "city", 640, 400)

CLIPS = [  # kind, text, from, when, extra
    ("text", "Thanks for the quick turnaround on the Elseworld cut. Can we lock picture by Friday and send the "
             "stems to the mix on Monday?", "PR7-W", "just now", "", False),
    ("text", "https://github.com/ARYEZ/Paragon-PR7-DU/releases/latest", "Firefox", "2 min ago", "", False),
    ("image", "Screenshot  ·  1600 × 900", "PR7-Q", "6 min ago", "", False),
    ("text", "C:\\Users\\me\\Videos\\Elseworld shoot\\A001_C0006.mov", "PR7-DU", "12 min ago", "", False),
    ("files", "3 files: Elseworld_v3.mp4, poster.png, credits.txt", "PR7-E", "25 min ago", "", False),
    ("text", "Invoice 2026-114  ·  Static Bloom  ·  Mix and master, 4 songs  ·  due 15 December", "PR7-W",
     "1 hour ago", "", True),
    ("text", "def squarify(sizes, box):\n    order = sorted(range(len(sizes)), key=lambda i: -sizes[i])", "PR7-W",
     "2 hours ago", "", False),
    ("text", "Thursday 4 pm — call with the label about the cover art", "Mail", "yesterday", "", True),
    ("text", "#DE0639  #CD6619", "PR7-P", "yesterday", "", False),
    ("text", "Static Bloom — Last Light (Extended Mix)", "PR7-L", "2 days ago", "", False),
]


def desktop() -> QImage:
    img = QImage(W * 2, H * 2, QImage.Format.Format_RGB32)
    img.setDevicePixelRatio(2)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, W, H), sample_images.photo(0, "hills", W * 2, H * 2))
    win = QRectF(60, 40, 1000, 640)
    p.fillRect(win.translated(0, 10), QColor(0, 0, 0, 120))
    p.drawImage(win, EDITOR)
    bar = QRectF(0, H - 44, W, 44)
    p.fillRect(bar, QColor(18, 14, 18, 235))
    p.end()
    return img


def stylesheet():
    return theme.stylesheet() + f"""
QFrame#popup {{ background: {theme.PANEL if theme.FINISH == 'obsidian' else theme.BACKGROUND};
    border: 1px solid {theme.PANEL_EDGE}; border-radius: 8px; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border: none; padding: 0; }}
QListWidget::item:selected {{ background: {theme.ACCENT_DIM}; border-radius: 4px; }}
QLabel[role="num"] {{ color: {theme.TEXT_DIM}; font-size: 11px; font-weight: 600; }}
QLabel[role="pin"] {{ color: {theme.LED_ORANGE}; border: 1px solid {theme.LED_ORANGE}; border-radius: 7px;
    font-size: 9px; font-weight: 600; padding: 0 5px; }}
QPushButton[kind="primary"] {{ background: {theme.qss_gradient()}; color: #FFFFFF; border: none; font-weight: 600;
    padding: 7px 22px; }}"""


def label(text, role=None, size=None, bold=False, wrap=False):
    w = QLabel(text)
    if role:
        w.setProperty("role", role)
    f = w.font()
    if size:
        f.setPixelSize(size)
    if bold:
        f.setWeight(QFont.Weight.DemiBold)
    w.setFont(f)
    w.setWordWrap(wrap)
    return w


def clip_row(i, clip, selected, find=""):
    kind, text, src, when, _, pinned = clip
    row = QWidget()
    h = QHBoxLayout(row); h.setContentsMargins(10, 8, 10, 8); h.setSpacing(10)
    num = label(str(i + 1) if i < 9 else "", "num"); num.setFixedWidth(12)
    num.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
    h.addWidget(num)
    if kind == "image":
        thumb = QLabel()
        pm = QPixmap.fromImage(PHOTO.scaled(QSize(144, 90), Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        pm.setDevicePixelRatio(2)
        thumb.setPixmap(pm)
        h.addWidget(thumb)
    col = QVBoxLayout(); col.setSpacing(3)
    shown = text.replace("\n", "  ⏎  ")
    f = QFont("Inter"); f.setPixelSize(13)
    from PySide6.QtGui import QFontMetrics
    shown = QFontMetrics(f).elidedText(shown, Qt.TextElideMode.ElideRight, 300 if kind == "image" else 370)
    if find:
        lo = shown.lower().find(find)
        if lo >= 0:
            shown = (shown[:lo] + f'<span style="color:{theme.LED_ORANGE}">{shown[lo:lo + len(find)]}</span>'
                     + shown[lo + len(find):])
    body = label(shown, size=13)
    body.setTextFormat(Qt.TextFormat.RichText)
    body.setMaximumHeight(38)
    if selected:
        body.setStyleSheet("color: #FFFFFF;")
    col.addWidget(body)
    meta = QHBoxLayout(); meta.setSpacing(8)
    m = label(f"{kind.upper()}  ·  {src}  ·  {when}", "dim", 11)
    if selected:
        m.setStyleSheet("color: rgba(255,255,255,0.7);")
    meta.addWidget(m)
    if pinned:
        meta.addWidget(label("PINNED", "pin"))
    meta.addStretch(1)
    col.addLayout(meta)
    h.addLayout(col, 1)
    return row


def popup(find="", sel=0):
    pop = QFrame(); pop.setObjectName("popup")
    pop.setStyleSheet(stylesheet())
    pop.resize(440, 580)
    v = QVBoxLayout(pop); v.setContentsMargins(10, 10, 10, 8); v.setSpacing(8)
    top = QHBoxLayout()
    search = QLineEdit(find); search.setPlaceholderText("Type to search your clips")
    top.addWidget(search, 1)
    top.addWidget(widgets.SmallKey("more", "Options"))
    v.addLayout(top)
    lst = QListWidget()
    clips = [c for c in CLIPS if find in c[1].lower()] if find else CLIPS
    for i, c in enumerate(clips):
        it = QListWidgetItem(lst)
        wdg = clip_row(i, c, i == sel, find)
        it.setSizeHint(QSize(400, 74 if c[0] == "image" else 58))
        lst.setItemWidget(it, wdg)
        if i == sel:
            it.setSelected(True)
    v.addWidget(lst, 1)
    foot = label("ENTER PASTE   ·   SHIFT+ENTER PLAIN TEXT   ·   CTRL+P PIN   ·   DEL FORGET", "dim", 10)
    foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
    v.addWidget(foot)
    pop.show(); app.processEvents()
    return pop


def over_desktop(pop, name, at=(470, 150)):
    img = desktop()
    p = QPainter(img)
    shot = pop.grab()
    p.fillRect(QRectF(at[0] + 4, at[1] + 8, pop.width(), pop.height()), QColor(0, 0, 0, 90))
    p.drawPixmap(at[0], at[1], shot)
    p.end()
    img.save(str(out / name))
    print(out / name)


def options():
    theme.set_finish("aurora")
    d = QWidget(); d.setPalette(theme.palette()); d.setAutoFillBackground(True)
    d.setStyleSheet(stylesheet()); d.resize(560, 640)
    v = QVBoxLayout(d); v.setContentsMargins(0, 0, 0, 16); v.setSpacing(0)
    v.addWidget(widgets.Header("CLIPBOARD"))
    g = QGridLayout(); g.setContentsMargins(22, 18, 22, 8); g.setHorizontalSpacing(16); g.setVerticalSpacing(12)
    rows = [("KEY TO OPEN", QLineEdit("Ctrl+`")), ("KEEP", QSpinBox()), ("FORGET AFTER", QComboBox()),
            ("ENTER", QComboBox()), ("POPUP AT", QComboBox())]
    rows[1][1].setRange(10, 10000); rows[1][1].setValue(500); rows[1][1].setSuffix(" clips")
    rows[2][1].addItem("30 days (pinned clips: never)")
    rows[3][1].addItem("Paste into the program I was in")
    rows[4][1].addItem("The text cursor")
    for r, (name, w) in enumerate(rows):
        g.addWidget(label(name, size=12, bold=True), r, 0)
        g.addWidget(w, r, 1)
    v.addLayout(g)
    box = QVBoxLayout(); box.setContentsMargins(22, 6, 22, 6); box.setSpacing(8)
    box.addWidget(label("NEVER RECORD COPIES FROM", size=12, bold=True))
    ign = QLineEdit("PR7-K.exe;  KeePassXC.exe;  1Password.exe")
    box.addWidget(ign)
    box.addWidget(label("Programs that mark a copy as private (password managers do) are never recorded either.",
                        "dim", 11, wrap=True))
    for text, on in (("Paste as plain text by default", False), ("Keep pictures (up to 20 MB each)", True),
                     ("Start PR7-CB with Windows", True), ("Check for updates automatically", True)):
        c = QCheckBox(text); c.setChecked(on); box.addWidget(c)
    v.addLayout(box)
    v.addStretch(1)
    b = QHBoxLayout(); b.setContentsMargins(22, 0, 22, 0); b.addStretch(1)
    ok = QPushButton("OK"); ok.setProperty("kind", "primary"); b.addWidget(ok); b.addWidget(QPushButton("Cancel"))
    v.addLayout(b)
    d.show(); app.processEvents()
    d.grab().save(str(out / "3_options_aurora.png"))
    print(out / "3_options_aurora.png")
    theme.set_finish("obsidian")


app.setPalette(theme.palette())
over_desktop(popup(), "1_popup.png")
over_desktop(popup("invoice"), "2_search.png")
options()

"""Screenshots of the real PR7-CB popup and Options on a made-up history (nothing real is read or kept):
QT_SCALE_FACTOR=2 python tools/screenshots.py OUT_DIR"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PR7CB_DATA"] = tempfile.mkdtemp()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPoint, QRectF, QSettings  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())

from pr7cb import theme  # noqa: E402
from pr7cb.store import Clip, Store  # noqa: E402
from pr7cb.tray import OptionsDialog, TrayApp  # noqa: E402
import sample_images  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
out.mkdir(parents=True, exist_ok=True)
app = QApplication([])
theme.load_fonts()
app.setPalette(theme.palette())
W, H = 1280, 800
EDITOR = QImage("/home/user/paragon-pr7-w/docs/screenshots/main_window.png")
now = time.time()


def png(img: QImage) -> bytes:
    ba = QByteArray(); buf = QBuffer(ba); buf.open(QIODevice.OpenModeFlag.WriteOnly); img.save(buf, "PNG")
    return bytes(ba)


store = Store()
photo = sample_images.photo(2, "city", 1600, 900)
for age, clip in reversed([
    (2 * 86400, Clip("text", "Static Bloom — Last Light (Extended Mix)", source="PR7-L")),
    (86400 + 600, Clip("text", "#DE0639  #CD6619", source="PR7-P")),
    (86400, Clip("text", "Thursday 4 pm — call with the label about the cover art", source="Mail", pinned=True)),
    (7200, Clip("text", "def squarify(sizes, box):\n    order = sorted(range(len(sizes)), key=lambda i: -sizes[i])",
                source="PR7-W")),
    (3600, Clip("text", "Invoice 2026-114  ·  Static Bloom  ·  Mix and master, 4 songs  ·  due 15 December",
                source="PR7-W", pinned=True)),
    (1500, Clip("files", "", files=["C:\\Exports\\Elseworld_v3.mp4", "C:\\Exports\\poster.png",
                                    "C:\\Exports\\credits.txt"], source="PR7-E")),
    (720, Clip("text", "C:\\Users\\me\\Videos\\Elseworld shoot\\A001_C0006.mov", source="PR7-DU")),
    (360, Clip("image", "Picture", image=png(photo), width=1600, height=900, source="PR7-Q")),
    (120, Clip("text", "https://github.com/ARYEZ/Paragon-PR7-DU/releases/latest", source="firefox")),
    (5, Clip("text", "Thanks for the quick turnaround on the Elseworld cut. Can we lock picture by Friday and send "
                     "the stems to the mix on Monday?", source="PR7-W")),
]):
    store.add(clip, now=now - age)


def desktop() -> QImage:
    img = QImage(W * 2, H * 2, QImage.Format.Format_RGB32)
    img.setDevicePixelRatio(2)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawImage(QRectF(0, 0, W, H), sample_images.photo(0, "hills", W * 2, H * 2))
    win = QRectF(60, 40, 1000, 640)
    p.fillRect(win.translated(0, 10), QColor(0, 0, 0, 120))
    p.drawImage(win, EDITOR)
    p.fillRect(QRectF(0, H - 44, W, 44), QColor(18, 14, 18, 235))
    p.end()
    return img


tray = TrayApp(store, show_tray=False, source=lambda: "PR7-W")
tray.popup.keep_open = True


def shot(name, query=""):
    tray.popup.show_at(QPoint(470, 144))
    tray.popup.search.setText(query)
    app.processEvents()
    img = desktop()
    p = QPainter(img)
    p.fillRect(QRectF(474, 158, tray.popup.width(), tray.popup.height()), QColor(0, 0, 0, 90))
    p.drawPixmap(470, 150, tray.popup.grab())
    p.end()
    img.save(str(out / name))
    print(out / name)
    tray.popup.hide()


shot("popup.png")
shot("search.png", "invoice")
theme.set_finish("aurora")
app.setPalette(theme.palette())
tray.key_problems = {}                  # Linux has no keys-from-any-program: not shown on Windows
d = OptionsDialog(tray)
d.show(); app.processEvents()
d.grab().save(str(out / "options_aurora.png"))
print(out / "options_aurora.png")
d.close()
theme.set_finish("obsidian")
tray.watcher.stop()
app.clipboard().clear()

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PARAGON_FAMILY_FILE"] = os.path.join(__import__("tempfile").mkdtemp(prefix="family-"), "finish")  # never the real choice


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    # Tests never write the real settings (QSettings -> INI files in a temp folder) or the real clip history.
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from pr7cb import theme
    os.environ["PR7CB_DATA"] = str(tmp_path_factory.mktemp("data"))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path_factory.mktemp("settings")))
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    theme.load_fonts()
    app.setPalette(theme.palette())
    yield app
    for w in app.topLevelWidgets():
        w.close()
    app.clipboard().clear()          # PySide's offscreen clipboard crashes at exit while it holds data
    app.processEvents()


@pytest.fixture
def clean_settings(qapp):
    from PySide6.QtCore import QSettings
    s = QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, "Paragon", "PR7-CB")
    s.clear(); s.sync()
    yield
    s.clear(); s.sync()


@pytest.fixture
def store(tmp_path):
    from pr7cb.store import Store
    s = Store(str(tmp_path / "clips.db"))
    yield s
    s.close()


@pytest.fixture
def copy(qapp):
    """copy(text=..., html=..., image=..., files=[...], private=...) puts it on the real clipboard and lets the
    watcher see it (the offscreen clipboard signals; the watcher reads a moment later)."""
    from PySide6.QtCore import QMimeData, QUrl

    def do(text=None, html=None, image=None, files=None, formats=None):
        md = QMimeData()
        if text is not None:
            md.setText(text)
        if html is not None:
            md.setHtml(html)
        if image is not None:
            md.setImageData(image)
        if files is not None:
            md.setUrls([QUrl.fromLocalFile(str(f)) for f in files])
        for name, data in (formats or {}).items():
            md.setData(name, data)
        qapp.clipboard().setMimeData(md)
        for _ in range(3):
            qapp.processEvents()
    return do


@pytest.fixture
def tray(qapp, clean_settings, store):
    from pr7cb.tray import TrayApp
    t = TrayApp(store, show_tray=False, source=lambda: "PR7-W")
    t.pastes = []
    t.paste_keys = lambda hwnd: t.pastes.append(hwnd) or True
    t.said = []
    t.answers["say"] = lambda kind, text: t.said.append((kind, text))
    t.popup.keep_open = True                    # offscreen windows don't keep focus: don't close on "click away"
    yield t
    t.popup.hide()
    t.hotkeys.unregister()
    t.watcher.stop()

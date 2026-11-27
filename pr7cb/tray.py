"""PR7-CB in the notification area, as Ditto lives: the history, the watcher, the key, the popup and Options.

Pasting (Ditto's way): the clip goes on the clipboard (not recorded again), moves to the top, then the program that
was in front when the key was pressed gets the focus back and Ctrl+V. With ENTER set to "Copy only", the clip is just
put on the clipboard. `answers` replaces dialogs and `paste` the key presses in tests."""

from __future__ import annotations

import json
import os
import sys

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMenu, QMessageBox, QPushButton, QSpinBox, QSystemTrayIcon, QVBoxLayout)

from . import __version__, finish, hotkeys, settings, theme, widgets, winclip
from .clipwatch import Watcher
from .popup import Popup
from .store import Clip, Store

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULTS = {"key_show": "Ctrl+`", "keep": 500, "days": 30, "enter": "paste", "popup_at": "caret",
            "ignore": ["PR7-PM", "KeePassXC", "KeePass", "1Password", "Bitwarden"], "plain_default": False,
            "keep_images": True, "max_image_mb": 20}


def option(key: str):
    d = DEFAULTS[key]
    if isinstance(d, bool):
        return settings.get_bool(key, d)
    if isinstance(d, int):
        return settings.get_int(key, d)
    if isinstance(d, list):
        v = settings.get(key, "")
        if not v:
            return list(d)
        try:
            got = json.loads(v)
            return got if isinstance(got, list) else list(d)
        except ValueError:
            return list(d)
    return settings.get(key, d)


AUTOSTART_NAME = "paragon-pr7-cb.desktop"


def autostart_file() -> str:
    """Linux: your own sign-in autostart entry (freedesktop.org's autostart folder; Plasma reads it)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "autostart", AUTOSTART_NAME)


def system_autostart() -> bool:
    """PR7-OS starts PR7-CB for everyone (/etc/xdg/autostart); your own entry of the same name overrides it."""
    dirs = (os.environ.get("XDG_CONFIG_DIRS") or "/etc/xdg").split(":")
    return any(os.path.exists(os.path.join(d, "autostart", AUTOSTART_NAME)) for d in dirs if d)


def start_with_windows(on: bool | None = None) -> bool:
    """Read (on=None) or set what starts PR7-CB (quietly) when you sign in: the HKCU Run entry on Windows, an autostart
    entry on Linux; off while PR7-OS starts it for everyone = your own entry with Hidden=true (PR7-Q's way)."""
    if sys.platform != "win32":
        path = autostart_file()
        if on is None:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return "\nHidden=true" not in f.read()
            return system_autostart()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if on:
            import shlex
            import shutil
            command = shutil.which("pr7-cb") or f"{shlex.quote(sys.executable)} -m pr7cb"
            with open(path, "w", encoding="utf-8") as f:
                f.write("[Desktop Entry]\nType=Application\nName=Paragon PR7-CB\nComment=Clipboard history\n"
                        f"Exec={command} --tray\nIcon=paragon-pr7-cb\nX-GNOME-Autostart-enabled=true\n")
        elif system_autostart():
            with open(path, "w", encoding="utf-8") as f:
                f.write("[Desktop Entry]\nType=Application\nName=Paragon PR7-CB\nHidden=true\n")
        elif os.path.exists(path):
            os.remove(path)
        return on
    import winreg
    exe = f'"{sys.executable}" --tray' if getattr(sys, "frozen", False) else \
        f'"{sys.executable.replace("python.exe", "pythonw.exe")}" -m pr7cb --tray'
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as k:
        if on is None:
            try:
                winreg.QueryValueEx(k, "Paragon PR7-CB")
                return True
            except OSError:
                return False
        if on:
            winreg.SetValueEx(k, "Paragon PR7-CB", 0, winreg.REG_SZ, exe)
        else:
            try:
                winreg.DeleteValue(k, "Paragon PR7-CB")
            except OSError:
                pass
        return on


class TrayApp(QObject):
    pasted = Signal(object, bool)

    def __init__(self, store: Store | None = None, show_tray: bool = True, source=None, klipper_source=None):
        super().__init__()
        self.answers: dict = {}
        self.store = store or Store()
        self.watcher = Watcher(self.store, self._watch_options, source=source)
        self.watcher.recorded.connect(lambda _: self._maybe_trim())
        self.klipper = None                     # Linux (Plasma): Klipper feeds the history (klipper.py)
        if sys.platform != "win32" and klipper_source is not False:
            from .klipper import KlipperSource
            self.klipper = klipper_source or KlipperSource(self.store, self.watcher, parent=self)
            self.klipper.recorded.connect(lambda _: self._maybe_trim())
        self.popup = Popup(self.store)
        self.popup.chosen.connect(self.paste)
        self.popup.menu_wanted.connect(lambda pos: self.menu.exec(pos))
        self.hotkeys = hotkeys.Hotkeys()
        self.previous = None                    # the window that was in front when the key was pressed
        self.paste_keys = winclip.paste_into    # tests: a stand-in
        self.anchor = None
        self._build_menu()
        self.tray = None
        if show_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(QApplication.windowIcon() or QIcon(), self)
            self.tray.setToolTip("Paragon PR7-CB")
            self.tray.setContextMenu(self.menu)
            self.tray.activated.connect(lambda reason: self.show_popup(at_mouse=True)
                                        if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
            self.tray.show()
        self.key_problems = self.register_keys()
        self.trim()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.trim)
        self._timer.start(3600 * 1000)          # forget old clips once an hour too

    def _watch_options(self) -> dict:
        return {"ignore": option("ignore"), "keep_images": option("keep_images"),
                "max_image": option("max_image_mb") * 1_000_000}

    # ---------------------------------------------------------------- the menu
    def _build_menu(self):
        m = QMenu()
        self.acts = {}
        self.acts["show"] = m.addAction(self._show_text(), lambda: self.show_popup(at_mouse=True))
        self.acts["pause"] = m.addAction("Pause recording")
        self.acts["pause"].setCheckable(True)
        self.acts["pause"].toggled.connect(self.pause)
        m.addSeparator()
        fin = m.addMenu("Finish")
        for name in ("obsidian", "aurora"):
            a = fin.addAction(name.upper(), lambda n=name: self.set_finish(n))
            a.setCheckable(True)
            a.setChecked(theme.FINISH == name)
            self.acts[f"finish_{name}"] = a
        m.addAction("Options...", self.options)
        m.addAction("Clear history...", self.clear)
        m.addSeparator()
        m.addAction("Check for updates...", self.check_updates)
        m.addAction("About PR7-CB", lambda: self._say("info", f"Paragon PR7-CB {__version__}\nClipboard history, the "
                                                              "way Ditto keeps it."))
        m.addSeparator()
        m.addAction("Exit", self.quit)
        self.menu = m

    def _show_text(self) -> str:
        return f"Show clips\t{option('key_show')}"

    def register_keys(self) -> dict:
        problems = self.hotkeys.register({"show": (option("key_show"), lambda: self.show_popup())})
        if problems and hotkeys.available() and self.tray:
            self.tray.showMessage("PR7-CB", "\n".join(dict.fromkeys(problems.values())),
                                  QSystemTrayIcon.MessageIcon.Warning, 8000)
        self.acts["show"].setText(self._show_text())
        return problems

    # ---------------------------------------------------------------- showing and pasting
    def show_popup(self, at_mouse: bool = False):
        self.previous = winclip.foreground()
        point = None
        if QApplication.platformName().startswith("wayland"):     # the pointer isn't known there: the screen's middle
            self.popup.restyle()
            self.popup.show_at(None)
            return
        if not at_mouse and option("popup_at") == "caret":
            got = winclip.caret(self.previous)
            if got:
                point = QPoint(*got)
                ratio = QApplication.primaryScreen().devicePixelRatio()      # Windows gives physical pixels
                point = QPoint(int(point.x() / ratio), int(point.y() / ratio))
        self.popup.restyle()
        self.popup.show_at(point or QCursor.pos())

    def paste(self, clip: Clip, plain: bool = False):
        plain = plain != option("plain_default")            # Shift+Enter flips the default
        self.watcher.put(clip, plain)
        self.store.touch(clip.id)
        self.pasted.emit(clip, plain)
        if option("enter") == "paste" and self.previous:
            prev = self.previous
            QTimer.singleShot(60, lambda: self.paste_keys(prev))

    def pause(self, on: bool):
        self.watcher.paused = on
        if self.klipper is not None:
            self.klipper.paused = on
        if self.tray:
            self.tray.setToolTip("Paragon PR7-CB (paused)" if on else "Paragon PR7-CB")

    # ---------------------------------------------------------------- keeping the history in bounds
    def trim(self):
        self.store.trim(option("keep"), option("days"))

    def _maybe_trim(self):
        if self.store.count() > option("keep") + 50:
            self.trim()

    def clear(self):
        if self._ask("clear", "Forget every clip that isn't pinned?"):
            self.store.clear(keep_pinned=True)
            self.popup.refresh()

    # ---------------------------------------------------------------- Options
    def set_finish(self, name: str):
        """OBSIDIAN or AURORA, for the popup and (finish.py) every other family app."""
        theme.set_finish(name)
        finish.set(theme.FINISH)                 # every family app follows (finish.py)
        settings.set("finish", theme.FINISH)
        app = QApplication.instance()
        app.setPalette(theme.palette())
        self.popup.restyle()
        self.popup.update()
        for n in ("obsidian", "aurora"):
            if f"finish_{n}" in self.acts:
                self.acts[f"finish_{n}"].setChecked(theme.FINISH == n)

    def options(self):
        d = OptionsDialog(self)
        self.options_dialog = d
        ok = self.answers["options"](d) if "options" in self.answers else d.exec() == QDialog.DialogCode.Accepted
        if ok:
            d.save()
            self.key_problems = self.register_keys()
            self.trim()

    def check_updates(self):
        from . import update_ui
        update_ui.check(self.anchor, manual=True)

    def quit(self):
        self.watcher.stop()
        self.hotkeys.unregister()
        QApplication.instance().quit()

    # ---------------------------------------------------------------- questions
    def _ask(self, kind: str, text: str) -> bool:
        if kind in self.answers:
            a = self.answers[kind]
            return a(text) if callable(a) else a
        return QMessageBox.question(None, "Paragon PR7-CB", text) == QMessageBox.StandardButton.Yes

    def _say(self, kind: str, text: str):
        if "say" in self.answers:
            self.answers["say"](kind, text)
            return
        (QMessageBox.warning if kind == "warning" else QMessageBox.information)(None, "Paragon PR7-CB", text)


class OptionsDialog(QDialog):
    def __init__(self, app: TrayApp):
        super().__init__()
        self.app = app
        self.setWindowTitle("PR7-CB Options")
        self.setPalette(theme.palette())
        self.setStyleSheet(theme.stylesheet() + f"""QPushButton[kind="primary"] {{ background: {theme.qss_gradient()};
            color: #FFFFFF; border: none; font-weight: 600; padding: 7px 22px; }}""")
        self.resize(560, 620)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 16); v.setSpacing(0)
        v.addWidget(widgets.Header("CLIPBOARD"))
        g = QGridLayout(); g.setContentsMargins(22, 18, 22, 8); g.setHorizontalSpacing(16); g.setVerticalSpacing(12)
        self.key = QLineEdit(option("key_show"))
        self.keep = QSpinBox(); self.keep.setRange(10, 10000); self.keep.setSuffix(" clips"); self.keep.setValue(option("keep"))
        self.days = QComboBox()
        for n, text in ((7, "7 days"), (30, "30 days"), (90, "90 days"), (365, "A year"), (0, "Never")):
            self.days.addItem(text + (" (pinned clips: never)" if n else ""), n)
        self.days.setCurrentIndex(max(0, self.days.findData(option("days"))))
        self.enter = QComboBox()
        self.enter.addItem("Paste into the program I was in", "paste")
        self.enter.addItem("Copy only (I paste myself)", "copy")
        self.enter.setCurrentIndex(max(0, self.enter.findData(option("enter"))))
        self.at = QComboBox()
        self.at.addItem("The text cursor", "caret")
        self.at.addItem("The mouse pointer", "mouse")
        self.at.setCurrentIndex(max(0, self.at.findData(option("popup_at"))))
        for r, (name, w) in enumerate((("KEY TO OPEN", self.key), ("KEEP", self.keep), ("FORGET AFTER", self.days),
                                       ("ENTER", self.enter), ("POPUP AT", self.at))):
            lab = QLabel(name); f = lab.font(); f.setWeight(f.Weight.DemiBold); lab.setFont(f)
            g.addWidget(lab, r, 0)
            g.addWidget(w, r, 1)
        v.addLayout(g)
        box = QVBoxLayout(); box.setContentsMargins(22, 6, 22, 6); box.setSpacing(8)
        lab = QLabel("NEVER RECORD COPIES FROM"); f = lab.font(); f.setWeight(f.Weight.DemiBold); lab.setFont(f)
        box.addWidget(lab)
        self.ignore = QLineEdit(";  ".join(option("ignore")))
        self.ignore.setPlaceholderText("Program names, separated by ;  (KeePassXC; 1Password)")
        box.addWidget(self.ignore)
        note = QLabel("Programs that mark a copy as private (password managers do) are never recorded either.")
        note.setProperty("role", "dim"); note.setWordWrap(True)
        box.addWidget(note)
        self.plain = QCheckBox("Paste as plain text by default"); self.plain.setChecked(option("plain_default"))
        self.images = QCheckBox("Keep pictures (up to 20 MB each)"); self.images.setChecked(option("keep_images"))
        self.startup = QCheckBox("Start PR7-CB with Windows" if sys.platform == "win32" else "Start PR7-CB when I sign in")
        self.startup.setChecked(start_with_windows())
        from . import update_ui
        self.updates = QCheckBox("Check for updates automatically"); self.updates.setChecked(update_ui.auto_enabled())
        for c in (self.plain, self.images, self.startup, self.updates):
            box.addWidget(c)
        if app.key_problems:
            warn = QLabel("\n".join(dict.fromkeys(app.key_problems.values())))
            warn.setProperty("role", "ok"); warn.setWordWrap(True)
            box.addWidget(warn)
        v.addLayout(box)
        v.addStretch(1)
        b = QHBoxLayout(); b.setContentsMargins(22, 0, 22, 0); b.addStretch(1)
        ok = QPushButton("OK"); ok.setProperty("kind", "primary"); ok.setDefault(True); ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        b.addWidget(ok); b.addWidget(cancel)
        v.addLayout(b)

    def save(self):
        settings.set("key_show", self.key.text().strip() or DEFAULTS["key_show"])
        settings.set("keep", self.keep.value())
        settings.set("days", self.days.currentData())
        settings.set("enter", self.enter.currentData())
        settings.set("popup_at", self.at.currentData())
        settings.set("ignore", [n.strip() for n in self.ignore.text().split(";") if n.strip()])
        settings.set("plain_default", self.plain.isChecked())
        settings.set("keep_images", self.images.isChecked())
        if self.startup.isChecked() != start_with_windows():
            start_with_windows(self.startup.isChecked())
        from . import update_ui
        update_ui.set_auto(self.updates.isChecked())

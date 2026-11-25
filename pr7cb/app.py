"""Start PR7-CB.

    PR7-CB.exe                    run in the notification area (Ctrl+` opens the clips); started again, it opens the
                                  clips in the running PR7-CB instead of starting twice
    PR7-CB.exe --tray             start quietly (Windows' start-up entry)
    PR7-CB.exe --startup on|off   start with Windows or not (the installer's task)
    PR7-CB.exe --unregister       take the start-up entry away (the uninstaller)
    PR7-CB.exe --version
    PR7-CB.exe --selftest OUT.json   copy text, HTML, a picture, files and a private copy through the real clipboard
                                     offscreen, and write what was kept and pasted back (CI checks the installed exe)
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import sys

TIMEOUT_MS = 1500


def server_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = "user"
    return "Paragon-PR7-CB-" + hashlib.sha1(user.encode()).hexdigest()[:12]


def hand_over(show: bool) -> bool:
    from PySide6.QtNetwork import QLocalSocket
    s = QLocalSocket()
    s.connectToServer(server_name())
    if not s.waitForConnected(TIMEOUT_MS):
        return False
    s.write(json.dumps({"show": show}).encode() + b"\n")
    s.flush()
    s.waitForBytesWritten(TIMEOUT_MS)
    if not s.waitForDisconnected(TIMEOUT_MS):
        s.disconnectFromServer()
    return True


def listen(tray):
    """Later starts hand over to this PR7-CB (PR7-R's hand-off, with its Windows fix)."""
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer(tray)
    QLocalServer.removeServer(server_name())
    if not server.listen(server_name()):
        return None

    def connection():
        sock = server.nextPendingConnection()
        if sock is None:
            return
        buf = bytearray()
        done = []

        def read():
            buf.extend(bytes(sock.readAll()))
            if buf.endswith(b"\n") and not done:
                done.append(True)
                try:
                    msg = json.loads(buf.decode())
                except ValueError:
                    return
                if msg.get("show"):
                    tray.show_popup(at_mouse=True)
                sock.disconnectFromServer()
        sock.readyRead.connect(read)
        sock.disconnected.connect(read)
        if sock.bytesAvailable():
            read()
    server.newConnection.connect(connection)
    tray.instance_server = server
    return server


def selftest(out: str) -> int:
    import tempfile
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    data = tempfile.mkdtemp()
    os.environ["PR7CB_DATA"] = data
    from PySide6.QtCore import QMimeData, QSettings, QUrl
    from PySide6.QtGui import QColor, QFontDatabase, QImage
    from PySide6.QtWidgets import QApplication
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())
    result = {}
    try:
        from . import __version__, theme
        from .store import Store
        from .tray import TrayApp
        app = QApplication.instance() or QApplication(sys.argv[:1])
        theme.load_fonts()
        tray = TrayApp(Store(), show_tray=False, source=lambda: "selftest")
        cb = app.clipboard()
        w = tray.watcher

        def copy(md):
            cb.setMimeData(md)
            app.processEvents()
            w.changed()                          # the offscreen clipboard may not signal: look as Windows would
        md = QMimeData(); md.setText("Hello from the self-test"); md.setHtml("<b>Hello</b> from the self-test")
        copy(md)
        img = QImage(120, 80, QImage.Format.Format_RGB32); img.fill(QColor("#DE0639"))
        md = QMimeData(); md.setImageData(img); copy(md)
        f = os.path.join(data, "note.txt")
        open(f, "w").write("x")
        md = QMimeData(); md.setUrls([QUrl.fromLocalFile(f)]); copy(md)
        md = QMimeData(); md.setText("secret password"); md.setData("ExcludeClipboardContentFromMonitorProcessing",
                                                                  b"\0")
        copy(md)
        clips = tray.store.list()
        tray.popup.show_at(None)
        tray.popup.search.setText("hello")
        found = [c.title() for c in tray.popup.model.clips]
        tray.popup.hide()
        tray.paste(clips[-1], plain=True)        # the text clip, as plain text
        app.processEvents()
        result = {"version": __version__, "kinds": [c.kind for c in clips], "count": len(clips),
                  "private_kept": any("secret" in c.text for c in clips), "found": found,
                  "pasted": cb.text(), "pasted_html": cb.mimeData().hasHtml(),
                  "image": [clips[1].width, clips[1].height] if len(clips) > 1 else None,
                  "fonts": "Inter" in QFontDatabase.families(),
                  "db": os.path.exists(os.path.join(data, "clips.db"))}
        tray.store.close()
        cb.clear()          # PySide's offscreen clipboard crashes at exit while it still holds data (not on Windows)
    except Exception as e:  # noqa: BLE001 - reported in the output
        result = {"error": f"{type(e).__name__}: {e}"}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    return 0 if "kinds" in result else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--version"]:
        from . import __version__
        print(__version__)
        return 0
    if argv[:1] == ["--selftest"] and len(argv) == 2:
        return selftest(argv[1])
    if argv[:1] == ["--startup"] and len(argv) == 2:
        from .tray import start_with_windows
        start_with_windows(argv[1].lower() in ("on", "1", "yes"))
        return 0
    if argv[:1] == ["--unregister"]:
        from .tray import start_with_windows
        start_with_windows(False)
        return 0
    quiet = "--tray" in argv
    from PySide6.QtWidgets import QApplication

    from . import settings, theme
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setOrganizationName("Paragon")
    app.setApplicationName("PR7-CB")
    app.setQuitOnLastWindowClosed(False)          # it lives in the notification area
    if hand_over(not quiet):
        return 0
    theme.set_finish(settings.get("finish", "obsidian"))
    theme.load_fonts()
    app.setPalette(theme.palette())
    from PySide6.QtGui import QIcon
    icon = os.path.join(os.path.dirname(__file__), "icons", "app.ico")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    from .tray import TrayApp, option
    tray = TrayApp()
    listen(tray)
    if not quiet and tray.tray:
        tray.tray.showMessage("PR7-CB is keeping your clipboard", f"{option('key_show')} opens your clips. Its menu "
                              "is here in the notification area.", tray.tray.MessageIcon.Information, 5000)
    from PySide6.QtWidgets import QWidget
    tray.anchor = QWidget()                       # a parent for the update dialog
    from . import update_ui
    update_ui.start(tray.anchor)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

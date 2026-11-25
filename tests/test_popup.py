import json
import os
import subprocess
import sys
import time

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from pr7cb import __version__, app, hotkeys, settings
from pr7cb.popup import when_text
from pr7cb.store import Clip


def fill(store):
    for i, text in enumerate(["Thursday 4 pm call", "Invoice 2026-114 Static Bloom", "https://example.org/a",
                              "def squarify(sizes, box):", "Last Light (Extended Mix)"]):
        store.add(Clip("text", text, source="PR7-W"), now=1000 + i)


def test_the_popup_lists_searches_and_pastes(tray, qapp):
    fill(tray.store)
    tray.previous = 4242                       # the window that was in front
    tray.popup.show_at(QPoint(300, 200))
    p = tray.popup
    assert p.isVisible() and [c.text for c in p.model.clips][0] == "Last Light (Extended Mix)"
    assert p.pos().y() >= 200                  # below the text cursor
    QTest.keyClicks(p.search, "invoice")
    assert [c.text for c in p.model.clips] == ["Invoice 2026-114 Static Bloom"]
    p.grab()                                   # the delegate paints the match without trouble
    QTest.keyClick(p.search, Qt.Key.Key_Return)
    assert not p.isVisible() and qapp.clipboard().text() == "Invoice 2026-114 Static Bloom"
    QTest.qWait(150)
    assert tray.pastes == [4242]               # focus back to that window, then Ctrl+V
    assert tray.store.list()[0].text == "Invoice 2026-114 Static Bloom"          # pasted: moved to the top


def test_keys(tray, qapp):
    fill(tray.store)
    p = tray.popup
    p.show_at(None)
    QTest.keyClick(p.search, Qt.Key.Key_Down)
    assert p.list.currentIndex().row() == 1
    QTest.keyClick(p.search, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier)
    assert tray.store.list("squarify")[0].pinned
    QTest.keyClick(p.search, Qt.Key.Key_Delete)
    assert tray.store.count() == 4 and "squarify" not in [c.text for c in p.model.clips][1]
    QTest.keyClick(p.search, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
    assert qapp.clipboard().text() == tray.store.list()[0].text
    p.show_at(None)
    QTest.keyClick(p.search, Qt.Key.Key_Escape)
    assert not p.isVisible()


def test_copy_only_and_plain_by_default(tray, qapp):
    tray.store.add(Clip("text", "styled", html="<b>styled</b>"))
    settings.set("enter", "copy")
    settings.set("plain_default", True)
    tray.previous = 7
    tray.popup.show_at(None)
    QTest.keyClick(tray.popup.search, Qt.Key.Key_Return)
    QTest.qWait(150)
    assert tray.pastes == [] and not qapp.clipboard().mimeData().hasHtml()     # just copied, as plain text
    tray.popup.show_at(None)
    QTest.keyClick(tray.popup.search, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)   # Shift flips it
    assert qapp.clipboard().mimeData().html() == "<b>styled</b>"


def test_options_clear_and_limits(tray):
    for i in range(30):
        tray.store.add(Clip("text", f"c{i}"), now=time.time() - i)
    tray.answers["options"] = lambda d: (d.keep.setValue(10), d.ignore.setText("KeePassXC; Bitwarden"), True)[-1]
    tray.options()
    assert settings.get_int("keep") == 10 and json.loads(settings.get("ignore")) == ["KeePassXC", "Bitwarden"]
    assert tray.store.count() == 10
    tray.answers["clear"] = True
    tray.store.pin(tray.store.list()[0].id)
    tray.clear()
    assert tray.store.count() == 1
    assert [a.text().split("\t")[0] for a in tray.menu.actions() if a.text()][:2] == ["Show clips", "Pause recording"]


def test_backtick_key_and_when():
    assert hotkeys.parse("Ctrl+`") == (hotkeys.MOD_CONTROL, 0xC0)
    assert hotkeys.parse("Ctrl+Shift+V") == (hotkeys.MOD_CONTROL | hotkeys.MOD_SHIFT, ord("V"))
    now = 1_000_000
    assert [when_text(now - s, now) for s in (5, 300, 7200, 90000, 3 * 86400)] == \
        ["just now", "5 min ago", "2 hours ago", "yesterday", "3 days ago"]


def test_version(capsys):
    assert app.main(["--version"]) == 0 and capsys.readouterr().out.strip() == __version__


def test_a_second_start_opens_the_running_one(tray, qapp):
    shown = []
    tray.show_popup = lambda at_mouse=False: shown.append(at_mouse)
    assert app.listen(tray) is not None
    code = ("import sys; sys.path.insert(0, sys.argv[1]); from PySide6.QtCore import QCoreApplication; "
            "a = QCoreApplication([]); from pr7cb import app; sys.exit(0 if app.hand_over(True) else 1)")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.Popen([sys.executable, "-c", code, root])
    end = time.time() + 20
    while (not shown or proc.poll() is None) and time.time() < end:
        qapp.processEvents(); time.sleep(0.01)
    assert proc.wait(5) == 0 and shown == [True]
    tray.instance_server.close()


def test_selftest(tmp_path):
    out = tmp_path / "out.json"
    code = subprocess.run([sys.executable, "-m", "pr7cb", "--selftest", str(out)],
                          cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), timeout=120).returncode
    got = json.loads(out.read_text())
    assert code == 0 and got["kinds"] == ["files", "image", "text"] and not got["private_kept"]
    assert got["found"] == ["Hello from the self-test"] and got["pasted"] == "Hello from the self-test"
    assert got["pasted_html"] is False and got["image"] == [120, 80] and got["fonts"] and got["db"]

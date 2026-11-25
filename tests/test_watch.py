from PySide6.QtGui import QColor, QImage

from pr7cb import clipwatch
from pr7cb.clipwatch import Watcher


def watcher(store, **opts):
    w = Watcher(store, options=lambda: opts, source=lambda: opts.get("_source", "PR7-W"))
    return w


def picture(w=40, h=30, colour="#DE0639"):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(colour))
    return img


def test_every_kind_of_copy_is_kept(store, copy, tmp_path):
    w = watcher(store)
    copy(text="Hello", html="<b>Hello</b>")
    copy(image=picture())
    f = tmp_path / "report.pdf"; f.write_bytes(b"x")
    copy(files=[f])
    kinds = [(c.kind, c.source) for c in store.list()]
    assert kinds == [("files", "PR7-W"), ("image", "PR7-W"), ("text", "PR7-W")]
    text = store.list("hello")[0]
    assert text.html == "<b>Hello</b>"
    pic = store.list()[1]
    back = QImage(); back.loadFromData(pic.image, "PNG")
    assert (back.width(), back.height()) == (40, 30) and back.pixelColor(5, 5) == QColor("#DE0639")
    assert store.list()[0].files == [str(f)]
    w.stop()


def test_text_wins_over_the_picture_office_adds(store, copy):
    w = watcher(store)
    copy(text="A paragraph from Word", image=picture())
    assert [c.kind for c in store.list()] == ["text"]
    w.stop()


def test_private_copies_are_never_kept(store, copy):
    w = watcher(store)
    copy(text="hunter2", formats={"ExcludeClipboardContentFromMonitorProcessing": b"\x00"})
    copy(text="also secret", formats={"Clipboard Viewer Ignore": b"\x00"})
    copy(text="no history please", formats={"CanIncludeInClipboardHistory": b"\x00\x00\x00\x00"})
    copy(text="history is fine", formats={"CanIncludeInClipboardHistory": b"\x01\x00\x00\x00"})
    assert [c.text for c in store.list()] == ["history is fine"]
    w.stop()


def test_ignored_programs_pause_and_big_pictures(store, copy):
    w = watcher(store, ignore=["KeePassXC.exe", "1Password"], _source="KeePassXC", max_image=2000)
    copy(text="from the password manager")
    assert store.count() == 0
    w.options = lambda: {"max_image": 2000}
    w.source = lambda: "PR7-W"
    copy(image=picture(400, 300))                          # bigger than 2000 bytes as PNG? noise makes it so
    w.paused = True
    copy(text="while paused")
    w.paused = False
    copy(text="after")
    assert [c.text for c in store.list()][:1] == ["after"] and "while paused" not in {c.text for c in store.list()}
    w.options = lambda: {"keep_images": False}
    copy(image=picture(10, 10, "#CD6619"))
    assert not any(c.kind == "image" and c.width == 10 for c in store.list())
    w.stop()


def test_pasting_back_is_not_recorded_twice(store, copy, qapp):
    w = watcher(store)
    copy(text="one", html="<i>one</i>")
    copy(text="two")
    one = store.list("one")[0]
    w.put(one)
    for _ in range(3):
        qapp.processEvents()
    assert store.count() == 2 and qapp.clipboard().mimeData().html() == "<i>one</i>"
    w.put(one, plain=True)
    for _ in range(3):
        qapp.processEvents()
    assert store.count() == 2 and not qapp.clipboard().mimeData().hasHtml() and qapp.clipboard().text() == "one"
    w.stop()


def test_mime_round_trip(tmp_path):
    from pr7cb.store import Clip
    md = clipwatch.mime_of(Clip("files", files=[str(tmp_path / "a.txt")]))
    assert [u.toLocalFile() for u in md.urls()] == [str(tmp_path / "a.txt")]
    assert clipwatch.clip_from(md).kind == "files"

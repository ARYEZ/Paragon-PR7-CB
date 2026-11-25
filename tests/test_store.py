from pr7cb.store import Clip, Store


def test_copies_are_kept_newest_first_and_again_moves_to_the_top(store):
    a = store.add(Clip("text", "first"), now=100)
    store.add(Clip("text", "second"), now=200)
    assert [c.text for c in store.list()] == ["second", "first"]
    again = store.add(Clip("text", "first", source="Firefox"), now=300)
    assert again == a and store.count() == 2                       # not kept twice
    assert [c.text for c in store.list()] == ["first", "second"] and store.get(a).source == "Firefox"


def test_search_every_word_any_case_any_language(store):
    store.add(Clip("text", "Invoice 2026-114 for Static Bloom"), now=1)
    store.add(Clip("text", "Rechnung für Über-Mix"), now=2)
    store.add(Clip("text", "100% done_ok"), now=3)
    store.add(Clip("files", "C:\\Music\\Last Light.flac", files=["C:\\Music\\Last Light.flac"]), now=4)
    assert [c.text for c in store.list("invoice bloom")] == ["Invoice 2026-114 for Static Bloom"]
    assert [c.text for c in store.list("ÜBER für")] == ["Rechnung für Über-Mix"]       # casefold, not just A-Z
    assert [c.text for c in store.list("100%")] == ["100% done_ok"]                    # % and _ are just letters
    assert len(store.list("_")) == 1 and store.list("light")[0].kind == "files"
    assert store.list("nothing like this") == []


def test_trim_keeps_the_newest_and_every_pinned_clip(store):
    day = 86400
    for i in range(10):
        store.add(Clip("text", f"clip {i}"), now=i * day)
    pinned = store.list("clip 0")[0].id
    store.pin(pinned)
    gone = store.trim(keep=5, days=0, now=10 * day)
    assert gone == 4 and store.count() == 6                        # 5 newest + the pinned one
    assert {c.text for c in store.list()} == {"clip 0", "clip 5", "clip 6", "clip 7", "clip 8", "clip 9"}
    store.trim(keep=100, days=3, now=10 * day)                     # older than 3 days: gone, pinned stays
    assert {c.text for c in store.list()} == {"clip 0", "clip 7", "clip 8", "clip 9"}
    store.clear()
    assert [c.text for c in store.list()] == ["clip 0"]


def test_pictures_and_files_survive_a_restart(tmp_path):
    path = str(tmp_path / "c.db")
    s = Store(path)
    s.add(Clip("image", "Picture", image=b"\x89PNG fake", width=12, height=8))
    s.add(Clip("files", "a\nb", files=["C:\\a.txt", "C:\\b.txt"]))
    s.close()
    s = Store(path)
    files, pic = s.list()
    assert files.files == ["C:\\a.txt", "C:\\b.txt"] and files.title() == "2 files: a.txt, b.txt"
    assert pic.image == b"\x89PNG fake" and pic.title() == "Picture  ·  12 × 8"
    s.close()


def test_titles():
    assert Clip("text", "\n  line one \n\n line two").title() == "line one ⏎ line two"
    assert Clip("files", "", files=["C:\\x\\report.pdf"]).title() == "report.pdf"

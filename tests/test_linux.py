"""PR7-CB on Linux's Plasma (PR7-OS): Klipper feeds the history (a stand-in Klipper process on a private session bus,
answering as Plasma's does), PR7-CB's own pastes aren't recorded twice, pausing stops it, start at sign-in."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pr7cb import klipper, tray as traymod
from pr7cb.store import Clip, Store

STANDIN = Path(__file__).resolve().parent / "standin_klipper.py"
needs_bus = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("dbus-daemon"), reason="needs dbus-daemon")


@pytest.fixture
def plasma(tmp_path):
    daemon = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True)
    address = daemon.stdout.readline().strip()
    hist = tmp_path / "klipper.txt"
    hist.write_text("second copy\nfirst copy\n")
    proc = subprocess.Popen([sys.executable, str(STANDIN), address, str(hist)], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "READY"
    yield address, hist
    proc.terminate()
    proc.wait()
    daemon.terminate()
    daemon.wait()


@needs_bus
def test_klippers_history_becomes_pr7cbs(qapp, plasma, tmp_path):
    address, hist = plasma
    assert klipper.history(address) == ["second copy", "first copy"]
    store = Store(str(tmp_path / "clips.db"))
    src = klipper.KlipperSource(store, address=address, interval_ms=60_000)
    assert src.poll() == 2                                       # the first look: Klipper's whole history
    assert [c.text for c in store.list("")] == ["second copy", "first copy"]
    assert src.poll() == 0                                       # nothing new
    hist.write_text("a new copy\\nwith two lines\nsecond copy\nfirst copy\n")
    assert src.poll() == 1
    assert store.list("")[0].text == "a new copy\nwith two lines" and store.list("")[0].source == "Klipper"
    src.paused = True
    hist.write_text("while paused\na new copy\\nwith two lines\n")
    assert src.poll() == 0 and "while paused" not in [c.text for c in store.list("")]
    src.stop()


@needs_bus
def test_what_pr7cb_pasted_isnt_recorded_again(qapp, plasma, tmp_path):
    address, hist = plasma
    store = Store(str(tmp_path / "clips.db"))

    class Watcher:                                               # what clipwatch.Watcher.put leaves behind
        _plain_text = None
        _ours = Clip(kind="text", text="chosen from the popup").digest()
    src = klipper.KlipperSource(store, Watcher(), address=address, interval_ms=60_000)
    src.poll()
    before = store.count()
    hist.write_text("chosen from the popup\nsecond copy\nfirst copy\n")    # Klipper saw PR7-CB's own paste
    assert src.poll() == 0 and store.count() == before


def test_no_klipper_means_nothing(qapp, tmp_path):
    assert klipper.history("unix:path=" + str(tmp_path / "no-bus")) is None
    src = klipper.KlipperSource(Store(str(tmp_path / "c.db")), address="unix:path=" + str(tmp_path / "no-bus"),
                                interval_ms=60_000)
    assert src.poll() == 0
    src.stop()


@pytest.mark.skipif(sys.platform == "win32", reason="Linux's autostart")
def test_start_at_sign_in(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CONFIG_DIRS", str(tmp_path / "xdg"))
    (tmp_path / "xdg/autostart").mkdir(parents=True)
    (tmp_path / "xdg/autostart/paragon-pr7-cb.desktop").write_text("[Desktop Entry]\nExec=pr7-cb --tray\n")
    assert traymod.start_with_windows() is True                  # PR7-OS starts it for everyone
    traymod.start_with_windows(False)
    assert "Hidden=true" in (tmp_path / "config/autostart/paragon-pr7-cb.desktop").read_text()
    assert traymod.start_with_windows() is False

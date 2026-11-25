"""What only real Windows can show (CI runs these): the key, the start-up entry, which program owns a copy."""
import os
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only (CI)")


def test_the_key_registers_and_lets_go(qapp):
    from pr7cb import hotkeys
    h = hotkeys.Hotkeys()
    problems = h.register({"show": ("Ctrl+Alt+Shift+F24", lambda: None)})     # a key nothing else holds
    assert problems == {} and len(h.ids) == 1
    h.unregister()
    assert not h.ids


@pytest.mark.skipif(not os.environ.get("CI"), reason="writes the registry: CI only")
def test_start_with_windows():
    from pr7cb.tray import start_with_windows
    try:
        assert start_with_windows(True) and start_with_windows() is True
        assert start_with_windows(False) is False and start_with_windows() is False
    finally:
        start_with_windows(False)


def test_a_copy_names_its_program(qapp):
    from pr7cb import winclip
    qapp.clipboard().setText("from this test")
    qapp.processEvents()
    name = winclip.clipboard_source().lower()
    assert name.startswith("python") or name.startswith("pr7-cb")
    qapp.clipboard().clear()

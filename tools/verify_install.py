"""Check a real install of PR7-CB-Setup.exe (CI, Windows): python tools/verify_install.py installed|uninstalled

`installed` runs the installed PR7-CB.exe --selftest (offscreen: text with HTML, a picture, files and a private copy
through the real clipboard; search; paste as plain text) and checks the start-with-Windows entry. `uninstalled`
checks it's all gone."""
import json
import os
import subprocess
import sys
import tempfile
import time
import winreg
from pathlib import Path

HKCU = winreg.HKEY_CURRENT_USER
APP = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "PR7-CB"
SHORTCUT = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Paragon PR7-CB.lnk"
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{5F4E0C50-1C11-4E53-A835-221E3BBB7509}_is1"
RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def value(path, name=""):
    try:
        with winreg.OpenKey(HKCU, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def check(ok, what, p):
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        p.append(what)


def installed():
    p = []
    exe = APP / "PR7-CB.exe"
    for f in (exe, APP / "unins000.exe", APP / "_internal" / "pr7cb" / "fonts" / "Inter-Regular.ttf",
              APP / "_internal" / "pr7cb" / "icons" / "app.ico"):
        check(f.is_file(), f"file {f}", p)
    check(SHORTCUT.is_file(), "Start menu shortcut", p)
    check(value(UNINSTALL, "DisplayName") == "Paragon PR7-CB", "Installed apps entry", p)
    run = value(RUN, "Paragon PR7-CB") or ""
    check(str(exe).lower() in run.lower() and "--tray" in run, f"starts with Windows: {run}", p)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.json"
        code = subprocess.run([str(exe), "--selftest", str(out)], timeout=180, check=False).returncode
        got = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        check(code == 0 and got.get("kinds") == ["files", "image", "text"], f"copies kept ({got})", p)
        check(got.get("private_kept") is False, "a private copy is not kept", p)
        check(got.get("found") == ["Hello from the self-test"], "search", p)
        check(got.get("pasted") == "Hello from the self-test" and got.get("pasted_html") is False,
              "pasted back as plain text", p)
        check(got.get("image") == [120, 80] and got.get("fonts") is True and got.get("db") is True,
              "the picture, Inter and the history file", p)
    return p


def uninstalled():
    deadline = time.time() + 60
    while True:
        p = []
        check(not (APP / "PR7-CB.exe").exists(), "program files removed", p)
        check(not SHORTCUT.exists(), "Start menu shortcut removed", p)
        check(value(UNINSTALL, "DisplayName") is None, "Installed apps entry removed", p)
        check(value(RUN, "Paragon PR7-CB") is None, "start-with-Windows entry removed", p)
        if not p or time.time() > deadline:
            return p
        print("... waiting for the uninstaller to finish")
        time.sleep(3)


if __name__ == "__main__":
    problems = {"installed": installed, "uninstalled": uninstalled}[sys.argv[1]]()
    print("\nALL OK" if not problems else f"\n{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)

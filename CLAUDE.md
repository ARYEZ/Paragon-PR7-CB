# Paragon PR7-CB: notes for Claude

**Paragon PR7-CB** is the owner's personal clipboard history: Python (**PySide6**) that **works the way Ditto works**,
in the Paragon family look (PR7-Z ... PR7-Q, PR7-U, PR7-DU `ARYEZ/Paragon-PR7-DU`). The repo is Paragon-PR7-CB
(Paragon-PR7-C was already taken). Windows 10/11 x64 is the target; it runs on Linux for tests. The owner writes
Python; explain the why of changes.

## How it's built

- `pr7cb/store.py` (no Qt): SQLite in `%APPDATA%\Paragon\PR7-CB\clips.db` (**PR7CB_DATA** overrides; tests always set
  it). `Clip` (text + html, image PNG, files), digest = same content -> moved to the top, not kept twice; `list(query)`
  every word through a Python `fold` (casefold) function; `trim(keep, days)` keeps pinned clips; `touch` on paste.
- `pr7cb/clipwatch.py`: `Watcher` reads QClipboard a moment after dataChanged (QTimer 0); `private(md)` =
  ExcludeClipboardContentFromMonitorProcessing / Clipboard Viewer Ignore / CanIncludeInClipboardHistory = 0;
  ignored programs (Options), pause, its own pastes (`put`) skipped; files > text > picture. `stop()` before closing.
- `pr7cb/winclip.py` (ctypes, Windows; no-ops elsewhere): `clipboard_source` (owner window's program), `caret`
  (GetGUIThreadInfo), `paste_into(hwnd)` (SetForegroundWindow, held modifiers released, Ctrl+V by SendInput).
- `pr7cb/popup.py`: `Popup` (frameless tool window; keys in `handle_key`), `ClipModel` (plain Python list model),
  `ClipDelegate` paints the rows (number, thumbnail, one elided line with the match in orange, meta, PINNED).
  `keep_open` stops it closing on deactivation (tests: offscreen windows don't keep focus).
- `pr7cb/tray.py`: `TrayApp` (menu, key via `hotkeys.py` = PR7-Q's with the punctuation keys, `paste` = put + touch +
  `paste_keys(previous)`, trim hourly), `OptionsDialog`, `start_with_windows` (HKCU Run "Paragon PR7-CB" --tray),
  `option()` with DEFAULTS. `answers` for questions in tests.
- `pr7cb/app.py`: one per user (QLocalSocket hand-off, PR7-R's Windows fix), `--tray`, `--startup on|off`,
  `--unregister`, `--selftest OUT.json` (CI runs it on the installed exe).
- **PySide's offscreen clipboard crashes at exit while it holds data** (a 6-line program shows it; not Windows'):
  anything offscreen that set the clipboard clears it before exiting (conftest, selftest, screenshots).
- Installer `installer/pr7cb.iss` (per user, AppId {5F4E0C50-1C11-4E53-A835-221E3BBB7509} permanent; tasks startup
  (ticked), desktopicon); CI installs it, `tools/verify_install.py installed|uninstalled`.
- Updates: `pr7cb/updates.py` / `update_ui.py` (the family's files, keep them in step; with PR7-U installed,
  update_ui offers it); `family.py`: the family's AppIds (PR7-CB included).

## The look (family rules)

- Theme is PR7-DU's (OBSIDIAN + AURORA). Colours: the family's only; Inter; labels UPPER CASE.
- The PR7-CB mark: PR7 `Logo.cpp` geometry plus C and B (`widgets.C_SHAPE`, `B_OUTER` / `B_COUNTERS`); icon "7CB" by
  `tools/make_icon.py`, wizard art by `tools/make_installer_art.py`. Check visuals with
  `QT_SCALE_FACTOR=2 python tools/screenshots.py OUT`.

## Rules

- Behaviour questions: do what Ditto does (keys, popup, paste, groups of options).
- Tests: `python -m pytest` (offscreen) with the real clipboard and a real SQLite file. Never the real settings or
  history (conftest), or, outside CI, the registry or global keys.
- Releases: bump `__version__` in `pr7cb/__init__.py` and add a `## x.y.z` section to CHANGELOG.md, then push: CI
  publishes that version by itself once every check has passed. Run workflow / `v*` tags still work.

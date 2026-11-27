# Changelog

## 0.3.0

PR7-CB runs on Linux's Plasma desktop (PR7-OS):
- **Klipper feeds the history.** On Wayland only the window in front may read the clipboard, so PR7-CB asks Plasma's
  own clipboard keeper (Klipper) once a second and keeps what's new: your history (search, pins, numbers, the popup)
  is PR7-CB's, the copies are the ones Plasma saw. The first time, Klipper's existing history comes in too. Copies
  marked private (PR7-PM's passwords) never reach Klipper, so never reach PR7-CB.
- **Choosing a clip puts it on the clipboard; press Ctrl+V to paste it.** Wayland doesn't let one program type into
  another, so PR7-CB can't paste for you there.
- The popup opens in the middle of the screen (Wayland doesn't say where the pointer is); Ctrl+` is a Plasma shortcut;
  start at sign-in is an autostart entry.
Nothing changes on Windows.

## 0.2.3

- The family list (`family.py`) knows the three newest Paragon apps: PR7-HW (hardware information), PR7-BK
  (backups) and PR7-TM (terminal), so links between the apps and the PR7-U offer find them.

## 0.2.2

- The family list (`family.py`) knows the four newest Paragon apps: PR7-HX (hex editor), PR7-DB (SQLite browser),
  PR7-UN (uninstaller) and PR7-LN (launcher), so links between the apps and the PR7-U offer find them.

## 0.2.1

- The family's list knows the newest apps (PR7-HB, PR7-FS, PR7-AR, PR7-WM), so links between apps and Check for Updates find them.

## 0.2.0

- **One finish for the whole family.** Choosing OBSIDIAN or AURORA here switches every Paragon app, open ones included (within a couple of seconds), and every app starts in the family's choice. PR7-CB's tray menu has a Finish choice now.
- In AURORA, group titles and selected rows are dark and readable (they were white on the light finish).

## 0.1.1

- Knows the whole family: PR7-DU, PR7-CB, PR7-IS, PR7-PM and PR7-SM are in its list of family apps (their permanent install IDs), so the family links find them when they're installed.

## 0.1.0

- First release: clipboard history, the way Ditto keeps it. It keeps text, pictures and files you copy. Ctrl+` opens
  your clips at the text cursor, with search, paste (or plain text) into the program you were in, Ctrl+1...9, pins
  and forget. Copies that programs mark as private, and copies from password managers, are never kept. Options let
  you set the key, how many clips to keep and how long, and whether it starts with Windows. It updates itself like
  the other family apps.

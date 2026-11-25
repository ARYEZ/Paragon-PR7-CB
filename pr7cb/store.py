"""The clip history (no Qt): an SQLite file in %APPDATA%\\Paragon\\PR7-CB\\clips.db (PR7CB_DATA overrides; tests).

A clip is text (with its HTML when the copy had some), a picture (PNG) or a list of files. Copying the same thing
again moves it back to the top instead of keeping it twice (Ditto's way), matched by a hash of its content. `trim`
keeps the newest `keep` clips and forgets anything older than `days`; pinned clips are always kept."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field

KINDS = ("text", "image", "files")


def data_folder() -> str:
    env = os.environ.get("PR7CB_DATA")
    if env:
        return env
    base = os.environ.get("APPDATA") if sys.platform == "win32" else os.path.join(os.path.expanduser("~"), ".local",
                                                                                    "share")
    return os.path.join(base or os.path.expanduser("~"), "Paragon", "PR7-CB")


@dataclass
class Clip:
    kind: str                        # text | image | files
    text: str = ""                   # the text; for a picture its description; for files the paths, one a line
    html: str = ""
    image: bytes = b""               # PNG
    files: list[str] = field(default_factory=list)
    source: str = ""                 # the program it was copied from ("PR7-W", "firefox")
    created: float = 0.0             # when it was copied (or copied again)
    pinned: bool = False
    width: int = 0
    height: int = 0
    id: int = 0

    def digest(self) -> str:
        h = hashlib.sha1(self.kind.encode())
        if self.kind == "image":
            h.update(self.image)
        elif self.kind == "files":
            h.update("\n".join(self.files).encode("utf-8"))
        else:
            h.update(self.text.encode("utf-8", "surrogatepass"))
        return h.hexdigest()

    def title(self) -> str:
        """One line for the list: the text's first non-empty line(s), a picture's size, the files' names."""
        if self.kind == "image":
            return f"Picture  ·  {self.width} × {self.height}"
        if self.kind == "files":
            names = [re.split(r"[\\/]", p.rstrip("\\/"))[-1] or p for p in self.files]    # Windows paths anywhere
            head = f"{len(names)} files: " if len(names) > 1 else ""
            return head + ", ".join(names)
        return " ⏎ ".join(line.strip() for line in self.text.splitlines() if line.strip()) or self.text


SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL, text TEXT NOT NULL DEFAULT '', html TEXT NOT NULL DEFAULT '',
    image BLOB, files TEXT NOT NULL DEFAULT '[]', source TEXT NOT NULL DEFAULT '',
    created REAL NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0, digest TEXT NOT NULL UNIQUE);
CREATE INDEX IF NOT EXISTS clips_created ON clips(created);
"""


class Store:
    def __init__(self, path: str | None = None):
        if path is None:
            os.makedirs(data_folder(), exist_ok=True)
            path = os.path.join(data_folder(), "clips.db")
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False)
        # SQLite's own LIKE folds only A-Z; Python's casefold makes "über" find "Über" (and "ß" find "SS")
        self.db.create_function("fold", 1, lambda s: (s or "").casefold(), deterministic=True)
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self):
        self.db.close()

    # ---- writing
    def add(self, clip: Clip, now: float | None = None) -> int:
        """Keep a clip (or bring an identical one back to the top); returns its id."""
        when = now if now is not None else time.time()
        d = clip.digest()
        row = self.db.execute("SELECT id FROM clips WHERE digest = ?", (d,)).fetchone()
        if row:
            self.db.execute("UPDATE clips SET created = ?, source = ? WHERE id = ?", (when, clip.source, row[0]))
            self.db.commit()
            return row[0]
        cur = self.db.execute(
            "INSERT INTO clips (kind, text, html, image, files, source, created, pinned, width, height, digest) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (clip.kind, clip.text, clip.html, clip.image or None, json.dumps(clip.files), clip.source, when,
             int(clip.pinned), clip.width, clip.height, d))
        self.db.commit()
        return cur.lastrowid

    def pin(self, clip_id: int, on: bool = True):
        self.db.execute("UPDATE clips SET pinned = ? WHERE id = ?", (int(on), clip_id))
        self.db.commit()

    def touch(self, clip_id: int, now: float | None = None):
        """A pasted clip moves to the top, as Ditto does."""
        self.db.execute("UPDATE clips SET created = ? WHERE id = ?", (now if now is not None else time.time(), clip_id))
        self.db.commit()

    def delete(self, clip_id: int):
        self.db.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
        self.db.commit()

    def clear(self, keep_pinned: bool = True):
        self.db.execute("DELETE FROM clips" + (" WHERE pinned = 0" if keep_pinned else ""))
        self.db.commit()

    def trim(self, keep: int, days: float, now: float | None = None) -> int:
        """Forget clips past the newest `keep` and older than `days` (0 = never by age); pinned ones stay."""
        now = now if now is not None else time.time()
        gone = 0
        if days > 0:
            gone += self.db.execute("DELETE FROM clips WHERE pinned = 0 AND created < ?",
                                    (now - days * 86400,)).rowcount
        ids = [r[0] for r in self.db.execute("SELECT id FROM clips WHERE pinned = 0 ORDER BY created DESC, id DESC")]
        extra = ids[max(0, keep):]
        if extra:
            self.db.executemany("DELETE FROM clips WHERE id = ?", [(i,) for i in extra])
            gone += len(extra)
        self.db.commit()
        if gone:
            self.db.execute("VACUUM")             # give the space of forgotten pictures back
        return gone

    # ---- reading
    def _clip(self, row) -> Clip:
        (cid, kind, text, html, image, files, source, created, pinned, width, height) = row
        return Clip(kind, text, html, image or b"", json.loads(files or "[]"), source, created, bool(pinned),
                    width, height, cid)

    COLUMNS = "id, kind, text, html, image, files, source, created, pinned, width, height"

    def get(self, clip_id: int) -> Clip | None:
        row = self.db.execute(f"SELECT {self.COLUMNS} FROM clips WHERE id = ?", (clip_id,)).fetchone()
        return self._clip(row) if row else None

    def list(self, query: str = "", limit: int = 500) -> list[Clip]:
        """Newest first. A query keeps clips whose text (or file names, or source) holds every word, any case."""
        sql = f"SELECT {self.COLUMNS} FROM clips"
        args: list = []
        words = query.split()
        if words:
            sql += " WHERE " + " AND ".join("(fold(text) LIKE ? ESCAPE '\\' OR fold(source) LIKE ? ESCAPE '\\')"
                                            for _ in words)
            for w in words:
                w = w.casefold()
                pat = "%" + w.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                args += [pat, pat]
        sql += " ORDER BY created DESC, id DESC LIMIT ?"
        args.append(limit)
        return [self._clip(r) for r in self.db.execute(sql, args)]

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM clips").fetchone()[0]

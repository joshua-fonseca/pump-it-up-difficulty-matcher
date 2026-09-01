"""
build_db.py

Reads Pump It Up song data (base dataset + optional supplemental songs added
after the base dataset's last update) and builds a SQLite database containing
only Singles ("S") charts, since that's the only chart type relevant to two
players finding songs they can play together.

Data source: base dataset is songlist_phoenix.json, sourced from
https://github.com/pugkung/piutool (MIT licensed; reused per the repo's
explicit usage agreement: "Feel free to use this tool or data provided for
any purpose."). That dataset is snapshotted at Pump It Up Phoenix v1.05 and
is not actively maintained for newer song releases, so newer songs are
tracked separately in supplemental_songs.json and merged in here.

Usage:
    python build_db.py
Produces:
    piu_songs.db
"""

import json
import sqlite3
from pathlib import Path

BASE_DATA_FILE = Path("songlist_phoenix.json")
SUPPLEMENTAL_DATA_FILE = Path("supplemental_songs.json")
OVERRIDES_FILE = Path("chart_overrides.json")
DB_FILE = Path("piu_songs.db")


def load_overrides(path: Path) -> dict[int, list[int]]:
    """Load chart overrides: a mapping of songID -> the CURRENT complete
    list of Singles difficulty levels for that song, replacing whatever the
    base dataset says. Used when a song's charts change after the base
    dataset was snapshotted (a difficulty gets rebalanced, e.g. S16 -> S18,
    or a new Singles chart is added to an existing song).

    Full-list replacement (rather than trying to patch individual chart
    entries) avoids ambiguity: there's no need to figure out whether a
    changed number means "this chart was rebalanced" vs. "this chart was
    removed and a different one added" — you just state the current truth.
    """
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {entry["songID"]: entry["singles"] for entry in data}


def load_songs(path: Path) -> list[dict]:
    """Load a song list JSON file. Returns [] if the file doesn't exist
    (used for the optional supplemental file)."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # base file wraps songs in {"songlist": [...]}; supplemental file is
    # just a plain list for simplicity when hand-editing it.
    if isinstance(data, dict) and "songlist" in data:
        return data["songlist"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unrecognized JSON shape in {path}")


def build_database():
    songs = load_songs(BASE_DATA_FILE)
    supplemental = load_songs(SUPPLEMENTAL_DATA_FILE)
    overrides = load_overrides(OVERRIDES_FILE)

    if supplemental:
        print(f"Merging {len(supplemental)} supplemental song(s) not present in the base dataset.")
        songs.extend(supplemental)

    if overrides:
        print(f"Applying chart overrides for {len(overrides)} song(s).")

    if DB_FILE.exists():
        DB_FILE.unlink()  # rebuild fresh each run

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE songs (
            song_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            artist TEXT,
            bpm TEXT,
            version TEXT,
            song_type TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE charts (
            chart_id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            difficulty INTEGER NOT NULL,
            FOREIGN KEY (song_id) REFERENCES songs(song_id)
        )
    """)

    song_rows = []
    chart_rows = []
    skipped_no_singles = 0

    for song in songs:
        song_id = song.get("songID")
        title = song.get("songName")
        artist = song.get("artist")
        bpm_raw = song.get("bpm")
        # Some songs have a single BPM (int), others have a tempo range
        # (list, e.g. [140, 202]) for songs with tempo changes. Normalize
        # both to a display-friendly string so the column type is consistent.
        if isinstance(bpm_raw, list):
            bpm = "-".join(str(b) for b in bpm_raw)
        elif bpm_raw is not None:
            bpm = str(bpm_raw)
        else:
            bpm = None

        if song_id is None or title is None:
            print(f"Skipping malformed song entry: {song}")
            continue

        singles = [
            chart for chart in song.get("chartList", [])
            if chart.get("chartType") == "single"
        ]

        # If this song has an override, its Singles list fully replaces
        # whatever the base/supplemental data said (see load_overrides).
        if song_id in overrides:
            singles = [{"level": lvl} for lvl in overrides[song_id]]

        if not singles:
            skipped_no_singles += 1
            continue

        song_rows.append((song_id, title, artist, bpm, song.get("version"), song.get("songType")))
        for chart in singles:
            level = chart.get("level")
            if level is not None:
                chart_rows.append((song_id, level))

    cur.executemany(
        "INSERT OR IGNORE INTO songs (song_id, title, artist, bpm, version, song_type) VALUES (?, ?, ?, ?, ?, ?)",
        song_rows,
    )
    cur.executemany(
        "INSERT INTO charts (song_id, difficulty) VALUES (?, ?)",
        chart_rows,
    )

    conn.commit()

    print(f"Loaded {len(song_rows)} songs with Singles charts.")
    print(f"Loaded {len(chart_rows)} Singles chart entries.")
    print(f"Skipped {skipped_no_singles} song(s) with no Singles chart (Doubles/Coop-only).")
    print(f"Database written to {DB_FILE.resolve()}")

    conn.close()


if __name__ == "__main__":
    build_database()

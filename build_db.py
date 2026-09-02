# Usage:
#     python build_db.py
# Produces:
#     piu_songs.db

import json
import sqlite3
from pathlib import Path
import csv

BASE_DATA_FILE = Path("songlist_phoenix.json")
SUPPLEMENTAL_DATA_FILE = Path("supplemental_songs.json")
OVERRIDES_FILE = Path("chart_overrides.json")
DB_FILE = Path("piu_songs.db")
REMOVED_FILE = Path("removed_songs.json")
SONGS_CSV_FILE = Path("piu_songs.csv")
TITLE_CORRECTIONS_FILE = Path("title_corrections.json")

def export_songs_csv(conn: sqlite3.Connection, path: Path):
    cur = conn.cursor()
    cur.execute("SELECT song_id, title, artist, version, song_type FROM songs ORDER BY title, song_id")
    rows = cur.fetchall()

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["song_id", "title", "artist", "version", "song_type"])
        writer.writerows(rows)

    print(f"Exported {len(rows)} songs to {path.resolve()}")

def load_title_corrections(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {entry["songID"]: entry["title"] for entry in data}

def load_overrides(path: Path) -> dict[int, list[int]]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # for every entry in data, create a dictionary entry
    # where the key is the song ID and the value is the singles
    return {entry["songID"]: entry["singles"] for entry in data}

def load_removed(path: Path) -> set[int]:
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # go through every entry in data and collect its songIDs into a set
    return {entry["songID"] for entry in data}


def load_songs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # base file wraps songs in {"songlist": [...]};
    if isinstance(data, dict) and "songlist" in data: # does the dict have a key called songlist
        return data["songlist"]

    # supplemental file is just a plain list for simplicity:
    # [{"songID": 789, "singles": [...]}]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unrecognized JSON shape in {path}")


def build_database():
    songs = load_songs(BASE_DATA_FILE)
    supplemental = load_songs(SUPPLEMENTAL_DATA_FILE)
    overrides = load_overrides(OVERRIDES_FILE)
    removed = load_removed(REMOVED_FILE)
    corrected = load_title_corrections(TITLE_CORRECTIONS_FILE)

    if corrected:
         print(f"Corrected {len(corrected)} song title(s) in the base dataset.")

    if removed:
        print(f"Removing {len(removed)} song(s) present in the base dataset.")
        songs = [s for s in songs if s["songID"] not in removed]


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

        if song_id in corrected:
            title = corrected[song_id]

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

    export_songs_csv(conn, SONGS_CSV_FILE)

    conn.close()


if __name__ == "__main__":
    build_database()

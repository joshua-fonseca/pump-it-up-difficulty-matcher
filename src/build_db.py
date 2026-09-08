"""
build_db.py

Builds the Pump It Up song database from the base song dataset and
supplemental song data. The resulting database contains only Singles ("S")
charts, since that is the only chart type relevant to two players finding
songs they can play together.

Usage:
    python src/build_db.py
Produces:
    piu_songs.db
    piu_songs.csv
"""

import json
import sqlite3
from pathlib import Path
import csv
from csv_to_supplemental import build_supplemental_songs

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
JSON_DIR = DATA_DIR / "json"
CSV_DIR = DATA_DIR / "csv"

# Make sure these two directories exist
# Create them if not already exists, otherwise continue as normal
for d in (JSON_DIR, CSV_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Source of truth lives in data/
NEW_SONGS_CSV_FILE = CSV_DIR / "new_songs.csv"
BASE_DATA_FILE = JSON_DIR / "songlist_phoenix.json"
REMOVED_FILE = JSON_DIR / "removed_songs.json"
TITLE_CORRECTIONS_FILE = JSON_DIR / "title_corrections.json"
ADDED_DIFFICULTIES_FILE = JSON_DIR / "added_difficulties.json"
VERSION_ORDER_FILE = JSON_DIR / "version_order.json"

# Generated files live at project root
SUPPLEMENTAL_DATA_FILE = BASE_DIR / "supplemental_songs.json"
SONGS_CSV_FILE = BASE_DIR / "piu_songs.csv"
DB_FILE = BASE_DIR / "piu_songs.db"

def export_songs_csv(conn: sqlite3.Connection, path: Path):
    cur = conn.cursor()
    cur.execute("SELECT * FROM songs")
    rows = cur.fetchall()

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["song_id", "title", "artist", "bpm", "version", "song_type"])
        writer.writerows(rows)

    print(f"Exported {len(rows)} songs to {path.resolve()}")

def load_title_corrections(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        # Expected format: [ { "songID": 123, "title": "Correct Title", "Note": "Corrected title" }, ... ]
        # File is converted to a list of python dictionaries
        data = json.load(f)
    return {entry["songID"]: entry["title"] for entry in data}

# Use a set for fast membership checking; a list would look at one item at a time
def load_removed(path: Path) -> set[int]:
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        # Expected format: [ { "songID": 123 "Note": "Deleted" }, ... ]
        data = json.load(f)

    # Go through every entry in data and collect its songIDs into a set
    return {entry["songID"] for entry in data}

def load_added_difficulties(path: Path) -> dict[int, list[int]]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        # Expected format: [ { "songID": 123, "add": [22], "note": "New S22 chart added" }, ... ]
        data = json.load(f)
    return {entry["songID"]: entry["add"] for entry in data}

# List preserves order which is important for this case, and tuples keep multiple items in a var
# Dictionary or a list of lists could be viable here too
def load_version_order(path: Path) -> list[tuple[str, int]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        # Expected format: [ { "version": "1st", "rank": 0 }, ... ]
        data = json.load(f)
    return [(entry["version"], entry["rank"]) for entry in data]

def load_songs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        # Expected format: { "songlist": [ { "songID": 123, ... , "chartlist":[ ... ] ] }
        data = json.load(f)

    # Base file wraps songs in {"songlist": [...]};
    if isinstance(data, dict) and "songlist" in data: # Does the dict have a key called songlist
        return data["songlist"]
    raise ValueError(f"Unrecognized JSON shape in {path}")

def build_database():
    # Load everything into memory
    songs = load_songs(BASE_DATA_FILE)
    removed = load_removed(REMOVED_FILE)
    corrected = load_title_corrections(TITLE_CORRECTIONS_FILE)
    added_difficulties = load_added_difficulties(ADDED_DIFFICULTIES_FILE)
    supplemental = build_supplemental_songs(NEW_SONGS_CSV_FILE)

    with open(SUPPLEMENTAL_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(supplemental, f, indent=2, ensure_ascii=False)

    print(f"> Base data modifications:")

    # Actual correction is done later in the main per-song loop
    if corrected:
         print(f"Correcting {len(corrected)} song title(s) in the base dataset.")

    if removed:
        print(f"Removing {len(removed)} song(s) present in the base dataset.")
        songs = [s for s in songs if s["songID"] not in removed]

    if supplemental:
        print(f"Adding {len(supplemental)} song(s) to song list.")
        songs.extend(supplemental)

    if DB_FILE.exists():
        DB_FILE.unlink()  # Using pathlib.unlink() method, instead of older os.remove() method

    # Establish connection + cursor object to execute SQL
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

    cur.execute("""
        CREATE TABLE versions (
            version_name TEXT PRIMARY KEY,
            release_rank INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE song_notes (
            song_id INTEGER PRIMARY KEY,
            note TEXT NOT NULL,
            FOREIGN KEY (song_id) REFERENCES songs(song_id)
        )
    """)

    version_rows = load_version_order(VERSION_ORDER_FILE)
    cur.executemany(
        "INSERT OR IGNORE INTO versions (version_name, release_rank) VALUES (?, ?)",
        version_rows,
    )
    print(f"Loaded {len(version_rows)} version(s) into the versions table.")

    song_rows = []
    chart_rows = []
    note_rows = []
    skipped_no_singles = 0
    songs_with_new_difficulties = set()

    # Main per song loop
    for song in songs:
        # A song is a dictionary so can access .get()
        song_id = song.get("songID")
        title = song.get("songName")

        if song_id in corrected: # Actual corrections happen here
            title = corrected[song_id]

        artist = song.get("artist")
        bpm_raw = song.get("bpm")

        # Some songs have a single BPM (int), others have a tempo range
        # (The songlist can have BPM as a list, e.g. [140, 202]). Normalize
        # both to a display-friendly string so the column type is consistent.
        if isinstance(bpm_raw, list):
            bpm = "-".join(str(b) for b in bpm_raw)
        elif bpm_raw is not None:
            bpm = str(bpm_raw)
        else:
            bpm = None

        # Safeguard, though unlikely to run with
        # songlist_phoenix.json or supplemental_songs.json
        if song_id is None or title is None:
            print(f"Skipping malformed song entry: {song}")
            continue

        singles = []
        # A chart looks like: { "chartType": "single", "level": 8, "tags": [] }
        for chart in song.get("chartList", []): # If no chartlist available, default to empty list
            if chart.get("chartType") == "single":
                singles.append(chart)

        if song_id in added_difficulties:
            # {"chartType": "single", "level": 15, "tags": []}
            # for every chart in singles, pull out its "level", and collect into a set
            # existing_levels = {chart.get("level") for chart in singles}
            existing_levels = set()
            for chart in singles:
                existing_levels.add(chart.get("level"))

            # Added difficulties is: {songID: [levels]}
            for new_level in added_difficulties[song_id]:
                if new_level in existing_levels:
                    print(f"Song {song_id}: difficulty S{new_level} already exists, ignoring addition.")
                    continue
                singles.append({"level": new_level}) # actually add the level, looks like: { "level": 22 }
                songs_with_new_difficulties.add(song_id)

        if not singles:
            skipped_no_singles += 1
            continue

        # Build the songs table row
        song_rows.append((song_id, title, artist, bpm, song.get("version"), song.get("songType")))

        # Add to frontend note (Typically for RISE indication, this is used)
        note = song.get("displayedNote")
        if note:
            note_rows.append((song_id, note))

        for chart in singles:
            level = chart.get("level") # Not using chart["level"], as .get returns None if missing the key
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
    cur.executemany(
        "INSERT OR IGNORE INTO song_notes (song_id, note) VALUES (?, ?)",
        note_rows,
    )

    if songs_with_new_difficulties:
        print(f"Added new difficulties to {len(songs_with_new_difficulties)} song(s).")

    if note_rows:
        print(f"Added notes for {len(note_rows)} song(s).")

    conn.commit()

    print(f"\n> SUMMARY")
    print(f"Loaded {len(song_rows)} songs with Singles charts.")
    print(f"Loaded {len(chart_rows)} Singles chart entries.")
    print(f"Skipped {skipped_no_singles} song(s) with no Singles chart (Doubles/Coop-only).")
    print(f"Database written to {DB_FILE.resolve()}")

    export_songs_csv(conn, SONGS_CSV_FILE)

    conn.close()

if __name__ == "__main__":
    build_database()
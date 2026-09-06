"""
build_final_db.py

Creates a new database (piu_songs_final.db) by copying the base song
database (piu_songs.db) and applying rerates from the raw staging database
(piu_rerates.db) on top of the copy.

The base database and the raw rerates database are both left completely
untouched by this script — this preserves piu_songs.db as a historical
snapshot of the un-rerated data, rather than mutating it in place, so you
can always go back and compare "before" vs "after" by keeping both files.

Matching logic (same as apply_rerates.py): joins raw rerate rows to songs
on (title, song_type), and to charts on (song_id, old difficulty) —
requiring all three together avoids mismatches from duplicate titles in
the database (e.g. "Super Fantasy" exists as both "arcade" and
"shortcut").

Run build_db.py and build_rerates_db.py first to produce their respective
databases before running this script.

Usage:
    python src/build_final_db.py
Produces:
    piu_songs_final.db
"""

import shutil
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

BASE_DB_FILE = BASE_DIR / "piu_songs.db"
RERATES_DB_FILE = BASE_DIR / "piu_rerates.db"
FINAL_DB_FILE = BASE_DIR / "piu_songs_final.db"

def build_final_db():
    if not BASE_DB_FILE.exists():
        raise FileNotFoundError(f"{BASE_DB_FILE} does not exist. Run build_db.py first.")
    if not RERATES_DB_FILE.exists():
        raise FileNotFoundError(f"{RERATES_DB_FILE} does not exist. Run build_rerates_db.py first.")

    # Copy the base database rather than modifying it in place, so
    # piu_songs.db always remains the untouched, pre-rerate snapshot.
    if FINAL_DB_FILE.exists():
        FINAL_DB_FILE.unlink()
    shutil.copy(BASE_DB_FILE, FINAL_DB_FILE)

    conn = sqlite3.connect(FINAL_DB_FILE)
    conn.execute(f"ATTACH DATABASE '{RERATES_DB_FILE}' AS rerates")
    cur = conn.cursor()

    cur.execute("""
        SELECT c.chart_id, r.final_name, r.song_type_raw,
               r.old_rating_processed, r.new_rating_processed
        FROM rerates.raw_rerates r
        JOIN main.songs s
            ON LOWER(TRIM(s.title)) = LOWER(TRIM(r.final_name))
           AND LOWER(TRIM(s.song_type)) = LOWER(TRIM(r.song_type_raw))
        JOIN main.charts c
            ON c.song_id = s.song_id
           AND c.difficulty = CAST(r.old_rating_processed AS INTEGER)
    """)
    matches = cur.fetchall()

    matched_rerate_keys = {
        (m[1].strip().lower(), m[2].strip().lower(), m[3].strip()) for m in matches
    }

    for chart_id, final_name, song_type_raw, old_rating, new_rating in matches:
        cur.execute(
            "UPDATE main.charts SET difficulty = ? WHERE chart_id = ?",
            (int(new_rating), chart_id),
        )

    conn.commit()

    cur.execute("SELECT final_name, song_type_raw, old_rating_processed, new_rating_processed FROM rerates.raw_rerates")
    all_rerates = cur.fetchall()

    skipped = [
        row for row in all_rerates
        if (row[0].strip().lower(), row[1].strip().lower(), row[2].strip()) not in matched_rerate_keys
    ]

    print(f"Copied {BASE_DB_FILE} -> {FINAL_DB_FILE} ({FINAL_DB_FILE.resolve()}).")
    print(f"Applied {len(matches)} rerate(s) to the copy. {BASE_DB_FILE} was not modified.")
    if skipped:
        print(f"\n{len(skipped)} rerate row(s) could not be matched — needs manual review:")
        for final_name, song_type_raw, old_rating, new_rating in skipped:
            print(f"  - {final_name} ({song_type_raw}): S{old_rating} -> S{new_rating}")

    conn.close()


if __name__ == "__main__":
    build_final_db()

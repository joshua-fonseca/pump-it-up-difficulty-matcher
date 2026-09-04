"""
build_rerates_db.py

Materializes a rerate CSV into its own SQLite database (piu_rerates.db) as
a raw staging table — columns and values kept exactly as they appear in
the source file, with no cleaning, renaming, or type normalization.

This deliberately mirrors a real-world data pipeline pattern: raw source
data is captured faithfully in a staging layer, separate from the
"clean" production data (piu_songs.db). Transformation/matching logic
lives in a separate step (apply_rerates.py), not here.

Usage:
    python build_rerates_db.py <rerates.csv>
Produces:
    piu_rerates.db
"""

import csv
import sqlite3
import sys
from pathlib import Path

RERATES_DB_FILE = Path("piu_rerates.db")


def build_rerates_db(csv_path: Path):
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    if RERATES_DB_FILE.exists():
        RERATES_DB_FILE.unlink()

    conn = sqlite3.connect(RERATES_DB_FILE)
    cur = conn.cursor()

    # Columns are named after the raw CSV headers as closely as SQLite
    # column-naming allows (spaces/punctuation replaced), since the point
    # of this table is to preserve the source as-is, not to relabel it
    # into the naming conventions used elsewhere in this project.
    column_names = [
        "final_name",
        "old_rating_processed",
        "new_rating_processed",
        "song_type_raw",
    ]

    cur.execute(f"""
        CREATE TABLE raw_rerates (
            rerate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            {", ".join(f"{col} TEXT" for col in column_names)}
        )
    """)

    cur.executemany(
        f"INSERT INTO raw_rerates ({', '.join(column_names)}) VALUES ({', '.join('?' * len(column_names))})",
        rows,
    )

    conn.commit()
    print(f"Loaded {len(rows)} raw rerate row(s) into {RERATES_DB_FILE.resolve()}")
    print(f"Source CSV header (preserved for reference): {header}")
    conn.close()


def main():
    if len(sys.argv) != 2:
        print("Usage: python build_rerates_db.py <rerates.csv>")
        sys.exit(1)
    build_rerates_db(Path(sys.argv[1]))


if __name__ == "__main__":
    main()

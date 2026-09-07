"""
Converts a CSV of new songs into supplemental_songs.json.

Each row represents one song, with all Singles difficulty charts stored
in the `difficulty` field as a semicolon-separated list. The resulting
supplemental_songs.json uses the same song-object shape as
songlist_phoenix.json, so these songs pass through build_db.py's
per-song loop identically to base-dataset songs.

CSV format (one row per song):

    songID,songName,artist,bpm,songType,version,difficulty,note

Example:

    9001,Example New Song,Example Artist,150,arcade,random,11;17;21,Added after Phoenix 2 rerate

The semicolon (`;`) is used to separate difficulty levels because commas
are already used as the CSV column delimiter.

Usage:
    python src/csv_to_supplemental.py data/csv/new_songs.csv supplemental_songs.json
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def build_supplemental_songs(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []

    songs = []
    skipped = []

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            song_id_raw = row.get("songID", "").strip()

            if not song_id_raw:
                continue

            try:
                song_id = int(song_id_raw)
            except ValueError:
                print(f"Skipping row with non-numeric songID: {row}")
                continue

            # Parse difficulties from semicolon-separated list
            difficulty_raw = row.get("difficulty", "").strip()
            difficulties = []

            for level_raw in difficulty_raw.split(";"):
                level_raw = level_raw.strip()

                if not level_raw:
                    continue

                try:
                    difficulties.append(int(level_raw))
                except ValueError:
                    skipped.append(
                        (song_id, f"invalid difficulty value: {level_raw!r}")
                    )
                    break
            else:
                song_entry = {
                    "songID": song_id,
                    "songName": row.get("songName", "").strip(),
                    "artist": row.get("artist", "").strip(),
                    "bpm": (
                        int(row["bpm"].strip())
                        if row.get("bpm", "").strip().isdigit()
                        else row.get("bpm", "").strip()
                    ),
                    "chartList": [
                        {
                            "chartType": "single",
                            "level": level,
                            "tags": []
                        }
                        for level in sorted(difficulties)
                    ],
                    "songType": row.get("songType", "").strip(),
                    "version": row.get("version", "").strip(),
                }

                note = row.get("note", "").strip()

                if note:
                    song_entry["note"] = note

                displayed_note = row.get("displayedNote", "").strip()

                if displayed_note:
                    song_entry["displayedNote"] = displayed_note

                songs.append(song_entry)

    if skipped:
        print(f"\n{len(skipped)} song(s) skipped — needs manual review:")

        for song_id, reason in skipped:
            print(f"  - songID {song_id}: {reason}")

    songs.sort(key=lambda s: s["songID"])

    return songs


def main():
    if len(sys.argv) != 3:
        print("Usage: python csv_to_supplemental.py <new_songs.csv> <supplemental_songs.json>")
        sys.exit(1)

    csv_path, output_path = Path(sys.argv[1]), Path(sys.argv[2])

    songs = build_supplemental_songs(csv_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(songs, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(songs)} song(s) to {output_path}")


if __name__ == "__main__":
    main()
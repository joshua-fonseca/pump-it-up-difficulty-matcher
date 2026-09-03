"""
csv_to_supplemental.py

Converts a CSV of new songs (one row per Singles difficulty chart) into
supplemental_songs.json, in the same song-object shape used elsewhere in
this project (matching songlist_phoenix.json's structure), so these songs
pass through build_db.py's per-song loop identically to base-dataset songs.

CSV format (one row per chart, song metadata repeated per row):
    songID,songName,artist,bpm,songType,version,difficulty,note

    9001,Example New Song,Example Artist,150,arcade,random,11,Added after Phoenix 2 rerate
    9001,Example New Song,Example Artist,150,arcade,random,17,
    9001,Example New Song,Example Artist,150,arcade,random,21,

Notes:
  - One row per difficulty — a song with 3 Singles charts needs 3 rows,
    all sharing the same songID.
  - Song-level fields (songName, artist, bpm, songType, version) should be
    identical across all rows for the same songID. If they don't match,
    this script warns and skips that song rather than guessing which
    value is correct.
  - note only needs to be filled on one row per song; blank on the rest
    is fine. It's carried through into the output JSON as documentation
    for whoever is maintaining the supplemental file — it's never read by
    build_db.py itself.
  - BPM ranges (e.g. songs with tempo changes) aren't supported by this
    CSV format — enter a single number. Add tempo-range BPM songs to
    supplemental_songs.json by hand if needed.

Usage:
    python csv_to_supplemental.py new_songs.csv supplemental_songs.json
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def build_supplemental_songs(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []

    rows_by_song: dict[int, list[dict]] = defaultdict(list)

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
            rows_by_song[song_id].append(row)

    songs = []
    skipped = []

    for song_id, rows in rows_by_song.items():
        # Metadata fields should match across every row for this song.
        meta_fields = ["songName", "artist", "bpm", "songType", "version"]
        first = rows[0]
        mismatched = [
            field for field in meta_fields
            if any(row.get(field, "").strip() != first.get(field, "").strip() for row in rows)
        ]
        if mismatched:
            skipped.append((song_id, f"inconsistent {', '.join(mismatched)} across rows"))
            continue

        difficulties = []
        for row in rows:
            level_raw = row.get("difficulty", "").strip()
            try:
                difficulties.append(int(level_raw))
            except ValueError:
                skipped.append((song_id, f"invalid difficulty value: {level_raw!r}"))
                break
        else:
            note = next((row.get("note", "").strip() for row in rows if row.get("note", "").strip()), "")

            song_entry = {
                "songID": song_id,
                "songName": first["songName"].strip(),
                "artist": first["artist"].strip(),
                "bpm": int(first["bpm"]) if first["bpm"].strip().isdigit() else first["bpm"].strip(),
                "chartList": [
                    {"chartType": "single", "level": level, "tags": []}
                    for level in sorted(difficulties)
                ],
                "songType": first["songType"].strip(),
                "version": first["version"].strip(),
            }
            if note:
                song_entry["note"] = note

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

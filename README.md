# PIU Song Matcher — Data Layer

Two players at different skill levels often can't tell which songs both of
them can comfortably play. This tool lets each player enter their difficulty
range and returns the songs that fall within *both* ranges (Singles charts
only, since that's the chart type used when playing together).

This README covers the data layer: where the song data comes from, how it's
structured, and how to keep it up to date.

## Data source

Base dataset: [`pugkung/piutool`](https://github.com/pugkung/piutool)
(MIT licensed). Per the repo's own usage agreement: *"Feel free to use this
tool or data provided for any purpose."*

That dataset is snapshotted at **Pump It Up Phoenix v1.05** and is not
actively maintained for songs released after that version. Songs released
since then are tracked separately (see below) and merged in at build time.

## Files

| File | Purpose |
|---|---|
| `songlist_phoenix.json` | Base dataset (all songs as of Phoenix v1.05) |
| `supplemental_songs.json` | Songs released after v1.05, added manually (optional — omit if empty) |
| `chart_overrides.json` | Corrections for existing songs whose charts changed after v1.05 — rebalanced difficulties or new charts added (optional — omit if empty) |
| `build_db.py` | Reads all three files, filters to Singles charts, builds `piu_songs.db` |
| `piu_songs.db` | Output SQLite database (generated, not committed) |

## Schema

```sql
CREATE TABLE songs (
    song_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT,
    bpm TEXT       -- stored as text since some songs have a tempo range (e.g. "140-202")
);

CREATE TABLE charts (
    chart_id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL,
    difficulty INTEGER NOT NULL,
    FOREIGN KEY (song_id) REFERENCES songs(song_id)
);
```

A song can have multiple Singles charts at different difficulty levels
(e.g. a Normal S13 and a Hard S18 of the same song), so `songs` and `charts`
are separate tables in a one-to-many relationship. Doubles and Co-op charts
are intentionally excluded — this tool only concerns two players on
Singles.

## The matching query

Given two players' difficulty ranges, return songs playable by both:

```sql
SELECT s.title, c.difficulty
FROM songs s
JOIN charts c ON s.song_id = c.song_id
WHERE c.difficulty BETWEEN :player1_min AND :player1_max
  AND c.difficulty BETWEEN :player2_min AND :player2_max
ORDER BY c.difficulty;
```

## Building the database

```bash
python build_db.py
```

This regenerates `piu_songs.db` from scratch each run (safe to re-run any
time the source JSON files change).

## Adding songs released after Phoenix v1.05

Since the base dataset isn't actively maintained, new songs need to be added
by hand. Create/edit `supplemental_songs.json` (see
`supplemental_songs.example.json` for the format) and re-run `build_db.py`.

A few notes:
- Use a `songID` in the 9000+ range to avoid colliding with IDs in the base
  dataset (which currently tops out in the 800s).
- Only `single` chart entries are read — `double`/`coop` entries can be
  included for completeness but are ignored by the build script.
- BPM can be a single number or a two-value list (e.g. `[140, 202]`) for
  songs with tempo changes.

## Handling difficulty changes to existing songs

Charts for songs *already in the base dataset* sometimes change after v1.05
— a difficulty gets rebalanced (e.g. S16 becomes S18), or a new Singles
chart is added to a song that previously didn't have one at that level.

Rather than trying to patch individual chart entries (which gets ambiguous —
did S16 become S18, or was S16 removed and an unrelated S18 added?),
`chart_overrides.json` uses full-list replacement: you provide the complete,
current list of Singles difficulties for that song, and it replaces
whatever the base dataset says entirely.

```json
[
  {
    "songID": 4,
    "singles": [4, 6, 8, 18],
    "note": "S16 rebalanced to S18"
  }
]
```

See `chart_overrides.example.json` for the template. The `note` field is
optional but recommended — it's not read by the build script, but it's
useful documentation for why the override exists (which patch/version
introduced the change, etc.).

## Known limitations

- Song data reflects Pump It Up Phoenix v1.05 plus whatever has been
  manually added to `supplemental_songs.json`; it is not automatically kept
  in sync with the live game.
- Doubles and Co-op charts are excluded by design, not by omission.

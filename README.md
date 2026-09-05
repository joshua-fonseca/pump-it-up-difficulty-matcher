# PIU Song Matcher
> Find songs two players of different skill levels can play together

Pump It Up is a rhythm game where songs come in multiple difficulty charts.
When two players of different skill levels want to play together, there's no
easy way to see which songs fall within *both* of their comfortable ranges.
This project builds a queryable song database, each player enters their
difficulty range, and the tool returns songs both of them can play (Singles
charts only, since that's the chart type used when playing together).

This repository currently covers the **data layer**: sourcing, cleaning, and
structuring the song data into a SQLite database ready to be queried by a
frontend (not yet built).

## Installing / Getting started

You'll need Python 3.10+ (for modern type-hint syntax) and no external
packages, everything here uses the standard library (`sqlite3`, `json`,
`csv`, `pathlib`).

```shell
git clone https://github.com/<your-username>/pump-it-up-difficulty-matcher.git
cd pump-it-up-difficulty-matcher
python src/build_db.py
```

This reads the base song dataset plus any corrections/additions you've
configured (see **Configuration** below) and produces `piu_songs.db` at the
project root, a SQLite database of every song and its Singles difficulty
charts.

### Initial Configuration

No API keys or secrets are needed. The one thing worth doing before your
first run is deciding whether you have a chart-rerate CSV to apply (see
**Developing → Applying rerates** below), if not, `build_db.py` alone
produces a fully usable database.

## Developing

```shell
git clone https://github.com/<your-username>/pump-it-up-difficulty-matcher.git
cd pump-it-up-difficulty-matcher
```

Project layout:

```
src/                          Python scripts
data/
  json/                       Source-of-truth JSON (hand-maintained)
  csv/                        Source-of-truth CSVs (hand-maintained)
piu_songs.db                  Generated database (gitignored)
piu_rerates.db                Generated database (gitignored)
piu_songs_final.db            Generated database (gitignored)
supplemental_songs.json       Generated from data/csv/new_songs.csv (gitignored)
piu_songs.csv                 Generated export of the songs table (gitignored)
```

Everything under `data/` is a hand-maintained input; everything else listed
above is rebuilt from scratch on every run and safe to delete at any time.

### Building

The base database:

```shell
python src/build_db.py
```

This applies, in order: title corrections, song removals, supplemental
(newly-released) songs, and additive difficulties, then writes
`piu_songs.db`.

### Applying rerates

Chart difficulties occasionally get rebalanced during a major game update
(e.g. Phoenix 1 to Phoenix 2, where a song's S16 chart might become S18).
Rerates typically affect far more charts at once than a handful of title
corrections or removed songs, so unlike those (which are small enough to
hand-edit directly as JSON), rerates are processed from a CSV instead,
since automating the CSV to database matching is far less error-prone than
manually retyping dozens or hundreds of chart changes by hand.

This is handled as a separate two-step pipeline, deliberately kept apart
from `build_db.py` so the un-rerated baseline stays available for
comparison:

```shell
python src/build_rerates_db.py data/csv/piu_rerates.csv   # stages the raw CSV into piu_rerates.db, unmodified
python src/build_final_db.py                              # copies piu_songs.db -> piu_songs_final.db, applies rerates to the copy
```

`piu_songs.db` is never modified by this step, `piu_songs_final.db` is the
combined, "current" output, while `piu_songs.db` remains a historical
snapshot of the pre-rerate data.

### Cleaning generated files

```shell
bash clean.sh
```

Deletes every generated database and derived file so the pipeline can be
rerun from scratch.

## Features

* Builds a queryable SQLite database of Pump It Up songs and their Singles
  difficulty charts
* Title correction, song removal, new-song addition, and additive-difficulty
  mechanisms for keeping the base dataset current without touching the
  original source data
* A separate rerate pipeline that preserves the pre-rerate database as a
  historical snapshot rather than overwriting it
* All new-song data is added by hand (see **Configuration**) rather than
  scraped, since the community sites that host up-to-date PIU chart data
  disallow automated access in both `robots.txt` and their Terms of Service

## Configuration

All configuration is done via the data files below. Every optional file is
safe to omit entirely, `build_db.py` treats a missing file as "no changes
of this kind."

#### `data/json/songlist_phoenix.json`
Type: JSON (required)

The base dataset, sourced from
[`pugkung/piutool`](https://github.com/pugkung/piutool). Snapshotted at
Pump It Up Phoenix v1.05; not actively maintained for songs released after
that version.

#### `data/csv/new_songs.csv`
Type: CSV (optional)

Songs released after the base dataset's snapshot, entered manually by
watching official gameplay/reveal videos on the
[official Pump It Up YouTube channel](https://www.youtube.com/@PUMPITUPOfficial)
(one row per Singles difficulty chart). This is done manually rather than
scraped, see **Features** below for why. Regenerates
`supplemental_songs.json` on every `build_db.py` run.

Example:
```csv
songID,songName,artist,bpm,songType,version,difficulty,note
9001,Example New Song,Example Artist,150,arcade,random,11,
9001,Example New Song,Example Artist,150,arcade,random,17,
```

#### `data/json/removed_songs.json`
Type: JSON (optional)

Songs present in the base dataset that have since been removed from the
game.

```json
[{ "songID": 123, "note": "Removed in [version/patch]" }]
```

#### `data/json/title_corrections.json`
Type: JSON (optional)

Fixes typos in the base dataset's song titles (matched by `songID`, since
the existing title is exactly what may be wrong).

```json
[{ "songID": 113, "title": "Monkey Fingers", "note": "Base dataset typo" }]
```

#### `data/json/added_difficulties.json`
Type: JSON (optional)

Adds new Singles charts to a song already in the base dataset, without
needing to restate its existing chart list. Each `songID` should appear
**once**, with every new difficulty in a single `add` list.

```json
[{ "songID": 271, "add": [22], "note": "New S22 chart added" }]
```

#### `data/csv/piu_rerates.csv`
Type: CSV (optional)

Chart rerates from a game update, in long format (one row per chart
change). Consumed by `build_rerates_db.py` / `build_final_db.py`, not
`build_db.py` directly.

Sourced from the community-compiled
[Pump It Up Phoenix 2 chart rerates and removals](https://www.reddit.com/r/PumpItUp/comments/1tji3wg/pump_it_up_phoenix_2_chart_rerates_and_removals/)
Reddit post and its accompanying
[Google Sheet](https://docs.google.com/spreadsheets/d/1MhrFJf9Mnp5i5-cqWgeRvqcJZmzlDPwheLdQL4S1vaQ/edit?gid=1983447790#gid=1983447790),
then reprocessed by hand into the long-format CSV this pipeline expects,
see the
[processed sheet](https://docs.google.com/spreadsheets/d/1DUMNMJJqfnBMCe_tdNmKEJyV_JGmkqqVBelZW0WIfSo/edit?usp=sharing)
for the cleaned version.

## Contributing

This is currently a personal portfolio project, but suggestions are
welcome, feel free to open an issue if you spot a data error or a bug in
the build pipeline.

## Links

- Repository: `https://github.com/<your-username>/pump-it-up-difficulty-matcher`
- Base dataset source: [pugkung/piutool](https://github.com/pugkung/piutool)
- Chart rerate data: [r/PumpItUp rerates & removals post](https://www.reddit.com/r/PumpItUp/comments/1tji3wg/pump_it_up_phoenix_2_chart_rerates_and_removals/) · [original Google Sheet](https://docs.google.com/spreadsheets/d/1MhrFJf9Mnp5i5-cqWgeRvqcJZmzlDPwheLdQL4S1vaQ/edit?gid=1983447790#gid=1983447790) · [processed sheet used by this project](https://docs.google.com/spreadsheets/d/1DUMNMJJqfnBMCe_tdNmKEJyV_JGmkqqVBelZW0WIfSo/edit?usp=sharing)
- New song data: [official Pump It Up YouTube channel](https://www.youtube.com/@PUMPITUPOfficial)

## Licensing

The code in this project is licensed under the MIT license.

The base song dataset is sourced from
[pugkung/piutool](https://github.com/pugkung/piutool) (MIT licensed), reused
per the repository's stated terms: *"Feel free to use this tool or data
provided for any purpose."*

## Known limitations

- Song data reflects Pump It Up Phoenix v1.05 plus whatever has been
  manually added since; it is not automatically kept in sync with the live
  game.
- Doubles and Co-op charts are excluded by design, not by omission, this
  tool only concerns Singles charts, since that's what two players share.
- New songs are added by manual transcription from official gameplay
  footage rather than scraped, since the community sites with up-to-date
  chart data (e.g. tier-list sites) disallow automated access.
#!/bin/bash
# clean.sh — deletes generated artifacts so the pipeline can be rerun from scratch

set -e  # stop immediately if any command fails, rather than continuing silently

rm -f piu_songs.db piu_rerates.db piu_songs_final.db
rm -f supplemental_songs.json piu_songs.csv

echo "Cleaned generated artifacts."
#!/usr/bin/env bash
# Compute the helper's plan and H for every goal word that has a trace (in parallel).
# usage: scripts/make_all_helpers.sh [WORD ...]     (default: all words except MASTER, which already exists)
cd "$(dirname "$0")/.." || exit 1
source .venv/bin/activate
WORDS=("$@"); [ ${#WORDS[@]} -eq 0 ] && WORDS=(HER OTHER BOTHER MOTHER FATHER LATHER FASTER FOSTER HATER LATER WATER)
mkdir -p out/logs
for w in "${WORDS[@]}"; do
  python3 -u scripts/make_helper.py "$w" > "out/logs/helper_$w.txt" 2>&1 &
done
wait
echo "all helpers finished"

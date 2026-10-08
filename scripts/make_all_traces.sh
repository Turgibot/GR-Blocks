#!/usr/bin/env bash
# Build the calculation trace for every goal word (in parallel). Each trace takes 1 to ~20 minutes.
# usage: scripts/make_all_traces.sh [WORD ...]     (default: all words except MASTER, which already exists)
cd "$(dirname "$0")/.." || exit 1
source .venv/bin/activate
WORDS=("$@"); [ ${#WORDS[@]} -eq 0 ] && WORDS=(HER OTHER BOTHER MOTHER FATHER LATHER FASTER FOSTER HATER LATER WATER)
mkdir -p out/logs
for w in "${WORDS[@]}"; do
  python3 -u scripts/make_trace.py "$w" > "out/logs/trace_$w.txt" 2>&1 &
done
wait
echo "all traces finished"

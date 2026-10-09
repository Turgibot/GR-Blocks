"""Two-arm plan cost for one word from the start state, with a chosen search.   usage: two_arm_word.py WORD SEARCH TIME_LIMIT_SECONDS"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import twoarm

word, search, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
towers = json.loads((ROOT / "data" / "blockworld.json").read_text())["towers"]
goal = [f"on({a},{b})" for a, b in zip(word, word[1:])] + [f"ontable({word[-1]})"]
t0 = time.time()
r = twoarm.solve(towers, goal, time_limit=limit, search=search)
print(f"{word} {search}: cost {r['cost']} {r.get('reason', '')}  ({time.time() - t0:.0f} s)")
if r["cost"]:
    for i, s in enumerate(r["steps"], 1):
        print(f"  {i}: {s['comps']}")

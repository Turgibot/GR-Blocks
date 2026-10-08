"""For every goal word: cost with the observations, cost without, likelihood and posterior.

usage: python3 scripts/recognize.py ["action a b, action c"] [beta]
   likelihood P(O|G) = 1 / (1 + exp(-beta * (cost_without_O - cost_with_O)))     (Part 6)
   posterior  P(G|O) is proportional to P(O|G) with a uniform prior over the 12 words
"""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
goals = list(json.loads((ROOT / "data" / "blockworld.json").read_text())["goals"])
obs = sys.argv[1] if len(sys.argv) > 1 else "unstack H T, put-down H"
beta = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
INF = float("inf")


def cost_of(label, text):
    m = re.search(rf"=== {re.escape(label)}: (cost (\d+)|no plan) ===", text)
    return int(m.group(2)) if m and m.group(2) else INF


rows = []
for word in goals:
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "compile_observations.py"), word, obs],
                         capture_output=True, text=True).stdout
    c_o, c_not = cost_of("G+O", out), cost_of("G+notO", out)
    if c_o == INF:
        like = 0.0
    elif c_not == INF:
        like = 1.0
    else:
        like = 1.0 / (1.0 + math.exp(-beta * (c_not - c_o)))
    rows.append((word, c_o, c_not, like))

total = sum(r[3] for r in rows)
print(f"observations: {obs}      beta = {beta}      prior: uniform (1/12 each)\n")
print(f"{'word':8}{'cost with O':>12}{'cost w/o O':>12}{'gap':>6}{'P(O|G)':>9}{'P(G|O)':>9}")
for word, c_o, c_not, like in rows:
    gap = "inf" if INF in (c_o, c_not) else str(c_not - c_o)
    print(f"{word:8}{c_o:>12}{c_not:>12}{gap:>6}{like:>9.3f}{like / total:>9.3f}")
print(f"\nsum of posteriors = {sum(r[3] / total for r in rows):.3f}")

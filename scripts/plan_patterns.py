"""Run the recognizer on many different optimal plans for MASTER and compare the early curves with the paper's Fig. 2.

usage: python3 scripts/plan_patterns.py [N_plans=150] [T=9]       needs out/plans_MASTER.json (scripts/enumerate_plans.py)
For every sampled plan and every step t <= T it needs the 12 pairs (c(G+O), c(G+notO)); steps that two plans share
(same first t actions) are computed once. Results are cached in out/prefix_costs.json.
What I read off the paper's plot (by eye): at t=4 one goal clearly leads (~0.24); at t=6 about three goals are tied at the
top (~0.30); at t=7 about six goals are tied (~0.165).
"""
import json
import math
import random
import re
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
WORDS = json.loads((ROOT / "data" / "blockworld.json").read_text())["goals"].keys()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 150
T = int(sys.argv[2]) if len(sys.argv) > 2 else 9
CACHE = OUT / "prefix_costs.json"


def costs_for(args):
    prefix, word = args
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "compile_observations.py"), word, ", ".join(prefix)], capture_output=True, text=True).stdout
    res = []
    for label in ("G+O", "G+notO"):
        m = re.search(rf"=== {re.escape(label)}: (?:cost (\d+)|no plan) ===", out)
        res.append(int(m.group(1)) if m and m.group(1) else None)
    return res


def analyse(cost, plan, beta=1.0):
    """For t = 3..T: the leading goals of the base belief (likelihood only, uniform prior)."""
    rows = {}
    for t in range(3, T + 1):
        post = {}
        for w in WORDS:
            cO, cN = cost[json.dumps([plan[:t], w])]
            e1 = 0.0 if cO is None else math.exp(-beta * cO)
            e2 = 0.0 if cN is None else math.exp(-beta * cN)
            post[w] = e1 / (e1 + e2) if e1 + e2 > 0 else 0.0
        z = sum(post.values()) or 1.0
        post = {w: v / z for w, v in post.items()}
        m = max(post.values())
        rows[t] = (sorted(w for w, v in post.items() if v > 0.9 * m), round(m, 2))
    return rows


if __name__ == "__main__":
    plans = [p["plan"] for p in json.loads((OUT / "plans_MASTER.json").read_text())["plans"]]
    rng = random.Random(1)
    sample = rng.sample(plans, min(N, len(plans)))
    cost = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    need = sorted({(tuple(p[:t]), w) for p in sample for t in range(1, T + 1) for w in WORDS if json.dumps([p[:t], w]) not in cost})
    print(f"{len(sample)} plans sampled, {len(need)} (prefix, goal) planner calls needed (the rest are cached)", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(28) as ex:
        for (prefix, w), r in zip(need, ex.map(costs_for, need, chunksize=8)):
            cost[json.dumps([list(prefix), w])] = r
    CACHE.write_text(json.dumps(cost))
    print(f"computed in {time.time() - t0:.0f} s", flush=True)

    pat = {}
    for p in sample:
        rows = analyse(cost, p)
        pat[tuple(p)] = rows
    # how many goals are tied at the top, per step, over all sampled plans
    for t in range(3, T + 1):
        c = Counter(len(rows[t][0]) for rows in pat.values())
        lead = Counter(",".join(rows[t][0]) if len(rows[t][0]) <= 3 else f"{len(rows[t][0])} goals" for rows in pat.values())
        print(f"t={t}: tied at the top (count of plans): " + ", ".join(f"{k} goals: {v}" for k, v in sorted(c.items())) + "   | most common leaders: " + "; ".join(f"{k} ({v})" for k, v in lead.most_common(3)))
    paper_like = [p for p, rows in pat.items() if rows[4][0] == ["BOTHER"] and len(rows[6][0]) == 3 and len(rows[7][0]) >= 5]
    print(f"\nplans whose pattern is like the paper's (BOTHER alone on top at t=4, three tied at t=6, five or more tied at t=7): {len(paper_like)} of {len(pat)}")
    print("plans with a single leader at t=4:", sum(len(rows[4][0]) == 1 for rows in pat.values()), "| leaders at t=4:", Counter(rows[4][0][0] for rows in pat.values() if len(rows[4][0]) == 1).most_common(4))
    print("max number of goals tied at t=7 over all plans:", max(len(rows[7][0]) for rows in pat.values()))

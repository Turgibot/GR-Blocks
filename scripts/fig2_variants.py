"""Which small change to the recognizer would make our curves look like the paper's Fig. 2?  (No planner calls.)

Uses the stored planner costs and plans of out/trace_MASTER.json and recomputes the beliefs under alternatives:
  ours             t = number of observed actions; likelihood = Boltzmann over {G+O, G+notO}   (what the workbench shows)
  t = c(G+O)       the prior's t is goal-specific: the cost of the optimal plan that explains the observations
  t = prefix       ... the length of the plan prefix up to the last explained observation ("the subplan with the fewest
                   consumed resources" of the paper, p. 6)
  excess           likelihood = exp(-beta * (c(G+O) - c*(G))): no comparison with G+notO
  beta = ...       a weaker likelihood
What I read off the paper's plots by eye (approximate): single spike ~0.24 at t=4; peak ~0.30 at t=6 (0.36 for eps=6);
~0.165 with about six goals tied at t=7; with eps=3 and 6 a costly goal reaches ~0.7 / ~1.0 at t=16 while the goals
that fit MASTER fall to ~0.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from survival import survival

tr = json.loads((ROOT / "out" / "trace_MASTER.json").read_text())
meta, steps = tr["meta"], tr["steps"]
WORDS, LAM = meta["words"], meta["lambda"]
cstar = {w: meta["goals"][w]["c_star"] for w in WORDS}


def prefix_len(plan, observed):
    """Position (1-based) of the last observation when the observations are matched in order, as early as possible."""
    i = 0
    for k, a in enumerate(plan, 1):
        if i < len(observed) and a == observed[i]:
            i += 1
            if i == len(observed):
                return k
    return len(plan)


def belief(t, eps, variant, beta=1.0):
    s = steps[t]
    score = {}
    for w in WORDS:
        g = s["goals"][w]
        cO, cN = g["c_O"], g["c_notO"]
        if variant.startswith("excess"):
            like = 0.0 if cO is None else math.exp(-beta * (cO - cstar[w]))
        else:
            e1 = 0.0 if cO is None else math.exp(-beta * cO)
            e2 = 0.0 if cN is None else math.exp(-beta * cN)
            like = e1 / (e1 + e2) if e1 + e2 > 0 else 0.0
        if cO is None:
            tw = t
        elif "c(G+O)" in variant:
            tw = cO
        elif "prefix" in variant:
            tw = prefix_len(g["plan_O"], s["observed"])
        else:
            tw = t
        score[w] = like * survival(tw + eps, cstar[w], LAM)
    z = sum(score.values()) or 1.0
    return {w: v / z for w, v in score.items()}


def line(variant, eps, beta=1.0):
    B = {t: belief(t, eps, variant, beta) for t in range(1, len(steps))}
    def top(t, k=1):
        p = B[t]; ws = sorted(p, key=p.get, reverse=True)[:k]; return ", ".join(f"{w} {p[w]:.2f}" for w in ws)
    p7 = B[7]; m7 = max(p7.values()); tied7 = sum(v > 0.9 * m7 for v in p7.values())
    mast = B[16]["MASTER"]
    return f"  eps={eps}:  t4 [{top(4)}]  t6 [{top(6)}]  t7 [{top(7)}] ({tied7} goals within 10% of the top)  t16 [{top(16, 2)}]  MASTER at t16 = {mast:.2f}"


VARIANTS = [("ours", 1.0), ("t = c(G+O)", 1.0), ("t = prefix", 1.0), ("excess", 1.0), ("excess, t = prefix", 1.0),
            ("ours, beta = 0.3", 0.3), ("ours, beta = 0.1", 0.1)]
for name, beta in VARIANTS:
    print(f"{name}")
    v = name.split(",")[0] if name.startswith("ours") else name
    for eps in (0, 3, 6):
        print(line("ours" if name.startswith("ours") else name, eps, beta))
print("\npaper (read by eye): t4 [one goal ~0.24]  t6 [~0.30, three goals]  t7 [~0.165, about six goals]  t16: eps=3 costly goal ~0.7, eps=6 ~1.0, MASTER ~0")

"""Add the paper's dynamic prior (survival analysis, Parts 18-21) to the saved beliefs.

usage: python3 scripts/dynamic_prior.py [lambda]        (default lambda = 1; the paper gives no value)
Reads out/belief_MASTER.json (made by watch_belief.py). No planner calls are needed:
the saved posteriors are proportional to the likelihoods because the old prior was uniform.

   P(G | O, t)  proportional to  P(O | G) * survival(t + eps | G)
   survival(t' | G) = P(cost >= t' | G),  cost = c*(G) - 1 + k,  k ~ positive Poisson(lambda + 1)
"""
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
lam = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
EPSILONS = [0, 1, 3, 6]          # the four panels of the paper's Fig. 2

cost = {w: g["cost_one_agent"] for w, g in json.loads((ROOT / "data" / "blockworld.json").read_text())["goals"].items()}
saved = json.loads((ROOT / "out" / "belief_MASTER.json").read_text())
ts = sorted(int(t) for t in saved["posterior"])
likelihood = {t: saved["posterior"][str(t)] for t in ts}       # proportional to P(O|G)


def pmf(x, c):
    """P(real plan cost = x | G): the paper's shifted positive Poisson."""
    if x < c:
        return 0.0
    k, l = x - c + 1, lam + 1
    return l ** k / (math.factorial(k) * (math.exp(l) - 1))


def survival(tp, c):
    """P(plan is still running at tp)."""
    if tp <= c:
        return 1.0
    return max(1.0 - sum(pmf(x, c) for x in range(c, tp)), 1e-12)


def belief(eps):
    out = {}
    for t in ts:
        w = {g: likelihood[t][g] * survival(t + eps, cost[g]) for g in cost}
        z = sum(w.values())
        out[t] = {g: v / z for g, v in w.items()}
    return out


results = {eps: belief(eps) for eps in EPSILONS}
print(f"lambda = {lam} (my assumption)   hidden goal = MASTER   t = actions seen\n")
for eps in EPSILONS:
    print(f"--- eps = {eps} ---")
    print(f"{'t':>3}  top three goals")
    for t in (2, 6, 8, 12, 14, 16):
        post = results[eps][t]
        top = sorted(post, key=post.get, reverse=True)[:3]
        print(f"{t:>3}  " + "   ".join(f"{g} {post[g]:.2f}" for g in top))
    print()

fig, axes = plt.subplots(1, 4, figsize=(20, 4))
for ax, eps in zip(axes, EPSILONS):
    for g in cost:
        ax.plot(ts, [results[eps][t][g] for t in ts], lw=2.6 if g == "MASTER" else 1.1, label=g)
    ax.set_title(f"Recognition over time, epsilon = {eps}")
    ax.set_xlabel("Time step t")
    ax.set_ylim(0, 1.0 if eps >= 3 else 0.6)
axes[0].set_ylabel("P(G | O, t)")
axes[-1].legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8)
fig.suptitle(f"Our reproduction of Fig. 2 (lambda = {lam} is my assumption)", y=1.02)
fig.tight_layout()
(ROOT / "out").mkdir(exist_ok=True)
fig.savefig(ROOT / "out" / "fig2_ours.png", dpi=110, bbox_inches="tight")
print("wrote out/fig2_ours.png")

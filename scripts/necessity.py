"""Necessity N(p | O) and the helper's estimated goal G_hat (Definition 1, Part 7).

usage: python3 scripts/necessity.py [tau] [lambda]        (defaults: tau = 0.3 as in the paper, lambda = 1)
Uses the beliefs saved by watch_belief.py for R_ed's plan to MASTER. Two versions of the belief:
  base   : likelihood only (uniform prior)
  eps=3  : with the dynamic prior, foresight eps = 3 (the value the paper uses in its example)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from survival import survival

tau = float(sys.argv[1]) if len(sys.argv) > 1 else 0.3
lam = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
EPS = 3

goals = json.loads((ROOT / "data" / "blockworld.json").read_text())["goals"]
cost = {w: g["cost_one_agent"] for w, g in goals.items()}
saved = json.loads((ROOT / "out" / "belief_MASTER.json").read_text())["posterior"]


def conditions(word):
    return [f"on({a},{b})" for a, b in zip(word, word[1:])] + [f"ontable({word[-1]})"]


def belief(t, with_prior):
    if t == 0:
        return {w: 1 / len(goals) for w in goals}
    post = dict(saved[str(t)])
    if with_prior:
        post = {w: p * survival(t + EPS, cost[w], lam) for w, p in post.items()}
        z = sum(post.values())
        post = {w: p / z for w, p in post.items()}
    return post


def necessity(post):
    n = {}
    for w, p in post.items():
        for c in conditions(w):
            n[c] = n.get(c, 0.0) + p          # sum of P(G|O) over goals that contain the condition
    return n


def conflicts(conds):
    """Pairs of conditions that cannot both be true."""
    parsed = []
    for c in conds:
        name, args = c[:-1].split("(")
        parsed.append((c, name, args.split(",")))
    found = []
    for i, (c1, n1, a1) in enumerate(parsed):
        for c2, n2, a2 in parsed[i + 1:]:
            if n1 == n2 == "on" and ((a1[1] == a2[1] and a1[0] != a2[0]) or (a1[0] == a2[0] and a1[1] != a2[1])):
                found.append((c1, c2))                     # two blocks on one block, or one block on two
            if {n1, n2} == {"on", "ontable"}:
                on_args, tab_args = (a1, a2) if n1 == "on" else (a2, a1)
                if on_args[0] == tab_args[0]:
                    found.append((c1, c2))                 # a block both on another block and on the table
    return found


print(f"tau = {tau}   lambda = {lam}   hidden goal = MASTER   conditions are the paper's: 'X on Y' pairs plus 'last letter on table'\n")
for with_prior, label in ((False, "base (likelihood only)"), (True, f"dynamic prior, eps = {EPS}")):
    print(f"=== belief: {label} ===")
    for t in (0, 2, 6, 14, 16):
        post = belief(t, with_prior)
        n = necessity(post)
        g_hat = sorted((c for c, v in n.items() if v >= tau), key=lambda c: -n[c])
        bad = conflicts(g_hat)
        print(f"  t = {t:2}   G_hat = " + ", ".join(f"{c} {n[c]:.2f}" for c in g_hat))
        print(f"          conflicts: " + ("none -> a plan can exist" if not bad else "; ".join(f"{a} vs {b}" for a, b in bad) + " -> NO plan can satisfy G_hat"))
    print()

n2 = necessity(belief(2, False))
print(f"Check against the paper (after 2 actions): N(on(H,E)) = {n2['on(H,E)']:.2f}, N(on(T,E)) = {n2['on(T,E)']:.2f}   (paper says 0.5 and 0.5)")

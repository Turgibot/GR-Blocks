"""Offline experiment: helpfulness when R_ed only ever acts in her own favour.   (not part of the page)

usage: python3 scripts/ed_only_in_favour.py [WORD ...]        (needs out/helper_<WORD>.json; default: every word that has one)

The paper's pi_{R_ed<-R_ing} (plan D) lets the planner choose R_ed's moves freely, so she may make moves that do nothing
for her own goal only to make R_ing's (possibly wrong) plan possible. Here instead:
  * R_ed follows an optimal plan to her real goal G, and never makes a move for R_ing's sake;
  * R_ing performs pi_Ring (from the paper's plan B) in order; a move that is impossible right now (a block under another
    block, a hand that is full) or that touches a block R_ed is moving in the same step is delayed;
  * only the physical effects of R_ing's moves matter: when one makes R_ed's next move impossible, R_ed re-plans from the
    new state (optimal, alone, with R_ing's arm assumed to stay still);
  * the run ends when G holds.
H_favour = C - (number of joint steps), with C = R_ed alone to G from the joining state (the paper's plan C).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import twoarm

MAX_STEPS = 60


def facts(towers):
    f = set()
    for col in towers:
        f.add(f"ontable({col[-1]})")
        f |= {f"on({a},{b})" for a, b in zip(col, col[1:])}
    return f


def parse(a):
    p = a.split()
    return p[0], p[1:]


def blocks_of(a):
    return set(parse(a)[1])


def apply(st, a):
    """Return the new state (towers top-first, hands {1,2}) after action a by arm 1 or 2, or None if it is impossible."""
    arm, act = a
    name, args = parse(act)
    towers, hands = [list(c) for c in st["towers"]], dict(st["hands"])
    if name in ("pick-up", "unstack") and hands[arm] is not None:
        return None
    if name in ("put-down", "stack") and hands[arm] != args[0]:
        return None
    if name == "pick-up":
        x = args[0]
        col = next((c for c in towers if c[0] == x and len(c) == 1), None)
        if not col:
            return None
        towers.remove(col); hands[arm] = x
    elif name == "unstack":
        x, y = args
        col = next((c for c in towers if c[0] == x and len(c) > 1 and c[1] == y), None)
        if not col:
            return None
        col.pop(0); hands[arm] = x
    elif name == "put-down":
        towers.append([args[0]]); hands[arm] = None
    elif name == "stack":
        x, y = args
        col = next((c for c in towers if c[0] == y), None)
        if not col:
            return None
        col.insert(0, x); hands[arm] = None
    else:
        return None
    return {"towers": towers, "hands": hands}


def plan_alone(st, goal):
    """R_ed's optimal plan to the goal from this state, R_ing's arm assumed not to move."""
    r = twoarm.solve(st["towers"], goal, forced_arm2=[], hands=st["hands"], time_limit=120)
    if r["cost"] is None:
        return None
    return [s["comps"][1] for s in r["steps"]]


def simulate(start, goal, pi_ring):
    st = {"towers": [list(c) for c in start["towers"]], "hands": {1: start["hands"].get("1"), 2: start["hands"].get("2")}}
    ed, replans, j, log = plan_alone(st, goal), 0, 0, []
    for step in range(1, MAX_STEPS + 1):
        if set(goal) <= facts(st["towers"]):
            return step - 1, replans, log
        if not ed:                                                         # no plan (R_ing holds a block she needs): wait, then try again
            ed = plan_alone(st, goal)
        a_ed = ed[0] if ed else None
        if a_ed is not None and apply(st, (1, a_ed)) is None:                 # R_ing's moves got in the way: R_ed re-plans
            ed = plan_alone(st, goal); replans += 1
            a_ed = ed[0] if ed else None
        a_ring = pi_ring[j] if j < len(pi_ring) else None
        nxt = st
        did_ed = did_ring = None
        if a_ed is not None:
            n = apply(st, (1, a_ed))
            if n is not None:
                nxt, did_ed = n, a_ed
        if a_ring is not None and not (did_ed and blocks_of(did_ed) & blocks_of(a_ring)):
            n = apply(nxt, (2, a_ring))
            if n is not None and apply(st, (2, a_ring)) is not None:
                nxt, did_ring = n, a_ring; j += 1
        if did_ed is None and did_ring is None:
            log.append((step, "nobody can move", st["towers"]))
            return None, replans, log
        if did_ed:
            ed.pop(0)
        log.append((step, did_ed, did_ring))
        st = nxt
    return None, replans, log


def run(word):
    h = json.loads((ROOT / "out" / f"helper_{word}.json").read_text())
    start, goal, pi_ring = h["start"], h["goal"], h["pi_ring"]
    c_alone = h["alone_G"]["cost"] if isinstance(h["alone_G"], dict) else h["alone_G"]
    cost, replans, log = simulate(start, goal, pi_ring)
    return h, c_alone, cost, replans, log


if __name__ == "__main__":
    words = sys.argv[1:] or sorted(p.stem.split("_", 1)[1] for p in (ROOT / "out").glob("helper_*.json"))
    rows = []
    for w in words:
        h, c, cost, replans, log = run(w)
        d = h["response_G"]["cost"] if isinstance(h["response_G"], dict) else h["response_G"]
        rows.append((w, c, d, h["H"], cost, replans))
        print(f"\n== {w}: R_ed alone C = {c};  paper's plan D = {d} (H = {h['H']});  R_ed only in her favour: "
              f"{'never finishes' if cost is None else str(cost) + ' steps'}  ({replans} re-plans)")
        for s in log:
            print("   ", s)
    print("\nword      C   D(paper)  H(paper)   favour   H(favour)")
    for w, c, d, hp, cost, rp in rows:
        print(f"{w:8} {c:3} {d:8} {hp:9}   {'inf' if cost is None else cost:>6}   {'-inf' if cost is None else c - cost:>8}")

"""Safe exposure (branch 'improvements'), step 1: which R_ing moves are harmless before recognition has settled?

usage: python3 scripts/safe_exposure.py [WORD] [min_posterior]      (needs out/trace_<WORD>.json)

A candidate move at step t: R_ing takes the top block x of a column (x not in R_ed's hand) and puts it on the table.
Live goals = goals with posterior (eps3) >= min_posterior (default 0.01).
  safe   : no live goal has the fact on(x, y) (y = the block x sits on). The move destroys no wanted fact.
  useful : for how many live goals must x move anyway, because some block b below x is not in its final place
           (b's fact on(b, c) / ontable(b) is not in that goal's conditions), so x has to come off to free b.
Only syntactic tests so far; the cost check with the planner comes in step 2.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
word = sys.argv[1] if len(sys.argv) > 1 else "MASTER"
min_p = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
trace = json.loads((ROOT / "out" / f"trace_{word}.json").read_text())
goals = {w: set(g["conditions"]) for w, g in trace["meta"]["goals"].items()}


def position_fact(col, i):
    """The fact that says where block col[i] sits (columns are listed top to bottom)."""
    return f"on({col[i]},{col[i + 1]})" if i + 1 < len(col) else f"ontable({col[i]})"


for s in trace["steps"]:
    live = [w for w, p in s["posterior"]["eps3"].items() if p >= min_p]
    held = s["world"]["hand"]
    print(f"\nt={s['t']}  after '{s['last_action']}'   R_ed holds {held}   live goals: {len(live)}")
    for col in s["world"]["towers"]:
        if not col or len(col) < 2 or col[0] == held:
            continue
        x = col[0]
        fact = position_fact(col, 0)
        killed_by = [w for w in live if fact in goals[w]]
        movers = [w for w in live if any(position_fact(col, i) not in goals[w] for i in range(1, len(col)))]
        verdict = "SAFE  " if not killed_by else "unsafe"
        print(f"   x={x} ({fact:12}) {verdict}  useful for {len(movers):2}/{len(live)} live goals"
              + (f"   wanted by {','.join(killed_by)}" if killed_by else ""))

"""Safe exposure (branch 'improvements'): the data for the page safe-exposure.html.

usage: python3 scripts/make_exposure.py [WORD] [min_posterior]      (needs out/trace_<WORD>.json and out/helper_<WORD>.json)
writes out/exposure_<WORD>.json

Same procedure as exposure_experiment.py (see its docstring and docs/safe_exposure.md), but everything the page shows is saved:
for every step before the paper's joining time t_join
  - R_ed's action, R_ing's action, the world after the step, R_ed's replan if her plan stopped being applicable,
  - the live goals (posterior >= min_posterior) and every candidate exposure move with its tests:
        safe    = no live goal contains the fact on(x, below)
        useful  = the live goals for which some block below x is not in its goal position
        u       = number of useful goals; the chosen move is the safe one with the largest u
and after t_join the paper's helper computation from the exposed world (C, B, pi_Ring, D) with the joint steps of D.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import twoarm

word = sys.argv[1] if len(sys.argv) > 1 else "MASTER"
min_p = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
VARIANT = "eps3"
trace = json.loads((ROOT / "out" / f"trace_{word}.json").read_text())
paper = json.loads((ROOT / "out" / f"helper_{word}.json").read_text())
t_join, g_hat, goal = paper["t_join"], paper["G_hat"], paper["goal"]
goals = {w: set(g["conditions"]) for w, g in trace["meta"]["goals"].items()}


def pos_fact(col, i):
    """The fact that says where block col[i] sits (columns are listed top to bottom)."""
    return f"on({col[i]},{col[i + 1]})" if i + 1 < len(col) else f"ontable({col[i]})"


def candidates(world, live, busy):
    """Every top block that could be moved, with the tests. R_ing's own block and R_ed's busy blocks are marked."""
    out = []
    for col in world["towers"]:
        if len(col) < 2:
            continue
        x, fact = col[0], pos_fact(col, 0)
        wanted_by = [w for w in live if fact in goals[w]]
        useful_for = [w for w in live if any(pos_fact(col, i) not in goals[w] for i in range(1, len(col)))]
        out.append({"x": x, "y": col[1], "fact": fact, "safe": not wanted_by, "wanted_by": wanted_by,
                    "useful_for": useful_for, "u": len(useful_for), "busy": x in busy or col[1] in busy})
    return out


def act(state, arm, text):
    op, *args = text.split()
    return twoarm.apply_joint(state, f"one_{op}_arm{arm}", args)


def applicable(state, arm, text):
    try:
        act(state, arm, text)
        return True
    except ValueError:
        return False


state = twoarm.state_from(trace["meta"]["start_towers"])
plan, done, holding2 = list(trace["meta"]["observed_plan"]), 0, None
steps, finished_at = [], None
for t in range(t_join):
    replan = None
    if plan and not applicable(state, 1, plan[0]):
        w = twoarm.world_of(state)
        r = twoarm.solve(w["towers"], goal, forced_arm2=[], hands=w["hands"])
        plan = [s["comps"][1] for s in r["steps"]]
        replan = {"reason": f"'{plan[0]}' is next in the new plan; the old next action no longer applies", "plan": list(plan)}
    a1 = plan.pop(0) if plan else None
    post_idx = min(done, len(trace["steps"]) - 1)
    posterior = trace["steps"][post_idx]["posterior"][VARIANT]
    live = [w for w, p in posterior.items() if p >= min_p]
    busy = set(a1.split()[1:]) if a1 else set()
    world_before = twoarm.world_of(state)
    cands = candidates(world_before, live, busy)
    a2, chosen, why = None, None, ""
    if holding2:
        a2, why = f"put-down {holding2}", f"R_ing is holding {holding2}: second half of the exposure move"
    elif t + 2 > t_join:
        why = "too late to start a move (it needs two steps before R_ing joins)"
    else:
        ok = [c for c in cands if c["safe"] and not c["busy"] and c["u"] > 0]
        if ok:
            chosen = max(ok, key=lambda c: c["u"])
            a2, why = f"unstack {chosen['x']} {chosen['y']}", f"safe, and useful for {chosen['u']} of {len(live)} live goals (the most)"
        else:
            why = "no safe move is useful for any live goal"
    s1 = act(state, 1, a1) if a1 else state
    collision = None
    if a2:
        if set(a2.split()[1:]) & busy:
            collision, a2 = f"'{a2}' touches a block R_ed is using; dropped", None
        else:
            s1 = act(s1, 2, a2)
            holding2 = a2.split()[1] if a2.startswith("unstack") else None
    state = s1
    done += 1
    steps.append({"step": t + 1, "posterior_index": post_idx, "posterior": {w: round(q, 5) for w, q in posterior.items()}, "live": live, "n_live": len(live), "candidates": cands, "chosen": chosen["x"] if chosen else None,
                  "why": why, "ed": a1, "ing": a2, "collision": collision, "replan": replan, "world": twoarm.world_of(state)})
    print(f"step {t + 1:2}: R_ed {a1 or '-':14} R_ing {a2 or '-':16} live {len(live):2}   {why}" + (f"   [replan]" if replan else ""))
    if set(twoarm.goal_facts(goal)) <= state and not holding2:
        finished_at = t + 1
        break

world = twoarm.world_of(state)
result = {"word": word, "min_posterior": min_p, "variant": VARIANT, "t_join": t_join, "goal": goal, "G_hat": g_hat,
          "start": twoarm.world_of(twoarm.state_from(trace["meta"]["start_towers"])), "steps": steps, "finished_at": finished_at,
          "paper": {"alone": t_join + paper["alone_G"]["cost"], "joint": t_join + paper["response_G"]["cost"],
                    "C": paper["alone_G"]["cost"], "D": paper["response_G"]["cost"], "H": paper["H"]}}
if finished_at:
    result["completion"] = finished_at
    print(f"\nR_ed's goal is reached after step {finished_at}, before t_join = {t_join}")
elif world["hands"][1] is not None or world["hands"][2] is not None:
    sys.exit(f"{word}: a hand is full at t_join: {world['hands']}")
else:
    towers = world["towers"]
    C = twoarm.solve(towers, goal, forced_arm2=[])
    B = twoarm.solve(towers, g_hat)
    pi_ring = [s["comps"][2] for s in B["steps"]] if B["cost"] else None
    D = twoarm.solve(towers, goal, forced_arm2=pi_ring) if pi_ring is not None else {"cost": None}
    if None in (C["cost"], D["cost"]):
        sys.exit(f"{word}: C, B or D not found within the time limit")
    result.update({"C": C["cost"], "B": B["cost"], "pi_ring": pi_ring, "D": D["cost"], "H": C["cost"] - D["cost"],
                   "joint_steps": [{"comps": s["comps"], "world": s["world"]} for s in D["steps"]], "completion": t_join + D["cost"]})
    print(f"\nC = {C['cost']}   B = {B['cost']}   pi_Ring = {pi_ring}   D = {D['cost']}   H = C - D = {C['cost'] - D['cost']}")
p = result["paper"]
print(f"completion: R_ed alone {p['alone']}  paper {p['joint']}  safe exposure {result['completion']}")
(ROOT / "out" / f"exposure_{word}.json").write_text(json.dumps(result, indent=1))
print(f"wrote out/exposure_{word}.json")

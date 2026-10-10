"""Safe exposure (branch 'improvements'), step 2: does exposing blocks before recognition shorten the joint plan?

usage: python3 scripts/exposure_experiment.py [WORD] [min_posterior]      (needs out/trace_<WORD>.json and out/helper_<WORD>.json)

R_ed follows her observed plan, one action per step. In the same step R_ing (arm 2) may do ONE action of a safe exposure:
  unstack the top block x of a column, then (next step) put it on the table.
x must be safe (no live goal wants on(x, below), live = posterior >= min_posterior at that step), and the best one is the
move that is useful for the most live goals (see safe_exposure.py). R_ing does not know R_ed's next action; if its action would
make hers inapplicable it is a COLLISION: R_ing's action is dropped and counted.
No exposure is started so late that R_ing's hand is still full at t_join (the paper's joining time, from helper_<WORD>.json).

Then, from the exposed world, the paper's helper computation is run again (as in make_helper.py):
  C  R_ed alone to her goal G                                             (single arm)
  B  both arms to G_hat = P_Ring; pi_Ring = arm 2's part of it
  D  both arms to G with arm 2 locked to pi_Ring = P_{R_ed<-R_ing}
and completion time = t_join + D steps is compared with the paper's way (R_ing waits, then joins): t_join + D_paper.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import twoarm

word = sys.argv[1] if len(sys.argv) > 1 else "MASTER"
min_p = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
trace = json.loads((ROOT / "out" / f"trace_{word}.json").read_text())
paper = json.loads((ROOT / "out" / f"helper_{word}.json").read_text())
t_join, g_hat, goal = paper["t_join"], paper["G_hat"], paper["goal"]
goals = {w: set(g["conditions"]) for w, g in trace["meta"]["goals"].items()}
observed = trace["meta"]["observed_plan"]


def pos_fact(col, i):
    return f"on({col[i]},{col[i + 1]})" if i + 1 < len(col) else f"ontable({col[i]})"


def choose_exposure(world, live, busy):
    """Best safe top block to move: most live goals for which it has to move anyway. Returns (x, y, useful) or None."""
    best = None
    for col in world["towers"]:
        if len(col) < 2 or col[0] in busy or col[1] in busy:
            continue
        x = col[0]
        if any(pos_fact(col, 0) in goals[w] for w in live):                       # unsafe: some live goal wants on(x, below)
            continue
        useful = sum(any(pos_fact(col, i) not in goals[w] for i in range(1, len(col))) for w in live)
        if useful and (best is None or useful > best[2]):
            best = (x, col[1], useful)
    return best


def act(state, arm, text):
    op, *args = text.split()
    return twoarm.apply_joint(state, f"one_{op}_arm{arm}", args)


state = twoarm.state_from(trace["meta"]["start_towers"])


def applicable(state, arm, text):
    op, *args = text.split()
    try:
        twoarm.apply_joint(state, f"one_{op}_arm{arm}", args)
        return True
    except ValueError:
        return False


plan, done, replans = list(observed), 0, 0                 # R_ed's remaining plan; replanned (single arm, optimal) when her next action no longer applies
holding2, collisions = None, 0
for t in range(t_join):                                    # step t+1: R_ed does her next action; R_ing its exposure action
    if plan and not applicable(state, 1, plan[0]):
        w = twoarm.world_of(state)
        r = twoarm.solve(w["towers"], goal, forced_arm2=[], hands=w["hands"])
        plan, replans = [s["comps"][1] for s in r["steps"]], replans + 1
        print(f"        (R_ed replans, {len(plan)} actions left: {plan})")
    a1 = plan.pop(0) if plan else None
    live = [w for w, p in trace["steps"][min(done, len(trace["steps"]) - 1)]["posterior"]["eps3"].items() if p >= min_p]
    busy = set(a1.split()[1:]) if a1 else set()
    a2 = None
    if holding2:
        a2 = f"put-down {holding2}"
    elif t + 2 <= t_join:                                  # room for unstack now and put-down next step
        pick = choose_exposure(twoarm.world_of(state), live, busy)
        if pick:
            a2 = f"unstack {pick[0]} {pick[1]}"
    s1 = act(state, 1, a1) if a1 else state
    note = ""
    if a2:
        try:
            if set(a2.split()[1:]) & busy:
                raise ValueError("same block as R_ed")
            s1 = act(s1, 2, a2)
            holding2 = a2.split()[1] if a2.startswith("unstack") else None
        except ValueError as e:
            collisions += 1
            note, a2 = f"   COLLISION, dropped ({e})", None
    state = s1
    done += 1
    print(f"step {t + 1:2}: R_ed {a1 or '-':14} R_ing {a2 or '-':14}{note}")
    if set(twoarm.goal_facts(goal)) <= state and not holding2:
        print(f"\nR_ed's goal is reached after step {t + 1}, before the paper's join time {t_join}: "
              f"completion {t + 1}  (paper: {t_join + paper['response_G']['cost']}, R_ed alone: {t_join + paper['alone_G']['cost']})")
        sys.exit(0)

world = twoarm.world_of(state)
if world["hands"][1] is not None or world["hands"][2] is not None:
    sys.exit(f"{word}: a hand is full at t_join: {world['hands']}")
towers = world["towers"]
print(f"\nworld at t_join={t_join}: " + " | ".join("".join(c) for c in towers) + f"      collisions: {collisions}, replans: {replans}")
print(f"paper's way (R_ing waits): C = {paper['alone_G']['cost']}, D = {paper['response_G']['cost']}, H = {paper['H']}\n")

C = twoarm.solve(towers, goal, forced_arm2=[])
B = twoarm.solve(towers, g_hat)
pi_ring = [s["comps"][2] for s in B["steps"]] if B["cost"] else None
D = twoarm.solve(towers, goal, forced_arm2=pi_ring) if pi_ring is not None else {"cost": None}
print(f"C  R_ed alone to G           : {C['cost']}")
print(f"B  both arms to G_hat        : {B['cost']}   pi_Ring = {pi_ring}")
print(f"D  both arms, arm 2 locked   : {D['cost']}")
if None not in (C["cost"], D["cost"]):
    print(f"H (exposed) = C - D = {C['cost']} - {D['cost']} = {C['cost'] - D['cost']}")
    print(f"completion: paper {t_join} + {paper['response_G']['cost']} = {t_join + paper['response_G']['cost']}   "
          f"with exposure {t_join} + {D['cost']} = {t_join + D['cost']}   "
          f"R_ed alone: {t_join} + {paper['alone_G']['cost']} = {t_join + paper['alone_G']['cost']}")

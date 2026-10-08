"""Independent and adversarial interaction (Definitions 3 and 4), computed from the moment R_ing joins.

usage: python3 scripts/make_scenarios.py [WORD] [all|independent|adversarial]       needs out/helper_<WORD>.json; writes out/scenarios_<WORD>.json

Each scenario is a plan pi_Ring for R_ing; R_ed's best response is then planned with arm 2 locked to it (P_{Red<-Ring}),
and the helpfulness is H = c(R_ed alone) - c(R_ed's response)  (Definition 5, with c = infinity if no plan exists).

INDEPENDENT (Def. 3). R_ing has her own goal G'. The paper's centralized problem asks for G' together with `success`,
and `success` is set once R_ed's actions have made G_hat true. I plan for G' AND G_hat at the end (slightly stronger than
the paper's sticky `success`; it is the same for the paper's example). R_ing's part of that joint plan is pi_Ring.

ADVERSARIAL (Def. 4). The paper's centralized formulation {not success, d} is satisfied trivially by everybody doing
nothing, so it cannot by itself produce a blocking plan (the paper then discusses blocking plans in prose). I therefore
evaluate the two blocking plans the paper describes (§5, Fig. 3): hoarding a needed block, and stacking S on M.
These are given plans, not plans found by a planner.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import twoarm

word = sys.argv[1] if len(sys.argv) > 1 else "MASTER"
which = sys.argv[2] if len(sys.argv) > 2 else "all"          # all | independent | adversarial
helper = json.loads((ROOT / "out" / f"helper_{word}.json").read_text())
trace = json.loads((ROOT / "out" / f"trace_{word}.json").read_text())
t_join, g_hat, goal = helper["t_join"], helper["G_hat"], helper["goal"]
towers = trace["steps"][t_join]["world"]["towers"]
C = helper["alone_G"]["cost"]
print(f"{word}: R_ing joins after action {t_join}; R_ed alone needs {C} more steps for her goal.\n")


def word_conds(w):
    return [f"on({a},{b})" for a, b in zip(w, w[1:])] + [f"ontable({w[-1]})"]


def arm2_only_steps(plan):
    """World after each of R_ing's actions when R_ed does nothing (used when R_ed has no plan at all)."""
    state, steps = twoarm.state_from(towers), []
    for a in plan:
        if a is None:
            comps = {"1": None, "2": None}
            name, args = None, None
        else:
            op, *args = a.split()
            name = f"one_{op}_arm2"
            state = twoarm.apply_joint(state, name, args)
        steps.append({"comps": {"1": None, "2": a}, "world": twoarm.world_of(state)})
    return steps


def stringify(plan):                                   # JSON keys: arms become "1" and "2"
    return {"cost": plan["cost"], "reason": plan.get("reason"),
            "steps": [{"comps": {str(k): v for k, v in s["comps"].items()}, "world": {"towers": s["world"]["towers"], "hands": {str(k): v for k, v in s["world"]["hands"].items()}}} for s in plan.get("steps", [])]}


def evaluate(key, label, kind, text, pi_ring, extra_rows, plans, timeline=None, coupling=True):
    print(f"--- {label}")
    resp = twoarm.solve(towers, goal, forced_arm2=pi_ring, coupling=coupling)
    own_timeline = timeline is not None                  # the independent case shows the joint plan itself
    if resp["cost"] is not None:
        H, H_text = C - resp["cost"], f"{C} − {resp['cost']} = {C - resp['cost']}"
        timeline = timeline if own_timeline else resp
    elif resp.get("reason") == "unsolvable":
        H, H_text, timeline = None, f"{C} − ∞ = −∞", {"cost": None, "steps": arm2_only_steps(pi_ring)}
    else:
        print("   response not found within the time limit; scenario skipped")
        return None
    print(f"   pi_Ring = {pi_ring}   R_ed's best response: {resp['cost'] if resp['cost'] is not None else 'no plan (infinite cost)'}   H = {H_text}")
    rows = extra_rows + [["R_ed alone, from now to her goal G", C, ""],
                         ["R_ed's best response while R_ing follows π_Ring (P_Red←Ring)", resp["cost"] if resp["cost"] is not None else "∞", "no plan exists: R_ed can never finish" if resp["cost"] is None else ""]]
    return {"key": key, "label": label, "kind": kind, "text": text, "pi_ring": pi_ring, "rows": rows, "plans": plans,
            "response": stringify(resp), "timeline": stringify(timeline), "timeline_source": "plan0" if own_timeline else "response", "alone_cost": C, "H": H, "H_text": H_text, "H_is_minus_inf": H is None}


scenarios = {}

# ---- independent: R_ing builds her own word by herself while R_ed follows her own plan ----
# R_ed is locked to the plan she would follow alone (she does not know R_ing exists) and nothing is coordinated: no
# handovers, no pair lifts. R_ing must reach her goal G' and R_ed her goal G, so R_ing must not break R_ed's plan.
# Among the shortest joint plans, the one where R_ing does the fewest actions is chosen. This is how I model "R_ing has
# a personal goal but should avoid preventing R_ed from accomplishing hers" (Definition 3).
ed_plan = [st["comps"]["1"] for st in helper["alone_G"]["steps"]]
for g_word in (("HOWL", "WOLF") if which in ("all", "independent") else ()):
    gp = word_conds(g_word)
    joint = twoarm.solve(towers, gp + goal, forced_arm1=ed_plan, coupling=False, tidy=True, time_limit=600)
    print(f"independent {g_word}: joint plan for G' and G, R_ed following her own plan: cost {joint['cost']} ({joint.get('reason', '')})")
    if joint["cost"] is None:
        continue
    pi = [st["comps"][2] for st in joint["steps"]]
    s = evaluate(f"independent_{g_word}", f"independent: R_ing builds {g_word}", "independent",
                 f"R_ing has her own goal G′ = {g_word} ({', '.join(gp)}) and plans it <b>by herself</b>. R_ed does not know about R_ing and follows the plan she would follow alone; "
                 f"R_ing must not break it. (No handovers or pair lifts: nothing is coordinated.)",
                 pi, [[f"R_ed follows her own plan and R_ing reaches G′ = {g_word}: joint plan", joint["cost"], f"R_ing does {sum(a is not None for a in pi)} actions; the fewest among the shortest plans"]],
                 [{"title": f"joint plan: R_ed follows her plan, R_ing builds {g_word}", "plan": stringify(joint)}], timeline=joint, coupling=False)
    if s:
        scenarios[s["key"]] = s

# ---- adversarial: the two blocking plans the paper describes ----
if which in ("all", "adversarial"):
    s = evaluate("adversarial_hoard", "adversarial: R_ing hoards S", "adversarial",
                 "R_ing takes the block S off the tower and holds it for ever (the paper's “trivial plan” π^hoard, §5). R_ed needs S for MASTER, so she can never finish.",
                 ["unstack S T"], [["π_Ring (R_ing takes S and then only waits)", 1, "unstack(S,T), then waiting"]], [])
    if s:
        scenarios[s["key"]] = s
    s = evaluate("adversarial_S_on_M", "adversarial: R_ing stacks S on M", "adversarial",
                 "R_ing unstacks S from the goal tower and stacks it on M (the paper's Fig. 3). This undoes two satisfied conditions; R_ed can still finish, but later.",
                 ["unstack S T", "stack S M"], [["π_Ring (R_ing moves S onto M, then waits)", 2, "unstack(S,T), stack(S,M)"]], [])
    if s:
        scenarios[s["key"]] = s

path = ROOT / "out" / f"scenarios_{word}.json"
if path.exists():                                      # keep what an earlier run already computed
    scenarios = {**json.loads(path.read_text())["scenarios"], **scenarios}
path.write_text(json.dumps({"word": word, "t_join": t_join, "scenarios": scenarios}, indent=1))
print(f"\nwrote out/scenarios_{word}.json with {len(scenarios)} scenarios: {', '.join(scenarios)}")

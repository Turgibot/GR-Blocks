"""Two-arm Block-words planning (the paper's joint actions), as a library.

  solve(towers, goal, forced_arm2=None)  -> {"cost": n, "steps": [...]}  or  {"cost": None}  (no plan / time limit)

A *joint action* is one time step: arm 1 (R_ed) and arm 2 (R_ing) each do one action or wait. The kinds are
(my reading of the paper's p. 6, validated on 9 of 12 words of Fig. 1):
  one arm acts alone | two arms on different blocks | handover | stacked-pair pick-up | stacked-pair put-down,
  the last two also for a pair whose lower block is on the table.

tidy=True gives every joint step cost 100 and every R_ing action 1, so among the shortest plans R_ing does the fewest actions.
coupling=False removes the handovers and pair lifts (R_ed does not coordinate with R_ing: independent interaction).
forced_arm1 does the same for arm 1 (R_ed follows a given plan while arm 2 is free).
forced_arm2 = list of arm-2 actions ("unstack F W", or None for waiting). It makes arm 2 follow exactly that plan,
step by step, and wait afterwards; arm 1 is free. That is the problem P_{Red<-Ring} of the paper (Part 12).
With forced_arm2 = [] arm 2 never acts, which is plain single-arm planning (R_ed alone).
"""
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
FD = ROOT / "third_party" / "downward" / "fast-downward.py"
OPS = json.loads((ROOT / "data" / "actions.json").read_text())["operators"]
BLOCKS = sorted(b for t in json.loads((ROOT / "data" / "blockworld.json").read_text())["towers"] for b in t)


# ---------------------------------------------------------------- the joint actions ----------------------------------
def _hand(pred, arm):
    return f"{pred}_{arm}" if pred in ("handempty", "holding") else pred


def _single(name, arm, suffix=""):
    o = OPS[name]
    conv = lambda facts: [tuple([_hand(f[0], arm)] + [a + suffix for a in f[1:]]) for f in facts]
    return {"params": [p + suffix for p in o["params"]], "pre": conv(o["pre"]), "add": conv(o["add"]), "del": conv(o["del"])}


def _build_joint():
    J = []
    for arm in (1, 2):                                            # one arm acts, the other waits
        for name in OPS:
            a = _single(name, arm)
            J.append({"name": f"one_{name}_arm{arm}", **a, "comps": {arm: (name, a["params"])}})
    for n1, n2 in itertools.product(OPS, repeat=2):               # two arms, different blocks
        a, b = _single(n1, 1, "1"), _single(n2, 2, "2")
        neq = [("neq", p, q) for p in a["params"] for q in b["params"]]
        J.append({"name": f"par_{n1}_{n2}", "params": a["params"] + b["params"], "pre": a["pre"] + b["pre"] + neq,
                  "add": a["add"] + b["add"], "del": a["del"] + b["del"], "comps": {1: (n1, a["params"]), 2: (n2, b["params"])}})
    for i, j in ((1, 2), (2, 1)):
        h = lambda p, k: _hand(p, k)
        J.append({"name": f"handover_{i}to{j}", "params": ["x"], "pre": [(h("holding", i), "x"), (h("handempty", j),)],
                  "add": [(h("holding", j), "x"), (h("handempty", i),)], "del": [(h("holding", i), "x"), (h("handempty", j),)],
                  "comps": {i: ("put-down", ["x"]), j: ("pick-up", ["x"])}})
        hands_free = [(h("handempty", i),), (h("handempty", j),)]
        J.append({"name": f"pairup_{i}{j}", "params": ["x", "y", "z"], "pre": [("on", "x", "y"), ("on", "y", "z"), ("clear", "x")] + hands_free,
                  "add": [(h("holding", i), "x"), (h("holding", j), "y"), ("clear", "z")], "del": [("on", "x", "y"), ("on", "y", "z"), ("clear", "x")] + hands_free,
                  "comps": {i: ("unstack", ["x", "y"]), j: ("unstack", ["y", "z"])}})
        J.append({"name": f"pairdown_{i}{j}", "params": ["x", "y", "z"], "pre": [(h("holding", i), "x"), (h("holding", j), "y"), ("clear", "z")],
                  "add": [("on", "x", "y"), ("on", "y", "z"), ("clear", "x")] + hands_free, "del": [(h("holding", i), "x"), (h("holding", j), "y"), ("clear", "z")],
                  "comps": {i: ("stack", ["x", "y"]), j: ("stack", ["y", "z"])}})
        J.append({"name": f"pairup_table_{i}{j}", "params": ["x", "y"], "pre": [("on", "x", "y"), ("ontable", "y"), ("clear", "x")] + hands_free,
                  "add": [(h("holding", i), "x"), (h("holding", j), "y")], "del": [("on", "x", "y"), ("ontable", "y"), ("clear", "x")] + hands_free,
                  "comps": {i: ("unstack", ["x", "y"]), j: ("pick-up", ["y"])}})
        J.append({"name": f"pairdown_table_{i}{j}", "params": ["x", "y"], "pre": [(h("holding", i), "x"), (h("holding", j), "y")],
                  "add": [("on", "x", "y"), ("ontable", "y"), ("clear", "x")] + hands_free, "del": [(h("holding", i), "x"), (h("holding", j), "y")],
                  "comps": {i: ("stack", ["x", "y"]), j: ("put-down", ["y"])}})
    return J


JOINT = _build_joint()
SPEC = {j["name"]: j for j in JOINT}


# ---------------------------------------------------------------- states ---------------------------------------------
def state_from(towers, hands=None):
    """Facts for columns listed top to bottom; hands = {1: block or None, 2: ...}."""
    hands = hands or {}
    f = set()
    for t in towers:
        f.add(("clear", t[0])); f.add(("ontable", t[-1]))
        f |= {("on", a, b) for a, b in zip(t, t[1:])}
    for arm in (1, 2):
        f.add((f"handempty_{arm}",)) if not hands.get(arm) else f.add((f"holding_{arm}", hands[arm]))
    return f


def world_of(state):
    """Columns (top first, sorted by bottom block) and what each hand holds."""
    cols = []
    for bottom in sorted(f[1] for f in state if f[0] == "ontable"):
        col = [bottom]
        while True:
            above = [f[1] for f in state if f[0] == "on" and f[2] == col[-1]]
            if not above:
                break
            col.append(above[0])
        cols.append(col[::-1])
    hands = {arm: next((f[1] for f in state if f[0] == f"holding_{arm}"), None) for arm in (1, 2)}
    return {"towers": cols, "hands": hands}


def _bind(facts, b):
    return {tuple([f[0]] + [b.get(a, a) for a in f[1:]]) for f in facts if f[0] != "neq"}


def apply_joint(state, name, args):
    spec = SPEC[name]
    b = dict(zip(spec["params"], args))
    missing = _bind(spec["pre"], b) - state
    if missing:
        raise ValueError(f"{name} {args} is not applicable: needs {sorted(missing)}")
    return (state - _bind(spec["del"], b)) | _bind(spec["add"], b)


def components(name, args):
    """What each arm does in a joint step: {1: 'unstack F W' or None, 2: ...}."""
    spec = SPEC[name]
    b = dict(zip(spec["params"], args))
    return {arm: (" ".join([spec["comps"][arm][0]] + [b[v] for v in spec["comps"][arm][1]]) if arm in spec["comps"] else None) for arm in (1, 2)}


# ---------------------------------------------------------------- PDDL -----------------------------------------------
def _pf(f):
    if f[0] == "neq":
        return f"(not (= ?{f[1]} ?{f[2]}))"
    return "(" + " ".join([f[0]] + ["?" + a for a in f[1:]]) + ")"


def _key(op):
    return op.replace("-", "")


def domain_pddl(forced_len=None, locked_arm=2, coupling=True, tidy=False):
    acts = []

    def emit(name, params, pre, add, dele, cost=None):
        eff = " ".join([_pf(f) for f in add] + ["(not " + _pf(f) + ")" for f in dele] + ([f"(increase (total-cost) {cost})"] if tidy else []))
        acts.append(f"  (:action {name}\n    :parameters ({' '.join('?' + p for p in params)})\n"
                    f"    :precondition (and {' '.join(_pf(f) if f[0] != 'raw' else f[1] for f in pre)})\n    :effect (and {eff}))")

    for j in (JOINT if coupling else [x for x in JOINT if x['name'].startswith(('one_', 'par_'))]):   # no coupling: no handovers or pair lifts
        cost = 100 + (1 if 2 in j["comps"] else 0)
        if forced_len is None:
            emit(j["name"], j["params"], j["pre"], j["add"], j["del"], cost)
            continue
        c2 = j["comps"].get(locked_arm)
        if c2 is None:
            emit(j["name"] + "_wait", j["params"] + ["c", "d"], j["pre"] + [("cur", "c"), ("nxt", "c", "d"), ("r2_noop", "c")],
                 j["add"] + [("cur", "d")], j["del"] + [("cur", "c")], cost)
            emit(j["name"] + "_after", j["params"], j["pre"] + [("raw", f"(cur s{forced_len})")], j["add"], j["del"], cost)
        else:
            op, vs = c2
            emit(j["name"], j["params"] + ["c", "d"], j["pre"] + [("cur", "c"), ("nxt", "c", "d"), (f"r2_{_key(op)}", "c", *vs)],
                 j["add"] + [("cur", "d")], j["del"] + [("cur", "c")], cost)
    preds = ["(on ?a ?b)", "(ontable ?a)", "(clear ?a)", "(handempty_1)", "(handempty_2)", "(holding_1 ?a)", "(holding_2 ?a)"]
    consts = " ".join(BLOCKS)
    if forced_len is not None:
        preds += ["(cur ?a)", "(nxt ?a ?b)", "(r2_noop ?a)", "(r2_pickup ?a ?b)", "(r2_putdown ?a ?b)", "(r2_stack ?a ?b ?c)", "(r2_unstack ?a ?b ?c)"]
        consts += " " + " ".join(f"s{i}" for i in range(forced_len + 1))
    extra = "\n  (:functions (total-cost) - number)" if tidy else ""
    return (f"(define (domain two-arms)\n  (:requirements :strips :equality :negative-preconditions{' :action-costs' if tidy else ''})\n  (:constants {consts})\n"
            f"  (:predicates {' '.join(preds)}){extra}\n" + "\n".join(acts) + "\n)\n")


def problem_pddl(state, goal, forced=None, tidy=False):
    init = [f"({' '.join(f)})" for f in sorted(state)]
    if forced is not None:
        n = len(forced)
        init.append("(cur s0)")
        for i, a in enumerate(forced):
            init.append(f"(nxt s{i} s{i + 1})")
            if a is None:
                init.append(f"(r2_noop s{i})")
            else:
                op, *args = a.split()
                init.append(f"(r2_{_key(op)} s{i} {' '.join(args)})")
    goal_s = " ".join(f"({' '.join(g)})" for g in goal)
    if tidy:
        init.append("(= (total-cost) 0)")
    metric = "\n  (:metric minimize (total-cost))" if tidy else ""
    return f"(define (problem p)\n  (:domain two-arms)\n  (:init {' '.join(init)})\n  (:goal (and {goal_s})){metric})\n"


def goal_facts(conds):
    """'on(A,S)' -> ('on','A','S'); 'ontable(R)' -> ('ontable','R')."""
    out = []
    for c in conds:
        name, args = c[:-1].split("(")
        out.append(tuple([name] + args.split(",")))
    return out


# ---------------------------------------------------------------- solving --------------------------------------------
def solve(towers, goal_conds, forced_arm2=None, hands=None, time_limit=600, search="astar(lmcut())", forced_arm1=None, coupling=True, tidy=False):
    """Optimal joint plan (A* with LM-cut by default; pass another `search` string for a fast, non-optimal plan). Returns {"cost", "steps": [{name, args, comps, state}], "states": [...]}."""
    OUT.mkdir(exist_ok=True)
    tag = f"two_{os.getpid()}"
    state0 = state_from(towers, hands)
    locked_arm, forced = (1, forced_arm1) if forced_arm1 is not None else (2, forced_arm2)
    forced_len = None if forced is None else len(forced)
    dom, prob = domain_pddl(forced_len, locked_arm, coupling, tidy), problem_pddl(state0, goal_facts(goal_conds), forced, tidy)
    files = [OUT / f"{tag}_domain.pddl", OUT / f"{tag}_problem.pddl", OUT / f"{tag}.sas", OUT / f"{tag}_plan.txt"]
    files[0].write_text(dom); files[1].write_text(prob); files[3].unlink(missing_ok=True)
    run = subprocess.run([sys.executable, str(FD), "--plan-file", str(files[3]), "--sas-file", str(files[2]), "--search-time-limit", f"{time_limit}s",
                          str(files[0]), str(files[1]), "--search", search], capture_output=True, text=True)
    if not files[3].exists():
        for f in files:
            f.unlink(missing_ok=True)
        text = (run.stdout + run.stderr).lower()
        # "provably unsolvable" is a proof that no plan exists (infinite cost); a time limit only means "not found yet"
        reason = "unsolvable" if "provably unsolvable" in text or "no solution" in text else ("time limit" if "time limit" in text or "timeout" in text else "error")
        return {"cost": None, "reason": reason}
    names = {}
    for j in JOINT:
        for suffix in ("", "_wait", "_after"):
            names[(j["name"] + suffix).lower()] = j
    steps, state = [], state0
    for ln in files[3].read_text().splitlines():
        if not ln.startswith("("):
            continue
        parts = ln.strip("() ").split()
        j = names[parts[0]]
        args = [a.upper() for a in parts[1:1 + len(j["params"])]]
        state = apply_joint(state, j["name"], args)
        steps.append({"name": j["name"], "args": args, "comps": components(j["name"], args), "world": world_of(state)})
    for f in files:
        f.unlink(missing_ok=True)
    return {"cost": len(steps), "steps": steps, "start": world_of(state0)}


if __name__ == "__main__":                      # quick self-test against numbers we already trust
    from time import time
    towers = json.loads((ROOT / "data" / "blockworld.json").read_text())["towers"]
    def goal(word): return [f"on({a},{b})" for a, b in zip(word, word[1:])] + [f"ontable({word[-1]})"]
    for word, expected in (("HER", 2), ("OTHER", 6), ("HATER", 6)):
        t0 = time(); r = solve(towers, goal(word))
        print(f"two arms free  {word:6} cost {r['cost']}  (paper {expected})  {time() - t0:4.0f} s")
    for word, expected in (("HER", 6), ("OTHER", 16)):
        t0 = time(); r = solve(towers, goal(word), forced_arm2=[])
        print(f"arm 2 forced to wait (= one arm) {word:6} cost {r['cost']}  (single-arm Fig. 1: {expected})  {time() - t0:4.0f} s")

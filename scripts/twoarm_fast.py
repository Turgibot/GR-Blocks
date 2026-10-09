"""Faster encoding of the same two-arm problem (same rules as twoarm.py, about 12 times fewer ground operators).

twoarm.py writes "arm 1 and arm 2 act at once on different blocks" as one operator per pair of actions (about 83 000 of them),
and LM-cut is slow with that many. Here one time step is split into phases instead:
  phase 1: arm 1 acts (or waits) - this costs 1 and marks the blocks it touched      (or a handover / pair lift: one operator, cost 1)
  phase 2: arm 2 acts (or waits) on blocks that arm 1 did not touch - cost 0
  phase 3: the marks are removed, back to phase 1 - cost 0
Arm 2's action may not touch arm 1's blocks, which is exactly the "different blocks" rule, and facts of different blocks do
not interact, so a step has the same meaning as before. The plan is rebuilt as joint steps and replayed with twoarm.apply_joint
to check it.

    solve_fast(towers, goal_conds, hands=None, time_limit=600, search="astar(lmcut())")  ->  same result format as twoarm.solve
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import twoarm
from twoarm import OPS, BLOCKS, FD, OUT, JOINT, _single, _pf, apply_joint, components, goal_facts, state_from, world_of


def _emit(acts, name, params, pre, add, dele, cost):
    eff = " ".join([_pf(f) for f in add] + ["(not " + _pf(f) + ")" for f in dele] + [f"(increase (total-cost) {cost})"])
    acts.append(f"  (:action {name}\n    :parameters ({' '.join('?' + p for p in params)})\n"
                f"    :precondition (and {' '.join(_pf(f) for f in pre)})\n    :effect (and {eff}))")


def domain_pddl():
    acts = []
    for name in OPS:
        a1, a2 = _single(name, 1), _single(name, 2)
        ps = a1["params"]
        _emit(acts, f"a1_{name}", ps, a1["pre"] + [("p1",)], a1["add"] + [("p2",)] + [("used", p) for p in ps], a1["del"] + [("p1",)], 1)
        _emit(acts, f"a2_{name}", ps, a2["pre"] + [("p2",)] + [("not_used", p) for p in ps], a2["add"] + [("p3",)], a2["del"] + [("p2",)], 0)
    _emit(acts, "noop1", [], [("p1",)], [("p2",)], [("p1",)], 1)
    _emit(acts, "noop2", [], [("p2",)], [("p3",)], [("p2",)], 0)
    _emit(acts, "clear_mark", ["b"], [("p3",), ("used", "b")], [], [("used", "b")], 0)
    acts.append("  (:action finish\n    :parameters ()\n    :precondition (and (p3) " + " ".join(f"(not (used {b}))" for b in BLOCKS) +
                ")\n    :effect (and (p1) (not (p3)) (increase (total-cost) 0)))")
    for j in JOINT:                                            # handovers and pair lifts: one operator, a whole step
        if j["name"].startswith(("one_", "par_")):
            continue
        _emit(acts, "cp_" + j["name"], j["params"], j["pre"] + [("p1",)], j["add"], j["del"], 1)
    preds = ["(on ?a ?b)", "(ontable ?a)", "(clear ?a)", "(handempty_1)", "(handempty_2)", "(holding_1 ?a)", "(holding_2 ?a)",
             "(p1)", "(p2)", "(p3)", "(used ?a)"]
    return (f"(define (domain two-arms-fast)\n  (:requirements :strips :negative-preconditions :action-costs)\n  (:constants {' '.join(BLOCKS)})\n"
            f"  (:predicates {' '.join(preds)})\n  (:functions (total-cost) - number)\n" + "\n".join(acts) + "\n)\n")


def _fix(dom):
    """_pf wrote '(not_used ?x)'; turn it into '(not (used ?x))'."""
    import re
    return re.sub(r"\(not_used (\?\w+)\)", r"(not (used \1))", dom)


def problem_pddl(state, goal):
    init = [f"({' '.join(f)})" for f in sorted(state)] + ["(p1)", "(= (total-cost) 0)"]
    goal_s = " ".join(f"({' '.join(g)})" for g in goal) + " (p1)"
    return f"(define (problem p)\n  (:domain two-arms-fast)\n  (:init {' '.join(init)})\n  (:goal (and {goal_s}))\n  (:metric minimize (total-cost)))\n"


def solve_fast(towers, goal_conds, hands=None, time_limit=600, search="astar(lmcut())", tag=None):
    OUT.mkdir(exist_ok=True)
    tag = tag or f"fast_{os.getpid()}"
    state0 = state_from(towers, hands)
    files = [OUT / f"{tag}_domain.pddl", OUT / f"{tag}_problem.pddl", OUT / f"{tag}.sas", OUT / f"{tag}_plan.txt"]
    files[0].write_text(_fix(domain_pddl())); files[1].write_text(problem_pddl(state0, goal_facts(goal_conds))); files[3].unlink(missing_ok=True)
    run = subprocess.run([sys.executable, str(FD), "--plan-file", str(files[3]), "--sas-file", str(files[2]), "--search-time-limit", f"{time_limit}s",
                          str(files[0]), str(files[1]), "--search", search], capture_output=True, text=True)
    if not files[3].exists():
        text = (run.stdout + run.stderr).lower()
        for f in files:
            f.unlink(missing_ok=True)
        return {"cost": None, "reason": "unsolvable" if "provably unsolvable" in text else ("time limit" if "time limit" in text else "error")}
    param_names = {n: o["params"] for n, o in OPS.items()}
    coupled = {("cp_" + j["name"]).lower(): j for j in JOINT if not j["name"].startswith(("one_", "par_"))}
    steps, cur, state = [], None, state0
    ops = [ln.strip("() \n").split() for ln in files[3].read_text().splitlines() if ln.startswith("(")]
    pending = None                                                      # arm 1's action of the step being built: (name, args) or "noop"
    for op in ops:
        head, args = op[0], [a.upper() for a in op[1:]]
        if head in coupled:
            j = coupled[head]
            state = apply_joint(state, j["name"], args)
            steps.append({"name": j["name"], "args": args, "comps": components(j["name"], args), "world": world_of(state)})
        elif head == "noop1":
            pending = "noop"
        elif head.startswith("a1_"):
            pending = (head[3:], args)
        elif head.startswith(("a2_", "noop2")):
            second = None if head == "noop2" else (head[3:], args)
            first = None if pending == "noop" else pending
            pending = None
            if first is None and second is None:
                continue                                                # both wait: a wasted step (an optimal plan has none)
            if first and second:
                (n1, a1), (n2, a2) = first, second
                jn, jargs = f"par_{n1}_{n2}", a1 + a2
            elif first:
                jn, jargs = f"one_{first[0]}_arm1", first[1]
            else:
                jn, jargs = f"one_{second[0]}_arm2", second[1]
            state = apply_joint(state, jn, jargs)                       # raises if the rebuilt step is not applicable: a check on the encoding
            steps.append({"name": jn, "args": jargs, "comps": components(jn, jargs), "world": world_of(state)})
    for f in files:
        f.unlink(missing_ok=True)
    return {"cost": len(steps), "steps": steps, "start": world_of(state0)}


if __name__ == "__main__":
    import json
    import time
    word = sys.argv[1]
    towers = json.loads((ROOT / "data" / "blockworld.json").read_text())["towers"]
    goal = [f"on({a},{b})" for a, b in zip(word, word[1:])] + [f"ontable({word[-1]})"]
    t0 = time.time()
    r = solve_fast(towers, goal, time_limit=int(sys.argv[2]) if len(sys.argv) > 2 else 600)
    print(f"{word}: cost {r['cost']} {r.get('reason', '')} ({time.time() - t0:.0f} s)")
    for i, s in enumerate(r.get("steps", []), 1):
        print(f"  {i}: {s['comps']}")

"""Compile observed actions into a planning problem (Part 5 of the reading companion), then solve
the two versions of the goal:   G+O (reach G and perform all observations, in order)
                                G+notO (reach G without performing all of them).

usage: python3 scripts/compile_observations.py [WORD] ["action a b, action c, ..."]
   e.g. python3 scripts/compile_observations.py HER "unstack H T, put-down H"
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
world = json.loads((ROOT / "data" / "blockworld.json").read_text())
operators = json.loads((ROOT / "data" / "actions.json").read_text())["operators"]
towers = world["towers"]
blocks = sorted(b for t in towers for b in t)

word = sys.argv[1] if len(sys.argv) > 1 else "HER"
obs_text = sys.argv[2] if len(sys.argv) > 2 else "unstack H T, put-down H"
observations = [tuple(part.split()) for part in obs_text.split(",")]
n = len(observations)


def fmt(fact):
    return "(" + " ".join(fact) + ")"


def ground_actions():
    """Every operator with its letters filled in, e.g. ('unstack','H','T')."""
    result = []
    for name, op in operators.items():
        for args in itertools.permutations(blocks, len(op["params"])):
            bind = dict(zip(op["params"], args))
            sub = lambda facts: [tuple([f[0]] + [bind.get(a, a) for a in f[1:]]) for f in facts]
            result.append({"key": (name,) + args, "pre": sub(op["pre"]), "add": sub(op["add"]), "del": sub(op["del"])})
    return result


def compile_problem(allow_complete):
    """Return the list of (name, pre, add, del) actions with the progress counter f0..fn added."""
    actions = []
    for ga in ground_actions():
        idx = [i + 1 for i, o in enumerate(observations) if o == ga["key"]]
        base = "_".join(ga["key"])
        if not idx:
            actions.append((base, ga["pre"], ga["add"], ga["del"]))
            continue
        for k in range(n + 1):                      # one copy of this action per counter value
            advances = (k + 1) in idx
            if advances and not allow_complete and k + 1 == n:
                continue                            # G+notO: finishing the observations is not allowed
            add, dele = list(ga["add"]), list(ga["del"])
            if advances:
                add.append((f"f{k + 1}",)); dele.append((f"f{k}",))
            actions.append((f"{base}_at{k}", ga["pre"] + [(f"f{k}",)], add, dele))
    return actions


def write_pddl(actions, allow_complete):
    preds = {(f[0], len(f) - 1) for _, pre, add, dele in actions for f in pre + add + dele}
    preds |= {(f"f{k}", 0) for k in range(n + 1)}
    dom = ["(define (domain blockworld-obs)", "  (:requirements :strips)", f"  (:constants {' '.join(blocks)})", "  (:predicates"]
    dom += [f"    ({p} {' '.join('?a' + str(i) for i in range(a))})" for p, a in sorted(preds)] + ["  )"]
    for name, pre, add, dele in actions:
        dom += [f"  (:action {name}", "    :parameters ()", f"    :precondition (and {' '.join(map(fmt, pre))})",
                f"    :effect (and {' '.join(map(fmt, add))} {' '.join('(not ' + fmt(f) + ')' for f in dele)}))"]
    dom.append(")")
    init = ["(handempty)", "(f0)"]
    for t in towers:
        init += [f"(clear {t[0]})", f"(ontable {t[-1]})"] + [f"(on {a} {b})" for a, b in zip(t, t[1:])]
    goal = [f"(on {a} {b})" for a, b in zip(word, word[1:])] + [f"(ontable {word[-1]})"]
    if allow_complete:
        goal.append(f"(f{n})")
    prob = ["(define (problem p)", "  (:domain blockworld-obs)", "  (:init " + " ".join(init) + ")",
            "  (:goal (and " + " ".join(goal) + ")))"]
    return "\n".join(dom) + "\n", "\n".join(prob) + "\n"


def solve(tag, allow_complete):
    tag = f"{tag}_{os.getpid()}"                   # per-process file names, so several runs can go in parallel
    actions = compile_problem(allow_complete)
    dom, prob = write_pddl(actions, allow_complete)
    OUT.mkdir(exist_ok=True)
    (OUT / f"obs_domain_{tag}.pddl").write_text(dom)
    (OUT / f"obs_problem_{tag}.pddl").write_text(prob)
    plan_file = OUT / f"obs_plan_{tag}.txt"
    plan_file.unlink(missing_ok=True)
    subprocess.run(["python3", str(FD), "--plan-file", str(plan_file), "--sas-file", str(OUT / f"obs_{tag}.sas"),
                    str(OUT / f"obs_domain_{tag}.pddl"), str(OUT / f"obs_problem_{tag}.pddl"),
                    "--search", "astar(lmcut())"], capture_output=True, text=True)
    files = [OUT / f"obs_domain_{tag}.pddl", OUT / f"obs_problem_{tag}.pddl", OUT / f"obs_{tag}.sas"]
    if not plan_file.exists():
        for f in files:
            f.unlink(missing_ok=True)
        return None, actions
    names = {a[0].lower(): a[0] for a in actions}
    steps = [names[ln.strip("() \n")] for ln in plan_file.read_text().splitlines() if ln.startswith("(")]
    for f in files + [plan_file]:
        f.unlink(missing_ok=True)
    return [s.split("_at")[0].replace("_", " ") for s in steps], actions


print(f"goal word: {word}")
print(f"observations O (n = {n}): " + ", ".join(" ".join(o) for o in observations))
print("\n--- NEW FACTS: a progress counter, exactly one of these is true at a time ---")
print("  " + ", ".join(f"f{k}" for k in range(n + 1)) + f"      (f0 is true at the start; f{n} means 'all {n} observations performed')")

print("\n--- COPIES OF THE OBSERVED ACTIONS (the compiler's changes) ---")
for name, pre, add, dele in compile_problem(True):
    if "_at" in name:
        k = int(name.rsplit("_at", 1)[1])
        moves = f"ADVANCES: removes f{k}, adds f{k + 1}" if any(a[0] == f"f{k + 1}" for a in add) else "plain: counter unchanged"
        print(f"  {name:22} needs f{k:<2} -> {moves}")
print("\nExample, as PDDL (the first observed action when the counter is at f0):")
for name, pre, add, dele in compile_problem(True):
    if name.endswith("_at0") and any(a[0] == "f1" for a in add):
        print(f"  (:action {name}\n    :precondition (and {' '.join(map(fmt, pre))})\n"
              f"    :effect (and {' '.join(map(fmt, add))} {' '.join('(not ' + fmt(f) + ')' for f in dele)}))")
        break

print("\n--- TWO GOALS ---")
print(f"  G+O    : the goal conditions of {word}  AND  f{n}   (all observations performed, in order)")
print(f"  G+notO : the goal conditions of {word}, but the step that would reach f{n} is removed")

plan_o, _ = solve("GO", True)
plan_not, _ = solve("GnotO", False)
for label, plan in (("G+O", plan_o), ("G+notO", plan_not)):
    print(f"\n=== {label}: " + (f"cost {len(plan)}" if plan else "no plan") + " ===")
    for i, s in enumerate(plan or [], 1):
        print(f"  {i:2}. {s}")
if plan_o and plan_not:
    print(f"\ncost with O = {len(plan_o)}, cost without O = {len(plan_not)}, gap = {len(plan_not) - len(plan_o)}")

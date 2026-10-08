"""Write PDDL for one goal word, run Fast Downward (A* with LM-cut), and show the plan.

usage: python3 scripts/plan_word.py [WORD]        (default HER)
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
FD = ROOT / "third_party" / "downward" / "fast-downward.py"
world = json.loads((ROOT / "data" / "blockworld.json").read_text())
operators = json.loads((ROOT / "data" / "actions.json").read_text())["operators"]
word = sys.argv[1] if len(sys.argv) > 1 else "HER"
towers = world["towers"]
blocks = sorted(b for t in towers for b in t)


def atom(fact, bind=None):
    bind = bind or {}
    return "(" + " ".join([fact[0]] + [("?" + a if a in bind else a) for a in fact[1:]]) + ")"


def domain_pddl():
    preds = {(f[0], len(f) - 1) for op in operators.values() for k in ("pre", "add", "del") for f in op[k]}
    lines = ["(define (domain blockworld)", "  (:requirements :strips)", "  (:predicates"]
    lines += [f"    ({n} {' '.join('?a' + str(i) for i in range(k))})" for n, k in sorted(preds)]
    lines.append("  )")
    for name, op in operators.items():
        bind = set(op["params"])
        params = " ".join("?" + p for p in op["params"])
        pre = " ".join(atom(f, bind) for f in op["pre"])
        eff = " ".join([atom(f, bind) for f in op["add"]] + ["(not " + atom(f, bind) + ")" for f in op["del"]])
        lines += [f"  (:action {name}", f"    :parameters ({params})",
                  f"    :precondition (and {pre})", f"    :effect (and {eff}))"]
    return "\n".join(lines + [")"]) + "\n"


def problem_pddl(goal_word):
    init = ["(handempty)"]
    for t in towers:
        init.append(f"(clear {t[0]})")
        init.append(f"(ontable {t[-1]})")
        init += [f"(on {a} {b})" for a, b in zip(t, t[1:])]
    goal = [f"(on {a} {b})" for a, b in zip(goal_word, goal_word[1:])] + [f"(ontable {goal_word[-1]})"]
    return (f"(define (problem spell-{goal_word.lower()})\n  (:domain blockworld)\n"
            f"  (:objects {' '.join(blocks)})\n  (:init\n    " + "\n    ".join(init) + "\n  )\n"
            f"  (:goal (and {' '.join(goal)})))\n")


OUT.mkdir(exist_ok=True)
(OUT / "domain.pddl").write_text(domain_pddl())
(OUT / f"problem_{word}.pddl").write_text(problem_pddl(word))
print("=== domain.pddl ===\n" + domain_pddl())
print(f"=== problem_{word}.pddl ===\n" + problem_pddl(word))

plan_file = OUT / f"plan_{word}.txt"
plan_file.unlink(missing_ok=True)
run = subprocess.run(
    ["python3", str(FD), "--plan-file", str(plan_file), "--sas-file", str(OUT / "output.sas"),
     str(OUT / "domain.pddl"), str(OUT / f"problem_{word}.pddl"), "--search", "astar(lmcut())"],
    capture_output=True, text=True)
if not plan_file.exists():
    sys.exit("No plan found.\n" + run.stdout[-1500:] + run.stderr[-500:])

steps = [ln.strip("() \n") for ln in plan_file.read_text().splitlines() if ln.startswith("(")]
print(f"=== plan found by Fast Downward for {word} ===")
for i, s in enumerate(steps, 1):
    print(f"  {i:2}. {s}")
paper = world["goals"][word]["cost_one_agent"]
print(f"\nplan cost = {len(steps)}   paper's Fig. 1 value for {word} = {paper}   match: {len(steps) == paper}")

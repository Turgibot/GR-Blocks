"""Two arms working together (Part 22's rules): generate PDDL, plan with Fast Downward, compare with Fig. 1.

usage: python3 scripts/plan_two_arms.py WORD [table]       WORD = HER ... WATER, or ALL
       'table' also allows the stacked pair at the bottom of a tower (see RULES below)

Each time step = one joint action, cost 1. Rules (my reading of the paper's p. 6, see Step 10a):
  one arm acts, the other waits | two arms act on different blocks | handover |
  stacked-pair pick-up | stacked-pair put-down | everything else sharing a block is omitted.
"""
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
FD = ROOT / "third_party" / "downward" / "fast-downward.py"
world = json.loads((ROOT / "data" / "blockworld.json").read_text())
operators = json.loads((ROOT / "data" / "actions.json").read_text())["operators"]
towers, goals = world["towers"], world["goals"]
blocks = sorted(b for t in towers for b in t)
use_table = "table" in sys.argv[2:]


def fact(f, arm=None, suffix=""):
    pred = f[0] + (f"_{arm}" if arm and f[0] in ("handempty", "holding") else "")
    return "(" + " ".join([pred] + ["?" + a + suffix for a in f[1:]]) + ")"


def op(name, arm, suffix=""):
    o = operators[name]
    return {"params": [p + suffix for p in o["params"]],
            "pre": [fact(f, arm, suffix) for f in o["pre"]],
            "add": [fact(f, arm, suffix) for f in o["add"]],
            "del": [fact(f, arm, suffix) for f in o["del"]]}


def action(name, params, pre, add, dele):
    eff = " ".join(add + ["(not " + d + ")" for d in dele])
    return (f"  (:action {name}\n    :parameters ({' '.join('?' + p for p in params)})\n"
            f"    :precondition (and {' '.join(pre)})\n    :effect (and {eff}))")


def domain_pddl():
    acts = []
    for arm in (1, 2):                                   # one arm acts, the other waits
        for name in operators:
            o = op(name, arm)
            acts.append(action(f"one_{name}_arm{arm}", o["params"], o["pre"], o["add"], o["del"]))
    for n1, n2 in itertools.product(operators, repeat=2):  # two arms, different blocks
        a, b = op(n1, 1, "1"), op(n2, 2, "2")
        distinct = [f"(not (= ?{p} ?{q}))" for p in a["params"] for q in b["params"]]
        acts.append(action(f"par_{n1}_{n2}", a["params"] + b["params"], a["pre"] + b["pre"] + distinct,
                           a["add"] + b["add"], a["del"] + b["del"]))
    for i, j in ((1, 2), (2, 1)):
        h = {"x": "?x"}
        acts.append(action(f"handover_{i}to{j}", ["x"], [f"(holding_{i} ?x)", f"(handempty_{j})"],
                           [f"(holding_{j} ?x)", f"(handempty_{i})"], [f"(holding_{i} ?x)", f"(handempty_{j})"]))
        acts.append(action(f"pairup_{i}{j}", ["x", "y", "z"],
                           ["(on ?x ?y)", "(on ?y ?z)", "(clear ?x)", f"(handempty_{i})", f"(handempty_{j})"],
                           [f"(holding_{i} ?x)", f"(holding_{j} ?y)", "(clear ?z)"],
                           ["(on ?x ?y)", "(on ?y ?z)", "(clear ?x)", f"(handempty_{i})", f"(handempty_{j})"]))
        acts.append(action(f"pairdown_{i}{j}", ["x", "y", "z"],
                           [f"(holding_{i} ?x)", f"(holding_{j} ?y)", "(clear ?z)"],
                           ["(on ?x ?y)", "(on ?y ?z)", "(clear ?x)", f"(handempty_{i})", f"(handempty_{j})"],
                           [f"(holding_{i} ?x)", f"(holding_{j} ?y)", "(clear ?z)"]))
        if use_table:                                    # pair whose lower block sits on the table
            acts.append(action(f"pairup_table_{i}{j}", ["x", "y"],
                               ["(on ?x ?y)", "(ontable ?y)", "(clear ?x)", f"(handempty_{i})", f"(handempty_{j})"],
                               [f"(holding_{i} ?x)", f"(holding_{j} ?y)"],
                               ["(on ?x ?y)", "(ontable ?y)", "(clear ?x)", f"(handempty_{i})", f"(handempty_{j})"]))
            acts.append(action(f"pairdown_table_{i}{j}", ["x", "y"],
                               [f"(holding_{i} ?x)", f"(holding_{j} ?y)"],
                               ["(on ?x ?y)", "(ontable ?y)", "(clear ?x)", f"(handempty_{i})", f"(handempty_{j})"],
                               [f"(holding_{i} ?x)", f"(holding_{j} ?y)"]))
    preds = ["(on ?a ?b)", "(ontable ?a)", "(clear ?a)", "(handempty_1)", "(handempty_2)", "(holding_1 ?a)", "(holding_2 ?a)"]
    return ("(define (domain blockworld-two-arms)\n  (:requirements :strips :equality :negative-preconditions)\n"
            "  (:predicates " + " ".join(preds) + ")\n" + "\n".join(acts) + "\n)\n")


def problem_pddl(word):
    init = ["(handempty_1)", "(handempty_2)"]
    for t in towers:
        init += [f"(clear {t[0]})", f"(ontable {t[-1]})"] + [f"(on {a} {b})" for a, b in zip(t, t[1:])]
    goal = [f"(on {a} {b})" for a, b in zip(word, word[1:])] + [f"(ontable {word[-1]})"]
    return (f"(define (problem two-arms-{word.lower()})\n  (:domain blockworld-two-arms)\n  (:objects {' '.join(blocks)})\n"
            f"  (:init {' '.join(init)})\n  (:goal (and {' '.join(goal)})))\n")


def pretty(line):
    parts = line.strip("() \n").split()
    name, args = parts[0], [a.upper() for a in parts[1:]]
    if name.startswith("one_"):
        _, op_name, arm = name.split("_", 2)[0], name.split("_")[1], name[-1]
        return f"arm {arm}: {op_name}({','.join(args)})   [other arm waits]"
    if name.startswith("par_"):
        _, o1, o2 = name.split("_")
        n1 = len(operators[o1]["params"])
        return f"arm 1: {o1}({','.join(args[:n1])})  |  arm 2: {o2}({','.join(args[n1:])})"
    if name.startswith("handover"):
        return f"HANDOVER of {args[0]}: arm {name[-3]} puts it down as arm {name[-1]} picks it up"
    kind = "pair PICK-UP" if name.startswith("pairup") else "pair PUT-DOWN"
    arms = name[-2:]
    return f"{kind}: arm {arms[0]} handles {args[0]}, arm {arms[1]} handles {args[1]} (stacked together)"


def solve(word, show=True):
    OUT.mkdir(exist_ok=True)
    (OUT / "two_arm_domain.pddl").write_text(domain_pddl())
    (OUT / f"two_arm_problem_{word}.pddl").write_text(problem_pddl(word))
    plan = OUT / f"two_arm_plan_{word}.txt"
    plan.unlink(missing_ok=True)
    subprocess.run(["python3", str(FD), "--plan-file", str(plan), "--sas-file", str(OUT / f"two_arm_{word}.sas"),
                    "--search-time-limit", "600s",   # driver options must come before the PDDL files
                    str(OUT / "two_arm_domain.pddl"), str(OUT / f"two_arm_problem_{word}.pddl"),
                    "--search", "astar(lmcut())"], capture_output=True, text=True)
    if not plan.exists():
        return None                                      # no plan found within the 10-minute search limit
    lines = [ln for ln in plan.read_text().splitlines() if ln.startswith("(")]
    if show:
        for k, ln in enumerate(lines, 1):
            print(f"  step {k}: {pretty(ln)}")
    return len(lines)


word = sys.argv[1] if len(sys.argv) > 1 else "HER"
if word != "ALL":
    print(f"two arms, goal {word} (table pairs {'on' if use_table else 'off'})")
    c = solve(word)
    print(f"\ncost = {c}   paper's Fig. 1 value = {goals[word]['cost_two_agents']}   match: {c == goals[word]['cost_two_agents']}")
else:
    print(f"two arms, all words (table pairs {'on' if use_table else 'off'})\n{'word':8}{'ours':>6}{'paper':>7}{'match':>7}")
    ok = True
    for w, g in goals.items():
        t0 = time.time()
        c = solve(w, show=False)
        ok &= c == g["cost_two_agents"]
        print(f"{w:8}{str(c):>6}{g['cost_two_agents']:>7}{'yes' if c == g['cost_two_agents'] else 'NO':>7}   {time.time() - t0:5.0f} s", flush=True)
    print("\nall 12 match the paper:", ok)

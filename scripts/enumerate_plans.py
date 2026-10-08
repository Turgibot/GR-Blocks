"""Collect many different optimal plans for one goal word, by shuffling the order of the planner's input.

usage: python3 scripts/enumerate_plans.py [WORD] [runs]       (default MASTER, 400)  ->  out/plans_<WORD>.json
Fast Downward returns the same plan however its input is ordered, so instead every action gets a tiny random extra cost:
only plans with the fewest steps win, and among them the one with the smallest random total, which differs per seed.
"""
import json
import random
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FD = ROOT / "third_party" / "downward" / "fast-downward.py"
world = json.loads((ROOT / "data" / "blockworld.json").read_text())
OPS = json.loads((ROOT / "data" / "actions.json").read_text())["operators"]
towers, blocks = world["towers"], sorted(b for t in world["towers"] for b in t)
word = sys.argv[1] if len(sys.argv) > 1 else "MASTER"
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 400


def ground_actions():
    out = []
    import itertools
    for name, o in OPS.items():
        for args in itertools.permutations(blocks, len(o["params"])):
            bind = dict(zip(o["params"], args))
            sub = lambda fs: [tuple([f[0]] + [bind.get(a, a) for a in f[1:]]) for f in fs]
            out.append((name + "_" + "_".join(args), sub(o["pre"]), sub(o["add"]), sub(o["del"])))
    return out


GROUND = ground_actions()


def pddl(rng):
    """Ground domain in which every action costs 1000 + a random 0..20: only shortest plans win, a random one of them."""
    fa = lambda f: "(" + " ".join(f) + ")"
    acts = []
    for name, pre, add, dele in GROUND:
        eff = [fa(f) for f in add] + ["(not " + fa(f) + ")" for f in dele] + [f"(increase (total-cost) {1000 + rng.randint(0, 20)})"]
        acts.append(f"(:action {name} :parameters () :precondition (and {' '.join(fa(f) for f in pre)}) :effect (and {' '.join(eff)}))")
    consts = " ".join(blocks)
    domain = (f"(define (domain bw) (:requirements :strips :action-costs) (:constants {consts}) "
              "(:predicates (on ?a ?b) (ontable ?a) (clear ?a) (holding ?a) (handempty)) (:functions (total-cost) - number) " + " ".join(acts) + ")")
    init = ["(handempty)", "(= (total-cost) 0)"]
    for t in towers:
        init += [f"(clear {t[0]})", f"(ontable {t[-1]})"] + [f"(on {a} {b})" for a, b in zip(t, t[1:])]
    goal = [f"(on {a} {b})" for a, b in zip(word, word[1:])] + [f"(ontable {word[-1]})"]
    problem = f"(define (problem p) (:domain bw) (:init {' '.join(init)}) (:goal (and {' '.join(goal)})) (:metric minimize (total-cost)))"
    return domain, problem


def one(seed):
    rng = random.Random(seed)
    dom, prob = pddl(rng)
    with tempfile.TemporaryDirectory(prefix="enum_") as d:
        Path(d, "d.pddl").write_text(dom)
        Path(d, "p.pddl").write_text(prob)
        subprocess.run([sys.executable, str(FD), "--plan-file", str(Path(d, "plan")), "--sas-file", str(Path(d, "o.sas")),
                        str(Path(d, "d.pddl")), str(Path(d, "p.pddl")), "--search", "astar(lmcut())"], capture_output=True, text=True, cwd=d)
        pf = Path(d, "plan")
        if not pf.exists():
            return None
        names = {n.lower(): n for n, _, _, _ in GROUND}
        steps = []
        for ln in pf.read_text().splitlines():
            if ln.startswith("("):
                steps.append(names[ln.strip("() \n")].replace("_", " "))
        return tuple(steps)


if __name__ == "__main__":
    with ProcessPoolExecutor(24) as ex:
        results = [r for r in ex.map(one, range(runs)) if r]
    counts = Counter(results)
    plans = [{"plan": list(p), "found": n} for p, n in counts.most_common()]
    (ROOT / "out" / f"plans_{word}.json").write_text(json.dumps({"word": word, "runs": runs, "plans": plans}, indent=1))
    print(f"{word}: {len(results)} successful runs, {len(plans)} distinct optimal plans (lengths: {sorted(set(len(p['plan']) for p in plans))})")
    print("most often found:", plans[0]["found"], "times; found only once:", sum(1 for p in plans if p["found"] == 1))

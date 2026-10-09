"""Optimal two-arm plan cost for one word, searched in parallel by splitting the first joint steps.

usage: python3 scripts/split_search.py WORD MAX_TOTAL [WORKERS=30] [TIME_LIMIT_PER_BRANCH=14400] [DEPTH=2]

Every different state reachable by DEPTH joint steps from the start becomes its own A*(LM-cut) problem, restricted to plans whose
total cost is at most MAX_TOTAL (FD's `bound` is exclusive, so bound = MAX_TOTAL - DEPTH + 1 for the rest). The answer is
min over the branches of DEPTH + the branch's optimal cost.
A branch that exhausts its space without a plan is proven to have none within the bound; a branch that hits the time limit is
*unknown*, and then the overall answer is only an upper bound.
Mirror images (arm 1 and arm 2 exchanged) are searched once, because both arms start empty.
Results are written to out/split_<WORD>_<MAX_TOTAL>.json after every finished branch.
"""
import itertools
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import twoarm
from twoarm import BLOCKS, JOINT, apply_joint, state_from, world_of

TOWERS = json.loads((ROOT / "data" / "blockworld.json").read_text())["towers"]


def goal_of(word):
    return [f"on({a},{b})" for a, b in zip(word, word[1:])] + [f"ontable({word[-1]})"]


def mirror(state):
    sw = {"handempty_1": "handempty_2", "handempty_2": "handempty_1", "holding_1": "holding_2", "holding_2": "holding_1"}
    return frozenset(tuple([sw.get(f[0], f[0])] + list(f[1:])) for f in state)


def canon(s):
    return min(tuple(sorted(s)), tuple(sorted(mirror(s))))


def successors(state):
    """All different states one joint step away, with one representative step each (mirror images merged)."""
    seen, out = set(), []
    for j in JOINT:
        for args in itertools.permutations(BLOCKS, len(j["params"])):
            b = dict(zip(j["params"], args))
            if any(f[0] == "neq" and b[f[1]] == b[f[2]] for f in j["pre"]):
                continue
            try:
                s = frozenset(apply_joint(state, j["name"], list(args)))
            except ValueError:
                continue
            key = canon(s)
            if key not in seen:
                seen.add(key)
                out.append((j["name"], list(args), s))
    return out


def frontier(state0, depth):
    """Different states reachable in exactly `depth` joint steps (mirror images merged), each with the steps that lead to it."""
    level = [([], frozenset(state0))]
    for _ in range(depth):
        nxt, seen = [], set()
        for path, st in level:
            for name, args, s in successors(st):
                key = canon(s)
                if key not in seen:
                    seen.add(key)
                    nxt.append((path + [[name, args]], s))
        level = nxt
    return level


def branch(task):
    idx, towers, hands, goal, bound, limit = task
    t0 = time.time()
    r = twoarm.solve(towers, goal, hands=hands, time_limit=limit, search=f"astar(lmcut(),bound={bound})")
    return idx, r["cost"], r.get("reason"), time.time() - t0


if __name__ == "__main__":
    word, max_total = sys.argv[1], int(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else 14400
    depth = int(sys.argv[5]) if len(sys.argv) > 5 else 2
    goal = goal_of(word)
    steps = frontier(state_from(TOWERS), depth)
    print(f"{word}: {len(steps)} different states after {depth} joint steps (mirror images merged); looking for total cost <= {max_total}", flush=True)
    tasks = []
    for i, (path, s) in enumerate(steps):
        w = world_of(s)
        tasks.append((i, w["towers"], w["hands"], goal, max_total - depth + 1, limit))
    results, best, t0 = [], None, time.time()
    out = ROOT / "out" / f"split_{word}_{max_total}.json"
    with ProcessPoolExecutor(workers) as ex:
        futs = [ex.submit(branch, t) for t in tasks]
        for n, f in enumerate(as_completed(futs), 1):
            idx, cost, reason, secs = f.result()
            results.append({"i": idx, "path": steps[idx][0], "rest_cost": cost, "reason": reason, "seconds": round(secs)})
            if cost is not None and (best is None or depth + cost < best[0]):
                best = (depth + cost, steps[idx][0])
            unknown = sum(1 for r in results if r["rest_cost"] is None and r["reason"] != "unsolvable")
            print(f"[{n}/{len(tasks)}] {time.time() - t0:5.0f}s  branch {idx}: rest cost {cost} {reason or ''} ({secs:.0f}s)   best total so far: {best[0] if best else None}   unknown: {unknown}", flush=True)
            out.write_text(json.dumps({"word": word, "max_total": max_total, "done": n, "of": len(tasks), "best": best, "results": results}))
    unknown = [r for r in results if r["rest_cost"] is None and r["reason"] != "unsolvable"]
    print(f"\nRESULT {word}: " + (f"optimal total cost {best[0]} (first steps {best[1]})" if best else f"no plan with total cost <= {max_total}")
          + ("" if not unknown else f"   -- but {len(unknown)} branches were NOT finished, so this is only an upper bound"))

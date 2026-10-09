"""The Fig. 1 reference case: both robots work together from the very start (no recognition, nobody joins late).

usage: python3 scripts/make_reference.py WORD [time_limit_seconds=3600]          searches the optimal two-arm plan (A*, LM-cut)
       python3 scripts/make_reference.py WORD --replay LOGFILE                   rebuilds the plan from a two_arm_word.py log (when the search was already done)
writes out/reference_<WORD>.json: the plan (every step with the world after it), its cost, c*(G) alone, and the paper's numbers
from the caption of Fig. 1: WORD (c(pi*_G), c(pi*_{Red+Ring})).
"""
import itertools
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import twoarm
from twoarm import BLOCKS, JOINT, apply_joint, components, state_from, world_of

PAPER = {"HER": (6, 2), "OTHER": (16, 6), "BOTHER": (22, 10), "MOTHER": (18, 6), "FATHER": (18, 8), "LATHER": (18, 8),
         "MASTER": (16, 8), "FASTER": (16, 8), "FOSTER": (12, 6), "HATER": (12, 6), "LATER": (12, 6), "WATER": (12, 6)}
TOWERS = json.loads((ROOT / "data" / "blockworld.json").read_text())["towers"]


def goal_of(word):
    return [f"on({a},{b})" for a, b in zip(word, word[1:])] + [f"ontable({word[-1]})"]


def replay(log_text):
    """Turn the step lines of a two_arm_word.py log ("  3: {1: 'unstack L S', 2: 'unstack W B'}") back into joint steps with worlds."""
    state, steps = state_from(TOWERS), []
    for ln in log_text.splitlines():
        m = re.match(r"\s*(\d+): (\{.*\})\s*$", ln)
        if not m:
            continue
        want = eval(m.group(2))
        for j in JOINT:
            hit = None
            for args in itertools.permutations(BLOCKS, len(j["params"])):
                if components(j["name"], list(args)) == want:
                    try:
                        new = apply_joint(state, j["name"], list(args))
                    except ValueError:
                        continue
                    hit = (list(args), new)
                    break
            if hit:
                state = hit[1]
                steps.append({"name": j["name"], "args": hit[0], "comps": want, "world": world_of(state)})
                break
        else:
            raise SystemExit(f"cannot rebuild step: {ln}")
    return {"cost": len(steps), "steps": steps, "start": world_of(state_from(TOWERS))}


if __name__ == "__main__":
    word = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == "--replay":
        r = replay(Path(sys.argv[3]).read_text())
    else:
        t0 = time.time()
        r = twoarm.solve(TOWERS, goal_of(word), time_limit=int(sys.argv[2]) if len(sys.argv) > 2 else 3600)
        print(f"{word}: search finished in {time.time() - t0:.0f} s")
    if r["cost"] is None:
        sys.exit(f"{word}: no optimal plan ({r.get('reason')}); nothing written")
    alone, paper_joint = PAPER[word]
    out = {"word": word, "cost": r["cost"], "alone": alone, "paper": [alone, paper_joint], "start": r["start"], "steps": r["steps"]}
    (ROOT / "out" / f"reference_{word}.json").write_text(json.dumps(out, indent=1))
    ok = "matches the paper" if r["cost"] == paper_joint else f"DIFFERS from the paper's {paper_joint}"
    print(f"{word}: both robots from the start = {r['cost']} steps ({ok}); R_ed alone = {alone}")
    for i, s in enumerate(r["steps"], 1):
        print(f"  {i}: {s['comps']}")

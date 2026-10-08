"""The helper's side (assistive interaction, Parts 8, 12 and 13): R_ing's plan and the helpfulness H.

usage: python3 scripts/make_helper.py [WORD] [t_join]       (needs out/trace_<WORD>.json; writes out/helper_<WORD>.json)

At the time R_ing joins (the first step where G_hat has no conflicts, something is still unmet and R_ed's hand is empty, or t_join):
  A  R_ed alone to G_hat                       (single arm)                 c_alone(G_hat)
  B  both arms to G_hat   = P_Ring (Def. 2)    optimal joint plan; R_ing's part of it is pi_Ring
  C  R_ed alone to her real goal G             c(pi*_{G,>=now})
  D  both arms to G with arm 2 locked to pi_Ring = P_{R_ed<-R_ing} (Part 12)         c(pi_{R_ed<-R_ing})
  H  = C - D                                    (Definition 5)
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import twoarm

word = sys.argv[1] if len(sys.argv) > 1 else "MASTER"
trace = json.loads((ROOT / "out" / f"trace_{word}.json").read_text())
steps, meta = trace["steps"], trace["meta"]
VARIANT = "eps3"


def facts_of(world):
    f = set()
    for col in world["towers"]:
        f.add(f"ontable({col[-1]})")
        f |= {f"on({a},{b})" for a, b in zip(col, col[1:])}
    return f


if len(sys.argv) > 2:
    t_join = int(sys.argv[2])
else:
    t_join = next((t for t, s in enumerate(steps) if not s["necessity"][VARIANT]["conflicts"] and s["world"]["hand"] is None
                   and set(s["necessity"][VARIANT]["G_hat"]) - facts_of(s["world"])), None)    # R_ed's hand must be empty
    if t_join is None:
        sys.exit(f"{word}: G_hat never becomes conflict-free with something left to do; R_ing never joins.")
world = steps[t_join]["world"]
assert world["hand"] is None, "R_ed is holding a block at the joining time; choose another t_join"
towers = world["towers"]
g_hat = steps[t_join]["necessity"][VARIANT]["G_hat"]
goal = meta["goals"][word]["conditions"]
print(f"{word}: R_ing joins after R_ed's action {t_join};  world: " + " | ".join("".join(c) for c in towers))
print(f"G_hat = {g_hat}")
print(f"unmet now: {sorted(set(g_hat) - facts_of(world))}\n")


def run(label, **kw):
    t0 = time.time()
    r = twoarm.solve(towers, **kw)
    print(f"{label:58} cost {r['cost']}   ({time.time() - t0:.0f} s)", flush=True)
    return r


A = run("A  R_ed alone to G_hat", goal_conds=g_hat, forced_arm2=[])
B = run("B  both arms to G_hat  (P_Ring)", goal_conds=g_hat)
pi_ring = [s["comps"][2] for s in B["steps"]] if B["cost"] else None
print("   pi_Ring (arm 2's part of B):", pi_ring)
C = run("C  R_ed alone to her goal G", goal_conds=goal, forced_arm2=[])
D = run("D  both arms to G, arm 2 locked to pi_Ring (P_Red<-Ring)", goal_conds=goal, forced_arm2=pi_ring) if pi_ring is not None else {"cost": None}
E = run("E  (reference) both arms free to G", goal_conds=goal)

if any(x["cost"] is None for x in (A, B, C, D)):
    sys.exit(f"{word}: at least one of the plans A-D was not found within the time limit; no helper data written.")
H = C["cost"] - D["cost"]
print(f"\nH(pi_Ring) = c(pi*_G,>=now) - c(pi_Red<-Ring) = {C['cost']} - {D['cost']} = {H}")
(ROOT / "out" / f"helper_{word}.json").write_text(json.dumps({
    "word": word, "t_join": t_join, "variant": VARIANT, "start": twoarm.world_of(twoarm.state_from(towers)),
    "G_hat": g_hat, "goal": goal, "pi_ring": pi_ring,
    "alone_Ghat": A, "joint_Ghat": B, "alone_G": C, "response_G": D, "joint_free_G": E, "H": H}, indent=1))
print(f"wrote out/helper_{word}.json")

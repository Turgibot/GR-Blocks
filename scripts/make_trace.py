"""Build a complete calculation trace of the recognition process, for the viewer pages.

For every step t = 0 ... n of R_ed's plan it records, with all intermediate numbers:
  the world, the planner's plans and costs for G+O and G+notO, the likelihood arithmetic, the dynamic-prior
  arithmetic (every Poisson term, for every foresight eps), the posteriors, the necessities and G_hat.

usage: python3 scripts/make_trace.py [HIDDEN_WORD]          (default MASTER; takes about 5 minutes)
writes out/trace_<WORD>.json
"""
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "scripts"))
from survival import pmf, survival

HIDDEN = sys.argv[1] if len(sys.argv) > 1 else "MASTER"
BETA, LAM, TAU, EPSILONS = 1.0, 1.0, 0.3, [0, 1, 3, 6]

world = json.loads((ROOT / "data" / "blockworld.json").read_text())
operators = json.loads((ROOT / "data" / "actions.json").read_text())["operators"]
towers0 = world["towers"]
WORDS = list(world["goals"])


# ---------------------------------------------------------------- the world ---------------------------------------
def initial_state():
    facts = {("handempty",)}
    for tower in towers0:
        facts.add(("clear", tower[0])); facts.add(("ontable", tower[-1]))
        facts |= {("on", a, b) for a, b in zip(tower, tower[1:])}
    return facts


def inst(facts, bind):
    return {tuple([f[0]] + [bind.get(a, a) for a in f[1:]]) for f in map(tuple, facts)}


def apply(state, action):
    name, *blocks = action.split()
    op = operators[name]
    bind = dict(zip(op["params"], blocks))
    if inst(op["pre"], bind) - state:
        raise ValueError(f"{action} is not applicable")
    return (state - inst(op["del"], bind)) | inst(op["add"], bind)


def draw(state):
    cols = []
    for bottom in sorted(f[1] for f in state if f[0] == "ontable"):
        col = [bottom]
        while True:
            above = [f[1] for f in state if f[0] == "on" and f[2] == col[-1]]
            if not above:
                break
            col.append(above[0])
        cols.append(col[::-1])                       # top first
    held = [f[1] for f in state if f[0] == "holding"]
    return {"towers": cols, "hand": held[0] if held else None}


# ---------------------------------------------------------------- planner calls ----------------------------------
def read_plan_file(word):
    lines = (OUT / f"plan_{word}.txt").read_text().splitlines()
    plan = []
    for ln in lines:
        if ln.startswith("("):
            p = ln.strip("() ").split()
            plan.append(" ".join([p[0]] + [x.upper() for x in p[1:]]))
    return plan


def plans_with_observations(word, observed):
    """Run scripts/compile_observations.py and read back both plans."""
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "compile_observations.py"), word, ", ".join(observed)],
                         capture_output=True, text=True).stdout
    result = {}
    for label in ("G+O", "G+notO"):
        m = re.search(rf"=== {re.escape(label)}: (?:cost (\d+)|no plan) ===\n((?:\s+\d+\. .*\n?)*)", out)
        if not m or m.group(1) is None:
            result[label] = (None, [])
        else:
            result[label] = (int(m.group(1)), [ln.split(". ", 1)[1].strip() for ln in m.group(2).splitlines() if ln.strip()])
    return result


# ---------------------------------------------------------------- the statistics ---------------------------------
def conditions_of(word):
    return [f"on({a},{b})" for a, b in zip(word, word[1:])] + [f"ontable({word[-1]})"]


def conflicts_of(conds):
    parsed = []
    for c in conds:
        name, args = c[:-1].split("(")
        parsed.append((c, name, args.split(",")))
    found = []
    for i, (c1, n1, a1) in enumerate(parsed):
        for c2, n2, a2 in parsed[i + 1:]:
            if n1 == n2 == "on" and ((a1[1] == a2[1] and a1[0] != a2[0]) or (a1[0] == a2[0] and a1[1] != a2[1])):
                found.append([c1, c2])
            if {n1, n2} == {"on", "ontable"}:
                on_a, tab_a = (a1, a2) if n1 == "on" else (a2, a1)
                if on_a[0] == tab_a[0]:
                    found.append([c1, c2])
    return found


def prior_terms(c_star, t_prime):
    """Every term of the survival computation: P(cost = x | G) for x = c* ... t'-1."""
    terms, cum = [], 0.0
    for x in range(c_star, t_prime):
        v = pmf(x, c_star, LAM)
        cum += v
        terms.append({"x": x, "k": x - c_star + 1, "pmf": v, "cum": cum})
    return {"t_prime": t_prime, "terms": terms, "cum": cum, "survival": survival(t_prime, c_star, LAM)}


def necessity(posterior):
    table = {}
    for w, p in posterior.items():
        for c in conditions_of(w):
            table.setdefault(c, []).append([w, p])
    rows = [{"condition": c, "contributors": sorted(v, key=lambda x: -x[1]), "N": sum(p for _, p in v)} for c, v in table.items()]
    rows.sort(key=lambda r: -r["N"])
    g_hat = [r["condition"] for r in rows if r["N"] >= TAU]
    for r in rows:
        r["in_G_hat"] = r["N"] >= TAU
    return {"rows": rows, "G_hat": g_hat, "conflicts": conflicts_of(g_hat)}


# ---------------------------------------------------------------- build the trace --------------------------------
for w in WORDS:                                       # plans for each goal on its own (needed at t = 0)
    if not (OUT / f"plan_{w}.txt").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "plan_word.py"), w], capture_output=True)

c_star = {w: world["goals"][w]["cost_one_agent"] for w in WORDS}
observed_plan = read_plan_file(HIDDEN)
n = len(observed_plan)

meta = {
    "hidden_goal": HIDDEN, "beta": BETA, "lambda": LAM, "tau": TAU, "epsilons": EPSILONS,
    "observed_plan": observed_plan, "start_towers": towers0, "words": WORDS,
    "goals": {w: {"c_star": c_star[w], "conditions": conditions_of(w), "plan_alone": read_plan_file(w),
                  "two_agent_cost_paper": world["goals"][w]["cost_two_agents"]} for w in WORDS},
}

steps, state = [], initial_state()
t_start = time.time()
for t in range(n + 1):
    if t > 0:
        state = apply(state, observed_plan[t - 1])
    observed = observed_plan[:t]
    goals_t = {}
    for w in WORDS:
        if t == 0:                                    # nothing observed: both questions have the same answer
            plan = meta["goals"][w]["plan_alone"]
            c_o, c_not, plan_o, plan_not = len(plan), len(plan), plan, plan
        else:
            r = plans_with_observations(w, observed)
            (c_o, plan_o), (c_not, plan_not) = r["G+O"], r["G+notO"]
        if t == 0:
            like = {"exp_O": None, "exp_notO": None, "alpha": None, "value": 1.0, "note": "no observations yet: likelihood 1 for every goal"}
        else:
            # "no plan" means infinite cost: exp(-beta * infinity) = 0
            e_o = 0.0 if c_o is None else math.exp(-BETA * c_o)
            e_n = 0.0 if c_not is None else math.exp(-BETA * c_not)
            alpha = e_o + e_n
            like = {"exp_O": e_o, "exp_notO": e_n, "alpha": alpha, "value": (e_o / alpha) if alpha > 0 else 0.0}
            if c_not is None:
                like["note"] = "no plan reaches G without performing O (infinite cost), so the observations are unavoidable: likelihood 1"
            elif c_o is None:
                like["note"] = "no plan reaches G while performing O (infinite cost): likelihood 0"
        goals_t[w] = {"c_O": c_o, "plan_O": plan_o, "c_notO": c_not, "plan_notO": plan_not,
                      "gap": (c_not - c_o) if (c_o is not None and c_not is not None) else None, "likelihood": like,
                      "prior": {str(e): prior_terms(c_star[w], t + e) for e in EPSILONS}}
    # posteriors for the base method and for each foresight value
    variants = {"base": {w: goals_t[w]["likelihood"]["value"] for w in WORDS}}
    for e in EPSILONS:
        variants[f"eps{e}"] = {w: goals_t[w]["likelihood"]["value"] * goals_t[w]["prior"][str(e)]["survival"] for w in WORDS}
    post, z_of = {}, {}
    for name, scores in variants.items():
        z = sum(scores.values())
        z_of[name] = z
        post[name] = {w: s / z for w, s in scores.items()}
    steps.append({
        "t": t, "observed": observed, "last_action": observed[-1] if observed else None,
        "world": draw(state), "goals": goals_t,
        "score": variants, "normalizer": z_of, "posterior": post,
        "necessity": {name: necessity(post[name]) for name in post},
    })
    top = sorted(post["eps3"], key=post["eps3"].get, reverse=True)[:3]
    print(f"t = {t:2}  done ({time.time() - t_start:5.0f} s)   top (eps=3): " + ", ".join(f"{w} {post['eps3'][w]:.2f}" for w in top), flush=True)

meta["formulas"] = {
    "likelihood": "P(O|G) = exp(-beta*c(G+O)) / ( exp(-beta*c(G+O)) + exp(-beta*c(G+notO)) )",
    "prior_pmf": "P(c(pi)=x | G) = (lambda+1)^k / ( k! * (e^(lambda+1) - 1) ),  k = x - c*(G) + 1,  x >= c*(G)",
    "prior_survival": "P(t'|G) = 1 - sum of P(c(pi)=x | G) for x = c*(G) ... t'-1,   t' = t + eps   (equals 1 if t' <= c*(G))",
    "posterior": "P(G|O,t) = P(O|G) * P(t+eps|G) / Z,   Z = sum over all goals",
    "necessity": "N(p|O) = sum over goals G of P(G|O,t) * [p in G]",
    "G_hat": "G_hat = { p : N(p|O) >= tau }",
}
(OUT / f"trace_{HIDDEN}.json").write_text(json.dumps({"meta": meta, "steps": steps}, indent=1))
size = (OUT / f"trace_{HIDDEN}.json").stat().st_size
print(f"\nwrote out/trace_{HIDDEN}.json  ({size / 1024:.0f} KB, {len(steps)} steps, {time.time() - t_start:.0f} s)")

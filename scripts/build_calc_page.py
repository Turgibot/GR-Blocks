"""Build the self-contained page: viewer/calc_template.html + every out/trace_<WORD>.json (+ out/helper_<WORD>.json).

usage: python3 scripts/build_calc_page.py          writes recognition-calculations.html
The traces are slimmed: the page recomputes likelihoods, priors, posteriors and necessities itself, and only
keeps the stored posteriors and necessities to check its own arithmetic against Python.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
DEFAULT = "MASTER"


def slim_trace(trace):
    meta = trace["meta"]
    keep_meta = {k: meta[k] for k in ("hidden_goal", "beta", "lambda", "tau", "epsilons", "observed_plan", "start_towers", "words")}
    keep_meta["goals"] = {w: {"c_star": g["c_star"], "conditions": g["conditions"]} for w, g in meta["goals"].items()}
    steps = []
    for s in trace["steps"]:
        steps.append({
            "last_action": s["last_action"], "world": s["world"],
            "goals": {w: {"c_O": g["c_O"], "c_notO": g["c_notO"], "plan_O": g["plan_O"], "plan_notO": g["plan_notO"]} for w, g in s["goals"].items()},
            "posterior": s["posterior"],
            "necessity": {v: {"N": {r["condition"]: r["N"] for r in n["rows"]}, "G_hat": n["G_hat"], "conflicts": n["conflicts"]} for v, n in s["necessity"].items()},
        })
    return {"meta": keep_meta, "steps": steps}


words = {}
for path in sorted(OUT.glob("trace_*.json")):
    word = path.stem.split("_", 1)[1]
    entry = slim_trace(json.loads(path.read_text()))
    helper = OUT / f"helper_{word}.json"
    entry["helper"] = json.loads(helper.read_text()) if helper.exists() else None
    scen = OUT / f"scenarios_{word}.json"
    entry["scenarios"] = json.loads(scen.read_text())["scenarios"] if scen.exists() else None
    ref = OUT / f"reference_{word}.json"
    entry["reference"] = json.loads(ref.read_text()) if ref.exists() else None
    expo = OUT / f"exposure_{word}.json"
    if expo.exists():                                                # the extension page (safe-exposure.html): numbers for the note in panel 6
        e = json.loads(expo.read_text())
        entry["exposure"] = {"completion": e["completion"], "paper": e["paper"]["joint"], "alone": e["paper"]["alone"]}
    else:
        entry["exposure"] = None
    words[word] = entry
assert DEFAULT in words, "out/trace_MASTER.json is missing"
order = [w for w in words[DEFAULT]["meta"]["words"] if w in words]
data = {"default": DEFAULT, "order": order, "words": words, "blocks": sorted(b for t in words[DEFAULT]["meta"]["start_towers"] for b in t)}

page = (ROOT / "viewer" / "workbench_template.html").read_text()
assert "/*DATA_JSON*/null" in page
out = ROOT / "recognition-calculations.html"
out.write_text(page.replace("/*DATA_JSON*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/")))
print(f"wrote {out.name}: {len(order)} goal words ({', '.join(order)}), "
      f"{sum(1 for w in order if words[w]['helper'])} with a helper plan, {out.stat().st_size / 1024 / 1024:.1f} MB")

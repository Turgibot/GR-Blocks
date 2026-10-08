"""Feed R_ed's plan to the recognizer one action at a time and print how the belief changes.

usage: python3 scripts/watch_belief.py [HIDDEN_WORD] [beta]        (default MASTER, beta 1)
Needs out/plan_<WORD>.txt, which scripts/plan_word.py writes.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
hidden = sys.argv[1] if len(sys.argv) > 1 else "MASTER"
beta = sys.argv[2] if len(sys.argv) > 2 else "1"

plan = []
for line in (OUT / f"plan_{hidden}.txt").read_text().splitlines():
    if line.startswith("("):
        parts = line.strip("() ").split()
        plan.append(" ".join([parts[0]] + [p.upper() for p in parts[1:]]))
print(f"R_ed's plan for {hidden} ({len(plan)} actions); beta = {beta}; no dynamic prior; uniform prior\n")

history = {}          # t -> {word: posterior}
for t in range(1, len(plan) + 1):
    obs = ", ".join(plan[:t])
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "recognize.py"), obs, beta],
                         capture_output=True, text=True).stdout
    post = {}
    for line in out.splitlines():
        m = re.match(r"^([A-Z]+)\s+\S+\s+\S+\s+\S+\s+([\d.]+)\s+([\d.]+)$", line)
        if m:
            post[m.group(1)] = float(m.group(3))
    history[t] = post
    top = sorted(post, key=post.get, reverse=True)[:3]
    print(f"after action {t:2} ({plan[t - 1]:<14}) top: " + ", ".join(f"{w} {post[w]:.2f}" for w in top))

(OUT / f"belief_{hidden}.json").write_text(json.dumps({"plan": plan, "posterior": history}, indent=1))

words = list(history[1])
print("\nposterior of every word after each action (columns are t = 1 ... %d)" % len(plan))
print(f"{'':8}" + "".join(f"{t:>5}" for t in history))
for w in words:
    print(f"{w:8}" + "".join(f"{history[t][w]:>5.2f}" for t in history) + ("   <- hidden goal" if w == hidden else ""))

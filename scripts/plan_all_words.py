"""Run scripts/plan_word.py for every goal word and compare plan costs with the paper's Fig. 1."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
goals = json.loads((ROOT / "data" / "blockworld.json").read_text())["goals"]

print(f"{'word':8}{'planner':>9}{'paper':>7}{'match':>7}{'seconds':>9}")
all_match = True
for word, g in goals.items():
    t0 = time.time()
    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "plan_word.py"), word],
                         capture_output=True, text=True)
    m = re.search(r"plan cost = (\d+)", run.stdout)
    cost = int(m.group(1)) if m else None
    ok = cost == g["cost_one_agent"]
    all_match &= ok
    print(f"{word:8}{str(cost):>9}{g['cost_one_agent']:>7}{'yes' if ok else 'NO':>7}{time.time() - t0:>9.1f}")
print("\nall 12 match the paper:", all_match)

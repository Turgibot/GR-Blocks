"""Play R_ed's plan in the running Isaac Sim, one action at a time.

usage: python3 scripts/replay_in_sim.py [seconds_per_step]      (default 2.0)
Needs Isaac Sim running with the scene built (isaac/README.md) and out/trace_MASTER.json.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEND = ROOT / "third_party" / "isaac-sim-remote" / "scripts" / "isaacsim_send.py"
pause = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
n = 16

for t in range(n + 1):
    out = subprocess.run([sys.executable, str(SEND), "--file", str(ROOT / "isaac" / "replay_step.py"), "--arg", f"t={t}"],
                         capture_output=True, text=True)
    print(out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr[-300:], flush=True)
    time.sleep(pause)

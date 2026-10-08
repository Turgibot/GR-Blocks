"""Put the blocks where they are after R_ed's t-th action (run through the python server).

usage (from the repo root, .venv active):
  python3 third_party/isaac-sim-remote/scripts/isaacsim_send.py --file isaac/replay_step.py --arg t=6

Reads /workspace/out/trace_MASTER.json (the trace the calculation page uses), so the sim and the page show the same
world. Blocks are only moved (kinematic: they are teleported), never deleted or recreated.
"""
import builtins
import json

import omni.ui as ui
import omni.usd
from pxr import UsdGeom

if "t" not in dir():
    t = 0                                           # noqa: F841 (injected by --arg t=...)
EDGE = 0.05
HAND = (0.20, 0.0, 0.30)                            # where the held block floats (x, y, z)
SLOTS = [(0.0, -0.18), (0.0, 0.0), (0.0, 0.18), (0.0, -0.36), (0.0, 0.36),
         (-0.2, -0.18), (-0.2, 0.0), (-0.2, 0.18), (-0.2, -0.36), (-0.2, 0.36)]   # table places (x, y)

trace = json.load(open("/workspace/out/trace_MASTER.json"))
steps, plan = trace["steps"], trace["meta"]["observed_plan"]
t = max(0, min(len(steps) - 1, int(t)))

# which table place each column of blocks uses; a column keeps its place while its bottom block stays on the table.
# The start towers keep the places they were built in (left to right as in Fig. 1: H-T-E-R, L-S-M-O, F-W-B-A).
slot_of = {tower[-1]: i for i, tower in enumerate(trace["meta"]["start_towers"])}
for k in range(t + 1):
    bottoms = [col[-1] for col in steps[k]["world"]["towers"]]
    slot_of = {b: slot_of[b] for b in bottoms if b in slot_of}
    for b in bottoms:
        if b not in slot_of:
            slot_of[b] = next(i for i in range(len(SLOTS)) if i not in slot_of.values())

stage = omni.usd.get_context().get_stage()
world = steps[t]["world"]
placed = 0
for col in world["towers"]:
    x, y = SLOTS[slot_of[col[-1]]]
    for level, letter in enumerate(reversed(col)):                  # level 0 = the block on the table
        UsdGeom.XformCommonAPI(stage.GetPrimAtPath(f"/World/Blocks/{letter}")).SetTranslate((x, y, level * EDGE + EDGE / 2))
        placed += 1
if world["hand"]:
    UsdGeom.XformCommonAPI(stage.GetPrimAtPath(f"/World/Blocks/{world['hand']}")).SetTranslate(HAND)
    placed += 1
assert placed == 12, f"placed {placed} blocks, expected 12"

# a small label window; created once, then only its text changes
if not hasattr(builtins, "GR_REPLAY_LABELS"):
    win = ui.Window("Replay of R_ed's plan", width=430, height=95, position_x=20, position_y=60)
    with win.frame:
        with ui.VStack(spacing=4):
            line1, line2 = ui.Label("", height=24), ui.Label("", height=24)
    builtins.GR_REPLAY_WINDOW, builtins.GR_REPLAY_LABELS = win, (line1, line2)
line1, line2 = builtins.GR_REPLAY_LABELS
line1.text = f"step {t} of {len(steps) - 1}"
line2.text = ("start state, nothing done yet" if t == 0 else "R_ed just did:  " + plan[t - 1].replace(" ", "(", 1).replace(" ", ",") + ")")
print(f"t={t}: columns " + " | ".join("".join(c) for c in world["towers"]) + (f" | hand: {world['hand']}" if world["hand"] else ""))

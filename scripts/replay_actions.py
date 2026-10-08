"""Apply Blocksworld actions to the start state of data/blockworld.json, one at a time."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
towers = json.loads((ROOT / "data" / "blockworld.json").read_text())["towers"]
operators = json.loads((ROOT / "data" / "actions.json").read_text())["operators"]


def initial_state(towers):
    """A state is a set of facts, e.g. ('on', 'H', 'T')."""
    facts = {("handempty",)}
    for tower in towers:                       # tower is listed top to bottom
        facts.add(("clear", tower[0]))
        facts.add(("ontable", tower[-1]))
        for upper, lower in zip(tower, tower[1:]):
            facts.add(("on", upper, lower))
    return facts


def instantiate(facts, binding):
    """Replace parameter names (x, y) in a list of fact templates by block letters."""
    return {tuple([f[0]] + [binding.get(a, a) for a in f[1:]]) for f in map(tuple, facts)}


def apply(state, name, *blocks):
    op = operators[name]
    binding = dict(zip(op["params"], blocks))
    missing = instantiate(op["pre"], binding) - state
    if missing:
        raise ValueError(f"{name}({','.join(blocks)}) is not allowed: needs {sorted(missing)}")
    return (state - instantiate(op["del"], binding)) | instantiate(op["add"], binding)


def show(state):
    """Draw the towers (top first) and the hand."""
    bottoms = sorted(f[1] for f in state if f[0] == "ontable")
    columns = []
    for b in bottoms:                          # build each tower upward from the table
        col = [b]
        while True:
            above = [f[1] for f in state if f[0] == "on" and f[2] == col[-1]]
            if not above:
                break
            col.append(above[0])
        columns.append(col[::-1])              # top first
    held = [f[1] for f in state if f[0] == "holding"]
    height = max(len(c) for c in columns)
    for row in range(height):
        print("   " + "   ".join(f"[{c[row - (height - len(c))]}]" if row >= height - len(c) else "   " for c in columns))
    print("   " + "-----" * len(columns) + "  table")
    print("   hand:", f"holding {held[0]}" if held else "empty")


state = initial_state(towers)
print("START"); show(state)

plan = [("unstack", "H", "T"), ("put-down", "H"), ("unstack", "T", "E"),
        ("put-down", "T"), ("pick-up", "H"), ("stack", "H", "E")]
for step, action in enumerate(plan, 1):
    state = apply(state, *action)
    print(f"\nstep {step}: {action[0]}({','.join(action[1:])})   [cost so far: {step}]")
    show(state)

goal = {("on", "H", "E"), ("on", "E", "R"), ("ontable", "R")}
print("\nHER conditions all true after 6 actions:", goal <= state)

print("\nTrying an illegal action on the start state: stack(H,E)")
try:
    apply(initial_state(towers), "stack", "H", "E")
except ValueError as err:
    print("  refused ->", err)

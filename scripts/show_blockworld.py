"""Print the Block-words data in data/blockworld.json and check it for mistakes."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "blockworld.json"
world = json.loads(DATA.read_text())
towers, goals = world["towers"], world["goals"]

# --- checks -----------------------------------------------------------------
blocks = [b for tower in towers for b in tower]
assert len(blocks) == len(set(blocks)), "a letter appears on two blocks"
for word in goals:
    assert len(word) == len(set(word)), f"{word} repeats a letter"
    assert set(word) <= set(blocks), f"{word} uses a letter with no block"
print(f"OK: {len(blocks)} blocks, {len(towers)} towers, {len(goals)} goal words\n")

# --- start state, drawn like Fig. 1 -----------------------------------------
print("Start state (as in Fig. 1, top of each tower first):")
height = max(len(t) for t in towers)
for row in range(height):
    print("   " + "   ".join(f"[{t[row]}]" if row < len(t) else "   " for t in towers))
print("   " + "---".join("---" for _ in towers) + "----  table\n")

# --- goals ------------------------------------------------------------------
def conditions(word):
    """Goal conditions of a word spelled top to bottom (my reading of the paper)."""
    on = [f"on({a},{b})" for a, b in zip(word, word[1:])]
    return on + [f"ontable({word[-1]})"]

print(f"{'word':8}{'one agent':>10}{'two agents':>12}   goal conditions")
for word, c in goals.items():
    mark = "*" if word == world["hidden_goal_in_paper_example"] else " "
    print(f"{word:7}{mark}{c['cost_one_agent']:>10}{c['cost_two_agents']:>12}   {', '.join(conditions(word))}")
print("\n* = the hidden goal in the paper's example")
print("Assumption (not stated in the paper): the top block of a goal word is also required to be clear.")

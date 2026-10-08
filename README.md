# GR-Blocks

A step-by-step implementation of Freedman & Zilberstein, *Integration of Planning with Recognition for Responsive
Interaction Using Classical Planners* (AAAI-17), in the paper's Block-words domain. Everything is shown in one web page.

## What to open

| File | What it is |
|---|---|
| `recognition-calculations.html` | **The workbench.** Animated blocks world, R_ed's plan, the goal recognition with every formula and number, necessity, and the helper R_ing's plan and helpfulness. Works offline; open it in a browser. |
| `integration-of-planning-with-recognition-reading-companion.html` | A slide-by-slide study guide to the paper (27 parts). |

In the workbench choose R_ed's goal word and a scenario (R_ed alone, assistive, independent, adversarial), press play, or
step with the arrow keys. β, λ, τ and the foresight ε can be changed live; the page recomputes everything and checks
its own arithmetic against the Python numbers (see the line at the bottom).

## How the numbers are made

Fast Downward (A* with LM-cut) is the planner. It is built into `third_party/` (not tracked by git) and the Python
environment is `.venv`.

```
data/blockworld.json, data/actions.json      the world and the four operators
scripts/plan_word.py, plan_all_words.py      one-arm optimal plans; all 12 costs match Fig. 1
scripts/compile_observations.py              observed actions -> planning problem (G+O and G+notO)
scripts/make_trace.py WORD                   every plan, cost and intermediate number for R_ed's plan to WORD
scripts/make_all_traces.sh                   all words in parallel (about 10 minutes)
scripts/twoarm.py                            two-arm joint-action planner (the paper's rules)
scripts/make_helper.py WORD                  R_ing's plan and the helpfulness H
scripts/make_scenarios.py WORD               independent and adversarial interaction
scripts/build_calc_page.py                   builds recognition-calculations.html from out/*.json
viewer/workbench_template.html               the page itself
```

Rebuild everything: `scripts/make_all_traces.sh`, then `scripts/make_all_helpers.sh`, `scripts/make_scenarios.py MASTER`,
then `python3 scripts/build_calc_page.py`.

## Decisions and open points

* **No ROS 2, no Isaac Sim.** The robot arm does not matter for the paper's algorithm. `docker/` and `isaac/` hold an
  earlier Isaac Sim version (blocks scene and replay) that is kept but not developed further.
* The two-arm rules (parallel moves, handover, stacked-pair lifts including a pair whose lower block is on the table)
  reproduce 9 of the 12 two-agent costs of Fig. 1; BOTHER, MASTER and FASTER hit the 10-minute optimal-search limit.
  The helper numbers for MASTER match the paper: 8 and 4 steps, H = 4.
* Our recognition does not reproduce the curves of the paper's Fig. 2 exactly (the paper gives no λ or β, and its
  plan for MASTER is not printed). FOSTER ties with MASTER and FASTER after action 6.
* The goal conditions are the "X on Y" pairs and "last letter on the table"; the paper does not say whether the top
  block must also be clear.
* Independent interaction: R_ed is locked to the plan she would follow alone, nothing is coordinated (no handovers or
  pair lifts), and R_ing plans her own word by herself without breaking R_ed's plan. This is my reading of Definition 3;
  the paper's centralized formulation would let the planner use R_ed's arm to build R_ing's word, which is not what its
  own example describes. Only MASTER has independent and adversarial scenarios.
* In the adversarial case the paper's centralized formulation cannot produce a blocking plan by itself, so the two
  blocking plans the paper describes (hoarding, S on M) are evaluated exactly instead of being found.

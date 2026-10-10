## Safe Exposure: Proactive Assistance Before Goal Recognition Converges

**Motivation.** In the integration of planning with recognition (Freedman & Zilberstein, 2017), the observer R_ing joins the actor R_ed only once the recognized goal set Ĝ is free of conflicts. Until then R_ing is idle. Because the time at which R_ing joins largely determines the benefit of joint execution, this idle period is a cost. We propose that R_ing use it to perform actions that are harmless under every goal that remains plausible, and thereby prepare the world for R_ed.

**Positioning.** The paper treats the joining time as a quantity that can be evaluated ("the decision of when to join can be evaluated as well"), but its procedure fixes it: R_ing acts only when the recognized goal set is free of conflicts. The paper also names the cost of this rule. For MASTER and FASTER it observes that R_ing could uncover the blocks H, O and W and start to stack them, but rejects stacking as impractical because it would have to be undone, and concludes that more observations may be necessary and that R_ing may have to wait until the goal is already complete. Our proposal is that R_ing need not wait. What it can safely do before it can safely build is to *uncover*, not to stack, so that nothing has to be undone if the belief changes. Joining is then no longer a single moment, and idleness before recognition converges is replaced by preparation that is harmless under every goal still in play.

**Setting.** Let G be the set of candidate goals, each a conjunction of facts of the form `on(a,b)` and `ontable(a)`. After R_ed's first t observed actions O_t, the recognition procedure yields a posterior P(g | O_t). For a threshold θ, the set of *live goals* is

  L_t = { g ∈ G : P(g | O_t) ≥ θ }.

In our experiments θ = 0.01.

**Exposure move.** Let x be the topmost block of a column in which x rests on y, and suppose R_ed is not holding x. An *exposure move* e(x) consists of two actions of R_ing, `unstack x y` followed by `put-down x`, which relocate x to the table. The first is executed in one time step, the second in the next. Each is executed in parallel with one action of R_ed, which the joint-action model permits when the two arms act on different blocks.

**Safety.** An exposure move is *safe at time t* if it destroys no fact that a live goal requires:

  safe_t(x) ⇔ on(x, y) ∉ g for all g ∈ L_t.

**Utility.** A safe move is *useful for g* if x must be moved in any plan for g, that is, if some block b beneath x in the column does not occupy its goal position in g (its fact `on(b,c)` or `ontable(b)` is not in g). Write

  u_t(x) = |{ g ∈ L_t : x is useful for g }|.

At each step R_ing selects the safe move with maximal u_t(x), and performs none if no safe move has u_t(x) > 0. R_ing is not informed of R_ed's next action. If its action would conflict with R_ed's, the action is dropped. If an earlier exposure invalidates R_ed's remaining plan, R_ed re-plans optimally from the current world.

**Relation to necessity.** The paper identifies conditions that are required by the live goals, and R_ing builds those. Safe exposure applies the complementary principle: R_ing undoes only conditions that no live goal requires. Both depend on the same belief over goals, and neither requires R_ing to commit to a single goal.

**Evaluation.** We evaluated exposure on the Block-words domain of the paper (twelve goal words, one start configuration) with optimal planning (Fast Downward, A* with LM-cut) and with the paper's joint actions, which count a coupled pair of arm actions as one time step. The measure was completion time, the number of steps until R_ed's goal is satisfied. In each run, R_ing performed exposure moves until the paper's joining time, after which the paper's helper procedure was applied to the resulting world. Of the nine words for which the baseline procedure yields a joining time, exposure was never slower than the baseline and was faster in seven.

| Word | R_ed alone | Baseline (join after recognition) | Safe exposure |
|---|---|---|---|
| MASTER | 16 | 12 | 10 |
| FASTER | 16 | 12 | 10 |
| FOSTER | 12 | 18 | 10 |
| BOTHER | 22 | 20 | 14 |
| FATHER | 18 | 16 | 12 |
| LATER | 12 | 12 | 10 |
| WATER | 12 | 14 | 12 |
| MOTHER | 18 | 16 | 16 |
| OTHER | 16 | 14 | 14 |

For FOSTER and WATER, where the baseline helper had mis-identified R_ed's goal (helpfulness −6 and −2), exposure removed that cost. For MOTHER and OTHER, exposure invalidated part of R_ed's plan and she had to re-plan, and completion time equalled the baseline.

**Limitations.** First, safety is verified on goal conditions only, not on the intermediate states that optimal plans for live goals traverse, which explains the re-plans observed in MOTHER and OTHER. Second, placing x on the table may require a later pick-up, and this cost is not charged by the safety test, so the absence of harm in our runs is empirical, not guaranteed. Third, the threshold θ and the greedy selection rule are heuristic. Fourth, the evaluation uses one start configuration and does not cover the words HER, HATER and LATHER, for which the baseline procedure never reaches a joining time. Finally, the paper's helpfulness H does not capture the gain: for MASTER, H falls from 4 to 0 because R_ed alone, from the exposed world, is already near-optimal. A measure that also counts the time before joining would be needed. A stronger safety criterion would use the planner itself, accepting a move only if no live goal's optimal joint cost increases.

**Reference.** Freedman, R. G., and Zilberstein, S. 2017. Integration of Planning with Recognition for Responsive Interaction Using Classical Planners. In *Proceedings of the Thirty-First AAAI Conference on Artificial Intelligence (AAAI-17)*. AAAI Press.

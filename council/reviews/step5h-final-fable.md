# Council round 5h, Fable judge (saved verbatim from the agent's final reply; it scored commit cc0e017, before the done-rule rescoring)

**Next action:** rescore section 6k under the rule v1.14 actually registered (an episode that never calls `done` is a failure). This flips B3 to MISSED for Haiku, and the committed README, PROTOCOL outcome and RESULTS.md all say B3 is met.

**State:** I recomputed the within-10 table, the Sonnet bullet and the budget paragraph from the raw files with my own parser. Every count and interval the README prints matches. All 152 tests pass, the checker reports 1,714 files clean, and the meter reads $79.43 and $28.80. I regenerated RESULTS.md to scratch and the diff was empty. Both registrations reached origin before the first run file existed (10 s and 6 s). `scripts/analyze.py` has an uncommitted edit in the working tree that I did not make; it starts on the two generator bugs below. I scored HEAD `cc0e017`.

## A. Claims still wrong, overstated or inconsistent

1. **"B3 met for both" is wrong under the registered rule.** v1.14 says an episode that does not call `done` in time is a failure. Section 6k at HEAD counts the simulator's verdict alone, and 36 of the 960 held-out budget episodes are physically solved without `done`. The table shows the notebook (12 episodes) against the names list under each rule:

   | cell | as committed | registered rule | verdict |
   |---|---|---|---|
   | Haiku `stack` (B1) | 37 vs 35, +5.0 | 36 vs 34, +5.0 | met |
   | Haiku `flasks` (B2) | 40 vs 34, +15.0 | 40 vs 31, +22.5 | missed |
   | Luna `flasks` (B2) | 40 vs 24, +40.0 | 40 vs 23, +42.5 | met |
   | Haiku `bins` (B3) | 13 vs 0, +32.5 | 8 vs 0, **+20.0** | **flips to MISSED** |
   | Luna `bins` (B3) | 39 vs 19, +50.0 | 38 vs 16, +55.0 | met |

   The honest summary is that both number-jobs predictions held for Luna and missed for Haiku. "It mostly held" (finding 3) is too generous and is not a registered reading. Other README counts move too: Haiku no memory on `flasks` is 33, not 37, and the one-episode notebook on `stack` is 17, not 20.

2. **The Sonnet bullet says the data "do not separate what the parts do", but within 10 calls they do, against the headline.** Solved within 10 calls of 40: no memory 8, frame 22, names 9, instruction 26, generic 28. Names minus instruction is −42.5 points (−64.9 to −20.1, plain t). On the one discrete-choice job, the names list buys Sonnet no efficiency. The reading "a list is enough where the fix is a discrete choice" therefore rests on Haiku `stack` alone. The README applies the within-10 lens to every Haiku and Luna cell and not to Sonnet.

3. **"A discrete choice, not a number" is confounded with the job.** There is one discrete job and two number jobs, and only Haiku has room on the discrete one. The related-work paragraph ("on `flasks` and `bins`, where the notebook stores a number") also skips that Haiku's notebook solves `bins` 0 of 40 times within 10 calls.

4. **"No clear label effect" lacks the within-10 caveat.** The generic sentence on Haiku `stack` solves 36 of 40 within 10 calls under the neutral label against 24 under the operator label, which is +30.0 points (+13.6 to +46.4). The within-10 table's naming-sentence column is also the operator-label arm, unlabelled; under the neutral label Haiku `bins` is 35, not 28.

5. **Smaller items.**
   - The finding 3 title and row 3 say six predictions missed; with B2 it is seven, or eight once B3 is rescored.
   - The limits and "Not done" still say "one model on one job" for the split.
   - "`code-dose` (which is `main`)" is stale.
   - Section 6k and PROTOCOL say "plain 95% intervals", but `paired_difference` returns the wider floored bootstrap interval (Haiku `flasks` names minus none prints −21.8 to +6.8, plain t gives −19.6 to +4.6). This is conservative but mislabelled.
   - "The Sonnet split, below" should read "above".

## B. Generator and checker

1. **6k deviates from v1.14's success rule** (item A1). The thresholds, the floor of 10 and 8 pairs, the hash and run-seed void, and the partial-miss reading are otherwise faithful. The split of `'('` in the reading breaks if a status carries the "fewer than the planned pairs" suffix.
2. **6j handles the uncovered case correctly.** Q1 and Q3 met with Q2 missed prints "the registered reading does not cover this combination", and the post hoc paragraph is labelled as such. The gate, the thresholds with tolerance, and Q4 "reported either way" are right.
3. **6j's gate-failed branch is unreachable at HEAD.** With the gate failed and no stage 2 files, the Q rows read "inconclusive", so the code falls through to "scored when the cell has finished". The uncommitted edit fixes this, but it has no test.
4. **No test covers the 6j or 6k scoring logic.** `tests/` has nothing for the readings, the gate or the `done` rule.
5. **Checker:** the import failure, the per-episode memory check, the run-seed ranges and the name manifest all work as described. The manifest hashes file names, not contents; the archive hash covers contents. `main_fixhold` and `main_fixcollide` share one manifest hash, which is correct because the names are identical.

## C. Critique per parameter

**Novelty (7.6).** The stated-budget cell is a real addition: a registered test showing a settings list does not buy efficiency on two jobs. The second model did not reproduce the part ordering, the "discrete against number" idea rests on one cell, and every catch is still one constant. The original cheap-against-frontier angle remains a ceiling.

**Rigour (8.6).** Registration before launch is verifiable, misses are reported, and the room gate for Sonnet was honest. A registered success rule was not applied and that flips a prediction. Ten-pair cells, no multiplicity correction, and a prediction (B3 Haiku) set on a cell with a 9-call minimum under a 12-call budget hold it down.

**Engineering (9.0).** Clean regeneration, a stricter checker with tests, and metered caps that held. Against that: a dead reading branch, no tests for the 6j and 6k logic, a mislabelled interval, and an uncommitted generator edit sitting on a published tree.

**Validity (8.2).** No simulator or parsing bug moves a number. The claims run ahead in A1 to A4: one "met" is a miss under the registered rule, and the headline reading is contradicted by the project's own second-model data on the measure the README now prefers.

**Clarity (8.3).** The one-screen table still works. "How to read this" in finding 3 is now a single paragraph of about 700 words holding the table reading, the whole budget cell and nine caveats. A stranger cannot find the budget result or tell which rule "solved" means.

## D. Best remaining step

1. **First, at no cost (about 40 minutes):** commit the `done`-rule rescoring with a test, mark B3 as MISSED for Haiku in README and PROTOCOL, add Sonnet's within-10 row, and split "How to read this" into a budget subsection.
2. **Then build the two-sided job, time-boxed.** Novelty is my lowest score and nothing else moves it. I said no last round; the budget cell has since used up the cheap alternatives.
   - **Design:** in `stack`, one cube per layout is heavy (needs `firm`) and one is fragile (a `firm` grip ejects or crushes it, so it needs `normal`). Which cube is which is randomised per layout and never shown. The fix is a procedure: try, read the finger gap, switch.
   - **Gate, 60 minutes maximum:** scripts using always-normal and always-firm each score at most 5 of 100, and a script that reads the gap scores at least 95 of 100. If the gate fails by then, stop and publish.
   - **Cell, registered and pushed first:** Haiku and Luna, run seeds 40 to 49, with four arms: no memory, the names list, a constant sentence ("use grip_level firm"), and own notebook after 12 episodes. That is 560 episodes, about $3 Anthropic and $3 OpenAI.
   - **Predictions:** the constant sentence solves at most 60%; the notebook beats both the constant and the list by at least 20 points for at least one model.
   - Either outcome is publishable: a notebook that stores a procedure beats any constant, or it cannot and practice only ever found constants.

**Next step:** apply item D1, then start the 60-minute gate for the two-sided job.

```json
{"novelty": 7.6, "rigour": 8.6, "engineering": 9.0, "validity": 8.2, "clarity": 8.3,
 "fixes": [
  "Score section 6k by the registered v1.14 rule (success AND done called within 12 calls): 36 held-out episodes are simulator-solved without done; Haiku bins notebook(12) minus names becomes 8 vs 0 = +20.0, so B3 is MISSED for Haiku; correct README finding 3, PROTOCOL v1.14 outcome and RESULTS.md (Haiku flasks +22.5, none 33 of 40; stack nb1 17 of 40), commit the pending analyze.py edit with a test.",
  "Add Sonnet's within-10 counts to finding 3 (none 8, frame 22, names 9, instruction 26, generic 28 of 40; names minus instruction -42.5, -64.9 to -20.1) and restrict 'a list is enough where the fix is a discrete choice' to Haiku stack; say the discrete-versus-number reading is confounded with job (one discrete job, two number jobs).",
  "Build the two-sided stack job (heavy cube needs firm, fragile cube fails under firm, identity randomised per layout) with a 60-minute gate (always-normal and always-firm scripts at most 5 of 100, gap-reading script at least 95 of 100), then a registered cell: Haiku and Luna, arms none / names list / constant sentence / own notebook (12), run seeds 40 to 49, about $6 total.",
  "Replace 'it mostly held' with the scored outcome (B1 met; B2 and B3 met for Luna, missed for Haiku) and fix the missed-prediction count in row 3 and the finding 3 title (six is now eight with B2 and B3).",
  "Add the within-10 caveat to the label bullet (generic sentence on Haiku stack: 36 neutral vs 24 operator label, +30.0, +13.6 to +46.4) and state that the within-10 table's naming column is the operator-label arm (neutral label gives 35 on Haiku bins, not 28).",
  "Add tests for the 6j and 6k scoring logic (gate-failed branch, which is unreachable at HEAD; the uncovered Q1-met-Q2-missed reading; the done rule; the partial-miss reading string), and relabel 'plain 95% intervals' in 6j/6k and PROTOCOL as the floored bootstrap interval paired_difference really returns.",
  "Split finding 3 'How to read this' (about 700 words in one paragraph) into a short reading, a 'stated 12-call budget' subsection with its own table, and a caveat list; fix stale lines (limits and Not done: 'one model on one job'; 'code-dose (which is main)'; 'Sonnet 5.5, below'; related-work sentence that ignores Haiku bins notebook 0 of 40 within 10)."
 ]}
```

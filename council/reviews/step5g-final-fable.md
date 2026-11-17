# Council round 5g, Fable judge (saved verbatim from the agent's final reply)

**Next action:** add a free "solved within 10 calls" table for every arm, model and job to RESULTS.md and the README. It overturns the claim that only Haiku on `stack` has room, and it narrows the headline negative to `stack`.

**State:** I recomputed sections 6h and 6i from the raw files and every reported count, percentage and paired difference matches. The archive SHA-256 matches, a clean copy without `logs/` regenerates RESULTS.md with an empty diff, and the checker reports 1,424 files clean. Both registrations reached origin before the first run file existed (6 s and 7 s). All eight memory texts in `runs/wordsplit2` match v1.11, the held-out layouts are identical across arms, and firm-grip counts are 40/40 names and 30/40 for frame and "change how you call it". I ran 35 tests (checker, wordsplit, analysis) in the copy and they pass; I did not run the full suite.

## A. README claims that are still wrong or overstated

1. **"Only Haiku on `stack` has room" (finding 3, finding 4, limits) holds only for success at 20 calls.** Counting an episode as solved only if it finished within 10 calls (run seeds 20 to 29, 40 episodes per cell) gives room everywhere, and the reminder stops matching the notebook outside `stack`:

   | cell, solved within 10 calls | no memory | generic sentence | own notebook (12 episodes) |
   |---|---|---|---|
   | Haiku `stack` | 8 | 36 | 31 |
   | Haiku `flasks` | 27 | 22 | 40 |
   | Luna `flasks` | 20 | 25 | 40 |
   | Luna `bins` | 0 | 0 | 28 |

   The "most useful single finding" sentence (README:212) generalises to "jobs whose catch is one constant among a few listed settings". `flasks` and `bins` are such jobs, and there the list buys nothing in efficiency while the notebook buys everything. This is post hoc, and the models ran under a stated 20-call budget.

2. **Row 4 and the finding 4 title, "one episode gets most of the way, three reach the ceiling", are overstated.** Three episodes give 94% pooled and 90% on the fresh seeds, the same as one and six. Twelve minus one is +15.0 points (+4.7 to +25.3 by a plain t interval), so "the steps between 1, 3, 6 and 12 cannot be told from zero" is true only for adjacent steps. Within 10 calls the curve is steep: 40/80, 60/80 and 58/80 for 1, 3 and 6 episodes, and 40/40 for 12 (fresh seeds only).

3. **"So the first failures are what teach it" (finding 4) is not shown.** Of the 20 single practice episodes, 13 failed outright. Held-out success is 28/28 after a solved practice episode and 40/52 (77%) after a failed one. Notebooks without "firm" still score 23/32, against 45/48 for those with it. The dose is closer to "has it solved the job once" than to an episode count, and the README should say that.

4. **"The instruction does help once it says 'settings'" (README:75) uses the wrong baseline.** The +30.0 is against no memory, where the frame alone already gave +17.5. Against the frame it is +12.5 (−8.6 to +33.6), and the pooled "change how you call it" minus frame is +10.0 (−5.4 to +25.4). "Both parts help" and row 3's "the instruction some, the frame little" are not supported: on the fresh layouts the frame did as much as the instruction.

5. **Smaller items:**
   - Adding "read the message" to the names lowered success from 98% to 88% (+10.0, +0.8 to +19.2 by plain t), and the README does not say so.
   - README:101 and README:220 still say "one wording per part" and "ten pairs".
   - README:220 says the wall-height design was "not built", without saying the threshold scan shows a constant would pass it.
   - README:106 still describes hash checks as needing `--expect`.
   - "One practice episode costs about 1 cent per run" includes the four held-out episodes.

The numbers of finding 3 and finding 4 themselves all match the raw files. The pooled primary (+27.5) is robust: 14 of 20 runs favour the names, none favour the instruction, and the sign-flip p is about 0.0001.

## B. Generator and checker

- **6h is faithful to v1.11.** Thresholds, the 10-pair and 8-pair floor, the void rule, the reading branches and every registered comparison are present.
- **R2 and R4 pass on exact float equality** (`&lt;= 0.65`, `&gt;= 0.10`). They pass today because the per-run means are quarters, but the code should compare integer counts (26 of 40 or fewer; a difference of 4 episodes or more).
- **6i omits a registered measure.** v1.12 registers "difference to 12 practice episodes" for every dose; the table prints only 12 against 6. Add 12 against 1 and 12 against 3 (+6.2, −4.4 to +16.9).
- **The pooled 12-episode cost ($0.027) is inflated.** `per_run_cost` does not filter phase for `nb12`, so the `rep_fixed` half includes four `eval_disturbed` episodes that the dose runs do not have. The README uses the fresh-seed $0.024, which is fine.
- **Dose relabelling and pairing are correct**, including the regex on `__p(\d+)__s` and the borrowed arms from `rep_fixed`, `wordsplit` and `wordsplit2`. The D1 floor counts pooled pairs, not the ten fresh runs, and 6i does not void when an anchor folder fails.
- **Checker:** the expected table sums to 1,424 and the six tests pass. `registered_text` returns `None` on any import failure, so the memory-text check can vanish silently. It checks the header field, not the per-episode `memory`, and has no per-folder run-seed range.

## C. Critique per parameter

**Novelty (7.4).** The names-against-instruction split and the dose cell are careful controls on a known idea (ExpeL, Voyager, PhysMem). The negative result is the distinctive part, and item A1 shows it is narrower than stated. The stated angle (cheap against frontier, disturbances, pose tools) ended in ceilings.

**Rigour (8.9).** Registration before launch is verifiable from the reflog and file birth times, the replication on fresh seeds held, and misses are reported. What holds it back is ten-pair cells, thresholds met at exact equality, no multiplicity correction, and a missing registered comparison in 6i.

**Engineering (9.0).** Byte-identical regeneration from a clean copy, a matching hash, and a checker with a documented table and tests. The remaining gaps are the silent text-check skip, the float thresholds and the cost-column phase bug.

**Validity (8.5).** I found no bug that moves a number. The claims run ahead of the evidence in A1 to A4, and the central limit ("only one cell has room") is an artefact of the 20-call success measure.

**Clarity (8.5).** The one-screen table and the printed arm texts work. Finding 3 is now a 600-word paragraph block with stale limits below it, and a stranger cannot tell that the calls measure tells a different story from the success measure.

## D. What raises the lowest score

Novelty is lowest. The single best move costs nothing: publish the within-k table (k = 8, 10, 12) for all arms, and restate the finding as "a settings list replaces the notebook where the catch is a discrete choice among listed values (`firm`), and not where the notebook stores a number (`grasp_height` 0.9, a release height)". That is a sharper and more defensible claim than the current one, and it takes about 30 minutes.

The one experiment I would still run confirms it under a real budget, registered first: `max_calls` 10 stated in the prompt, Haiku and Luna, three jobs, run seeds 30 to 39, arms none, names list, and own notebook after 1 and 12 episodes. That is 240 runs at about $4 in total across both providers and about 40 minutes. Predictions: the notebook beats the names list by at least 30 points on `flasks` for both models, and the names list is within 10 points of the notebook on Haiku `stack`. I would not build new physics for the rule-not-constant job in three hours.

**Next step:** fix A1 to A4 in the README, then add the within-10-calls table to section 6i and a matching section for 6f.

```json
{"novelty": 7.4, "rigour": 8.9, "engineering": 9.0, "validity": 8.5, "clarity": 8.5,
 "fixes": [
  "Add a 'solved within k calls' table (k = 8, 10, 12) for every arm, model and job; drop 'only Haiku on stack has room' and restrict the headline negative (README:212, finding 3 'How to read this') to stack, since within 10 calls the generic sentence gives 22/40 and 25/40 on flasks (Haiku, Luna) against 40/40 for the notebook and 0/40 against 28/40 on Luna bins.",
  "Rewrite row 4 and the finding 4 title: three episodes do not reach the ceiling (94% pooled, 90% fresh); add 12 against 1 (+15.0, +4.7 to +25.3) and 12 against 3 to section 6i, which v1.12 registered as measures; report the dose curve within 10 calls (40/80, 60/80, 58/80, 40/40).",
  "Replace 'the first failures are what teach it' with the split by practice outcome: held-out 28/28 after a solved single practice episode, 40/52 after a failed one; notebooks without 'firm' still score 23/32.",
  "Fix README:75 and row 3: the instruction with 'settings' is +12.5 (-8.6 to +33.6) over the frame, not shown to help; on fresh layouts the frame did as much as the instruction; state that adding 'read the message' to the names lowered success from 98% to 88%.",
  "Run one registered budget-10 cell (Haiku and Luna, three jobs, run seeds 30 to 39, arms none, names list, notebook after 1 and 12 episodes; about $4) to confirm the within-k result with the budget stated to the model.",
  "Generator: score R2, R4 and the D thresholds on integer episode counts instead of float equality; filter per_run_cost to practice and clean eval so the pooled 12-episode cost excludes eval_disturbed; make D1's floor count the ten fresh runs; void 6i when an anchor folder fails.",
  "Checker: fail (not skip) when robot_play cannot be imported for the memory-text check, compare the per-episode memory as well as the header, and add a per-folder run-seed range to EXPECTED.",
  "Remove stale limits (README:101 and README:220 'one wording per part', 'ten pairs'; README:106 '--expect'), and say in 'Not done' that the wall-height design fails because any high constant passes (results/release_threshold.md)."
 ]}
```

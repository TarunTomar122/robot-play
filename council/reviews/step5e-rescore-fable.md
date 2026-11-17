# Step 5e review (round 5e: re-score after the 5d fixes and the label-matched control) - judge: fable

Saved by the author from the judge's reply (condensed; scores and fix list as given). Read-only review. The judge confirmed: the label-matched cell was registered (commit 02:38:40 local) before its first run file (02:38:50) and episode (02:38:59); all 180 files carry hash `58b19ca1be3740fe`; pairing is correct (0 layout mismatches in 540 comparisons); the numbers in README finding 3 match RESULTS.md 6f; the mechanism holds in the logs (firm grip: inert 15 of 40, generic 36 of 40, naming 40 of 40); the archive regenerates RESULTS.md byte for byte; 133 tests pass.

## Remaining problems named
1. README says "every folder passes" the run-file checker; the recipe fails on `runs/spend/ledger.jsonl`.
2. "the settings the sentence lists": the generic sentence differs from the inert one in two ways (the list and the instruction to change settings one at a time); the supported claim is "its content, not the label or length".
3. The "inert" sentence is not fully inert (Luna `bins` 92% to 72%, -20.0, interval -40.3 to +0.3; "look at the scene again" may cost calls).
4. The headline contrast (+52.5 over inert) is the flattering one; generic minus fresh is +42.5 (+21.8 to +63.2).
5. L2 and L3 were near-certain when written; the registration reached GitHub only with the results (ordering rests on local timestamps).
6. Per-job reversal: Haiku `flasks` generic under the neutral label 85% against 95% fresh.
7. Stale times in README.md:9 and data/README.md; the run_seed default of 20 in the validation lets a header without a run seed pass.
8. The README is too long and too dense with intervals.

## Scores
```json
{"novelty": 7.0, "rigour": 8.4, "engineering": 8.6, "validity": 8.3, "clarity": 7.9,
 "fixes": [
  "Split the generic sentence under the neutral label on Haiku stack (list only, vary-instruction only, a shorter inert text without 'look again'), registered and pushed first; or reword README to 'the sentence's content'.",
  "Fix the false 'every folder passes' claim (checker skips runs/spend).",
  "Do not call the inert sentence inert without caveat; give generic minus fresh beside generic minus inert.",
  "State that the registration was pushed with the results and that L2 and L3 were near-certain.",
  "Add the three label-matched arms to results/firm_grip_audit.md.",
  "Remove the run_seed default of 20 in the validation.",
  "Fix stale times; mention the Haiku flasks reversal.",
  "Cut the README to a one-screen summary table."
 ]}
```

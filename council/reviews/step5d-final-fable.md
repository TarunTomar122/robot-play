# Step 5d review (round 5d: README rewritten around the final results) - judge: fable

Saved by the author from the judge's reply (condensed; the judge's scores and fix list are reproduced as given). Read-only review; the judge verified the archive (SHA-256 matches, regenerated RESULTS.md byte-identical), 130 tests, deviations 5 and 6 against `logs/quarantine_*`, the generator's scoring of 6c to 6e against the registered thresholds, and spend ($72.05 / $26.03).

## Verdict
Not publishable as it stood, about one hour of text edits away, no new data required. Main finding: the README's new headline rested on a mislabelled control: the "generic sentence naming no setting" in fact lists `grip_level`, `grasp_height`, `release_height` and `speed` (robot_play/runner.py), under the label "a hint from an experienced operator of this same task".

## Claims the judge found wrong or overstated (all addressed in the next commits)
1. "names no setting" is false for the generic hint (README, scripts/analyze.py, RESULTS 6d).
2. "the notebook carries one fact" overstates H1 (equality at a 100% ceiling; Haiku with its own notebook used no firm grip in 12 of 40 `stack` episodes).
3. The falsified H2 was not at the top of the README.
4. Dead links to the untracked firm-grip audit.
5. "three of three predictions met" should be three of four (S4 not testable), and v1.8 was registered after the hint result was known.
6. Q4: the control test had no room (fresh agents kept 94% and 96%).
7. Pose: raw calls instead of calls-to-success; Luna fresh falsely said done in 18 of 36.
8. "1 to 2% false done" is skill tools only.
9. `check_run_files.py` claim overstated (no hash check, silent skip of header-less files).
10. Deviation 5 omitted the 14 resumed files with outage abort records.
11. Related work had no links.

## Scores
```json
{"novelty": 7.1, "rigour": 8.3, "engineering": 8.4, "validity": 7.7, "clarity": 7.6,
 "fixes": [
  "Stop calling the generic hint 'naming no setting'; print the full sentence; reword the conclusion to 'a parameter shortlist plus permission to vary recovers 40 of 50 points on Haiku stack'.",
  "Put the registered reading at the top: H2 missed, headline weakened; replace 'carries one fact' with 'one sentence is sufficient to match it at a 100% ceiling'.",
  "Run a rule-not-constant job (bins with randomised wall height; arms none, own notebook, constant hint, rule hint, true placebo with the same label and no parameter names).",
  "Pose: report calls-to-success and Luna's false 'done'; qualify the 1 to 2% claim as skill tools only.",
  "Q4: add that the control test had no room.",
  "Commit results/firm_grip_audit.md and its script; explain the turn-only success.",
  "Deviation 5 and check_run_files.py: record the 14 resumed files; make the checker fail on unexpected hashes and header-less files.",
  "Say three of four predictions met and that v1.8 was registered after the hint result; rewrite related work with links."
 ]}
```

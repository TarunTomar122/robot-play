# Step 5b review (round 5b: mid-run re-check) - judge: fable

Date: 16 Nov 2026, 23:05 to 23:20. Read-only review of HEAD `032f664`, the `fix-false-hold` checkout at `9d402a7` and the `q5-borrowed`
checkout at `bedacd5`. No paid API call, no `.env` read, nothing written to `runs/`, `logs/` or `media/`; all my outputs are in `/tmp/fable5c/`.
`pytest`: 113 passed (main), 115 passed (fix), 113 passed (q5). I did not read Codex's 5a or 5b review.

## Verdict

**Let the matrix finish. Most of my 5a must-fix list is done and done properly. But the false `holding` I reported in 5a was a symptom, and
the cause is still in both the frozen simulator and the "fixed" rerun, so `runs/main_fixhold` will not settle what v1.5B says it settles.**

**The new finding (root cause of deviation 4).** `Motion.colliding` (`robot_play/motion.py:131-132`) sets the fingers to fully open
(`qpos[finger] = 0.04`) whenever nothing is attached. A failed `pick` leaves the hand closed (width 0.019 m). So the next `move_to` down onto
a cube is planned as collision-free for an open hand, the closed hand lands on the cube, and the tool answers `ok: true` with the hand 2 cm
high and 2 to 3 cm off sideways. I reproduced it on layout 20000 in both checkouts: request (0.396, 0.096, 0.02), result `tcp_m` (0.415,
0.098, 0.04), `touched: [cube_green]`, and the cube is pushed 6 mm sideways and 5 mm into the floor. With `open_gripper` first the same call
lands exactly. The false `holding` is what happens when the model then closes the hand; it is the second half of the same defect.

**How much of the headline cell this touches.** Haiku, `stack`, no memory, held-out, run seeds 0 to 9: 28 of 40 episodes contain such a
`move_to`, and **25 of the 27 failed episodes contain either it or a false `holding`** (8 with a false hold, 17 more with only the off-target
move). Run seeds 10 to 19: 24 of 31 failures. Notebook and replay arms: 0 of 80. Section 2a prints the 28 but builds its two sensitivity rows
from the 9 false-hold episodes only, and calls the +47.5 row "the worst case". It is not the worst case. If every failed episode touched by
the defect had succeeded, fresh would be 38 of 40 and the gap about +5 points.

**Why I still believe the direction.** I checked the physics by hand on three layouts: a clean manual grasp (open hand, `move_to` to z 0.02,
`close_gripper`, lift) leaves the heavy cube on the table at `normal` and lifts it at `firm`, 3 of 3 each. So the manual route also needs
`firm`, 28 of 40 fresh episodes never tried `firm`, and Luna finds it unaided (40 of 40). The defect wastes calls after the catch has already
beaten the model; it does not replace the catch. What nobody can say yet is how many of those 25 would have reached `firm` inside 20 calls if
`move_to` had told the truth. First look at `runs/main_fixhold` (4 of 10 fresh runs complete, so a peek and not a result): false holds 0 of
16, off-target moves still 7 of 16, fresh success 6 of 16 (38%, against 32% registered).

## What I verified

| 5a must-fix | Status | Evidence |
|---|---|---|
| Count false holds and short moves per model, job, condition, phase; sensitivity rows | **Done, with the understated bound above** | `analysis.py:53-74`, test at `test_analysis.py:282`; my own count from the run files gives the same 9 (8 failed), 13 (9 failed) and 28 |
| Q5 per-job table, calls with intervals, practice-only cost, break-even, label confound | **Done** | Report section 6: Haiku `stack` 13/40 fresh, 40/40 borrowed; calls -2.5 (-3.2 to -1.8) against own notebook; $1.40 against $0.023 and $0.015; break-even 24 and 5,433 episodes |
| Matched runs in the "same runs" table, section numbers, stale seed text | **Done** | 27 and 26 runs in every row except replay (20), which is labelled by its own count |
| Timing of the 22:24 floor, what was read at 21:40 | **Done, honestly** | PROTOCOL 10 item 10 and deviation 1 addendum; deviation 2 addendum says "my recollection, not a recorded fact" |
| Hash per folder, `main_ext` in the check | **Partly** | Table is there; `runs/main_fixhold` (`c694b1a45aaf30c5`) is not in it although section 6b says "listed in section 1" (`analyze.py:148-150` reads `cov + ext_cov` only) |
| Deviation 3 stated as outcome-independent | **Done** | Addendum 22:54 |
| Notebook audit states its threshold change; stale-held audit corrected | **Done** | Both regenerated to `/tmp/fable5c`; the stale-held file now attributes 7 of 10 hits to false holds |

**New cells.**

| Check | Result |
|---|---|
| Registered before running | v1.5 committed 22:56:23, first `borrowed_1` file 22:56:31. v1.5B committed 23:02:18, first `main_fixhold` file 23:02:26. Both predictions are in the registration commits. The margins are 8 seconds, so "before any result" is true and "blind" is not: the v1.5 prediction was written knowing the audit, v1.5B knowing the +48 bound |
| Right code ran | `scripts/run_experiment.py` puts its own checkout first on `sys.path`, the processes' working directories are the two worktrees, and the headers carry `90bd12fc77ec6f43` (58 of 58) and `c694b1a45aaf30c5`, not the matrix hash |
| `borrowed_1` integrity | 58 of 58 headers hold exactly Fable's notebook after practice episode 1 of the matching run, 0 of 58 equal the final notebook, no practice, layouts 20000 + 100 x run seed + 0..3, memory never changes |
| `borrowed_1` result | 232 of 232 solved; Haiku `stack` 40 of 40, so the prediction (at least 90%) holds. A $0.13 notebook does what the $1.40 one does |
| Fix is minimal | Two lines in `skills.py:104-110`, nothing else under `robot_play/` differs from `matrix-launch`. The test replays the logged calls of layout 10302 and a real `firm` hold still reports `holding` |
| No contamination | `analyze.py` loads `runs/main_fixhold` only through `--fixhold` into `fix_rows`, never into `rows`; borrowed conditions never match `none` or `notebook` selects; `run_night.sh` does not touch these folders. The risk left is human: the fixhold files have the same run names as the registered ones |
| Video | `media/claude-haiku-5-5-stack-eval_disturbed1-d2.mp4` is `runs/main/claude-haiku-5-5__stack__notebook__quirk__p12__s7`, disturbed layout 20701. My replay gives **13 of 13 call results byte-identical** to the log, success, disturbance fired |
| Coverage | `results/coverage_sim.md` exists and runs the real `paired_difference`. Lowest row 95.8% (Luna-like). My own 200 repetitions: 94.5% for 0.96 against 1.0, and 0 of 200 false exclusions of zero with no effect at 0.97 |

## What would still mislead in the morning report

1. **"+68 points" or "+48 in the worst case" for Haiku on `stack`.** The honest sentence is: 25 of 27 fresh failures contain a `move_to` or
   `close_gripper` answer that a correct simulator would not have given, the gap is somewhere between about +5 and +68, and the reasons to
   think it is large are the firm-only physics and the 28 episodes that never tried `firm`.
2. **Presenting `main_fixhold` as "the artefact removed".** It removes the false sentence and keeps the cause. Its own table will show the
   short-move column non-zero; the text must say so, and deviation 4 promised "report a stop short", which v1.5B dropped without saying.
3. **"Experience transfers from a frontier model."** One successful episode's notes are enough (40 of 40), Fable solves everything on its
   first try, and a replay does the same. The finding is "one line of advice fixes Haiku on one job", and the control that would show it
   (a one-line hint, or a notebook Fable writes with no practice) was not run.
4. **The headline chart** (`make_headline_chart.py`): bars in one group are not matched runs and carry no run counts (the flasks replay bars
   rest on a handful of runs), the frontier lines are 20 layouts per job from run seeds 0 to 4 while the bars are seeds 0 to 9, and the 32 bar
   has no artefact mark.
5. **The video caption** does not say it is the notebook arm, that the model uses the 45 degree grasp and not `firm`, or that it is a chosen
   success (notebook arm under disturbance is 96%; the fresh arm is 66%).
6. **Luna's Q1** (+8.3, 97.5% interval +0.6 to +16.1) rests on flasks with 7 complete pairs so far and sits in the regime where coverage is
   about 95%, not 97.5%. PROTOCOL 1 still says "94 to 95%" for the 0.95 against 0.99 case, for which the committed simulation now says 98.0%.
7. **Small report defects.** Section 6a's per-job table is empty until `borrowed_3` has rows (`analyze.py:448-451` intersects with an empty
   arm), so the one table that checks the registered prediction prints nothing; the hash sentence blames deviation 2 for hashes that come
   from v1.5 and v1.5B; PROTOCOL section 10 is still headed "everything below happened before any reported run".

## The single highest-value thing left

**Fix the cause, register it, and rerun the one cell: about $1 and 25 minutes.** On a third branch from `fix-false-hold`: make `colliding`
use the real finger opening when nothing is held (or, more simply, make `move_to` fail like `pick` does when it stops more than 1.2 cm from
the request, with the message "hand stopped short, touching X"). Add a test from my reproduction (failed `pick`, then `move_to` onto the
cube must not answer `ok: true`), rerun the five validation gates on that hash, write the prediction first, and run Haiku `stack`, `none` and
`notebook`, run seeds 0 to 9 into a new folder. Report all three simulators side by side. That one table turns the validity question from a
bound nobody can compute into a measured number, and it is the number the whole Q1 and Q5 story stands on.

## Scores

**Novelty 6.8.** `borrowed_1` is a sharp, cheap, pre-registered addition and its answer is clean. But it also shows the "experience" is a
one-line recipe from a model that never fails, in one job; the zero-practice or one-line-hint control is still missing, and Q4 and the pose
cell (the other two new axes) have no data yet.

**Rigour 8.2.** Predictions are in the registration commits, the borrowed notebooks check out 58 of 58, intervals are implemented as written
and the coverage simulation is reproducible. Held back by a sensitivity row called "worst case" that is not (`analyze.py` section 2a), a
rerun that fixes the symptom, the Q5 label confound (disclosed, not removed), and registrations seconds before launch by an author who had
seen the neighbouring data.

**Engineering 7.6.** Tests pass in all three checkouts, hashes separate the cells, the fix is two lines with a test from a real log. Down
from 7.8: the planner's open-hand assumption (`motion.py:131-132`) was never diagnosed although the report counted its symptom 28 times,
`pick`'s "closed on nothing" check (`skills.py:185`, width under 0.004) looks unable to fire because an empty closed hand reads 0.019, `main_fixhold` is
missing from the hash table, and section 6a prints an empty table.

**Validity 7.0.** Down from 7.2. The report now counts the artefact honestly, but the cause reaches 25 of 27 failures in the cell that carries
Q1 and Q5, only on the fresh side, and the printed bound covers 8 of them. The direction is well supported (firm-only physics checked by
hand, Luna 40 of 40, notebooks 0 of 80 affected); the size is not known and the running rerun will not make it known.

**Clarity 8.0.** Section 6 is now a model of an honest exploratory section and the deviations file is dated to the minute. Held back by the
headline chart (unmatched bars, no counts, no artefact mark), the video caption, the stale section 10 heading, the 94 to 95% figure that the
committed simulation no longer shows, and no README results yet.

```json
{"novelty": 6.8, "rigour": 8.2, "engineering": 7.6, "validity": 7.0, "clarity": 8.0,
 "fixes": [
  "Root cause of deviation 4: Motion.colliding (robot_play/motion.py:131-132) sets the fingers fully open whenever nothing is attached, so after a failed pick (hand closed at 0.019 m) a move_to onto a cube is planned as free, lands on the cube and answers ok:true 2 cm high and 2-3 cm off sideways (reproduced on layout 20000 in both the matrix and the fix-false-hold checkout). On a new branch make colliding use the real finger opening, or make move_to fail when it stops more than 1.2 cm short as pick does; add a test from that reproduction; rerun the five gates; register a prediction; rerun Haiku stack none and notebook, run seeds 0-9 (about $1) and print all three simulators side by side.",
  "Section 2a of analyze.py: the 'worst case' row uses only false-hold episodes. In Haiku stack no-memory held-out, 25 of 27 failures (run seeds 0-9) and 24 of 31 (seeds 10-19) contain a false hold or an off-target move_to that answered ok. Add a third sensitivity treatment over episodes with either flag (fresh 38 of 40, gap about +5 points), stop calling +47.5 the worst case, and state the reasons the direction still holds: a clean manual grasp lifts the heavy cube only at firm (3 of 3 layouts), 28 of 40 fresh episodes never tried firm, Luna 40 of 40.",
  "Section 6b and PROTOCOL v1.5B: say that main_fixhold removes the false 'holding' but not the closed-hand move_to (first 16 fresh held-out episodes: false holds 0, off-target moves 7, success 6 of 16), that deviation 4 promised 'report a stop short' and v1.5B did not do it, and add runs/main_fixhold to the hash table (analyze.py:148-150 reads cov + ext_cov only, yet 6b says its hash is listed in section 1).",
  "Q5 wording and the missing control: borrowed_1 is 232 of 232 (Haiku stack 40 of 40) with a $0.13 notebook written after one successful episode, so the claim is 'one line of advice fixes Haiku on one job', not 'frontier experience transfers'. Run the cheapest control that tests it: a fixed one-line hint per job, or a notebook Fable writes with no practice, same label, same layouts (about $0.20).",
  "analyze.py:448-451: the per-job table of section 6a is empty while borrowed_3 has no rows because the run intersection includes an empty arm; intersect only arms that have data and print the registered prediction with its verdict (Haiku stack 40 of 40, at least 90% predicted). Fix the hash sentence that blames deviation 2 for the v1.5 and v1.5B hashes.",
  "scripts/make_headline_chart.py: use the same complete runs in every bar of a job, print the run and episode counts under each group, draw the frontier lines only over the layouts they played (run seeds 0-4, 20 per job) or say so, and mark the Haiku stack no-memory bar with the artefact note. Caption the disturbance video as the notebook arm of run seed 7, layout 20701, a chosen success using the 45 degree grasp (my replay matches the log on 13 of 13 calls).",
  "PROTOCOL.md: section 1 says 94 to 95% coverage for the 0.95 against 0.99 case while results/coverage_sim.md now gives 98.0% for it and 95.8% for the Luna-like case; quote the committed table. Rename section 10 ('everything below happened before any reported run' is false from v1.4 on) and bump the title from v1.3. Remove or repair the dead 'fingers closed on nothing' check in skills.py:185 after the matrix (an empty closed hand reads 0.019 m, the check needs under 0.004).",
  "Luna Q1 (+8.3, 97.5% interval +0.6 to +16.1): report it with the per-job row beside it (the gain is flasks, 7 complete pairs at the time of this review), the coverage of about 95% for that regime, and no stronger word than 'small and borderline'."
 ]}
```

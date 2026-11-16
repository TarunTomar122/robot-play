# Step 5a review (round 5a: mid-run, matrix still running) - judge: fable

Date: 16 Nov 2026, 22:40 to 23:05. Read-only review of HEAD `8110399` and the `q5-borrowed` checkout at `302a7fc`. No paid API call, no `.env`
read, nothing written to `runs/`, `logs/` or `media/`. `pytest`: **111 passed** in 16 s. `scripts/analyze.py`, `notebook_audit.py` and
`stale_held_audit.py` were run with `--out`, `--img` and `--meter` pointing to `/tmp/fable5a` (the meter pointed to an empty scratch folder, so
`runs/spend/lock` was not touched; I read `runs/spend/state.json` as a plain file). I did not read Codex's round 5a review.

## Verdict

**Do not stop the matrix.** The run files are clean and the analysis rules are implemented as written. But the morning report is not ready
to carry a headline yet, for one new reason that I got wrong in round 4 and four reasons of wording.

**The new finding (my round-4 scoping error).** I said the false `holding` from `close_gripper` touched only the pose cell. It does not. The
skills toolset also has `move_to` and `close_gripper`, and Haiku with no memory uses them by hand after the default `pick` fails on the heavy
cube. In `runs/main`, Haiku, `stack`, no memory, clean held-out episodes (run seeds 0 to 9): **9 of 40 episodes contain a `close_gripper` that
answers `holding: cube_green` at a finger width of about 0.02 m for a 0.04 m cube** (the closed fingertips rest on top of it), and 8 of those 9
failed. Run seeds 10 to 19: 13 of 40, 9 failed. Example: `claude-haiku-5-5__stack__none__quirk__p12__s3`, practice 2, calls 5 to 9: `move_to`
returns `ok: true` at z = 0.042 for a request of 0.03, `close_gripper` says `holding`, `pick` then answers `already holding cube_green`, and
`place` answers `not holding anything`. Four calls of a 20-call budget are spent on a false statement, in the one cell that drives Q1 and Q5,
and almost only in the fresh arm (notebook arm: 0 such held-out episodes).

This does not create the effect. Of the 40 fresh episodes, 28 never tried `grip_level: firm` and 25 of those failed; 10 of the 12 that tried it
succeeded. The catch is doing the work. But the size of the Haiku stack gap has a bound that must be printed: if every failed false-hold
episode had succeeded, fresh would be 21 of 40 (52%) and not 13 of 40 (32%), so the stack gap would be about +48 points and not +68.

## What I ran

| Check | Result |
|---|---|
| Integrity of every run file (header, torn lines, duplicate episodes, plan order, row fields against header) | `main` 129 files, `main_ext` 60, `frontier` 6, `frontier_exp` 30, `borrowed` 58, `borrowed_other` 58: **0 missing headers, 0 torn lines, 0 duplicate episodes, 0 plan mismatches, 0 refusals** |
| Code hashes | `main`, `main_ext`, `frontier`, `frontier_exp`: all `4d59e8f26cd2a9b6`. `borrowed`: run seeds 0 to 4 `1cd309b2c89e94d7` (30 files), run seeds 5 to 9 `bdda918f09675319` (28). `borrowed_other`: all `bdda918f09675319`. This matches the addendum to deviation 2 |
| Borrowed notebooks against their source | 58 of 58 `borrowed` headers hold exactly the final notebook of the matching Fable run; 58 of 58 `borrowed_other` headers hold the notebook of the shifted job; no practice episode, memory never changed, layouts 20000 + 100 x run seed + 0..3 |
| Unsamplable layout (deviation 3) | I scanned all 1,920 practice and evaluation layouts of run seeds 0 to 19, three jobs, both scenes: **only flasks 20801 fails, in both scenes**. The claim is correct |
| Coverage of the three-piece Q1 interval (400 repetitions each, nominal 97.5%) | No effect, mixed rates: 97.0%. Haiku-like (stack 0.3 to 1.0, others at 0.99): 99.0%. Small gap with every arm near ceiling: **95.3%**. All at 0.97: 99.8%. This agrees with the 94 to 99.6% that PROTOCOL 1 states |
| Spend at 22:50 | Anthropic $56.1 of $90, OpenAI $15.9 of $45 (metered), 1 `settle_unknown`, no sign of the outage risk R2 |
| Fable with a notebook | 360 of 360 practice episodes and 116 of 116 held-out episodes solved; the notebook names the fix after practice episode **1** in 29 of 29 runs |

## (1) Analysis-rule changes

| Rule in deviation 1 and PROTOCOL 1 | Code | Verdict |
|---|---|---|
| Wider of percentile bootstrap and stratified t (k minus h degrees of freedom, pooled within-task variance) | `analysis.py:92-97`, `_pooled_ss` 101-110; `did` 304-309 | As written. Tested at `test_analysis.py:204` |
| Binomial sampling-noise floor for Q1 and Q4 | `_floor_half` 113-123, `paired_difference` 154-161, `recovery_drop_difference` 373-376 | As written (it is also applied to every exploratory success difference, which only widens). Tested at 253 and 267 |
| Q3 whole four-layout clusters, cost on matched layouts | `q3_gap` 239, `q3_cost` 266-273; `analyze.py:228` | As written. Tested at 243 |
| Q3 intraclass correlation from notebook runs only | `intraclass` 194-215 | As written |
| Report states code hashes and never-started cells | `analyze.py:146-162` | Partly. It prints the hashes but not which cell has which; `runs/main_ext` is left out of the check (`cov` at line 109 has no `--ext` folders); it reports and does not refuse to pool |

**Over-claims in the text.** (a) "Before any confirmatory result was analysed" is too strong for the 22:24 floor. The Q5 table read at 21:57
(night log) contains Haiku's no-memory and own-notebook success on run seeds 0 to 4, which is half of the Q1 data. The floor can only widen an
interval, so no harm follows, but the sentence should say what had been seen. (b) The pooled t interval assumes equal variance in the three
jobs; in the real data all the variance sits in `stack`. My simulation of that case still covered 99% because the bootstrap piece takes over,
so this is a note and not a defect. (c) Coverage at 94 to 95% in the near-ceiling case is disclosed; the Luna rows are that case and the
report should repeat it next to them.

## (2) Exploratory cells

**Integrity: passes** (table above). Two notes. The ten files deleted in deviation 2 were not kept in `runs/_archive`, so nobody can check
that the deletions were blind to outcomes; only the ledger remembers them. And the wrong-task control was committed at 21:40 while the
rerun matching cell was two minutes into its run (first episode 21:37:48, last 21:46:23); PROTOCOL should say whether any borrowed result had
been read by then. The control cell itself started at 21:46:47, after its registration.

**Does the wrong-task control separate content from presence? Mostly yes.** Haiku on `stack`: fresh 13 of 40, wrong-task notebook 12 of 40,
matching notebook 40 of 40. A confident notebook about another job does nothing. Three limits the report must state:

1. **The whole Q5 success effect is one job.** Per job, Haiku fresh against borrowed: `stack` 13/40 against 40/40, `bins` 40/40 against 40/40,
   `flasks` 12/12 against 36/36. Luna: 40/40, 37/40 and no data yet against 40/40, 40/40, 36/36. The pooled "+31 points" is "Haiku learns
   `grip_level firm` from one line", repeated over ten run seeds.
2. **The labels differ.** The matching notebook is introduced as written by "a more capable assistant" (`agent.py` in the branch, line 89),
   the model's own notebook as "written by you", and the wrong-task one adds "it may or may not apply". So borrowed against own mixes
   content with an authority cue, and matching against wrong-task mixes content with a warning. A fair statement is "content matters";
   "Fable's notes are better than Haiku's own" is not shown.
3. **On success the borrowed notebook is not better than the model's own.** Haiku +1.2 points (95% interval -2.8 to +5.3), Luna 0.0. The
   difference is in calls: Haiku -3.4 calls to success (-4.4 to -2.4), Luna -1.0 (-1.8 to -0.1), which I computed with `paired_difference`;
   the report has no interval for it.

**Is the cost comparison honest? Not yet.** (a) The "$1.58 for Fable's practice and notebook writing" (`analyze.py:292-295`) includes the four
held-out episodes ($0.18); practice alone is $1.39. (b) The cheap side "$0.024" is the whole notebook run including evaluation; practice alone is
$0.024 for Haiku and $0.016 for Luna, so the protocol's "$0.016" is Luna's number only. (c) Fable's notebook names the fix after one practice
episode in 29 of 29 runs and Fable never failed an episode, so eleven of the twelve practice episodes bought nothing that the audit can see; a
one-episode notebook would cost about $0.13. That was not tested and the report should say so, and not present $1.6 as the price of a useful
notebook. (d) The break-even is missing. Fable's own first try solves 60 of 60 at $0.060 an episode; Haiku with the borrowed notebook costs
$0.0007 an episode, so the $1.39 is repaid after about 23 episodes of the same job against running Fable directly. Against Haiku's own
notebook ($0.024, 99%) the borrowed one saves $0.0004 an episode, so it is repaid after about 3,400 episodes.

**What else the report must say.** Replay matches the notebook (Haiku `stack` 40/40 for both), so one successful transcript is enough and the
notebook is not special. Fable's notebook is a strong model's working recipe written after zero failures, so Q5 is not "experience transfers";
a notebook Fable writes with no practice at all is the missing control. One frontier writer, one family pair with a real effect.

## (3) Deviation 3

**Defensible.** The crash is decided by the layout seed before any model call, in every cell and every condition, so dropping run seed 8 of
`flasks` cannot select on outcomes; 29 of 30 pairs is above the registered 24. Changing the sampler mid-matrix would have been worse. Three
additions: say in the report that the exclusion is outcome-independent; give a sensitivity row that uses the three layouts of run seed 8 that
can be played; and admit the engineering miss, because a one-second scan of the planned seeds (which I ran) would have caught it before launch
and saved the $1.2 Fable run that crashed at episode 13.

## (4) Scripts

- `notebook_audit.py`: the 0.85 to 0.8 change is disclosed in the docstring, which promises "this is stated in the report", but the generated
  file does not state it. Print it, and print both thresholds. The keyword check is weak for `bins`: Haiku's final notebook "names the fix" in
  1 of 20 runs yet solves 99%, so the table mostly measures wording. Folders passed together are pooled (`main` and `main_ext` gave 20 runs).
- `stale_held_audit.py`: the commit says "negative on live data". It printed 10 hits for me, and six of them follow `move_to > move_to >
  close_gripper`: they are the false `holding` above, a different defect that this script found and its author did not read. It also catches
  only the cases where a `pick` followed.
- `make_llm_videos.py`: the replay must match the logged outcome or the file is deleted, which is right. `pick_borrowed` selects a layout
  that failed fresh and passed with the notebook, so the caption or README must call the pair a chosen illustration.
- `make_q5_chart.py`: bars at 100% get a zero-width error bar (`A.bootstrap` has no floor), and the docstring's "same runs in every bar" is
  not true while `main` is incomplete and never true for the wrong-task bar (it lacks `bins` run seed 8).

## (5) What would mislead in the morning report

1. "Experience raises success" without "in one of six cells". Haiku `stack` is +68 points; every other cell is within noise of zero.
2. Any Haiku `stack` number without the false-hold count and the bound next to it.
3. "A cheap model with Fable's notebook matches the frontier" without "the frontier is at 60 of 60 on its first try, Haiku's own $0.02
   notebook reaches 99%, and Luna reaches 96% with nothing".
4. The table headed "same layouts in every row" (`analyze.py:316`): its rows have 88, 80, 116 and 112 episodes.
5. Two sections numbered 5, no section 6, and the Q5 text still says "run seeds 0 to 4" and "five run seeds" (`analyze.py:296-297`).

## Before the final report, and what can wait

**Must change before the final report (all analysis or text, no run is touched):**

1. Count false `holding` episodes (a `close_gripper` result of `holding` at a width more than 5 mm under the object's width) and `move_to`
   results more than 1 cm from the request, per model, job, condition and phase, in the skills cells too. Print them beside Q1, Q5 and the
   room cells, with two sensitivity rows: those episodes dropped from both arms, and those episodes counted as fresh successes.
2. Q5: per-job table, the calls-to-success difference with its interval, practice-only costs on both sides, the one-episode note, the two
   break-even numbers, the label confound, and the replay row beside the notebook row.
3. Fix the "same layouts" table by intersecting runs across its rows, the section numbers and the stale seed text.
4. Correct "before any confirmatory result was analysed" for the 22:24 floor, and say what had been read at 21:40.
5. Print which folder carries which code hash, include `runs/main_ext` in that check, and state deviation 3 as outcome-independent with
   the three-layout sensitivity row.
6. State the notebook-audit threshold change inside `results/notebook_audit.md`.

**Can wait until after the matrix:** fix `close_gripper` (attach only when the finger width matches the object) and make `move_to` report a
stop short; add a test that every planned layout can be sampled; a Fable notebook written with no practice; the same label on every borrowed
arm; a second frontier writer; archive deleted files and never delete them; a floor on the chart error bars.

## Scores

**Novelty 6.7.** Q5 with a wrong-task control (PROTOCOL v1.4) is a real, cheap, new angle next to RoboARCade and WICL. It is held back because
both frontier models solve 60 of 60 unaided and Fable never fails in practice, so "frontier experience" is a recipe, and the effect is one job.

**Rigour 8.0.** The three-piece interval is implemented as written (`analysis.py:92-97, 113-123, 154-161`) and I reproduced its coverage; the new
cells were registered before they ran and the replication is labelled. Held back by the label confound in the Q5 arms, the over-stated
"before any confirmatory result" for the 22:24 floor, deleted files that were not archived, and no refusal to pool across hashes.

**Engineering 7.8.** Run files are clean in all six folders and the spend ledger is healthy. Down from 8.2: an unsamplable planned layout that
no test caught (`env.py:19-26`), an edit to a live checkout that changed a hash mid-cell (deviation 2), `runs/main_ext` outside the hash check
(`analyze.py:109`), and a report with two sections 5.

**Validity 7.2.** Down from 7.6. The false `holding` (`skills.py:104-109`) is in 9 of 40 and 13 of 40 fresh Haiku `stack` held-out episodes of
the confirmatory cell, on the side that makes the Q1 and Q5 gaps larger, and `stale_held_audit.py` was read as negative. The direction of the
effect is safe (25 of 28 episodes that never tried `firm` failed); its size is not, until the bound is printed.

**Clarity 7.8.** PROTOCOL 10 and `results/deviations.md` are candid and dated to the minute. Held back by the mislabelled Q5 table
(`analyze.py:316`), the stale Q5 text (296-297), the $1.58 and $0.024 labels (329), and an audit file that omits its own disclosed change.

```json
{"novelty": 6.7, "rigour": 8.0, "engineering": 7.8, "validity": 7.2, "clarity": 7.8,
 "fixes": [
  "Do not stop the matrix. In analyze.py count, for the skills cells as well as pose, episodes where close_gripper answers holding at a finger width more than 5 mm under the object's width and move_to results more than 1 cm from the request, per model, job, condition and phase. In runs/main Haiku stack no-memory held-out this is 9 of 40 episodes (8 failed) on run seeds 0-9 and 13 of 40 on seeds 10-19, against 0 in the notebook arm. Print the counts beside Q1, Q5 and the room cells with two sensitivity rows: those episodes dropped from both arms, and counted as fresh successes (stack gap about +48 instead of +68 points).",
  "Q5 section of analyze.py: add a per-job table (the whole success effect is Haiku on stack, 13/40 fresh against 40/40), the paired calls-to-success difference with its interval (Haiku -3.4, Luna -1.0 against their own notebooks; success difference +1.2 and 0.0, not significant), and say plainly that the borrowed notebook is not better on success than the model's own $0.02 notebook or than replay.",
  "Q5 cost (analyze.py:292-295, 329): use practice-only cost on both sides ($1.39 Fable; $0.024 Haiku, $0.016 Luna), state that Fable's notebook names the fix after practice episode 1 in 29 of 29 runs and Fable solved 360 of 360 practice episodes, so about $0.13 might buy the same notebook (untested), and give the break-even: about 23 episodes against running Fable directly ($0.060 an episode, 60 of 60), about 3,400 against Haiku's own notebook.",
  "Fix the report text: the table headed 'same layouts in every row' (analyze.py:316) has 88, 80, 116 and 112 episodes, so intersect the runs; two sections are numbered 5; lines 296-297 still say run seeds 0 to 4 and five run seeds; print which folder carries which code hash and include runs/main_ext in that check (line 109).",
  "PROTOCOL 1 and deviation 1 addendum: 'before any confirmatory result was analysed' is too strong for the 22:24 floor, because the Q5 table read at 21:57 shows Haiku's no-memory and notebook success on run seeds 0-4; say so, and say whether any borrowed result had been read when the wrong-task control was committed at 21:40 (the matching cell ran 21:37 to 21:46). State the label confound: 'a more capable assistant' against 'written by you' against 'may or may not apply'.",
  "Deviation 3 is defensible; add that the exclusion is decided by the layout seed before any model call, add a sensitivity row on the three playable layouts of flasks run seed 8, and after the matrix add a test that every planned layout can be sampled (a scan of 1,920 layouts takes seconds and finds only 20801).",
  "scripts/notebook_audit.py: write the 0.85 to 0.8 change and both thresholds into the generated file (the docstring promises it, the output omits it) and note that the bins keyword misses most working notebooks (1 of 20 Haiku notebooks 'names the fix' at 99% success). scripts/stale_held_audit.py: six of its ten hits follow move_to > move_to > close_gripper and are the false holding, so 'negative on live data' is wrong.",
  "After the matrix: make close_gripper attach only when the finger width matches the object and make move_to report a stop short (skills.py:104-109, 121-128); add a Fable notebook written with no practice and one label for every borrowed arm; archive rather than delete run files; give the Q5 chart a floor on its error bars and call the video pair a chosen illustration."
 ]}
```

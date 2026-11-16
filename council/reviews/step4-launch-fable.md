# Step 4 review (round 4: launch check, matrix already running) - judge: fable

Date: 16 Nov 2026, 21:12 to 21:20. Read-only review of HEAD `6994f96` (the launch revision `9e446d1` plus one commit that adds only
`scripts/notebook_audit.py` and the brief). Code hash on disk `4d59e8f26cd2a9b6`, the same as `logs/code_hash.txt`. No paid API call, no `.env`
read. `pytest`: **108 passed** in 15 s. I did not read Codex's round 4 review.

One disclosure: to read the spend totals I called `SpendMeter('runs/spend').totals()` once. That call opens `runs/spend/lock` for a fraction of
a second (an empty lock file; the ledger and the state file were not changed). Everything else under `runs/` and `logs/` was read with plain file reads.

## Verdict

**Do not stop the matrix.** Every round-3 must-fix item is really fixed, and I found nothing in `robot_play/` that corrupts a confirmatory cell
(main, control, frontier). Two residual tool behaviours touch **only the exploratory pose cell** and can be handled by counting them in the logs.
The one thing that matters now is analysis-only: the pre-registered small-sample factor is almost a no-op at 30 clusters, so the Q1 and Q4
"97.5%" intervals cover about 95.5 to 96.5%. That should be written down as a deviation **before** `analyze.py` is run on any matrix data.

## What I ran

| Probe (scripted, layouts 60300+, used by nothing else; nothing written) | Result |
|---|---|
| Pose, stack catch, default squeeze, lift, `observe` | Cube on the table, `held: false`, `holding: null` in **6 of 6** (round 3: stale in 8 of 8) |
| Skills, `pick` green with `lift_height=0.05`, one `move_to`, `observe`, `place` | `held: false` in 6 of 6; `place` answers `not holding anything` (round 3: stale in 4 of 4) |
| False detach: `pick` then three moves (fast, normal, fast), all three jobs, catch and control | **144 checks, 0 mismatches** between "object is up in the hand" and `held` |
| Pose, firm squeeze, carry slow and fast | Lost 0 of 6 at each speed, `held` true throughout |
| Pose, after the drop, descend with the fingers still closed, then `close_gripper` | `move_to` returns `ok: true` with the hand at z = 0.042 for a request of 0.024 and `touched: []`; `close_gripper` then says `holding: cube_green` at width 0.02 (6 of 6). The fingertips rest on top of the 4 cm cube. The next move clears it (R1) |
| Coverage of the pre-registered interval rule (3,000 repetitions, run means in quarters) | Q1 and Q4 (3 jobs x 10 runs, nominal 97.5%): 95.1% raw, **95.5%** with sqrt(k/(k-1)). Q3 bootstrap (3 x 5, nominal 98.75%): 95.6%. Pose (3 x 3, nominal 95%): 84.2% |
| The same data with a stratified t interval (20,000 repetitions) | 97.5%, 98.7% and 95.1%: on target in all three |
| Live run files at 21:15 (11 files, 152 episodes) | All carry code `4d59e8f26cd2a9b6`, protocol 1.3, budget 20. 0 aborts, 0 refusals, 0 notes, 0 `observe` lines with a held object lying below the hand |
| Spend ledger at 21:16 | 9,191 reservations, 9,184 settled, 0 released, 0 unknown, 0 overruns |
| Cost so far, list price per episode | Fable $0.057, Astra $0.104, Haiku $0.0023, Luna $0.0008. Projected about $35 to $40 Anthropic and about $25 metered OpenAI: inside both caps |

## (1) Round-3 must-fix items

| Item | Status | Evidence |
|---|---|---|
| Stale held state | **Fixed** | `skills.py:72-76`, called in `observe` (80), `close_gripper` (102, 105), `move_to` (127), `place` (226); `test_tools.py:69`; my probes above. All five gates were rerun after the last edit of `skills.py` (20:51:02): result files are dated 20:57 to 21:07 |
| Truncated replies | **Fixed** | `agent.py:153` aborts on any `max_tokens` turn; `llm.py:264-265` drops the calls of an incomplete OpenAI response; `test_agent.py:219`, `test_llm.py:135,153` |
| Refusals | **Fixed** | `llm.py:263,266`, `agent.py:157`; `test_llm.py:142`. The test named `test_a_refusal_with_a_call_is_recorded_as_a_refusal` sends a turn with **no** call, so its name is wrong, but the code path is right |
| Run hash covers the Panda assets | **Fixed** | `runner.py:35-54`: every XML, OBJ, STL and PNG under `franka_emika_panda`. Menagerie is at `370c439` with a clean tree |
| Provider interleaving | **Fixed** | `runner.py:199-203`; chunk size 1 in `imap_unordered` |
| Retrying night script | **Fixed** | `run_night.sh:26-37` (four passes), exit codes kept (41-48), `NIGHT_INCOMPLETE` (58-62), `caffeinate` (13), clean-tree check (16), revision recorded; `run_experiment.py:56` exits 3 |
| 10 control seeds | **Fixed** | `run_night.sh:47`, 2,400 episodes asserted at `test_agent.py:163` |
| Pose-cell caveats | **Fixed** | PROTOCOL 5 line 88 (exploratory, three times the budget, planner refusal on flasks); "cost-matched" is gone from section 9 (v) |

## (2) Pre-registered analysis rules against the code

| Rule in PROTOCOL 1 | Code | Match |
|---|---|---|
| sqrt(k/(k-1)) on every interval | `analysis.py:92-93`, `did` at 255-258 | Yes, except `conditional_recovery` (347), which has no factor. See A1: the rule itself is too weak |
| Q3 design effect max(2, 1 + 3 rho), cheap arm only | `analysis.py:176-179, 200-201` | Yes. I reproduced +6.9 (60 against 60) and +10.5 (60 against 59) by hand |
| rho from "notebook and no-memory runs pooled inside each task" | `analysis.py:156-158` | **Not as written** (A3): the code also takes the replay runs and stratifies by (task, condition) |
| Minimum complete runs 24/30, 12/15, 24/30 | `analyze.py:25-27, 156, 200, 238` | Yes. The Q3 count is of clusters with at least one shared layout, not four (A4) |
| Frontier files complete per layout | `analysis.py:60` | Yes |
| Stratified resampling in `did` and `curve` | `analysis.py:250-252, 133` | Yes |
| Abandoned cost keyed with toolset, frontier aborts added | `analyze.py:105`, `analysis.py:221-223` | Yes |
| Skills against pose on run seeds 0 to 2 | `analyze.py:260-263`, `analysis.py:261-275` | Yes |

## (3) Result files

`gate.md` (0, 0, 0 naive against 100, 100, 100 oracle; Sort control 99), `gate_pose.md` (naive 17, 0, 0), `disturbance.md` and
`disturbance_control.md` (fired 50 of 50 everywhere, flask nudge honestly excluded) and `settings_audit.md` all pass and were regenerated on the
final code. `pilot_no_memory.md` is honest: it carries the code hash, says the earlier pilot gave different counts, and PROTOCOL 1 quotes it
correctly (Haiku 4, 6, 8 and Luna 7, 7, 8). It moved Haiku on `stack` from 1 of 8 to 4 of 8 between two pilots, so the "cell with room" is now
two half-open cells, not one wide-open one. None of these files states which code hash produced it except the pilot.

## (4) Anything that touches the running matrix

**R1. `close_gripper` can still say `holding` for a cube it only rests on (pose cell only, exploratory).** The attach rule is "both fingers
touch the object" (`skills.py:108`), and closed fingertips pressing on the top face satisfy it. `move_to` has no stopped-short check, so the
descent that leads there returns `ok: true` 1.8 cm short. The false statement lasts one call: the next `move_to` or `observe` clears it.
Affected: `runs/pose`, mostly `stack`, only when a model descends without opening the hand. Not affected: main, control, frontier (the skills
`pick` has its own stopped-short check at `skills.py:176`). **Handle by analysis:** count pose episodes with a `close_gripper` result of
`holding` at a width more than 5 mm below the object's width, and `move_to` results more than 1 cm from the request, and print both counts
next to the pose table.

**R2. A provider outage on Fable can trip the Anthropic cap with phantom charges.** A 5xx or timeout is charged its full reservation
(`llm.py:88`), eight attempts per call, four passes per cell. For Fable that is roughly $0.3 per attempt. Expected real Anthropic spend is
about $40 of $90, so about 150 failed Fable attempts would exhaust the cap, and the cells that run last (Haiku in `control` and `pose`,
`frontier_exp`) would be skipped. No sign of it yet (0 unknown settlements). **Handle by watching:** check the ledger for `settle_unknown`
lines when the frontier cell ends; no code change.

**R3. Nothing checks that every analysed file has one code hash.** Later cells and retry passes start new processes hours from now, and
`maxtasksperchild=4` re-imports the package throughout, so a change on disk to `robot_play/` (except `analysis.py` and `render.py`),
`uv.lock` or the Panda folder would give later files a different hash with no error, because a new file has nothing to mismatch. Also
do not edit `scripts/run_night.sh` while it runs: bash reads it as it goes. **Handle by analysis:** `analyze.py` should print the set of
(code, protocol) values across files and refuse to pool more than one.

## Analysis findings (all changeable now: `analysis.py` is outside the run hash)

**A1. The small-sample rule does almost nothing.** With 30 clusters the factor is 1.017. The stratified bootstrap understates the spread by
the size of each stratum (10 runs, so sqrt(10/9)) and uses a normal-shaped tail where a t tail is needed. Result: 95.5% coverage for a
nominal 97.5% in Q1 and Q4, which cancels the Bonferroni step. A stratified t interval (standard error from the within-job variances,
k minus 3 degrees of freedom) covers 97.5%. Record the deviation in `results/deviations.md` now: each interval is the wider of the
pre-registered one and the stratified t interval.

**A2. The pose interval covers 84%** (3 runs per job). The text says "few"; the number should be in the report.

**A3. The intraclass correlation is not computed as PROTOCOL 1 says** (replay runs included, strata by condition). The literal rule is the
more conservative one. Pick one before looking at Q3. The floor of 2 will decide most rows either way.

**A4. Smaller.** A Q3 cluster counts toward the 12 with one shared layout; aborts in the disturbed phase enter the Q3 cheap cost although
those episodes do not; `scripts/notebook_audit.py` was added after launch and must be listed as a post-launch exploratory addition;
PROTOCOL 5 line 92 still says the hash covers "the pinned model download" (it now covers the asset contents).

## Scores

**Novelty 6.5.** Unchanged design, honestly credited (PROTOCOL 9). The pose axis is now correctly labelled exploratory (PROTOCOL 5 line 88), which
is right but removes claim (i) as a finding. The first 34 frontier episodes are 34 of 34, so Q3 will be a ceiling comparison, as section 1 predicts.

**Rigour 7.8.** Ten control seeds, a fixed Q3 design effect with worked numbers, minimum counts and stratified resampling are all implemented.
Held back by A1 (`analysis.py:92`: 95.5% for a nominal 97.5%), A3 (`analysis.py:156-158` against PROTOCOL 1 Q3) and no single-hash check (R3).

**Engineering 8.2.** 108 tests, every round-3 defect fixed and verified by running it, a launch script that retries and reports failure, a
clean ledger. Held back by R1 (`skills.py:108`, `move_to` at 121-128), R2 (`llm.py:88`) and a misnamed test (`test_agent.py:231`).

**Validity 7.6.** The stale held state is gone (0 mismatches in 144 skills checks, 0 in the live files) and the gates were rerun on the final
code. Still: one false `holding` path in the pose cell (R1), and the confirmatory intervals are narrower than labelled until A1 is recorded.

**Clarity 8.0.** PROTOCOL 1, 5 and 10 and the README now agree with each other and with the result files. Held back by line 92 of PROTOCOL 5,
result files without a code hash, and no mention yet of the post-launch `notebook_audit.py`.

```json
{"novelty": 6.5, "rigour": 7.8, "engineering": 8.2, "validity": 7.6, "clarity": 8.0,
 "fixes": [
  "Do not stop the matrix. Before analyze.py is run on any matrix data, record a deviation in results/deviations.md: the pre-registered factor sqrt(k/(k-1)) (analysis.py:92) is 1.017 at 30 clusters and the Q1 and Q4 intervals cover about 95.5% for a nominal 97.5% (Q3 bootstrap 95.6% for 98.75%, pose 84% for 95%). Report each interval as the wider of the pre-registered one and a stratified t interval (within-job variances, k minus 3 degrees of freedom), which covers 97.5%, 98.7% and 95.1% in the same simulation.",
  "scripts/analyze.py: print the set of (code hash, protocol, code_history) across all analysed files and refuse to pool more than one. Later cells and retry passes start new processes and nothing else would catch a change to robot_play/, uv.lock or the Panda folder during the night. Do not edit scripts/run_night.sh while it runs.",
  "Pose cell (runs/pose only, exploratory): close_gripper says holding for a cube the closed fingertips only rest on (skills.py:108, 6 of 6 in my probe) and move_to returns ok: true 1.8 cm short. In the report count close_gripper results with holding at a width more than 5 mm under the object's width and move_to results more than 1 cm from the request, per model, next to the pose table. Fix skills.py only after the run.",
  "robot_play/analysis.py intraclass (156-158): PROTOCOL 1 says notebook and no-memory runs pooled inside each task; the code also takes replay runs and stratifies by (task, condition). Make the code match the text (the conservative reading) or amend the text, before looking at any Q3 row.",
  "Watch runs/spend/ledger.jsonl for settle_unknown lines when the frontier cell ends: a Fable 5xx or timeout is charged about $0.3 per attempt (llm.py:88), so about 150 failed attempts would exhaust the $90 cap and skip Haiku in the control and pose cells and frontier_exp, which run last.",
  "Analysis details: add the small-sample factor to conditional_recovery (analysis.py:347); count a Q3 cluster toward the 12 only when all four layouts exist in both arms; keep disturbed-phase aborts out of the Q3 cheap cost; state the pose interval's 84% coverage in section 6 of the report.",
  "Text: list scripts/notebook_audit.py as a post-launch exploratory addition in PROTOCOL 10; correct PROTOCOL 5 line 92 (the hash covers the asset contents, not the download script); write the code hash into the gate, disturbance and audit result files; rename test_a_refusal_with_a_call_is_recorded_as_a_refusal (it sends no call)."
 ]}
```

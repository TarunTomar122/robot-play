# Step 3 review (round 3: v1.3, last check before the matrix launches) - judge: fable

Date: 16 Nov 2026, 20:50 to 21:35. Read-only review of HEAD `053cfb6` (code identical to `f74a5cf`; code hash `71abe4596b00fe49`, the same hash the
final-code pilot files carry). No paid API call, no `.env` read. `pytest`: **97 passed**. I did not read Codex's round 3 review.

## Verdict

Ten of the eleven round-2 findings are really fixed, and I verified them by running the code, not by reading the changelog. The runner, the abort
accounting, the resume binding and the report all behaved correctly on real `FakeProvider` runs and on three synthetic 5,496-episode matrices.
**One defect under `robot_play/` should still be fixed before the freeze:** the "held" state is never re-checked after the grasp, so `observe`
and `close_gripper` keep saying `holding: cube_green` for a cube that is lying on the table. In the pose toolset this happens on the one hidden
catch every time (8 of 8 in my probe) and it is already in the live pilot (3 of 6 Haiku pose-stack episodes). The main, control and frontier
cells are safe to launch as they are; the pose cell is not. The launch script also needs three small safeguards, and four sentences of
PROTOCOL.md need to be settled before data exist.

## What I ran

| Probe (scripted, layouts 60300+, used by nothing else) | Result |
|---|---|
| Pose: grasp green with `close_gripper` (firm), lift, lower 5 cm, carry, lower onto red | 8 of 8 ok. Round-2 A1 is fixed |
| Pose, stack catch, default grip: `close_gripper`, lift to 0.30, `observe` | Cube stays at z = 0.020, gripper width 0.019, yet `held: true`, `holding: cube_green` in **8 of 8** |
| Same state: `move_to` down onto the dropped cube, then `close_gripper` | `ok: true` with the hand stopped 2.6 cm short and no error (the planner ignores the real cube); `close_gripper` answers `holding: cube_green` at width 0.02 |
| Skills: `pick` green, `lift_height=0.05`, default grip | `ok: true`, rise 0.038, 10 of 10. The cube is now static in the hand (creep 0.1 to 0.3 mm over 2 more seconds), so the report is true when made |
| Same, then one `move_to` and `observe` | Cube on the table (z = 0.02), `held: true` in 4 of 4 |
| Pose flasks: open hand down to 60 / 70 / 90% of flask height | Catch scene: refused, refused, ok. Control scene: 60% refused, 70% ok. The refusal text is `arm/hand would touch flask_a` |
| `run_one` with `FakeProvider`: abort in evaluation, resume | `_aborted` line kept with its dollars, no duplicate rows, resumed prompts carry the frozen notebook, zero rewrites after resume |
| `run_one`: `BudgetExceeded` mid-episode | Status `budget`, abort line with the $0.30 already paid |
| `scripts/analyze.py` on three synthetic matrices (realistic, all at ceiling, partial with a missing control cell) | Exit 0, no stderr in all three; counts, clusters and coverage table correct |
| Coverage simulation of the stratified percentile bootstrap at the planned cluster counts (3,000 repetitions) | Q4 (3 tasks x 5 runs) nominal 97.5% covers **93.0%**; Q1 (3 x 10) covers 96.5%; pose (3 x 3) nominal 95% covers 85.8% |
| Spend ledger after the pilots | 10,112 rows, reconciles, 0 open reservations, 0 overruns, 0 released or unknown calls; $0.48 Anthropic and $0.28 OpenAI already count toward the caps |
| Prices in `spend.py` against Anthropic's model table | Haiku 5.5 $0.10 / $0.50 (prompts stay under its 100K tier), Fable 5.2 $8 / $40 with cache reads $0.20: correct |

## Round-2 findings, one by one

| Finding | Status | Evidence |
|---|---|---|
| Pose toolset attach, plus `results/gate_pose.md` | **Fixed, with a new hole** | `skills.py:97-101` attaches on a two-finger contact; gate 100/100 oracle, naive 17, 0, 0. The attach is never undone when the object is lost (N1) |
| `pick` dwell | **Fixed as far as a dwell can** | `skills.py:185`; default pick on the heavy cube now says `ok: false` 10 of 10. At `lift_height=0.05` the cube is truly held at report time and lost in transit (N1 again) |
| Control-scene disturbances, `results/disturbance_control.md` | **Fixed** | `runner.py:83,211`; gate on layouts 3000+; flask nudge honestly excluded; test at `test_agent.py:210` |
| Q3 clusters and Agresti-Caffo floor | **Fixed, one assumption left** | `analysis.py:163-177`; synthetic 60/60 gives +0.0 (-5.7 to +5.7). The design effect falls back to 1 exactly when it cannot be estimated (N4) |
| Q4 confirmed in control scenes | **Fixed, interval too narrow** | `analyze.py:226-243`, `analysis.py:247`. Percentile bootstrap with 5 runs per task undercovers (N3) |
| Notebook-rewrite abort | **Fixed** | `agent.py:200-202`, `runner.py:158-160`; my resume run and `test_agent.py:130` |
| Abandoned-attempt cost | **Fixed** | `runner.py:107-111,155-159`; coverage table and Q3 cost column read it. Attribution leaks across cells (N5) |
| Code-hash-bound resume | **Fixed** | `runner.py:34-41,120-129`; `analysis.py` and `render.py` excluded as asked |
| `frontier_exp` seeds | **Fixed** | `runner.py:231-235`; 15 keys, 5 seeds, 240 episodes asserted at `test_agent.py:163-165` |
| Per-model cache-read prices | **Fixed** | `spend.py:38,62` |
| Overrun halt | **Fixed** | `spend.py:124,134-136`, tested |

## New findings

**N1. Stale "held" state (must fix, `robot_play/skills.py`).** `mv.held` is set by `pick` or `close_gripper` and cleared only by `open_gripper`
or a failed pick. Nothing re-checks it. Consequences I measured: `observe` reports `held: true` for an object on the table; `close_gripper`
skips its contact check (`if not self.mv.held`, line 97) and repeats the stale name; the planner treats the real object as part of the hand, so
a descent onto it is approved and stalls short with `ok: true`. This contradicts PROTOCOL 3 ("Tools return measured facts only", "`observe` then
lists it as held"). It sits on the main path of the pose stack scene, the only hidden catch, so the pose numbers there would partly measure a
false tool statement. Live evidence: `runs/pilot21_pose/claude-haiku-5-5__stack...` seed 50005, call 29 (cube z 0.02, hand z 0.2, `held: true`);
phantom observations in 3 of 6 episodes. In the skills toolset it needs a pick that succeeds and a loss in transit, so the main cell is only
touched at the edges. Fix: one helper that detaches when the held object no longer touches both fingers, called at the end of `move_to` and
`close_gripper` and at the start of `observe` and `place`; add a test; rerun `gate.py`, `gate_pose.py`, the audit and both disturbance gates.

**N2. `scripts/run_night.sh` has no retry pass, no sleep guard and no revision check.** A run that ends `aborted` (eight failed attempts,
about four minutes of rate limiting) is never retried, and incomplete runs are dropped from every confirmatory number. One missing frontier
episode removes that model's whole 20-layout file: my partial matrix with a single Astra run at 19 of 20 turned two Q3 rows into "inconclusive:
8 complete clusters". The script is safe to rerun, so loop each cell until nothing is `aborted` (two or three passes). Wrap the script in
`caffeinate -dimsu`: on a sleeping Mac every hung call is charged its full reservation eight times. Record `git rev-parse HEAD` and stop on a
dirty tree. All `main` specs are ordered Haiku first, so the eight workers hit one provider at a time; interleaving the models halves the
rate-limit exposure.

**N3. The confirmatory Q4 interval is anti-conservative.** With 5 runs per task the stratified percentile bootstrap covers 93.0% for a nominal
97.5% (Q1 with 10 per task: 96.5%). Either state in PROTOCOL 1 before launch that Q1 and Q4 use a small-sample method (a sign-flip permutation
test inside each task, or the bootstrap spread scaled by sqrt(n / (n - 1)) with a t quantile), or raise the control cell to 10 run seeds (about
1,200 more cheap episodes, about $3, a one-word change in `run_night.sh` plus the count in `test_agent.py:163`). The code for the interval can
follow after launch; the rule cannot.

**N4. Q3 can pass only at ceiling, and there it rests on a design effect of 1.** With both arms between 80% and 95% the 98.75% interval reaches
+19 to +34 points in my realistic matrix, so "within 10 points" is unreachable unless the cheap model beats the frontier. At 60 of 60 against
60 of 60 the claim passes with +5.7, but `deff` is set to 1 because the data have no variance to estimate it from (`analysis.py:174`); with the
four layouts of a run fully dependent the upper end is about +15 and the claim fails. Fix the design effect in PROTOCOL 1 now (for example 1 + 3 x
0.5 on the cheap arm) and state the expected width.

**N5. Analysis details (all analysis-only, can follow).** (a) `q3_cost` matches abandoned dollars by (model, task, condition, quirk, run seed)
without the toolset or the folder (`analyze.py:103-106`), so pose-cell aborts are added to the cheap model's Q3 cost: $12.00 of phantom cost
in my partial matrix. (b) The frontier side of the cost table leaves out its own abandoned attempts. (c) Frontier first-try files should be
judged complete per layout, not per file. (d) Section 6 compares skills on 10 seeds with pose on 3 seeds, gives no interval for the
skills-minus-pose interaction that claim (i) is about, and its 3-per-task bootstrap covers 86%. (e) `did()` and `curve()` resample without
strata (`analysis.py:132,216`), against PROTOCOL 1 line 14.

**N6. The pose flask catch is a planner refusal, not the physical effect.** `move_to` does not ignore the target object, so the open hand is
refused at 60% and 70% of the flask height in the catch scene and at 60% in the control scene too. The naive pose script was set to 70% so that
the gate passes (disclosed in PROTOCOL 7.3b). The pose cell also has three times the call budget. Claim (i) must therefore be worded as
exploratory, and the flask row described as "the planner names the object it would touch".

## Claims the code or results contradict

- PROTOCOL 9 (v) says "a cost-matched cheap-versus-frontier comparison"; PROTOCOL 1 Q3 and `analyze.py:213` say it is "not a cost-matched claim".
- PROTOCOL 1 (lines 28-29) and README lines 71-74 quote the older pilot (Haiku 0, 8, 7 of 8; Luna 7, 7, 7). `results/pilot_no_memory.md`, the
  pilot on the final code, says Haiku 1, 8, 8 and Luna 7, 8, 7. PROTOCOL 10 does not list that pilot (48 skills and 36 pose episodes) at all.
- PROTOCOL 3: "measured facts only" and "`observe` then lists it as held" (N1).
- README line 53: Sort control 100 / 100; `results/gate.md` says 99 / 100. README line 9: 85 tests (97). README line 87: "about 5,300
  episodes" (5,496) and "a call that could push past the cap is refused", which PROTOCOL 6 now correctly calls an estimate.
- README line 85 and line 130 do not mention the control-scene Q4, `gate_pose.py`, `run_night.sh` or the pose pilot.

## The no-memory pilot on the final code (`results/pilot_no_memory.md`)

It is honest and useful. It confirms that five of six cheap skill cells are at ceiling and that Haiku on `stack` is the only cell with room
(1 of 8, 19.9 of 20 calls). The pose rows show real models can work the pose tools (Haiku bins 6 of 6). Three cautions: six layouts per pose
cell say nothing about rates; Luna's pose-stack failures are four false "done" claims after `close_gripper` said `holding` and no later result
said otherwise (N1 would have told it on the next `observe`); and Haiku's pose-flask failures are physical (it leaves with the fingers still
closed around the neck and tips the flask), which is a fair pose-level difficulty and not a bug. Expected spend from these rates is about $50
to $60 in total, mostly Fable, inside both caps but not "well under $50".

## Must change before launch

1. Fix the stale held state in `robot_play/skills.py` (N1), add a test, rerun the five gate scripts. If there is no time, launch main, control
   and frontier now and remove the pose cell and claim (i) from this run; do not run the pose cell on the current code.
2. `scripts/run_night.sh`: `caffeinate`, a retry loop per cell, the git revision and clean-tree check (N2).
3. PROTOCOL.md, before any data: the small-sample rule for Q1 and Q4 or 10 control seeds (N3); a fixed design effect and expected width for Q3
   (N4); delete "cost-matched" from section 9; pose cell exploratory with the flask caveat (N6); the final-code pilot in sections 1 and 10.

## Can follow during the run (analysis and README only)

N5 (a) to (e); the code for the N3 and N4 rules; README lines 9, 53, 71-74, 85, 87 and 130; a per-cell count of abandoned attempts in the text
of the results (the coverage table already has it).

## Scores

**Novelty 6.5.** The combination is stated clearly and credited honestly. The pose axis now runs, but its stack scene carries a false "held"
report and its flask catch is a planner message (N1, N6), and the final-code pilot again shows one of six cheap cells with room, so the bold
part of the angle still rests on Haiku plus `stack`.

**Rigour 7.5.** One confirmatory family per question with adjusted intervals, complete runs only, minimum counts, Q4 in control scenes, Q3
clustered by run with a no-memory row, a difference in differences on calls. Held back by the 93% coverage of the Q4 interval (N3), the Q3
design effect of 1 at ceiling and its unreachable margin elsewhere (N4), and no matched interaction test for the pose claim (N5d).

**Engineering 7.5.** 97 tests green, resume bound to a code hash, abort cost kept, honest meter with overrun halt, correct prices, clean
ledger; all verified by running them. Held back by the unchecked held state (N1), a launch script with no retry, sleep guard or revision check
(N2), and the abandoned-cost leak across cells (N5a).

**Validity 6.5.** Round 2's pose and Q4 defects are gone and I found no leak and no inflated number in the skills cells. Still: tools state a
false fact after an object is lost, live-confirmed in the pilot (N1); a descent onto the lost object returns `ok: true` 2.6 cm short; and
PROTOCOL and README still carry the contradicted sentences listed above.

**Clarity 7.5.** PROTOCOL 1, 6 and 10 are now precise and candid, and the report reads well on synthetic data. Held back by "cost-matched"
against "not cost-matched", two different pilots quoted as one, and five stale README numbers.

```json
{"novelty": 6.5, "rigour": 7.5, "engineering": 7.5, "validity": 6.5, "clarity": 7.5,
 "fixes": [
  "Before launch, robot_play/skills.py: the held state is never re-checked. After a grasp is lost, observe says held: true and close_gripper says holding: cube_green for a cube on the table (pose stack catch 8/8; skills after pick lift_height=0.05 plus one move_to 4/4; live in runs/pilot21_pose Haiku stack seed 50005 call 29), and the planner approves a descent onto the real cube that stalls 2.6 cm short with ok: true. Detach when the held object no longer touches both fingers (end of move_to and close_gripper, start of observe and place), add a test, rerun gate.py, gate_pose.py, the audit and both disturbance gates. Otherwise drop the pose cell and claim (i) from this run.",
  "Before launch, scripts/run_night.sh: wrap in caffeinate -dimsu, rerun each cell until no run is 'aborted' (aborted runs are never retried and incomplete runs are dropped; one missing frontier episode voided 5 Q3 clusters in my partial matrix), record git rev-parse HEAD and stop on a dirty tree, and interleave Haiku and Luna specs.",
  "Before launch, PROTOCOL 1: the stratified percentile bootstrap covers 93.0% for the nominal 97.5% Q4 interval (3 tasks x 5 runs; Q1 96.5%). Pre-state a small-sample method (sign-flip test inside each task, or sqrt(n/(n-1)) scaling with a t quantile) or raise the control cell to 10 run seeds (about $3); the code can follow, the rule cannot.",
  "Before launch, PROTOCOL 1 Q3: fix the design effect in advance (analysis.py:174 sets it to 1 exactly when everything succeeds, which is the only case where the margin can be met: +5.7 at deff 1, about +15 if the four layouts of a run are fully dependent) and state the expected interval width (+19 to +34 points at 80 to 95% success).",
  "Before launch, PROTOCOL text: remove 'cost-matched' from section 9 (v), which section 1 contradicts; replace the old pilot numbers in section 1 with results/pilot_no_memory.md (Haiku 1, 8, 8; Luna 7, 8, 7 of 8) and list that pilot in section 10; mark the pose cell exploratory and say that its flask catch is a planner refusal (60% refused in the control scene too) and that it has three times the call budget.",
  "During the run, scripts/analyze.py: key abandoned dollars by toolset and folder (pose aborts leaked $12 into the Q3 cheap-model cost), add the frontier's own abandoned attempts, judge frontier first-try files complete per layout, compare skills and pose on the same run seeds 0 to 2 with an interval for the interaction, and stratify did() and curve().",
  "During the run, README: 97 tests not 85 (line 9), Sort control 99/100 not 100/100 (line 53), the final-code pilot table (lines 71-74), control-scene Q4 (line 85), 5,496 episodes and the estimate-based cap wording (line 87), and gate_pose.py, run_night.sh and pilot_table.py in the folder map (line 130)."
 ]}
```

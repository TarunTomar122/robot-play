# Step 2 review (round 2: fixed environment, spend meter, runner, analysis plan) - judge: fable

Date: 16 Nov 2026, 19:56 to 20:05. Read-only review. No paid API call, no `.env` read.

**What I reviewed.** The working tree, not a commit. `robot_play/agent.py`, `llm.py`, `runner.py` and `spend.py` were edited at 20:00 while I was
reading (uncommitted: code hash in the run header, `_aborted` lines, failed notebook rewrite stops the run, overrun stop, `frontier_exp` seeds,
`PROTOCOL_VERSION = "1.3"`). `pytest` was 85 passed at 19:57 and **84 passed, 1 failed at 20:01**
(`tests/test_agent.py::test_a_provider_error_is_not_saved_as_a_failed_episode_and_changes_no_memory`). I did not read Codex's round 2 review.

**Probes I ran** (scripted, no model, layouts 60100 to 60208, used by nothing else):

| Probe | Result |
|---|---|
| Bins: `pick`, `move_to` bin centre z = 0.10, `open_gripper`, `home` | `home` ok 10/10 (round 1: 0/20). Fixed |
| Stack: `pick` green with `lift_height=0.05`, default grip | `ok: true, holding: cube_green` 10/10 while the cube slides out (rise 0.037 of 0.05); tower 0/10. **Not fixed** |
| Stack: `yaw_offset_deg=45`, default grip | tower 8/10 (audit says 10/20). Documented now, not removed |
| Stack: `speed=slow`, `grasp_height=0.3`, `yaw=30` | 0/10 each |
| Shortest winning script: stack and flasks without `home` | 10/10 in **5** calls each. PROTOCOL says the floor is 6 |
| Pose toolset, scripted pick and place from moves, 8 layouts per scene | stack catch 6/8, stack control 7/8, bins 8/8, flasks 8/8 (20 to 38 calls of 60) |
| Pose toolset: grasp a cube with `close_gripper`, lift, then `move_to` any lower point | **`goal pose: arm/hand would touch cube_green` 9/9**, including a 5 cm descent |

## Verdict in one paragraph

Round 1's four number-changing defects are fixed or honestly re-labelled, the spend meter is now a real bound in dollars, and the protocol is far
more honest about ceilings. I would still not launch the full matrix tonight. Three things would put wrong numbers into the paper: the pose-level
toolset cannot lower a held cube because the planner treats the cube in the hand as an obstacle, so the headline "skill-level against pose-level"
comparison measures a harness artefact; the Q3 interval resamples layouts although the cheap model's four layouts per run share one notebook, and
it declares "within margin" with a zero-width interval when both arms are at ceiling; and the Q4 difference of drops is biased against the
notebook wherever the fresh agent already fails clean (it cannot drop below zero). The pilot also shows only one of six cheap cells with room for
success to rise, which the protocol understates. The main, control and frontier first-try cells are safe to launch once the tree is committed and
green; the pose cell is not.

## Round 1 findings, checked one by one

| # | Round 1 finding (who) | Status | Evidence |
|---|---|---|---|
| 1 | Bins instruction and predicate disagree (fable) | **Fixed** | `env.py:125` accepts `0.01 < z < 0.08` plus 5 mm stability; predicate test for cube on cube; pilot20b Haiku bins 8/8 |
| 2 | Stuck arm after opening inside a bin (fable) | **Fixed** | `motion.py` `_escape`; my probe 10/10; error now names the body. `tests/test_motion.py` covers it |
| 3 | `yaw_offset_deg=45` defeats the stack catch; `lift_height=0.05` reports a slipping cube as held (fable) | **Half** | Audit published and wording corrected. `skills.py:179-184` still settles 0.3 s and reports `ok/holding` for a sliding cube (probe above). README line 17 still says "A normal squeeze cannot hold it" |
| 4 | Provider error saved as failed episode and fed to the notebook (fable) | **Fixed, in flux** | `runner.py` returns before writing; 20:00 edit also logs `_aborted` with cost and stops on a failed rewrite. Its own test fails right now |
| 5 | Disturbance gate reported on tuning seeds (fable, codex) | **Fixed** | `results/disturbance.md` on 3000+, 50 per row, thresholds in PROTOCOL 7.4. Bins nudge 47/50 |
| 6 | Q4 mixes catch knowledge with recovery; denominator conditioned on firing (fable, codex) | **Half** | All-assigned denominator and fire rate are in. The drop-difference has a floor bias (new finding B3) and no disturbed control cell exists |
| 7 | Efficiency outcome survivor-biased and undefined at zero successes (fable) | **Fixed** | `calls_to_success` charges failures the budget; `within_k`. Not tested as catch minus control (B5) |
| 8 | Budget chosen after seeing model data, 20 vs 30 conflict (fable, codex) | **Mostly** | Rule and history written (3, 10.2). `env.py:15 MAX_CALLS = 30` is still dead code. `docs/TASKS.md:52` still promises to tighten the budget if models solve everything, which contradicts PROTOCOL 3 |
| 9 | Spend cap not a hard cap: flat 6,000-token history, cache writes, prices (codex, fable) | **Fixed** | `llm.py:163,242` use the provider's own count x 1.1; reservation at cache-write rate plus full 6,000 output; OpenAI x2; overrun logged and (20:00) stops the provider. The output reservation alone is 30,000 input tokens of slack, so a dollar overrun is not realistic |
| 10 | Failed and retried calls missing from episode cost (codex) | **Fixed** | `Tally`, `agent.py:180,196`. Aborted attempts are now in `_aborted` lines but `analysis.load` does not read them (C2) |
| 11 | Resume not bound to config (codex) | **Fixed** | Full header compared, `ConfigMismatch`; 20:00 edit adds a code hash |
| 12 | One provider's cap stops everything (fable) | **Fixed** | `_worker` skips per provider; test present |
| 13 | Gates bypass `Episode` and the call budget (codex) | **Fixed** | `scripted.py` plays through `Episode`; gate rerun 19:45. No gate exists for the pose toolset (A1) |
| 14 | Stability only at the end of the second (codex) | **Fixed** | `settle_and_track`, 10 slices, 5 mm |
| 15 | Leakage claims: visible geometry vs hidden (codex, fable) | **Fixed** | PROTOCOL 2, README table, `test_leakage.py:58,69` |
| 16 | Provider settings not matched or recorded (fable) | **Partly** | Both `low`, recorded; reasoning tokens logged for OpenAI only. Frontier at `low` is not named as such in Q3 (B6) |
| 17 | `uv.lock`, Menagerie pin, stale README (codex, fable) | **Fixed** | Lock committed, `fetch_models.sh` pins `370c439`, README status current |
| 18 | Five clusters, no primary contrast, no multiplicity statement (fable) | **Half** | Ten run seeds now. Still no named primary test and no correction (B4) |

## New findings

### A. Things that would put wrong numbers in the results

**A1. Pose toolset: a held cube cannot be lowered, and nothing gates the pose cell.** `close_gripper` never calls `mv.attach`
(`skills.py:92-97`), so the planner checks the goal pose with the cube left where it is now, inside the wrist of the lowered hand. Every descent
with a held cube fails with `arm/hand would touch cube_green`, naming the object in the hand (9/9, even 5 cm). `observe` reports `held: false`
and `holding: null` the whole time. Stack is only solvable by dropping from carrying height (6/8 for my script) or by carrying at exactly the
release height. So 576 paid episodes and novelty claim (i) would measure this artefact, not the abstraction level.
`tests/test_agent.py:146` only tests a pick. Fix: attach when `close_gripper` ends with an object between the fingers, then add a pose-level
oracle and naive gate (100 layouts, 60 calls) to `results/`. The change touches `close_gripper` in the skills toolset too, so rerun `gate.py`.

**A2. `pick` still says `ok: true, holding` for a cube that is sliding out** at `lift_height=0.05` (10/10). It is the same for every condition, so
it does not bias a contrast, but it breaks "tools return measured facts only" (PROTOCOL 3) and it feeds a false fact into notebooks. Re-check
after a 1 s dwell or compare finger width before and after.

**A3. Only one of six cheap cells has room for success to rise, and the protocol says two are at ceiling.** `runs/pilot20b`: Haiku stack 0/8,
bins 8/8, flasks 7/8; Luna 7/8, 7/8, 7/8. PROTOCOL 1 names "two such cells (Haiku on flasks, Luna on stack)". Five cells are at 88% or above, so
Luna's Q1 is a near-certain null and the pooled Haiku Q1 is carried by stack alone. In that cell Haiku fails because it runs out of the 20 calls
(all eight episodes used 20), so the Q1 gain and the Q2 gain are the same event counted twice. Say so: Q1 is "success within a 20-call budget",
and Q1 and Q2 are not independent evidence. Haiku bins used 17 to 20 calls with 8/8 success, so the budget is binding there too.

### B. Analysis plan (PROTOCOL 1, `robot_play/analysis.py`)

**B1. Q3 clusters by the wrong unit.** `q3_gap` (`analysis.py:107-117`) resamples layouts. The cheap arm's 20 layouts per task are five runs of
four layouts that share a frozen notebook, so they are not independent. Resample (task, run seed) blocks of four gaps (15 clusters). The current
interval is too narrow, which makes "within margin" easier to claim.

**B2. Q3 degenerates at ceiling and is underpowered away from it.** If both arms are 60/60 the percentile bootstrap returns [0, 0] and prints
"yes"; `tests/test_analysis.py:38-45` asserts exactly that as correct. With 60 layouts and both arms near 80%, the upper bound sits about 13
points above the estimate, so the claim can only pass if the cheap model beats the frontier. Use a method that has width at 0 or 1 (Newcombe or
Wilson-based paired interval, or a one-sided exact test against the margin), state the expected width, and add the missing row
**cheap with no memory against frontier**: Luna is already at 88% without a notebook, so a "yes" must not be credited to experience.

**B3. Q4 difference of drops has a floor bias.** `recovery_drop_difference` computes (clean minus disturbed) per arm. Where the fresh agent
fails clean (Haiku stack, 0/8) its drop is 0 by construction and the notebook agent's drop is positive, so the measure says the notebook
"loses more". The clean design is a disturbed evaluation in the **control** scenes, where neither arm needs catch knowledge: `runner.py:66`
skips it (`if self.disturb_eval and self.quirk`) and the control cell never sets `disturb_eval`. Add it (240 episodes, about $0.60) and make
it the primary Q4 measure; keep the catch-scene drop as secondary, plus success when disturbed given success clean on the same layout.

**B4. No primary contrast and no multiplicity control.** Q1 alone is 2 models x 2 memory types pooled, plus 6 per-task rows, plus the
difference in differences; Q2 to Q4 repeat it. Name one primary test per question (I suggest notebook against none, per model, pooled over
tasks, Holm over the two models) and label everything else secondary.

**B5. Pairing and bootstrap details.**
- Pairing by (task, run seed) is right: the two arms share the four evaluation layouts.
- Pooled over tasks, the bootstrap resamples pairs across tasks, so task imbalance in a resample adds variance. Stratify by task (resample the
  10 seeds inside each task). Conservative as it stands, so not a launch stopper.
- Per-task rows have 10 clusters; a percentile bootstrap undercovers there (roughly 90% for a nominal 95%). Use BCa or a sign-flip
  permutation test for those rows, or say they are descriptive.
- `did` resamples catch pairs (30) and control pairs (15) independently and unstratified. Acceptable and conservative. But with control
  success near 100% the control gain is 0 with no spread, so the success DiD equals Q1 and adds nothing. The DiD that matters is on
  **calls to success**, and `analyze.py` never computes it (`did(..., metric="calls_to_success")` is one line). Without it, "faster because it
  learned the catch" cannot be told apart from "skips `observe`".
- The call floors are 5, 9, 5, not 6, 10, 6 (no `home` needed; probe above). `within_k` starts at 6, so no table breaks, but fix the sentence.

**B6. Q3 compares against a frontier model held at `effort: low`.** Fable's default is `high`. The row label and README point 3 must say
"frontier at low effort", or the comparison flatters the cheap model.

### C. Engineering and accounting

**C1. The tree is not frozen.** Four files are uncommitted, one test fails, `PROTOCOL.md` says v1.2 while `runner.py` says 1.3, and
`scripts/run_night.sh` is untracked. The new `code_hash()` covers every `robot_play/*.py` including `analysis.py` and `render.py`, so any later
analysis fix blocks every resume unless `ROBOT_PLAY_ALLOW_CODE_CHANGE=1`. Hash only the files a run executes.

**C2. `analysis.load` will crash on the new `_aborted` lines** (`analysis.py:26-28` skips only `_config`, then reads `r["result"]`). It also
has to add their dollars to the Q3 cost, otherwise PROTOCOL 1 "cost counts every paid call" is false.

**C3. Q3 cost and the frontier-with-experience cell have no analysis.** `analyze.py` section 4 prints no cost column, and nothing reads
`runs/frontier_exp` (240 Fable episodes, the dearest cell). Claim (v) "cost-matched" has no code behind it.

**C4. Fable cache reads are priced four times too high in reported dollars.** `spend.py:33` uses 0.10 of input for every Anthropic model;
Fable 5.2 cache reads are $0.20 per million (0.025). Safe for the cap, wrong for the Q3 cost table, in the direction that favours the cheap
model. Make `CACHE_READ` per model. The Haiku and Fable base prices match the published list.

**C5. Aborts redraw the episode.** A cut-off reply or failed rewrite is discarded and replayed with a fresh sample. Pilot output is at most
about 200 tokens per turn against a 6,000 limit, so this should be rare; report the abort count per cell from the `_aborted` lines.

**C6. Budget headroom.** Haiku measured $0.0012 to $0.0030 per episode. Fable at 80 times the price is about $0.15 to $0.25, so 60 + 240
Fable episodes plus rewrites is $50 to $75 against a $90 stop. `run_night.sh` starts `frontier_exp` before `pose`, which is fine, but if the
cap hits, the missing runs are the later tasks and seeds, not a random subset. Make `analyze.py` list incomplete runs and use complete pairs only.

### D. Claims the evidence does not support

- README 17: "A normal squeeze cannot hold it." A 45 degree hand turn with the normal squeeze builds the tower in 8 to 10 of 20.
- README 61: "Speed, lift height and the pause after letting go change nothing." `place speed=fast` gives 16, 15, 18 of 20 in the controls.
- README 40 and PROTOCOL 9 (i): the pose comparison "tells us whether good building blocks make learning easier". Not until A1 is fixed.
- PROTOCOL 1: "two such cells" at ceiling (five), and oracle floors 6, 10, 6 (5, 9, 5).
- PROTOCOL 6.1 and README 87: "a call that could push past the cap is refused" is true for assumed prices; the 20:00 `spend.py` docstring
  says this honestly, the protocol text should match it.
- `results/gate.md` says "seeds 0..99" with no note that it was rerun through `Episode`; one line would settle it.

## Must change before launch

1. Commit a green tree and tag it; make protocol and code versions agree.
2. Fix A1 and gate the pose toolset, or pull the pose cell and claim (i) from this run.
3. Fix `analysis.load` for `_aborted` lines (C2).
4. Add the disturbed control evaluation (B3). It changes the run plan, so it cannot be added after launch.
5. Write the primary contrasts, the Q3 clustering and ceiling rule, and "Q1 = success within budget" into PROTOCOL 1 (A3, B1, B2, B4).

Can follow during the run, before any number is published: B5, B6, C3, C4, C5, the README sentences, A2 (if A2 is changed, change it before
launch or not at all, because it alters tool output).

## Scores

**Novelty 6.5.** The combination is still clearly stated and honestly credited. The pose-level axis exists now but is broken (A1), and the
pilot shows the "hidden catch" bites in one of six cheap cells (A3), so the bold part of the angle currently rests on Haiku plus stack.

**Rigour 7.0.** Paired layouts, frozen memory, fresh-seed gates, settings audit, all-assigned Q4 denominator, calls-to-success with failures
charged. Held back by Q3 clustering and ceiling behaviour (B1, B2), the Q4 floor bias with no disturbed control (B3), no primary contrast or
multiplicity rule (B4), no calls DiD (B5), frontier at low effort unlabelled (B6).

**Engineering 7.0.** The meter is a real dollar bound with overrun stop, per-attempt tally, config-bound resume, abort log, 85 fast tests,
lock file and pinned model. Held back by a tree edited mid-review with a failing test (C1), `analysis.load` not matching the new file
format (C2), no pose gate, missing Q3 cost and `frontier_exp` analysis (C3), wrong Fable cache-read price (C4).

**Validity 6.0.** Round 1's bins, stuck-arm and provider-error defects are gone and I found no leak. Still: the pose cell measures a planner
artefact (A1), `pick` reports a sliding cube as held (A2), Q1 and Q2 are one effect in the only cell with headroom (A3), and four README or
PROTOCOL sentences overstate the evidence (D).

**Clarity 7.5.** The README is now accurate about status, plain, and shows the gates and the pilot honestly; PROTOCOL 10 is a real history.
Held back by v1.2 against 1.3, `docs/TASKS.md:52` contradicting the budget rule, the stale ceiling and floor sentences, and no statement of
which test is primary.

```json
{"novelty": 6.5, "rigour": 7.0, "engineering": 7.0, "validity": 6.0, "clarity": 7.5,
 "fixes": [
  "Pose toolset: close_gripper never attaches the grasped object (skills.py:92-97), so every descent with a held cube fails with 'arm/hand would touch cube_green' (9/9) and observe says held: false. Attach on close when an object is between the fingers, add a pose-level oracle/naive gate (100 layouts, 60 calls) to results/, rerun gate.py; otherwise drop the pose cell and claim (i) from this run.",
  "Freeze for real before launch: commit the 20:00 edits, get pytest green (test_a_provider_error_is_not_saved... fails now), make PROTOCOL.md (v1.2) and runner.py (1.3) agree, track run_night.sh, make analysis.load skip and cost the new _aborted lines (it will KeyError on them), and keep analysis.py/render.py out of code_hash().",
  "Q4: the difference of clean-to-disturbed drops is biased against the notebook wherever the fresh agent fails clean (its drop is floored at 0). Add disturbed evaluation to the control cell (runner.py:66 skips it; about 240 episodes) as the primary recovery measure, and report success when disturbed given success clean on the same layout.",
  "Q3: resample (task, run seed) blocks, not layouts, because the cheap arm's four layouts per run share one notebook; replace the percentile bootstrap at ceiling (60/60 vs 60/60 gives [0,0] and 'yes', and tests/test_analysis.py asserts that); add the cheap-without-memory vs frontier row; label the frontier as effort low; add the cost column including practice, rewrites and aborted attempts.",
  "PROTOCOL section 1: name one primary test per question with Holm over the two models and mark the rest secondary; say Q1 is success within a 20-call budget and that Q1 and Q2 are the same effect in the one cell with headroom; correct 'two cells at ceiling' to five of six (pilot20b) and the oracle floors to 5/9/5.",
  "Add the difference in differences on calls_to_success (catch minus control) to analyze.py, stratify the pooled bootstrap by task, and use BCa or a sign-flip test for the 10-cluster per-task rows.",
  "spend.py:33 prices Fable 5.2 cache reads at 0.10 of input; the published rate is 0.025 ($0.20 per million). Safe for the cap but it overstates frontier cost in the Q3 table; make CACHE_READ per model and analyse runs/frontier_exp, which no code reads today.",
  "pick reports ok/holding for a sliding cube at lift_height=0.05 (10/10); re-check after a 1 s dwell before launch or leave it and document it. Correct README lines 17 and 61 ('cannot hold', 'change nothing') and docs/TASKS.md:52 (budget tightening promise)."
 ]}
```

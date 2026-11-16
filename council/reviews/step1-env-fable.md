# Step 1 review (environment, tools, gates, disturbances, spend meter, agent loop) - judge: fable

Date: 16 Nov 2026. Read-only review. `pytest`: 59 passed in 11 s. I ran scripted probes with no model calls
(seeds 60000-60019, used by nothing else) and read the in-progress pilot files in `runs/pilot20/`.

## Verdict in one paragraph

The build is much stronger than the step 0 plan: the catches are physical, the gates are real, the simulator is
deterministic, the spend meter reserves before each call and is tested under concurrency, and evaluation memory is
frozen. But the pilot data and my probes show four defects that would corrupt the main run if it started now. The
bins success rule does not match the instruction the model is given, a legal tool sequence leaves the arm stuck for
the rest of the episode, one "decoy" setting defeats the stack catch, and a provider error is saved as a task
failure and fed into the notebook. The protocol also does not yet handle the "gain shows up as fewer calls" outcome
honestly, because the call budget is about to be chosen after looking at model results with no rule written first.

## Findings that can change the numbers (most serious first)

**1. Bins: the instruction and the success rule disagree, so no-memory bins is scored 0 for a valid solution.**
The model is told "into bin_red ... resting inside the bin" (`robot_play/env.py:141-142`). The rule requires
`0.01 < z < 0.05` (`env.py:103`), which is "on the bin floor". In `runs/pilot20/claude-haiku-5-5__bins__none...jsonl`
all 8 episodes fail the same way: Haiku gives up on `place`, carries each cube over the bin with `move_to`, opens
the gripper, and the second cube lands on the first (final z = 0.062, inside the bin, sorted correctly). Every one
is recorded as a failure and 7 of 8 as a `false_success_claim`. This deflates the no-memory baseline and inflates
the false-claim rate, and it would make memory look good for the wrong reason (learning the grader, not the catch).
Only `place` knows about the two slots (`skills.py:194-198`), and nothing the agent sees says there are slots.

**2. Bins: a legal call sequence leaves the arm permanently stuck.** Reproduced on seed 60001: `pick`, then `move_to`
the bin centre at z = 0.10 (the planner accepts it, the physics result reports `touched: ["bin_red_wall4"]`), then
`open_gripper`. After that `move_to`, `home` and `pick` all return `no collision-free path: arm/hand would touch
obstacle`, for the rest of the episode (20 of 20 seeds in my probe). The cause is that the start pose is already in
collision, so `Mover.plan` (`motion.py:165-176`) can never succeed, and the error names a generic "obstacle" and not
the wall. This killed a real pilot episode (Luna, bins, seed 50000, calls 10-17). There is no recovery path, and
the planner and the physics disagree about whether the first move was free.

**3. Stack: `yaw_offset_deg` is not a decoy, it defeats the catch.** Probe, 20 seeds, green cube, `normal` grip:

| pick setting | green pick reported ok | tower success |
|---|---|---|
| defaults | 0/20 (matches the gate) | 0/20 |
| `yaw_offset_deg=45` | 20/20 | **17/20** |
| `speed=slow` | 1/20 | 0/20 |
| `lift_height=0.05` | 20/20 (cube still slipping) | 0/20 |
| `grip_level=firm` | 20/20 | 20/20 |

README says `yaw_offset_deg` and `lift_height` "do nothing useful", and PROTOCOL section 2 says "a normal squeeze cannot
hold it". Both are false as written. In the pilot, Luna lifted the green cube with `normal` grip and `speed=slow`
on seed 50001 (rise 0.135 m, success in 6 calls). The gate only tests the all-defaults script, so it cannot see
any of this. `lift_height=0.05` also makes `pick` report `ok: true, holding` for a cube that is sliding out.

**4. A provider error is written as a finished, failed episode and updates the notebook.** In `runner.py:86-97` the
episode row is appended and `update_memory` is called before the `provider error` note is checked. On resume that
row counts as done, so an outage becomes a task failure and a notebook rewrite from a truncated transcript.
`llm.py:77` retries a rate limit only 3 times with 2, 4, 8 s waits, so with 8 workers this will happen.
`max_tokens` and refusal stops are also scored as plain failures with only a note.

**5. The disturbance gate is reported on the seeds it was tuned on.** PROTOCOL section 10 says the nudge was tuned on
seeds 2000-2029 "so that the gate passes", and `results/disturbance.md` is those same 30 seeds. Bins nudge passes
at 24/30, exactly the 80% line. The thresholds (95% / 30% / 80%) live only in `scripts/gate_disturbance.py`; the
"section 7 check list below" that section 10 points to does not exist.

**6. Q4 mixes knowing the catch with recovering from the disturbance.** The "fresh" agent (`none`) has to find the
catch and recover inside one budget; the notebook agent only has to recover. A positive Q4 could be Q1 again.
Also "denominator = episodes in which the disturbance fired" conditions on something the agent controls (a slip
needs a 3 cm lift, which a fresh agent on stack often never achieves), so the two arms are compared on different
episode sets. With 4 evaluation layouts per run there are 10 slip and 10 nudge episodes per cell.

## Does the protocol handle "success may not rise, calls may fall" honestly? Not yet.

- Q2 exists, which is good, but it is "calls, seconds and dollars **per successful episode**". That is undefined when
  an arm has zero successes (bins, no memory: 0/10 in the pilot) and it is survivor-biased everywhere else, because
  the no-memory arm only succeeds on the easy layouts.
- The pilot shows where the room is. Flasks: 11/11 with no memory, median about 8 calls against a 6-call floor.
  Stack with Luna: 7/7 in 6-10 calls. So Q1 has no headroom on those cells and Q2 has about 1-2 calls of headroom.
  The protocol should say this before the run, with the oracle call floor per task (6, 10, 6) as the reference.
- The call budget is "pending" and will be picked after looking at no-memory model results. Section 10's heading says
  none of the changes "used model results", `docs/TASKS.md` says the budget will be tightened if "every model solves
  every job", and section 10 says "practice seeds" while the pilot uses 50000+. Choosing the budget so that discovery
  does not fit is choosing the Q1 answer. It needs a mechanical rule written before the choice, and the budget
  sensitivity shown.
- Section 3 still says 30 calls, `Task.max_calls` is 20, `env.MAX_CALLS = 30` is dead code.
- The control clause ("no comparable gain in the control") is empty for Q1 when the control sits at 100%, and
  "comparable" has no number. For Q2 it matters a lot: a notebook will cut calls in the control scenes too (fewer
  `observe` calls, known tool habits), so Q2 needs the quirk-minus-control difference as the test.
- Five runs per cell is too few clusters for a bootstrap interval to have its stated coverage, and there is no
  statement of which pooling is primary or how 2 models x 3 tasks x 2 memory types x 4 questions are corrected.

## Scores

**Novelty 6.5.** The combination (skill tools with decoys, gated physical catches, frozen-memory held-out curves,
disturbance by physics, pre-stated margin) is clearly stated and honestly credited in PROTOCOL section 9. But two of
three catches are visible in `observe` (bin height 0.13, flask width 0.10) or named by the planner error, and the
pilot shows cheap models solving flasks and stack first try. The "hidden quirk" angle is thinner than claimed; the
PhysMem/PhysCaP overlap is larger once only stack is truly hidden.

**Rigour 6.0.** Good: paired seeds across models and conditions (`agent.py:32-38`), disjoint practice/eval/gate
seeds with a test, frozen evaluation memory with a test, control scenes, dose-response, false-claim logging. Weak:
budget chosen after seeing model data with no rule, Q2 metric conditioned on success, Q4 confound, disturbance gate
on tuning seeds, 5 clusters, no decoy audit, Anthropic runs with no `thinking` setting while OpenAI gets
`reasoning: low` (`llm.py:109,186`), which is not "the same setting" and is described as "provider defaults".

**Engineering 6.5.** Clean small modules, deterministic sim (repeat run identical), 59 fast tests, reserve/settle
meter with file lock, ledger, restart and concurrency tests, retries metered per attempt, no secrets tracked,
`runs/` ignored. Faults: finding 4; the OpenAI reservation adds a flat 6,000 tokens for history instead of a worst
case (`llm.py:214`), so section 6.1 is not strictly true for Astra; one provider hitting its cap terminates the whole
pool including the other provider (`runner.py:119-123`); `uv.lock`, `Makefile`/`make report` named in PROTOCOL and
README do not exist; SDKs are unpinned (`anthropic>=0.60`); prices are "third-party lists" not yet reconciled.

**Validity 5.0.** Findings 1-3 each move a headline number today: bins no-memory is 0% for a grading reason, a trap
state ends episodes, and a decoy solves stack. The gate table is true but narrow (defaults versus one oracle), so
"the catch really does stop a naive attempt" holds only for the exact default call. The catches themselves are
real physics, the success rule is simulator-only, and nothing leaks through text; those parts are sound.

**Clarity 6.5.** The README analogy, tables, hand-play transcripts and `HOW_IT_WORKS.md` are easy to follow. But the
README status block is stale against the repo (says no model has run and that the agent loop, spend meter and
memory are "not done"; folder map omits `spend/llm/agent/runner`; disturbances "still need validation"), the 20
versus 30 budget conflict, and `uv sync` with no lock file mean a stranger cannot reproduce it exactly.

## Fixes, most valuable first

1. Make bins fair: either change the instruction to say each cube must rest on the bin floor (and expose the two
   slots or make `place` the only sensible route), or accept any cube fully inside the bin. Re-run the gate and the
   bins pilot afterwards; discard the current bins pilot rows.
2. Remove the stuck-arm state: when the start pose is in collision, allow a straight retreat upward (or resolve
   the penetration), name the real body in the error, and make the planner check use the real finger opening and a
   margin so it agrees with the physics. Add a test: pick, `move_to` inside a bin, open, `home` must succeed.
3. Run a decoy audit and publish it in `results/`: for each task, each single setting changed from default over its
   range, 30 seeds, quirk and control. Then fix or re-label: clamp or redesign `yaw_offset_deg` so a diagonal grip
   does not hold 250 g, make `pick` re-check holding after a 1 s dwell so a slipping cube is not reported held,
   and correct the README/PROTOCOL sentences ("cannot hold", "do nothing").
4. Pre-register the efficiency outcome before the budget is chosen: co-primary = calls to simulator-verified
   success with failures counted at the budget, paired by layout, tested as (memory minus none) in quirk scenes
   minus the same in control scenes; report success-within-k-calls curves for every k so the budget choice cannot
   make the result; set the budget by a written rule (for example 2x the oracle call count per task); state the
   oracle floors and that flasks and stack are expected to show calls, not success. Record in section 10 that the
   pilot used no-memory model results on layouts 50000+, and fix the 20/30 conflict.
5. In `runner.py`, do not write the row or update memory when an episode ends on a provider error, `max_tokens` or
   budget stop; redo it on resume. Raise the rate-limit retry count and wait, and stop only the capped provider.
6. Fix Q4: compare the drop from clean to disturbed within each arm (difference in differences on the same
   layouts), or add a disturbed control-scene cell; use all disturbed episodes as the denominator and report the
   fire rate separately; re-validate both disturbances on fresh seeds and put the thresholds in section 7.
7. Make the provider settings truly matched and recorded: set thinking/reasoning explicitly for both, log reasoning
   tokens per episode, reconcile the ledger against both billing dashboards after the pilot, and make the OpenAI
   reservation a real upper bound.
8. Bring the docs level with the code: update the README status and folder map, commit `uv.lock`, pin the SDKs, add
   the `make report` target or remove the sentence, extend the leakage test to the notebook and replay prompts,
   and say plainly that the bins and flasks catches are visible geometry while only the stack catch is hidden.

```json
{"novelty": 6.5, "rigour": 6.0, "engineering": 6.5, "validity": 5.0, "clarity": 6.5,
 "fixes": [
  "Bins grading mismatch: the instruction says 'resting inside the bin' but env.py:103 requires the bin floor; all 8 Haiku no-memory pilot episodes fail with the second cube resting on the first inside the right bin and are logged as false success claims. Align instruction, slots and predicate, then re-run the gate and bins pilot.",
  "Remove the stuck-arm trap: pick, move_to inside a bin (z=0.10), open_gripper leaves every later move/home failing with 'obstacle' (20/20 seeds; killed Luna bins seed 50000). Allow a retreat from an in-collision start, name the real body, make planner and physics agree, add a test.",
  "Decoy audit per task and setting (30 seeds, quirk and control) published in results/: yaw_offset_deg=45 with normal grip solves stack 17/20, speed=slow lifts the green cube on some layouts, lift_height=0.05 reports a slipping cube as held. Fix or re-label, and correct 'cannot hold' / 'do nothing' in README and PROTOCOL.",
  "Pre-register the efficiency outcome before choosing the budget: calls to verified success with failures counted at the budget, paired by layout, as a quirk-minus-control difference; success-within-k-calls curves; a written budget rule (e.g. 2x oracle calls); state oracle floors and that the pilot's no-memory model results informed the budget; fix the 20 vs 30 call conflict.",
  "runner.py:86-97: an episode that ends on a provider error, max_tokens or refusal must not be saved as a failed episode or update the notebook; redo it on resume, lengthen rate-limit retries, and stop only the provider that hit its cap.",
  "Q4: separate recovery from catch knowledge (clean-to-disturbed drop within each arm, or a disturbed control cell), use all disturbed episodes as the denominator, and re-validate both disturbances on seeds not used for tuning with thresholds written in section 7.",
  "Match and record provider reasoning settings explicitly (Anthropic sends no thinking setting, OpenAI sends reasoning low), log reasoning tokens, reconcile prices against billing, and make the OpenAI reservation a true worst case.",
  "Docs and reproducibility: update the stale README status and folder map, commit uv.lock and pin SDKs, add or drop 'make report', extend the leakage test to notebook/replay prompts, and state that bins and flasks catches are visible geometry and only stack is hidden."
 ]}
```

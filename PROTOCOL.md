# robot-play protocol (overnight pilot, v1.2)

This document is written **before** the paid experiments run. It fixes what is compared, how many runs there are, what counts as success, which numbers
answer which question, and which results would count against each claim. Anything that deviates from it in the results is listed in `results/RESULTS.md`
under "Deviations". Section 10 lists every change made to the setup and why, including the ones made after looking at a few live model runs.

## 1. Questions, measures and what would count against each claim

Setting: a language model orchestrates a simulated Franka Panda through tools built on inverse kinematics and collision-checked motion planning. No weights
are trained. Each task has a physical **catch** (section 2). Between episodes the model may update a small memory (section 4).

A **run** is one model on one task with one memory condition and one run seed: 12 practice episodes with the memory carried over, then 4 **held-out**
evaluation episodes on layouts the practice never used, with the memory frozen. All intervals are 95% **cluster-bootstrap** intervals (10,000 resamples) that
resample whole runs or whole layouts, never single episodes, because episodes inside a run share a memory.

| ID | Question | Primary measure | The claim is *not* supported if |
|---|---|---|---|
| Q1 | Does experience raise success on a task with a catch? | Held-out success, memory (notebook, replay) minus none, same model, paired by (task, run seed). Secondary: the **difference in differences**, (gain with the catch) minus (the same gain in the no-catch control scenes) | The interval of the paired difference includes 0. We only say the gain is *because of the catch* if the difference-in-differences interval also excludes 0 |
| Q2 | Does experience make it faster and cheaper? | **Calls to success**: the number of tool calls an episode used if it succeeded, and the full call budget if it failed (so a failure is never hidden and a run with no successes still has a value). Paired by (task, run seed), memory minus none. Also: share of episodes that succeeded within k calls for k = 6 to 20, simulated seconds, and dollars per episode | The interval of the paired difference includes 0. Dollars per success is reported only where there were successes, and as secondary |
| Q3 | Can a cheap model with experience come within a stated margin of a frontier model's first try? | Gap = frontier first-try success minus cheap-with-notebook success **on the same layouts**, clustered by layout (task, evaluation seed) | The upper end of the gap's interval is not below **+10 percentage points**. Then we report the gap with its interval and do not say "matches". Cost counts **every** paid call of the cheap model (practice, notebook rewrites, evaluation, retried attempts) |
| Q4 | Does experience help recovery from a disturbance? | Each memory condition's own **drop** in success from clean to disturbed on the same layouts (clean minus disturbed, **all assigned disturbed episodes** as the denominator), then notebook's drop minus fresh's drop. This isolates recovery from simply knowing the catch | The interval of the difference of drops includes 0. The firing rate (how often the disturbance actually happened) and success among episodes where it fired are reported next to it, because an agent can influence whether a disturbance fires |

Null results are reported. Every number in the README comes from `results/RESULTS.md`, which `python scripts/analyze.py` regenerates from the run files.

**Floors and ceilings, stated up front.** The scripted oracle needs about 6 calls for `stack`, 10 for `bins` and 6 for `flasks`, so no memory can bring the call count
below those floors. Success has no room to rise where a model already succeeds without memory: the no-memory pilot (section 10) showed two such cells (Haiku on
`flasks`, Luna on `stack`). They stay in the matrix and are reported as they are; the effect for those cells can only show up in calls, seconds and cost.

## 2. Environments

- Robot: Franka Panda (MuJoCo Menagerie, pinned to commit `370c439`, see `scripts/fetch_models.sh`). The SO-101 is future work; it is not in this pilot.
- MuJoCo 4.0.1; Python dependencies pinned in `uv.lock`; the two SDKs are pinned in `pyproject.toml`. Physics timestep 2 ms.
- Three tasks, each with one catch that is **fixed across all seeds** (the layouts are resampled each episode, the catch is not):

| Task | Goal (decided only by the simulator, after the model says `done` or runs out of calls) | Catch | Control scene (no catch) |
|---|---|---|---|
| `stack` | Red, green, blue stacked in that order, each within 12 mm of the stack axis, and **still for 1 s** (no object drifting more than 5 mm during that second) | The green cube weighs 250 g (the others 50 g) and has lower friction (0.5 against 0.9). **Hidden**: weight and friction are never shown | Green cube 50 g, friction 0.9 |
| `bins` | Every cube inside the bin of its colour: inside the bin's footprint, above its floor, below the height of two stacked cubes, and still for 1 s | The bin walls are 12 cm tall. **Visible geometry**: the wall heights are in `observe`. What they imply (the hand cannot reach over them while holding a cube low) is never stated | 1.5 cm walls |
| `flasks` | Both flasks upright (under 10 degrees) within 3 cm of their rings, standing on the floor and still for 1 s | Each flask has a 10 cm wide, 7 cm tall base under a 4 cm wide neck. **Visible geometry**: the flask sizes are in `observe`. The open hand is 8 cm wide, so the fingers land on the base | Plain 5 cm cylinder of the same height |

- Only the `stack` catch is hidden. For `bins` and `flasks` a model could in principle work it out from the visible sizes; the catch there is that the *consequence* has to be discovered by trying. The README says so.
- The collision model used by the planner is **identical** in catch and control scenes: the tools never route around a catch for the model.
- Settings that fix a catch are allowed and are written down, not assumed away: `results/settings_audit.md` changes one tool setting at a time and reports, per task, which settings alone solve or break which task. A setting that happens to solve a catch is another way to succeed, not a bug.

## 3. Tools (what the model can do and see)

Two toolsets. **Skills** (the main one): `observe`, `pick(object, grasp_height, speed, grip_level, yaw_offset_deg, lift_height)`, `place(target, release_height, speed,
settle_time)`, `move_to(x, y, z, speed)`, `open_gripper`, `close_gripper(grip_level)`, `home`, `done`. **Pose** (an ablation): the same without `pick` and `place`, so the model builds
them from moves and the gripper; its call budget is three times larger.

- Descriptions are neutral. They say what a setting is, never which value is good for which task, and never mention a catch (`tests/test_leakage.py` checks the prompts, tools, observations, failure messages and the memory prompts).
- Tools return **measured facts only**: finger width, how far the object rose, tilt, contacts, planner and IK failure reasons. They never state a cause.
- `observe` returns exact simulator poses (no perception noise in the pilot).
- **Call budget: 20 tool calls per episode in the skills toolset (60 in the pose toolset), including `observe`.** Rule: twice the oracle's calls on the longest task (bins, 10). It was in the code from the first commit and was **not** changed after the pilot.
- **One tool call per turn.** Parallel tool calls are switched off for both providers, so every call sees the result of the one before it.
- A reply with no tool call is answered with one reminder, at most twice. Provider failures and cut-off replies are **not** recorded as failed episodes (the run stops and the episode is redone on resume). A refusal by the model's safety system is recorded as a failed episode and counted.
- Success is decided only by the simulator. The model's own claim is logged and the rate of "said done, simulator disagreed" is reported.

## 4. Memory conditions (all without training)

| Condition | After each practice episode the model gets | Cap |
|---|---|---|
| `none` | nothing carried over | none |
| `notebook` | its own notebook, rewritten by the same model from the simulator's verdict and a shortened transcript (replace, not append). The writer is told object positions change every attempt | 600 tokens (2,400 characters) |
| `replay` | the transcript of its most recent successful practice episode on this task, if any | 1,200 tokens (4,800 characters) |

Caps are enforced as character caps at 4 characters per token. Evaluation episodes never change the memory. The tokens added to each episode's prompt are logged.

## 5. Experiment matrix and budget

Layout seeds: practice `10,000 + 100 x run seed + i`, evaluation `20,000 + 100 x run seed + j`. They are disjoint (tested), shared by every model and memory condition (so comparisons are
paired on the same layouts), and above every seed the validation gates used. Seeds 50,000 and up and run seed 99 were used for smoke tests and the pilot and are **excluded from every reported result**.

| Cell | Models | Tasks | Conditions | Run seeds | Episodes |
|---|---|---|---|---|---|
| Main | Haiku 5.5, GPT-6 Luna | 3 | none, notebook, replay | 10 | 2 x 3 x 3 x 10 x 16 = 2,880 |
| Disturbed evaluation (Q4) | same | 3 | none, notebook | 10 | the 4 evaluation layouts again with a disturbance (slip on layouts 1 and 3, nudge on 2 and 4): 2 x 3 x 2 x 10 x 4 = 480 |
| Control (no catch) | same | 3 | none, notebook | 5 | 2 x 3 x 2 x 5 x 16 = 960 |
| Frontier first try (Q3) | Fable 5.2, GPT-6 Astra | 3 | none | 20 layouts each (the first 20 evaluation layouts) | 2 x 3 x 20 = 120 |
| Frontier with experience | Fable 5.2 | 3 | notebook | 5 | 3 x 5 x 16 = 240 |
| Pose-level tools | Haiku 5.5, GPT-6 Luna | 3 | none, notebook | 3 | 2 x 3 x 2 x 3 x 16 = 576 |

- Hard stops: Anthropic **$90** of a $100 budget, OpenAI **$45** of a $50 budget. If measured cost makes the matrix infeasible, cells are dropped in this order: pose, control seeds, replay, frontier with experience.
- Pinned IDs: `claude-haiku-5-5`, `claude-fable-5-2`, `gpt-6-luna`, `gpt-6-astra`.
- Provider settings, identical in spirit for every model: Anthropic `effort: low`, adaptive thinking left at its default (no `thinking` field is sent), default sampling, no refusal fallback (a silent switch to another model would corrupt "which model did this"); OpenAI Responses API with `reasoning.effort: low`, default sampling. Maximum output per turn: 6,000 tokens including thinking. The two providers do not think in the same way; that difference is part of what the cheap-versus-frontier comparison measures and is stated in the results.
- Runs execute in parallel worker processes. Every run is a JSONL file whose first line records the full configuration (model, task, memory condition, seeds, call budget, the complete episode plan and a hash of every prompt and tool schema). **A file whose configuration differs is never resumed.**

## 6. Spend meter (enforced in code, covered by tests)

1. Before every paid call the worst-case cost is **reserved** under a cross-process file lock, and a call that would pass the cap is refused before anything is sent. The worst case prices every estimated input token at the dearest input rate (the cache-write rate) and assumes the full 6,000 output tokens. After the first call of an episode, the input estimate is the provider's own token count of the conversation so far plus the new text, plus 10%.
2. After the call the reservation is replaced by the real cost from the response's usage (cached input and cache writes included). A call whose real cost is higher than its reservation is recorded as an **overrun** in the ledger and in the totals, so a too-low estimate cannot be silent.
3. Anthropic prices are the published list. OpenAI prices could not be checked against an official list from here, so the meter charges **twice** the assumed OpenAI price: the cap can only be reached early. Reported dollars use the plain list price.
4. A failed call that may have been billed (timeout, server error) is charged at its full reservation. Only failures that happen before the provider processes anything (bad request, rate limit, bad key) are released free. Every attempt, retries included, is counted in the episode's cost.
5. The ledger is a JSONL file that survives restarts. `reconcile` recomputes the totals from the ledger alone and compares them with the running state. When one provider reaches its cap, only that provider's remaining runs are skipped.
6. The council's judge calls run on the user's subscriptions and are not part of these caps.

## 7. Validation gates (before any paid run, on the final setup)

All gates play through `Episode`, the same wrapper a model uses (same call budget, same defaults, same `done` rule).

1. **Oracle gate:** on 100 layouts per scene, the scripted oracle succeeds in at least 95% and the naive script (all defaults) in at most 30%. In the control scenes the naive script succeeds in at least 90%.
2. **Dose-response:** naive success against the catch parameter (cube mass, wall height, flask base height), 30 layouts per point, so a null learning curve can be told apart from a catch that does nothing.
3. **Settings audit:** the naive script changing one setting at a time (`results/settings_audit.md`).
4. **Disturbance gate** on layouts **not used for tuning**: the disturbance fires in at least 95% of episodes; a script that knows the catch but never reacts succeeds in at most 30% of the episodes where it fired; a script that re-tries succeeds in at least 80%. The nudge was tuned on layouts 2,000 to 2,029 (`results/disturbance_tuning_seeds_2000.md`); the reported gate uses layouts 3,000 and up.
5. **Predicate tests:** positive and negative cases for each success predicate, including a cube resting on another cube inside a bin and a tower still moving during the one-second window.
6. **Leakage tests:** no catch value or hint appears in anything a model is shown, which of the catches are visible geometry is tested, and practice and evaluation layouts are disjoint.

## 8. Disturbances (Q4)

Applied by physics, not by editing state: (a) *slip*: the gripper is commanded open for 0.15 s after the object has been lifted 3 cm; (b) *nudge*: a 0.3 s horizontal force of
1.1 times the object's weight, pointing within 45 degrees of the x axis (from the front or back, because a sideways shove is caught by the open fingers), applied the first time the open
hand descends next to an object that is not yet grasped. Timing is fixed relative to events, the same for every condition. The disturbed evaluation episodes reuse the four held-out layouts of each run, so each
layout has a clean and a disturbed outcome. "Tool failure" and "instruction change" are text injections and are not in the pilot.

## 9. Related work and the claimed gap

Verified against abstracts or full text (see the README for links):

| Work | What it does | Closest overlap |
|---|---|---|
| RoboARCade (2611.08209) | 22 long-horizon MuJoCo tasks, agents use pose-level MCP tools; one successful demo in context lifts success; reports false success claims | In-context improvement and the false-success finding are theirs. We do not claim them as new |
| WICL / RoboScript (2611.12885) | Rehearses in simulation from one demo, stores a frozen "task memory", 83.4% on RoboTwin 2.0 | Memory learned without gradients |
| GPT-Policy (2609.19138) | VLM with IK-backed pose tools on real robots, context from videos and interaction history, 3 trials per condition | Tool-calling agent and interaction feedback |
| PhysMem (2602.20323) | Frozen VLM planner builds and verifies hypotheses about physical principles at test time | **Closest** on hidden physics plus memory |
| Act-Observe-Rewrite (2603.04466) | LLM rewrites controller code between episodes (robosuite Lift, PickPlaceCan, Stack) | In-context policy learning across episodes |
| PhysCaP (2608.21031) | Code-as-policy agent explores to infer hidden mass/stiffness | Hidden physical properties |
| Voyager, ExpeL, Reflexion, REFLECT, DoReMi, Inner Monologue | Skill/lesson memory and reflection in games or robot planning | Memory mechanisms |
| LangPert, ROBOREPAIR, EmbodiedBench | Perturbation handling, recovery, benchmarks | Disturbances |

**What we claim is new is the combination, not any single axis:** (i) the same task played through a skill-level and a pose-level tool API, so the effect of the abstraction on learning from experience is measured, not assumed;
(ii) catches validated by oracle gates, dose-response sweeps, a settings audit and no-catch controls; (iii) learning curves over 12 practice episodes with frozen-memory held-out evaluation and cluster-bootstrap intervals;
(iv) disturbance recovery as a function of experience, with the clean-to-disturbed drop as the measure; (v) a cost-matched cheap-versus-frontier comparison with a pre-stated equivalence margin; and (vi) every paid call, including failed retries and memory-writing calls, counted by an enforced spend cap.

## 10. Changelog and history (everything below happened before any reported run)

**v1.1, 16 Nov 2026.** Built the environment and played each task by hand through the tool interface. `bottle` (top-heavy, pinch-height quirk) became `flasks` (wide base, neck grasp): with a top-down hand the palm sits 4 cm above the fingertips, so a low pinch on a tall object is impossible, and a top-heavy bottle did not flop because the finger pads resist twisting. The stack cube changed from 0.9 kg to 250 g (the firm squeeze holds about 300 g); the gripper force was scaled 5 times so `light`, `normal` and `firm` differ. Contact physics became stricter (elliptic friction cone, `impratio` 10, finger-pad twisting friction). The nudge force and direction were tuned on layouts 2,000 to 2,029. No model results were used.

**v1.2, 16 Nov 2026, after the first live runs and the first council review.** Here is exactly what the model and the council changed, in order:

1. *Live smoke tests* (three episodes on layouts 50,000 and up; Haiku on `stack`, Luna on `bins`). Haiku issued dependent calls blindly in one turn (a `place` together with the `pick` that had just failed), so parallel tool calls were switched off for both providers. This is a validity decision about the harness, not tuning on outcomes.
2. *No-memory pilot* (48 episodes: Haiku and Luna, 8 layouts per task, layouts 50,000 to 50,007, call budget 20). Results informed the council review and the discussion of floors and ceilings in section 1. They did **not** change the call budget (section 3).
3. *Memory smoke test* (112 episodes, run seed 99, old code). It confirmed the notebook and replay loops work end to end. It showed that notebooks recorded episode-specific positions, so the notebook writer is now told not to. These episodes are excluded from every reported result.
4. *Council review 1* (Fable and Codex) found real defects, all fixed before any reported run: (a) the `bins` instruction said "resting inside the bin" while the predicate demanded the bin floor, so a cube resting on the other cube in the bin was marked wrong (all 8 pilot episodes of one model failed this way); the predicate now matches the instruction; (b) after `open_gripper` inside a tall-walled bin the hand touched the wall and every later move failed ("stuck arm"); the planner can now lift the hand straight out of a contact it starts in, and may not touch anything new on the way; (c) the stack predicate checked positions only at the end of its settle second, so it now also requires no object to drift more than 5 mm during that second; (d) "decoy" settings were not all harmless (for example a 45 degree hand turn can build the tower with the default grip), so the wording was corrected and a settings audit was added; (e) the validation gates bypassed the call budget, so they now play through `Episode`; (f) provider errors were saved as failed episodes, resumes did not check the configuration, a rate limit stopped everything, and the spend cap did not bound later calls of a conversation or cache writes: all fixed (sections 3, 5, 6); (g) the disturbance gate reported the layouts it was tuned on, so it now uses fresh layouts.
5. *Scope*: the budget was far larger than needed (measured cost about $0.002 per Haiku episode), so seeds were doubled in the main cell, a pose-level ablation and 20 frontier layouts were added, and the efficiency measure (calls to success) was fixed before any reported run.

Validation evidence: `results/gate.md`, `results/dose_response.json`, `results/settings_audit.md`, `results/disturbance.md`, `tests/`, and the hand-played transcripts in `docs/TASKS.md`.

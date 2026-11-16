# step0-plan review (judge: fable)

Reviewed: `NIGHT-2026-11-16.md` (83 lines) and `pyproject.toml`. No code exists yet, so engineering and validity are scored on what the plan commits to, not on intent.

What I checked: the arXiv abstract pages for 2611.08209, 2611.12885 and 2609.19138, plus one web search for missing prior work. I did not read the full papers, so table cells that the abstracts do not state are marked "unverified" below, not "wrong".

## 1. Novelty: 6.0

- The gap is real only as a combination. Each column of the table (NIGHT:11-18) already exists somewhere; no single axis is new. RoboARCade's abstract already reports in-context improvement without human input (one demo lifts Astra 53.5% to 73.0% on five tasks; a self-revised prompt reaches 72.0%) and already reports that agents wrongly claim success, so "false-success claims" (NIGHT:46) is a replication, not a contribution.
- The "hidden quirks" column says "none/No" for everyone, but the search turned up PhysMem (2602.20323: a VLM planner that builds test-time memory of physical principles from its own experience), PhysCaP (code-as-policy agent that explores to infer hidden physical properties; ID unverified) and Act-Observe-Rewrite (2603.04466: an LLM rewrites a controller between trials on robosuite, no gradients). These three sit closer to the claimed gap than Voyager or ExpeL and are absent. Reflexion, REFLECT and DoReMi are also missing.
- Unverified cells: RoboARCade "pose tools" and "2 prompt-revision rounds", GPT-Policy "3 trials per condition" and "IK-backed pose tools". GPT-Policy's abstract says it learns from "interaction feedback" at deployment, which the row undersells. The WICL row matches its abstract.
- The cheap-with-experience versus frontier-first-try headline (NIGHT:7) is the one bold, clearly stated angle. Keep it, and make it the paper.

## 2. Rigour: 4.5

- No numbers are committed: seeds per cell, episodes per run, temperature, model snapshot IDs and the stopping rule are all absent. "Bootstrap confidence intervals over seeds" (NIGHT:51) must be a cluster bootstrap over runs, because episodes inside one run share a memory and are not independent.
- The headline is confounded as written. Frontier gets no experience and cheap gets N episodes, so the comparison needs the fourth cell (frontier with experience, even if tiny) and an equivalence margin stated up front. "Matches" with 10 frontier episodes is a plus or minus 30 point interval, which supports nothing.
- Leakage is not addressed. The plan never says what stays fixed across episodes (the quirk) and what is resampled (poses, sizes), so a rising curve could be scene memorisation. It needs frozen-memory evaluation on held-out seeds, and a control environment with no quirk where memory should give no gain.
- Memory conditions are not token-matched (replay and macros add context that "none" lacks), and the pose-versus-skill ablation in the table (NIGHT:18) never appears in the order of work (NIGHT:61-66).

## 3. Engineering: 4.0

- Nothing is built, and the scope for one night is five tasks, two robots, IK, RRT-Connect, four memory modes, five disturbances and two providers. The 95% oracle gate (NIGHT:61) is the right first step; the plan has no cut list for when it slips.
- `pyproject.toml:7` says `mujoco>=3.2` while NIGHT:82 says the environment is MuJoCo 4.0.1. Contact behaviour changes across versions, so quirk results are not reproducible without an exact pin and a lock file. No `[project.scripts]` entry point, no linter, no retry library.
- The spend meter is one sentence (NIGHT:57). To "really enforce" it needs: a reservation of worst-case cost before each call (input tokens plus `max_tokens`), a lock for concurrent workers, a ledger on disk that survives restarts, retries and cache-read/cache-write prices counted, and a test that a mocked over-budget call is refused. It should also say whether council judge calls draw on the same $90.
- I did not inspect `.gitignore` or the `.venv`; the no-secrets check is still open.

## 4. Validity: 4.5

- Two of the four example quirks are not hidden physics. "A perception bias on one object" (NIGHT:27) is an offset added to the `observe` return, which is a text trick by the rubric's own definition. "An out-of-reach zone" (NIGHT:28) is real kinematics but is revealed by the first IK failure, so it tests reading an error, not learning.
- The skill layer can erase the other two. If the planner's collision model includes the bin lip, `place` routes over it and the quirk never fires; if `pick` chooses its own grasp height, the slip quirk never fires. The plan must state that quirks act only through parameters the agent sets, and that the planner's collision model is the same in quirk and control scenes.
- The tool signatures leak the answer: `grasp_height?` and `release_height?` (NIGHT:23) name the exact axes the quirks live on. "Honest feedback" must report only measurable facts (object z dropped, contact lost at t), never the cause.
- "A naive script fails some" (NIGHT:62) is too weak a proof. Each quirk needs a measured gap (informed oracle at least 95%, naive at most 30%) and a dose-response sweep of the physical parameter, or a null learning curve cannot be told apart from a quirk that does nothing.

## 5. Clarity: 6.5

- The plan is short, the question is stated in two sentences and the table makes the positioning quick to read. A stranger understands the idea in about two minutes.
- It is not yet a protocol: no hypotheses with pass/fail thresholds, no experiment matrix with cell counts, no cost table. The reader cannot tell what result would falsify the headline.
- Model names lack API IDs, and "where possible" on judge separation (NIGHT:56) is vague given Fable is both an orchestrator and a judge.

## Budget feasibility (my estimate, not measured)

Assumptions: about 20 tool calls per episode, about 6k input tokens per call as history grows, about 4k output tokens per episode. That is roughly 120k input tokens per episode.

| Model | Cost per episode | Episodes the cap buys |
|---|---|---|
| Haiku 5.5 / Luna ($0.10/$0.50) | about $0.015, or $0.03 with replay in context | 1,500 to 3,000 per provider cap |
| Fable 5.2 ($8/$40) | about $1.10 uncached, about $0.35 with prompt caching | 80 uncached under $90 |
| Astra ($10/$50) | about $1.40 uncached, about $0.45 cached | 32 uncached under $45 |

- The full grid implied by the plan (2 robots, 5 tasks, 4 memory modes, 6 models, 75 episodes, 5 seeds) is 90,000 episodes. Cheap models alone would be 15,000 episodes, about $300. It does not fit.
- A grid that fits: 1 robot (Panda), 3 tasks, 3 conditions (none, notebook, replay), 30 episodes, 5 seeds, 2 cheap models. That is 1,350 episodes per model, about $20 to $40 each. This leaves the OpenAI cap nearly full before any Astra call, so the Astra reference must be about 30 cached episodes (about $14) or be dropped.
- Wall clock is the tighter limit. 2,700 episodes at 20 calls and 2 seconds per call is 30 hours in sequence, so the harness needs 8 or more concurrent workers and rate-limit handling from the start. Drop Sonnet 5.5 and 6.1 Sol; they add cost and no claim.
- Measure real tokens per episode in the smoke run (NIGHT:64) and recompute this table before the main run.

## Can the quirks be physically real in MuJoCo?

Yes for three, with care:

1. Slip unless grasped low: build the object from two geoms with different `friction` (slick upper band, grippy lower band), or a tapered frustum, or an off-centre mass via `inertial` that rotates out of a high pinch during lift. Needs `condim` 4 or 6 on the pads and enough solver iterations, or the grasp will be unstable everywhere.
2. Bin lip: plain geometry. The object strikes the lip during a low transit or tips off it on a low release. Keep the lip out of what `observe` reports, but in the physics.
3. Out-of-reach zone needing a push: real kinematics, but make it hidden by having reach depend on something unobservable at first (for example a heavy object that IK can reach but the gripper cannot lift from full extension because of actuator `forcerange`).
4. Perception bias: only real if `observe` reads a rendered camera and the bias comes from optics or occlusion. Otherwise rename it a sensor fault and report it separately from the physical quirks.

The same applies to disturbances: implement "grasp slips" with `xfrc_applied` or a commanded gripper opening, and "object moved" with an applied force, not by writing `qpos`. "Tool fails" and "instruction changes" are text injections; label them as such.

## Scores

```json
{"novelty": 6.0, "rigour": 4.5, "engineering": 4.0, "validity": 4.5, "clarity": 6.5,
 "fixes": [
  "Cut the grid to fit: Panda only, 3 tasks, 3 memory conditions (none, notebook, replay), 30 episodes x 5 seeds, Haiku 5.5 + Luna (about 1,350 episodes and $20-40 per model); drop Sonnet 5.5 and 6.1 Sol; run 8+ concurrent workers; recompute cost from smoke-run token counts before the main run.",
  "Write the protocol before code: fixed seeds, temperature, pinned model IDs, the quirk fixed while poses are resampled each episode, frozen-memory evaluation on held-out seeds, a no-quirk control environment, token-matched memory conditions, and a cluster bootstrap over runs.",
  "Make every quirk physical and prove it: two-friction or tapered or off-centre-mass object for the slip, real lip geometry for the bin, actuator force limit for the reach quirk; require informed oracle >= 95% and naive script <= 30% per quirk plus a dose-response sweep; drop or relabel the perception-bias quirk as a sensor fault.",
  "Stop the skill layer and tool schema from giving the answer away: quirks must act only through agent-set parameters, the planner collision model must be identical in quirk and control scenes, feedback reports measured facts and never causes, and parameter names must not single out the quirk axis.",
  "Fix the headline comparison: add the frontier-with-experience cell (small), state an equivalence margin in advance, and report about 30 cached frontier first-try episodes pooled over tasks with the interval shown; say 'within X points' and not 'matches' if the interval is wide.",
  "Correct the related-work table: add PhysMem (2602.20323), Act-Observe-Rewrite (2603.04466), PhysCaP, Reflexion, REFLECT and DoReMi; credit RoboARCade for in-context improvement and the false-success finding; verify the unverified cells against the full papers; restate the gap as the combination and the cost-matched headline.",
  "Specify and test the spend meter: pre-call worst-case reservation, lock for concurrent workers, on-disk ledger that survives restarts, retries and cache prices counted, a unit test that refuses a mocked over-budget call, and a stated rule for whether council judge calls count against the $90.",
  "Pin mujoco to the installed 4.0.1 with a lock file, add a CLI entry point, and schedule the pose-versus-skill ablation in the order of work or remove it from the table."
 ]}
```

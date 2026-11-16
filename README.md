# robot-play

**Can an AI that only gives orders to a robot arm get better at a job just by practising it?**

Picture a new worker in a workshop. On day one they do not know that one drill sticks, or that one shelf is too tall to reach with the short ladder. They find out by trying, they make a note, and by day ten they are faster and make fewer mistakes. Nobody retrained them. They just remembered.

This project asks whether a language model can do the same thing with a simulated robot arm. The model never touches the arm's motors. It only calls simple tools such as `pick` and `place`. Behind those tools, ordinary robotics code (inverse kinematics and collision-free motion planning) does the careful movement. We hide a small physical "catch" in each job and watch whether the model finds it, writes it down, and uses it next time.

> **Status, 16 Nov 2026 (night 1).** The simulated world, the tools, three jobs, the checks that prove the jobs are fair, the spend cap, the agent loop and the analysis code are built and tested (108 automated tests). A few live runs have shown the setup works end to end. **The main experiments have not been run yet, so there are no learning results to show.** The plan is written down before running them in [PROTOCOL.md](PROTOCOL.md).

## The three jobs

Each job has one physical catch. The catch is not stated anywhere the model can read. The model has to notice what the simulator reports and change how it acts.

| Job | The catch | Can the model see it? | What a failure looks like | What fixes it |
|---|---|---|---|---|
| **Stack** three cubes into a tower | The green cube is heavy (250 g against 50 g) and slippery. A normal squeeze did not hold it in any of 100 test layouts. | **No.** Weight and friction are never shown. | The fingers close to 1.9 cm and the cube stays on the table. | A firm grip. |
| **Sort** four cubes into a red bin and a blue bin | The bin walls are 12 cm tall, higher than the hand can reach over when it lowers the cube. | **Partly.** The wall heights are in the observation. What they mean for the hand is not stated. | `arm/hand would touch bin_red_wall2` | Letting go from 14 cm up or higher. |
| **Stand** two flasks upright on rings | Each flask has a wide base (10 cm) that the fully open hand (8 cm) cannot get around. | **Partly.** The flask sizes are in the observation. What they mean for the fingers is not stated. | `hand stopped 1.4 cm short of the requested grasp point` | Grabbing the narrow neck near the top (`grasp_height` 0.9). |

Every job also has a **control** version with no catch, so that any improvement we later see can be traced to the catch and not to the model simply warming up.

These clips are me playing each job by hand, using only the tools and the numbers an AI would get (the full transcripts are in [docs/TASKS.md](docs/TASKS.md)). I failed the first attempt in each one, read the measurements, and fixed it.

| Stack | Sort | Stand up |
|---|---|---|
| ![stack](media/stack-hand-play.gif) | ![bins](media/bins-hand-play.gif) | ![flasks](media/flasks-hand-play.gif) |
| [full video](media/stack_seed11-v2.mp4) | [full video](media/bins_seed5-v2.mp4) | [full video](media/flasks_seed7-v2.mp4) |

## How an AI drives the arm

The model gets eight tools, one call per turn, so each call sees the result of the one before it. No tool description mentions a catch, and every result is a measurement, never an explanation.

- **`observe`** shows where every object and zone is.
- **`pick`** moves above an object, goes down, squeezes, and lifts. You can choose where on the object to grab (`grasp_height`), how hard to squeeze (`grip_level`), how fast to move (`speed`), how far to lift (`lift_height`) and how far to turn the hand (`yaw_offset_deg`).
- **`place`** carries the held object to a target, lowers it, lets go, and backs off. You can choose how high above the surface to let go (`release_height`), the speed and a pause (`settle_time`).
- **`move_to`**, **`open_gripper`**, **`close_gripper`**, **`home`** are the basic moves.
- **`done`** ends the episode. The simulator then decides whether the job was really finished. The model's own claim is recorded separately so we can count how often it says "done" when it is not.

The model has 20 tool calls per episode, so wasting calls on discovering a catch costs it. There is also a **pose-level version** with no `pick` and `place`, where the model builds them from moves and the gripper, with three times the call budget. Comparing the two is an exploratory look at whether good building blocks make learning from experience easier; because the budget and the planner's feedback differ too, it cannot isolate the abstraction alone.

## How we know the jobs are fair

A badly made job would give meaningless results. So before any AI is allowed near them, the jobs pass these checks. All of them are played through the same wrapper the AI uses, with the same 20-call budget.

**1. A script that knows the answer always wins, and one that does not always loses** (100 random layouts per row, `python scripts/gate.py`).

| Job | Scene | A script using default settings | A script that knows the catch |
|---|---|---|---|
| Stack | with the catch | 0 / 100 | 100 / 100 |
| Stack | control | 100 / 100 | 100 / 100 |
| Sort | with the catch | 0 / 100 | 100 / 100 |
| Sort | control | 99 / 100 | 100 / 100 |
| Stand up | with the catch | 0 / 100 | 100 / 100 |
| Stand up | control | 100 / 100 | 100 / 100 |

**2. The catch switches on gradually.** For example, a green cube of 150 g is still fine with default settings, and at 250 g it never works.

![dose response](docs/img/dose_response.png)

**3. We know which settings matter** ([full table](results/settings_audit.md), 20 layouts per cell). Changing one setting at a time from its default, exactly one setting rescues each catch: a firm grip for the stack (20 of 20), letting go from 14 cm or higher for the sort (20 of 20), and a high grasp for the flasks (20 of 20). Speed, lift height and the pause after letting go never rescue a catch (all stay at 0 of 20), and fast placing even lowers success in the no-catch scenes (16 to 17 of 20). A few settings do harm without any catch (a light grip, a low grasp on the flasks, letting go at 0 cm). Turning the hand 45 degrees also builds the tower about half the time with the default grip (10 of 20), so there is more than one way to fix the stack. We do not call any setting a harmless decoy.

**4. The disturbances work**, in the catch scenes ([table](results/disturbance.md)) and in the no-catch control scenes ([table](results/disturbance_control.md)), 50 fresh layouts per row, not the layouts the nudge was tuned on. Both the slip (the gripper lets go 3 cm into the lift) and the shove (a sideways push on the object) happened in every episode. A script that knows the catch but does not react never recovered (0 of 50 in every row). A script that tries again recovered in 47 to 50 of 50.

**What this does not prove.** It proves the jobs can be solved, are failed by default settings, and respond to the catch. It does not prove that a language model can learn the catch. That is what the experiments are for.

## A first live look (not a result)

Before the main run, I ran two small models with no memory on 8 layouts per job that nothing else uses (these runs are excluded from every result), on the final code. Each episode cost about a fifth of a cent. ([Full table with the pose-level runs](results/pilot_no_memory.md).)

| Model | Stack | Sort | Stand up |
|---|---|---|---|
| Claude Haiku 5.5 | 4 of 8 | 6 of 8 | 8 of 8 |
| GPT-6 Luna | 7 of 8 | 7 of 8 | 8 of 8 |

Two things stand out. First, some model and job pairs already succeed without any memory, so in those pairs practice can only show up as fewer calls, less time and less money, not as a higher success rate. That matters, and the plan measures it (calls to success). Second, eight layouts is a small sample: the same Haiku on the same stack job scored 1 of 8 in the pilot before the last round of fixes and 4 of 8 now. The jobs where Haiku fails are the ones where a notebook has room to help, because it can start with the grip that worked. A small run of the whole memory loop before the final fixes (112 episodes, one layout set, excluded from results) pointed the same way: Haiku with a notebook finished the stack on all 12 practice attempts, against 5 of 12 without one. One layout set is not evidence, and the real experiment has ten.

## What we plan to measure

All of this is fixed in advance in [PROTOCOL.md](PROTOCOL.md), including what result would count against each claim.

1. **Does practice raise the success rate?** Compare an AI that keeps notes between episodes (or sees its last success) with one that starts fresh every time, on layouts it has never seen. Then check that the gain is bigger where the catch exists than in the control scene.
2. **Does practice make it faster and cheaper?** Count tool calls (a failed episode is charged the whole budget), simulated seconds and dollars.
3. **Can a cheap model with practice come close to an expensive model's first try?** The cheap models are Claude Haiku 5.5 and GPT-6 Luna. The expensive ones are Claude Fable 5.2 and GPT-6 Astra. "Close" means the gap is under 10 percentage points with its whole interval, which we fixed beforehand.
4. **Does practice help when something goes wrong mid-task?** We make the object slip out of the gripper, or give it a sideways shove, and compare how much success drops for an AI with a notebook against one without. The main test is in the no-catch control scenes, where both start out solving the job about equally often, so a drop cannot be hidden by a floor.

The plan is 6,696 episodes. The money is capped in code by an *estimate*: before every call the worst case is reserved, a call that would pass the cap is refused, and Anthropic stops at $90 and OpenAI at $45 (of $100 and $50). The cap counts failed retries and notebook-writing calls too. It is not an invoice audit: Anthropic's prices were checked against its own documentation, OpenAI's were not (the meter doubles them), and the morning report compares the ledger with both billing consoles.

## Where things stand

**Done**
- A simulated Franka Panda arm (MuJoCo) with inverse kinematics, collision-free planning and smooth motion.
- Eight tools (and a pose-level variant), three jobs with catches and matching controls, and a success check that only the simulator decides.
- Fairness checks on the final setup: oracle and naive gates, a dose-response chart, a settings audit and disturbance validation on fresh layouts.
- Memory conditions (none, notebook, replay), the agent loop for Anthropic and OpenAI, the spend cap, a resumable runner that refuses to continue a run whose setup changed, and the analysis code.
- Three rounds of fixes after review by two independent AI judges (a list is in [PROTOCOL.md](PROTOCOL.md) section 10).

**In progress**
- The overnight run itself, then the judges' review of the results, with a target of 9.5 out of 10 on every score.

**Not done yet**
- Every main experiment. There are no learning curves yet, and nothing here says an AI learns anything.
- Other robots. The SO-101 arm is future work.

## Run it yourself

```bash
uv sync --extra dev                      # installs MuJoCo 4.0.1, the pinned packages from uv.lock and pytest
bash scripts/fetch_models.sh             # downloads the Franka Panda model at the pinned revision
.venv/bin/python -m pytest -q            # the automated tests (no network, no money)
.venv/bin/python scripts/play.py start stack 11
.venv/bin/python scripts/play.py call pick '{"object": "cube_green"}'
.venv/bin/python scripts/gate.py --seeds 100     # the fairness checks (about 6 minutes)
.venv/bin/python scripts/audit_settings.py       # the settings audit
# with ANTHROPIC_API_KEY / OPENAI_API_KEY set (this spends money, behind the spend cap):
.venv/bin/python scripts/smoke.py --model claude-haiku-5-5 --task stack
.venv/bin/python scripts/run_experiment.py --cell main --models claude-haiku-5-5 gpt-6-luna --seeds 0-9 --out runs/main
.venv/bin/python scripts/analyze.py      # writes results/RESULTS.md and the learning-curve charts
```

`play.py` lets you play a job yourself through the exact tools an AI gets. Try the default `pick` on the green cube first.

## What is already known in this area

Several papers study parts of this, and the closest ones are listed in [PROTOCOL.md](PROTOCOL.md) section 9: RoboARCade (in-context improvement from one example demo, and false success claims), PhysMem (an AI building and testing guesses about physics while it works) and PhysCaP (an AI exploring to find hidden masses). We do not claim any one of those ideas as new. What we are testing is the combination: the same jobs through skill-level and pose-level tools, catches proved by validation, learning curves on layouts the AI has never seen, recovery from mid-task problems, and a cost comparison against bigger models with a margin we fixed beforehand.

## Folder map

- `robot_play/` the code: `world.py` (the physics scene), `motion.py` (inverse kinematics and planning), `skills.py` (the tools), `env.py` (the three jobs), `tools.py` (what the AI sees), `disturb.py`, `scripted.py` (the validation scripts), `llm.py` (Anthropic and OpenAI), `agent.py` (the loop and the memory), `runner.py` (resumable runs), `spend.py` (the spend cap), `analysis.py` (the statistics), `render.py` (videos).
- `scripts/` things you run: `gate.py`, `gate_pose.py`, `gate_disturbance.py`, `audit_settings.py`, `play.py`, `smoke.py`, `pilot_table.py`, `run_experiment.py`, `run_night.sh` (the whole overnight matrix, safe to run again), `analyze.py`, `make_videos.py`, `make_charts.py`.
- `tests/` the automated tests.
- `docs/` plain-language explanations, hand-played transcripts and charts.
- `results/` the raw numbers behind every table and chart.
- `council/` the judges' rubric and their reviews.

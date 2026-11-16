# robot-play

**Can an AI that only gives orders to a robot arm get better at a job just by practising it?**

Picture a new worker in a workshop. On day one they do not know that one drill sticks, or that one shelf is too tall to reach with the short ladder. They find out by trying, they make a note, and by day ten they are faster and make fewer mistakes. Nobody retrained them. They just remembered.

This project asks whether a language model can do the same thing with a simulated robot arm. The model never touches the arm's motors. It only calls simple tools such as `pick` and `place`. Behind those tools, ordinary robotics code (inverse kinematics and collision-free motion planning) does the careful movement. We hide a small physical "catch" in each job and watch whether the model finds it, writes it down, and uses it next time.

> **Status, 16 Nov 2026 (night 1):** the simulated world, the tools, three jobs and the checks that prove the jobs are fair are done and tested. **No AI model has been run on them yet, so there are no learning results to show.** The plan for the experiments is written down before running them in [PROTOCOL.md](PROTOCOL.md).

## The three jobs

Each job has one hidden catch. The catch is physical (weight, wall height, shape), so the model cannot get around it by being clever with words. It has to notice what the simulator reports and change how it acts.

| Job | The catch (the model is **not** told) | What a failure looks like | What fixes it |
|---|---|---|---|
| **Stack** three cubes into a tower | The green cube is heavy (250 g against 50 g for the others). A normal squeeze cannot hold it. | The fingers close to 1.9 cm and the cube is left on the table. | A firmer grip. |
| **Sort** four cubes into a red bin and a blue bin | The bin walls are 12 cm tall, higher than the hand can reach over when it lowers the cube. | `arm/hand would touch bin_red_wall2` | Letting go from higher up. |
| **Stand** two flasks upright on rings | Each flask has a wide base (10 cm) that the fully open hand (8 cm) cannot get around. | `hand stopped 1.4 cm short of the requested grasp point` | Grabbing the narrow neck near the top. |

Every job also has a **control** version with no catch, so that any improvement we later see can be traced to the catch and not to the model simply warming up.

These clips are me playing each job by hand, using only the tools and the numbers an AI would get (the full transcripts are in [docs/TASKS.md](docs/TASKS.md)). I failed the first attempt in each one, read the measurements, and fixed it.

| Stack | Sort | Stand up |
|---|---|---|
| ![stack](media/stack-hand-play.gif) | ![bins](media/bins-hand-play.gif) | ![flasks](media/flasks-hand-play.gif) |
| [full video](media/stack_seed11-v2.mp4) | [full video](media/bins_seed5-v2.mp4) | [full video](media/flasks_seed7-v2.mp4) |

## How an AI drives the arm

The model gets eight tools. None of their descriptions mentions a catch, and every result is a measurement, never an explanation.

- **`observe`** shows where every object and zone is.
- **`pick`** moves above an object, goes down, squeezes, and lifts. You can choose where on the object to grab (`grasp_height`), how hard to squeeze (`grip_level`), how fast to move (`speed`), and some settings that do nothing useful in these jobs (`yaw_offset_deg`, `lift_height`, and `settle_time` on `place`). Those are decoys, so the model has to work out which settings matter.
- **`place`** carries the held object to a target, lowers it, lets go, and backs off. You can choose how high above the surface to let go (`release_height`).
- **`move_to`**, **`open_gripper`**, **`close_gripper`**, **`home`** are the basic moves.
- **`done`** ends the episode. The simulator then decides whether the job was really finished. The model's own claim is recorded separately so we can count how often it says "done" when it is not.

The model has a small budget of tool calls per episode, so wasting calls on discovering a catch costs it.

## How we know the jobs are fair

A badly made job would give meaningless results, so before any AI is allowed near them they have to pass four checks, run on 100 random layouts each (`python scripts/gate.py`).

| Job | Scene | A script using default settings | A script that knows the catch |
|---|---|---|---|
| Stack | with the catch | 0 / 100 | 100 / 100 |
| Stack | control | 100 / 100 | 100 / 100 |
| Sort | with the catch | 0 / 100 | 100 / 100 |
| Sort | control | 99 / 100 | 100 / 100 |
| Stand up | with the catch | 0 / 100 | 100 / 100 |
| Stand up | control | 100 / 100 | 100 / 100 |

In plain words: the catch really does stop a naive attempt, a script that knows the answer always succeeds, and with the catch removed the naive attempt works. No run crashed.

The chart below shows the catch switching on as it gets stronger. For example, a green cube of 150 g is still fine with default settings, and at 250 g it never works.

![dose response](docs/img/dose_response.png)

## What we plan to measure

All of this is fixed in advance in [PROTOCOL.md](PROTOCOL.md), including what result would count as the idea being wrong.

1. **Does practice raise the success rate?** Compare an AI that keeps notes between episodes with one that starts fresh every time, on layouts it has never seen.
2. **Does practice make it faster and cheaper?** Count tool calls, simulated seconds and dollars per successful episode.
3. **Can a cheap model with practice come close to an expensive model's first try?** The cheap models are Claude Haiku 5.5 and GPT-6 Luna. The expensive ones are Claude Fable 5.2 and GPT-6 Astra.
4. **Does practice help when something goes wrong mid-task?** We make the object slip out of the gripper, or give it a sideways shove, and check how often the AI recovers.

The money is capped in code: Anthropic stops at $90 and OpenAI at $45, and a call that could push past the cap is refused before it is made.

## Where things stand

**Done**
- A simulated Franka Panda arm (MuJoCo) with inverse kinematics, collision-free planning and smooth motion.
- Eight tools, three jobs with hidden catches and matching controls, and a success check that only the simulator decides.
- Validation on 100 layouts per cell, with a chart of how strong each catch is.
- All three jobs solved by hand through the same tool interface an AI uses.
- A recorder that turns any episode into a captioned video.

**In progress**
- Physical disturbances (a slip and a shove) are written and still need their own validation.
- Reviews of the plan and code by two independent AI judges, with a target of 9.5 out of 10 on every score.

**Not done yet**
- The AI loop for Anthropic and OpenAI models, the spend meter that enforces the budget, and the memory conditions.
- Every experiment. There are no learning curves yet, and nothing here says an AI learns anything.
- Other robots. The SO-101 arm is future work.

## Run it yourself

```bash
uv sync                                  # installs MuJoCo 4.0.1 and the rest
bash scripts/fetch_models.sh             # downloads the Franka Panda model
.venv/bin/python scripts/play.py start stack 11
.venv/bin/python scripts/play.py call pick '{"object": "cube_green"}'
.venv/bin/python scripts/gate.py --seeds 100     # the fairness checks (about 10 minutes)
.venv/bin/python scripts/make_videos.py v1       # the captioned videos
```

`play.py` lets you play a job yourself through the exact tools an AI gets. Try the default `pick` on the green cube first.

## What is already known in this area

Several papers study parts of this, and the closest ones are listed in [PROTOCOL.md](PROTOCOL.md) section 9: RoboARCade (in-context improvement from one example demo, and false success claims), PhysMem (an AI building and testing guesses about physics while it works) and PhysCaP (an AI exploring to find hidden masses). We do not claim any one of those ideas as new. What we are testing is the combination: skill-level tools with decoy settings, catches proved by validation, learning curves on layouts the AI has never seen, recovery from mid-task problems, and a cost comparison against bigger models with a margin we fixed beforehand.

## Folder map

- `robot_play/` the code: `world.py` (the physics scene), `motion.py` (inverse kinematics and planning), `skills.py` (the tools), `env.py` (the three jobs), `tools.py` (what the AI sees), `disturb.py`, `render.py` (videos).
- `scripts/` things you run: `gate.py`, `play.py`, `make_videos.py`, `make_charts.py`.
- `docs/` plain-language explanations, hand-played transcripts and charts.
- `results/` the raw numbers behind every table and chart.
- `council/` the judges' rubric and their reviews.

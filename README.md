# robot-play

**Can an AI that only gives orders to a robot arm get better at a job just by practising it?**

![The stack job played by hand: the first pick fails, a firm grip works](media/stack-hand-play.gif)

A language model drives a simulated Franka Panda arm by calling tools such as `pick` and `place`. Each job hides one physical catch, for example a cube that is heavier than it looks. The model practises twelve times, keeps a 300-word notebook that it rewrites after each attempt, and is then tested on layouts it has not seen. Nothing is retrained.

**The full write-up is the [research report](https://tarunTomar122.github.io/robot-play/).** This page is the short version.

## What came out

- **A notebook helped where there was something to learn.** On unseen layouts Claude Haiku 5.5 went from 76% to 99% and GPT-6 Luna from 91% to 100%, with about a third fewer tool calls.
- **Very little of the notebook was needed.** For Haiku on the stacking job, two sentences that list the adjustable settings gave 92% against 50% with no memory, and one practice episode gave 85%.
- **Another model's notebook works too.** Haiku and Luna solved 100% of test layouts reading notebooks written by Sonnet, with no practice of their own.
- **Error messages did most of the work on the hardest job.** When one cube needs a firm grip and another cracks under one, the models coped while the simulator explained each failure. With the message removed, their own notebooks solved 28% (Haiku) and 35% (Luna), and a deliberately wrong rule solved 0 of 40 layouts.
- **Larger models left no room.** Claude Fable 5.2 and GPT-6 Astra solved every test layout on the first try.

All numbers come from [results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
uv sync --extra dev                      # MuJoCo, pinned packages, pytest
bash scripts/fetch_models.sh             # the Franka Panda model
.venv/bin/python -m pytest -q            # tests, no network and no money
.venv/bin/python scripts/play.py start stack 11                        # play a job by hand
.venv/bin/python scripts/play.py call pick '{"object": "cube_green"}'
.venv/bin/python scripts/analyze.py      # rebuild results/RESULTS.md from the run files
```

Running models needs `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` and spends money, behind a spend cap:

```bash
.venv/bin/python scripts/smoke.py --model claude-haiku-5-5 --task stack
.venv/bin/python scripts/run_experiment.py --cell main --models claude-haiku-5-5 gpt-6-luna --seeds 0-9 --out runs/main
```

## Where things are

| | |
|---|---|
| [Research report](https://tarunTomar122.github.io/robot-play/) | The study, written to be read. |
| [results/RESULTS.md](results/RESULTS.md) | Every table, generated from the raw run files. |
| [PROTOCOL.md](PROTOCOL.md) | The plan, each prediction and its outcome, and related work (section 9). |
| [results/deviations.md](results/deviations.md) | Every change made after the plan was fixed. |
| [results/code_versions.md](results/code_versions.md) | Which code revision produced which numbers. |
| [data/](data/README.md) | The raw run files and how to regenerate the results from them. |
| [docs/TASKS.md](docs/TASKS.md), [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) | The jobs in detail and how the simulator and tools work. |
| [docs/other-findings.md](docs/other-findings.md) | Smaller results that the report only mentions. |
| [docs/FOLDERS.md](docs/FOLDERS.md) | Folder map. |

## Not done

- Nothing has been run on a real arm.
- The jobs are too easy for the larger models, so the comparison with them is open for harder jobs.
- Only a few models were tested, all at low reasoning effort.

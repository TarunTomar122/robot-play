# Roadmap

Think of this as a board with three columns. Each card says what the thing is and why it matters.

## Done

| Card | What it is | Why it matters |
|---|---|---|
| **The simulated arm** | A Franka Panda arm in the MuJoCo physics engine that moves smoothly and avoids collisions. | The AI never touches motors, so the arm has to be trustworthy. |
| **Three jobs with a hidden catch** | Stack three cubes, sort four cubes into bins, stand two flasks up. Each has one physical catch. | A catch is something an AI can only find by trying, which is what practice is for. |
| **Fairness checks** | A script that knows the answer always wins, one that does not always loses, and the catch grows gradually. | Without these, a good or bad result could just be a broken job. |
| **Settings audit** | Changing one setting at a time to see which ones really matter. | Tells us exactly which fixes exist, so nobody can claim a setting is meaningless when it is not. |
| **Disturbances** | A slip (the gripper lets go mid-lift) and a shove (a sideways push). Checked on layouts we did not tune on. | Lets us ask whether practice helps when something goes wrong. |
| **The AI loop and the memory** | Works with Anthropic and OpenAI models. Three conditions: starts fresh, keeps a notebook, sees its last success. | The thing we are actually comparing. |
| **The spend cap** | Refuses any call that could push the bill past $90 (Anthropic) or $45 (OpenAI). | The experiment cannot overspend, even with many runs at once. |
| **Plan written first** | PROTOCOL.md says what we measure and what result would count against each claim, before the runs. | So we cannot move the goalposts afterwards. |

## In progress

| Card | What it is | Why it matters |
|---|---|---|

## To do

| Card | What it is | Why it matters |
|---|---|---|
| **Main experiment** | About 3,400 episodes with the two small models: starts fresh, notebook, last success, plus the disturbed runs. | Answers whether practice raises success and cuts calls, time and cost. |
| **No-catch control** | The same runs in scenes where the catch is removed. | Shows the gain comes from the catch and not from warming up. |
| **Big models** | Claude Fable 5.2 and GPT-6 Astra on their first try, and Fable with a notebook. | Answers whether a cheap model with practice can come close to an expensive one. |
| **Skill tools against pose tools** | The same jobs without `pick` and `place`, so the AI builds them from moves. | Tells us whether good building blocks make learning easier. |
| **Charts and a results page** | Learning curves, a results table with intervals, a plain-language summary. | So a stranger can read the outcome in two minutes. |
| **Other robots** | The SO-101 arm. | The idea should not depend on one arm. |

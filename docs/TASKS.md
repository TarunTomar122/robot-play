# The three jobs, and how I played them by hand

Before spending any money on AI models, I played every job myself through `scripts/play.py`. That script shows exactly what an AI would see: the task text, the tool results, and nothing else. If I could not solve a job from those numbers, an AI could not either, and the job would have to be fixed first. All three were solvable, and each needed one failed attempt to find the catch.

## 1. Stack the cubes

**The goal.** Put the green cube on the red one, then the blue cube on the green one. Success means the three cubes sit in a straight tower, within 12 mm of one axis, and stay there for one second.

**The hidden catch.** The green cube weighs 250 g. The other two weigh 50 g. The fingers have three squeeze levels (`light`, `normal`, `firm`). `normal` is not strong enough for 250 g.

**What I did** (seed 11, 8 tool calls, 1 wasted):

1. `observe` showed three 4 cm cubes. Nothing about weight.
2. `pick(cube_green)` returned `ok: false`, `object_rise_m: 0`, `gripper_width_m: 0.019`. The fingers had closed past the cube's 4 cm width, so the cube was no longer between them.
3. My reasoning: the cube slipped out, so squeeze harder. `pick(cube_green, grip_level=firm)` returned `ok: true`.
4. `place(cube_red)`, then `pick(cube_blue)` and `place(cube_green)` worked with default settings, because the blue cube is light. `done()`. The simulator said the tower was correct.

[Video](../media/stack_seed11-v2.mp4)

## 2. Sort the cubes into bins

**The goal.** Both red cubes go into the red bin and both blue cubes into the blue bin, resting inside.

**The hidden catch.** The bin walls are 12 cm tall. The hand is wide, so it cannot lower a cube inside a bin that deep without the hand hitting the rim. The cube has to be let go from higher up.

**What I did** (seed 5, 11 tool calls, 1 wasted):

1. `observe` listed the bins with an outer height of 0.13 m (that is the wall height, visible but not explained).
2. `pick(cube_red1)` worked.
3. `place(bin_red)` returned `error: straight move: arm/hand would touch bin_red_wall2`. The hand was blocked by the wall, and the cube was still held.
4. My reasoning: the wall is in the way, so let go from higher. `place(bin_red, release_height=0.12)` worked, and I used 0.12 for the other three cubes.

[Video](../media/bins_seed5-v2.mp4)

## 3. Stand the flasks on their rings

**The goal.** Each flask must end up upright (under 10 degrees of tilt), within 3 cm of the centre of its ring, standing on the floor.

**The hidden catch.** A flask is a wide base (10 cm across, 7 cm tall) with a narrow neck (4 cm across) on top. The hand opens only 8 cm, so grabbing halfway up is impossible: the fingers land on the base. The neck is the only place to grab.

**What I did** (seed 7, 7 tool calls, 1 wasted):

1. `observe` showed each flask as 10 cm wide (the widest part).
2. `pick(flask_a)` returned `error: hand stopped 1.4 cm short of the requested grasp point`. The fingers had landed on top of something.
3. My reasoning: the object is wider than the hand opens, so grab it higher. `pick(flask_a, grasp_height=0.9)` worked, and the result showed the fingers at 3.9 cm, narrower than the 10 cm the flask had looked like. That is the clue that the top is thinner than the bottom.
4. `place(ring_a)`, `pick(flask_b, grasp_height=0.9)`, `place(ring_b)`, `done()`.

[Video](../media/flasks_seed7-v2.mp4)

## What this tells us about the study

All three catches can be found inside a single episode after one failure, so an AI with no memory is not doomed. It just pays for the discovery in tool calls, simulated time and money every episode. That means the first thing practice should improve is cost and speed, and the success rate only if the call budget is tight enough that the discovery cannot fit. We will measure both. The no-memory pilot showed that most model and job pairs already succeed without memory, but we did **not** tighten the call budget: it stays at 20 calls, fixed before the pilot, and where success has no room to rise the effect can only show up as fewer calls, less time and less money.

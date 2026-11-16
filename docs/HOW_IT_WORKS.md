# How the pieces work, in plain words

## The big picture

There are three layers, like a boss, an assistant and a pair of hands.

- **The AI (the boss)** decides what to do next, one tool call at a time: "pick the green cube", "place it on the red one".
- **The skills (the assistant)** turn each order into careful movements. This is ordinary robotics code, not AI.
- **The simulator (the hands and the world)** is MuJoCo, a physics engine. It moves the arm, drops things under gravity, and decides if the job worked.

## What the skills do

**Inverse kinematics.** To put your fingertip at a spot on the table, your shoulder, elbow and wrist each have to bend by exactly the right amount. Working out those bends from the spot is called inverse kinematics. Our version starts from the current pose and nudges the seven joints a little at a time until the fingertip lands within half a millimetre, with the hand pointing straight down.

**Collision-free planning.** Before the arm moves, we test the planned path against everything in the scene by asking the physics engine whether any part of the arm would touch anything it should not. If a straight path would hit something, a random search (RRT-Connect) looks for a way around. When no safe path exists, the tool returns the plain reason, for example `arm/hand would touch bin_red_wall2`.

**Smooth motion.** The arm follows its path with one smooth speed-up and slow-down over the whole move. `slow`, `normal` and `fast` set the average joint speed (0.6, 1.2 and 2.4 radians per second). Starting and stopping at every waypoint, which our first version did, shakes heavy objects loose.

**Measuring, not explaining.** After each tool call the result lists only what the simulator measured: how far the object rose, how wide the fingers ended up, how much the object tilts, where it came to rest. It never says why something failed. Working out the "why" is the AI's job, and it is what we are measuring.

## Why the catches are physical

A catch must be something the AI cannot talk its way past. So each one is a real property of the simulated world: a mass, the height of a wall, the width of a base. They stay the same in every episode, while the positions of the objects change each time. The same collision rules apply in the catch scene and the control scene, so the skills never quietly work around a catch for the AI.

## Things we had to fix to make the simulation honest

Getting an arm to hold things in a simulator has traps. These are the ones we hit, because they are the kind that can quietly corrupt results.

- **The gripper was far too weak.** The stock model squeezes with about 2 N and a "light" setting that squeezed with nothing. We scaled it up 5 times so that light, normal and firm are three really different forces.
- **Held objects slowly slid out.** MuJoCo's default friction is slightly soft, so a held cube crept down at 3 mm per second even when the arm was standing still. Switching to an elliptic friction cone with a high `impratio` made the creep 0.15 mm per second.
- **Held cubes pivoted like pendulums.** The finger pads had almost no resistance to twisting, so a cube swung about 10 degrees while the arm moved and landed crooked. Giving the pads a realistic patch of twisting friction fixed it, and stacking error dropped from about 5 mm to under 1 mm.
- **Stop-and-go motion** shook things loose and was replaced by one smooth profile per move.
- **Placing slightly off-target.** The object sits a few millimetres off-centre in the grip. `place` now looks at where the object actually is and nudges it into position just before letting go.

## How a job is judged

When the AI calls `done()` or runs out of tool calls, the simulator waits one second for everything to settle and then checks the job's rule on the real object positions (for example "the green cube is within 12 mm of the red cube's axis and exactly one cube-height above it"). The AI's own opinion never counts.

/* Short explanations for the underlined terms on docs/index.html. Plain sentences, one idea each. */
window.TERMS = {
  notebook: {
    title: "Notebook",
    text: "A text of at most 300 words that the model rewrites after each practice episode and reads at the start of every later episode. It is the only thing that changes between episodes. The model itself is never retrained."
  },
  episode: {
    title: "Episode",
    text: "One attempt at one job, starting from one layout of the objects. It ends when the model calls done or uses its 20th tool call."
  },
  toolcall: {
    title: "Tool call",
    text: "One request from the model to the simulator, such as observe or pick. The model gets 20 per episode. After the 20th the episode ends and the simulator checks the result."
  },
  practice: {
    title: "Practice episode",
    text: "A full episode played before the test. After each one the model rewrites its notebook. Practice scores are not part of the main results."
  },
  heldout: {
    title: "Held-out layouts",
    text: "Starting positions of the objects that the model never played during practice. The notebook is frozen before these episodes, so the score measures what was learned and not what was memorised."
  },
  run: {
    title: "Run",
    text: "Twelve practice episodes followed by four held-out episodes, all with one notebook. Each model and job is run ten times, and each run uses its own set of layouts, named by a run seed."
  },
  ik: {
    title: "Inverse kinematics and motion planning",
    text: "Standard robotics code. Inverse kinematics works out how to bend each joint so that the hand reaches a point. Motion planning finds a path that does not hit anything on the way."
  },
  catch: {
    title: "Catch",
    text: "The one hidden physical detail that makes the default settings fail on a job, such as a cube that is heavier than it looks. The model is never told what it is."
  },
  control: {
    title: "Control version",
    text: "The same job with the catch removed. If a notebook helps in the control version as much as in the catch version, the gain is not about the catch."
  },
  registered: {
    title: "Registered",
    text: "Planned in writing, with the analysis rules fixed, and pushed to GitHub before any run started. The plan is PROTOCOL.md in the repository."
  },
  exploratory: {
    title: "Exploratory",
    text: "An extra experiment added after earlier results were known. Each one was also written down and pushed before it ran, but it was chosen with earlier results in view, and its 95% intervals are not adjusted for how many things were tried."
  },
  interval: {
    title: "95% interval",
    text: "A range of differences that fits the data, found by resampling whole runs. If the range includes zero, the data cannot rule out that there is no difference. The registered tests use wider intervals (97.5% or 98.75%) because each makes several comparisons at once."
  },
  points: {
    title: "Percentage points",
    text: "The gap between two percentages. A move from 76% to 99% is a gain of 23 points."
  },
  fresh: {
    title: "No memory",
    text: "The model starts every episode with no notebook and no notes, so it has to find any catch again each time."
  },
  frame: {
    title: "Frame",
    text: "One sentence placed in the memory slot: \"Defaults do not suit every object or surface.\""
  },
  names: {
    title: "The four names",
    text: "A sentence that lists the four settings the model can change: grip_level, grasp_height, release_height and speed. It does not say which one fixes which job."
  },
  generic: {
    title: "Generic sentence",
    text: "The frame, then an instruction (\"When a pick or place fails or is refused, read the message and change the settings one at a time instead of repeating the same call\"), then the four names."
  },
  answerkey: {
    title: "Written procedure",
    text: "A short text written by us, not by a model, that tells the model what to try and when to switch. It is used as a best case: how well can the model do if the lesson is already written down?"
  },
  constant: {
    title: "Rule: firm for every cube",
    text: "The text \"Pick every cube with grip_level firm.\" It is right for the heavy cube and wrong for the fragile one, so it tests what happens when a remembered rule is half wrong."
  },
  squeeze: {
    title: "Squeeze-limit message",
    text: "The fragile cube cannot take more than 3.5 newtons per finger. A normal grip is about 2.6 newtons and a firm one about 4.95. In the version with an error message, a firm pick is refused and the message gives the limit."
  },
  factsonly: {
    title: "Facts only",
    text: "The model that writes the notebook is told \"You never invent facts\", so it records only what it saw."
  },
  mayguess: {
    title: "Writer may guess",
    text: "The notebook writer may also add sentences that begin with GUESS, for causes it has not tested."
  },
  room: {
    title: "Room to improve",
    text: "A model that already solves almost every episode with no memory leaves a notebook nothing to fix. Such cells cannot say whether a notebook helps."
  },
  disturbance: {
    title: "Disturbance",
    text: "Part-way through an episode the simulator slips the held object or shoves something on the table, and the model has to recover."
  },
  pose: {
    title: "Pose-level tools",
    text: "A version of the tools with no pick and no place. The model builds them itself from move_to and the gripper, with three times the call budget."
  }
};

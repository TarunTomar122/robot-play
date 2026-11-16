"""The agent-facing contract: tool schemas, one episode wrapper, and logging.

The descriptions are neutral on purpose. They say what a parameter *is*, never which value is good for which task,
and never mention a quirk. A test (tests/test_leakage.py) checks that no hidden quirk value appears in anything the agent sees.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .disturb import Disturbance
from .env import TaskEnv

TOOLS = [
    {"name": "observe", "description": "Return the current exact state: every object (name, size, position, tilt, whether held), the zones you can place on, the gripper opening, the hand position and the elapsed simulation time. Counts as one tool call.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "pick", "description": "Move above an object, descend, close the gripper on it and lift it. Returns measured facts: the gripper opening after the lift, how far the object rose, its tilt, and any error raised by planning or by the descent.",
     "input_schema": {"type": "object", "properties": {
         "object": {"type": "string", "description": "Name of the object to pick."},
         "grasp_height": {"type": "number", "description": "Fraction (0 to 1) of the object's height, measured from its base, at which the fingers close. Default 0.6."},
         "speed": {"type": "string", "enum": ["slow", "normal", "fast"], "description": "Arm speed during this call. Default normal."},
         "grip_level": {"type": "string", "enum": ["light", "normal", "firm"], "description": "How hard the fingers squeeze. Default normal."},
         "yaw_offset_deg": {"type": "number", "description": "Extra rotation of the hand about the vertical axis, in degrees. Default 0."},
         "lift_height": {"type": "number", "description": "How far to lift the object after closing, in metres (0.05 to 0.4). Default 0.15."}},
         "required": ["object"]}},
    {"name": "place", "description": "Carry the held object above a target (an object or a zone), lower it, open the gripper and retreat upwards. Returns where the object ended up and its tilt, or the planning error.",
     "input_schema": {"type": "object", "properties": {
         "target": {"type": "string", "description": "Name of an object or zone to place on."},
         "release_height": {"type": "number", "description": "Gap in metres between the bottom of the held object and the target surface at the moment the fingers open (0 to 0.3). Default 0.02."},
         "speed": {"type": "string", "enum": ["slow", "normal", "fast"], "description": "Arm speed during this call. Default normal."},
         "settle_time": {"type": "number", "description": "Seconds to wait after opening the fingers before retreating. Default 0.3."}},
         "required": ["target"]}},
    {"name": "move_to", "description": "Move the hand (fingertip centre, gripper pointing down) to a position in the world frame, in metres.",
     "input_schema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"},
         "speed": {"type": "string", "enum": ["slow", "normal", "fast"]}}, "required": ["x", "y", "z"]}},
    {"name": "open_gripper", "description": "Open the fingers. Anything held is released where it is.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "close_gripper", "description": "Close the fingers at the current hand position.", "input_schema": {"type": "object", "properties": {
        "grip_level": {"type": "string", "enum": ["light", "normal", "firm"], "description": "How hard the fingers squeeze. Default normal."}}}},
    {"name": "home", "description": "Return the arm to its home pose.", "input_schema": {"type": "object", "properties": {
        "speed": {"type": "string", "enum": ["slow", "normal", "fast"]}}}},
    {"name": "done", "description": "Declare the task finished. The episode ends and the simulator judges the result.", "input_schema": {"type": "object", "properties": {}}},
]

# The pose-level toolset has no pick or place: the model must build them from moves and the gripper. Used for the skill-level versus pose-level comparison.
POSE_TOOLS = [t for t in TOOLS if t["name"] in ("observe", "move_to", "open_gripper", "close_gripper", "home", "done")]
TOOLSETS = {"skills": TOOLS, "pose": POSE_TOOLS}
CALL_BUDGET_FACTOR = {"skills": 1, "pose": 3}      # building a pick and a place from moves takes about three times as many calls

SYSTEM_PROMPT = """You control a simulated Franka Panda arm through the tools you are given. All positions are in metres in the world frame (x forward, y left, z up, the table surface is z = 0).
Your task is described below. You have at most {max_calls} tool calls in total, and each call (including observe) counts. When you believe the task is complete, call done().
The simulator, not you, decides whether the task was completed. Tool results are measurements taken by the simulator; they do not explain causes.

TASK: {instruction}"""


@dataclass
class Episode:
    task: str
    seed: int
    quirk: bool = True
    max_calls: int | None = None
    disturbance: str | None = None
    toolset: str = "skills"
    env_kw: dict = field(default_factory=dict)          # scene overrides used only by validation sweeps (cube mass, wall height, flask base)
    env: TaskEnv = field(init=False)
    log: list = field(default_factory=list)
    calls: int = 0
    claimed_done: bool = False
    over_budget: bool = False

    def __post_init__(self):
        self.env = TaskEnv(self.task, self.seed, quirk=self.quirk, **self.env_kw)
        self.dist = Disturbance(self.disturbance, self.seed) if self.disturbance else None
        if self.dist:
            self.dist.attach(self.env)
        if self.max_calls is None:
            self.max_calls = self.env.task.max_calls * CALL_BUDGET_FACTOR[self.toolset]

    @property
    def tools(self) -> list:
        return TOOLSETS[self.toolset]

    @property
    def finished(self) -> bool:
        return self.claimed_done or self.over_budget

    @property
    def prompt(self) -> str:
        return SYSTEM_PROMPT.format(max_calls=self.max_calls, instruction=self.env.task.instruction)

    def call(self, name: str, args: dict | None = None) -> dict:
        args = dict(args or {})
        if self.finished:
            return {"error": "episode already ended"}
        self.calls += 1
        sk = self.env.skills
        try:
            if name not in {t["name"] for t in self.tools}:
                res = {"error": f"unknown tool '{name}'"}
            elif name == "observe":
                res = sk.observe()
            elif name == "pick":
                res = sk.pick(args["object"], args.get("grasp_height", 0.6), args.get("speed", "normal"), args.get("grip_level", "normal"),
                              args.get("yaw_offset_deg", 0.0), args.get("lift_height", 0.15))
            elif name == "place":
                res = sk.place(args["target"], args.get("release_height", 0.02), args.get("speed", "normal"), args.get("settle_time", 0.3))
            elif name == "move_to":
                res = sk.move_to(args["x"], args["y"], args["z"], args.get("speed", "normal"))
            elif name == "open_gripper":
                res = sk.open_gripper()
            elif name == "close_gripper":
                res = sk.close_gripper(args.get("grip_level", "normal"))
            elif name == "home":
                res = sk.home(args.get("speed", "normal"))
            elif name == "done":
                self.claimed_done = True
                res = {"ok": True, "message": "episode finished"}
            else:
                res = {"error": f"unknown tool '{name}'"}
        except KeyError as e:
            res = {"error": f"missing or unknown argument {e}"}
        except (TypeError, ValueError) as e:
            res = {"error": f"bad arguments: {e}"}
        if self.calls >= self.max_calls and not self.claimed_done:
            self.over_budget = True
            res = {**res, "note": "call budget exhausted; the episode has ended"}
        self.log.append({"i": self.calls, "tool": name, "args": args, "result": res})
        return res

    def result(self) -> dict:
        ok, detail = self.env.success()
        return {"task": self.task, "seed": self.seed, "quirk": self.quirk, "toolset": self.toolset, "success": bool(ok), "detail": detail,
                "claimed_done": self.claimed_done, "false_success_claim": bool(self.claimed_done and not ok),
                "calls": self.calls, "sim_time_s": round(self.env.sim_time, 1),
                "disturbance": self.disturbance, "disturbance_fired": bool(self.dist and self.dist.fired)}

    def to_json(self) -> str:
        return json.dumps({"result": self.result(), "log": self.log})

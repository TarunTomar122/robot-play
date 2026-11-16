"""Tasks: scene generation, hidden quirks, success predicates, and the episode wrapper.

Quirks are physical (mass, friction, torsion, wall height) and fixed per task; poses are resampled from the seed.
`quirk=False` builds the matching control scene.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .skills import Skills
from .world import ObjectSpec, PandaWorld, SceneSpec, StaticSpec

MAX_CALLS = 30


def _sample_xy(rng, n, x=(0.40, 0.58), y=(-0.26, 0.26), min_sep=0.11, avoid=()):
    pts = []
    for _ in range(2000):
        p = np.array([rng.uniform(*x), rng.uniform(*y)])
        if all(np.linalg.norm(p - q) >= min_sep for q in list(pts) + list(avoid)):
            pts.append(p)
        if len(pts) == n:
            return pts
    raise RuntimeError("could not sample poses")


@dataclass
class Task:
    name: str
    instruction: str
    build: callable                       # (rng, quirk) -> (SceneSpec, targets, meta)
    check: callable                       # (env) -> (bool, dict)


# ---------------------------------------------------------------------------------------------- stack
def _build_stack(rng, quirk: bool):
    pts = _sample_xy(rng, 3)
    heavy = dict(mass=0.9, friction=(0.45, 0.001, 0.0001)) if quirk else dict(mass=0.05, friction=(1.0, 0.01, 0.001))
    objs = [
        ObjectSpec("cube_red", "box", (.02, .02, .02), tuple(pts[0]), (.9, .15, .15, 1), mass=0.05),
        ObjectSpec("cube_green", "box", (.02, .02, .02), tuple(pts[1]), (.15, .75, .2, 1), **heavy),
        ObjectSpec("cube_blue", "box", (.02, .02, .02), tuple(pts[2]), (.15, .25, .9, 1), mass=0.05),
    ]
    return SceneSpec(objects=objs), {}, {}


def _check_stack(env):
    w = env.w
    env.world_settle(1.0)
    r, g, b = (w.obj_pos(n) for n in ("cube_red", "cube_green", "cube_blue"))
    ok_g = np.linalg.norm(g[:2] - r[:2]) < 0.012 and abs(g[2] - (r[2] + 0.04)) < 0.008
    ok_b = np.linalg.norm(b[:2] - r[:2]) < 0.012 and abs(b[2] - (r[2] + 0.08)) < 0.008
    tilts = max(w.obj_tilt_deg(n) for n in ("cube_red", "cube_green", "cube_blue"))
    ok = bool(ok_g and ok_b and tilts < 15)
    return ok, {"green_on_red": bool(ok_g), "blue_on_green": bool(ok_b), "max_tilt_deg": round(tilts, 1)}


# ---------------------------------------------------------------------------------------------- bins
BIN_INNER = 0.10
WALL_T = 0.01


def _bin_statics(name, cx, cy, rgba, wall_h):
    hi = BIN_INNER / 2
    out = [StaticSpec(name, "box", (hi + WALL_T, hi + WALL_T, 0.005), (cx, cy, 0.005), rgba)]
    for i, (dx, dy, sx, sy) in enumerate([(hi + WALL_T / 2, 0, WALL_T / 2, hi + WALL_T), (-(hi + WALL_T / 2), 0, WALL_T / 2, hi + WALL_T),
                                           (0, hi + WALL_T / 2, hi, WALL_T / 2), (0, -(hi + WALL_T / 2), hi, WALL_T / 2)]):
        out.append(StaticSpec(f"{name}_wall{i + 1}", "box", (sx, sy, wall_h / 2), (cx + dx, cy + dy, 0.01 + wall_h / 2), rgba))
    return out


def _build_bins(rng, quirk: bool, wall_h: float | None = None):
    wall_h = wall_h if wall_h is not None else (0.12 if quirk else 0.015)
    bin_xy = _sample_xy(rng, 2, x=(0.42, 0.50), y=(-0.30, 0.30), min_sep=0.34)
    cubes = _sample_xy(rng, 4, x=(0.36, 0.60), y=(-0.30, 0.30), min_sep=0.09, avoid=bin_xy)
    cubes = [c for c in cubes]
    objs = []
    for i, (name, rgba) in enumerate([("cube_red1", (.9, .15, .15, 1)), ("cube_blue1", (.15, .25, .9, 1)),
                                      ("cube_red2", (.9, .15, .15, 1)), ("cube_blue2", (.15, .25, .9, 1))]):
        objs.append(ObjectSpec(name, "box", (.0175, .0175, .0175), tuple(cubes[i]), rgba, mass=0.05))
    statics = _bin_statics("bin_red", *bin_xy[0], (.75, .25, .25, 1), wall_h) + _bin_statics("bin_blue", *bin_xy[1], (.25, .35, .8, 1), wall_h)
    full = BIN_INNER + 2 * WALL_T
    targets = {"bin_red": {"xy": bin_xy[0], "top_z": 0.01, "size": (full, full, 0.01 + wall_h),
                           "ignore": ["bin_red", "bin_red_wall1", "bin_red_wall2", "bin_red_wall3", "bin_red_wall4"]},
               "bin_blue": {"xy": bin_xy[1], "top_z": 0.01, "size": (full, full, 0.01 + wall_h),
                            "ignore": ["bin_blue", "bin_blue_wall1", "bin_blue_wall2", "bin_blue_wall3", "bin_blue_wall4"]}}
    return SceneSpec(objects=objs, statics=statics), targets, {"bin_xy": {"bin_red": bin_xy[0], "bin_blue": bin_xy[1]}, "wall_h": wall_h}


def _check_bins(env):
    w = env.w
    env.world_settle(1.0)
    inside = {}
    for n in ("cube_red1", "cube_red2", "cube_blue1", "cube_blue2"):
        want = "bin_red" if "red" in n else "bin_blue"
        c = np.array(env.meta["bin_xy"][want])
        p = w.obj_pos(n)
        inside[n] = bool(np.all(np.abs(p[:2] - c) < BIN_INNER / 2 - 0.005) and 0.01 < p[2] < 0.05)
    return all(inside.values()), inside


# ---------------------------------------------------------------------------------------------- bottle
def _build_bottle(rng, quirk: bool):
    pts = _sample_xy(rng, 4, x=(0.40, 0.56), y=(-0.28, 0.28), min_sep=0.13)
    spec = dict(mass=0.6, friction=(0.9, 0.0002, 0.0001), com_z=0.035) if quirk else dict(mass=0.6, friction=(1.0, 0.01, 0.001), com_z=0.09)
    objs = [ObjectSpec("bottle_a", "cylinder", (0.025, 0.09, 0), tuple(pts[0]), (.2, .65, .9, 1), **spec),
            ObjectSpec("bottle_b", "cylinder", (0.025, 0.09, 0), tuple(pts[1]), (.9, .6, .2, 1), **spec)]
    statics = [StaticSpec("ring_a", "box", (0.045, 0.045, 0.0005), (*pts[2], 0.0005), (.2, .65, .9, 1), collide=False),
               StaticSpec("ring_b", "box", (0.045, 0.045, 0.0005), (*pts[3], 0.0005), (.9, .6, .2, 1), collide=False)]
    targets = {"ring_a": {"xy": pts[2], "top_z": 0.0, "size": (0.09, 0.09, 0.001), "ignore": ["ring_a", "floor"]},
               "ring_b": {"xy": pts[3], "top_z": 0.0, "size": (0.09, 0.09, 0.001), "ignore": ["ring_b", "floor"]}}
    return SceneSpec(objects=objs, statics=statics), targets, {"ring": {"bottle_a": pts[2], "bottle_b": pts[3]}}


def _check_bottle(env):
    w = env.w
    env.world_settle(1.0)
    res = {}
    for n in ("bottle_a", "bottle_b"):
        p = w.obj_pos(n)
        c = np.array(env.meta["ring"][n])
        res[n] = bool(np.linalg.norm(p[:2] - c) < 0.03 and w.obj_tilt_deg(n) < 10 and abs(p[2] - 0.09) < 0.01)
    return all(res.values()), res


TASKS = {
    "stack": Task("stack", "Stack the three cubes into one tower. cube_red is the bottom and stays where it is, cube_green goes on top of it, "
                  "then cube_blue on top of cube_green. Call done() when the tower is finished.", _build_stack, _check_stack),
    "bins": Task("bins", "Sort the cubes: put both red cubes (cube_red1, cube_red2) into bin_red and both blue cubes (cube_blue1, cube_blue2) "
                 "into bin_blue, resting inside the bin. Call done() when finished.", _build_bins, _check_bins),
    "bottle": Task("bottle", "Move bottle_a upright onto ring_a and bottle_b upright onto ring_b, centred in each ring and standing on the floor. "
                   "Call done() when finished.", _build_bottle, _check_bottle),
}


class TaskEnv:
    def __init__(self, task: str, seed: int, quirk: bool = True, **kw):
        self.task = TASKS[task]
        self.seed = seed
        self.quirk = quirk
        rng = np.random.default_rng(seed)
        scene, targets, self.meta = (self.task.build(rng, quirk, **kw) if kw else self.task.build(rng, quirk))
        self.w = PandaWorld(scene)
        self.skills = Skills(self.w, targets)
        self.calls = 0
        self.log: list[dict] = []

    def world_settle(self, s: float):
        self.w.settle(s)

    def success(self):
        return self.task.check(self)

    @property
    def sim_time(self) -> float:
        return self.w.time - self.skills.sim_time0

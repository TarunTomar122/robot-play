"""Scripted policies used to validate the environments: a naive one (default parameters) and an oracle (knows the quirk)."""
from __future__ import annotations

from .disturb import Disturbance
from .env import TaskEnv

ORDER = {"stack": ["cube_green", "cube_blue"], "bins": ["cube_red1", "cube_blue1", "cube_red2", "cube_blue2"], "flasks": ["flask_a", "flask_b"]}


def _dest(task, obj, env):
    if task == "stack":
        return "cube_red" if obj == "cube_green" else "cube_green"
    if task == "bins":
        return "bin_red" if "red" in obj else "bin_blue"
    return "ring_a" if obj == "flask_a" else "ring_b"


def run_script(task: str, seed: int, quirk: bool, policy: str, disturbance: str | None = None, **kw) -> dict:
    """policy: naive (defaults), oracle (knows the quirk), oracle_retry (oracle that re-picks after a failed pick/place)."""
    env = TaskEnv(task, seed, quirk=quirk, **kw)
    s = env.skills
    dist = Disturbance(disturbance, seed) if disturbance else None
    if dist:
        dist.attach(env)
    retries = 3 if policy == "oracle_retry" else 1
    if policy == "oracle_retry":
        policy = "oracle"
    pick_kw, place_kw = {}, {}
    if policy == "oracle":
        if task == "stack":
            pick_kw = {"grip_level": "firm", "speed": "slow"}
            place_kw = {"speed": "slow"}
        elif task == "bins":
            place_kw = {"release_height": 0.14}
        elif task == "flasks":
            pick_kw = {"grasp_height": 0.9}
    trace = []
    for obj in ORDER[task]:
        for _ in range(retries):
            if s.mv.held and s.mv.held != obj:
                s.open_gripper()
            if s.mv.held != obj:
                r = s.pick(obj, **pick_kw)
                trace.append(("pick", obj, r.get("ok"), r.get("error")))
                if not r["ok"]:
                    continue
            r = s.place(_dest(task, obj, env), **place_kw)
            trace.append(("place", obj, r.get("ok"), r.get("error")))
            if r["ok"]:
                break
    s.home()
    ok, detail = env.success()
    return {"ok": bool(ok), "detail": detail, "trace": trace, "sim_time": env.sim_time, "fired": bool(dist and dist.fired)}

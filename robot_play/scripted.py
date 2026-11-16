"""Scripted policies used to validate the environments: a naive one (default parameters) and an oracle (knows the catch).

They play through `Episode`, the very same wrapper a language model uses, so they obey the same call budget, the same defaults and the same
`done` rule. A gate that passes here says the task can be solved, and fails to be solved by defaults, *as the model experiences it*.
"""
from __future__ import annotations

from .tools import Episode

ORDER = {"stack": ["cube_green", "cube_blue"], "bins": ["cube_red1", "cube_blue1", "cube_red2", "cube_blue2"], "flasks": ["flask_a", "flask_b"]}
ORACLE = {"stack": ({"grip_level": "firm", "speed": "slow"}, {"speed": "slow"}), "bins": ({}, {"release_height": 0.14}), "flasks": ({"grasp_height": 0.9}, {})}


def _dest(task, obj):
    if task == "stack":
        return "cube_red" if obj == "cube_green" else "cube_green"
    if task == "bins":
        return "bin_red" if "red" in obj else "bin_blue"
    return "ring_a" if obj == "flask_a" else "ring_b"


def run_script(task: str, seed: int, quirk: bool, policy: str, disturbance: str | None = None, pick_kw: dict | None = None,
               place_kw: dict | None = None, max_calls: int | None = None, **env_kw) -> dict:
    """policy: naive (defaults), oracle (knows the catch), oracle_retry (oracle that re-picks after a failed pick/place).
    `pick_kw` / `place_kw` are extra tool arguments (used for single-setting audits); they override the oracle's."""
    ep = Episode(task, seed, quirk=quirk, max_calls=max_calls, disturbance=disturbance, env_kw=env_kw)
    mv = ep.env.skills.mv
    retries = 3 if policy == "oracle_retry" else 1
    pk, plk = {}, {}
    if policy in ("oracle", "oracle_retry"):
        pk, plk = (dict(x) for x in ORACLE[task])
    pk.update(pick_kw or {})
    plk.update(place_kw or {})
    trace = []
    for obj in ORDER[task]:
        for _ in range(retries):
            if ep.finished:
                break
            if mv.held and mv.held != obj:
                ep.call("open_gripper")
            if mv.held != obj:
                r = ep.call("pick", {"object": obj, **pk})
                trace.append(("pick", obj, r.get("ok"), r.get("error")))
                if not r.get("ok"):
                    continue
            r = ep.call("place", {"target": _dest(task, obj), **plk})
            trace.append(("place", obj, r.get("ok"), r.get("error")))
            if r.get("ok"):
                break
    if not ep.finished:
        ep.call("home")
    if not ep.finished:
        ep.call("home")
    if not ep.finished:
        ep.call("done")
    res = ep.result()
    return {"ok": bool(res["success"]), "detail": res["detail"], "trace": trace, "sim_time": res["sim_time_s"], "fired": res["disturbance_fired"],
            "calls": res["calls"], "over_budget": ep.over_budget}


NAIVE_FLASK_GRASP = 0.7       # control scenes work from about 0.65 up, catch scenes from about 0.8 up (results/gate_pose.md)


def run_pose_script(task: str, seed: int, quirk: bool, policy: str, max_calls: int | None = None, disturbance: str | None = None) -> dict:
    """The pose-level counterpart of `run_script`: builds pick and place out of `move_to`, `close_gripper` and `open_gripper` through the same
    `Episode` wrapper with the pose toolset and its larger call budget. policy: naive (default grip, release 2 cm above the target, grasp at 60% of
    the object height) or oracle (knows the catch). It reads zone heights from the simulator, which a model gets from `observe`, to aim the release."""
    ep = Episode(task, seed, quirk=quirk, max_calls=max_calls, disturbance=disturbance, toolset="pose")
    sk = ep.env.skills
    oracle = policy == "oracle"
    grip = "firm" if oracle and task == "stack" else "normal"
    release = 0.14 if oracle and task == "bins" else 0.02
    gh = 0.9 if oracle and task == "flasks" else NAIVE_FLASK_GRASP if task == "flasks" else 0.6       # at pose level the planner will not put the palm on a flask top, so the naive grasp is 0.8, not 0.6
    safe = 0.40
    trace = []
    def go(name, args, obj):
        if name == "move_to" and sk.mv.held:
            args = {**args, "speed": "slow"}       # both scripts carry at slow speed: a swinging load can slip, which is not the catch under test
        r = ep.call(name, args)
        trace.append((name, obj, r.get("ok"), r.get("error")))
        return r.get("ok") is not False

    for obj in ORDER[task]:
        if ep.finished:
            break
        if sk.mv.held and sk.mv.held != obj:
            go("open_gripper", {}, obj)
        obs = ep.call("observe")
        o = next(x for x in obs["objects"] if x["name"] == obj)
        px, py, pz = o["position_m"]
        h = o["size_xyz_m"][2]
        zg = max(0.012, pz - h / 2 + gh * h)
        (tx, ty), top_z = (lambda s_: (s_[0], s_[1]))(sk._support(_dest(task, obj)))
        ok = (go("move_to", {"x": px, "y": py, "z": safe}, obj) and go("move_to", {"x": px, "y": py, "z": zg}, obj)
              and go("close_gripper", {"grip_level": grip}, obj) and go("move_to", {"x": px, "y": py, "z": safe}, obj)
              and go("move_to", {"x": tx, "y": ty, "z": safe}, obj))
        off = (0.0, 0.0)
        if ok and not ep.finished:
            obs = ep.call("observe")                                 # above the target and at rest: where is the object in the grip? aim the object, not the hand
            o = next(x for x in obs["objects"] if x["name"] == obj)
            tcp = obs["tcp_m"]
            off = (o["position_m"][0] - tcp[0], o["position_m"][1] - tcp[1])
            dz = tcp[2] - (o["position_m"][2] - h / 2)
            ok = (go("move_to", {"x": tx - off[0], "y": ty - off[1], "z": safe}, obj)
                  and go("move_to", {"x": tx - off[0], "y": ty - off[1], "z": top_z + release + dz}, obj))
        if ok and not ep.finished:                                   # a failed step is not retried; the object stays in the hand until the next pick, as in the skill-level naive script
            go("open_gripper", {}, obj)
            go("move_to", {"x": tx - off[0], "y": ty - off[1], "z": safe}, obj)
    if not ep.finished:
        ep.call("home")
    if not ep.finished:
        ep.call("done")
    res = ep.result()
    return {"ok": bool(res["success"]), "detail": res["detail"], "trace": trace, "sim_time": res["sim_time_s"], "fired": res["disturbance_fired"],
            "calls": res["calls"], "over_budget": ep.over_budget}

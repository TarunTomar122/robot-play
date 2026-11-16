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
        ep.call("done")
    res = ep.result()
    return {"ok": bool(res["success"]), "detail": res["detail"], "trace": trace, "sim_time": res["sim_time_s"], "fired": res["disturbance_fired"],
            "calls": res["calls"], "over_budget": ep.over_budget}

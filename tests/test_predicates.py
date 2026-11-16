"""Every success predicate must say yes to a real success and no to the usual near-misses."""
import numpy as np
import pytest

from robot_play.scripted import run_script
from robot_play.tools import Episode


def _verdict(task, calls, seed=3, quirk=True):
    ep = Episode(task, seed, quirk=quirk)
    for name, args in calls:
        ep.call(name, args)
    return ep.result()


@pytest.mark.parametrize("task", ["stack", "bins", "flasks"])
def test_doing_nothing_fails(task):
    assert not _verdict(task, [("done", {})])["success"]


@pytest.mark.parametrize("task", ["stack", "bins", "flasks"])
def test_oracle_succeeds(task):
    assert run_script(task, 3, True, "oracle")["ok"]


def test_stack_half_a_tower_fails():
    r = _verdict("stack", [("pick", {"object": "cube_green", "grip_level": "firm"}), ("place", {"target": "cube_red"}), ("done", {})])
    assert r["detail"]["green_on_red"] and not r["detail"]["blue_on_green"] and not r["success"]


def test_stack_cube_beside_the_base_fails():
    ep = Episode("stack", 3, quirk=False)
    red = ep.env.w.obj_pos("cube_red")
    ep.env.skills.pick("cube_green")
    ep.env.skills.move_to(red[0] + 0.07, red[1], 0.12)       # let go 7 cm to the side of the base cube
    ep.env.skills.open_gripper()
    ep.call("done", {})
    assert not ep.result()["detail"]["green_on_red"]


def test_bins_three_out_of_four_fails():
    calls = []
    for obj, bin_ in [("cube_red1", "bin_red"), ("cube_blue1", "bin_blue"), ("cube_red2", "bin_red")]:
        calls += [("pick", {"object": obj}), ("place", {"target": bin_, "release_height": 0.14})]
    r = _verdict("bins", calls + [("done", {})])
    assert sum(r["detail"].values()) == 3 and not r["success"]


def test_bins_wrong_colour_in_bin_fails():
    r = _verdict("bins", [("pick", {"object": "cube_red1"}), ("place", {"target": "bin_blue", "release_height": 0.14}), ("done", {})])
    assert not r["detail"]["cube_red1"]


def test_flask_lying_down_fails():
    ep = Episode("flasks", 3, quirk=True)
    w = ep.env.w
    ring = np.array(ep.env.meta["ring"]["flask_a"])
    adr = w.model.jnt_qposadr[w.model.body_jntadr[w.obj_ids["flask_a"]]]
    w.data.qpos[adr:adr + 7] = [ring[0], ring[1], 0.03, np.cos(np.pi / 4), np.sin(np.pi / 4), 0, 0]   # on its side, centred on the ring
    w.data.qvel[:] = 0
    ep.call("done", {})
    assert not ep.result()["detail"]["flask_a"]


def test_cube_upside_down_is_still_upright():
    ep = Episode("stack", 3, quirk=True)
    w = ep.env.w
    adr = w.model.jnt_qposadr[w.model.body_jntadr[w.obj_ids["cube_blue"]]]
    w.data.qpos[adr + 3:adr + 7] = [0, 1, 0, 0]               # turned over by 180 degrees about x
    mujoco_forward = __import__("mujoco").mj_forward
    mujoco_forward(w.model, w.data)
    assert w.obj_tilt_deg("cube_blue") < 1.0

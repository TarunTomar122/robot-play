import numpy as np

from robot_play.motion import Collision, IKFailure, ik
from robot_play.world import PandaWorld
from robot_play.env import TaskEnv


def test_ik_reaches_the_target_within_a_millimetre():
    env = TaskEnv("stack", 1, quirk=False)
    w = env.w
    for p in ([0.45, 0.0, 0.2], [0.5, -0.2, 0.05], [0.4, 0.25, 0.3]):
        q = ik(w, np.array(p), 0.0, w.q)
        d = w.scratch
        d.qpos[w.arm_qadr] = q
        import mujoco
        mujoco.mj_kinematics(w.model, d)
        assert np.linalg.norm(w.tcp(d) - p) < 1e-3


def test_ik_refuses_an_unreachable_point():
    env = TaskEnv("stack", 1, quirk=False)
    try:
        ik(env.w, np.array([1.6, 0.0, 0.1]), 0.0, env.w.q)
    except IKFailure:
        return
    raise AssertionError("expected IKFailure")


def test_planner_reports_the_wall_it_would_hit():
    env = TaskEnv("bins", 0, quirk=True)
    s = env.skills
    assert s.pick("cube_red1")["ok"]
    r = s.place("bin_red")                                       # default release height is too low for the walls
    assert not r["ok"] and "bin_red_wall" in r["error"] and r["holding"] == "cube_red1"


def test_straight_move_is_collision_checked_against_held_object_too():
    env = TaskEnv("stack", 2, quirk=False)
    s = env.skills
    s.pick("cube_green")
    red = env.w.obj_pos("cube_red")
    r = s.move_to(red[0], red[1], 0.05)                          # would drive the held cube into the red cube
    assert not r["ok"]


def test_arm_can_leave_a_bin_after_letting_go_inside_it():
    """Regression: after pick, move_to inside a tall-walled bin and open_gripper, the fingers touch the walls; every later move used to fail."""
    from robot_play.tools import Episode
    ep = Episode("bins", 60000, quirk=True)
    bx = ep.env.meta["bin_xy"]["bin_red"]
    assert ep.call("pick", {"object": "cube_red1"})["ok"]
    assert ep.call("move_to", {"x": float(bx[0]), "y": float(bx[1]), "z": 0.10})["ok"]
    ep.call("open_gripper", {})
    assert ep.env.skills.mv.colliding(ep.env.w.q)                         # the start pose really is in contact
    assert ep.call("move_to", {"x": 0.4, "y": 0.0, "z": 0.3})["ok"]
    assert ep.call("home", {})["ok"]


def test_the_escape_cannot_be_used_to_tunnel_through_a_wall():
    from robot_play.tools import Episode
    ep = Episode("bins", 60000, quirk=True)
    bx = ep.env.meta["bin_xy"]["bin_red"]
    ep.call("pick", {"object": "cube_red1"})
    ep.call("move_to", {"x": float(bx[0]), "y": float(bx[1]), "z": 0.10})
    ep.call("open_gripper", {})
    r = ep.call("move_to", {"x": float(bx[0]), "y": float(bx[1]) + 0.2, "z": 0.03})       # straight across the wall at table height
    assert not r["ok"]

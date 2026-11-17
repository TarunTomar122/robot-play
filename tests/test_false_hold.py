"""Fix for the false `holding` found by council round 5a: close_gripper must not attach an object that both fingertips only rest on (nothing between the fingers)."""
from robot_play.tools import Episode


def test_closing_the_hand_on_top_of_a_cube_does_not_claim_to_hold_it():
    ep = Episode("stack", 10302, quirk=True)           # the layout and the calls of a logged Haiku episode that got `holding: cube_green` at a finger width of 0.021 m
    for tool, args in [("observe", {}), ("pick", {"object": "cube_green"}), ("pick", {"object": "cube_green", "grasp_height": 0.5, "speed": "slow"}),
                       ("move_to", {"x": 0.579, "y": 0.039, "z": 0.2}), ("move_to", {"x": 0.579, "y": 0.039, "z": 0.03, "speed": "slow"})]:
        ep.call(tool, args)
    r = ep.call("close_gripper", {})
    assert r["ok"] and r["holding"] is None and r["gripper_width_m"] < 0.03
    assert ep.call("pick", {"object": "cube_green"}).get("error") != "already holding cube_green"


def test_a_real_hold_between_the_fingers_is_still_reported():
    ep = Episode("stack", 10_000, quirk=False, toolset="pose")
    p = ep.env.w.obj_pos("cube_green")
    assert ep.call("move_to", {"x": float(p[0]), "y": float(p[1]), "z": 0.12})["ok"]
    assert ep.call("move_to", {"x": float(p[0]), "y": float(p[1]), "z": 0.02})["ok"]
    r = ep.call("close_gripper", {"grip_level": "firm"})
    assert r["holding"] == "cube_green" and r["gripper_width_m"] > 0.035

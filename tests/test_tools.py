import json

from robot_play.tools import Episode


def test_unknown_tool_and_bad_arguments_are_reported_not_raised():
    ep = Episode("stack", 1)
    assert "error" in ep.call("fly", {})
    assert "error" in ep.call("pick", {})                       # missing object
    assert "error" in ep.call("pick", {"object": "cube_green", "speed": "warp"})
    assert ep.calls == 3                                         # bad calls still cost budget


def test_budget_ends_the_episode():
    ep = Episode("stack", 1, max_calls=3)
    for _ in range(3):
        ep.call("observe", {})
    assert ep.finished and ep.over_budget
    assert ep.call("observe", {}) == {"error": "episode already ended"}
    assert ep.calls == 3


def test_done_ends_and_false_claim_is_recorded():
    ep = Episode("stack", 1)
    ep.call("done", {})
    r = ep.result()
    assert ep.finished and r["claimed_done"] and r["false_success_claim"] and not r["success"]


def test_same_calls_give_identical_results():
    calls = [("pick", {"object": "cube_green", "grip_level": "firm"}), ("place", {"target": "cube_red"}), ("done", {})]
    out = []
    for _ in range(2):
        ep = Episode("stack", 5)
        for n, a in calls:
            ep.call(n, a)
        out.append(json.dumps(ep.log, sort_keys=True))
    assert out[0] == out[1]


def test_log_is_json_serialisable():
    ep = Episode("bins", 2)
    ep.call("observe", {})
    json.loads(ep.to_json())


def test_extra_settings_do_not_break_the_oracle():
    """Adding lift_height or a hand turn on top of the oracle's settings must not stop it from stacking (the audit in results/settings_audit.md covers single settings)."""
    for kw in ({"lift_height": 0.3}, {"yaw_offset_deg": 20.0}):
        ep = Episode("stack", 6, quirk=False)
        assert ep.call("pick", {"object": "cube_green", **kw})["ok"]


def test_pose_level_close_gripper_attaches_what_is_between_the_fingers_and_a_pose_script_can_carry_it():
    from robot_play.scripted import run_pose_script
    ep = Episode("stack", 3, quirk=True, toolset="pose")
    ep.call("move_to", {"x": 0.45, "y": 0.0, "z": 0.4})
    assert ep.call("close_gripper", {})["holding"] is None            # closing on nothing attaches nothing
    ep.call("open_gripper")
    o = [x for x in ep.call("observe")["objects"] if x["name"] == "cube_green"][0]
    x, y, z = o["position_m"]
    ep.call("move_to", {"x": x, "y": y, "z": 0.4})
    ep.call("move_to", {"x": x, "y": y, "z": 0.024})
    assert ep.call("close_gripper", {"grip_level": "firm"})["holding"] == "cube_green"
    assert ep.call("move_to", {"x": x, "y": y, "z": 0.3, "speed": "slow"})["ok"]          # carrying the cube straight up works: it is not an obstacle to its own hand
    assert run_pose_script("stack", 3, True, "oracle")["ok"] and not run_pose_script("stack", 3, True, "naive")["ok"]


def test_a_lost_object_is_no_longer_reported_as_held():
    ep = Episode("stack", 3, quirk=True, toolset="pose")
    o = [x for x in ep.call("observe")["objects"] if x["name"] == "cube_green"][0]
    x, y, z = o["position_m"]
    ep.call("move_to", {"x": x, "y": y, "z": 0.4})
    ep.call("move_to", {"x": x, "y": y, "z": 0.024})
    ep.call("close_gripper", {})                                           # the default squeeze cannot hold the heavy cube: it slips out on the way up
    ep.call("move_to", {"x": x, "y": y, "z": 0.3, "speed": "slow"})
    obs = ep.call("observe")
    green = [o for o in obs["objects"] if o["name"] == "cube_green"][0]
    assert green["position_m"][2] < 0.05 and green["held"] is False and obs["gripper"]["holding"] is None      # it lies on the table, and the tools say so
    assert ep.call("close_gripper", {})["holding"] is None

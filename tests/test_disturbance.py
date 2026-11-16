from robot_play.tools import Episode


def test_slip_fires_once_and_drops_the_object():
    ep = Episode("stack", 3, quirk=False, disturbance="slip")
    r = ep.call("pick", {"object": "cube_green"})
    assert ep.dist.fired and not r["ok"] and r["holding"] is None
    t = ep.dist.fired_at
    ep.call("pick", {"object": "cube_green"})
    assert ep.dist.fired_at == t                                  # only once per episode


def test_nudge_moves_an_object_that_was_not_yet_grasped():
    ep = Episode("stack", 3, quirk=False, disturbance="nudge")
    before = ep.env.w.obj_pos("cube_green").copy()
    ep.call("pick", {"object": "cube_green"})
    assert ep.dist.fired
    after = ep.env.w.obj_pos("cube_green")
    assert ((after - before)[:2] ** 2).sum() ** 0.5 > 0.02 or ep.env.skills.mv.held


def test_no_force_is_left_applied_after_a_nudge():
    ep = Episode("stack", 3, quirk=False, disturbance="nudge")
    ep.call("pick", {"object": "cube_green"})
    ep.env.w.settle(1.0)
    assert abs(ep.env.w.data.xfrc_applied[:, :3]).sum() == 0

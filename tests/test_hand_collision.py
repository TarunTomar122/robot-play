"""Root cause of the false `holding` (council round 5b, Fable): the planner assumed an open hand whenever nothing was held, so after a failed `pick` (hand closed) a `move_to` onto a cube was planned
as free, landed on the cube and still answered ok. A plain move_to is now planned with the finger opening the hand really has."""
from robot_play.tools import Episode


def _closed_hand_after_a_failed_pick():
    ep = Episode("stack", 20_000, quirk=True)
    r = ep.call("pick", {"object": "cube_green"})                    # the heavy cube is not held by a normal squeeze: the hand stays closed
    assert not r["ok"] and r["gripper_width_m"] < 0.03
    return ep


def test_a_closed_hand_cannot_move_down_onto_a_cube_and_answer_ok():
    ep = _closed_hand_after_a_failed_pick()
    p = ep.env.w.obj_pos("cube_green")
    r = ep.call("move_to", {"x": float(p[0]), "y": float(p[1]), "z": 0.02})
    reached = r.get("ok") and abs(r["tcp_m"][2] - 0.02) < 0.012 and abs(r["tcp_m"][0] - p[0]) < 0.012
    assert (not r.get("ok")) or reached                              # either an honest refusal or a move that really arrived, never ok about 2 cm high and off to the side
    if not r.get("ok"):
        assert "touch" in r["error"] or "stopped" in r["error"] or "collid" in r["error"].lower() or "would" in r["error"]


def test_after_opening_the_hand_the_same_move_arrives_where_it_was_asked():
    ep = _closed_hand_after_a_failed_pick()
    p = ep.env.w.obj_pos("cube_green")
    assert ep.call("open_gripper", {})["ok"]
    r = ep.call("move_to", {"x": float(p[0]), "y": float(p[1]), "z": 0.02})
    assert r["ok"] and abs(r["tcp_m"][2] - 0.02) < 0.012 and abs(r["tcp_m"][0] - p[0]) < 0.012

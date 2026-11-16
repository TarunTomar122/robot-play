"""Nothing the agent can see may reveal a hidden catch."""
import json

import pytest

from robot_play.tools import SYSTEM_PROMPT, TOOLS, Episode

FORBIDDEN = ["heavy", "mass", "weigh", "friction", "quirk", "catch", "hidden", "slip", "wide base", "top-heavy", "firm grip is needed",
             "release higher", "grab the neck", "narrow neck", "gram", " kg"]
ALLOWED_OBJECT_KEYS = {"name", "shape", "size_xyz_m", "position_m", "tilt_deg", "held"}


def _text(x):
    return json.dumps(x).lower()


@pytest.mark.parametrize("task", ["stack", "bins", "flasks"])
def test_prompt_and_tools_name_no_catch(task):
    ep = Episode(task, 1, quirk=True)
    blob = _text(TOOLS) + ep.prompt.lower() + SYSTEM_PROMPT.lower()
    for word in FORBIDDEN:
        assert word not in blob, f"'{word}' appears in what the agent is shown ({task})"


@pytest.mark.parametrize("task", ["stack", "bins", "flasks"])
def test_observation_has_only_geometry_and_poses(task):
    ep = Episode(task, 1, quirk=True)
    obs = ep.call("observe", {})
    assert set(obs) == {"objects", "zones", "gripper", "tcp_m", "sim_time_s"}
    for o in obs["objects"]:
        assert set(o) == ALLOWED_OBJECT_KEYS
    for word in FORBIDDEN:
        assert word not in _text(obs)


@pytest.mark.parametrize("task", ["stack", "bins", "flasks"])
def test_failure_messages_do_not_explain_causes(task):
    """The tool results of the naive failures must be measurements or raw planner reasons, never advice."""
    ep = Episode(task, 2, quirk=True)
    results = []
    if task == "stack":
        results.append(ep.call("pick", {"object": "cube_green"}))
    elif task == "bins":
        ep.call("pick", {"object": "cube_red1"})
        results.append(ep.call("place", {"target": "bin_red"}))
    else:
        results.append(ep.call("pick", {"object": "flask_a"}))
    for word in FORBIDDEN + ["try ", "should", "too ", "because"]:
        assert word not in _text(results), f"'{word}' in a failure result"


def test_quirk_and_control_observations_differ_only_by_visible_geometry():
    q = Episode("stack", 4, quirk=True).call("observe", {})
    c = Episode("stack", 4, quirk=False).call("observe", {})
    assert q == c            # the heavy cube looks identical to a light one

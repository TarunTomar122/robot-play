"""Play a task by hand through exactly the interface an LLM sees. The simulation is deterministic, so a session is just a
list of calls that is replayed each time.

  play.py start stack 3            new session (quirk scene by default; add --control for the no-quirk scene)
  play.py call pick '{"object": "cube_green"}'
  play.py finish                   print the simulator's verdict
"""
import json, sys
from pathlib import Path

from robot_play.tools import Episode

SESSION = Path("/tmp/robot_play_session.json")


def build(sess):
    ep = Episode(sess["task"], sess["seed"], quirk=sess["quirk"])
    out = None
    for name, args in sess["calls"]:
        out = ep.call(name, args)
    return ep, out


def main():
    cmd = sys.argv[1]
    if cmd == "start":
        sess = {"task": sys.argv[2], "seed": int(sys.argv[3]), "quirk": "--control" not in sys.argv, "calls": []}
        SESSION.write_text(json.dumps(sess))
        ep = Episode(sess["task"], sess["seed"], quirk=sess["quirk"])
        print(ep.prompt)
        return
    sess = json.loads(SESSION.read_text())
    if cmd == "call":
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        ep, _ = build(sess)
        res = ep.call(sys.argv[2], args)
        sess["calls"].append([sys.argv[2], args])
        SESSION.write_text(json.dumps(sess))
        print(f"[call {ep.calls}/{ep.max_calls}]", json.dumps(res))
    elif cmd == "finish":
        ep, _ = build(sess)
        print(json.dumps(ep.result()))


main()

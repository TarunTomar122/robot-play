"""One live episode with one model, printed call by call. Uses the real spend meter. Seeds 50000+ are never used by any experiment."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from robot_play.agent import Memory, play_episode
from robot_play.llm import load_env_keys, make_provider
from robot_play.spend import SpendMeter

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--task", default="stack")
ap.add_argument("--seed", type=int, default=50000)
ap.add_argument("--control", action="store_true")
ap.add_argument("--save", default=None)
a = ap.parse_args()
load_env_keys()
meter = SpendMeter("runs/spend")
p = make_provider(a.model, meter, run_id=f"smoke-{a.model}-{a.task}-{a.seed}")
rec = play_episode(p, a.task, a.seed, not a.control, Memory("none"))
for e in rec.log:
    print(f"{e['i']:>2}. {e['tool']} {json.dumps(e['args'])[:110]}\n      -> {json.dumps(e['result'])[:230]}")
print("RESULT", json.dumps(rec.result))
print("USAGE", rec.usage, "cost $%.4f" % rec.cost_usd, "turns", rec.turns, "nudges", rec.nudges, "wall %.0fs" % rec.wall_s, rec.notes)
print("METER", meter.totals())
if a.save:
    Path(a.save).write_text(json.dumps(rec.to_dict()))

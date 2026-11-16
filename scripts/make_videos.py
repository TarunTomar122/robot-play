"""Render the hand-played episodes (docs/human_play/*.json) to captioned videos in media/."""
import json, sys
from pathlib import Path

from robot_play.render import record_episode
from robot_play.tools import Episode

ROOT = Path(__file__).resolve().parents[1]
TITLES = {"stack": "Stack the three cubes", "bins": "Sort the cubes into the bins", "flasks": "Stand the flasks in their rings"}


def main(tag="v1", only=None):
    for f in sorted((ROOT / "docs/human_play").glob("*.json")):
        s = json.loads(f.read_text())
        if only and s["task"] != only:
            continue
        ep = Episode(s["task"], s["seed"], quirk=s["quirk"])
        out = ROOT / "media" / f"{f.stem}-{tag}.mp4"
        r = record_episode(ep, [tuple(c) for c in s["calls"]], out, f"{TITLES[s['task']]}  (played by hand through the same tools an AI gets)")
        print(out.name, r["success"], r["calls"])


if __name__ == "__main__":
    main(*(sys.argv[1:3]))

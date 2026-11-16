"""Render episodes that a language model actually played (from the run files) as captioned videos, by replaying the logged tool calls on the same layout.

  python scripts/make_llm_videos.py --pick runs/main --model claude-haiku-5-5 --task stack --tag a1      # find a learning pair and render it
  python scripts/make_llm_videos.py --file runs/main/<run>.jsonl --phase eval --idx 0 --tag a1             # render one named episode

A learning pair is one run seed where the notebook model's FIRST practice episode failed and a held-out episode of the same run succeeded, plus the
no-memory model's attempt on the same held-out layout. The replay is deterministic (the simulator is), and the script checks that the replayed result matches the logged one,
so a video can never show an outcome the model did not get. Output: media/<model>-<task>-<what>-<tag>.mp4 (use a new tag for every render and watch it before showing it)."""
import argparse
import json
from pathlib import Path

from robot_play.render import record_episode
from robot_play.tools import Episode

ROOT = Path(__file__).resolve().parents[1]
TITLES = {"stack": "Stack the three cubes", "bins": "Sort the cubes into the bins", "flasks": "Stand the flasks in their rings"}


def _rows(path):
    out = []
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        if "run" in r and "log" in r:
            out.append(r)
    return out


def render(row, tag: str, what: str, headline: str) -> Path:
    calls = [(c["tool"], c["args"]) for c in row["log"]]
    ep = Episode(row["task"], row["seed"], quirk=row["quirk"], max_calls=row["max_calls"], disturbance=row["disturbance"], toolset=row["toolset"])
    out = ROOT / "media" / f"{row['model']}-{row['task']}-{what}-{tag}.mp4"
    out.parent.mkdir(exist_ok=True)
    r = record_episode(ep, calls, out, f"{headline}  ({row['model']}, {row['condition']} memory)")
    logged = bool(row["result"]["success"])
    if bool(r["success"]) != logged:
        out.unlink(missing_ok=True)
        raise SystemExit(f"replay disagrees with the logged result for {row['run']} {row['phase']} {row['idx']}: replayed {r['success']}, logged {logged}")
    print(out.name, "success" if r["success"] else "failed", r["calls"], "calls")
    return out


def pick_pairs(run_dir, model, task):
    """Yield (practice0, eval_with_notebook, eval_fresh) for run seeds where the first practice attempt failed, the notebook run succeeded on a held-out layout and the fresh run did not."""
    by = {}
    for f in sorted(Path(run_dir).glob("*.jsonl")):
        for r in _rows(f):
            if r["model"] == model and r["task"] == task and r["quirk"] and r["disturbance"] is None:
                by.setdefault((r["condition"], r["run_seed"]), []).append(r)
    for (cond, rs), rows in sorted(by.items()):
        if cond != "notebook":
            continue
        p0 = next((r for r in rows if r["phase"] == "practice" and r["idx"] == 0), None)
        fresh = by.get(("none", rs), [])
        if not p0 or p0["result"]["success"]:
            continue
        for e in (r for r in rows if r["phase"] == "eval" and r["result"]["success"]):
            f = next((x for x in fresh if x["phase"] == "eval" and x["seed"] == e["seed"] and not x["result"]["success"]), None)
            if f:
                yield p0, e, f
                break


def pick_borrowed(main_dir, borrowed_dir, model, task):
    """Yield (fresh_failed, borrowed_succeeded) on the same layout: the no-memory model failed it, the same model reading Fable's notebook solved it."""
    fresh = {}
    for f in sorted(Path(main_dir).glob("*.jsonl")):
        for r in _rows(f):
            if r["model"] == model and r["task"] == task and r["condition"] == "none" and r["phase"] == "eval" and r["quirk"] and not r["result"]["success"]:
                fresh[r["seed"]] = r
    for f in sorted(Path(borrowed_dir).glob("*.jsonl")):
        for r in _rows(f):
            if r["model"] == model and r["task"] == task and r["condition"] == "borrowed" and r["phase"] == "eval" and r["result"]["success"] and r["seed"] in fresh:
                yield fresh[r["seed"]], r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick")
    ap.add_argument("--pick-borrowed", nargs=2, metavar=("MAIN_DIR", "BORROWED_DIR"), help="find a layout the model failed fresh and solved with Fable's notebook")
    ap.add_argument("--model")
    ap.add_argument("--task")
    ap.add_argument("--file")
    ap.add_argument("--phase")
    ap.add_argument("--idx", type=int)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--max-pairs", type=int, default=1)
    a = ap.parse_args()
    if a.file:
        for r in _rows(a.file):
            if r["phase"] == a.phase and r["idx"] == a.idx:
                render(r, a.tag, f"{a.phase}{a.idx}", TITLES[r["task"]])
        return
    if a.pick_borrowed:
        n = 0
        for fresh, bor in pick_borrowed(a.pick_borrowed[0], a.pick_borrowed[1], a.model, a.task):
            base = f"layout{fresh['seed']}"
            render(fresh, a.tag, f"{base}-no-memory", f"{TITLES[a.task]}: a new layout, no memory")
            render(bor, a.tag, f"{base}-fable-notebook", f"{TITLES[a.task]}: the same layout, reading Fable's notebook")
            n += 1
            if n >= a.max_pairs:
                break
        if n == 0:
            print("no layout found that the model failed fresh and solved with Fable's notebook")
        return
    n = 0
    for p0, e, f in pick_pairs(a.pick, a.model, a.task):
        base = f"rs{p0['run_seed']}"
        render(p0, a.tag, f"{base}-first-practice-attempt", f"{TITLES[a.task]}: first ever attempt")
        render(f, a.tag, f"{base}-heldout-fresh", f"{TITLES[a.task]}: same new layout, no memory")
        render(e, a.tag, f"{base}-heldout-notebook", f"{TITLES[a.task]}: same new layout, with its notebook")
        n += 1
        if n >= a.max_pairs:
            break
    if n == 0:
        print("no learning pair found (needs a failed first practice attempt, a successful held-out notebook episode and a failed fresh episode on the same layout)")


if __name__ == "__main__":
    main()

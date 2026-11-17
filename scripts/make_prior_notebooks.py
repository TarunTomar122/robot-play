"""Zero-practice notebooks for the `prior` cell (PROTOCOL.md v1.7): a stronger model writes a notebook from the task description and the tool descriptions ALONE, before any episode is played.
One file per (job, run seed), written once and never rewritten, so every cheap model that reads it reads the same text.
  python scripts/make_prior_notebooks.py --seeds 20-29 --out runs/prior_notebooks [--model claude-fable-5-2] [--meter runs/spend]
Spends money behind the spend cap (about 30 short calls). Resumable: a file that exists is kept."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from robot_play.agent import PRIOR_SYSTEM, prior_request
from robot_play.env import TASKS
from robot_play.llm import load_env_keys, make_provider
from robot_play.spend import SpendMeter
from robot_play.tools import TOOLSETS


def tool_text(toolset: str = "skills") -> str:
    lines = []
    for t in TOOLSETS[toolset]:
        props = t.get("input_schema", {}).get("properties", {})
        params = "; ".join(f"{k} ({v.get('type', '')}{', one of ' + '/'.join(v['enum']) if v.get('enum') else ''}): {v.get('description', '')}" for k, v in props.items())
        lines.append(f"- {t['name']}: {t['description']}" + (f" Parameters: {params}" if params else ""))
    return "\n".join(lines)


def parse_seeds(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="20-29")
    ap.add_argument("--out", default="runs/prior_notebooks")
    ap.add_argument("--model", default="claude-fable-5-2")
    ap.add_argument("--meter", default="runs/spend")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tt = tool_text()
    todo = [(t, s) for t in TASKS for s in parse_seeds(a.seeds) if not (out / f"{t}__s{s}.json").exists()]
    print(f"{len(todo)} notebooks to write ({len(TASKS) * len(parse_seeds(a.seeds)) - len(todo)} exist)")
    if a.dry_run:
        print(prior_request(TASKS["stack"].instruction, tt, TASKS["stack"].max_calls)[:1500])
        return
    load_env_keys()
    provider = make_provider(a.model, SpendMeter(a.meter), run_id="prior_notebooks")
    for t, s in todo:
        paid0 = provider.tally.usd
        text, usage = provider.complete(PRIOR_SYSTEM, prior_request(TASKS[t].instruction, tt, TASKS[t].max_calls))
        if not text:
            print(f"{t} s{s}: empty or cut off, skipped")
            continue
        (out / f"{t}__s{s}.json").write_text(json.dumps({"task": t, "run_seed": s, "model": a.model, "text": text.strip(), "usage": usage, "cost_usd": provider.tally.usd - paid0, "ts": int(time.time())}, indent=1))
        print(f"{t} s{s}: {len(text)} chars, ${provider.tally.usd - paid0:.4f}")
    print(f"spent ${provider.tally.usd:.3f}")


if __name__ == "__main__":
    main()

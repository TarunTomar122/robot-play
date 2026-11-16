"""An independent recomputation of the headline numbers straight from the run files, with no use of robot_play.analysis, so a bug in the analysis code cannot hide.
Held-out (phase 'eval', catch scenes) success of each model and memory condition, per job and pooled, from complete runs only (every planned episode finished), and calls to success.
  python scripts/recompute_headlines.py runs/main --out results/recomputed_headlines.md"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default="results/recomputed_headlines.md")
    a = ap.parse_args()
    cell = defaultdict(lambda: [0, 0, 0.0])           # (model, task, condition) -> [successes, episodes, calls to success]
    complete = incomplete = 0
    for d in a.dirs:
        for f in sorted(Path(d).glob("*.jsonl")):
            cfg, rows = None, []
            for line in f.read_text().splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    break
                if "_config" in r:
                    cfg = r["_config"]
                elif "_aborted" not in r:
                    rows.append(r)
            if not cfg:
                continue
            if len(rows) < len(cfg["plan"]):
                incomplete += 1
                continue
            complete += 1
            for r in rows:
                if r["phase"] != "eval" or not r["quirk"] or r.get("toolset", "skills") != "skills":
                    continue
                c = cell[(r["model"], r["task"], r["condition"])]
                res = r["result"]
                c[0] += int(bool(res["success"]))
                c[1] += 1
                c[2] += res["calls"] if res["success"] else (r.get("max_calls") or 20)
    L = ["# Headline numbers, recomputed from the raw run files", "", f"No use of `robot_play.analysis`. Complete runs: {complete}; incomplete runs left out: {incomplete}. Held-out episodes, catch scenes, skills toolset.", "",
         "| model | memory | job | episodes | solved | success | calls to success |", "|---|---|---|---|---|---|---|"]
    pooled = defaultdict(lambda: [0, 0, 0.0])
    for (m, t, c), (s, n, k) in sorted(cell.items()):
        L.append(f"| {m} | {c} | {t} | {n} | {s} | {100 * s / n:.1f}% | {k / n:.2f} |")
        p = pooled[(m, c)]
        p[0] += s
        p[1] += n
        p[2] += k
    L += ["", "Pooled over jobs (episode-weighted; the analysis report weights each job by its number of complete runs, so the two can differ by a point where a job lost a run):", "",
          "| model | memory | episodes | solved | success | calls to success |", "|---|---|---|---|---|---|"]
    for (m, c), (s, n, k) in sorted(pooled.items()):
        L.append(f"| {m} | {c} | {n} | {s} | {100 * s / n:.1f}% | {k / n:.2f} |")
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L[-12:]))


if __name__ == "__main__":
    main()

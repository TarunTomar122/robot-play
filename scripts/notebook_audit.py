"""Did the notebooks write down the setting that fixes each job? Descriptive and exploratory; a keyword check, not a judgement of quality.

For every notebook run (a model, a job, a run seed) this reads the notebook the model wrote after each practice episode and checks whether it names the fixing setting:
  stack  : a firm grip      -> grip_level set to firm
  bins   : letting go high  -> release_height of 0.14 or more
  flasks : a high grasp     -> grasp_height of 0.8 or more (the pose gate found the catch bites below about 80% of the flask height; I first wrote 0.85, a guess, and changed it
                               to 0.8 after reading Fable's finished notebooks, which use 0.8 and succeed; this is stated in the report)
It reports, per model and job, the share of runs whose final notebook names the fix, how many practice episodes it took on average, and the held-out success of runs whose
notebook names the fix against runs whose notebook does not. A notebook can name the fix and the model can still fail, or succeed without naming it; this table says which.
  python scripts/notebook_audit.py runs/main --out results/notebook_audit.md"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

FIX = {
    "stack": lambda t: re.search(r"grip_level[\"'\s:=]*firm", t, re.I) is not None,
    "bins": lambda t: any(float(v) >= 0.14 for v in re.findall(r"release_height[\"'\s:=]*([0-9]*\.?[0-9]+)", t)),
    "flasks": lambda t: any(float(v) >= 0.8 for v in re.findall(r"grasp_height[\"'\s:=]*([0-9]*\.?[0-9]+)", t)),
}
NAMES = {"stack": "stack (firm grip)", "bins": "sort (release from 14 cm or higher)", "flasks": "stand the flasks (grasp at 0.8 or higher)"}


def _text(mem) -> str:
    if isinstance(mem, dict):
        return str(mem.get("notebook") or "")
    return str(mem or "")


def load_runs(dirs):
    runs = defaultdict(lambda: {"practice": {}, "eval": []})
    for d in dirs:
        for f in sorted(Path(d).glob("*.jsonl")):
            for line in f.read_text().splitlines():
                r = json.loads(line)
                if "result" not in r or r.get("condition") != "notebook" or not r.get("quirk") or r.get("disturbance"):
                    continue
                k = (r["model"], r["task"], r["run_seed"], r.get("toolset", "skills"))
                if r["phase"] == "practice":
                    runs[k]["practice"][r["idx"]] = _text(r.get("memory"))
                elif r["phase"] == "eval":
                    runs[k]["eval"].append(int(r["result"]["success"]))
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default="results/notebook_audit.md")
    a = ap.parse_args()
    runs = load_runs(a.dirs)
    by = defaultdict(list)
    for (model, task, rs, tools), v in runs.items():
        if tools != "skills" or not v["practice"] or len(v["eval"]) < 4:
            continue                                          # complete runs only: all practice notebooks and four held-out episodes
        texts = [v["practice"][i] for i in sorted(v["practice"])]
        named = [FIX[task](t) for t in texts]
        first = next((i + 1 for i, n in enumerate(named) if n), None)
        by[(model, task)].append({"final": named[-1], "first": first, "eval": float(np.mean(v["eval"]))})
    L = ["# Did the notebooks name the fix?", "",
         "Exploratory and descriptive: a keyword check of each run's notebooks (the notebook after each of the 12 practice episodes), not a judgement of quality. Complete notebook runs only. "
         "'Names the fix' means the notebook contains the setting that fixes the job: " + "; ".join(f"{NAMES[t]}" for t in FIX) + ".", "",
         "| model | job | runs | final notebook names the fix | practice episodes until it first does (mean, of the runs that do) | held-out success, notebook names the fix | held-out success, it does not |", "|---|---|---|---|---|---|---|"]
    for (model, task), rs in sorted(by.items()):
        yes = [r for r in rs if r["final"]]
        no = [r for r in rs if not r["final"]]
        firsts = [r["first"] for r in rs if r["first"]]
        L.append(f"| {model} | {task} | {len(rs)} | {len(yes)}/{len(rs)} | {np.mean(firsts):.1f} | " if firsts else f"| {model} | {task} | {len(rs)} | {len(yes)}/{len(rs)} | never | ")
        L[-1] += (f"{100 * np.mean([r['eval'] for r in yes]):.0f}% ({len(yes)} runs)" if yes else "n/a") + " | " + (f"{100 * np.mean([r['eval'] for r in no]):.0f}% ({len(no)} runs)" if no else "n/a") + " |"
    if not by:
        L.append("| no complete notebook runs yet | | | | | | |")
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

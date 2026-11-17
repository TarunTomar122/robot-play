"""Do Haiku's own notebooks name the firm grip after 1, 3, 6 and 12 practice episodes? (`stack`, final notebook of each run, keyword audit)

    python scripts/dose_audit.py [runs] > results/dose_notebook_audit.md

A keyword audit, chosen after seeing that the firm grip is the fix: it says whether the notebook mentions `firm`, not that the model followed it."""
import collections
import glob
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs")
res = collections.defaultdict(list)
held = collections.defaultdict(lambda: [0, 0])          # (names firm?, practice outcome of a one-episode run) -> [held-out successes, held-out episodes]
files = sorted(glob.glob(str(root / "dose" / "*.jsonl"))) + sorted(glob.glob(str(root / "rep_fixed" / "claude-haiku-5-5__stack__notebook__quirk__p12__s*.jsonl")))
for f in files:
    rows = [json.loads(x) for x in Path(f).read_text().splitlines()][1:]
    k = int(re.search(r"__p(\d+)__s", f).group(1))
    rs = int(re.search(r"__s(\d+)", f).group(1))
    practice = [r for r in rows if r.get("phase") == "practice"]
    nb = practice[-1].get("memory") if practice else None
    text = nb if isinstance(nb, str) else json.dumps(nb)
    res[k].append((rs, "firm" in text.lower()))
    ev = [r for r in rows if r.get("phase") == "eval"]
    keys = ["names firm" if "firm" in text.lower() else "does not name firm"]
    if k == 1:
        keys.append("one-episode notebooks that " + ("name firm" if "firm" in text.lower() else "do not name firm"))
        keys.append("one-episode notebooks, first practice episode " + ("solved" if practice and practice[0]["result"]["success"] else "failed"))
    for key in keys:
        held[key][0] += sum(1 for r in ev if r["result"]["success"])
        held[key][1] += len(ev)
print("# Do the model's own notebooks name the firm grip?\n")
print("Final notebook of every Haiku `stack` run with its own notebook, by number of practice episodes (run seeds 20 to 39; 12 episodes: 20 to 29 from `rep_fixed`, 30 to 39 from `dose`). Keyword audit: the word `firm` appears in the notebook. The keyword was chosen after the fact; this is not evidence that the notebook caused the success.\n")
print("| practice episodes | runs | notebooks mentioning `firm` |")
print("|---|---|---|")
for k in sorted(res):
    print(f"| {k} | {len(res[k])} | {sum(x for _, x in res[k])} |")
print("\nHeld-out success by what the final notebook says and, for the one-episode notebooks, by how the single practice episode went (all runs above; 4 held-out layouts per run; descriptive):\n")
print("| group | held-out successes | held-out episodes |")
print("|---|---|---|")
for key in sorted(held):
    print(f"| {key} | {held[key][0]} | {held[key][1]} |")

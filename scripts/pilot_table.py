"""Summarise a no-memory pilot (layouts 50,000 and up, never part of any reported result) into a committed table.

  python scripts/pilot_table.py runs/pilot21 --out results/pilot_no_memory.md [--note "..."]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from robot_play import analysis as A


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default="results/pilot_no_memory.md")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    rows = A.load(*a.dirs)
    L = ["# No-memory pilot", "", "Layouts 50,000 and up, which no reported result uses. One try per layout, no memory. " + a.note, "",
         "| model | tools | task | episodes | success | mean calls | said done but wrong | dollars per episode |", "|---|---|---|---|---|---|---|---|"]
    for m in sorted({r["model"] for r in rows}):
        for tools in sorted({r["toolset"] for r in rows if r["model"] == m}):
            for t in ("stack", "bins", "flasks"):
                rs = [r for r in rows if r["model"] == m and r["task"] == t and r["toolset"] == tools]
                if rs:
                    L.append(f"| {m} | {tools} | {t} | {len(rs)} | {sum(r['success'] for r in rs)}/{len(rs)} | {np.mean([r['calls'] for r in rs]):.1f} | {sum(r['false_claim'] for r in rs)} | ${np.mean([r['cost_usd'] for r in rs]):.4f} |")
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

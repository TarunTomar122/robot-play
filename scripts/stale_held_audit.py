"""Could the 'held' state be wrong? Two ways, both listed here (symptoms only: absence of the symptom does not prove the state was right).
1. Stale after `home` (Codex's round-4 note: `home` and the start of `pick` do not refresh the held state): `pick` answers "already holding X" although the object was lost.
2. False hold (Fable's round-5a finding, which this script first reported as noise): `close_gripper` answers `holding` with the fingers nearly closed (under 3 cm), because the fingertips rest on top of the
   object; `pick` then says "already holding" and `place` says "not holding anything". Most "already holding" hits on live data are this second kind.
This lists every episode where `pick` said "already holding", with the calls just before it, and counts the false holds separately.
  python scripts/stale_held_audit.py runs/main runs/control ... [--out results/stale_held_audit.md]"""
import argparse
import json
from collections import Counter
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", default="results/stale_held_audit.md")
    a = ap.parse_args()
    total = home_then_pick = already = false_hold_eps = fh_already = 0
    flagged, by = [], Counter()
    for d in a.dirs:
        for f in sorted(Path(d).glob("*.jsonl")):
            for line in f.read_text().splitlines():
                r = json.loads(line)
                if "log" not in r:
                    continue
                total += 1
                log = r["log"]
                fh_idx = [i for i, c in enumerate(log) if c["tool"] == "close_gripper" and (c.get("result") or {}).get("holding") and float((c.get("result") or {}).get("gripper_width_m", 1.0)) < 0.03]
                false_hold_eps += bool(fh_idx)
                for i, c in enumerate(log):
                    if c["tool"] == "pick" and i and log[i - 1]["tool"] == "home":
                        home_then_pick += 1
                    if c["tool"] == "pick" and "already holding" in json.dumps(c.get("result", {})):
                        already += 1
                        fh_already += any(j < i for j in fh_idx)
                        prev = [x["tool"] for x in log[max(0, i - 3):i]]
                        by[tuple(prev)] += 1
                        flagged.append((r["run"], r["phase"], r["idx"], i + 1, " > ".join(prev)))
    L = ["# Stale held state after `home` (audit)", "",
         f"Episodes scanned: {total}. Times `pick` came directly after `home`: {home_then_pick}. Times `pick` answered \"already holding\": {already}, of which {fh_already} came after a false hold (a `close_gripper` that said `holding` with the fingers under 3 cm apart). "
         f"Episodes containing a false hold: {false_hold_eps}.", ""]
    if flagged:
        L += ["| run | phase | episode | call | the three calls before it |", "|---|---|---|---|---|"] + [f"| {a_} | {b} | {c} | {d_} | {e} |" for a_, b, c, d_, e in flagged[:60]]
        L += ["", f"Most common call just before: {by.most_common(3)}. Each listed episode could have been affected only if the object had in fact been lost during `home` (check its log); an honest \"already holding\" after a successful pick is not a defect."]
    else:
        L += ["No episode shows the symptom."]
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()

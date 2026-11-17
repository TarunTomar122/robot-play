"""Check every run file for repeated or out-of-order episodes and for a missing or mixed code hash.

    python scripts/check_run_files.py runs/main runs/control ...

A run file is a header line (`_config`, with the plan) followed by one line per finished episode in plan order. Two processes that write the same
file (for example workers that outlived a stopped runner) leave repeated (phase, index) pairs. Exit code 1 if any file is not clean."""
import collections
import json
import sys
from pathlib import Path

bad = 0
for d in sys.argv[1:] or ["runs"]:
    codes = collections.Counter()
    for f in sorted(Path(d).glob("*.jsonl")):
        lines = [x for x in f.read_text().splitlines() if x.strip()]
        if not lines or not lines[0].startswith('{"_config"'):
            continue
        cfg = json.loads(lines[0])["_config"]
        codes[cfg.get("code")] += 1
        eps = [json.loads(x) for x in lines[1:]]
        eps = [r for r in eps if "result" in r]
        keys = [(r.get("phase"), r.get("idx")) for r in eps]
        plan = [(p["phase"], p["idx"]) for p in cfg["plan"]]
        if len(set(keys)) != len(keys) or keys != plan[:len(keys)]:
            bad += 1
            print(f"NOT CLEAN {f}: {len(keys)} episodes, {len(plan)} planned, {len(keys) - len(set(keys))} repeated")
    print(f"{d}: code hashes {dict(codes)}")
print("all clean" if not bad else f"{bad} file(s) not clean")
raise SystemExit(1 if bad else 0)

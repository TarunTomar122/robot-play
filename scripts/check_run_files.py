"""Check run files for repeated or out-of-order episodes, header-less files and (optionally) unexpected code hashes.

    python scripts/check_run_files.py runs/main runs/control ...
    python scripts/check_run_files.py --expect 4d59e8f26cd2a9b6 runs/main        # also fail on any other code hash

A run file is a header line (`_config`, with the plan and the code hash) followed by one line per finished episode in plan order (and, if a run was
interrupted, `_aborted` records that cost nothing or are kept for their cost). Two processes that write the same file (for example workers that outlived
a stopped runner) leave repeated (phase, index) pairs; a file whose first line is not a header cannot be resumed or analysed. Exit code 1 if any file is not clean."""
import collections
import json
import sys
from pathlib import Path

args = sys.argv[1:]
expect = set()
if "--expect" in args:
    i = args.index("--expect")
    j = i + 1
    while j < len(args) and not Path(args[j]).exists():
        expect.add(args[j])
        j += 1
    args = args[:i] + args[j:]
bad = 0
for d in args or ["runs"]:
    codes = collections.Counter()
    aborted = 0
    for f in sorted(Path(d).glob("*.jsonl")):
        lines = [x for x in f.read_text().splitlines() if x.strip()]
        if not lines:
            continue
        if not lines[0].startswith('{"_config"'):
            bad += 1
            print(f"NOT CLEAN {f}: first line is not a header")
            continue
        cfg = json.loads(lines[0])["_config"]
        codes[cfg.get("code")] += 1
        if expect and cfg.get("code") not in expect:
            bad += 1
            print(f"NOT CLEAN {f}: code hash {cfg.get('code')} is not one of {sorted(expect)}")
        rows = [json.loads(x) for x in lines[1:]]
        aborted += sum(1 for r in rows if "_aborted" in r or r.get("aborted"))
        eps = [r for r in rows if "result" in r]
        keys = [(r.get("phase"), r.get("idx")) for r in eps]
        plan = [(p["phase"], p["idx"]) for p in cfg["plan"]]
        if len(set(keys)) != len(keys) or keys != plan[:len(keys)]:
            bad += 1
            print(f"NOT CLEAN {f}: {len(keys)} episodes, {len(plan)} planned, {len(keys) - len(set(keys))} repeated")
    print(f"{d}: code hashes {dict(codes)}" + (f", {aborted} abort record(s) (kept, harmless when the arm has no memory or the run resumed)" if aborted else ""))
print("all clean" if not bad else f"{bad} problem(s)")
raise SystemExit(1 if bad else 0)

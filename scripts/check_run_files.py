"""Check run files before analysing them.

    python scripts/check_run_files.py runs/main runs/control ...          # or: runs/*
    python scripts/check_run_files.py --expect 4d59e8f26cd2a9b6 runs/main  # also fail on any other code hash

A run file is a header line (`_config`: the plan and the code hash) followed by one line per finished episode in plan order (and, if a run was interrupted,
`_aborted` records that cost nothing or are kept for their cost). For every file the checker fails on:
  - an empty file or a first line that is not a header (such a file cannot be resumed or analysed);
  - a header whose plan seeds do not follow the registered rule (practice 10000 + 100 * run seed + i; held-out 20000 + 100 * (run seed + j // 4) + j % 4, which is 20000 + 100 * run seed + j for the usual four held-out episodes and spreads the frontier cell's 20 layouts over five run seeds' layouts);
  - an episode row whose model, task, condition, run seed, quirk flag, phase, index or seed differs from the header or its plan, or whose run name differs from the file name;
  - repeated or out-of-order episodes (two processes writing one file, for example workers that outlived a stopped runner);
  - with --expect, a code hash that is not one of the given hashes.
`--reported` stands for every run folder the results use (the pilot and smoke folders, which use layouts 50000+ and run seed 99, are left out).
Folders named `spend` (the spend ledger) and files that are not run files are not run folders and are skipped. Exit code 1 if any file is not clean."""
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
REPORTED = ["main", "main_ext", "control", "frontier", "frontier_exp", "pose", "borrowed", "borrowed_1", "borrowed_3", "borrowed_other", "borrowed_sonnet",
            "main_fixhold", "main_fixcollide", "rep_fixed", "hint", "hint_generic", "prior", "writer_sonnet", "labelmatch", "wordsplit"]
if "--reported" in args:
    i = args.index("--reported")
    args = args[:i] + [f"runs/{x}" for x in REPORTED if Path(f"runs/{x}").is_dir()] + args[i + 1:]
bad = 0
nfiles = 0
for d in args or ["runs"]:
    if not Path(d).is_dir() or Path(d).name == "spend":
        print(f"{d}: skipped (not a run folder)")
        continue
    codes = collections.Counter()
    aborted = 0
    for f in sorted(Path(d).glob("*.jsonl")):
        lines = [x for x in f.read_text().splitlines() if x.strip()]
        if not lines or not lines[0].startswith('{"_config"'):
            bad += 1
            print(f"NOT CLEAN {f}: {'empty file' if not lines else 'first line is not a header'}")
            continue
        nfiles += 1
        cfg = json.loads(lines[0])["_config"]
        codes[cfg.get("code")] += 1
        problems = []
        if expect and cfg.get("code") not in expect:
            problems.append(f"code hash {cfg.get('code')} is not one of {sorted(expect)}")
        rs = cfg.get("run_seed")
        for p in cfg["plan"]:
            want = 10000 + 100 * (rs if rs is not None else -10**6) + p["idx"] if p["phase"] == "practice" else 20000 + 100 * ((rs if rs is not None else -10**6) + p["idx"] // 4) + p["idx"] % 4
            if rs is None or p["seed"] != want:
                problems.append(f"plan seed {p['seed']} for {p['phase']} {p['idx']} is not the registered {want}")
                break
        rows = [json.loads(x) for x in lines[1:]]
        aborted += sum(1 for r in rows if "_aborted" in r or r.get("aborted"))
        eps = [r for r in rows if "result" in r]
        keys = [(r.get("phase"), r.get("idx")) for r in eps]
        plan = [(p["phase"], p["idx"]) for p in cfg["plan"]]
        if len(set(keys)) != len(keys) or keys != plan[:len(keys)]:
            problems.append(f"{len(keys)} episodes, {len(plan)} planned, {len(keys) - len(set(keys))} repeated or out of order")
        by_plan = {(p["phase"], p["idx"]): p for p in cfg["plan"]}
        for r in eps:
            p = by_plan.get((r.get("phase"), r.get("idx")))
            wrong = [k for k in ("model", "task", "condition", "run_seed", "quirk", "toolset") if r.get(k) != cfg.get(k)]
            if p is None or r.get("seed") != p["seed"] or r.get("result", {}).get("seed") != p["seed"]:
                wrong.append("seed")
            if r.get("run") != f.stem:
                wrong.append("run name")
            if wrong:
                problems.append(f"episode {r.get('phase')} {r.get('idx')} disagrees with the header or plan on {wrong}")
                break
        if problems:
            bad += 1
            print(f"NOT CLEAN {f}: " + "; ".join(problems))
    print(f"{d}: code hashes {dict(codes)}" + (f", {aborted} abort record(s) (kept, harmless when the arm has no memory or the run resumed)" if aborted else ""))
print(f"{nfiles} run files checked; " + ("all clean" if not bad else f"{bad} problem(s)"))
raise SystemExit(1 if bad else 0)

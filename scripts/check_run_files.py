"""Check run files before analysing them.

    python scripts/check_run_files.py runs/main runs/control ...          # or: runs/*
    python scripts/check_run_files.py --expect 4d59e8f26cd2a9b6 runs/main  # also fail on any other code hash

A run file is a header line (`_config`: the plan and the code hash) followed by one line per finished episode in plan order (and, if a run was interrupted,
`_aborted` records that cost nothing or are kept for their cost). For every file the checker fails on:
  - an empty file or a first line that is not a header (such a file cannot be resumed or analysed);
  - a header whose plan seeds do not follow the registered rule (practice 10000 + 100 * run seed + i; held-out 20000 + 100 * (run seed + j // 4) + j % 4, which is 20000 + 100 * run seed + j for the usual four held-out episodes and spreads the frontier cell's 20 layouts over five run seeds' layouts);
  - an episode row whose model, task, condition, run seed, quirk flag, phase, index or seed differs from the header or its plan, or whose run name differs from the file name;
  - repeated or out-of-order episodes (two processes writing one file, for example workers that outlived a stopped runner);
  - with --expect, a code hash that is not one of the given hashes;
  - a memory text (header `borrowed_notebook`) that differs from the registered text of that condition (hint, generic, inert and split arms);
  - with --reported, a missing folder, a different number of files or of unfinished files than the documented one (EXPECTED below), a code hash that is not the one
    results/code_versions.md lists for that folder, or no run file at all.
`--reported` stands for every run folder the results use (the pilot and smoke folders, which use layouts 50000+ and run seed 99, are left out).
Folders named `spend` (the spend ledger) and files that are not run files are not run folders and are skipped. Exit code 1 if any file is not clean."""
import collections
import json
import re
import sys
from pathlib import Path

HEX16 = re.compile(r"^[0-9a-f]{16}$")
args = sys.argv[1:]
expect = set()
if "--expect" in args:
    i = args.index("--expect")
    j = i + 1
    while j < len(args) and HEX16.match(args[j]):
        expect.add(args[j])
        j += 1
    args = args[:i] + args[j:]
# folder: (run files, files whose plan was not finished, code hashes). The unfinished files are the documented exclusions (the flasks run-seed-8 layout the original sampler cannot build, deviation 3).
EXPECTED = {
    "main": (180, 6, {"4d59e8f26cd2a9b6"}), "main_ext": (60, 0, {"4d59e8f26cd2a9b6"}), "control": (120, 4, {"4d59e8f26cd2a9b6"}), "frontier": (6, 0, {"4d59e8f26cd2a9b6"}),
    "frontier_exp": (30, 1, {"4d59e8f26cd2a9b6"}), "pose": (36, 0, {"4d59e8f26cd2a9b6"}), "borrowed": (58, 0, {"1cd309b2c89e94d7", "bdda918f09675319"}),
    "borrowed_1": (58, 0, {"90bd12fc77ec6f43"}), "borrowed_3": (58, 0, {"90bd12fc77ec6f43"}), "borrowed_other": (58, 2, {"bdda918f09675319"}), "borrowed_sonnet": (40, 0, {"088c639d7139a3af"}),
    "main_fixhold": (20, 0, {"c694b1a45aaf30c5"}), "main_fixcollide": (20, 0, {"aef351c5c3033d54"}), "rep_fixed": (120, 0, {"8fdcf6b2491b68a3"}),
    "hint": (60, 0, {"088c639d7139a3af"}), "hint_generic": (60, 0, {"088c639d7139a3af"}), "prior": (60, 0, {"088c639d7139a3af"}), "writer_sonnet": (20, 0, {"088c639d7139a3af"}),
    "labelmatch": (180, 0, {"58b19ca1be3740fe"}), "wordsplit": (30, 0, {"0346eddace878d63"}), "wordsplit2": (80, 0, {"c44187af32043997"}), "dose": (70, 0, {"33db266fef842900"}), "second": (50, 0, {"216aab61b6c8b09e"}),
}
# folder: (lowest, highest) run seed its files may carry (the registered seed plan of each cell; the dose folder holds seeds 20 to 39, its 12-episode runs only 30 to 39)
RUN_SEEDS = {
    "main": (0, 9), "main_ext": (10, 19), "control": (0, 9), "frontier": (0, 0), "frontier_exp": (0, 9), "pose": (0, 2), "borrowed": (0, 9), "borrowed_1": (0, 9), "borrowed_3": (0, 9),
    "borrowed_other": (0, 9), "borrowed_sonnet": (20, 29), "main_fixhold": (0, 9), "main_fixcollide": (0, 9), "rep_fixed": (20, 29), "hint": (20, 29), "hint_generic": (20, 29),
    "prior": (20, 29), "writer_sonnet": (20, 29), "labelmatch": (20, 29), "wordsplit": (20, 29), "wordsplit2": (30, 39), "dose": (20, 39), "second": (30, 39),
}
IMPORT_ERROR = None
try:
    from robot_play import runner
except Exception as exc:                      # the memory-text check cannot run without the registered texts: that is a failure, never a skip
    runner = None
    IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def registered_text(cond, task):
    """The memory text a run file of this condition must carry, or None when the condition has no fixed text."""
    if runner is None:
        return None
    fixed = {"hint_generic": runner.GENERIC_HINT, "lm_inert": runner.INERT_TEXT, "lm_generic": runner.GENERIC_HINT, "lm_frame": runner.SPLIT_TEXTS["lm_frame"],
             "lm_names": runner.SPLIT_TEXTS["lm_names"], "lm_instr": runner.SPLIT_TEXTS["lm_instr"], "lm_instr_n": runner.SPLIT2_TEXTS["lm_instr_n"], "lm_names2": runner.SPLIT2_TEXTS["lm_names2"]}
    if cond in ("hint", "lm_specific"):
        return runner.HINTS.get(task)
    return fixed.get(cond)


reported = "--reported" in args
if reported:
    i = args.index("--reported")
    args = args[:i] + [f"runs/{x}" for x in EXPECTED] + args[i + 1:]
bad = 0
nfiles = 0
if IMPORT_ERROR:
    bad += 1
    print(f"NOT CLEAN: cannot import robot_play.runner, so the registered memory texts cannot be checked ({IMPORT_ERROR}); run from the repository with its environment")
for d in args or ["runs"]:
    if Path(d).name == "spend":
        print(f"{d}: skipped (the spend ledger is not a run folder)")
        continue
    if not Path(d).is_dir():
        bad += 1
        print(f"NOT CLEAN {d}: no such folder")
        continue
    codes = collections.Counter()
    aborted = 0
    unfinished = 0
    files_here = 0
    for f in sorted(Path(d).glob("*.jsonl")):
        lines = [x for x in f.read_text().splitlines() if x.strip()]
        if not lines or not lines[0].startswith('{"_config"'):
            bad += 1
            print(f"NOT CLEAN {f}: {'empty file' if not lines else 'first line is not a header'}")
            continue
        nfiles += 1
        files_here += 1
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
        unfinished += len(eps) < len(cfg["plan"])
        want_text = registered_text(cfg.get("condition"), cfg.get("task"))
        if want_text is not None and cfg.get("borrowed_notebook") != want_text:
            problems.append(f"the memory text of condition {cfg.get('condition')} differs from the registered text")
        if want_text is not None:
            seen = [(r.get("phase"), r.get("idx")) for r in eps if (r.get("memory") or {}).get("notebook") != want_text]
            if seen:
                problems.append(f"{len(seen)} episode(s) carry a memory that differs from the registered text, first {seen[0]}")
        if Path(d).name in RUN_SEEDS and not (isinstance(rs, int) and RUN_SEEDS[Path(d).name][0] <= rs <= RUN_SEEDS[Path(d).name][1]):
            problems.append(f"run seed {rs} is outside the folder's range {RUN_SEEDS[Path(d).name]}")
        if Path(d).name == "dose" and "__p12__" in f.name and not (isinstance(rs, int) and rs >= 30):
            problems.append(f"the 12-episode dose runs start at run seed 30, not {rs}")
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
    if reported and Path(d).name in EXPECTED:
        n_exp, unf_exp, hashes_exp = EXPECTED[Path(d).name]
        if (files_here, unfinished) != (n_exp, unf_exp) or not set(codes) <= hashes_exp:
            bad += 1
            print(f"NOT CLEAN {d}: {files_here} files ({unfinished} unfinished) and hashes {sorted(codes)}, documented: {n_exp} files ({unf_exp} unfinished) and hashes {sorted(hashes_exp)}")
    print(f"{d}: code hashes {dict(codes)}" + (f", {aborted} abort record(s) (kept, harmless when the arm has no memory or the run resumed)" if aborted else ""))
if nfiles == 0:
    bad += 1
    print("NOT CLEAN: no run file was found")
print(f"{nfiles} run files checked; " + ("all clean" if not bad else f"{bad} problem(s)"))
raise SystemExit(1 if bad else 0)

"""Turn the run files into results/RESULTS.md and the learning-curve charts. Every number in the README comes from here.

  python scripts/analyze.py --main runs/main --control runs/control --frontier runs/frontier runs/frontier_exp --pose runs/pose

Tests and intervals are the ones fixed in PROTOCOL.md section 1: cluster bootstrap over runs (never single episodes or single layouts), complete runs only,
Bonferroni-adjusted intervals for the confirmatory family (Q1, Q3, Q4) and plain 95% intervals, labelled exploratory, for everything else.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from robot_play import analysis as A
from robot_play.spend import SpendMeter

ROOT = Path(__file__).resolve().parents[1]
MIN_Q1_PAIRS = 24                  # of 30 (task, run seed) pairs per model; fewer complete pairs and the claim is reported as inconclusive
MIN_Q3_CLUSTERS = 12               # of 15 (task, run seed) clusters per cheap model
MIN_Q4_PAIRS = 24                  # of 30 (task, run seed) pairs per model in the control cell (3 tasks x 10 run seeds)
FRONTIER_FLOOR = 0.5               # a frontier first try below this is not a target worth matching
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COLORS = {"none": "#2a78d6", "notebook": "#eb6834", "replay": "#1baf7a"}          # dataviz skill categorical slots 1-3 (validated all-pairs)
TASKS = ["stack", "bins", "flasks"]
NAMES = {"none": "starts fresh", "notebook": "keeps a notebook", "replay": "sees its last success", "borrowed": "reads Fable's notebook", "borrowed_other": "reads Fable's notebook for another job",
         "borrowed_1": "reads Fable's notebook after 1 practice episode", "borrowed_3": "reads Fable's notebook after 3 practice episodes"}


def f(x, pct=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{100 * x:.0f}%" if pct else f"{x:.2f}"


def ci(d, key="diff", pct=False, scale=1.0):
    if not d or d.get("n_pairs", d.get("n_catch_pairs", 1)) == 0 or key not in d:
        return "n/a"
    s = 100 * scale if pct else scale
    level = f"{100 * (1 - d.get('alpha', 0.05)):.2f}".rstrip("0").rstrip(".")
    return f"{s * d[key]:+.1f}{' pp' if pct else ''} ({level}% CI {s * d['lo']:+.1f} to {s * d['hi']:+.1f})"


def enough(d, need, key="n_pairs"):
    """True if the comparison rests on at least `need` complete pairs or clusters; otherwise the claim is reported as inconclusive."""
    return bool(d) and d.get(key, 0) >= need


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def mean_over(d, keys):
    v = [d[k] for k in keys if k in d]
    return f"${np.mean(v):.2f}" if v else "n/a"


def mean(rows, key):
    return float(np.mean([r[key] for r in rows])) if rows else float("nan")


def learning_chart(rows, models, out):
    fig, axes = plt.subplots(len(models), 3, figsize=(13, 3.6 * len(models)), sharey=True, facecolor=SURFACE, squeeze=False)
    for i, m in enumerate(models):
        for j, t in enumerate(TASKS):
            ax = axes[i][j]
            ax.set_facecolor(SURFACE)
            for c in ("none", "notebook", "replay"):
                cur = A.curve([r for r in rows if r["task"] == t], m, c, "success", n_boot=10_000)
                if not cur:
                    continue
                x = [p["idx"] + 1 for p in cur]
                ax.plot(x, [100 * p["mean"] for p in cur], color=COLORS[c], lw=2, marker="o", ms=5, label=NAMES[c])
                ax.fill_between(x, [100 * (p["lo"] if p["lo"] == p["lo"] else p["mean"]) for p in cur], [100 * (p["hi"] if p["hi"] == p["hi"] else p["mean"]) for p in cur], color=COLORS[c], alpha=0.15, lw=0)
            ax.set_title(f"{m}: {t}", loc="left", fontsize=11, color=INK)
            ax.set_ylim(-3, 103)
            ax.grid(axis="y", color=GRID, lw=0.8)
            ax.set_xlabel("practice attempt")
            for s in ("top", "right", "left"):
                ax.spines[s].set_visible(False)
            ax.tick_params(length=0)
    axes[0][0].set_ylabel("attempts that finish the job (%)")
    axes[0][0].legend(frameon=False, fontsize=9, loc="lower right")
    fig.suptitle("Success on each practice attempt, averaged over runs (band: 95% cluster-bootstrap interval)", x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=140, bbox_inches="tight", facecolor=SURFACE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", nargs="*", default=["runs/main"])
    ap.add_argument("--control", nargs="*", default=["runs/control"])
    ap.add_argument("--frontier", nargs="*", default=["runs/frontier", "runs/frontier_exp"])
    ap.add_argument("--pose", nargs="*", default=["runs/pose"])
    ap.add_argument("--borrowed", nargs="*", default=["runs/borrowed", "runs/borrowed_other", "runs/borrowed_1", "runs/borrowed_3"])
    ap.add_argument("--ext", nargs="*", default=["runs/main_ext"], help="exploratory room-cell extension (Haiku, stack and bins, run seeds 10-19); never enters a confirmatory number")
    ap.add_argument("--fixhold", nargs="*", default=["runs/main_fixhold"], help="exploratory rerun of Haiku on stack with only the false-holding symptom fixed (PROTOCOL.md v1.5B); never pooled with the registered rows")
    ap.add_argument("--fixcollide", nargs="*", default=["runs/main_fixcollide"], help="exploratory rerun of Haiku on stack with the cause fixed too: move_to planned with the real finger opening (PROTOCOL.md v1.5C)")
    ap.add_argument("--meter", default="runs/spend")
    ap.add_argument("--out", default="results/RESULTS.md")
    ap.add_argument("--img", default="docs/img")
    a = ap.parse_args()
    ex = lambda ds: [d for d in ds if Path(d).exists()]
    dirs = ex(a.main + a.control + a.frontier + a.pose + a.borrowed)
    rows = A.load(*dirs, complete_only=True)                          # confirmatory numbers use runs that finished their whole plan
    cov = A.coverage(*dirs)
    ext_rows = A.load(*ex(a.ext), complete_only=True) if ex(a.ext) else []
    ext_cov = A.coverage(*ex(a.ext)) if ex(a.ext) else []
    abandoned = {}
    for c in cov:
        k = (c["model"], c["toolset"], c["task"], c["condition"], c["quirk"], c["run_seed"])
        abandoned[k] = abandoned.get(k, 0.0) + c["aborted_usd"]
    skills = [r for r in rows if r.get("toolset") in (None, "skills")]
    pose = [r for r in rows if r.get("toolset") == "pose"]
    models = sorted({r["model"] for r in skills})
    cheap = [m for m in models if m in ("claude-haiku-5-5", "gpt-6-luna")]
    L = ["# Results", "", "Generated by `scripts/analyze.py`. Intervals are cluster-bootstrap intervals that resample runs (a task and run seed share one memory), never single episodes. "
         "There is one confirmatory family per question: Q1 is notebook against starting fresh for each cheap model (2 tests, 97.5% intervals), Q3 is the four frontier-versus-cheap gaps (98.75% intervals), Q4 is the notebook-against-fresh drop in the no-catch control scenes for each cheap model (2 tests, 97.5% intervals). "
         "Everything else (Q2, replay, per-task rows, the catch-scene recovery, the pose-level runs) is exploratory and uses plain 95% intervals. "
         "Held-out episodes are the four evaluation layouts of each run, played with the memory frozen. 'Calls to success' charges a failed episode the whole call budget.", ""]

    # --- inventory
    inv = []
    for m in models:
        for t in TASKS:
            for c in ("none", "notebook", "replay"):
                for q in (True, False):
                    rs = A.select(skills, model=m, task=t, condition=c, quirk=q)
                    if rs:
                        inv.append((m, t, c, "catch" if q else "control", len(rs), sum(r["refusal"] or 0 for r in rs), f"${sum(r['cost_usd'] for r in rs):.2f}"))
    L += ["## 1. What was run", "", table(["model", "task", "memory", "scene", "episodes", "refusals", "cost"], inv), ""]
    cv = {}
    for c in cov:
        x = cv.setdefault((c["model"], c["toolset"], c["condition"], "catch" if c["quirk"] else "control"), [0, 0, 0, 0, 0])
        x[0] += 1
        x[1] += int(c["complete"])
        x[2] += c["planned"]
        x[3] += c["done"]
        x[4] += c["aborted"]
    cvr = [(m, tools, NAMES[cond], scene, x[0], x[1], f"{x[3]}/{x[2]}", x[4]) for (m, tools, cond, scene), x in sorted(cv.items())]
    L += ["Coverage. Only runs that finished their whole plan enter the confirmatory comparisons below. An abandoned attempt (provider failure, cut-off reply, failed notebook rewrite, budget stop) is redone on resume and its cost is kept:", "",
          table(["model", "tools", "memory", "scene", "runs started", "runs complete", "episodes finished/planned", "abandoned attempts"], cvr) if cvr else "No runs yet.", ""]
    by_dir = {}
    extra_cov = A.coverage(*ex(a.fixhold + a.fixcollide)) if ex(a.fixhold + a.fixcollide) else []
    for c in cov + ext_cov + extra_cov:
        by_dir.setdefault(c["dir"], {}).setdefault(c.get("code") or "unknown", 0)
        by_dir[c["dir"]][c.get("code") or "unknown"] += 1
    hashes = sorted({h for v in by_dir.values() for h in v})
    L += [(f"Code: every analysed run file carries the same code hash, `{hashes[0]}`." if len(hashes) == 1 else
           f"**Code: the run files carry {len(hashes)} different code hashes. Each exploratory cell that was added while the matrix ran has its own hash by design (PROTOCOL.md v1.4 to v1.5C, results/deviations.md deviation 2); the registered cells main, control, frontier and frontier_exp must share one. Read any comparison across hashes with that in mind.**"), "",
          table(["folder", "code hash (run files with it)"], [(d, ", ".join(f"`{h}` ({n})" for h, n in sorted(v.items()))) for d, v in sorted(by_dir.items())]), ""]
    not_done = [c for c in cov + ext_cov if not c["complete"] and c["planned"] > 4]
    L += [f"Runs with practice or a borrowed notebook that did not finish their whole plan are left out of every comparison (complete cases only, so a missing run is a missing pair, not a zero): {len(not_done)}"
          + (" (" + ", ".join(f"{c['dir']}/{c['file']} {c['done']}/{c['planned']}" for c in not_done[:8]) + (" ..." if len(not_done) > 8 else "") + ")" if not_done else "") + ".", ""]
    try:                                                 # planned run files that were never created (a cell that never started shows up here, not only in a smaller table)
        from robot_play.runner import build_specs
        cheap_m, front_m = ["claude-haiku-5-5", "gpt-6-luna"], ["claude-fable-5-2", "gpt-6-astra"]
        planned = [("main", cheap_m, range(10), "runs/main", {}), ("control", cheap_m, range(10), "runs/control", {}), ("frontier", front_m, [0], "runs/frontier", {}),
                   ("frontier_exp", ["claude-fable-5-2"], range(5), "runs/frontier_exp", {}), ("pose", cheap_m, range(3), "runs/pose", {}),
                   ("main", ["claude-haiku-5-5"], range(10, 20), "runs/main_ext", {"tasks": ["stack", "bins"]})]
        import inspect
        if "source_dir" in inspect.signature(build_specs).parameters:             # the borrowed cells live on the q5-borrowed branch until it is merged after the matrix
            for cell, d in (("borrowed", "runs/borrowed"), ("borrowed_other", "runs/borrowed_other"), ("borrowed_1", "runs/borrowed_1"), ("borrowed_3", "runs/borrowed_3")):
                planned.append((cell, cheap_m, range(10), d, {"source_dir": "runs/frontier_exp"}))      # planned only where the Fable notebook it reads finished
        missing = {}
        for cell, ms, seeds, d, kw in planned:
            if not Path(d).exists() and cell.startswith("borrowed"):
                continue                                 # an exploratory cell that was never launched is not a gap
            specs = build_specs(cell, ms, list(seeds), d, **kw)
            n_missing = sum(1 for sp in specs if not sp.path.exists())
            if n_missing:
                missing[f"{cell} ({d})"] = f"{n_missing} of {len(specs)} planned run files were never created"
        L += ["Planned cells that did not start (exploratory cells included; the borrowed cells are planned only where the Fable notebook they read finished): " + ("; ".join(f"{k}: {v}" for k, v in missing.items()) if missing else "none (every planned run file exists)."), ""]
    except Exception as e:                               # noqa: BLE001
        L += [f"**The planned-cell inventory failed ({type(e).__name__}: {e}); the list of cells that never started is missing from this report.**", ""]
    ab_total = sum(c["aborted_usd"] for c in cov)
    try:
        tot = SpendMeter(a.meter).totals()
        rec = SpendMeter(a.meter).reconcile()
        L += [f"Spend meter (pessimistic pricing): {json.dumps(tot)}. Ledger reconciles with the running totals: {rec['matches_state']}. Open reservations: {rec['open_reservations']}. "
              f"Dollars of abandoned attempts kept in the run files (already inside the meter totals): ${ab_total:.2f}.", ""]
    except Exception:                                    # noqa: BLE001
        pass

    # --- Q1
    L += ["## 2. Q1: does experience raise held-out success?", "",
          f"Confirmatory: the notebook against starting fresh, one test per cheap model, 97.5% intervals, pooled over the three jobs with resampling inside each job. Fewer than {MIN_Q1_PAIRS} complete (task, run seed) pairs of 30 is reported as inconclusive. "
          "Success here means finishing the job within the 20-call budget, so wherever the fresh agent already succeeds there is no room to gain and the benefit shows up as fewer calls (Q2) instead; the two questions measure the same improvement from two sides in the cells that have room.", ""]
    q1 = []
    for m in cheap:
        for c, primary in (("notebook", True), ("replay", False)):
            d = A.paired_difference(rows=skills, model=m, a=c, b="none", quirk=True, alpha=A.ALPHA_Q1 if primary else 0.05)
            dd = A.did(skills, m, c, "none")
            lab = NAMES[c] + ("" if primary else " (exploratory, 95%)")
            if primary and not enough(d, MIN_Q1_PAIRS):
                q1.append((m, lab, f(d.get("a"), True), f(d.get("b"), True), f"inconclusive: {d.get('n_pairs', 0)} complete pairs", "-"))
                continue
            q1.append((m, lab, f(d.get("a"), True), f(d.get("b"), True), ci(d, pct=True), ci(dd, "did", pct=True) if dd.get("n_control_pairs") else "no control yet"))
    L += [table(["model", "memory", "success with memory", "success starting fresh", "difference (paired by task and run)", "difference minus the same gain without a catch (95%, exploratory)"], q1), ""]
    per_task = []
    for m in cheap:
        for t in TASKS:
            d = A.paired_difference(skills, m, "notebook", "none", tasks=[t])
            per_task.append((m, t, f(d.get("a"), True), f(d.get("b"), True), ci(d, pct=True)))
    L += ["Per task, notebook against starting fresh (exploratory, 95%, only ten runs each, so the intervals are rough):", "", table(["model", "task", "notebook", "fresh", "difference"], per_task), ""]

    # --- tool-state artefacts (Fable's round 5a finding): false 'holding' and short moves, counted per cell, with sensitivity rows for Q1
    L += ["### 2a. A tool-state artefact in the Q1 cell, and how much it could matter", "",
          "In the skills cells a model can still call `move_to` and `close_gripper` by hand. When the fingertips rest on top of an object, `close_gripper` can answer `holding` although nothing is between the fingers "
          f"(it reads 'holding' with the hand nearly closed, under {A.FALSE_HOLD_WIDTH * 100:.0f} cm); `pick` then says `already holding` and `place` says `not holding anything`, and calls are wasted on a false statement. "
          f"A `move_to` can also answer ok while stopping more than {A.SHORT_MOVE * 100:.0f} cm from the request. Both come from the frozen simulator, which I will fix after the run (not mid-matrix). Counts of held-out catch-scene episodes with at least one such call:", ""]
    art = []
    for m in cheap:
        for t in TASKS:
            for c in ("none", "notebook", "replay"):
                x = A.select(skills, model=m, task=t, condition=c, phase="eval", quirk=True)
                if x:
                    fh = [r for r in x if r["false_hold"]]
                    art.append((m, t, NAMES[c], len(x), f"{len(fh)} ({sum(1 - r['success'] for r in fh)} failed)", sum(1 for r in x if r["short_move"])))
    L += [table(["model", "job", "memory", "held-out episodes", "with a false 'holding' (of which failed)", "with a short move_to"], art), ""]
    sens = []
    for m in cheap:
        for tl, tname in ((None, "all three jobs"), (["stack"], "stack only")):
            hit = lambda r: r["false_hold"] or r["short_move"]
            variants = (("as run", skills),
                        ("episodes with a false 'holding' dropped from every arm", [r for r in skills if not r["false_hold"]]),
                        ("episodes with a false 'holding' counted as successes in every arm", [dict(r, success=1) if (r["false_hold"] and r["phase"] == "eval") else r for r in skills]),
                        ("episodes with a false 'holding' OR a short move_to dropped from every arm", [r for r in skills if not hit(r)]),
                        ("extreme bound: episodes with a false 'holding' OR a short move_to counted as successes", [dict(r, success=1) if (hit(r) and r["phase"] == "eval") else r for r in skills]))
            for label, rs in variants:
                d = A.paired_difference(rs, m, "notebook", "none", tasks=tl)
                if d.get("n_pairs"):
                    sens.append((m, tname, label, f(d.get("a"), True), f(d.get("b"), True), ci(d, pct=True)))
    L += ["Q1 sensitivity (notebook against fresh, 95% intervals so the rows are comparable; exploratory). The false-`holding` rows bound only the episodes that contain a false `holding`; "
          "the root cause is wider (round 5b): a `move_to` after a failed `pick` is planned for an open hand although the hand is closed, lands on the cube and still answers ok, and the false `holding` follows when the model closes the hand. "
          "The last two rows therefore count every episode touched by either symptom, and the **extreme bound** assumes every one of them would otherwise have succeeded, which is not credible but is the limit of what the registered rows can say. "
          "Sections 6b and 6c rerun Haiku on `stack` on simulators with the symptom and then the cause fixed.", "",
          table(["model", "jobs", "treatment of the artefact episodes", "notebook", "fresh", "difference"], sens), ""]
    if cheap:
        fa = []
        for m in cheap:
            for c in ("none", "notebook", "replay"):
                x = [r for r in A.select(skills, model=m, task="stack", condition=c, phase="eval", quirk=True)]
                if x:
                    fails = [r for r in x if not r["success"]]
                    fa.append((m, NAMES[c], len(x), len(fails), sum(1 for r in fails if r["false_hold"] or r["short_move"])))
        L += ["Failed `stack` held-out episodes that contain a false `holding` or a short `move_to` (round 5b: 25 of 27 for Haiku with no memory on run seeds 0 to 9):", "",
              table(["model", "memory", "held-out episodes", "failed", "failed episodes with such a call"], fa), ""]

    # --- Q2
    L += ["## 3. Q2: does experience make it faster and cheaper? (exploratory, 95% intervals)", ""]
    q2 = []
    for m in cheap:
        for c in ("none", "notebook", "replay"):
            rs = A.select(skills, model=m, condition=c, phase="eval", quirk=True)
            if rs:
                d = A.paired_difference(skills, m, c, "none", metric="calls_to_success") if c != "none" else {}
                dc = A.did(skills, m, c, "none", metric="calls_to_success") if c != "none" else {}
                q2.append((m, NAMES[c], f"{mean(rs, 'calls_to_success'):.1f}", ci(d) if d.get("n_pairs") else "-", ci(dc, "did") if dc.get("n_control_pairs") else "-",
                           f"{mean(rs, 'sim_time_s'):.0f} s", f"${mean(rs, 'cost_usd'):.4f}", f"{A.per_success(skills, m, c, 'cost_usd'):.4f}"))
    L += [table(["model", "memory", "calls to success", "difference from fresh (calls)", "minus the same difference without a catch", "simulated seconds", "dollars per episode (evaluation only)", "dollars per success"], q2),
          "", "Dollars here are evaluation episodes only. The practice episodes and notebook rewrites that produced the memory are not in these columns; section 4 counts them for the cheap-versus-frontier comparison.", ""]
    wk = []
    for m in cheap:
        for c in ("none", "notebook", "replay"):
            w = A.within_k(skills, m, c)
            if not np.isnan(list(w.values())[0]):
                wk.append((m, NAMES[c]) + tuple(f(v, True) for v in w.values()))
    L += ["Share of held-out episodes that succeeded within k calls:", "", table(["model", "memory", "6", "8", "10", "12", "14", "16", "18", "20"], wk), ""]

    # --- Q3
    L += ["## 4. Q3: can a cheap model with experience come close to a frontier model's first try?", "",
          f"Confirmatory for the notebook rows (4 gaps, 98.75% intervals). The frontier models ran at reasoning effort `low`, like every model here, so this compares models at the same low setting, not at their best. Clusters are (task, run seed) runs, because the four layouts of a run share one notebook; the interval is the wider of the cluster bootstrap and an Agresti-Caffo interval "
          f"whose cheap-arm variance carries the design effect fixed in PROTOCOL.md (max(2, 1 + 3 x rho), rho measured on that cheap model's own notebook held-out outcomes; the frontier arm and the no-memory row have none). A cluster counts only when all four of its layouts are paired (a block that is only partly observed is left out and reported), so it does not shrink to zero when every episode succeeds. Fewer than {MIN_Q3_CLUSTERS} of 15 complete clusters is inconclusive. A frontier first try below {int(100 * FRONTIER_FLOOR)}% is not treated as a target. The rows with no memory show how much of the gap the notebook closes (exploratory, 95%).", ""]
    q3, q3c = [], []
    for fr in [m for m in models if m in ("claude-fable-5-2", "gpt-6-astra")]:
        for ch in cheap:
            for cc in ("notebook", "none"):
                g = A.q3_gap(skills, fr, ch, cheap_condition=cc, alpha=A.ALPHA_Q3 if cc == "notebook" else 0.05)
                if not g.get("n_layouts"):
                    if g.get("n_partial_clusters"):
                        q3.append((fr, f"{ch}, {NAMES[cc]}", f"0 whole runs ({g['n_partial_clusters']} partly paired)", "-", "-", "-", "inconclusive: no run has all four layouts paired"))
                    continue
                if cc == "notebook" and g["n_clusters"] < MIN_Q3_CLUSTERS:
                    verdict = f"inconclusive: {g['n_clusters']} complete clusters"
                elif g["frontier"] < FRONTIER_FLOOR:
                    verdict = "frontier too low to be a target"
                else:
                    verdict = ("yes" if g["within_margin"] else "not shown") + ("" if cc == "notebook" else " (exploratory)")
                q3.append((fr, f"{ch}, {NAMES[cc]}", f"{g['n_layouts']} in {g['n_clusters']} runs", f(g["frontier"], True), f(g["cheap"], True), ci(g, "gap", pct=True), verdict))
                if cc == "notebook":
                    c = A.q3_cost(skills, fr, ch, abandoned=abandoned)
                    if c:
                        q3c.append((fr, ch, f"${c['frontier_usd']:.2f}", f"${c['cheap_total_usd']:.2f}", f"${c['cheap_practice_usd']:.2f}", f"${c['cheap_eval_only_usd']:.2f}", f"${c['cheap_abandoned_usd']:.2f}"))
    L += [table(["frontier first try", "cheap model", "layouts", "frontier", "cheap model", "gap (frontier minus cheap)", "gap below +10 pp?"], q3) if q3 else "No frontier runs yet.", ""]
    if q3c:
        L += ["What each side cost on exactly those layouts (descriptive; the cheap side includes its 12 practice episodes, notebook rewrites, retries and abandoned attempts, the frontier side is first try only, so this is not a cost-matched claim):", "",
              table(["frontier", "cheap model", "frontier first try", "cheap model, everything", "of which practice and notebook", "of which evaluation", "of which abandoned attempts"], q3c), ""]
    fe = [(m, NAMES["notebook"], len(A.select(skills, model=m, condition="notebook", phase="eval", quirk=True)), f(mean(A.select(skills, model=m, condition="notebook", phase="eval", quirk=True), "success"), True),
           f(mean(A.select(skills, model=m, condition="none", phase="eval", quirk=True), "success"), True), f"${mean(A.select(skills, model=m, condition='notebook', phase='eval', quirk=True), 'cost_usd'):.3f}")
          for m in models if m in ("claude-fable-5-2", "gpt-6-astra") and A.select(skills, model=m, condition="notebook", phase="eval", quirk=True)]
    if fe:
        L += ["Frontier model with its own notebook (exploratory):", "", table(["model", "memory", "held-out episodes", "success with notebook", "success first try", "dollars per episode"], fe), ""]

    # --- Q4
    L += ["## 5. Q4: does experience help recovery from a disturbance?", "",
          f"Confirmatory measure: the **no-catch control scenes**, 97.5% intervals, one test per cheap model, inconclusive below {MIN_Q4_PAIRS} complete (task, run seed) pairs of 30. There both conditions solve the clean layouts about equally often, so the clean-to-disturbed drop is not floored by a failure that has nothing to do with the disturbance. "
          "The catch-scene results are exploratory: a condition that already fails the clean layout cannot drop. For those the table also gives the share of clean wins that survive the disturbance. "
          "A difference of drops is an association, not proof that the notebook taught recovery: the notebook was written from clean practice, so it can only help through general habits. The disturbance fired in every episode of the validation gate, and the tables show how often it fired here.", ""]
    for scene, quirk, primary in (("no-catch control scenes (confirmatory)", False, True), ("catch scenes (exploratory)", True, False)):
        q4, rd = [], []
        for m in cheap:
            for c in ("none", "notebook"):
                s_ = A.disturbance_summary(skills, m, c, quirk=quirk)
                if s_.get("n_disturbed"):
                    q4.append((m, NAMES[c], s_["n_disturbed"], f(s_["fire_rate"], True), f(s_["success_all_assigned"], True), f(s_["success_when_fired"], True), f(s_["success_same_layouts_clean"], True)))
            d = A.recovery_drop_difference(skills, m, "notebook", "none", quirk=quirk, alpha=A.ALPHA_Q4 if primary else 0.05)
            d2 = A.recovery_drop_difference(skills, m, "notebook", "none", both_fired_only=True, quirk=quirk, alpha=A.ALPHA_Q4 if primary else 0.05)
            cr = A.conditional_recovery(skills, m, "notebook", "none", quirk=quirk)
            if not d.get("n_pairs"):
                continue
            main_ci = ci(d, pct=True) if (not primary or enough(d, MIN_Q4_PAIRS)) else f"inconclusive: {d['n_pairs']} complete pairs"
            rd.append((m, f(d["drop_a"], True), f(d["drop_b"], True), main_ci, ci(d2, pct=True) if d2.get("n_pairs") else "n/a",
                       f"{f(cr.get('a'), True)} against {f(cr.get('b'), True)}" if cr.get("n_pairs") else "n/a"))
        L += [f"**{scene}**", "", table(["model", "memory", "disturbed episodes", "disturbance fired", "success, all assigned", "success when it fired", "same layouts, no disturbance"], q4) if q4 else "No disturbance runs yet.", ""]
        L += ["Drop in success caused by the disturbance (clean minus disturbed, same layouts, all assigned episodes). A negative difference means the notebook agent loses less:", "",
              table(["model", "drop with notebook", "drop starting fresh", "difference (all assigned" + (", primary)" if primary else ")"), "difference (fired for both, sensitivity)", "clean wins that survived (notebook against fresh)"], rd) if rd else "No complete disturbed runs yet.", ""]

    # --- exploratory extension: the cells with room at 20 run seeds
    if ext_rows:
        L += ["## 5a. Exploratory: the cells with room, Haiku on `stack` and `bins`, at 20 run seeds", "",
              "Registered before it ran (PROTOCOL.md section 10, v1.4): the pilots showed Haiku on these two jobs was the only cheap-model cell clearly below ceiling, so the `main` cell was repeated for run seeds 10 to 19. Plain 95% intervals; none of this enters a confirmatory number, which uses run seeds 0 to 9 only. "
              f"Runs complete: {sum(c['complete'] for c in ext_cov)} of {len(ext_cov)} started (60 planned).", ""]
        pooled = [r for r in rows if r["model"] == "claude-haiku-5-5" and r["task"] in ("stack", "bins") and r.get("toolset") in (None, "skills")] + ext_rows
        extr = []
        for task in ("stack", "bins", None):
            for cond in ("notebook", "replay"):
                tl = [task] if task else ["stack", "bins"]
                for label, rs in (("run seeds 10-19", ext_rows), ("run seeds 0-19, pooled", pooled)):
                    d = A.paired_difference(rs, "claude-haiku-5-5", cond, "none", tasks=tl)
                    if d.get("n_pairs"):
                        extr.append((task or "both jobs", NAMES[cond], label, d["n_pairs"], f(d.get("a"), True), f(d.get("b"), True), ci(d, pct=True)))
        L += [table(["job", "memory", "runs", "pairs", "with memory", "starts fresh", "difference"], extr) if extr else "No complete pairs yet.", ""]
        fa = []
        for task in ("stack", "bins"):
            for cond in ("none", "notebook", "replay"):
                x = A.select(pooled, model="claude-haiku-5-5", task=task, condition=cond, phase="eval", quirk=True)
                if x:
                    fh = [r for r in x if r["false_hold"]]
                    fa.append((task, NAMES[cond], len(x), f"{len(fh)} ({sum(1 - r['success'] for r in fh)} failed)"))
        L += ["The false-`holding` artefact of section 2a in the same 20 run seeds (held-out episodes with at least one such call):", "", table(["job", "memory", "held-out episodes", "with a false 'holding' (of which failed)"], fa), ""]

    # --- Q5: a stronger model's notebook (exploratory)
    bor = [r for r in skills if r["condition"] in ("borrowed", "borrowed_other")]
    if bor:
        seeds5 = sorted({r["run_seed"] for r in bor})
        L += ["## 6. Exploratory: does a stronger model's notebook help a cheaper one?", "",
              f"Each cheap model reads, frozen and with no practice of its own, the notebook that the Fable-with-notebook run of the same task and run seed ended with, and plays the same four held-out layouts (run seeds {seeds5[0]} to {seeds5[-1]}, three jobs). "
              "Exploratory throughout, plain 95% intervals. The control `reads Fable's notebook for another job` gives each job the notebook written for a different job. "
              "Four things limit what the numbers can say: **(1)** the arms introduce their notebook differently ('written by a more capable assistant after it practised this same task', 'written by you', and for the control 'a DIFFERENT task ... may or may not apply'), "
              "so borrowed against the control shows that the content matters, and borrowed against the model's own notebook cannot show that Fable's notes are better than its own. "
              "**(2)** The replication on run seeds 5 to 9 was decided after the first five were seen. "
              "**(3)** Fable writes its notebook after solving every practice episode, so this is a working recipe from a strong model, not experience gathered from failures. "
              "**(4)** One frontier writer and two cheap models.", ""]
        q5 = []
        halves = (("run seeds 0-4", [r for r in skills if r["run_seed"] <= 4]), ("run seeds 5-9 (replication)", [r for r in skills if r["run_seed"] >= 5]), ("run seeds 0-9, pooled", skills))
        for m in cheap:
            for first, other in (("borrowed", "none"), ("borrowed", "notebook"), ("borrowed", "replay"), ("borrowed", "borrowed_other"), ("borrowed_other", "none")):
                for label, rs in halves:
                    d = A.paired_difference(rs, m, first, other)
                    if d.get("n_pairs"):
                        q5.append((m, f"{NAMES[first]} against {NAMES[other]}", label, d["n_pairs"], f(d.get("a"), True), f(d.get("b"), True), ci(d, pct=True)))
        L += ["Success on held-out layouts, paired by (task, run seed) with the runs each pair has in common (the column 'pairs' is that count):", "",
              table(["model", "comparison", "runs", "pairs (task, run seed)", "first", "second", "difference"], q5) if q5 else "No complete comparison yet.", ""]
        L += ["Calls to success (a failure is charged the whole budget); a negative difference means the first arm needs fewer calls:", ""]
        cs = []
        for m in cheap:
            for first, other in (("borrowed", "notebook"), ("borrowed", "none"), ("borrowed", "replay")):
                d = A.paired_difference(skills, m, first, other, metric="calls_to_success")
                if d.get("n_pairs"):
                    cs.append((m, f"{NAMES[first]} against {NAMES[other]}", d["n_pairs"], f"{d['a']:.1f}", f"{d['b']:.1f}", ci(d)))
        L += [table(["model", "comparison", "pairs", "first", "second", "difference in calls to success"], cs) if cs else "No pairs yet.", ""]
        mt, pj = [], []
        for m in cheap:
            conds = [c for c in ("none", "notebook", "replay", "borrowed", "borrowed_other") if A.select(skills, model=m, condition=c, phase="eval", quirk=True)]
            keys = None
            for c in ("none", "notebook", "borrowed", "borrowed_other"):
                kc = {(r["task"], r["run_seed"]) for r in A.select(skills, model=m, condition=c, phase="eval", quirk=True)}
                keys = kc if keys is None else keys & kc
            keys = keys or set()
            for c in conds:
                x = [r for r in A.select(skills, model=m, condition=c, phase="eval", quirk=True) if (r["task"], r["run_seed"]) in keys]
                if x:
                    mt.append((m, NAMES[c], len({(r["task"], r["run_seed"]) for r in x}), len(x), f(mean(x, "success"), True), f"{mean(x, 'calls'):.1f}", f"{mean(x, 'calls_to_success'):.1f}", f"${mean(x, 'cost_usd'):.4f}"))
                for t in TASKS:
                    y = [r for r in x if r["task"] == t]
                    if y:
                        pj.append((m, t, NAMES[c], len(y), f"{sum(r['success'] for r in y)}/{len(y)}"))
        L += ["Held-out episodes on exactly the runs that start, no memory, notebook, borrowed and wrong-task arms all have (same runs in every row of a model):", "",
              table(["model", "memory", "runs", "episodes", "success", "mean calls", "calls to success", "dollars per episode"], mt), ""]
        L += ["**The same, per job.** Most of the pooled effect is one cell; read the pooled rows with this table beside them:", "", table(["model", "job", "memory", "episodes", "solved"], pj), ""]
        gaps = []
        for fr in [m for m in models if m in ("claude-fable-5-2", "gpt-6-astra")]:
            for ch in cheap:
                g = A.q3_gap(skills, fr, ch, cheap_condition="borrowed", alpha=0.05)
                if g.get("n_layouts"):
                    gaps.append((fr, ch, f"{g['n_layouts']} in {g['n_clusters']} runs", f(g["frontier"], True), f(g["cheap"], True), ci(g, "gap", pct=True)))
        if gaps:
            L += ["Frontier first try against a cheap model that only reads Fable's notebook, on the same layouts (exploratory, same interval rule as Q3 at 95%; the cheap arm carries the design effect because the four layouts of a run share one notebook):", "",
                  table(["frontier first try", "cheap model with Fable's notebook", "layouts", "frontier", "cheap", "gap (frontier minus cheap)"], gaps), ""]
        # cost: practice only on both sides (cost_usd already contains retries; evaluation episodes are not part of making a notebook)
        ks = {(r["task"], r["run_seed"]) for r in bor if r["condition"] == "borrowed"}
        fprac, ffirst = {}, {}
        for r in skills:
            if r["model"] == "claude-fable-5-2" and r["condition"] == "notebook" and r["phase"] == "practice" and (r["task"], r["run_seed"]) in ks:
                k = (r["task"], r["run_seed"])
                fprac[k] = fprac.get(k, 0.0) + r["cost_usd"]
                if r["idx"] == 0:
                    ffirst[k] = r["cost_usd"]
        ftry = A.select(skills, model="claude-fable-5-2", condition="none", phase="eval", quirk=True)
        if fprac:
            fp, f1 = float(np.mean(list(fprac.values()))), float(np.mean(list(ffirst.values()))) if ffirst else float("nan")
            fr_ep = mean(ftry, "cost_usd")
            cr = []
            for m in cheap:
                own = {}
                for r in skills:
                    if r["model"] == m and r["condition"] == "notebook" and r["phase"] == "practice" and (r["task"], r["run_seed"]) in ks:
                        own[(r["task"], r["run_seed"])] = own.get((r["task"], r["run_seed"]), 0.0) + r["cost_usd"]
                op = float(np.mean(list(own.values()))) if own else float("nan")
                ev = lambda c: mean([r for r in A.select(skills, model=m, condition=c, phase="eval", quirk=True) if (r["task"], r["run_seed"]) in ks], "cost_usd")
                own_ep, bor_ep = ev("notebook"), ev("borrowed")
                be_f = f"{fp / (fr_ep - bor_ep):,.0f} episodes" if fr_ep > bor_ep else "never"
                be_o = f"{(fp - op) / (own_ep - bor_ep):,.0f} episodes" if own_ep > bor_ep else "never (not cheaper per episode)"
                cr.append((m, f"${fp:.2f}", f"${f1:.2f}", f"${op:.3f}", f"${fr_ep:.4f}", f"${own_ep:.4f}", f"${bor_ep:.4f}", be_f, be_o))
            L += ["**What the notebook costs, practice only on both sides** (evaluation episodes are not part of making a notebook; retries are inside the dollar figures once). Fable's 12 practice episodes and rewrites against the cheap model's own 12, and the number of episodes of the same job after which the one-off cost is repaid:", "",
                  table(["cheap model", "Fable notebook, per run", "of which practice episode 1 and its rewrite", "cheap model's own notebook, per run", "Fable first try, per episode", "cheap model with own notebook, per episode", "cheap model with Fable's notebook, per episode", "repaid against running Fable directly after", "repaid against the cheap model's own notebook after"], cr), "",
                  "`results/notebook_audit.md` counts in how many Fable runs the notebook already names the fixing setting after practice episode 1 (a keyword check, outcome-informed, see there); Fable also never failed a practice episode, so a one-episode notebook might cost about the 'practice episode 1' column. That was not tested: it is a guess, not a result. "
                  "The comparison assumes the notebook is reused for the same job, and Fable's notebook is a one-off cost that a deployment would pay once per job, not per run.", ""]

    # --- Q5b: how short can the expensive practice be? (v1.5, exploratory)
    short = [r for r in skills if r["condition"] in ("borrowed_1", "borrowed_3")]
    if short:
        L += ["## 6a. Exploratory: how short can the expensive practice be?", "",
              "Registered before it ran (PROTOCOL.md v1.5). The same borrowed cell, but each cheap model reads Fable's notebook as it stood after **1** or **3** practice episodes instead of 12, for the same finished Fable runs. "
              "Prediction written beforehand: Haiku on `stack` solves at least 90% of held-out layouts with the one-episode notebook. Plain 95% intervals, paired by (task, run seed).", ""]
        sh = []
        for m in cheap:
            for first, other in (("borrowed_1", "none"), ("borrowed_3", "none"), ("borrowed_1", "borrowed"), ("borrowed_3", "borrowed")):
                d = A.paired_difference(skills, m, first, other)
                dc = A.paired_difference(skills, m, first, other, metric="calls_to_success")
                if d.get("n_pairs"):
                    sh.append((m, f"{NAMES[first]} against {NAMES[other]}", d["n_pairs"], f(d.get("a"), True), f(d.get("b"), True), ci(d, pct=True), ci(dc)))
        L += [table(["model", "comparison", "pairs", "first", "second", "success difference", "calls-to-success difference"], sh), ""]
        sj = []
        for m in cheap:
            keys = None
            for c in ("none", "borrowed", "borrowed_1", "borrowed_3"):
                kc = {(r["task"], r["run_seed"]) for r in A.select(skills, model=m, condition=c, phase="eval", quirk=True)}
                if kc:                                   # an arm that has not produced any complete run yet does not empty the table
                    keys = kc if keys is None else keys & kc
            for c in ("none", "borrowed_1", "borrowed_3", "borrowed"):
                for t in TASKS:
                    y = [r for r in A.select(skills, model=m, condition=c, phase="eval", quirk=True, task=t) if (r["task"], r["run_seed"]) in (keys or set())]
                    if y:
                        sj.append((m, t, NAMES[c], len(y), f"{sum(r['success'] for r in y)}/{len(y)}", f"{mean(y, 'calls_to_success'):.1f}"))
        L += ["Per job, on exactly the runs that every arm in this table has:", "", table(["model", "job", "memory", "episodes", "solved", "calls to success"], sj), ""]
        cum = {1: [], 3: [], 12: []}
        for k in (1, 3, 12):
            by = {}
            for r in skills:
                if r["model"] == "claude-fable-5-2" and r["condition"] == "notebook" and r["phase"] == "practice" and r["idx"] < k:
                    by[(r["task"], r["run_seed"])] = by.get((r["task"], r["run_seed"]), 0.0) + r["cost_usd"]
            cum[k] = list(by.values())
        L += ["What the Fable practice behind each notebook cost (mean per run, practice episodes and rewrites only): " + ", ".join(f"{k} episode{'s' if k > 1 else ''}: ${np.mean(v):.2f}" for k, v in cum.items() if v) + ".", ""]

    # --- 6b/6c: Haiku on stack on three simulators (v1.5B, v1.5C; exploratory)
    fix_rows = A.load(*ex(a.fixhold), complete_only=True) if ex(a.fixhold) else []
    col_rows = A.load(*ex(a.fixcollide), complete_only=True) if ex(a.fixcollide) else []
    if fix_rows or col_rows:
        L += ["## 6b. Exploratory: Haiku on `stack` on three simulators", "",
              "Registered before they ran (PROTOCOL.md v1.5B and v1.5C). The same layouts (run seeds 0 to 9) and the same disturbed evaluation in all three rows. "
              "**Registered simulator:** the matrix as run. **Symptom fixed:** `close_gripper` attaches an object only if the hand is at least as wide as the object's narrowest side minus 8 mm (v1.5B); this removes the false sentence but keeps its cause, so short `move_to` stops remain (the last column). "
              "**Cause fixed too:** a plain `move_to` is planned with the finger opening the hand really has, so a closed hand gets an honest refusal instead of landing on the cube and answering ok (v1.5C). Each has its own code hash (section 1). "
              "Predictions written before the last one ran: notebook at or above 95%; no memory between 30% and 75%, a gain of at least +20 points; no memory at 85% or more would shrink the headline to a small effect. Plain 95% intervals.", ""]
        orig = [r for r in skills if r["model"] == "claude-haiku-5-5" and r["task"] == "stack"]
        fx, cmp_ = [], []
        sims = (("registered simulator", orig), ("symptom fixed (v1.5B)", fix_rows), ("cause fixed too (v1.5C)", col_rows))
        for label, rs in sims:
            for c in ("none", "notebook"):
                x = A.select(rs, model="claude-haiku-5-5", task="stack", condition=c, phase="eval", quirk=True)
                if x:
                    fx.append((label, NAMES[c], len({r["run_seed"] for r in x}), len(x), f"{sum(r['success'] for r in x)}/{len(x)} ({f(mean(x, 'success'), True)})", f"{mean(x, 'calls_to_success'):.1f}",
                               sum(1 for r in x if r["false_hold"]), sum(1 for r in x if r["short_move"])))
            d = A.paired_difference(rs, "claude-haiku-5-5", "notebook", "none")
            dc = A.paired_difference(rs, "claude-haiku-5-5", "notebook", "none", metric="calls_to_success")
            if d.get("n_pairs"):
                cmp_.append((label, d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True), ci(dc)))
        L += [table(["simulator", "memory", "runs", "held-out episodes", "solved", "calls to success", "episodes with a false 'holding'", "episodes with a short move_to"], fx), "",
              "Notebook against no memory on the same ten run seeds, per simulator (a run needs both arms complete):", "",
              table(["simulator", "pairs", "notebook", "no memory", "success difference", "calls-to-success difference"], cmp_), ""]

    # --- pose
    if pose:
        L += ["## 7. Skill-level against pose-level tools", "", "Pose-level runs have no `pick` or `place`: the model builds them from `move_to` and the gripper, with three times the call budget.", ""]
        pr = []
        for m in sorted({r["model"] for r in pose}):
            for tools, rs in (("skills", skills), ("pose", pose)):
                for c in ("none", "notebook"):
                    x = A.select(rs, model=m, condition=c, phase="eval", quirk=True)
                    if x:
                        pr.append((m, tools, NAMES[c], len(x), f(mean(x, "success"), True), f"{mean(x, 'calls'):.1f}", f"${mean(x, 'cost_usd'):.4f}"))
        L += [table(["model", "tools", "memory", "episodes", "held-out success", "calls", "dollars per episode"], pr), "",
              "The skills rows above use all ten run seeds; the interaction below uses only run seeds 0 to 2, the seeds the pose cell has, so both toolsets see the same layouts. Exploratory, 95%, three runs per task is few.", ""]
        for m in sorted({r["model"] for r in pose}):
            d = A.paired_difference(pose, m, "notebook", "none")
            L += [f"{m}, pose-level tools, notebook against fresh: {ci(d, pct=True)}", ""]
            sk3 = [r for r in skills if r["run_seed"] in (0, 1, 2)]
            ti = A.tool_interaction(sk3, pose, m)
            if ti.get("n_pairs"):
                L += [f"{m}, notebook gain with pose tools ({f(ti['gain_pose'], True)}) minus the gain with skill tools ({f(ti['gain_skills'], True)}) on the same {ti['n_pairs']} runs: {ci(ti, 'diff', pct=True)}", ""]

    # --- honesty about claims
    fc = []
    for m in cheap:
        x = A.select(skills, model=m, phase="eval", quirk=True)
        if x:
            fc.append((m, len(x), f(mean(x, "claimed_done"), True), f(sum(r["false_claim"] for r in x) / len(x), True)))
    L += ["## 8. Saying 'done' when the job is not done", "", table(["model", "held-out episodes", "said done", "said done but the simulator disagreed"], fc), ""]

    dev = ROOT / "results/deviations.md"
    L += ["## 9. Deviations from the protocol", "", dev.read_text() if dev.exists() else "None recorded.", ""]
    Path(a.out).write_text("\n".join(L))
    Path(a.img).mkdir(parents=True, exist_ok=True)
    if cheap and any(r["phase"] == "practice" for r in skills):
        learning_chart([r for r in skills if r["quirk"]], cheap, Path(a.img) / "learning_curves.png")
    print("\n".join(L)[:3000])


if __name__ == "__main__":
    main()

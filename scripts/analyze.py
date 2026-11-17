"""Turn the run files into results/RESULTS.md and the learning-curve charts. Every number in the README comes from here.

  python scripts/analyze.py --main runs/main --control runs/control --frontier runs/frontier runs/frontier_exp --pose runs/pose

Tests and intervals are the ones fixed in PROTOCOL.md section 1: cluster bootstrap over runs (never single episodes or single layouts), complete runs only,
Bonferroni-adjusted intervals for the confirmatory family (Q1, Q3, Q4) and unadjusted 95% intervals (the project's interval rule, no multiplicity correction), labelled exploratory, for everything else.
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
LM_HASH = "58b19ca1be3740fe"        # code hash of tag code-labelmatch (PROTOCOL.md v1.9)
WS_HASH = "0346eddace878d63"        # code hash of tag code-wordsplit (PROTOCOL.md v1.10)
WS2_HASH = "c44187af32043997"       # code hash of tag code-wordsplit2 (PROTOCOL.md v1.11)
DOSE_HASH = "33db266fef842900"      # code hash of tag code-dose (PROTOCOL.md v1.12)
SEC_HASH = "216aab61b6c8b09e"       # code hash of tag code-second (PROTOCOL.md v1.13)
BUD_HASH = "a047eaf9c4a9c258"       # code hash of tag code-budget (PROTOCOL.md v1.14)
MIX_HASH = "6119571baae3816f"       # code hash of tag code-mixed (PROTOCOL.md v1.15)
NAMES = {"none": "starts fresh", "notebook": "keeps a notebook", "replay": "sees its last success", "borrowed": "reads Fable's notebook", "borrowed_other": "reads Fable's notebook for another job",
         "borrowed_1": "reads Fable's notebook after 1 practice episode", "borrowed_3": "reads Fable's notebook after 3 practice episodes",
         "hint": "reads a one-sentence hint naming the fix", "hint_generic": "reads a generic tip (lists the four adjustable settings, names no fix)", "prior": "reads Fable's notebook written with no practice"}


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


def void_if(bad, pr):
    """Registered rule: a prediction table is void when any included file fails validation (hash or run seed)."""
    return [(a_, b_, "void (a file failed validation)") for a_, b_, _ in pr] if bad else pr


def bad_cov(cov, hashes, lo=20, hi=29):
    """Files that fail the registered validation: a code hash that is not one of `hashes`, or a run seed that is missing or outside lo to hi (no default is assumed)."""
    return [c for c in cov if c.get("code") not in hashes or not isinstance(c.get("run_seed"), int) or not lo <= c["run_seed"] <= hi]


def mean(rows, key):
    return float(np.mean([r[key] for r in rows])) if rows else float("nan")


def registered_solved(r):
    """PROTOCOL.md v1.14: an episode that never calls `done` within the stated budget is a failure, whatever the simulator says at the end."""
    return int(bool(r["success"]) and bool(r["claimed_done"]))


def reading_mixed(st):
    """Registered reading of PROTOCOL.md v1.15 from the statuses of M1 to M6 (each starts with 'met', 'MISSED' or 'not read')."""
    ok = [x.startswith("met") for x in st]
    if all(ok):
        return "M1 to M6 all met: where no single setting works, a note that states the fix is worthless or harmful and only a stated procedure (or practice that finds it) carries the benefit, which is the two-sided version of the main finding."
    names = {0: "M1 missed: a model recovers from a wrong rule by reading the error, so a rule is not harmful for it",
             1: "M2 missed: no room for that model (its M3 to M5 are reported but not read)",
             2: "M3 missed: even the answer key does not teach a procedure through one sentence",
             3: "M4 missed: practice does not discover a two-sided rule at this dose, or the notebook beat the answer key (see the table, the upper-bound reading is void in the second case)",
             4: "M5 missed: the sentence has a cost on ordinary cubes (size in the table)",
             5: "M6 missed: the names list is as good as the procedure here"}
    return "; ".join(names[i] for i, o in enumerate(ok) if not o) + "."


def reading_budget(st):
    """Registered reading of PROTOCOL.md v1.14 from the statuses of B1, B2 and B3 (each starts with 'met' or 'MISSED'; a MISSED status may say which model missed in parentheses)."""
    m_ = [x.startswith("met") for x in st]
    if all(m_):
        return "B1, B2 and B3 met: under a stated budget a list of settings is enough where the catch is a choice among named values, and not where the model has to find a number (a grasp height, a release height), so the notebook's value is the stored value."
    parts = []
    if not m_[0]:
        parts.append("B1 missed: the list does not match the notebook even on `stack` at this budget")
    for nm, ok, st_ in (("B2 (`flasks`)", m_[1], st[1]), ("B3 (`bins`)", m_[2], st[2])):
        if not ok:
            who = st_.split("(")[1].split(")")[0] if "(" in st_ else "a model"
            parts.append(f"{nm} missed ({who}): the notebook's efficiency advantage is not confirmed for that job and model")
    return "; ".join(parts) + "."


def reading_second(st, gate_failed):
    """Registered reading of PROTOCOL.md v1.13 from the statuses [gate, Q1, Q2, Q3, Q4]; Q4 is reported either way. The registered text does not cover Q1 met with Q2 or Q3 missed."""
    if gate_failed:
        return "the gate failed, so there was no room for a second model and nothing below is scored; the ceiling is reported."
    m = [x.startswith("met") for x in st]
    if not m[0]:
        return "the gate failed, so there was no room and no reading."
    if m[1] and m[2] and m[3]:
        return "the Haiku pattern also holds for a second, more capable model (the list reproduces the generic sentence, the frame alone does little)."
    if not m[1]:
        return "the names result is Haiku-specific on these layouts (Q1 missed)."
    return "the registered reading does not cover this combination (Q1 met with Q2 or Q3 missed)."


EPS = 1e-9


def at_least(x, t):
    """Registered threshold 'at least t', immune to float noise (a mean of 26 successes in 40 must count as exactly 0.65)."""
    return x >= t - EPS


def at_most(x, t):
    return x <= t + EPS


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
                ax.fill_between(x, [max(0.0, 100 * (p["lo"] if p["lo"] == p["lo"] else p["mean"])) for p in cur], [min(100.0, 100 * (p["hi"] if p["hi"] == p["hi"] else p["mean"])) for p in cur], color=COLORS[c], alpha=0.15, lw=0)
            ax.set_title(f"{m}: {t}", loc="left", fontsize=11, color=INK)
            ax.set_ylim(-3, 103)
            ax.grid(axis="y", color=GRID, lw=0.8)
            ax.set_xlabel("practice attempt")
            for s in ("top", "right", "left"):
                ax.spines[s].set_visible(False)
            ax.tick_params(length=0)
    axes[0][0].set_ylabel("attempts that finish the job (%)")
    axes[0][0].legend(frameon=False, fontsize=9, loc="lower right")
    fig.suptitle("Success on each practice attempt, averaged over runs (band: 95% cluster-bootstrap interval, clipped to 0-100%)", x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
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
    ap.add_argument("--rep", nargs="*", default=["runs/rep_fixed"], help="exploratory replication of the registered Q1 comparison on the corrected simulator, run seeds 20-29 (PROTOCOL.md v1.6); never pooled with the registered rows")
    ap.add_argument("--hint", nargs="*", default=["runs/hint", "runs/hint_generic", "runs/prior"], help="exploratory controls of PROTOCOL.md v1.7: one-sentence hint, generic hint, zero-practice Fable notebook (run seeds 20-29, no practice)")
    ap.add_argument("--prior-notebooks", default="runs/prior_notebooks")
    ap.add_argument("--labelmatch", nargs="*", default=["runs/labelmatch"], help="exploratory label-matched text control (PROTOCOL.md v1.9): one neutral label over an inert, a generic and a naming sentence, run seeds 20-29, no practice")
    ap.add_argument("--wordsplit", nargs="*", default=["runs/wordsplit"], help="exploratory split of the generic sentence (PROTOCOL.md v1.10): frame only, frame + names, frame + instruction under the neutral label; Haiku, stack, run seeds 20-29, no practice")
    ap.add_argument("--wordsplit2", nargs="*", default=["runs/wordsplit2"], help="exploratory repeat of the split on fresh layouts (PROTOCOL.md v1.11): Haiku, stack, run seeds 30-39, eight arms")
    ap.add_argument("--dose", nargs="*", default=["runs/dose"], help="exploratory practice-dose cell (PROTOCOL.md v1.12): Haiku, stack, own notebook after 1, 3, 6 (and 12 on run seeds 30-39) practice episodes")
    ap.add_argument("--second", nargs="*", default=["runs/second"], help="exploratory second model (PROTOCOL.md v1.13): Claude Sonnet 5.5 on stack, run seeds 30-39, room check then four split arms")
    ap.add_argument("--budget", nargs="*", default=["runs/budget"], help="exploratory stated-budget cell (PROTOCOL.md v1.14): Haiku and Luna, three jobs, run seeds 30-39, 12 calls stated to the model")
    ap.add_argument("--mixed", nargs="*", default=["runs/mixed"], help="exploratory two-sided job (PROTOCOL.md v1.15): Haiku and Luna, job mixed, run seeds 40-49, six arms plus a control scene")
    ap.add_argument("--writer", nargs="*", default=["runs/writer_sonnet"], help="exploratory second writer (PROTOCOL.md v1.8): Claude Sonnet 5.5 with its own notebook, run seeds 20-29 (stack) and 20-24 (bins, flasks)")
    ap.add_argument("--borrowed-sonnet", nargs="*", default=["runs/borrowed_sonnet"], help="cheap models reading the Sonnet notebooks with no practice (PROTOCOL.md v1.8)")
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
         "Everything else (Q2, replay, per-task rows, the catch-scene recovery, the pose-level runs) is exploratory and uses unadjusted 95% intervals (the project's interval rule, no multiplicity correction). "
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
    extra_cov = A.coverage(*ex(a.fixhold + a.fixcollide + a.rep + a.hint)) if ex(a.fixhold + a.fixcollide + a.rep + a.hint) else []
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
        planned += [("main", ["claude-haiku-5-5"], range(10), "runs/main_fixhold", {"tasks": ["stack"], "only": ("none", "notebook")}),
                    ("main", ["claude-haiku-5-5"], range(10), "runs/main_fixcollide", {"tasks": ["stack"], "only": ("none", "notebook")}),
                    ("main", cheap_m, range(20, 30), "runs/rep_fixed", {"only": ("none", "notebook")})]
        import inspect as _inspect
        if "source_dir" in _inspect.signature(build_specs).parameters:
            planned += [(c, cheap_m, range(20, 30), f"runs/{c}", {"source_dir": a.prior_notebooks}) for c in ("hint", "hint_generic", "prior")] if all(Path(f"runs/{c}").exists() for c in ("hint", "hint_generic", "prior")) else []
        for cell, ms, seeds, d, kw in planned:
            kw = dict(kw)
            only = kw.pop("only", None)
            if only and not Path(d).exists():
                continue                                 # an exploratory rerun that was never launched is not a gap
            if not Path(d).exists() and cell.startswith("borrowed"):
                continue                                 # an exploratory cell that was never launched is not a gap
            specs = build_specs(cell, ms, list(seeds), d, **kw)
            if only:
                specs = [sp for sp in specs if sp.condition in only]
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
          "The last two rows therefore count every episode touched by either symptom, and the **extreme bound** assumes every one of them would otherwise have succeeded, which is not credible but is the limit of what the registered rows can say; **the cause-fixed rerun of section 6b contradicts it** (no memory reached 42%, not about 95%). "
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
                q3.append((fr, f"{ch}, {NAMES[cc]}", f"{g['n_layouts']} in {g['n_clusters']} runs" + (f" ({g['n_partial_clusters']} partly paired runs left out)" if g.get("n_partial_clusters") else ""), f(g["frontier"], True), f(g["cheap"], True), ci(g, "gap", pct=True), verdict))
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
              "Registered before it ran (PROTOCOL.md section 10, v1.4): the pilots showed Haiku on these two jobs was the only cheap-model cell clearly below ceiling, so the `main` cell was repeated for run seeds 10 to 19. Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction); none of this enters a confirmatory number, which uses run seeds 0 to 9 only. "
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
              "Exploratory throughout, unadjusted 95% intervals (the project's interval rule, no multiplicity correction). The control `reads Fable's notebook for another job` gives each job the notebook written for a different job. "
              "Four things limit what the numbers can say: **(1)** the arms introduce their notebook differently ('written by a more capable assistant after it practised this same task', 'written by you', and for the control 'a DIFFERENT task ... may or may not apply'), "
              "so borrowed against the control is suggestive that the content matters (it changes the instruction as well as the content, so it does not isolate content), and borrowed against the model's own notebook cannot show that Fable's notes are better than its own. "
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
            conds = [c for c in ("none", "notebook", "borrowed", "borrowed_other") if A.select(skills, model=m, condition=c, phase="eval", quirk=True)]          # replay exists only for stack and sort, so it has its own rows in the comparison table above
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
        for k in list(fprac):
            fprac[k] += abandoned.get(("claude-fable-5-2", "skills", k[0], "notebook", True, k[1]), 0.0)          # attempts abandoned and redone (provider failure, cut-off reply) are part of what the notebook cost
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
                for k in list(own):
                    own[k] += abandoned.get((m, "skills", k[0], "notebook", True, k[1]), 0.0)
                op = float(np.mean(list(own.values()))) if own else float("nan")
                ev = lambda c: mean([r for r in A.select(skills, model=m, condition=c, phase="eval", quirk=True) if (r["task"], r["run_seed"]) in ks], "cost_usd")
                own_ep, bor_ep = ev("notebook"), ev("borrowed")
                be_f = f"{fp / (fr_ep - bor_ep):,.0f} episodes" if fr_ep > bor_ep else "never"
                be_o = ("never (not cheaper per episode)" if own_ep <= bor_ep else
                        (f"{(fp - op) / (own_ep - bor_ep):,.0f} episodes" if (fp - op) / (own_ep - bor_ep) < 100_000 else "effectively never (over 100,000 episodes)"))
                cr.append((m, f"${fp:.2f}", f"${f1:.2f}", f"${op:.3f}", f"${fr_ep:.4f}", f"${own_ep:.4f}", f"${bor_ep:.4f}", be_f, be_o))
            L += ["**What the notebook costs, practice only on both sides** (evaluation episodes are not part of making a notebook; retries are inside the dollar figures once; the dollars of attempts that were abandoned and redone are added; the few cents of run files deleted in deviation 2 cannot be allocated and are not included). Fable's 12 practice episodes and rewrites against the cheap model's own 12, and the number of episodes of the same job after which the one-off cost is repaid:", "",
                  table(["cheap model", "Fable notebook, per run", "of which practice episode 1 and its rewrite", "cheap model's own notebook, per run", "Fable first try, per episode", "cheap model with own notebook, per episode", "cheap model with Fable's notebook, per episode", "repaid against running Fable directly after", "repaid against the cheap model's own notebook after"], cr), "",
                  "`results/notebook_audit.md` counts in how many Fable runs the notebook already names the fixing setting after practice episode 1 (a keyword check, outcome-informed, see there); Fable also never failed a practice episode, so a one-episode notebook costs about the 'practice episode 1' column; section 6a tests exactly that (the cheap models read Fable's notebook as it stood after one practice episode) on the same finished runs. "
                  "The comparison assumes the notebook is reused for the same job, and Fable's notebook is a one-off cost that a deployment would pay once per job, not per run.", ""]

    # --- Q5b: how short can the expensive practice be? (v1.5, exploratory)
    short = [r for r in skills if r["condition"] in ("borrowed_1", "borrowed_3")]
    if short:
        L += ["## 6a. Exploratory: how short can the expensive practice be?", "",
              "Registered before it ran (PROTOCOL.md v1.5). The same borrowed cell, but each cheap model reads Fable's notebook as it stood after **1** or **3** practice episodes instead of 12, for the same finished Fable runs. "
              "Prediction written beforehand: Haiku on `stack` solves at least 90% of held-out layouts with the one-episode notebook. Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction), paired by (task, run seed).", ""]
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
              "Predictions written before the last one ran: notebook at or above 95%; no memory between 30% and 75%, a gain of at least +20 points; no memory at 85% or more would shrink the headline to a small effect. Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction).", ""]
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
        dist_rows = []
        for label, rs in sims:
            for c in ("none", "notebook"):
                x = A.select(rs, model="claude-haiku-5-5", task="stack", condition=c, phase="eval_disturbed", quirk=True)
                if x:
                    dist_rows.append((label, NAMES[c], len(x), f"{sum(r['success'] for r in x)}/{len(x)} ({f(mean(x, 'success'), True)})"))
        gaps = {}
        for label, rs in sims:
            ma = A._run_means(A.select(rs, model="claude-haiku-5-5", task="stack", condition="notebook", phase="eval", quirk=True), "success")
            mb = A._run_means(A.select(rs, model="claude-haiku-5-5", task="stack", condition="none", phase="eval", quirk=True), "success")
            gaps[label] = {k[1]: ma[k] - mb[k] for k in set(ma) & set(mb)}
        gap_rows = []
        for other in ("symptom fixed (v1.5B)", "cause fixed too (v1.5C)"):
            common = sorted(set(gaps["registered simulator"]) & set(gaps.get(other, {})))
            if len(common) >= 5:
                est, lo, hi = A.bootstrap([np.array([gaps["registered simulator"][k] - gaps[other][k]]) for k in common], np.mean, 10_000)
                gap_rows.append((f"registered minus {other}", len(common), f"{100 * est:+.1f} points (95% CI {100 * lo:+.1f} to {100 * hi:+.1f})"))
        L += [table(["simulator", "memory", "runs", "held-out episodes", "solved", "calls to success", "episodes with a false 'holding'", "episodes with a short move_to"], fx), "",
              "Notebook against no memory on the same ten run seeds, per simulator (a run needs both arms complete):", "",
              table(["simulator", "pairs", "notebook", "no memory", "success difference", "calls-to-success difference"], cmp_), "",
              "How much smaller is the notebook gain on a simulator with the defect removed? Difference of the gains, paired by run seed (a run-level bootstrap of the ten per-seed differences, exploratory and not pre-registered). The observed gain is smaller; with ten run seeds and one model the size of that change is uncertain, and an interval that includes zero means the data do not exclude no change at all:", "",
              table(["difference of gains", "run seeds", "estimate"], gap_rows), "",
              "The disturbed held-out episodes (a slip or a shove mid-task) on the same three simulators, Haiku on `stack`:", "",
              table(["simulator", "memory", "disturbed episodes", "solved"], dist_rows), ""]

    # --- 6c: the registered Q1 comparison replicated on the corrected simulator (v1.6; exploratory)
    rep_rows = [r for r in (A.load(*ex(a.rep), complete_only=True) if ex(a.rep) else []) if 20 <= r["run_seed"] <= 29]          # planned run seeds only
    if rep_rows:
        rcov = A.coverage(*ex(a.rep))
        L += ["## 6c. Exploratory: the registered Q1 comparison replicated on the corrected simulator, fresh layouts", "",
              "Registered before it ran (PROTOCOL.md v1.6, 23:51). Both cheap models, all three jobs, run seeds 20 to 29 (layouts no other cell uses), memory `none` and `notebook`, on the code with the false-holding cause fixed (tag `code-fixed`). "
              "Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction), the same interval rule as Q1, paired by (task, run seed); **never pooled** with the registered Q1 rows above, which stay the confirmatory result. "
              f"Runs complete: {sum(int(c['complete']) for c in rcov)} of {len(rcov)} started (120 planned); episodes finished {sum(c['done'] for c in rcov)} of {sum(c['planned'] for c in rcov)}.", ""]
        rr = []
        verdict = {}
        for m in cheap:
            for tl, tname in ((None, "all three jobs"), (["stack"], "stack"), (["bins"], "bins"), (["flasks"], "flasks")):
                d = A.paired_difference(rep_rows, m, "notebook", "none", tasks=tl)
                dc = A.paired_difference(rep_rows, m, "notebook", "none", metric="calls_to_success", tasks=tl)
                if d.get("n_pairs"):
                    rr.append((m, tname, d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True), ci(dc)))
                    verdict[(m, tname)] = d
        L += [table(["model", "jobs", "pairs (task, run seed)", "notebook", "no memory", "success difference", "calls-to-success difference"], rr), "",
              "The registered Q1 rows for comparison (run seeds 0 to 9, registered simulator): " + "; ".join(
                  f"{m}: {ci(A.paired_difference(skills, m, 'notebook', 'none'), pct=True)}" for m in cheap) + ".", ""]
        art = []
        for m in cheap:
            for c in ("none", "notebook"):
                x = A.select(rep_rows, model=m, condition=c, phase="eval", quirk=True)
                if x:
                    art.append((m, NAMES[c], len(x), sum(1 for r in x if r["false_hold"]), sum(1 for r in x if r["short_move"]), f"{sum(r['success'] for r in x)}/{len(x)}"))
        L += ["The artefact symptoms of section 2a on this code (both should now be 0):", "", table(["model", "memory", "held-out episodes", "with a false 'holding'", "with a short move_to", "solved"], art), ""]
        # the predictions of v1.6, scored mechanically, and only once every required cell and pair exists
        expected_pairs = {"all three jobs": 30, "stack": 10, "bins": 10, "flasks": 10}
        missing = [f"{m} {t}: {verdict.get((m, t), {}).get('n_pairs', 0)} of {n} pairs" for m in cheap for t, n in expected_pairs.items() if verdict.get((m, t), {}).get("n_pairs", 0) < n]
        floor = {"all three jobs": 24, "stack": 8, "bins": 8, "flasks": 8}                       # registered in PROTOCOL.md v1.6B: the Q1 floor (24 of 30 pooled pairs) and 8 of 10 per job
        final = (ROOT / "logs/rep_fixed_done.txt").exists()

        def S(cells, fn):
            """pending until every pair exists; once the cell has finished, scored if each cell has at least its floor, else inconclusive"""
            got = [verdict.get(c, {}).get("n_pairs", 0) for c in cells]
            if all(g >= expected_pairs[c[1]] for g, c in zip(got, cells)):
                return fn()
            if not final:
                return "pending"
            return "inconclusive (below the registered floor)" if any(g < floor[c[1]] for g, c in zip(got, cells)) else fn() + " (scored with fewer than the planned pairs, above the floor)"
        bad_files = [c["file"] for c in rcov if c.get("code") != "8fdcf6b2491b68a3" or not 20 <= c["run_seed"] <= 29]
        L += [f"Validation of the included files: {len(rcov)} run files, every one with code hash `8fdcf6b2491b68a3` and a run seed from 20 to 29: {'yes' if not bad_files else 'NO, ' + ', '.join(bad_files[:5])}. "
              + (f"**Incomplete: {len(missing)} of {len(cheap) * len(expected_pairs)} model and job cells are missing pairs ({'; '.join(missing[:6])}{' ...' if len(missing) > 6 else ''}). Every prediction below is pending until all 120 runs are complete; once the cell has finished it is scored if every cell has at least the registered floor (24 of 30 pooled pairs, 8 of 10 per job) and called inconclusive below it.**" if missing else "All 120 planned runs are complete."), ""]
        pr = []
        hs, hall = verdict.get(("claude-haiku-5-5", "stack")), verdict.get(("claude-haiku-5-5", "all three jobs"))
        ls_ = verdict.get(("gpt-6-luna", "all three jobs"))
        if hs:
            pr.append(("1. Haiku `stack`: notebook at or above 90%, no memory 30% to 75%, gain at least +20 points",
                       f"notebook {f(hs['a'], True)}, no memory {f(hs['b'], True)}, gain {hs['diff'] * 100:+.1f}", S([("claude-haiku-5-5", "stack")], lambda: "met" if hs["a"] >= 0.90 and 0.30 <= hs["b"] <= 0.75 and hs["diff"] >= 0.20 else "MISSED")))
        if hall:
            pr.append(("2. Haiku pooled: gain at least +10 points with the 95% interval above zero", f"gain {hall['diff'] * 100:+.1f}, interval {hall['lo'] * 100:+.1f} to {hall['hi'] * 100:+.1f}",
                       S([("claude-haiku-5-5", "all three jobs")], lambda: "met" if hall["diff"] >= 0.10 and hall["lo"] > 0 else "MISSED")))
        if ls_:
            pr.append(("3. Luna pooled: a small positive gain below +15 points (interval may include zero)", f"gain {ls_['diff'] * 100:+.1f}, interval {ls_['lo'] * 100:+.1f} to {ls_['hi'] * 100:+.1f}",
                       S([("gpt-6-luna", "all three jobs")], lambda: "met" if 0 < ls_["diff"] < 0.15 else "MISSED")))
        worst = [(k, v) for k, v in verdict.items() if k[1] != "all three jobs" and v["diff"] < -0.05]
        pr.append(("4. No job where the notebook arm is more than 5 points below no memory", "none" if not worst else "; ".join(f"{k[0]} {k[1]} {v['diff'] * 100:+.1f}" for k, v in worst), S([(m, t) for m in cheap for t in ("stack", "bins", "flasks")], lambda: "met" if not worst else "MISSED")))
        against = []
        if hs and hs["b"] >= 0.85:
            against.append("Haiku `stack` no memory at 85% or more")
        if hall and hall["diff"] < 0.05:
            against.append("pooled Haiku gain below +5 points")
        L += ["Note on the two corrected simulators: the three-simulator comparison of section 6b used the code with hash `aef351c5c3033d54` (tag `code-fixcollide`); this replication uses `8fdcf6b2491b68a3` (tag `code-fixed`), which adds only the layout sampler restart on top of it (a change that touches one flasks layout, not used here), so for the played layouts the two behave alike.", "",
              "Predictions of PROTOCOL.md v1.6, scored by the generator:", "", table(["prediction", "result", "status"], void_if(bad_files, pr)), "",
              ("Pending or inconclusive: the pre-stated conditions against the claim (Haiku `stack` no memory at 85% or more, or a pooled Haiku gain below +5 points) are judged under the same rule as the predictions (all pairs, or the registered floor once the cell has finished)." if S([("claude-haiku-5-5", "stack"), ("claude-haiku-5-5", "all three jobs")], lambda: "") in ("pending",) or S([("claude-haiku-5-5", "stack"), ("claude-haiku-5-5", "all three jobs")], lambda: "").startswith("inconclusive") else
               ("**The registered headline did not replicate on the corrected simulator** (" + "; ".join(against) + ")." if against else "The pre-stated condition against the claim (Haiku `stack` no memory at 85% or more, or a pooled Haiku gain below +5 points) did not occur.")),
              "The four predictions were written after the registered and three-simulator results were known, so they are predictions about a replication, not independent forecasts; the condition against the claim leaves a middle zone (a pooled Haiku gain between +5 and +10 points) in which the replication is neither confirmed nor refuted, and the report says so if it lands there.", ""]
        dr = []
        for m in cheap:
            for c in ("none", "notebook"):
                ds = A.disturbance_summary(rep_rows, m, c)
                if ds.get("n_disturbed"):
                    dr.append((m, NAMES[c], ds["n_disturbed"], f(ds["fire_rate"], True), f(ds["success_all_assigned"], True), f(ds["success_same_layouts_clean"], True)))
        if dr:
            L += ["Disturbed held-out episodes on the same code (catch scenes, exploratory replication of the catch-scene recovery rows of section 5):", "",
                  table(["model", "memory", "disturbed episodes", "disturbance fired", "success, all assigned", "same layouts, no disturbance"], dr), ""]

    # --- 6d: is it the experience, or one sentence? (v1.7; exploratory)
    hp_rows = [r for r in (A.load(*ex(a.hint), complete_only=True) if ex(a.hint) else []) if 20 <= r["run_seed"] <= 29]
    if hp_rows and rep_rows:
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "scripts"))
        from notebook_audit import FIX
        allr = rep_rows + hp_rows
        hcov = A.coverage(*ex(a.hint))
        L += ["## 6d. Exploratory: is it the experience, or one sentence? (hint, generic hint and zero-practice notebook)", "",
              "Registered before the cells existed (PROTOCOL.md v1.7). No practice in any of these arms; the memory slot holds (a) `hint`: one fixed sentence naming the fixing setting, (b) `hint_generic`: one fixed generic sentence that lists the adjustable settings (`grip_level`, `grasp_height`, `release_height`, `speed`, which include each job's fixing setting) and says to change them one at a time after a failure, but never says which one or to what value (it is **not** a placebo: it is a shortlist plus permission to vary), (c) `prior`: a notebook Fable wrote with **zero practice** from the task text and tool descriptions only. "
              "Compared with the `none` and `notebook` arms of the corrected-simulator replication (section 6c) on the same run seeds 20 to 29 and the same held-out layouts. The prompt labels differ between arms, so nothing here isolates content from label. "
              f"Run files started {len(hcov)}, complete {sum(int(c['complete']) for c in hcov)} (planned 180); every file's hash: " + ", ".join(sorted({f"`{c.get('code')}`" for c in hcov})) + ". Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction).", ""]
        arms = ("none", "notebook", "hint", "hint_generic", "prior")
        keys = {}
        for m in cheap:
            ks = None
            for c in arms:
                kc = {(r["task"], r["run_seed"]) for r in A.select(allr, model=m, condition=c, phase="eval", quirk=True)}
                ks = kc if ks is None else ks & kc
            keys[m] = ks or set()
        tr = []
        for m in cheap:
            for tname, tl in (("all three jobs", TASKS), ("stack", ["stack"]), ("bins", ["bins"]), ("flasks", ["flasks"])):
                cells = []
                for c in arms:
                    x = [r for r in A.select(allr, model=m, condition=c, phase="eval", quirk=True) if r["task"] in tl and (r["task"], r["run_seed"]) in keys[m]]
                    cells.append(f"{f(mean(x, 'success'), True)} ({mean(x, 'calls_to_success'):.1f} calls)" if x else "-")
                tr.append((m, tname, len({k for k in keys[m] if k[0] in tl}), *cells))
        pred_at_6d = len(L)
        L += ["Held-out success (and calls to success) on exactly the runs every arm of that model has:", "", table(["model", "jobs", "runs", "no memory", "own notebook", "hint", "generic hint", "Fable, no practice"], tr), ""]
        cmp_rows, vd = [], {}
        for m in cheap:
            for tname, tl in (("all three jobs", None), ("stack", ["stack"]), ("bins", ["bins"]), ("flasks", ["flasks"])):
                for x, y in (("hint", "notebook"), ("hint", "none"), ("hint_generic", "none"), ("hint_generic", "notebook"), ("prior", "none"), ("prior", "notebook")):
                    d = A.paired_difference(allr, m, x, y, tasks=tl)
                    if d.get("n_pairs"):
                        cmp_rows.append((m, tname, f"{NAMES[x]} against {NAMES[y]}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
                        vd[(m, tname, x, y)] = d
        L += ["Paired differences (task, run seed):", "", table(["model", "jobs", "comparison", "pairs", "first", "second", "difference"], cmp_rows), ""]
        pn = []
        pdir = Path(a.prior_notebooks)
        named = {}
        for t in TASKS:
            fs = sorted(pdir.glob(f"{t}__s*.json")) if pdir.exists() else []
            texts = [json.loads(fp.read_text()).get("text", "") for fp in fs]
            named[t] = sum(1 for x in texts if FIX[t](x))
            pn.append((t, len(texts), named[t]))
        L += ["Do the zero-practice notebooks name the fixing setting? (the same keyword rules as `results/notebook_audit.md`, run on the 30 notebooks before any cheap model read them; a keyword check, not a judgement of quality):", "",
              table(["job", "notebooks", "name the fixing setting"], pn), ""]
        expected = {"all three jobs": 30, "stack": 10, "bins": 10, "flasks": 10}
        floor = {"all three jobs": 24, "stack": 8, "bins": 8, "flasks": 8}
        final = (ROOT / "logs/hint_prior_done.txt").exists()

        def S2(cells, fn):
            got = [vd.get(c, {}).get("n_pairs", 0) for c in cells]
            if all(g >= expected[c[1]] for g, c in zip(got, cells)):
                return fn()
            if not final:
                return "pending"
            return "inconclusive (below the registered floor)" if any(g < floor[c[1]] for g, c in zip(got, cells)) else fn() + " (scored with fewer than the planned pairs, above the floor)"
        pr = []
        hn = [(m, "all three jobs", "hint", "notebook") for m in cheap]
        h1 = {m: vd.get((m, "all three jobs", "hint", "notebook")) for m in cheap}
        hs_ = vd.get(("claude-haiku-5-5", "stack", "hint", "none"))
        pr.append(("H1: the hint is within 5 points of the model's own notebook (pooled, each model) and Haiku `stack` with the hint is at least 90%",
                   "; ".join(f"{m}: hint minus notebook {h1[m]['diff'] * 100:+.1f}" for m in cheap if h1[m]) + (f"; Haiku stack hint {f(hs_['a'], True)}" if hs_ else ""),
                   S2(hn + [("claude-haiku-5-5", "stack", "hint", "none")], lambda: "met" if all(h1[m] and abs(h1[m]["diff"]) <= 0.05 for m in cheap) and hs_ and hs_["a"] >= 0.90 else "MISSED")))
        g2 = {m: vd.get((m, "all three jobs", "hint_generic", "none")) for m in cheap}
        gs_ = vd.get(("claude-haiku-5-5", "stack", "hint_generic", "none"))
        pr.append(("H2: the generic hint stays well below the notebook: Haiku `stack` at most 60% and a pooled gain over no memory under +10 points for each model",
                   "; ".join(f"{m}: generic minus none {g2[m]['diff'] * 100:+.1f}" for m in cheap if g2[m]) + (f"; Haiku stack generic {f(gs_['a'], True)}" if gs_ else ""),
                   S2([(m, "all three jobs", "hint_generic", "none") for m in cheap] + [("claude-haiku-5-5", "stack", "hint_generic", "none")],
                      lambda: "met" if all(g2[m] and g2[m]["diff"] < 0.10 for m in cheap) and gs_ and gs_["a"] <= 0.60 else "MISSED")))
        ps_ = vd.get(("claude-haiku-5-5", "stack", "prior", "none"))
        ok_kw = named.get("stack", 0) >= 5 and named.get("bins", 99) <= 2 and named.get("flasks", 99) <= 3
        n_notebooks = {t: n for t, n, _ in pn}
        kw_complete = all(n_notebooks.get(t, 0) >= 10 for t in TASKS)
        h3_state = S2([("claude-haiku-5-5", "stack", "prior", "none")], lambda: "met" if ok_kw and ps_ and ps_["a"] >= 0.60 else "MISSED")
        pr.append(("H3: the zero-practice notebooks name `grip_level firm` for `stack` in at least 5 of 10, a release height of 0.14 or more for `bins` in at most 2 of 10 and a grasp height of 0.8 or more for `flasks` in at most 3 of 10, and Haiku `stack` with a prior notebook solves at least 60%",
                   f"names the fix: stack {named.get('stack', 0)} of {n_notebooks.get('stack', 0)}, bins {named.get('bins', 0)} of {n_notebooks.get('bins', 0)}, flasks {named.get('flasks', 0)} of {n_notebooks.get('flasks', 0)}" + (f"; Haiku stack prior {f(ps_['a'], True)}" if ps_ else ""),
                   h3_state if kw_complete else "pending"))
        bad_files = bad_cov(hcov, {"088c639d7139a3af"})
        pr = void_if(bad_files, pr)
        L[pred_at_6d:pred_at_6d] = ["**Predictions of PROTOCOL.md v1.7, scored by the generator first, as the protocol requires** (pending until every pair exists; after the cells have finished, scored when each cell has the registered floor of 24 of 30 pooled and 8 of 10 per-job pairs, inconclusive below it). The registered reading: if H2 fails the headline is weakened, and if H3 fails because the notebooks name the fix, practice is the wrong cost to count.", "", table(["prediction", "result", "status"], pr), ""]
        L.insert(pred_at_6d + 4, f"Validation of the included files: {len(hcov)} run files, every one with code hash `088c639d7139a3af` and a run seed from 20 to 29: {'yes' if not bad_files else 'NO (' + str(len(bad_files)) + ' files)'}.\n")

    # --- 6e: a second, mid-tier writer (v1.8; exploratory)
    wr_rows = [r for r in (A.load(*ex(a.writer), complete_only=True) if ex(a.writer) else []) if 20 <= r["run_seed"] <= (29 if r["task"] == "stack" else 24)]
    bs_rows = [r for r in (A.load(*ex(a.borrowed_sonnet), complete_only=True) if ex(a.borrowed_sonnet) else []) if 20 <= r["run_seed"] <= (29 if r["task"] == "stack" else 24)]
    if wr_rows or bs_rows:
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "scripts"))
        from notebook_audit import FIX
        from robot_play.runner import frontier_notebook
        wm = "claude-sonnet-5-5"
        wdir = ex(a.writer)[0] if ex(a.writer) else "runs/writer_sonnet"
        wcov = A.coverage(*ex(a.writer)) if ex(a.writer) else []
        bcov = A.coverage(*ex(a.borrowed_sonnet)) if ex(a.borrowed_sonnet) else []
        planned_w = {"stack": 10, "bins": 5, "flasks": 5}
        L += ["## 6e. Exploratory: does the notebook need a frontier writer? (a second writer, Claude Sonnet 5.5)", "",
              "Registered before any episode ran (PROTOCOL.md v1.8). Sonnet 5.5 practises and writes its own notebook (`stack` run seeds 20 to 29, `bins` and `flasks` run seeds 20 to 24); Haiku and Luna then read that notebook with no practice of their own, on the same four held-out layouts as the corrected-simulator replication (section 6c), where they pair with the `none` and `notebook` arms. "
              f"Writer run files started {len(wcov)}, complete {sum(int(c['complete']) for c in wcov)} (planned 20); borrowed run files started {len(bcov)}, complete {sum(int(c['complete']) for c in bcov)} (planned 40). Code hashes: " + ", ".join(sorted({f"`{c.get('code')}`" for c in wcov + bcov})) + ". Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction).", ""]
        wt = []
        for t in TASKS:
            ev = [r for r in A.select(wr_rows, model=wm, condition="notebook", phase="eval", quirk=True) if r["task"] == t]
            pa = [r for r in A.select(wr_rows, model=wm, condition="notebook", phase="practice", quirk=True) if r["task"] == t]
            runs_ = sorted({r["run_seed"] for r in ev})
            texts = {rs: frontier_notebook(str(wdir), wm, t, rs) for rs in runs_}
            named_ = sum(1 for x in texts.values() if x and FIX[t](x))
            wt.append((t, f"{len(runs_)} of {planned_w[t]}", f(mean(pa, "success"), True) if pa else "-", f(mean(ev, "success"), True) if ev else "-", f"{named_} of {len(runs_)}"))
        L += ["Sonnet itself (its practice-episode success, its held-out success with its own notebook, and how many of its final notebooks name the fixing setting by the keyword rules of `results/notebook_audit.md`; a keyword check, not a judgement of quality):", "",
              table(["job", "runs finished", "practice success", "held-out success, own notebook", "notebooks naming the fix"], wt), ""]
        sn_named = {t: next((int(x.split(" of ")[0]) for x in [row[4]] ), 0) for t, row in zip(TASKS, wt)}
        allr = rep_rows + bs_rows
        sname = lambda c: "reads Sonnet's notebook" if c == "borrowed" else NAMES[c]
        arms = ("none", "notebook", "borrowed")
        keys = {}
        for m in cheap:
            ks = None
            for c in arms:
                kc = {(r["task"], r["run_seed"]) for r in A.select(allr, model=m, condition=c, phase="eval", quirk=True)}
                ks = kc if ks is None else ks & kc
            keys[m] = {k for k in (ks or set()) if k[1] in range(20, 30) and (k[0] == "stack" or k[1] < 25)}
        tr = []
        for m in cheap:
            for tname, tl in (("all three jobs", TASKS), ("stack", ["stack"]), ("bins", ["bins"]), ("flasks", ["flasks"])):
                cells = []
                for c in arms:
                    x = [r for r in A.select(allr, model=m, condition=c, phase="eval", quirk=True) if r["task"] in tl and (r["task"], r["run_seed"]) in keys[m]]
                    cells.append(f"{f(mean(x, 'success'), True)} ({mean(x, 'calls_to_success'):.1f} calls)" if x else "-")
                tr.append((m, tname, len({k for k in keys[m] if k[0] in tl}), *cells))
        pred_at_6e = len(L)
        L += ["Held-out success (and calls to success) on exactly the runs that have all three arms:", "", table(["model", "jobs", "runs", "no memory", "own notebook", "Sonnet's notebook, no practice"], tr), ""]
        cmp_rows, vd = [], {}
        for m in cheap:
            for tname, tl in (("all three jobs", None), ("stack", ["stack"]), ("bins", ["bins"]), ("flasks", ["flasks"])):
                for x, y in (("borrowed", "none"), ("borrowed", "notebook")):
                    d = A.paired_difference(allr, m, x, y, tasks=tl)
                    if d.get("n_pairs"):
                        cmp_rows.append((m, tname, f"{sname(x)} against {sname(y)}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
                        vd[(m, tname, x, y)] = d
        L += ["Paired differences (task, run seed; every pair that exists, which can be more than the table above):", "", table(["model", "jobs", "comparison", "pairs", "first", "second", "difference"], cmp_rows), ""]
        # S4: the runs where Haiku's own notebook failed
        hm = "claude-haiku-5-5"
        own = {}
        for r in A.select(rep_rows, model=hm, condition="notebook", phase="eval", quirk=True):
            own.setdefault((r["task"], r["run_seed"]), []).append(r["success"])
        bor = {}
        for r in A.select(bs_rows, model=hm, condition="borrowed", phase="eval", quirk=True):
            bor.setdefault((r["task"], r["run_seed"]), []).append(r["success"])
        failed = sorted(k for k, v in own.items() if sum(v) <= 1 and k in bor and len(bor[k]) == 4)
        if failed:
            L += ["Runs where Haiku's own notebook solved at most 1 of 4 held-out layouts, and what Haiku solved reading Sonnet's notebook for the same job and run seed:", "",
                  table(["job", "run seed", "own notebook (of 4)", "Sonnet's notebook (of 4)"], [(t, rs, sum(own[(t, rs)]), sum(bor[(t, rs)])) for t, rs in failed]), ""]
        final = (ROOT / "logs/borrowed_sonnet_done.txt").exists() or (len(wcov) == 20 and len(bcov) == 40 and all(c["complete"] for c in wcov + bcov))     # the marker, or every planned run file is complete
        ph = vd.get((hm, "stack", "borrowed", "none"))
        exp_pairs = {"stack": 10, "all three jobs": 20}
        def S3(cells, fn):
            got = [vd.get(c, {}).get("n_pairs", 0) for c in cells]
            if all(g >= exp_pairs[c[1]] for g, c in zip(got, cells)):
                return fn()
            if not final:
                return "pending"
            return "inconclusive (below the registered floor)" if any(g < 0.8 * exp_pairs[c[1]] for g, c in zip(got, cells)) else fn() + " (scored with fewer than the planned pairs, above the floor)"
        pr = []
        pr.append(("S1: Haiku `stack` reading Sonnet's notebook solves at least 90% of the 40 held-out layouts",
                   f"Haiku stack {f(ph['a'], True)}" if ph else "no data", S3([(hm, "stack", "borrowed", "none")], lambda: "met" if ph and ph["a"] >= 0.90 else "MISSED")))
        pn_ = vd.get((hm, "all three jobs", "borrowed", "notebook"))
        pr.append(("S2: pooled over the 20 runs, Haiku with Sonnet's notebook is within 5 points of Haiku's own notebook (difference at least -5)",
                   f"borrowed minus own notebook {pn_['diff'] * 100:+.1f}" if pn_ else "no data", S3([(hm, "all three jobs", "borrowed", "notebook")], lambda: "met" if pn_ and pn_["diff"] >= -0.05 else "MISSED")))
        n_stack = next((int(row[1].split(" of ")[0]) for row in wt if row[0] == "stack"), 0)
        pr.append(("S3: Sonnet's `stack` notebooks name `grip_level firm` in at least 8 of 10 runs",
                   f"{sn_named['stack']} of {n_stack}", ("met" if sn_named["stack"] >= 8 else "MISSED") if n_stack >= 10 else "pending"))
        if failed:
            mo = sum(sum(own[k]) for k in failed) / len(failed); mb = sum(sum(bor[k]) for k in failed) / len(failed)
            s4 = f"{len(failed)} such run(s): own notebook {mo:.2f} of 4 on average, Sonnet's notebook {mb:.2f} of 4"
            pr.append(("S4: where Haiku's own notebook solved at most 1 of 4, reading Sonnet's notebook solves strictly more on average", s4,
                       ("met" if mb > mo else "MISSED") if (final or all(len(bor.get(k, [])) == 4 for k in own if sum(own[k]) <= 1)) else "pending"))
        else:
            pr.append(("S4: where Haiku's own notebook solved at most 1 of 4, reading Sonnet's notebook solves strictly more on average", "no such run in the replication so far", "not testable" if final else "pending"))
        bad_files = bad_cov(wcov + bcov, {"088c639d7139a3af"})
        pr = void_if(bad_files, pr)
        L[pred_at_6e:pred_at_6e] = ["**Predictions of PROTOCOL.md v1.8, scored by the generator first** (pending until every pair exists; below 80% of the planned pairs inconclusive after the cells have finished). Note: v1.8 was registered at 01:35, after the hint cell (which showed the naming hint at 100% on `stack`) had finished, so S1 and S2 were close to certain when written.", "", table(["prediction", "result", "status"], pr), ""]
        L.insert(pred_at_6e + 4, f"Validation of the included files: {len(wcov) + len(bcov)} run files, every one with code hash `088c639d7139a3af` and a run seed from 20 to 29: {'yes' if not bad_files else 'NO (' + str(len(bad_files)) + ' files)'}.\n")

    # --- 6f: a label-matched text control (v1.9; exploratory)
    lm_rows = [r for r in (A.load(*ex(a.labelmatch), complete_only=True) if ex(a.labelmatch) else []) if 20 <= r["run_seed"] <= 29]
    if lm_rows and rep_rows:
        lcov = A.coverage(*ex(a.labelmatch))
        allr = rep_rows + [r for r in hp_rows if r["condition"] in ("hint", "hint_generic")] + lm_rows
        LN = {"lm_inert": "reads an inert sentence under the neutral label", "lm_generic": "reads the generic sentence under the neutral label", "lm_specific": "reads the naming sentence under the neutral label"}
        NAMES.update(LN)
        L += ["## 6f. Exploratory: is it the words or the label? (a label-matched text control)", "",
              "Registered before any episode ran (PROTOCOL.md v1.9). No practice; the memory slot has **one neutral label** (\"NOTES FOR THIS TASK\") over (a) an inert sentence of about the generic sentence's length that names no setting, (b) the generic sentence of section 6d (it lists `grip_level`, `grasp_height`, `release_height` and `speed`), (c) the naming sentence of section 6d. "
              "Same layouts as the replication and section 6d (run seeds 20 to 29), so every arm pairs. "
              f"Run files started {len(lcov)}, complete {sum(int(c['complete']) for c in lcov)} (planned 180). Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction).", ""]
        pred_at_6f = len(L)
        arms = ("none", "lm_inert", "lm_generic", "hint_generic", "lm_specific", "hint")
        keys = {}
        for m in cheap:
            ks = None
            for c in arms:
                kc = {(r["task"], r["run_seed"]) for r in A.select(allr, model=m, condition=c, phase="eval", quirk=True)}
                ks = kc if ks is None else ks & kc
            keys[m] = ks or set()
        tr = []
        for m in cheap:
            for tname, tl in (("all three jobs", TASKS), ("stack", ["stack"]), ("bins", ["bins"]), ("flasks", ["flasks"])):
                cells = []
                for c in arms:
                    x = [r for r in A.select(allr, model=m, condition=c, phase="eval", quirk=True) if r["task"] in tl and (r["task"], r["run_seed"]) in keys[m]]
                    cells.append(f"{f(mean(x, 'success'), True)} ({mean(x, 'calls_to_success'):.1f} calls)" if x else "-")
                tr.append((m, tname, len({k for k in keys[m] if k[0] in tl}), *cells))
        L += ["Held-out success (and calls to success) on exactly the runs every arm of that model has:", "",
              table(["model", "jobs", "runs", "no memory", "inert, neutral label", "generic, neutral label", "generic, operator label", "naming, neutral label", "naming, operator label"], tr), ""]
        cmp_rows, vd = [], {}
        for m in cheap:
            for tname, tl in (("all three jobs", None), ("stack", ["stack"]), ("bins", ["bins"]), ("flasks", ["flasks"])):
                for x, y in (("lm_inert", "none"), ("lm_generic", "lm_inert"), ("lm_generic", "none"), ("lm_specific", "lm_generic"), ("lm_specific", "none"), ("lm_generic", "hint_generic"), ("lm_specific", "hint")):
                    d = A.paired_difference(allr, m, x, y, tasks=tl)
                    if d.get("n_pairs"):
                        cmp_rows.append((m, tname, f"{NAMES[x]} against {NAMES[y]}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
                        vd[(m, tname, x, y)] = d
        L += ["Paired differences (task, run seed):", "", table(["model", "jobs", "comparison", "pairs", "first", "second", "difference"], cmp_rows), ""]
        hm = "claude-haiku-5-5"
        final = (ROOT / "logs/labelmatch_done.txt").exists()

        def S4(cells, fn):
            got = [vd.get(c, {}).get("n_pairs", 0) for c in cells]
            if all(g >= 10 for g in got):
                return fn()
            if not final:
                return "pending"
            return "inconclusive (below the registered floor)" if any(g < 8 for g in got) else fn() + " (scored with fewer than the planned pairs, above the floor)"
        pr = []
        li, lg, ls_, gi = (vd.get((hm, "stack", "lm_inert", "none")), vd.get((hm, "stack", "lm_generic", "none")), vd.get((hm, "stack", "lm_specific", "none")), vd.get((hm, "stack", "lm_generic", "lm_inert")))
        pr.append(("L1: Haiku `stack` with the inert text solves at most 65%", f"Haiku stack inert {f(li['a'], True)}" if li else "no data", S4([(hm, "stack", "lm_inert", "none")], lambda: "met" if li["a"] <= 0.65 else "MISSED")))
        pr.append(("L2: Haiku `stack` with the generic text under the neutral label solves at least 80%", f"Haiku stack generic {f(lg['a'], True)}" if lg else "no data", S4([(hm, "stack", "lm_generic", "none")], lambda: "met" if lg["a"] >= 0.80 else "MISSED")))
        pr.append(("L3: Haiku `stack` with the naming text under the neutral label solves at least 90%", f"Haiku stack naming {f(ls_['a'], True)}" if ls_ else "no data", S4([(hm, "stack", "lm_specific", "none")], lambda: "met" if ls_["a"] >= 0.90 else "MISSED")))
        pr.append(("L4: Haiku `stack`, generic minus inert is at least +20 points", f"generic minus inert {gi['diff'] * 100:+.1f}" if gi else "no data", S4([(hm, "stack", "lm_generic", "lm_inert")], lambda: "met" if gi["diff"] >= 0.20 else "MISSED")))
        bad_files = bad_cov(lcov, {LM_HASH})
        pr = void_if(bad_files, pr)
        L[pred_at_6f:pred_at_6f] = ["**Predictions of PROTOCOL.md v1.9, scored by the generator first** (pending until every pair exists; below 80% of the planned pairs inconclusive after the cell has finished). The registered reading: if L1 and L4 hold, the generic sentence's effect comes from the settings it lists and not from the label or from text of that length; if L1 fails (inert at 80% or more), much of it is an attention effect of any note; if L2 fails while the operator-labelled generic hint reached 90%, the authority of the label mattered.", "",
                                    table(["prediction", "result", "status"], pr), "",
                                    f"Validation of the included files: {len(lcov)} run files, every one with code hash `{LM_HASH}` and a run seed from 20 to 29: {'yes' if not bad_files else 'NO (' + str(len(bad_files)) + ' files)'}.", ""]

    # --- 6g: the generic sentence taken apart (v1.10; exploratory)
    ws_rows = [r for r in (A.load(*ex(a.wordsplit), complete_only=True) if ex(a.wordsplit) else []) if 20 <= r["run_seed"] <= 29]
    if ws_rows and rep_rows and lm_rows:
        wcov2 = A.coverage(*ex(a.wordsplit))
        allw = rep_rows + [r for r in lm_rows if r["condition"] in ("lm_inert", "lm_generic")] + ws_rows
        WN = {"lm_frame": "frame only", "lm_names": "frame + the four names", "lm_instr": "frame + the instruction"}
        NAMES.update({"lm_frame": "reads the frame sentence only (neutral label)", "lm_names": "reads the frame and the four names (neutral label)", "lm_instr": "reads the frame and the instruction to vary (neutral label)"})
        L += ["## 6g. Exploratory: which part of the generic sentence does the work? (the sentence taken apart)", "",
              "Registered before any episode ran, and pushed to GitHub before the first one started (PROTOCOL.md v1.10). The generic sentence is a **frame** (\"Defaults do not suit every object or surface.\"), an **instruction** (when a call fails or is refused, change the settings one at a time instead of repeating the call) and the **names** of the four settings. "
              "Claude Haiku 5.5, `stack` only, no practice, the neutral label of section 6f, run seeds 20 to 29 (the same layouts as every other arm of this model, so each arm pairs). The three new arms keep the frame and add the names, the instruction, or neither. "
              f"Run files started {len(wcov2)}, complete {sum(int(c['complete']) for c in wcov2)} (planned 30). Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction), ten pairs per comparison, so wide.", ""]
        pred_at_6g = len(L)
        hm = "claude-haiku-5-5"
        arms = ("none", "lm_inert", "lm_frame", "lm_names", "lm_instr", "lm_generic")
        ks = None
        for c in arms:
            kc = {(r["task"], r["run_seed"]) for r in A.select(allw, model=hm, condition=c, phase="eval", quirk=True) if r["task"] == "stack"}
            ks = kc if ks is None else ks & kc
        ks = ks or set()
        row = []
        for c in arms:
            x = [r for r in A.select(allw, model=hm, condition=c, phase="eval", quirk=True) if r["task"] == "stack" and (r["task"], r["run_seed"]) in ks]
            row.append(f"{f(mean(x, 'success'), True)} ({mean(x, 'calls_to_success'):.1f} calls)" if x else "-")
        L += [f"Held-out success on `stack` (and calls to success) on the {len(ks)} runs every arm has:", "",
              table(["", "no memory", "inert sentence", "frame only", "frame + names", "frame + instruction", "frame + instruction + names (the generic sentence)"], [("Haiku", *row)]), ""]
        cmp_rows, vd = [], {}
        for x, y in (("lm_frame", "none"), ("lm_names", "none"), ("lm_instr", "none"), ("lm_generic", "none"), ("lm_names", "lm_frame"), ("lm_instr", "lm_frame"), ("lm_generic", "lm_instr"), ("lm_generic", "lm_names"), ("lm_frame", "lm_inert"), ("lm_names", "lm_instr"), ("lm_frame", "lm_generic")):
            d = A.paired_difference(allw, hm, x, y, tasks=["stack"])
            if d.get("n_pairs"):
                cmp_rows.append((f"{NAMES[x]} against {NAMES[y]}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
                vd[(x, y)] = d
        L += ["Paired differences (run seed):", "", table(["comparison", "pairs", "first", "second", "difference"], cmp_rows), ""]
        final = (ROOT / "logs/wordsplit_done.txt").exists() or all(vd.get((c, "none"), {}).get("n_pairs", 0) >= 10 for c in ("lm_frame", "lm_names", "lm_instr"))     # every planned pair exists

        def arm_state(c, fn):
            n = min(len(ks), *[vd.get((x, "none"), {}).get("n_pairs", 0) for x in ("lm_frame", "lm_names", "lm_instr")])      # scored only when every arm has its pairs, on the same run seeds
            if n >= 10:
                return fn()
            if not final:
                return "pending"
            return "inconclusive (below the registered floor)" if n < 8 else fn() + " (scored with fewer than the planned pairs, above the floor)"
        ri, rn, rf = (vd.get(("lm_instr", "none")), vd.get(("lm_names", "none")), vd.get(("lm_frame", "none")))
        pr = [("W1: Haiku `stack` with the frame and the instruction (no names) solves at least 75%", f"frame + instruction {f(ri['a'], True)}" if ri else "no data", arm_state("lm_instr", lambda: "met" if at_least(ri["a"], 0.75) else "MISSED")),
              ("W2: Haiku `stack` with the frame and the four names (no instruction) solves at most 65%", f"frame + names {f(rn['a'], True)}" if rn else "no data", arm_state("lm_names", lambda: "met" if at_most(rn["a"], 0.65) else "MISSED")),
              ("W3: Haiku `stack` with the frame only solves at most 65%", f"frame only {f(rf['a'], True)}" if rf else "no data", arm_state("lm_frame", lambda: "met" if at_most(rf["a"], 0.65) else "MISSED"))]
        bad_files = bad_cov(wcov2, {WS_HASH}) + bad_cov(rcov, {"8fdcf6b2491b68a3"}) + bad_cov(lcov, {LM_HASH})          # the anchors (no-memory replication, inert and generic arms) must validate too
        pr = void_if(bad_files, pr)
        if final and not bad_files and all(st in ("met", "MISSED") or st.startswith(("met ", "MISSED ")) for _, _, st in pr):
            w1, w2, w3 = (st.startswith("met") for _, _, st in pr)
            reading = ("W3 missed: the frame sentence alone does part of the work, so no split of the other two parts can be read cleanly." if not w3 else
                       "the instruction to change settings, not their names, carries most of the generic sentence's effect." if (w1 and w2) else
                       "neither part alone is enough; the effect needs both the instruction and the list of names." if (not w1 and w2) else
                       "either part suffices on its own." if (w1 and not w2) else
                       "the effect needs both parts, and each part alone does more than the frame.")
            reading = "Registered reading of the outcome (the wording of PROTOCOL.md v1.10): " + reading
            dn, di, dg, dgn, dni = (vd.get(k) for k in (("lm_names", "none"), ("lm_instr", "none"), ("lm_generic", "none"), ("lm_generic", "lm_names"), ("lm_names", "lm_instr")))
            if all((dn, di, dg, dgn, dni)):
                reading += ("\n\n**What the numbers show (written after seeing them, not registered).** With the frame, the four names alone reached " + f"{f(dn['a'], True)}" + f" (over fresh: {ci(dn, pct=True)}), the same as the full generic sentence (generic minus frame + names: {ci(dgn, pct=True)}). "
                            f"The instruction alone reached {f(di['a'], True)} (over fresh: {ci(di, pct=True)}). Names minus instruction: {ci(dni, pct=True)} (not a registered comparison). "
                            "So in these runs the list of names is what carries the effect, and the instruction adds little on top of it; the registered reading's phrase for the case where both predictions are missed (\"the effect needs both parts\") does not describe this outcome and is not used.")
        else:
            reading = "Registered reading: scored when the cell has finished."
        L[pred_at_6g:pred_at_6g] = ["**Predictions of PROTOCOL.md v1.10, scored by the generator first** (pending until every pair exists; below 8 of the 10 planned pairs per arm inconclusive once the cell has finished). Written after the v1.9 results were known, so not blind. "
                                    "The registered reading: W1 and W2 met, the instruction carries the effect and the names do not; W1 missed and W2 met, neither part alone is enough; W1 met and W2 missed, either part suffices; both missed, both parts are needed and each does more than the frame; W3 missed, the frame does part of the work and the split cannot be read cleanly. No reading is claimed for differences under 20 points (as registered; the post-hoc paragraph below states which of its statements rest on an interval and which on a point estimate).", "",
                                    table(["prediction", "result", "status"], pr), "", reading, "",
                                    f"Validation of the included files: {len(wcov2)} run files with code hash `{WS_HASH}`, plus the anchor files of the replication (`8fdcf6b2491b68a3`) and the label-matched cell (`{LM_HASH}`), all with a run seed from 20 to 29: {'yes' if not bad_files else 'NO (' + str(len(bad_files)) + ' files)'}.", ""]

    # --- 6h: the split repeated on fresh layouts, with nested wordings (v1.11; exploratory)
    ws2_rows = [r for r in (A.load(*ex(a.wordsplit2), complete_only=True) if ex(a.wordsplit2) else []) if 30 <= r["run_seed"] <= 39]
    if ws2_rows:
        w2cov = A.coverage(*ex(a.wordsplit2))
        W2N = {"none": "starts fresh", "lm_inert": "reads the inert sentence", "lm_frame": "reads the frame only", "lm_names": "reads the frame and the four names", "lm_instr": "reads the frame and 'change how you call it'",
               "lm_instr_n": "reads the frame and 'change the settings one at a time' (no names)", "lm_names2": "reads the frame, 'read the message' and the four names", "lm_generic": "reads the generic sentence"}
        NAMES.update({k: v + " (neutral label)" for k, v in W2N.items() if k != "none"})
        L += ["## 6h. Exploratory: the split repeated on fresh layouts (run seeds 30 to 39), with nested wordings", "",
              "Registered before any episode ran, and pushed to GitHub before the first one started (PROTOCOL.md v1.11). Claude Haiku 5.5, `stack` only, no practice, the neutral label, layouts no earlier arm has played. "
              "`lm_inert`, `lm_frame`, `lm_names`, `lm_instr` and `lm_generic` repeat the texts of sections 6f and 6g unchanged; `lm_instr_n` is the generic sentence minus the names exactly (it keeps the word \"settings\") and `lm_names2` is the generic sentence with the instruction to change replaced by a bare \"read the message\" (it keeps the names). "
              f"Run files started {len(w2cov)}, complete {sum(int(c['complete']) for c in w2cov)} (planned 80). Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction), ten pairs per comparison.", ""]
        pred_at_6h = len(L)
        hm = "claude-haiku-5-5"
        order = ("none", "lm_inert", "lm_frame", "lm_names", "lm_instr", "lm_instr_n", "lm_names2", "lm_generic")
        ks = None
        for c in order:
            kc = {r["run_seed"] for r in A.select(ws2_rows, model=hm, condition=c, phase="eval", quirk=True)}
            ks = kc if ks is None else ks & kc
        ks = ks or set()
        cells = []
        for c in order:
            x = [r for r in A.select(ws2_rows, model=hm, condition=c, phase="eval", quirk=True) if r["run_seed"] in ks]
            cells.append(f"{f(mean(x, 'success'), True)} ({mean(x, 'calls_to_success'):.1f} calls)" if x else "-")
        L += [f"Held-out success on `stack` (and calls to success) on the {len(ks)} runs every arm has:", "",
              table(["", *[W2N[c].replace("reads ", "").replace("starts fresh", "no memory") for c in order]], [("Haiku", *cells)]), ""]
        cmp_rows, vd2 = [], {}
        pairs = [(c, "none") for c in order[1:]] + [("lm_names", "lm_instr"), ("lm_names2", "lm_instr_n"), ("lm_generic", "lm_names2"), ("lm_generic", "lm_instr_n"), ("lm_names", "lm_frame"), ("lm_instr", "lm_frame"), ("lm_instr_n", "lm_frame"), ("lm_names", "lm_names2")]
        for x, y in pairs:
            d = A.paired_difference(ws2_rows, hm, x, y, tasks=["stack"])
            if d.get("n_pairs"):
                cmp_rows.append((f"{W2N[x]} against {W2N[y]}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
                vd2[(x, y)] = d
        pooled = A.paired_difference(ws_rows + ws2_rows, hm, "lm_names", "lm_instr", tasks=["stack"])
        if pooled.get("n_pairs"):
            cmp_rows.append((f"**primary: {W2N['lm_names']} against {W2N['lm_instr']}, pooled over run seeds 20 to 39 (this cell and section 6g)**", pooled["n_pairs"], f(pooled["a"], True), f(pooled["b"], True), ci(pooled, pct=True)))
        L += ["Paired differences (run seed):", "", table(["comparison", "pairs", "first", "second", "difference"], cmp_rows), ""]
        final2 = (ROOT / "logs/wordsplit2_done.txt").exists() or all(vd2.get((c, "none"), {}).get("n_pairs", 0) >= 10 for c in order[1:])

        def score(cells_, fn):
            n = min([len(ks)] + [vd2.get(c_, {}).get("n_pairs", 0) for c_ in cells_])          # every arm must have the same run seeds
            if n >= 10:
                return fn()
            if not final2:
                return "pending"
            return "inconclusive (below the registered floor)" if n < 8 else fn() + " (scored with fewer than the planned pairs, above the floor)"
        g = lambda c: vd2.get((c, "none"))
        r0, r1, r2, r3, r5 = (g("none") and None, g("lm_names"), g("lm_frame"), g("lm_instr"), g("lm_generic"))
        nn = [r for r in A.select(ws2_rows, model=hm, condition="none", phase="eval", quirk=True) if r["task"] == "stack"]
        n0 = min([vd2.get((c, "none"), {}).get("n_pairs", 0) for c in order[1:]] or [0])
        none_rate = mean(nn, "success") if nn else float("nan")
        r4 = vd2.get(("lm_names2", "lm_instr_n"))
        allc = [(c, "none") for c in order[1:]]
        pr = [("R0: Haiku `stack` with no memory solves at most 75% on these layouts (they have room)", f"no memory {f(none_rate, True)}" if nn else "no data", score(allc, lambda: "met" if at_most(none_rate, 0.75) else "MISSED")),
              ("R1: `lm_names` (frame and the four names) solves at least 80%", f"{f(r1['a'], True)}" if r1 else "no data", score(allc, lambda: "met" if at_least(r1["a"], 0.80) else "MISSED")),
              ("R2: `lm_frame` (frame only) solves at most 65%", f"{f(r2['a'], True)}" if r2 else "no data", score(allc, lambda: "met" if at_most(r2["a"], 0.65) else "MISSED")),
              ("R3: `lm_instr` (frame and 'change how you call it') solves at most 80%", f"{f(r3['a'], True)}" if r3 else "no data", score(allc, lambda: "met" if at_most(r3["a"], 0.80) else "MISSED")),
              ("R4: `lm_names2` minus `lm_instr_n` is at least +10 points", f"{r4['diff'] * 100:+.1f}" if r4 else "no data", score([("lm_names2", "lm_instr_n")] + allc, lambda: "met" if at_least(r4["diff"], 0.10) else "MISSED")),
              ("R5: `lm_generic` solves at least 80%", f"{f(r5['a'], True)}" if r5 else "no data", score(allc, lambda: "met" if at_least(r5["a"], 0.80) else "MISSED"))]
        bad_files = bad_cov(w2cov, {WS2_HASH}, 30, 39)
        pr = void_if(bad_files, pr)
        st = [x[2] for x in pr]
        if final2 and not bad_files and all(x.startswith(("met", "MISSED")) for x in st):
            m = [x.startswith("met") for x in st]
            if not m[0]:
                reading = "R0 missed: these layouts left no room, so nothing below is read."
            elif not m[1]:
                reading = "R1 missed: the v1.10 names result does not replicate on fresh layouts."
            elif m[1] and m[2] and m[5]:
                reading = ("the v1.10 pattern replicates on fresh layouts (the frame and the names reproduce the generic sentence, the frame alone does little)"
                           + (", and the names beat the instruction under both wordings (R3 and R4 met)." if (m[3] and m[4]) else
                              ", but the instruction wording matters: with the word 'settings' added the instruction closes the gap (R3 met, R4 missed), so the v1.10 contrast is partly a wording effect." if (m[3] and not m[4]) else
                              ", but the instruction reaches the names' level on these layouts (R3 missed), so the v1.10 gap is not reliable."))
            else:
                reading = "mixed: the registered reading does not cover this combination (R1 met, but R2 or R5 missed); see the table."
            reading = "Registered reading of the outcome: " + reading
        else:
            reading = "Registered reading: scored when the cell has finished."
        L[pred_at_6h:pred_at_6h] = ["**Predictions of PROTOCOL.md v1.11, scored by the generator first** (pending until every pair of every arm exists; below 8 of 10 pairs inconclusive once the cell has finished). Written after the v1.10 results were known, so not blind. "
                                    "The registered reading: R0 missed, no reading; R0, R1, R2 and R5 met, the v1.10 pattern replicates; with R3 and R4 also met the names beat the instruction under both wordings; R3 met and R4 missed, the instruction wording matters; R3 missed, the v1.10 gap is not reliable; R1 missed, the names result does not replicate. No multiplicity correction; all intervals are descriptive.", "",
                                    table(["prediction", "result", "status"], pr), "", reading, "",
                                    f"Validation of the included files: {len(w2cov)} run files, every one with code hash `{WS2_HASH}` and a run seed from 30 to 39: {'yes' if not bad_files else 'NO (' + str(len(bad_files)) + ' files)'}.", ""]

    # --- 6i: how much practice does the model's own notebook need? (v1.12; exploratory)
    ds_rows = [r for r in (A.load(*ex(a.dose), complete_only=True) if ex(a.dose) else []) if 20 <= r["run_seed"] <= 39]
    if ds_rows and ws2_rows:
        import re as _re
        dcov = A.coverage(*ex(a.dose))
        kof = lambda r: int(_re.search(r"__p(\d+)__s", r["run"]).group(1))
        hm = "claude-haiku-5-5"
        rel = lambda rows, cond: [dict(r, condition=cond) for r in rows]
        rows_d = (rel([r for r in ds_rows if kof(r) == 1], "nb1") + rel([r for r in ds_rows if kof(r) == 3], "nb3") + rel([r for r in ds_rows if kof(r) == 6], "nb6")
                  + rel([r for r in ds_rows if kof(r) == 12], "nb12") + rel([r for r in rep_rows if r["condition"] == "notebook" and r["task"] == "stack" and kof(r) == 12], "nb12")
                  + rel([r for r in rep_rows + ws2_rows if r["condition"] == "none" and r["task"] == "stack"], "nb0")
                  + rel([r for r in ws_rows + ws2_rows if r["condition"] == "lm_names"], "names"))
        DN = {"nb0": "no memory", "nb1": "1 practice episode", "nb3": "3 practice episodes", "nb6": "6 practice episodes", "nb12": "12 practice episodes", "names": "the zero-practice reminder (frame + the four names)"}
        NAMES.update({k: "with " + v if k.startswith("nb") else "reads " + v for k, v in DN.items()})
        L += ["## 6i. Exploratory: how much practice does the model's own notebook need?", "",
              "Registered before any episode ran, and pushed to GitHub before the first one started (PROTOCOL.md v1.12). Claude Haiku 5.5, `stack` only, the notebook condition (the model rewrites its own notes after each practice episode, memory frozen for the four held-out episodes) after 1, 3 or 6 practice episodes on run seeds 20 to 39 and after 12 on run seeds 30 to 39; no memory and 12 episodes on run seeds 20 to 29 come from section 6c, the reminder from sections 6g and 6h. Every arm plays the same held-out layouts per run seed, so every comparison pairs. "
              f"Run files started {len(dcov)}, complete {sum(int(c['complete']) for c in dcov)} (planned 70). Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction), no multiplicity correction.", ""]
        pred_at_6i = len(L)

        def cell(rows, cond, seeds):
            x = [r for r in A.select(rows, model=hm, condition=cond, phase="eval", quirk=True) if r["task"] == "stack" and r["run_seed"] in seeds]
            return (f"{f(mean(x, 'success'), True)} ({mean(x, 'calls_to_success'):.1f} calls)", len({r["run_seed"] for r in x})) if x else ("-", 0)

        def per_run_cost(rows, cond, seeds):
            runs = {}
            for r in A.select(rows, model=hm, condition=cond, quirk=True):
                if r["phase"] == "eval_disturbed":
                    continue                      # the replication's 12-episode runs also played disturbed episodes; the dose runs did not
                if cond in ("nb0", "names") and r["phase"] != "eval":
                    continue                      # no memory and the reminder need no practice: only their held-out episodes are charged
                if r["task"] == "stack" and r["run_seed"] in seeds:
                    runs[r["run"]] = runs.get(r["run"], 0.0) + (r.get("cost_usd") or 0.0)
            return f"${np.mean(list(runs.values())):.3f}" if runs else "-"
        seeds_all, seeds_fresh = set(range(20, 40)), set(range(30, 40))
        order = ("nb0", "nb1", "nb3", "nb6", "nb12", "names")
        t1 = [(DN[c], *cell(rows_d, c, seeds_fresh), per_run_cost(rows_d, c, seeds_fresh)) for c in order]
        L += ["Run seeds 30 to 39 (10 runs, every dose exists):", "", table(["what the model has", "held-out success (calls to success)", "runs", "episode cost per run as recorded (practice, notebook writing and held-out; none and the reminder: held-out only)"], t1), ""]
        t2 = [(DN[c], *cell(rows_d, c, seeds_all), per_run_cost(rows_d, c, seeds_all)) for c in ("nb0", "nb1", "nb3", "nb6", "nb12", "names")]
        L += ["Run seeds 20 to 39 pooled (20 runs; the 12-episode notebooks are those of the replication on run seeds 20 to 29 and of this cell on 30 to 39):", "", table(["what the model has", "held-out success (calls to success)", "runs", "episode cost per run as recorded (practice, notebook writing and held-out; none and the reminder: held-out only)"], t2), ""]
        cmp_rows, vd3 = [], {}
        for x, y in (("nb1", "nb0"), ("nb3", "nb0"), ("nb6", "nb0"), ("nb12", "nb0"), ("nb3", "nb1"), ("nb6", "nb1"), ("nb6", "nb3"), ("nb12", "nb6"), ("nb12", "nb1"), ("nb12", "nb3"), ("names", "nb1"), ("names", "nb6"), ("names", "nb12")):
            d = A.paired_difference(rows_d, hm, x, y, tasks=["stack"])
            if d.get("n_pairs"):
                cmp_rows.append((f"{DN[x]} against {DN[y]}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
                vd3[(x, y)] = d
        L += ["Paired differences (run seed; the number of pairs says which run seeds each comparison could use):", "", table(["comparison", "pairs", "first", "second", "difference"], cmp_rows), ""]
        final3 = (ROOT / "logs/dose_done.txt").exists() or sum(int(c["complete"]) for c in dcov) == 70

        all_ready = all(vd3.get(k, {}).get("n_pairs", 0) >= 20 for k in (("nb1", "nb0"), ("nb3", "nb0"), ("nb6", "nb0"), ("nb6", "nb1"), ("nb12", "nb0"))) and len({r["run_seed"] for r in A.select(rows_d, model=hm, condition="nb12", phase="eval", quirk=True) if r["run_seed"] in seeds_fresh}) >= 10     # every dose must be complete before any prediction is scored

        def sc(keys, fn, need, n_over=None):
            n = n_over if n_over is not None else min([vd3.get(k, {}).get("n_pairs", 0) for k in keys] or [0])
            if n >= need and (all_ready or final3):
                return fn()
            if not final3:
                return "pending"
            return "inconclusive (below the registered floor)" if n < 0.8 * need else fn() + " (scored with fewer than the planned pairs, above the floor)"
        d1 = vd3.get(("nb12", "nb0"))
        d1r = [r for r in A.select(rows_d, model=hm, condition="nb12", phase="eval", quirk=True) if r["task"] == "stack" and r["run_seed"] in seeds_fresh]
        d1v = mean(d1r, "success") if d1r else float("nan")
        k1 = [r for r in A.select(rows_d, model=hm, condition="nb1", phase="eval", quirk=True) if r["task"] == "stack"]
        d2v = mean(k1, "success") if k1 else float("nan")
        d3, d4 = vd3.get(("nb6", "nb1")), vd3.get(("nb3", "nb0"))
        pr = [("D1: Haiku with 12 practice episodes solves at least 90% on run seeds 30 to 39", f"12 episodes {d1v * 100:.1f}%" if d1r else "no data", sc([("nb12", "nb0")], lambda: "met" if at_least(d1v, 0.90) else "MISSED", 10, n_over=len({r["run_seed"] for r in d1r})) if d1r else "pending"),
              ("D2: with 1 practice episode it solves at most 80% (pooled over 20 runs)", f"1 episode {d2v * 100:.1f}%" if k1 else "no data", sc([("nb1", "nb0")], lambda: "met" if at_most(d2v, 0.80) else "MISSED", 20)),
              ("D3: with 6 practice episodes it solves at least 10 points more than with 1 (pooled, paired)", f"{d3['diff'] * 100:+.1f}" if d3 else "no data", sc([("nb6", "nb1")], lambda: "met" if at_least(d3["diff"], 0.10) else "MISSED", 20)),
              ("D4: with 3 practice episodes it solves at least 20 points more than no memory (pooled, paired)", f"{d4['diff'] * 100:+.1f}" if d4 else "no data", sc([("nb3", "nb0")], lambda: "met" if at_least(d4["diff"], 0.20) else "MISSED", 20))]
        bad_files = [c for c in dcov if c.get("code") != DOSE_HASH or not isinstance(c.get("run_seed"), int) or not (30 if "__p12__" in str(c.get("file", "")) else 20) <= c["run_seed"] <= 39]
        bad_files += bad_cov(rcov, {"8fdcf6b2491b68a3"}) + bad_cov(A.coverage(*ex(a.wordsplit)), {WS_HASH}) + bad_cov(w2cov, {WS2_HASH}, 30, 39)          # the anchors (no memory, 12 episodes, the reminder) must validate too
        pr = void_if(bad_files, pr)
        st = [x[2] for x in pr]
        if final3 and not bad_files and all(x.startswith(("met", "MISSED")) for x in st):
            m = [x.startswith("met") for x in st]
            reading = ("D1 missed: the replication of the 12-episode notebook failed and nothing else is read." if not m[0] else
                       "a single practice episode already gives a notebook near the reminder's level (D2 missed)." if not m[1] else
                       "success rises with practice (D2 and D3 met); the dose at which it first reaches 90% is the answer and is read from the tables above." if m[2] else
                       "practice beyond one episode adds little on these layouts and the early episodes carry the effect (D2 met, D3 missed).")
            reading = "Registered reading of the outcome: " + reading + (" Three practice episodes pay for themselves against no memory (D4 met)." if m[3] else " Three practice episodes do not clear +20 points against no memory (D4 missed).")
        else:
            reading = "Registered reading: scored when the cell has finished."
        L[pred_at_6i:pred_at_6i] = ["**Predictions of PROTOCOL.md v1.12, scored by the generator first** (pending until every pair exists; below 80% of the planned runs inconclusive once the cell has finished). Written after the v1.11 results were known, so not blind. "
                                    "The registered reading: D1 missed, nothing else is read; D2 missed, one practice episode already gives a notebook near the reminder's level; D2 and D3 met, success rises with practice and the dose at which it first reaches 90% is the answer; D2 met and D3 missed, the early episodes carry the effect.", "",
                                    table(["prediction", "result", "status"], pr), "", reading, "",
                                    f"Validation of the included files: {len(dcov)} run files, every one with code hash `{DOSE_HASH}` and a run seed from 20 to 39 (30 to 39 for the 12-episode dose), plus the anchor files of the replication (`8fdcf6b2491b68a3`), the split (`{WS_HASH}`) and its repeat (`{WS2_HASH}`): {'yes' if not bad_files else 'NO (' + str(len(bad_files)) + ' files)'}.", ""]
        # within-k: how the dose curve looks when the budget is tight (descriptive, not registered)
        L += ["**Solved within k calls (descriptive, not registered).** An episode counts when it succeeded and used at most k tool calls, so the same episodes as above are scored against a tighter budget than the 20 calls the model was told. Run seeds 20 to 39 pooled, then run seeds 30 to 39 alone (every dose exists there):", ""]
        for title_, sd in (("Run seeds 20 to 39 pooled", seeds_all), ("Run seeds 30 to 39 only", seeds_fresh)):
            wk = []
            for c in ("nb0", "nb1", "nb3", "nb6", "nb12", "names"):
                x = [r for r in A.select(rows_d, model=hm, condition=c, phase="eval", quirk=True) if r["task"] == "stack" and r["run_seed"] in sd]
                if x:
                    wk.append((DN[c], len(x), *[f"{sum(1 for r in x if r['success'] and r['calls'] <= k)} ({sum(1 for r in x if r['success'] and r['calls'] <= k) / len(x) * 100:.0f}%)" for k in (8, 10, 12, 20)]))
            L += [f"{title_}:", "", table(["what the model has", "held-out episodes", "within 8 calls", "within 10", "within 12", "within 20 (the success above)"], wk), ""]
        sp = {}
        for r in A.select(rows_d, model=hm, condition="nb1", phase="eval", quirk=True):
            if r["task"] == "stack":
                sp.setdefault(r["run"], []).append(r)
        pr1 = {}
        for r in ds_rows:
            if kof(r) == 1 and r["phase"] == "practice" and r["idx"] == 0 and r["task"] == "stack":
                pr1[r["run"]] = bool(r["success"])
        solved_first = [(sum(1 for r in sp[k] if r["success"]), len(sp[k])) for k in sp if pr1.get(k) is True]
        failed_first = [(sum(1 for r in sp[k] if r["success"]), len(sp[k])) for k in sp if pr1.get(k) is False]
        if solved_first or failed_first:
            L += ["**By the outcome of the single practice episode (descriptive, not registered; runs on the corrected simulator with one practice episode, run seeds 20 to 39 as pooled above):** "
                  f"after a solved practice episode the held-out layouts were solved {sum(a_ for a_, _ in solved_first)} of {sum(b_ for _, b_ in solved_first)} times ({len(solved_first)} runs); after a failed practice episode {sum(a_ for a_, _ in failed_first)} of {sum(b_ for _, b_ in failed_first)} ({len(failed_first)} runs).", ""]

    # --- 6k: the same arms under a stated call budget (v1.14; exploratory)
    bud_rows = [r for r in (A.load(*ex(a.budget), complete_only=True) if ex(a.budget) else []) if 30 <= r["run_seed"] <= 39]
    if bud_rows:
        import re as _re
        bcov3 = A.coverage(*ex(a.budget))
        kofb = lambda r: int(_re.search(r"__p(\d+)__s", r["run"]).group(1))
        relb = lambda rows, cond: [dict(r, condition=cond, phys_success=int(r["success"]), success=registered_solved(r)) for r in rows]          # registered rule (v1.14): an episode that never calls `done` in time is a failure; the simulator's own verdict is kept as phys_success
        rows_b = (relb([r for r in bud_rows if r["condition"] == "none"], "b_none") + relb([r for r in bud_rows if r["condition"] == "lm_names"], "b_names")
                  + relb([r for r in bud_rows if r["condition"] == "notebook" and kofb(r) == 1], "b_nb1") + relb([r for r in bud_rows if r["condition"] == "notebook" and kofb(r) == 12], "b_nb12"))
        BN = {"b_none": "no memory", "b_names": "the frame and the four names", "b_nb1": "own notebook, 1 practice episode", "b_nb12": "own notebook, 12 practice episodes"}
        NAMES.update(BN)
        mods = [m for m in ("claude-haiku-5-5", "gpt-6-luna") if any(r["model"] == m for r in rows_b)]
        jobs = ("stack", "bins", "flasks")
        L += ["## 6k. Exploratory: the same arms with the call budget stated to the model (12 calls)", "",
              "Registered before any episode ran, and pushed to GitHub before the first one started (PROTOCOL.md v1.14, branch `budget`, tag `code-budget`). The system prompt says \"at most 12 tool calls in total\" (the practice episodes run under the same budget), so an episode that has not called `done` in time is a failure. Haiku 5.5 and Luna, all three jobs, run seeds 30 to 39, four held-out episodes per run. "
              f"Run files started {len(bcov3)}, complete {sum(int(c['complete']) for c in bcov3)} (planned 240). Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction), paired by (job, run seed), no multiplicity correction. The shortest possible `bins` episode takes 9 calls, `stack` and `flasks` 5.", ""]
        pred_at_6k = len(L)
        trows = []
        for m in mods:
            for t in jobs:
                for c in ("b_none", "b_names", "b_nb1", "b_nb12"):
                    x = [r for r in A.select(rows_b, model=m, condition=c, phase="eval", quirk=True) if r["task"] == t]
                    if x:
                        suc = [r for r in x if r["success"]]
                        ph = sum(1 for r in x if r["phys_success"])
                        trows.append((m, t, BN[c], len(x), f"{len(suc)} ({len(suc) / len(x) * 100:.0f}%)", f"{np.mean([r['calls'] for r in suc]):.1f}" if suc else "-", f"{sum(1 for r in suc if r['calls'] <= 10)}", f"{ph} ({ph / len(x) * 100:.0f}%)", f"{sum(1 for r in x if not r.get('claimed_done'))}"))
        L += ["**Solved** is the registered rule: the simulator's verdict is success **and** the model called `done` within the stated 12 calls. The simulator's own verdict without the `done` condition is shown separately (it is a different outcome: the job was physically finished but the model never said so within the budget). Columns: held-out episodes solved; calls used by those; solved within 10 calls; the simulator's verdict alone; episodes that never called `done`:", "",
              table(["model", "job", "what the model has", "episodes", "solved (registered rule)", "calls of the solved", "solved within 10", "simulator verdict alone", "never called `done`"], trows), ""]
        cmp_b, vb = [], {}
        for m in mods:
            for t in jobs:
                for x_, y_ in (("b_nb12", "b_names"), ("b_names", "b_none"), ("b_nb1", "b_none"), ("b_nb12", "b_none"), ("b_nb12", "b_nb1")):
                    d = A.paired_difference(rows_b, m, x_, y_, tasks=[t])
                    if d.get("n_pairs"):
                        cmp_b.append((m, t, f"{BN[x_]} against {BN[y_]}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
                        vb[(m, t, x_, y_)] = d
        L += ["Paired differences (run seed, per model and job):", "", table(["model", "job", "comparison", "pairs", "first", "second", "difference"], cmp_b), ""]
        finalb = (ROOT / "logs/budget_done.txt").exists() or (len(bcov3) == 240 and all(c["complete"] for c in bcov3))

        ready_b = all(vb.get((m, t, x_, y_), {}).get("n_pairs", 0) >= 10 for m in ("claude-haiku-5-5", "gpt-6-luna") for t in jobs for x_, y_ in (("b_nb12", "b_names"), ("b_names", "b_none"), ("b_nb1", "b_none"), ("b_nb12", "b_none")))          # every model, job and arm must be complete before any prediction is scored

        def scb(keys, fn):
            n = min([vb.get(k, {}).get("n_pairs", 0) for k in keys] or [0])
            if n >= 10 and (ready_b or finalb):
                return fn()
            if not finalb:
                return "pending"
            return "inconclusive (below the registered floor)" if n < 8 else fn() + " (scored with fewer than the planned pairs, above the floor)"
        H, Lu = "claude-haiku-5-5", "gpt-6-luna"
        kb = lambda m, t: (m, t, "b_nb12", "b_names")
        pr = []
        d_b1 = vb.get(kb(H, "stack"))
        pr.append(("B1: Haiku `stack`, own notebook (12) minus the names list is at most +10 points", f"{d_b1['diff'] * 100:+.1f}" if d_b1 else "no data", scb([kb(H, "stack")], lambda: "met" if at_most(d_b1["diff"], 0.10) else "MISSED")))
        for tag, job in (("B2", "flasks"), ("B3", "bins")):
            dh, dl = vb.get(kb(H, job)), vb.get(kb(Lu, job))
            res = " / ".join(f"{nm} {d['diff'] * 100:+.1f}" if d else f"{nm} no data" for nm, d in (("Haiku", dh), ("Luna", dl)))
            pr.append((f"{tag}: `{job}`, notebook (12) minus the names list is at least +30 points for Haiku and for Luna", res,
                       scb([kb(H, job), kb(Lu, job)], lambda: "met" if (at_least(dh["diff"], 0.30) and at_least(dl["diff"], 0.30)) else ("MISSED (Haiku only)" if at_least(dl["diff"], 0.30) else "MISSED (Luna only)" if at_least(dh["diff"], 0.30) else "MISSED (both)"))))
        bad_files = bad_cov(bcov3, {BUD_HASH}, 30, 39)
        pr = void_if(bad_files, pr)
        st = [x[2] for x in pr]
        if finalb and not bad_files and all(x.startswith(("met", "MISSED")) for x in st):
            reading = reading_budget(st)
            reading = "Registered reading of the outcome: " + reading
        else:
            reading = "Registered reading: scored when the cell has finished."
        L[pred_at_6k:pred_at_6k] = ["**Predictions of PROTOCOL.md v1.14, scored by the generator first** (pending until every pair exists; below 8 of 10 pairs inconclusive once the cell has finished). Written after the within-10-calls counts of section 6l were known, so not blind. "
                                    "The registered reading: B1, B2 and B3 all met, a list of settings is enough where the catch is a choice among named values and not where the model has to find a number, so the notebook's value is the stored value; B1 missed, the list does not match the notebook even on `stack` at this budget; B2 or B3 missed for a model, the notebook's efficiency advantage is not confirmed for that job and model (each reported separately).", "",
                                    table(["prediction", "result", "status"], pr), "", reading, "",
                                    f"Validation of the included files: {len(bcov3)} run files, every one with code hash `{BUD_HASH}` and a run seed from 30 to 39: {'yes' if not bad_files else 'NO (' + str(len(bad_files)) + ' files)'}.", ""]

    # --- 6m: the two-sided job (v1.15; exploratory)
    mix_rows = [r for r in (A.load(*ex(a.mixed), complete_only=True) if ex(a.mixed) else []) if 40 <= r["run_seed"] <= 49 and r["task"] == "mixed"]
    if mix_rows:
        import re as _re
        mcov = A.coverage(*ex(a.mixed))
        kofm = lambda r: int(_re.search(r"__p(\d+)__s", r["run"]).group(1))
        rows_m = [dict(r, condition="nb12" if r["condition"] == "notebook" else r["condition"]) for r in mix_rows if r["condition"] != "notebook" or kofm(r) == 12]
        MN = {"none": "no memory", "lm_names": "the frame and the four names", "lm_firm": "constant rule: firm for every cube", "lm_proc": "answer key: try, read, switch", "nb12": "own notebook, 12 practice episodes"}
        mm = [m for m in ("claude-haiku-5-5", "gpt-6-luna") if any(r["model"] == m for r in rows_m)]
        L += ["## 6m. Exploratory: a job where no single setting works (the `mixed` job)", "",
              "Registered before any episode ran, and pushed to GitHub before the first one started (PROTOCOL.md v1.15, branch `two-sided`, tag `code-mixed`). The job is `stack` with two odd cubes: in every layout one of `cube_green` and `cube_blue` is heavy and slippery (it needs `grip_level firm`) and the other is fragile (a firm grip makes the hand let go with a squeeze-limit message); which is which is drawn from the layout seed and never shown. "
              "The scripted gate (`results/gate_mixed.md`, 100 layouts, no model): every fixed pick setting solves 0 or 1 of 100 catch layouts and all 100 control layouts; a player that reads each result and switches grips solves 96 of 100. Haiku 5.5 and Luna, run seeds 40 to 49, four held-out episodes per run, 20 calls. "
              f"Run files started {len(mcov)}, complete {sum(int(c['complete']) for c in mcov)} (planned 140). Unadjusted 95% intervals by the project's interval rule, paired by run seed, no multiplicity correction, never pooled with registered rows.", ""]
        pred_at_6m = len(L)
        mrows = []
        for m in mm:
            for quirk in (True, False):
                for c in ("none", "lm_names", "lm_firm", "lm_proc", "nb12"):
                    x = A.select(rows_m, model=m, condition=c, phase="eval", quirk=quirk)
                    if x:
                        suc = [r for r in x if r["success"]]
                        mrows.append((m, "catch (one heavy, one fragile)" if quirk else "control (two ordinary cubes)", MN[c], len(x), f"{len(suc)} ({len(suc) / len(x) * 100:.0f}%)",
                                      f"{np.mean([r['calls'] for r in suc]):.1f}" if suc else "-", f"{sum(1 for r in x if r['squeezed'] > 0)} ({sum(1 for r in x if r['squeezed'] > 0) / len(x) * 100:.0f}%)",
                                      f"{sum(1 for r in x if r['silent_pick'] > 0)} ({sum(1 for r in x if r['silent_pick'] > 0) / len(x) * 100:.0f}%)"))
        L += ["Columns: held-out episodes; solved (the simulator's verdict); calls used by the solved episodes; episodes with at least one squeeze-limit refusal (the hand pressed too hard on the fragile cube); episodes with at least one silent failed pick (a cube slipped out of the grip with no error message).", "",
              table(["model", "scene", "what the model has", "episodes", "solved", "calls of the solved", "with a squeeze refusal", "with a silent failed pick"], mrows), ""]
        cmp_m, vm = [], {}
        for m in mm:
            for x_, y_, qk in (("lm_firm", "none", True), ("lm_names", "none", True), ("lm_proc", "none", True), ("nb12", "none", True), ("nb12", "lm_proc", True), ("lm_names", "lm_proc", True), ("lm_proc", "none", False)):
                d = A.paired_difference(rows_m, m, x_, y_, quirk=qk)
                if d.get("n_pairs"):
                    cmp_m.append((m, "catch" if qk else "control", f"{MN[x_]} against {MN[y_]}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
                    vm[(m, x_, y_, qk)] = d
        L += ["Paired differences (run seed, per model):", "", table(["model", "scene", "comparison", "pairs", "first", "second", "difference"], cmp_m), ""]
        finalm = (ROOT / "logs/mixed_done.txt").exists() or (len(mcov) == 140 and all(c["complete"] for c in mcov))
        need_m = [(x_, y_, qk) for x_, y_, qk in (("lm_firm", "none", True), ("lm_names", "none", True), ("lm_proc", "none", True), ("nb12", "none", True), ("nb12", "lm_proc", True), ("lm_names", "lm_proc", True), ("lm_proc", "none", False))]
        ready_m = all(vm.get((m, x_, y_, qk), {}).get("n_pairs", 0) >= 10 for m in ("claude-haiku-5-5", "gpt-6-luna") for x_, y_, qk in need_m)

        def scm(keys, fn):
            n = min([vm.get(k, {}).get("n_pairs", 0) for k in keys] or [0])
            if n >= 10 and (ready_m or finalm):
                return fn()
            if not finalm:
                return "pending"
            return "inconclusive (below the registered floor)" if n < 8 else fn() + " (scored with fewer than the planned pairs, above the floor)"
        H, Lu = "claude-haiku-5-5", "gpt-6-luna"
        rate = lambda m, c, qk=True: (lambda x: (sum(r["success"] for r in x) / len(x)) if x else float("nan"))(A.select(rows_m, model=m, condition=c, phase="eval", quirk=qk))
        both = lambda fn: all(fn(m) for m in (H, Lu))
        dd = lambda m, x_, y_, qk=True: vm.get((m, x_, y_, qk), {}).get("diff", float("nan"))
        show = lambda fn: " / ".join(f"{nm} {fn(m)}" for nm, m in (("Haiku", H), ("Luna", Lu)))
        pr = []
        pr.append(("M1: `lm_firm` solves at most 25% of the catch layouts for Haiku and Luna", show(lambda m: f"{rate(m, 'lm_firm') * 100:.0f}%"),
                   scm([(m, "lm_firm", "none", True) for m in (H, Lu)], lambda: "met" if both(lambda m: at_most(rate(m, "lm_firm"), 0.25)) else "MISSED")))
        pr.append(("M2: `none` solves less than 60% of the catch layouts for Haiku and Luna (room check)", show(lambda m: f"{rate(m, 'none') * 100:.0f}%"),
                   scm([(m, "lm_firm", "none", True) for m in (H, Lu)], lambda: "met" if both(lambda m: not at_least(rate(m, "none"), 0.60)) else "MISSED")))
        pr.append(("M3: `lm_proc` minus `none` is at least +20 points for Haiku and Luna", show(lambda m: f"{dd(m, 'lm_proc', 'none') * 100:+.1f}"),
                   scm([(m, "lm_proc", "none", True) for m in (H, Lu)], lambda: "met" if both(lambda m: at_least(dd(m, "lm_proc", "none"), 0.20)) else "MISSED")))
        pr.append(("M4: own notebook (12) minus `none` is at least +15 points for at least one model, and the notebook is not above `lm_proc` for either", show(lambda m: f"vs none {dd(m, 'nb12', 'none') * 100:+.1f}, vs lm_proc {dd(m, 'nb12', 'lm_proc') * 100:+.1f}"),
                   scm([(m, "nb12", "none", True) for m in (H, Lu)] + [(m, "nb12", "lm_proc", True) for m in (H, Lu)],
                       lambda: "met" if (any(at_least(dd(m, "nb12", "none"), 0.15) for m in (H, Lu)) and both(lambda m: at_most(dd(m, "nb12", "lm_proc"), 0.0))) else "MISSED")))
        pr.append(("M5: in the control scene `lm_proc` solves at least 80% for both models and is within 10 points of `none`", show(lambda m: f"{rate(m, 'lm_proc', False) * 100:.0f}% (difference {dd(m, 'lm_proc', 'none', False) * 100:+.1f})"),
                   scm([(m, "lm_proc", "none", False) for m in (H, Lu)], lambda: "met" if both(lambda m: at_least(rate(m, "lm_proc", False), 0.80) and at_most(abs(dd(m, "lm_proc", "none", False)), 0.10)) else "MISSED")))
        pr.append(("M6: `lm_names` is not above `lm_proc` for either model", show(lambda m: f"{dd(m, 'lm_names', 'lm_proc') * 100:+.1f}"),
                   scm([(m, "lm_names", "lm_proc", True) for m in (H, Lu)], lambda: "met" if both(lambda m: at_most(dd(m, "lm_names", "lm_proc"), 0.0)) else "MISSED")))
        bad_files = bad_cov(mcov, {MIX_HASH}, 40, 49)
        pr = void_if(bad_files, pr)
        st = [x[2] for x in pr]
        if finalm and not bad_files and all(x.startswith(("met", "MISSED")) for x in st):
            reading = "Registered reading of the outcome: " + reading_mixed(st)
        else:
            reading = "Registered reading: scored when the cell has finished."
        L[pred_at_6m:pred_at_6m] = ["**Predictions of PROTOCOL.md v1.15, scored by the generator first** (pending until every pair exists; below 8 of 10 pairs inconclusive once the cell has finished). Written after the scripted gate and after v1.12 to v1.14, so not blind to the earlier findings. "
                                    "If M2 is missed for a model there is no room for it: M3 to M5 are then reported but not read for that model.", "",
                                    table(["prediction", "result", "status"], pr), "", reading, "",
                                    f"Validation of the included files: {len(mcov)} run files, every one with code hash `{MIX_HASH}` and a run seed from 40 to 49: {'yes' if not bad_files else 'NO (' + str(len(bad_files)) + ' files)'}.", ""]

    # --- 6l: solved within k calls, every arm (descriptive; round 5g)
    wk_src = {"none": [r for r in rep_rows if r["condition"] == "none"], "notebook": [r for r in rep_rows if r["condition"] == "notebook"],
              "hint": [r for r in hp_rows if r["condition"] == "hint"], "hint_generic": [r for r in hp_rows if r["condition"] == "hint_generic"],
              "lm_generic": [r for r in lm_rows if r["condition"] == "lm_generic"], "lm_specific": [r for r in lm_rows if r["condition"] == "lm_specific"]}
    if all(wk_src.values()):
        WKN = {"none": "no memory", "hint_generic": "generic sentence (operator label)", "lm_generic": "generic sentence (neutral label)", "hint": "naming sentence (operator label)", "lm_specific": "naming sentence (neutral label)", "notebook": "own notebook (12 practice episodes)"}
        wrows = []
        for m in cheap:
            for t in ("stack", "bins", "flasks"):
                for c in ("none", "hint_generic", "lm_generic", "hint", "lm_specific", "notebook"):
                    x = [r for r in wk_src[c] if r["model"] == m and r["task"] == t and r["phase"] == "eval" and r["quirk"]]
                    if x:
                        cnt = {k: sum(1 for r in x if r["success"] and r["calls"] <= k) for k in (8, 10, 12, 20)}
                        wrows.append((m, t, WKN[c], len(x), *[f"{cnt[k]} ({cnt[k] / len(x) * 100:.0f}%)" for k in (8, 10, 12, 20)]))
        L += ["## 6l. Exploratory: solved within k calls, every arm of the replication (run seeds 20 to 29)", "",
              "Descriptive and **not registered**: it was added after round 5g of the review showed that the 20-call success rate hides differences in efficiency. An episode counts as solved within k calls when it succeeded and its logged call count (including `observe`) is at most k; the model was told 20 calls, not k, so this scores the same episodes against a tighter budget than the model saw. An episode that never calls `done` uses the whole 20-call budget, so for k below 20 \"solved within k\" also implies that `done` was called. Section 6k (when present) repeats the question with the budget stated to the model. "
              "Held-out episodes only, 40 per cell (10 runs of 4 layouts, the same layouts in every arm of a model and job).", "",
              table(["model", "job", "what the model has", "episodes", "within 8 calls", "within 10", "within 12", "within 20 (the success rate)"], wrows), ""]

    # --- 6j: the split with a second model (v1.13; exploratory)
    sec_rows = [r for r in (A.load(*ex(a.second), complete_only=True) if ex(a.second) else []) if 30 <= r["run_seed"] <= 39 and r["model"] == "claude-sonnet-5-5"]
    if sec_rows:
        scov = A.coverage(*ex(a.second))
        sm = "claude-sonnet-5-5"
        SN = {"none": "no memory", "lm_frame": "the frame only", "lm_names": "the frame and the four names", "lm_instr_n": "the frame and 'change the settings one at a time' (no names)", "lm_generic": "the generic sentence"}
        NAMES.update({k: ("starts fresh" if k == "none" else "reads " + v + " (neutral label)") for k, v in SN.items()})
        L += ["## 6j. Exploratory: the split with a second model (Claude Sonnet 5.5)", "",
              "Registered before any episode ran, and pushed to GitHub before the first one started (PROTOCOL.md v1.13, branch `second-model`, tag `code-second`). Only Haiku has room on `stack`, so this was a **room check first**: Sonnet 5.5 with no memory on run seeds 30 to 39 (the layouts of section 6h); the four text arms ran only because it solved at most 75%. "
              f"Run files started {len(scov)}, complete {sum(int(c['complete']) for c in scov)}. Unadjusted 95% intervals by the project's interval rule (the wider of a cluster bootstrap, a stratified t and a binomial noise floor; no multiplicity correction), ten pairs per comparison.", ""]
        pred_at_6j = len(L)
        order = ("none", "lm_frame", "lm_names", "lm_instr_n", "lm_generic")
        ks = None
        for c in order:
            kc = {r["run_seed"] for r in A.select(sec_rows, model=sm, condition=c, phase="eval", quirk=True)}
            ks = kc if ks is None else ks & kc
        ks = ks or set()
        cells = []
        for c in order:
            x = [r for r in A.select(sec_rows, model=sm, condition=c, phase="eval", quirk=True) if r["run_seed"] in ks]
            cells.append(f"{f(mean(x, 'success'), True)} ({mean(x, 'calls_to_success'):.1f} calls)" if x else "-")
        nn = A.select(sec_rows, model=sm, condition="none", phase="eval", quirk=True)
        L += [f"Held-out success on `stack` (and calls to success) on the {len(ks)} runs every arm has:", "", table(["", *[SN[c] for c in order]], [("Sonnet 5.5", *cells)]), ""]
        cmp_rows, vd4 = [], {}
        for x, y in [(c, "none") for c in order[1:]] + [("lm_names", "lm_frame"), ("lm_names", "lm_instr_n"), ("lm_generic", "lm_instr_n")]:
            d = A.paired_difference(sec_rows, sm, x, y, tasks=["stack"])
            if d.get("n_pairs"):
                cmp_rows.append((f"{SN[x]} against {SN[y]}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
                vd4[(x, y)] = d
        L += ["Paired differences (run seed):", "", table(["comparison", "pairs", "first", "second", "difference"], cmp_rows), ""]
        # descriptive, not registered: the same arms scored within 10 of the 20 calls (the lens of sections 6l and 6k)
        w10 = [dict(r, success=int(bool(r["success"]) and bool(r["claimed_done"]) and r["calls"] <= 10)) for r in sec_rows]
        w10_cells = []
        for c in order:
            x = [r for r in A.select(w10, model=sm, condition=c, phase="eval", quirk=True) if r["run_seed"] in ks]
            w10_cells.append(f"{sum(r['success'] for r in x)} of {len(x)}" if x else "-")
        w10_rows = []
        for x_, y_ in [(c, "none") for c in order[1:]] + [("lm_names", "lm_instr_n"), ("lm_names", "lm_frame")]:
            d = A.paired_difference(w10, sm, x_, y_, tasks=["stack"])
            if d.get("n_pairs"):
                w10_rows.append((f"{SN[x_]} against {SN[y_]}", d["n_pairs"], f(d["a"], True), f(d["b"], True), ci(d, pct=True)))
        L += ["**Solved within 10 calls (descriptive, not registered; added after round 5h).** The same episodes, counted as solved when the simulator says success, the model called `done`, and it used at most 10 of its 20 calls:", "",
              table(["", *[SN[c] for c in order]], [("Sonnet 5.5", *w10_cells)]), "", table(["comparison", "pairs", "first", "second", "difference"], w10_rows), ""]
        none_rate = mean(nn, "success") if nn else float("nan")
        gate = bool(nn) and len({r["run_seed"] for r in nn}) >= 10 and at_most(none_rate, 0.75)
        gate_failed = bool(nn) and len({r["run_seed"] for r in nn}) >= 10 and not at_most(none_rate, 0.75)          # registered: stage 2 must not have run, and nothing below is scored
        final4 = (ROOT / "logs/second_done.txt").exists() or gate_failed or all(vd4.get((c, "none"), {}).get("n_pairs", 0) >= 10 for c in order[1:])

        def sc4(keys, fn):
            n = min([vd4.get(k, {}).get("n_pairs", 0) for k in keys] or [0])
            if n >= 10:
                return fn()
            if not final4:
                return "pending"
            return "inconclusive (below the registered floor)" if n < 8 else fn() + " (scored with fewer than the planned pairs, above the floor)"
        allk = [(c, "none") for c in order[1:]]
        g4 = lambda c: vd4.get((c, "none"))
        q1, q2, q3, q4 = g4("lm_names"), g4("lm_frame"), g4("lm_generic"), vd4.get(("lm_names", "lm_instr_n"))
        pr = [("Gate: Sonnet 5.5 with no memory solves at most 75% of the 40 layouts (room for the second model)", f"no memory {f(none_rate, True)}" if nn else "no data", "met" if gate else ("MISSED (stage 2 must not have run)" if nn and len({r['run_seed'] for r in nn}) >= 10 else "pending")),
              ("Q1: `lm_names` solves at least 80%", f"{f(q1['a'], True)}" if q1 else "no data", sc4(allk, lambda: "met" if at_least(q1["a"], 0.80) else "MISSED")),
              ("Q2: `lm_frame` solves at most 65%", f"{f(q2['a'], True)}" if q2 else "no data", sc4(allk, lambda: "met" if at_most(q2["a"], 0.65) else "MISSED")),
              ("Q3: `lm_generic` solves at least 80%", f"{f(q3['a'], True)}" if q3 else "no data", sc4(allk, lambda: "met" if at_least(q3["a"], 0.80) else "MISSED")),
              ("Q4: `lm_names` minus `lm_instr_n` is at least +10 points (reported either way)", f"{q4['diff'] * 100:+.1f}" if q4 else "no data", sc4(allk + [("lm_names", "lm_instr_n")], lambda: "met" if at_least(q4["diff"], 0.10) else "MISSED"))]
        bad_files = bad_cov(scov, {SEC_HASH}, 30, 39)
        pr = void_if(bad_files, pr)
        if gate_failed:
            pr = [pr[0]] + [(a_, b_, "void (the room gate failed)") for a_, b_, _ in pr[1:]]
        st = [x[2] for x in pr]
        if gate_failed:
            reading = "Registered reading of the outcome: " + reading_second(st, True)
        elif final4 and not bad_files and all(x.startswith(("met", "MISSED")) for x in st):
            m = [x.startswith("met") for x in st]
            reading = "Registered reading of the outcome: " + reading_second(st, False)
            if m[0] and m[1] and not (m[2] and m[3]) and q1 and q2 and q3 and q4:
                reading += (f"\n\n**What the numbers show (written after seeing them, not registered).** With Sonnet 5.5 no memory solved {f(none_rate, True)}; "
                            f"{sum(1 for c in order[1:] if vd4.get((c, 'none')) and vd4[(c, 'none')]['lo'] > 0)} had an interval over no memory that excludes zero (of the four text arms), and the frame alone already reached {f(q2['a'], True)} (over fresh {ci(q2, pct=True)}) and the arms' intervals overlap. The four names alone reached {f(q1['a'], True)} and the instruction with the word \"settings\" and no names reached "
                            f"{f(q4['b'], True)}: names minus instruction is {ci(q4, pct=True)}, the opposite sign from Haiku's pooled +27.5 points. So for a second model on this job the data do not separate what the parts of the sentence do, and the names-over-instruction ordering is not shown to hold beyond Haiku; ten pairs per comparison and one job.")
        else:
            reading = "Registered reading: scored when the cell has finished."
        L[pred_at_6j:pred_at_6j] = ["**Predictions of PROTOCOL.md v1.13, scored by the generator first** (pending until every pair exists; below 8 of 10 pairs inconclusive once the cell has finished). Written after the Haiku results were known, so not blind. "
                                    "The registered reading: gate failed, no reading, ceiling reported; Q1, Q2 and Q3 met, the Haiku pattern also holds for a second model; Q1 missed, the names result is Haiku-specific; Q4 reported either way.", "",
                                    table(["prediction", "result", "status"], pr), "", reading, "",
                                    f"Validation of the included files: {len(scov)} run files, every one with code hash `{SEC_HASH}` and a run seed from 30 to 39: {'yes' if not bad_files else 'NO (' + str(len(bad_files)) + ' files)'}.", ""]

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
        for c in ("none", "notebook", "replay"):
            for ph, ph_name in (("eval", "clean"), ("eval_disturbed", "disturbed")):
                x = A.select(skills, model=m, condition=c, phase=ph, quirk=True)
                if x:
                    fc.append((m, NAMES[c], ph_name, len(x), f(mean(x, "claimed_done"), True), f"{sum(r['false_claim'] for r in x)} ({f(sum(r['false_claim'] for r in x) / len(x), True)})"))
    allx = {m: [r for r in skills if r["model"] == m and r["phase"] in ("eval", "eval_disturbed") and r["quirk"] and r["condition"] in ("none", "notebook", "replay")] for m in cheap}
    L += ["## 8. Saying 'done' when the job is not done", "",
          "Held-out catch-scene episodes, clean and disturbed separately (the disturbed ones are only played by the no-memory, notebook and replay arms that have a disturbed evaluation):", "",
          table(["model", "memory", "evaluation", "episodes", "said done", "said done but the simulator disagreed"], fc), "",
          "Over all held-out catch-scene episodes of the registered conditions (no memory, notebook, replay): " + "; ".join(f"{m}: {sum(r['false_claim'] for r in x)} of {len(x)} ({f(sum(r['false_claim'] for r in x) / len(x), True)})" for m, x in allx.items() if x) + ".", ""]

    dev = ROOT / "results/deviations.md"
    L += ["## 9. Deviations from the protocol", "", dev.read_text() if dev.exists() else "None recorded.", ""]
    Path(a.out).write_text("\n".join(L))
    Path(a.img).mkdir(parents=True, exist_ok=True)
    if cheap and any(r["phase"] == "practice" for r in skills):
        learning_chart([r for r in skills if r["quirk"]], cheap, Path(a.img) / "learning_curves.png")
    print("\n".join(L)[:3000])


if __name__ == "__main__":
    main()

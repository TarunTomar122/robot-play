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
NAMES = {"none": "starts fresh", "notebook": "keeps a notebook", "replay": "sees its last success"}


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


def mean(rows, key):
    return float(np.mean([r[key] for r in rows])) if rows else float("nan")


def learning_chart(rows, models, out):
    fig, axes = plt.subplots(len(models), 3, figsize=(13, 3.6 * len(models)), sharey=True, facecolor=SURFACE, squeeze=False)
    for i, m in enumerate(models):
        for j, t in enumerate(TASKS):
            ax = axes[i][j]
            ax.set_facecolor(SURFACE)
            for c in ("none", "notebook", "replay"):
                cur = A.curve([r for r in rows if r["task"] == t], m, c, "success", n_boot=500)
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
    ap.add_argument("--meter", default="runs/spend")
    ap.add_argument("--out", default="results/RESULTS.md")
    ap.add_argument("--img", default="docs/img")
    a = ap.parse_args()
    ex = lambda ds: [d for d in ds if Path(d).exists()]
    dirs = ex(a.main + a.control + a.frontier + a.pose)
    rows = A.load(*dirs, complete_only=True)                          # confirmatory numbers use runs that finished their whole plan
    cov = A.coverage(*dirs)
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
    hashes = sorted({c.get("code") or "unknown" for c in cov})
    L += [(f"Code: every analysed run file carries the same code hash, `{hashes[0]}`." if len(hashes) == 1 else
           f"**Code: the run files carry {len(hashes)} different code hashes ({', '.join(hashes)}). This is a deviation from the protocol: say which cells ran on which code before reading any comparison across them.**"), ""]
    try:                                                 # planned run files that were never created (a cell that never started shows up here, not only in a smaller table)
        from robot_play.runner import build_specs
        cheap_m, front_m = ["claude-haiku-5-5", "gpt-6-luna"], ["claude-fable-5-2", "gpt-6-astra"]
        planned = [("main", cheap_m, range(10), "runs/main"), ("control", cheap_m, range(10), "runs/control"), ("frontier", front_m, [0], "runs/frontier"),
                   ("frontier_exp", ["claude-fable-5-2"], range(5), "runs/frontier_exp"), ("pose", cheap_m, range(3), "runs/pose")]
        missing = {}
        for cell, ms, seeds, d in planned:
            specs = build_specs(cell, ms, list(seeds), d)
            n_missing = sum(1 for sp in specs if not sp.path.exists())
            if n_missing:
                missing[cell] = f"{n_missing} of {len(specs)} planned run files were never created"
        L += ["Planned cells that did not start: " + ("; ".join(f"{k}: {v}" for k, v in missing.items()) if missing else "none (every planned run file exists)."), ""]
    except Exception:                                    # noqa: BLE001
        pass
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
          f"whose cheap-arm variance carries the design effect fixed in PROTOCOL.md (max(2, 1 + 3 x rho), rho measured on that cheap model's own held-out outcomes; the frontier arm has none), so it does not shrink to zero when every episode succeeds. Fewer than {MIN_Q3_CLUSTERS} of 15 complete clusters is inconclusive. A frontier first try below {int(100 * FRONTIER_FLOOR)}% is not treated as a target. The rows with no memory show how much of the gap the notebook closes (exploratory, 95%).", ""]
    q3, q3c = [], []
    for fr in [m for m in models if m in ("claude-fable-5-2", "gpt-6-astra")]:
        for ch in cheap:
            for cc in ("notebook", "none"):
                g = A.q3_gap(skills, fr, ch, cheap_condition=cc, alpha=A.ALPHA_Q3 if cc == "notebook" else 0.05)
                if not g.get("n_layouts"):
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

    # --- pose
    if pose:
        L += ["## 6. Skill-level against pose-level tools", "", "Pose-level runs have no `pick` or `place`: the model builds them from `move_to` and the gripper, with three times the call budget.", ""]
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
    L += ["## 7. Saying 'done' when the job is not done", "", table(["model", "held-out episodes", "said done", "said done but the simulator disagreed"], fc), ""]

    dev = ROOT / "results/deviations.md"
    L += ["## 8. Deviations from the protocol", "", dev.read_text() if dev.exists() else "None recorded.", ""]
    Path(a.out).write_text("\n".join(L))
    Path(a.img).mkdir(parents=True, exist_ok=True)
    if cheap and any(r["phase"] == "practice" for r in skills):
        learning_chart([r for r in skills if r["quirk"]], cheap, Path(a.img) / "learning_curves.png")
    print("\n".join(L)[:3000])


if __name__ == "__main__":
    main()

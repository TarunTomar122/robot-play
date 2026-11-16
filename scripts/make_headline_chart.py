"""The headline chart: held-out success per job for each cheap model with no memory, its own notebook and a replay of its last success, with the frontier models' first try as horizontal lines.
Bars: pooled over run seeds; error bars: 95%, the wider of the cluster bootstrap (resampling runs inside each job, 10,000 resamples) and a binomial sampling-noise floor, so a bar at 100% still shows the uncertainty of the episodes behind it.
  python scripts/make_headline_chart.py --out docs/img/headline.png"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robot_play import analysis as A      # noqa: E402

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
COND = [("none", "No memory", "#2a78d6"), ("notebook", "Its own notebook", "#eb6834"), ("replay", "A replay of its last success", "#1baf7a")]
JOBS = [("stack", "Stack"), ("bins", "Sort"), ("flasks", "Flasks")]
FRONT = [("claude-fable-5-2", "Fable 5.2 first try"), ("gpt-6-astra", "GPT-6 Astra first try")]


def stat(rows, model, cond, task):
    by = {}
    for r in A.select(rows, model=model, condition=cond, phase="eval", quirk=True):
        if r["task"] == task and r.get("toolset") in (None, "skills"):
            by.setdefault(r["run_seed"], []).append(r["success"])
    if not by:
        return None
    clusters = [np.array(v, dtype=float) for v in by.values()]
    est, lo, hi = A.bootstrap(clusters, np.mean, 10_000)
    n = int(sum(len(c) for c in clusters))
    half = A._floor_half([(int(sum(c.sum() for c in clusters)), n)], 0.05)
    lo, hi = (min(lo, est - half), max(hi, est + half)) if lo == lo else (est - half, est + half)
    return est, max(0.0, lo), min(1.0, hi), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="*", default=["runs/main", "runs/frontier"])
    ap.add_argument("--out", default="docs/img/headline.png")
    a = ap.parse_args()
    rows = A.load(*[d for d in a.dirs if Path(d).exists()], complete_only=True)
    models = [m for m in ("claude-haiku-5-5", "gpt-6-luna") if any(r["model"] == m for r in rows)]
    fig, axes = plt.subplots(1, len(models), figsize=(6.6 * len(models), 4.2), facecolor=SURFACE, squeeze=False, sharey=True)
    w = 0.24
    for ax, m in zip(axes[0], models):
        for ci, (cond, label, color) in enumerate(COND):
            for gi, (task, _) in enumerate(JOBS):
                s = stat(rows, m, cond, task)
                if not s:
                    continue
                est, lo, hi, n = s
                x = gi + (ci - 1) * w
                ax.bar(x, 100 * est, w * 0.92, color=color, label=label if gi == 0 else None, zorder=2)
                ax.errorbar(x, 100 * est, yerr=[[100 * (est - lo)], [100 * (hi - est)]], color=INK, lw=1, capsize=2, zorder=3)
                ax.text(x, 100 * max(est, hi) + 1.5, f"{100 * est:.0f}", ha="center", va="bottom", fontsize=8, color=INK)
        for fi, (fm, flabel) in enumerate(FRONT):
            for gi, (task, _) in enumerate(JOBS):
                x_ = [r["success"] for r in A.select(rows, model=fm, condition="none", phase="eval", quirk=True) if r["task"] == task]
                if x_:
                    ax.hlines(100 * np.mean(x_), gi - 0.43, gi + 0.43, color=INK if fi == 0 else MUTED, lw=1.4, linestyles="-" if fi == 0 else (0, (2, 2)), zorder=4, label=flabel if gi == 0 else None)
        ax.set_xticks(range(len(JOBS)))
        ax.set_xticklabels([n for _, n in JOBS], color=INK)
        ax.set_ylim(0, 118)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
        for s_ in ("top", "right", "left"):
            ax.spines[s_].set_visible(False)
        ax.tick_params(length=0, colors=MUTED)
        ax.set_title(m, loc="left", fontsize=11, color=INK)
    axes[0][0].set_ylabel("held-out layouts solved (%)", color=INK)
    axes[0][0].legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.12), ncol=3)
    fig.suptitle("Held-out success by job, with the frontier models' first try as lines", x=0.01, y=1.04, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=140, bbox_inches="tight", facecolor=SURFACE)
    print("wrote", a.out)


if __name__ == "__main__":
    main()

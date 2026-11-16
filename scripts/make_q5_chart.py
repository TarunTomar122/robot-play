"""Chart for the exploratory Q5 cells: held-out success of a cheap model with no memory, with its own notebook, with Fable's notebook for the same job, and with Fable's notebook for another job.
Same runs (task, run seed) in every bar of a model: only runs that have a complete no-memory, own-notebook, borrowed and wrong-task arm are used (so the wrong-task bar of sort and flasks may have fewer runs than the cluster
bootstrap suggests: the run seed whose Fable notebook does not exist is missing from every arm). Error bars: 95%, the wider of the cluster bootstrap over runs (resampling inside each task, 10,000 resamples) and a binomial
sampling-noise floor (so a bar at 100% still shows the uncertainty of the 36 to 40 episodes behind it). The chart shows a pooled bar and per-job bars; most of the pooled effect is one job.
  python scripts/make_q5_chart.py --out docs/img/q5_borrowed.png"""
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
COND = [("none", "No memory", "#2a78d6"), ("notebook", "Its own notebook (12 practice episodes)", "#eb6834"),
        ("borrowed", "Fable's notebook for this job", "#6250d6"), ("borrowed_other", "Fable's notebook for another job", "#e87ba4")]
JOBS = [("stack", "Stack"), ("bins", "Sort"), ("flasks", "Flasks"), (None, "All three jobs")]


def run_success(rows, model, cond, task=None):
    by = {}
    for r in A.select(rows, model=model, condition=cond, phase="eval", quirk=True):
        if task is None or r["task"] == task:
            by.setdefault((r["task"], r["run_seed"]), []).append(r["success"])
    return by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", nargs="*", default=["runs/main"])
    ap.add_argument("--borrowed", nargs="*", default=["runs/borrowed", "runs/borrowed_other"])
    ap.add_argument("--out", default="docs/img/q5_borrowed.png")
    a = ap.parse_args()
    rows = A.load(*[d for d in a.main + a.borrowed if Path(d).exists()], complete_only=True)
    models = [m for m in ("claude-haiku-5-5", "gpt-6-luna") if any(r["model"] == m and r["condition"] == "borrowed" for r in rows)]
    if not models:
        print("no borrowed runs yet")
        return
    fig, axes = plt.subplots(1, len(models), figsize=(6.8 * len(models), 4.4), facecolor=SURFACE, squeeze=False, sharey=True)
    for ax, m in zip(axes[0], models):
        keys = None
        for cond, _, _ in COND:
            kc = set(run_success(rows, m, cond))
            keys = kc if keys is None else keys & kc
        w = 0.19
        for ci, (cond, label, color) in enumerate(COND):
            for gi, (task, _) in enumerate(JOBS):
                by = {k: v for k, v in run_success(rows, m, cond, task).items() if k in keys}
                if not by:
                    continue
                clusters = [np.array(v, dtype=float) for v in by.values()]
                est, lo, hi = A.bootstrap(clusters, np.mean, 10_000, strata=[k[0] for k in by])
                n_ep = int(sum(len(c) for c in clusters))
                half = A._floor_half([(int(sum(c.sum() for c in clusters)), n_ep)], 0.05)
                lo, hi = (min(lo, est - half), max(hi, est + half)) if lo == lo else (est - half, est + half)
                lo, hi = max(0.0, lo), min(1.0, hi)
                x = gi + (ci - 1.5) * w
                ax.bar(x, 100 * est, w * 0.92, color=color, label=label if gi == 0 else None, zorder=2)
                if lo == lo:
                    ax.errorbar(x, 100 * est, yerr=[[100 * (est - lo)], [100 * (hi - est)]], color=INK, lw=1, capsize=2, zorder=3)
                top = max(est, hi) if hi == hi else est                                  # the label sits above the top of the error bar, never on it
                ax.text(x, 100 * top + 1.5, f"{100 * est:.0f}", ha="center", va="bottom", fontsize=8, color=INK)
        ax.set_xticks(range(len(JOBS)))
        ax.set_xticklabels([n for _, n in JOBS], color=INK)
        ax.set_ylim(0, 118)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(length=0, colors=MUTED)
        ax.set_title(m, loc="left", fontsize=11, color=INK)
        n = len(keys)
        ax.text(0.0, -0.16, f"{n} runs (task and run seed) behind the pooled bar, the same runs split by job in the others; 4 held-out layouts per run", transform=ax.transAxes, fontsize=8, color=MUTED)
    axes[0][0].set_ylabel("held-out layouts solved (%)", color=INK)
    axes[0][0].legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.16), ncol=2)
    fig.suptitle("Can a cheap model use a stronger model's notes? (exploratory)", x=0.01, y=1.02, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.tight_layout()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=140, bbox_inches="tight", facecolor=SURFACE)
    print("wrote", a.out)


if __name__ == "__main__":
    main()

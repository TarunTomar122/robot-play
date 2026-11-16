"""Charts for the README, written in plain words. Colours follow the dataviz skill's validated pair (blue / orange, light surface)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({"font.family": "Helvetica", "font.size": 12, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})

USED = {"stack": 0.25, "bins": 0.12, "flasks": 0.07}
TITLES = {"stack": "Stack the cubes", "bins": "Sort into bins", "flasks": "Stand the flasks up"}
XLAB = {"stack": "weight of the green cube (kg)", "bins": "height of the bin walls (m)", "flasks": "height of the wide flask base (m)"}


def dose_chart():
    d = json.loads((ROOT / "results/dose_response.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.3), sharey=True, facecolor=SURFACE)
    for ax, (task, info) in zip(axes, d["tasks"].items()):
        ax.set_facecolor(SURFACE)
        xs = [p["value"] for p in info["points"]]
        for key, color, name in (("oracle", ORANGE, "knows the catch"), ("naive", BLUE, "default settings")):
            ys = [100 * p[key] for p in info["points"]]
            ax.plot(xs, ys, color=color, lw=2.2, marker="o", ms=8, mfc=color, mec=SURFACE, mew=2, label=name, clip_on=False)
        ax.axvline(USED[task], color=INK2, lw=1, ls=(0, (4, 4)))
        ax.text(USED[task], 106, "used in\nthe study", color=INK2, fontsize=10.5, va="bottom", ha="center", clip_on=False)
        ax.set_title(TITLES[task], loc="left", fontsize=14, fontweight="bold", color=INK, pad=34)
        ax.set_xlabel(XLAB[task])
        ax.set_ylim(-4, 104)
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{x:g}" for x in xs], fontsize=10)
        ax.grid(axis="y", color=GRID, lw=0.8)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(length=0)
    axes[0].set_ylabel("tries that finish the job (%)")
    axes[0].legend(loc="lower left", frameon=False, fontsize=11, bbox_to_anchor=(0.0, 0.0))
    fig.suptitle("Each catch switches on sharply: a script using default settings goes from always succeeding to never succeeding", x=0.01, ha="left",
                 fontsize=14, fontweight="bold", color=INK, y=1.02)
    fig.text(0.01, -0.04, f"Each point is {d['seeds_per_point']} random layouts of the objects. 'Knows the catch' is a hand-written script that uses the right setting. Source: results/dose_response.json.",
             color=INK2, fontsize=10.5)
    fig.tight_layout()
    out = ROOT / "docs/img/dose_response.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    return out


if __name__ == "__main__":
    print(dose_chart())

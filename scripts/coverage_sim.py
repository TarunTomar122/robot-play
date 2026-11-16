"""How often does the registered Q1 interval contain the true difference? Runs the real `analysis.paired_difference` (percentile bootstrap, stratified t, sampling-noise floor) on synthetic data
shaped like the Q1 design: 3 jobs x 10 run seeds, 4 held-out episodes per run, notebook arm against fresh arm, nominal 97.5%.

  python scripts/coverage_sim.py --reps 400 --out results/coverage_sim.md

Assumptions, stated so they can be attacked: the two arms are different runs (independent); within the fresh arm episodes are independent given the job; within the notebook arm the four
episodes of a run share one notebook, so their success probability is drawn per run from a beta distribution with the stated intraclass correlation (rho). The truth is the mean over the
three jobs of (notebook probability minus fresh probability). A binomial Monte Carlo error of +-sqrt(p(1-p)/reps) applies to every coverage figure."""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from robot_play import analysis as A      # noqa: E402

JOBS = ("stack", "bins", "flasks")
SCENARIOS = {     # name: (fresh probability per job, notebook probability per job)
    "no effect, mixed rates (0.3 / 0.7 / 0.99 in both arms)": ((0.3, 0.7, 0.99), (0.3, 0.7, 0.99)),
    "no effect, every arm at 0.97": ((0.97,) * 3, (0.97,) * 3),
    "Haiku-like: one job with a large gain (0.3 to 1.0), two at 0.99": ((0.3, 0.99, 0.99), (1.0, 0.99, 0.99)),
    "hardest case: small gap, every arm near ceiling (0.95 against 0.99)": ((0.95,) * 3, (0.99,) * 3),
    "moderate gain in every job (0.5 to 0.8)": ((0.5,) * 3, (0.8,) * 3),
}


def draw_arm(rng, p, rho, n_runs, m=4):
    if rho <= 0 or p in (0.0, 1.0):
        return rng.binomial(m, p, n_runs)
    a = p * (1 - rho) / rho
    b = (1 - p) * (1 - rho) / rho
    return rng.binomial(m, rng.beta(a, b, n_runs))


def one_rep(rng, fresh, nb, rho, n_runs, n_boot):
    rows = []
    for j, task in enumerate(JOBS):
        for cond, p, r in (("none", fresh[j], 0.0), ("notebook", nb[j], rho)):
            for rs, k in enumerate(draw_arm(rng, p, r, n_runs)):
                for i in range(4):
                    rows.append(dict(model="m", task=task, condition=cond, run_seed=rs, phase="eval", idx=i, success=int(i < k), seed=i, quirk=True))
    return A.paired_difference(rows, "m", "notebook", "none", alpha=A.ALPHA_Q1, n_boot=n_boot)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--rho", type=float, nargs="*", default=[0.0, 0.3])
    ap.add_argument("--runs", type=int, default=10, help="run seeds per job")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="results/coverage_sim.md")
    a = ap.parse_args()
    L = ["# Coverage of the registered Q1 interval (simulation)", "",
         f"Real `analysis.paired_difference`, nominal {100 * (1 - A.ALPHA_Q1):.1f}%, {a.runs} run seeds x 3 jobs x 4 held-out episodes, {a.reps} repetitions per row, {a.n_boot} bootstrap resamples per repetition (the report uses 10,000). "
         "Notebook-arm episodes within a run share a success probability drawn from a beta distribution with intraclass correlation rho; fresh-arm episodes are independent; the two arms are separate runs. "
         f"Monte Carlo error of each figure is at most +-{100 * 0.5 / np.sqrt(a.reps):.1f} points.", "",
         "| scenario | rho (notebook arm) | true difference | coverage | mean half-width |", "|---|---|---|---|---|"]
    rng = np.random.default_rng(a.seed)
    for name, (fresh, nb) in SCENARIOS.items():
        truth = float(np.mean(np.array(nb) - np.array(fresh)))
        for rho in a.rho:
            hit, hw = 0, []
            for _ in range(a.reps):
                d = one_rep(rng, fresh, nb, rho, a.runs, a.n_boot)
                hit += d["lo"] <= truth <= d["hi"]
                hw.append((d["hi"] - d["lo"]) / 2)
            L.append(f"| {name} | {rho} | {100 * truth:+.1f} pp | {100 * hit / a.reps:.1f}% | {100 * np.mean(hw):.1f} pp |")
            print(L[-1], flush=True)
    L += ["", "Reading: the interval is conservative where it matters for the headline (a large gain in one job, no effect) and does not reach the nominal level in the hardest case, a small gap with every arm near ceiling; "
          "there the true difference is inside the interval about as often as the figure above says, which is the figure to quote, not 97.5%. The sampling-noise floor treats episodes as independent (design effect 1), so a strongly shared notebook (rho above 0) can make it too narrow; the rows with rho > 0 show how much."]
    Path(a.out).write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()

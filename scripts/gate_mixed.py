"""Validation gate for the `mixed` job: no single pick setting solves it, a player that knows (or reads the errors) does.

  python scripts/gate_mixed.py --seeds 100 > results/gate_mixed.md
Plays through `Episode`, the same wrapper a model uses. Seeds 4000+ (not the layouts any run uses)."""
import argparse
import collections
from multiprocessing import Pool

from robot_play.scripted import MIXED_POLICIES, run_mixed

POLICIES = list(MIXED_POLICIES) + ["oracle", "procedure"]


def one(a):
    seed, quirk, policy = a
    try:
        r = run_mixed(seed, quirk, policy)
        return a, bool(r["ok"]), r["calls"], None
    except Exception as ex:
        return a, False, 0, f"{type(ex).__name__}: {str(ex)[:100]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--start", type=int, default=4000)
    args = ap.parse_args()
    jobs = [(args.start + i, q, p) for q in (True, False) for p in POLICIES for i in range(args.seeds)]
    with Pool(args.workers) as pool:
        res = pool.map(one, jobs)
    agg, calls, crashes = collections.defaultdict(list), collections.defaultdict(list), []
    for (sd, q, p), ok, n, err in res:
        agg[(q, p)].append(ok)
        calls[(q, p)].append(n)
        if err:
            crashes.append((sd, q, p, err))
    print(f"# Gate for the `mixed` job ({args.seeds} layouts per row, seeds {args.start} to {args.start + args.seeds - 1})\n")
    print("| scene | player | solved | mean calls |")
    print("|---|---|---|---|")
    for q in (True, False):
        for p in POLICIES:
            v = agg[(q, p)]
            print(f"| {'catch' if q else 'control'} | {p} | {sum(v)} / {len(v)} | {sum(calls[(q, p)]) / len(v):.1f} |")
    print(f"\nCrashed runs: {len(crashes)}")
    for c in crashes[:5]:
        print("-", c)


if __name__ == "__main__":
    main()

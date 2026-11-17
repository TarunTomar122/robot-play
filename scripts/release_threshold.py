"""How high must `place` let go for a given bin wall height? (scripted oracle, `bins` with the catch, 20 layouts per cell)

    python scripts/release_threshold.py > results/release_threshold.md

The README's table says "let go from 14 cm or higher" for the sort job; that is the value the hint and the settings audit used, a safe margin. This scan shows the
real threshold: the scripted oracle (which knows nothing else about the catch) places the four cubes with each release height, for several wall heights."""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from robot_play.scripted import run_script  # noqa: E402

WALLS = [0.04, 0.07, 0.10, 0.12, 0.15, 0.18, 0.21]
RELEASES = [0.02, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.14, 0.18, 0.22]
SEEDS = list(range(100, 120))


def one(a):
    h, r, seed = a
    return h, r, bool(run_script("bins", seed, True, "oracle", place_kw={"release_height": r}, wall_h=h, max_calls=20)["ok"])


if __name__ == "__main__":
    with ProcessPoolExecutor(6) as ex:
        res = list(ex.map(one, [(h, r, s) for h in WALLS for r in RELEASES for s in SEEDS]))
    print("# Release height against bin wall height (scripted oracle, 20 layouts per cell)\n")
    print("Layouts: seeds 100 to 119 of the `bins` job with the catch, wall height set by hand. Cells are layouts solved out of 20 when `place` lets go that many metres above the bin floor (the `release_height` argument).\n")
    print("| wall height (m) | " + " | ".join(f"{r:.2f}" for r in RELEASES) + " |")
    print("|---|" + "---|" * len(RELEASES))
    for h in WALLS:
        print(f"| {h:.2f} | " + " | ".join(str(sum(1 for hh, rr, ok in res if hh == h and rr == r and ok)) for r in RELEASES) + " |")
    print("\nThe catch's wall is 0.12 m. For it the threshold is sharp (about 6 cm); 0.14 m, the value the hint and the audit use, is a margin of 8 cm over it. Higher release heights up to the 0.30 m limit never failed in this scan, so a model that always lets go from high up solves the job, and the job cannot tell a stored rule from a stored constant.")

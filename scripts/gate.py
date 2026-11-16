"""Validation gates from PROTOCOL.md section 7. Writes results/gate.json, results/dose_response.json and results/gate.md.

  python scripts/gate.py --seeds 100 --dose-seeds 30
"""
import argparse, collections, json, sys
from multiprocessing import Pool
from pathlib import Path

from robot_play.scripted import run_script

OUT = Path(__file__).resolve().parents[1] / "results"
TASKS = ["stack", "bins", "flasks"]


def one(a):
    task, seed, quirk, policy, kw = a
    try:
        r = run_script(task, seed, quirk, policy, **kw)
        return a, bool(r["ok"]), None
    except Exception as ex:  # a crashed run counts as a failure and is reported
        return a, False, f"{type(ex).__name__}: {str(ex)[:100]}"


def rate(res):
    return sum(res) / len(res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--dose-seeds", type=int, default=30)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    jobs = [(t, sd, q, p, {}) for t in TASKS for q in (True, False) for p in ("naive", "oracle") for sd in range(args.seeds)]
    with Pool(args.workers) as pool:
        res = pool.map(one, jobs)
    agg, crashes = collections.defaultdict(list), []
    for (t, sd, q, p, _), ok, err in res:
        agg[(t, q, p)].append(ok)
        if err:
            crashes.append({"task": t, "seed": sd, "quirk": q, "policy": p, "error": err})
    table = {f"{t}|{'quirk' if q else 'control'}|{p}": {"success": sum(v), "n": len(v)} for (t, q, p), v in sorted(agg.items())}
    gates = {}
    for t in TASKS:
        g = lambda q, p: rate(agg[(t, q, p)])
        gates[t] = {"oracle_quirk>=0.95": g(True, "oracle") >= 0.95, "naive_quirk<=0.30": g(True, "naive") <= 0.30,
                    "naive_control>=0.90": g(False, "naive") >= 0.90, "oracle_control>=0.90": g(False, "oracle") >= 0.90}
    (OUT / "gate.json").write_text(json.dumps({"seeds": args.seeds, "table": table, "gates": gates, "crashes": crashes}, indent=1))

    # dose-response: the naive script's success as the quirk parameter moves from "no quirk" to "full quirk"
    sweeps = {
        "stack": ("mass", "green cube mass (kg)", [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]),
        "bins": ("wall_h", "bin wall height (m)", [0.015, 0.04, 0.07, 0.10, 0.12, 0.15]),
        "flasks": ("base_h", "flask base height (m; 0 = plain cylinder)", [0.0, 0.02, 0.04, 0.06, 0.07]),
    }
    djobs = []
    for t, (key, _, vals) in sweeps.items():
        for v in vals:
            for p in ("naive", "oracle"):
                for sd in range(args.dose_seeds):
                    kw = {key: v}
                    if t == "flasks" and v == 0.0:      # plain cylinder = control scene
                        djobs.append((t, 1000 + sd, False, p, {}))
                    else:
                        djobs.append((t, 1000 + sd, True, p, kw))
    with Pool(args.workers) as pool:
        dres = pool.map(one, djobs)
    dose = collections.defaultdict(list)
    for (t, sd, q, p, kw), ok, err in dres:
        v = 0.0 if (t == "flasks" and not q) else list(kw.values())[0]
        dose[(t, v, p)].append(ok)
    dose_out = {t: {"param": s[1], "points": [{"value": v, "naive": rate(dose[(t, v, "naive")]), "oracle": rate(dose[(t, v, "oracle")])} for v in s[2]]}
                for t, s in sweeps.items()}
    (OUT / "dose_response.json").write_text(json.dumps({"seeds_per_point": args.dose_seeds, "tasks": dose_out}, indent=1))

    lines = ["# Validation gates", "", f"{args.seeds} seeds per cell (seeds 0..{args.seeds - 1}); dose-response uses seeds 1000+.", "",
             "| Task | Scene | Naive script | Oracle script |", "|---|---|---|---|"]
    for t in TASKS:
        for q in (True, False):
            n, o = agg[(t, q, "naive")], agg[(t, q, "oracle")]
            lines.append(f"| {t} | {'quirk' if q else 'control'} | {sum(n)}/{len(n)} | {sum(o)}/{len(o)} |")
    lines += ["", "Gates: " + ", ".join(f"{t}: {'PASS' if all(g.values()) else 'FAIL ' + str([k for k, x in g.items() if not x])}" for t, g in gates.items()),
              f"Crashed runs: {len(crashes)}", "", "## Dose-response (naive / oracle success)", ""]
    for t, d in dose_out.items():
        lines.append(f"**{t}** ({d['param']}): " + "; ".join(f"{p['value']:g}: {p['naive']:.2f} / {p['oracle']:.2f}" for p in d["points"]))
        lines.append("")
    (OUT / "gate.md").write_text("\n".join(lines))
    print("\n".join(lines))
    sys.exit(0 if all(all(g.values()) for g in gates.values()) and not crashes else 1)


if __name__ == "__main__":
    main()

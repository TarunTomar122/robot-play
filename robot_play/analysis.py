"""Turn run files into the numbers behind each claim (PROTOCOL.md section 1).

Intervals are cluster-bootstrap intervals: the unit that gets resampled is a *cluster* (a run, or a layout), never a single episode, because
episodes inside one run share a memory and are not independent.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

KEEP = ("run", "model", "task", "condition", "quirk", "run_seed", "phase", "idx", "seed", "disturbance", "toolset", "max_calls", "memory_tokens_in", "cost_usd", "retry_usd", "turns", "nudges", "refusal")


def load(*dirs: str | Path) -> list[dict]:
    """One flat row per finished episode (the long tool-call log is dropped)."""
    rows = []
    for d in dirs:
        for f in sorted(Path(d).glob("*.jsonl")):
            for line in f.read_text().splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                res = r["result"]
                row = {k: r.get(k) for k in KEEP}
                row.update(success=int(res["success"]), calls=res["calls"], sim_time_s=res["sim_time_s"], claimed_done=int(res["claimed_done"]),
                           false_claim=int(res["false_success_claim"]), fired=int(res["disturbance_fired"]),
                           tokens_in=r["usage"]["input"] + r["usage"]["cache_read"] + r["usage"]["cache_write"], tokens_out=r["usage"]["output"])
                budget = row.get("max_calls") or res["calls"]
                row["calls_to_success"] = res["calls"] if res["success"] else budget           # a failure is charged the whole budget
                rows.append(row)
    return rows


def select(rows, **kw):
    return [r for r in rows if all(r.get(k) == v for k, v in kw.items())]


def bootstrap(clusters: list[np.ndarray], stat, n_boot: int = 10_000, seed: int = 0) -> tuple[float, float, float]:
    """`clusters` is a list of arrays (one per cluster). `stat(concatenated resample)` -> float. Returns (estimate, low, high) with a 95% interval."""
    rng = np.random.default_rng(seed)
    k = len(clusters)
    est = float(stat(np.concatenate(clusters)))
    if k < 2:
        return est, float("nan"), float("nan")
    vals = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, k, k)
        vals[b] = stat(np.concatenate([clusters[i] for i in idx]))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return est, float(lo), float(hi)


def _run_means(rows, metric: str) -> dict:
    """Mean of `metric` over each run's episodes, keyed by (task, run_seed)."""
    out: dict = {}
    for r in rows:
        out.setdefault((r["task"], r["run_seed"]), []).append(r[metric])
    return {k: float(np.mean(v)) for k, v in out.items()}


def paired_difference(rows, model: str, a: str, b: str, metric: str = "success", phase: str = "eval", quirk: bool = True,
                      tasks: list[str] | None = None, n_boot: int = 10_000, only_fired: bool = False) -> dict:
    """Condition `a` minus condition `b` for one model on the held-out episodes, paired by (task, run seed), cluster bootstrap over those pairs.
    With only_fired the denominator is the episodes in which the disturbance actually happened."""
    def pick(cond):
        rs = select(rows, model=model, condition=cond, phase=phase, quirk=quirk)
        if tasks:
            rs = [r for r in rs if r["task"] in tasks]
        if only_fired:
            rs = [r for r in rs if r["fired"]]
        return _run_means(rs, metric)
    ma, mb = pick(a), pick(b)
    keys = sorted(set(ma) & set(mb))
    diffs = [np.array([ma[k] - mb[k]]) for k in keys]
    if not diffs:
        return {"n_pairs": 0}
    est, lo, hi = bootstrap(diffs, np.mean, n_boot)
    return {"n_pairs": len(keys), "a": float(np.mean([ma[k] for k in keys])), "b": float(np.mean([mb[k] for k in keys])), "diff": est, "lo": lo, "hi": hi}


def curve(rows, model: str, condition: str, metric: str = "success", quirk: bool = True, n_boot: int = 2000) -> list[dict]:
    """Practice-episode curve: mean `metric` at practice index 0, 1, 2, ... with a cluster-bootstrap interval over runs."""
    rs = select(rows, model=model, condition=condition, phase="practice", quirk=quirk)
    out = []
    for i in sorted({r["idx"] for r in rs}):
        by_run: dict = {}
        for r in rs:
            if r["idx"] == i:
                by_run.setdefault((r["task"], r["run_seed"]), []).append(r[metric])
        est, lo, hi = bootstrap([np.array(v, dtype=float) for v in by_run.values()], np.mean, n_boot)
        out.append({"idx": i, "mean": est, "lo": lo, "hi": hi, "n_runs": len(by_run)})
    return out


def per_success(rows, model: str, condition: str, metric: str, phase: str = "eval", quirk: bool = True) -> float:
    """Total `metric` (cost, calls, sim seconds) divided by the number of successful episodes."""
    rs = select(rows, model=model, condition=condition, phase=phase, quirk=quirk)
    wins = sum(r["success"] for r in rs)
    return float(sum(r[metric] for r in rs) / wins) if wins else float("nan")


def q3_gap(rows, frontier: str, cheap: str, cheap_condition: str = "notebook", margin: float = 0.10, n_boot: int = 10_000) -> dict:
    """Frontier first-try success minus cheap-with-experience success on the *same* layouts, clustered by layout (task, seed).
    The claim 'comes within the margin' needs the whole 95% interval of the gap below +margin."""
    fr = {(r["task"], r["seed"]): r["success"] for r in select(rows, model=frontier, condition="none", quirk=True, phase="eval")}
    ch = {(r["task"], r["seed"]): r["success"] for r in select(rows, model=cheap, condition=cheap_condition, quirk=True, phase="eval")}
    keys = sorted(set(fr) & set(ch))
    if not keys:
        return {"n_layouts": 0}
    est, lo, hi = bootstrap([np.array([fr[k] - ch[k]]) for k in keys], np.mean, n_boot)
    return {"n_layouts": len(keys), "frontier": float(np.mean([fr[k] for k in keys])), "cheap": float(np.mean([ch[k] for k in keys])),
            "gap": est, "lo": lo, "hi": hi, "within_margin": bool(hi < margin), "margin": margin}


def did(rows, model: str, a: str, b: str, metric: str = "success", phase: str = "eval", tasks: list[str] | None = None, n_boot: int = 10_000) -> dict:
    """Difference in differences: (a - b) in the catch scenes minus (a - b) in the no-catch control scenes, held-out episodes.
    A positive value means memory `a` helped more where the catch exists than where it does not, which is the Q1 claim. Catch pairs and control
    pairs are different runs, so they are resampled independently."""
    def diffs(quirk):
        def pick(c):
            rs = select(rows, model=model, condition=c, phase=phase, quirk=quirk)
            if tasks:
                rs = [r for r in rs if r["task"] in tasks]
            return _run_means(rs, metric)
        ma, mb = pick(a), pick(b)
        return [ma[k] - mb[k] for k in sorted(set(ma) & set(mb))]
    dq, dc = diffs(True), diffs(False)
    if not dq or not dc:
        return {"n_catch_pairs": len(dq), "n_control_pairs": len(dc)}
    rng = np.random.default_rng(0)
    dq, dc = np.array(dq), np.array(dc)
    boots = [rng.choice(dq, len(dq)).mean() - rng.choice(dc, len(dc)).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"n_catch_pairs": len(dq), "n_control_pairs": len(dc), "gain_catch": float(dq.mean()), "gain_control": float(dc.mean()),
            "did": float(dq.mean() - dc.mean()), "lo": float(lo), "hi": float(hi)}


def disturbance_summary(rows, model: str, condition: str) -> dict:
    """Held-out disturbed episodes: how often the disturbance fired, success over ALL assigned episodes (the primary measure, because an agent can
    influence whether it fires) and success among those where it fired, next to the same layouts played clean."""
    dist = select(rows, model=model, condition=condition, phase="eval_disturbed", quirk=True)
    clean = select(rows, model=model, condition=condition, phase="eval", quirk=True)
    layouts = {(r["task"], r["seed"]) for r in dist}
    clean = [r for r in clean if (r["task"], r["seed"]) in layouts]
    fired = [r for r in dist if r["fired"]]
    if not dist:
        return {"n_disturbed": 0}
    return {"n_disturbed": len(dist), "fire_rate": len(fired) / len(dist), "success_all_assigned": float(np.mean([r["success"] for r in dist])),
            "success_when_fired": float(np.mean([r["success"] for r in fired])) if fired else float("nan"),
            "success_same_layouts_clean": float(np.mean([r["success"] for r in clean])) if clean else float("nan")}


def recovery_drop_difference(rows, model: str, a: str, b: str, n_boot: int = 10_000) -> dict:
    """Q4 without mixing in catch knowledge: each condition's own drop from clean to disturbed on the same layouts (clean minus disturbed success,
    all assigned disturbed episodes), then condition `a`'s drop minus condition `b`'s. A negative value means `a` loses less to the disturbance."""
    def drops(c):
        out = {}
        for r in select(rows, model=model, condition=c, quirk=True):
            if r["phase"] in ("eval", "eval_disturbed"):
                out.setdefault((r["task"], r["run_seed"], r["seed"]), {})[r["phase"]] = r["success"]
        per_run: dict = {}
        for (task, rs, _), v in out.items():
            if "eval" in v and "eval_disturbed" in v:
                per_run.setdefault((task, rs), []).append(v["eval"] - v["eval_disturbed"])
        return {k: float(np.mean(v)) for k, v in per_run.items()}
    da, db = drops(a), drops(b)
    keys = sorted(set(da) & set(db))
    if not keys:
        return {"n_pairs": 0}
    est, lo, hi = bootstrap([np.array([da[k] - db[k]]) for k in keys], np.mean, n_boot)
    return {"n_pairs": len(keys), "drop_a": float(np.mean([da[k] for k in keys])), "drop_b": float(np.mean([db[k] for k in keys])), "diff": est, "lo": lo, "hi": hi}


def within_k(rows, model: str, condition: str, ks=(6, 8, 10, 12, 14, 16, 18, 20), phase: str = "eval", quirk: bool = True) -> dict:
    """Share of episodes that succeeded using at most k tool calls."""
    rs = select(rows, model=model, condition=condition, phase=phase, quirk=quirk)
    return {k: float(np.mean([bool(r["success"] and r["calls"] <= k) for r in rs])) if rs else float("nan") for k in ks}

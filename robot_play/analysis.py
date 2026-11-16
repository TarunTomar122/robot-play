"""Turn run files into the numbers behind each claim (PROTOCOL.md section 1).

Intervals are cluster-bootstrap intervals: the unit that gets resampled is a *cluster* (a run, i.e. one task and run seed whose episodes share a
memory), never a single episode or a single layout. The confirmatory family uses Bonferroni-adjusted intervals (ALPHA_PRIMARY); everything else
is reported with plain 95% intervals and labelled exploratory.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

KEEP = ("run", "model", "task", "condition", "quirk", "run_seed", "phase", "idx", "seed", "disturbance", "toolset", "max_calls", "memory_tokens_in", "cost_usd", "retry_usd", "turns", "nudges", "refusal")
ALPHA_Q1 = 0.025                # Q1: notebook against starting fresh, one test per cheap model (2 tests): 0.05 / 2
ALPHA_Q3 = 0.0125               # Q3: one gap per (frontier, cheap) pair (4 gaps): 0.05 / 4
ALPHA_Q4 = 0.025                # Q4: notebook against starting fresh in the no-catch control scenes, one test per cheap model (2 tests): 0.05 / 2
ALPHA_PRIMARY = ALPHA_Q3        # older name
Z = {0.05: 1.959964, 0.025: 2.241403, 0.0125: 2.497705}


def _parse(path: Path):
    """(config or None, finished-episode lines, abandoned-attempt lines) of one run file; a torn last line ends the file."""
    cfg, rows, aborts = None, [], []
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            break
        if "_config" in r:
            cfg = r["_config"]
        elif "_aborted" in r:
            aborts.append(r["_aborted"])
        else:
            rows.append(r)
    return cfg, rows, aborts


def coverage(*dirs: str | Path) -> list[dict]:
    """One line per run file: how many episodes were planned, how many finished, how many attempts were abandoned and what they cost."""
    out = []
    for d in dirs:
        for f in sorted(Path(d).glob("*.jsonl")):
            cfg, rows, aborts = _parse(f)
            if not cfg:
                continue
            out.append({"file": f.name, "dir": str(d), "model": cfg["model"], "task": cfg["task"], "condition": cfg["condition"], "quirk": cfg["quirk"],
                        "toolset": cfg.get("toolset", "skills"), "run_seed": cfg["run_seed"], "planned": len(cfg["plan"]), "done": len(rows),
                        "aborted": len(aborts), "aborted_usd": float(sum(a["usd"] for a in aborts)), "complete": len(rows) >= len(cfg["plan"])})
    return out


def load(*dirs: str | Path, complete_only: bool = False) -> list[dict]:
    """One flat row per finished episode (the long tool-call log is dropped). With complete_only, runs that did not finish their whole plan are left
    out, so a paired comparison never mixes runs that stopped early with runs that did not (the incomplete runs are listed by `coverage`)."""
    rows = []
    for d in dirs:
        for f in sorted(Path(d).glob("*.jsonl")):
            cfg, lines, _ = _parse(f)
            if complete_only and cfg and len(lines) < len(cfg["plan"]):
                continue
            for r in lines:
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


def bootstrap(clusters: list[np.ndarray], stat, n_boot: int = 10_000, seed: int = 0, alpha: float = 0.05, strata: list | None = None) -> tuple[float, float, float]:
    """`clusters` is a list of arrays (one per cluster). `stat(concatenated resample)` -> float. Returns (estimate, low, high), a (1 - alpha) interval.
    With `strata` (one label per cluster, e.g. the task) clusters are resampled within their own stratum, so every resample keeps the task mix of the design."""
    rng = np.random.default_rng(seed)
    k = len(clusters)
    est = float(stat(np.concatenate(clusters)))
    if k < 2:
        return est, float("nan"), float("nan")
    groups = [np.array([i for i in range(k) if strata[i] == g]) for g in dict.fromkeys(strata)] if strata is not None else [np.arange(k)]
    vals = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups])
        vals[b] = stat(np.concatenate([clusters[i] for i in idx]))
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return est, float(lo), float(hi)


def _run_means(rows, metric: str) -> dict:
    """Mean of `metric` over each run's episodes, keyed by (task, run_seed)."""
    out: dict = {}
    for r in rows:
        out.setdefault((r["task"], r["run_seed"]), []).append(r[metric])
    return {k: float(np.mean(v)) for k, v in out.items()}


def paired_difference(rows, model: str, a: str, b: str, metric: str = "success", phase: str = "eval", quirk: bool = True,
                      tasks: list[str] | None = None, n_boot: int = 10_000, only_fired: bool = False, alpha: float = 0.05) -> dict:
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
    est, lo, hi = bootstrap(diffs, np.mean, n_boot, alpha=alpha, strata=[k[0] for k in keys])
    return {"n_pairs": len(keys), "a": float(np.mean([ma[k] for k in keys])), "b": float(np.mean([mb[k] for k in keys])), "diff": est, "lo": lo, "hi": hi, "alpha": alpha}


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


def _agresti_caffo(s1: int, n1: int, s2: int, n2: int, z: float, deff: float = 1.0) -> tuple[float, float, float]:
    """Difference of two proportions with one pseudo-success and one pseudo-failure added to each arm (Agresti and Caffo), the variance multiplied by a
    design effect. Unlike a bootstrap it does not collapse to zero width when every episode succeeds (or every episode fails)."""
    p1, p2 = (s1 + 1) / (n1 + 2), (s2 + 1) / (n2 + 2)
    se = float(np.sqrt(deff * (p1 * (1 - p1) / (n1 + 2) + p2 * (1 - p2) / (n2 + 2))))
    return p1 - p2, p1 - p2 - z * se, p1 - p2 + z * se


def q3_gap(rows, frontier: str, cheap: str, cheap_condition: str = "notebook", margin: float = 0.10, n_boot: int = 10_000, alpha: float = ALPHA_Q3) -> dict:
    """Frontier first-try success minus cheap-with-experience success on the *same* layouts.
    Layouts are nested inside clusters: the (task, run seed) runs whose four held-out layouts all use one notebook. The bootstrap resamples those clusters.
    Because a bootstrap interval has zero width when every episode succeeds, the reported interval is the wider of the cluster bootstrap and an
    Agresti-Caffo interval (variance times a design effect estimated from the cluster structure). 'Within the margin' needs the whole interval of the gap
    below +margin."""
    fr = {(r["task"], r["seed"]): r["success"] for r in select(rows, model=frontier, condition="none", quirk=True, phase="eval")}
    ch = {(r["task"], r["seed"]): (r["run_seed"], r["success"]) for r in select(rows, model=cheap, condition=cheap_condition, quirk=True, phase="eval")}
    keys = sorted(set(fr) & set(ch))
    if not keys:
        return {"n_layouts": 0}
    by_cluster: dict = {}
    for k in keys:
        by_cluster.setdefault((k[0], ch[k][0]), []).append(fr[k] - ch[k][1])
    clusters = [np.array(v, dtype=float) for v in by_cluster.values()]
    est, blo, bhi = bootstrap(clusters, np.mean, n_boot, alpha=alpha, strata=[k[0] for k in by_cluster])
    n = len(keys)
    s_fr, s_ch = sum(fr[k] for k in keys), sum(ch[k][1] for k in keys)
    d_all = np.concatenate(clusters)
    var_srs = d_all.var(ddof=1) / n if n > 1 else 0.0
    cmeans = np.array([c.mean() for c in clusters])
    var_cl = cmeans.var(ddof=1) / len(clusters) if len(clusters) > 1 else 0.0
    deff = max(1.0, var_cl / var_srs) if var_srs > 0 else 1.0
    _, alo, ahi = _agresti_caffo(s_fr, n, s_ch, n, Z[alpha], deff)
    lo = min(x for x in (blo, alo) if x == x)
    hi = max(x for x in (bhi, ahi) if x == x)
    return {"n_layouts": n, "n_clusters": len(clusters), "clusters": sorted(by_cluster), "frontier": s_fr / n, "cheap": s_ch / n, "gap": est, "lo": lo, "hi": hi,
            "lo_boot": blo, "hi_boot": bhi, "lo_ac": alo, "hi_ac": ahi, "deff": deff, "within_margin": bool(hi < margin), "margin": margin, "alpha": alpha}


def q3_cost(rows, frontier: str, cheap: str, cheap_condition: str = "notebook", abandoned: dict | None = None) -> dict:
    """Everything the Q3 comparison cost, so a cheap-model-with-practice is never compared to a frontier first try on evaluation cost alone.
    Cheap side: all 12 practice episodes with their notebook rewrites, the clean evaluation episodes, and abandoned attempts, for exactly the runs in the gap.
    Frontier side: its first-try episodes on the same layouts. `abandoned` maps (model, task, condition, quirk, run_seed) to dollars."""
    g = q3_gap(rows, frontier, cheap, cheap_condition, n_boot=10)
    if not g.get("n_layouts"):
        return {}
    cl = set(g["clusters"])
    cr = [r for r in select(rows, model=cheap, condition=cheap_condition, quirk=True) if (r["task"], r["run_seed"]) in cl and r["phase"] in ("practice", "eval")]
    layouts = {(r["task"], r["seed"]) for r in select(rows, model=cheap, condition=cheap_condition, quirk=True, phase="eval") if (r["task"], r["run_seed"]) in cl}
    fr = [r for r in select(rows, model=frontier, condition="none", quirk=True, phase="eval") if (r["task"], r["seed"]) in layouts]
    ab = sum(v for (m, t, c, q, s), v in (abandoned or {}).items() if m == cheap and c == cheap_condition and q and (t, s) in cl)
    ev = sum(r["cost_usd"] for r in cr if r["phase"] == "eval")
    return {"cheap_eval_only_usd": ev, "cheap_practice_usd": sum(r["cost_usd"] for r in cr if r["phase"] == "practice"), "cheap_abandoned_usd": ab,
            "cheap_total_usd": sum(r["cost_usd"] for r in cr) + ab, "frontier_usd": sum(r["cost_usd"] for r in fr), "n_frontier_episodes": len(fr), "n_cheap_eval_episodes": len(layouts)}


def did(rows, model: str, a: str, b: str, metric: str = "success", phase: str = "eval", tasks: list[str] | None = None, n_boot: int = 10_000, alpha: float = 0.05) -> dict:
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
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"n_catch_pairs": len(dq), "n_control_pairs": len(dc), "gain_catch": float(dq.mean()), "gain_control": float(dc.mean()),
            "did": float(dq.mean() - dc.mean()), "lo": float(lo), "hi": float(hi)}


def disturbance_summary(rows, model: str, condition: str, quirk: bool = True) -> dict:
    """Held-out disturbed episodes: how often the disturbance fired, success over ALL assigned episodes (the primary measure, because an agent can
    influence whether it fires) and success among those where it fired, next to the same layouts played clean."""
    dist = select(rows, model=model, condition=condition, phase="eval_disturbed", quirk=quirk)
    clean = select(rows, model=model, condition=condition, phase="eval", quirk=quirk)
    layouts = {(r["task"], r["seed"]) for r in dist}
    clean = [r for r in clean if (r["task"], r["seed"]) in layouts]
    fired = [r for r in dist if r["fired"]]
    if not dist:
        return {"n_disturbed": 0}
    return {"n_disturbed": len(dist), "fire_rate": len(fired) / len(dist), "success_all_assigned": float(np.mean([r["success"] for r in dist])),
            "success_when_fired": float(np.mean([r["success"] for r in fired])) if fired else float("nan"),
            "success_same_layouts_clean": float(np.mean([r["success"] for r in clean])) if clean else float("nan")}


def _layout_drops(rows, model: str, condition: str, quirk: bool = True) -> dict:
    """(task, run seed, layout seed) -> (clean success minus disturbed success, did the disturbance fire, clean success, disturbed success)."""
    out: dict = {}
    for r in select(rows, model=model, condition=condition, quirk=quirk):
        if r["phase"] in ("eval", "eval_disturbed"):
            out.setdefault((r["task"], r["run_seed"], r["seed"]), {})[r["phase"]] = r
    return {k: (v["eval"]["success"] - v["eval_disturbed"]["success"], bool(v["eval_disturbed"]["fired"]), v["eval"]["success"], v["eval_disturbed"]["success"])
            for k, v in out.items() if "eval" in v and "eval_disturbed" in v}


def recovery_drop_difference(rows, model: str, a: str, b: str, n_boot: int = 10_000, both_fired_only: bool = False, alpha: float = ALPHA_Q4, quirk: bool = False) -> dict:
    """Q4 without mixing in catch knowledge: each condition's own drop from clean to disturbed on the same layouts (clean minus disturbed success),
    then condition `a`'s drop minus condition `b`'s, clustered by (task, run seed). A negative value means `a` loses less to the disturbance.
    The primary version keeps every assigned disturbed episode (an agent can influence whether the disturbance fires). With both_fired_only, only layouts
    where the disturbance fired for both conditions are kept (a sensitivity check). A difference of drops is an association, not proof that the notebook
    taught recovery: a condition that is already at the ceiling cannot drop, and the two conditions can differ in which disturbances happen."""
    la, lb = _layout_drops(rows, model, a, quirk), _layout_drops(rows, model, b, quirk)
    keys = sorted(set(la) & set(lb))
    if both_fired_only:
        keys = [k for k in keys if la[k][1] and lb[k][1]]
    if not keys:
        return {"n_pairs": 0}
    by_cluster: dict = {}
    for k in keys:
        by_cluster.setdefault((k[0], k[1]), []).append((la[k][0], lb[k][0]))
    clusters = [np.array([x[0] - x[1] for x in v], dtype=float) for v in by_cluster.values()]
    est, lo, hi = bootstrap(clusters, np.mean, n_boot, alpha=alpha, strata=[k[0] for k in by_cluster])
    return {"n_pairs": len(clusters), "n_layouts": len(keys), "drop_a": float(np.mean([la[k][0] for k in keys])), "drop_b": float(np.mean([lb[k][0] for k in keys])),
            "diff": est, "lo": lo, "hi": hi, "alpha": alpha}


def conditional_recovery(rows, model: str, a: str, b: str, n_boot: int = 10_000, alpha: float = 0.05, quirk: bool = True) -> dict:
    """Of the layouts a condition solved when played clean, the share it still solved when the disturbance was added. Unlike a drop, this has no floor effect:
    a condition that fails the clean layout is simply not in its denominator. Reported for `a` minus `b`, clustered by (task, run seed)."""
    la, lb = _layout_drops(rows, model, a, quirk), _layout_drops(rows, model, b, quirk)
    clusters_keys = sorted({(k[0], k[1]) for k in list(la) + list(lb)})
    if not clusters_keys:
        return {"n_pairs": 0}
    def counts(l, ck):
        v = [x for k, x in l.items() if (k[0], k[1]) == ck and x[2] == 1]
        return [sum(x[3] for x in v), len(v)]
    arr = np.array([counts(la, ck) + counts(lb, ck) for ck in clusters_keys], dtype=float)           # per cluster: a hits, a clean wins, b hits, b clean wins
    def stat(x):
        x = x.reshape(-1, 4).sum(0)
        return (x[0] / x[1] if x[1] else np.nan) - (x[2] / x[3] if x[3] else np.nan)
    rng = np.random.default_rng(0)
    groups = [np.array([i for i, ck in enumerate(clusters_keys) if ck[0] == g]) for g in dict.fromkeys(ck[0] for ck in clusters_keys)]
    est = float(stat(arr))
    vals = []
    for _ in range(n_boot):
        idx = np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups])
        vals.append(stat(arr[idx]))
    vals = np.array(vals)
    vals = vals[~np.isnan(vals)]
    lo, hi = (np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)]) if len(vals) else (float("nan"), float("nan")))
    ta, tb = arr[:, :2].sum(0), arr[:, 2:].sum(0)
    return {"n_pairs": len(clusters_keys), "a": float(ta[0] / ta[1]) if ta[1] else float("nan"), "b": float(tb[0] / tb[1]) if tb[1] else float("nan"), "diff": est,
            "lo": float(lo), "hi": float(hi), "alpha": alpha, "n_clean_wins_a": int(ta[1]), "n_clean_wins_b": int(tb[1])}


def within_k(rows, model: str, condition: str, ks=(6, 8, 10, 12, 14, 16, 18, 20), phase: str = "eval", quirk: bool = True) -> dict:
    """Share of episodes that succeeded using at most k tool calls."""
    rs = select(rows, model=model, condition=condition, phase=phase, quirk=quirk)
    return {k: float(np.mean([bool(r["success"] and r["calls"] <= k) for r in rs])) if rs else float("nan") for k in ks}

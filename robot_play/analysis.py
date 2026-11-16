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
                        "toolset": cfg.get("toolset", "skills"), "code": cfg.get("code"), "run_seed": cfg["run_seed"], "planned": len(cfg["plan"]), "done": len(rows),
                        "aborted": len(aborts), "aborted_usd": float(sum(a["usd"] for a in aborts)), "complete": len(rows) >= len(cfg["plan"])})
    return out


FALSE_HOLD_WIDTH = 0.03          # metres: every object in these jobs is at least 0.035 m across and an empty closed hand reads 0.019 m, so 'holding' at less than 0.03 m means the fingertips rest on top of the object
SHORT_MOVE = 0.01                # metres: a move_to that answers ok but stops more than this far from the request


def episode_flags(log: list[dict]) -> dict:
    """Tool-state artefacts in one episode's call log (the long log is dropped by `load`, so these are counted here).
    false_hold: a close_gripper that answered `holding` with the fingers nearly closed, so the simulator believed an object was in the hand that was not between the fingers
    (the model then often gets `already holding` from pick and `not holding anything` from place). short_move: a move_to that answered ok but stopped over 1 cm from the request."""
    fh = sm = 0
    for c in log or []:
        res = c.get("result") or {}
        if c.get("tool") == "close_gripper" and res.get("holding") and float(res.get("gripper_width_m", 1.0)) < FALSE_HOLD_WIDTH:
            fh += 1
        if c.get("tool") == "move_to" and res.get("ok") and res.get("tcp_m"):
            a = c.get("args") or {}
            try:
                want = np.array([a["x"], a["y"], a["z"]], dtype=float)
            except KeyError:
                continue
            if float(np.linalg.norm(np.array(res["tcp_m"], dtype=float) - want)) > SHORT_MOVE:
                sm += 1
    return {"false_hold": fh, "short_move": sm}


def load(*dirs: str | Path, complete_only: bool = False) -> list[dict]:
    """One flat row per finished episode (the long tool-call log is dropped). With complete_only, runs that did not finish their whole plan are left
    out, so a paired comparison never mixes runs that stopped early with runs that did not (the incomplete runs are listed by `coverage`)."""
    rows = []
    for d in dirs:
        for f in sorted(Path(d).glob("*.jsonl")):
            cfg, lines, _ = _parse(f)
            if complete_only and cfg and len(lines) < len(cfg["plan"]) and (any(p["phase"] == "practice" for p in cfg["plan"]) or str(cfg.get("condition", "")).startswith("borrowed")):
                continue                         # a run with practice (or one that reads a borrowed notebook) is only meaningful whole; only the frontier first-try files count per finished layout
            for r in lines:
                res = r["result"]
                row = {k: r.get(k) for k in KEEP}
                row.update(episode_flags(r.get("log")))
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
    if stat is np.mean:                                # small-sample rule fixed in PROTOCOL.md section 1: never narrower than a stratified t interval (a percentile bootstrap from few clusters is too narrow)
        ss, df, n = _pooled_ss(clusters, strata)
        if df >= 1:
            from scipy.stats import t as _t
            half = float(_t.ppf(1 - alpha / 2, df) * np.sqrt(ss / df / n))
            lo, hi = min(lo, est - half), max(hi, est + half)
    return est, float(lo), float(hi)


def _pooled_ss(clusters, strata=None) -> tuple[float, int, int]:
    """Within-stratum sum of squares of the cluster means, its degrees of freedom (clusters minus strata) and the number of clusters."""
    means = np.array([float(np.mean(c)) for c in clusters])
    labels = list(strata) if strata is not None else [0] * len(means)
    ss, groups = 0.0, 0
    for g in dict.fromkeys(labels):
        m = means[[i for i, x in enumerate(labels) if x == g]]
        ss += float(((m - m.mean()) ** 2).sum())
        groups += 1
    return ss, len(means) - groups, len(means)


def _floor_half(arms, alpha: float) -> float:
    """Half-width of a sampling-noise floor for a difference of proportions. `arms` lists (successes, episodes) for every proportion in the difference, treated as
    independent binomials (design effect 1: the floor is only meant to bind where a bootstrap and a t interval over run means collapse, which happens when the runs of a
    task all behave the same, and there the data show no clustering). Each proportion gets one pseudo-success and one pseudo-failure (Agresti and Caffo), so the
    width never collapses to zero when every episode of an arm succeeds or every one fails (PROTOCOL.md section 1)."""
    from scipy.stats import norm
    v = 0.0
    for succ, n in arms:
        p = (succ + 1) / (n + 2)
        v += p * (1 - p) / (n + 2)
    return float(norm.ppf(1 - alpha / 2) * np.sqrt(v))


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
    raw = {}

    def pick(cond):
        rs = select(rows, model=model, condition=cond, phase=phase, quirk=quirk)
        if tasks:
            rs = [r for r in rs if r["task"] in tasks]
        if only_fired:
            rs = [r for r in rs if r["fired"]]
        raw[cond] = rs
        return _run_means(rs, metric)
    ma, mb = pick(a), pick(b)
    keys = sorted(set(ma) & set(mb))
    diffs = [np.array([ma[k] - mb[k]]) for k in keys]
    if not diffs:
        return {"n_pairs": 0}
    est, lo, hi = bootstrap(diffs, np.mean, n_boot, alpha=alpha, strata=[k[0] for k in keys])
    if metric == "success":                                    # never narrower than the sampling-noise floor of the episodes behind the two proportions
        ks = set(keys)
        arms = []
        for cond in (a, b):
            x = [r for r in raw[cond] if (r["task"], r["run_seed"]) in ks]
            arms.append((sum(r["success"] for r in x), len(x)))
        half = _floor_half(arms, alpha)
        lo, hi = min(lo, est - half), max(hi, est + half)
    return {"n_pairs": len(keys), "a": float(np.mean([ma[k] for k in keys])), "b": float(np.mean([mb[k] for k in keys])), "diff": est, "lo": lo, "hi": hi, "alpha": alpha}


def curve(rows, model: str, condition: str, metric: str = "success", quirk: bool = True, n_boot: int = 10_000) -> list[dict]:
    """Practice-episode curve: mean `metric` at practice index 0, 1, 2, ... with a cluster-bootstrap interval over runs."""
    rs = select(rows, model=model, condition=condition, phase="practice", quirk=quirk)
    out = []
    for i in sorted({r["idx"] for r in rs}):
        by_run: dict = {}
        for r in rs:
            if r["idx"] == i:
                by_run.setdefault((r["task"], r["run_seed"]), []).append(r[metric])
        est, lo, hi = bootstrap([np.array(v, dtype=float) for v in by_run.values()], np.mean, n_boot, strata=[k[0] for k in by_run])
        out.append({"idx": i, "mean": est, "lo": lo, "hi": hi, "n_runs": len(by_run)})
    return out


def per_success(rows, model: str, condition: str, metric: str, phase: str = "eval", quirk: bool = True) -> float:
    """Total `metric` (cost, calls, sim seconds) divided by the number of successful episodes."""
    rs = select(rows, model=model, condition=condition, phase=phase, quirk=quirk)
    wins = sum(r["success"] for r in rs)
    return float(sum(r[metric] for r in rs) / wins) if wins else float("nan")


def _agresti_caffo(s1: int, n1: int, s2: int, n2: int, z: float, deff1: float = 1.0, deff2: float = 1.0) -> tuple[float, float, float]:
    """Difference of two proportions with one pseudo-success and one pseudo-failure added to each arm (Agresti and Caffo), the variance of each arm multiplied by its
    design effect. Unlike a bootstrap it does not collapse to zero width when every episode succeeds (or every episode fails)."""
    p1, p2 = (s1 + 1) / (n1 + 2), (s2 + 1) / (n2 + 2)
    se = float(np.sqrt(deff1 * p1 * (1 - p1) / (n1 + 2) + deff2 * p2 * (1 - p2) / (n2 + 2)))
    return p1 - p2, p1 - p2 - z * se, p1 - p2 + z * se


def intraclass(rows, model: str, m: int = 4, condition: str = "notebook") -> float:
    """One-way ANOVA intraclass correlation of a model's held-out clean outcomes within a run (clusters of m layouts that share one notebook), computed inside each
    task and pooled by summing sums of squares. Only the notebook runs are used, because only there do the layouts of a run share a memory. Returns 0.0 when it cannot
    be estimated (no variation, or no clusters)."""
    strata: dict = {}
    for r in select(rows, model=model, condition=condition, phase="eval", quirk=True):
        strata.setdefault(r["task"], {}).setdefault(r["run_seed"], []).append(r["success"])
    ssb = ssw = dfb = dfw = 0.0
    for clusters in strata.values():
        ys = [np.array(v, dtype=float) for v in clusters.values() if len(v) == m]
        if len(ys) < 2:
            continue
        means = np.array([y.mean() for y in ys])
        grand = means.mean()
        ssb += m * float(((means - grand) ** 2).sum())
        ssw += float(sum(((y - y.mean()) ** 2).sum() for y in ys))
        dfb += len(ys) - 1
        dfw += len(ys) * (m - 1)
    if dfb == 0 or dfw == 0:
        return 0.0
    msb, msw = ssb / dfb, ssw / dfw
    return max(0.0, (msb - msw) / (msb + (m - 1) * msw)) if (msb + (m - 1) * msw) > 0 else 0.0


def q3_deff(rows, cheap: str, m: int = 4, condition: str = "notebook") -> float:
    """Design effect of the cheap arm, fixed in PROTOCOL.md section 1. With a notebook the four layouts of a run share it: 1 + (m - 1) x the intraclass correlation of that
    model's own notebook held-out outcomes, never below 2 (an intraclass correlation of at least one third is assumed even where the data show none, because at
    ceiling there is nothing to estimate it from). With no memory nothing is shared and the design effect is 1 (the exploratory no-memory row). The exploratory borrowed-notebook rows are treated like the notebook rows."""
    if condition == "none":
        return 1.0
    return max(2.0, 1.0 + (m - 1) * intraclass(rows, cheap, m, condition))      # any memory shared by the four layouts of a run: its own notebook or a borrowed one


def q3_gap(rows, frontier: str, cheap: str, cheap_condition: str = "notebook", margin: float = 0.10, n_boot: int = 10_000, alpha: float = ALPHA_Q3) -> dict:
    """Frontier first-try success minus cheap-with-experience success on the *same* layouts.
    Layouts are nested inside clusters: the (task, run seed) runs whose four held-out layouts all use one notebook. The bootstrap resamples those clusters inside each task.
    Because a bootstrap interval has zero width when every episode succeeds, the reported interval is the wider of the cluster bootstrap and an
    Agresti-Caffo interval whose cheap-arm variance is multiplied by the design effect of `q3_deff` (the frontier arm has no shared memory, so its design effect is 1).
    'Within the margin' needs the whole interval of the gap below +margin."""
    fr = {(r["task"], r["seed"]): r["success"] for r in select(rows, model=frontier, condition="none", quirk=True, phase="eval")}
    ch = {(r["task"], r["seed"]): (r["run_seed"], r["success"]) for r in select(rows, model=cheap, condition=cheap_condition, quirk=True, phase="eval")}
    matched = sorted(set(fr) & set(ch))
    per_cluster: dict = {}
    for k in matched:
        per_cluster.setdefault((k[0], ch[k][0]), []).append(k)
    keys = [k for ks in per_cluster.values() if len(ks) == 4 for k in ks]           # a confirmatory cluster needs all four of its layouts paired; a partly observed block is left out
    if not keys:
        return {"n_layouts": 0, "n_partial_clusters": len(per_cluster)}
    by_cluster: dict = {}
    for k in keys:
        by_cluster.setdefault((k[0], ch[k][0]), []).append(fr[k] - ch[k][1])
    clusters = [np.array(v, dtype=float) for v in by_cluster.values()]
    est, blo, bhi = bootstrap(clusters, np.mean, n_boot, alpha=alpha, strata=[k[0] for k in by_cluster])
    n = len(keys)
    s_fr, s_ch = sum(fr[k] for k in keys), sum(ch[k][1] for k in keys)
    deff = q3_deff(rows, cheap, condition=cheap_condition)
    _, alo, ahi = _agresti_caffo(s_fr, n, s_ch, n, Z[alpha], 1.0, deff)
    lo = min(x for x in (blo, alo) if x == x)
    hi = max(x for x in (bhi, ahi) if x == x)
    return {"n_layouts": n, "n_clusters": len(clusters), "n_partial_clusters": len(per_cluster) - len(clusters), "clusters": sorted(by_cluster), "layouts": keys, "frontier": s_fr / n, "cheap": s_ch / n, "gap": est, "lo": lo, "hi": hi,
            "lo_boot": blo, "hi_boot": bhi, "lo_ac": alo, "hi_ac": ahi, "deff": deff, "within_margin": bool(hi < margin), "margin": margin, "alpha": alpha}


def q3_cost(rows, frontier: str, cheap: str, cheap_condition: str = "notebook", abandoned: dict | None = None) -> dict:
    """Everything the Q3 comparison cost, so a cheap-model-with-practice is never compared to a frontier first try on evaluation cost alone.
    Cheap side: all 12 practice episodes with their notebook rewrites, the clean evaluation episodes, and abandoned attempts, for exactly the runs in the gap.
    Frontier side: its first-try episodes on the same layouts plus ALL of its own abandoned attempts on those tasks (the scope is the task, not the layout, because an abandoned attempt has no layout once it is redone).
    `abandoned` maps (model, toolset, task, condition, quirk, run_seed) to dollars; only skill-level runs are ever counted here."""
    g = q3_gap(rows, frontier, cheap, cheap_condition, n_boot=10)
    if not g.get("n_layouts"):
        return {}
    cl = set(g["clusters"])
    cr = [r for r in select(rows, model=cheap, condition=cheap_condition, quirk=True) if (r["task"], r["run_seed"]) in cl and (r["phase"] == "practice" or (r["phase"] == "eval" and (r["task"], r["seed"]) in set(g["layouts"])))]
    layouts = set(g["layouts"])                                                    # the matched layouts of the whole clusters in the gap, nothing else
    fr = [r for r in select(rows, model=frontier, condition="none", quirk=True, phase="eval") if (r["task"], r["seed"]) in layouts]
    ab = abandoned or {}
    ab_cheap = sum(v for (m, tools, t, c, q, s), v in ab.items() if m == cheap and tools == "skills" and c == cheap_condition and q and (t, s) in cl)
    tasks = {t for t, _ in cl}
    ab_front = sum(v for (m, tools, t, c, q, s), v in ab.items() if m == frontier and tools == "skills" and c == "none" and q and t in tasks)
    ev = sum(r["cost_usd"] for r in cr if r["phase"] == "eval" and (r["task"], r["seed"]) in layouts)
    return {"cheap_eval_only_usd": ev, "cheap_practice_usd": sum(r["cost_usd"] for r in cr if r["phase"] == "practice"), "cheap_abandoned_usd": ab_cheap,
            "cheap_total_usd": sum(r["cost_usd"] for r in cr) + ab_cheap, "frontier_usd": sum(r["cost_usd"] for r in fr) + ab_front, "frontier_abandoned_usd": ab_front,
            "n_frontier_episodes": len(fr), "n_cheap_eval_episodes": len(layouts)}


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
        ks = sorted(set(ma) & set(mb))
        return [k[0] for k in ks], [ma[k] - mb[k] for k in ks]
    tq, dq = diffs(True)
    tc, dc = diffs(False)
    if not dq or not dc:
        return {"n_catch_pairs": len(dq), "n_control_pairs": len(dc)}
    rng = np.random.default_rng(0)
    dq, dc, tq, tc = np.array(dq), np.array(dc), np.array(tq), np.array(tc)

    def draw(d, t):                                              # resample inside each task, so every resample keeps the task mix
        return np.concatenate([d[t == g][rng.integers(0, int((t == g).sum()), int((t == g).sum()))] for g in dict.fromkeys(t)])
    boots = np.array([draw(dq, tq).mean() - draw(dc, tc).mean() for _ in range(n_boot)])
    est = float(dq.mean() - dc.mean())
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    ssq, dfq, nq = _pooled_ss([np.array([v]) for v in dq], list(tq))
    ssc, dfc, nc = _pooled_ss([np.array([v]) for v in dc], list(tc))
    if dfq >= 1 and dfc >= 1:                             # a difference of two stratified means: variances add, degrees of freedom the smaller of the two
        from scipy.stats import t as _t
        half = float(_t.ppf(1 - alpha / 2, min(dfq, dfc)) * np.sqrt(ssq / dfq / nq + ssc / dfc / nc))
        lo, hi = min(lo, est - half), max(hi, est + half)
    return {"n_catch_pairs": len(dq), "n_control_pairs": len(dc), "gain_catch": float(dq.mean()), "gain_control": float(dc.mean()),
            "did": est, "lo": float(lo), "hi": float(hi)}


def tool_interaction(skills_rows, pose_rows, model: str, n_boot: int = 10_000) -> dict:
    """Does the notebook help more (or less) through pose-level tools than through skill-level tools? For each (task, run seed) that exists in the pose cell:
    (notebook minus fresh success with pose tools) minus (the same with skill tools), on the same run seeds and the same layouts. Exploratory."""
    def gains(rows):
        out = {}
        a, b = _run_means(select(rows, model=model, condition="notebook", phase="eval", quirk=True), "success"), _run_means(select(rows, model=model, condition="none", phase="eval", quirk=True), "success")
        for k in set(a) & set(b):
            out[k] = a[k] - b[k]
        return out
    gp, gs = gains(pose_rows), gains(skills_rows)
    keys = sorted(set(gp) & set(gs))
    if not keys:
        return {"n_pairs": 0}
    est, lo, hi = bootstrap([np.array([gp[k] - gs[k]]) for k in keys], np.mean, n_boot, strata=[k[0] for k in keys])
    return {"n_pairs": len(keys), "gain_pose": float(np.mean([gp[k] for k in keys])), "gain_skills": float(np.mean([gs[k] for k in keys])), "diff": est, "lo": lo, "hi": hi}


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
    n = len(keys)                                              # the difference of two drops is four proportions: clean and disturbed success of each condition on the same layouts
    arms = [(sum(la[k][2] for k in keys), n), (sum(la[k][3] for k in keys), n), (sum(lb[k][2] for k in keys), n), (sum(lb[k][3] for k in keys), n)]
    half = _floor_half(arms, alpha)
    lo, hi = min(lo, est - half), max(hi, est + half)
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
    if len(vals):                                         # a ratio of sums has no closed-form t interval: widen the percentile interval by t(df) / z, df = clusters - tasks (PROTOCOL.md section 1)
        from scipy.stats import norm, t as _t
        df = len(clusters_keys) - len(groups)
        if df >= 1:
            f = max(1.0, float(_t.ppf(1 - alpha / 2, df) / norm.ppf(1 - alpha / 2)))
            lo, hi = est - f * (est - lo), est + f * (hi - est)
    ta, tb = arr[:, :2].sum(0), arr[:, 2:].sum(0)
    return {"n_pairs": len(clusters_keys), "a": float(ta[0] / ta[1]) if ta[1] else float("nan"), "b": float(tb[0] / tb[1]) if tb[1] else float("nan"), "diff": est,
            "lo": float(lo), "hi": float(hi), "alpha": alpha, "n_clean_wins_a": int(ta[1]), "n_clean_wins_b": int(tb[1])}


def within_k(rows, model: str, condition: str, ks=(6, 8, 10, 12, 14, 16, 18, 20), phase: str = "eval", quirk: bool = True) -> dict:
    """Share of episodes that succeeded using at most k tool calls."""
    rs = select(rows, model=model, condition=condition, phase=phase, quirk=quirk)
    return {k: float(np.mean([bool(r["success"] and r["calls"] <= k) for r in rs])) if rs else float("nan") for k in ks}

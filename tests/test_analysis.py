import numpy as np

from robot_play.analysis import bootstrap, curve, paired_difference, per_success, q3_gap


def row(model, task, cond, rs, phase, idx, success, seed=0, **kw):
    return dict(model=model, task=task, condition=cond, run_seed=rs, phase=phase, idx=idx, success=success, seed=seed, quirk=True, calls=10, sim_time_s=20.0,
                cost_usd=0.01, fired=1, **kw)


def test_bootstrap_interval_contains_the_truth_and_widens_with_fewer_clusters():
    rng = np.random.default_rng(1)
    many = [rng.binomial(1, 0.7, 4).astype(float) for _ in range(60)]
    est, lo, hi = bootstrap(many, np.mean, 2000)
    assert lo < 0.7 < hi and lo < est < hi
    _, lo2, hi2 = bootstrap(many[:6], np.mean, 2000)
    assert (hi2 - lo2) > (hi - lo)


def test_paired_difference_pairs_by_task_and_run_seed():
    rows = []
    for task in ("stack", "bins"):
        for rs in range(5):
            for j in range(4):
                rows.append(row("m", task, "notebook", rs, "eval", j, 1))
                rows.append(row("m", task, "none", rs, "eval", j, 1 if j == 0 else 0))
    d = paired_difference(rows, "m", "notebook", "none", n_boot=500)
    assert d["n_pairs"] == 10 and abs(d["diff"] - 0.75) < 1e-9 and d["lo"] > 0.5


def test_curve_and_per_success():
    rows = [row("m", "stack", "none", rs, "practice", i, int(i >= 2)) for rs in range(4) for i in range(4)]
    c = curve(rows, "m", "none", n_boot=200)
    assert [x["mean"] for x in c] == [0, 0, 1, 1]
    assert per_success([row("m", "stack", "none", 0, "eval", 0, 1), row("m", "stack", "none", 0, "eval", 1, 0)], "m", "none", "cost_usd") == 0.02


def _q3_rows(n_per_task, small_ok=lambda s: 1, big_ok=lambda s: 1):
    rows = []
    for t in ("stack", "bins", "flasks"):
        for s in range(n_per_task):
            rows.append(row("big", t, "none", 0, "eval", 0, big_ok(s), seed=s))
            rows.append(row("small", t, "notebook", s // 4, "eval", 0, small_ok(s), seed=s))     # four layouts share one run (one notebook)
    return rows


def test_q3_clusters_are_runs_and_the_interval_does_not_collapse_when_everything_succeeds():
    g = q3_gap(_q3_rows(20), "big", "small", n_boot=300)
    assert g["n_layouts"] == 60 and g["n_clusters"] == 15 and g["gap"] == 0
    assert g["hi_boot"] == g["lo_boot"] == 0                                 # the bootstrap alone says 'zero uncertainty'...
    assert g["hi"] - g["lo"] > 0.10                                          # ...the reported interval does not
    assert g["within_margin"] is True                                         # 60 perfect layouts do support a 10-point margin
    few = q3_gap(_q3_rows(4), "big", "small", n_boot=300)                    # 12 perfect layouts do not
    assert few["n_layouts"] == 12 and few["within_margin"] is False


def test_q3_handles_all_failures_and_a_real_gap():
    allfail = q3_gap(_q3_rows(20, small_ok=lambda s: 0, big_ok=lambda s: 0), "big", "small", n_boot=300)
    assert allfail["gap"] == 0 and allfail["hi"] > allfail["lo"] and allfail["frontier"] == 0          # the caller must not treat 'both fail' as a target met
    gap = q3_gap(_q3_rows(20, small_ok=lambda s: 1 if s % 2 else 0), "big", "small", n_boot=300)
    assert gap["gap"] == 0.5 and gap["within_margin"] is False


def test_q3_cost_counts_practice_notebook_and_abandoned_attempts():
    from robot_play.analysis import q3_cost
    rows = _q3_rows(20)
    for t in ("stack", "bins", "flasks"):
        for rs in range(5):
            for i in range(12):
                rows.append(row("small", t, "notebook", rs, "practice", i, 1, seed=i))
    c = q3_cost(rows, "big", "small", abandoned={("small", "skills", "stack", "notebook", True, 0): 0.25, ("small", "pose", "stack", "notebook", True, 0): 9.0})
    assert abs(c["cheap_practice_usd"] - 0.01 * 12 * 15) < 1e-9 and abs(c["cheap_abandoned_usd"] - 0.25) < 1e-9
    assert c["cheap_total_usd"] > c["cheap_eval_only_usd"] + c["cheap_practice_usd"] and c["n_frontier_episodes"] == 60


def test_complete_only_drops_runs_that_stopped_early_and_coverage_reports_them(tmp_path):
    import json
    from robot_play.analysis import coverage, load

    def ep(i, phase):
        return {"run": "r", "model": "m", "task": "stack", "condition": "none", "quirk": True, "run_seed": 0, "phase": phase, "idx": i, "seed": i, "disturbance": None,
                "toolset": "skills", "max_calls": 20, "memory_tokens_in": 0, "cost_usd": 0.01, "retry_usd": 0.0, "turns": 3, "nudges": 0, "refusal": False,
                "result": {"success": True, "calls": 5, "sim_time_s": 5.0, "claimed_done": True, "false_success_claim": False, "disturbance_fired": False},
                "usage": {"input": 10, "output": 5, "cache_read": 0, "cache_write": 0}}
    plan = [{"phase": "practice", "idx": 0, "seed": 0, "disturbance": None}, {"phase": "eval", "idx": 0, "seed": 1, "disturbance": None}]
    cfg = {"model": "m", "task": "stack", "condition": "none", "quirk": True, "toolset": "skills", "run_seed": 0, "plan": plan}
    (tmp_path / "half.jsonl").write_text(json.dumps({"_config": cfg}) + "\n" + json.dumps({"_aborted": {"usd": 0.07, "reason": "x"}}) + "\n" + json.dumps(ep(0, "practice")) + "\n")
    (tmp_path / "full.jsonl").write_text(json.dumps({"_config": {**cfg, "run_seed": 1}}) + "\n" + json.dumps(ep(0, "practice")) + "\n" + json.dumps(ep(0, "eval")) + "\n")
    assert len(load(tmp_path)) == 3 and len(load(tmp_path, complete_only=True)) == 2
    cov = {c["file"]: c for c in coverage(tmp_path)}
    assert cov["half.jsonl"]["complete"] is False and cov["half.jsonl"]["aborted"] == 1 and abs(cov["half.jsonl"]["aborted_usd"] - 0.07) < 1e-9 and cov["full.jsonl"]["complete"]


def _r(cond, quirk, rs, success, phase="eval", seed=0, task="stack", **kw):
    return dict(model="m", task=task, condition=cond, run_seed=rs, phase=phase, idx=seed, seed=seed, quirk=quirk, success=success, calls=8, cost_usd=0.01,
                sim_time_s=10.0, fired=kw.get("fired", 1), max_calls=20, calls_to_success=8 if success else 20)


def test_difference_in_differences_separates_a_catch_gain_from_general_warming_up():
    rows = []
    for rs in range(6):
        for quirk, gain in ((True, 0.6), (False, 0.1)):
            rows += [_r("notebook", quirk, rs, 1 if j < round(4 * (0.3 + gain)) else 0, seed=j) for j in range(4)]
            rows += [_r("none", quirk, rs, 1 if j < round(4 * 0.3) else 0, seed=j) for j in range(4)]
    from robot_play.analysis import did
    d = did(rows, "m", "notebook", "none", n_boot=500)
    assert d["n_catch_pairs"] == 6 and d["did"] > 0.3 and d["gain_catch"] > d["gain_control"]


def test_disturbance_summary_uses_all_assigned_episodes_and_reports_the_firing_rate():
    rows = [_r("none", True, 0, 1, "eval_disturbed", seed=0, fired=1), _r("none", True, 0, 0, "eval_disturbed", seed=1, fired=1),
            _r("none", True, 0, 0, "eval_disturbed", seed=2, fired=0), _r("none", True, 0, 0, "eval_disturbed", seed=3, fired=0)]
    rows += [_r("none", True, 0, 1, "eval", seed=j) for j in range(4)]
    from robot_play.analysis import disturbance_summary
    s = disturbance_summary(rows, "m", "none")
    assert s["fire_rate"] == 0.5 and s["success_all_assigned"] == 0.25 and s["success_when_fired"] == 0.5 and s["success_same_layouts_clean"] == 1.0


def test_recovery_drop_can_be_restricted_to_layouts_where_the_disturbance_fired_in_both_conditions():
    from robot_play.analysis import recovery_drop_difference
    rows = []
    for rs in range(5):
        for j in range(4):
            fired = 0 if j == 3 else 1                                          # on layout 3 the disturbance never fired
            rows += [_r("notebook", True, rs, 1, "eval", seed=j), _r("notebook", True, rs, 1, "eval_disturbed", seed=j, fired=fired),
                     _r("none", True, rs, 1, "eval", seed=j), _r("none", True, rs, 0 if fired else 1, "eval_disturbed", seed=j, fired=fired)]
    allv = recovery_drop_difference(rows, "m", "notebook", "none", n_boot=300, quirk=True)
    both = recovery_drop_difference(rows, "m", "notebook", "none", n_boot=300, both_fired_only=True, quirk=True)
    assert allv["n_layouts"] == 20 and both["n_layouts"] == 15 and both["drop_b"] == 1.0 and abs(allv["drop_b"] - 0.75) < 1e-9
    assert recovery_drop_difference([], "m", "notebook", "none") == {"n_pairs": 0}


def test_recovery_drop_difference_and_within_k():
    rows = []
    for rs in range(5):
        for j in range(4):
            rows += [_r("notebook", True, rs, 1, "eval", seed=j), _r("notebook", True, rs, 1, "eval_disturbed", seed=j),
                     _r("none", True, rs, 1, "eval", seed=j), _r("none", True, rs, 0, "eval_disturbed", seed=j)]
    from robot_play.analysis import recovery_drop_difference, within_k
    d = recovery_drop_difference(rows, "m", "notebook", "none", n_boot=300, quirk=True)
    assert d["drop_a"] == 0 and d["drop_b"] == 1 and d["diff"] == -1
    assert within_k(rows, "m", "none", ks=(6, 8))[8] == 1.0 and within_k(rows, "m", "none", ks=(6, 8))[6] == 0.0


def test_load_skips_the_config_header_and_reads_episode_rows(tmp_path):
    import json
    from robot_play.analysis import load
    ep = {"run": "r", "model": "m", "task": "stack", "condition": "none", "quirk": True, "run_seed": 0, "phase": "eval", "idx": 0, "seed": 1, "disturbance": None,
          "toolset": "skills", "max_calls": 20, "memory_tokens_in": 0, "cost_usd": 0.01, "retry_usd": 0.0, "turns": 3, "nudges": 0, "refusal": False,
          "result": {"success": False, "calls": 20, "sim_time_s": 5.0, "claimed_done": False, "false_success_claim": False, "disturbance_fired": False},
          "usage": {"input": 10, "output": 5, "cache_read": 0, "cache_write": 0}}
    (tmp_path / "a.jsonl").write_text(json.dumps({"_config": {"x": 1}}) + "\n" + json.dumps(ep) + "\n")
    rows = load(tmp_path)
    assert len(rows) == 1 and rows[0]["calls_to_success"] == 20 and rows[0]["success"] == 0


def test_conditional_recovery_has_no_floor_effect_and_the_stratified_bootstrap_keeps_the_task_mix():
    from robot_play.analysis import bootstrap, conditional_recovery
    rows = []
    for t in ("stack", "bins"):
        for rs in range(4):
            for j in range(4):
                # notebook: always clean-solves and always survives; fresh: clean-solves only layout 0 and loses it under the disturbance
                rows += [_r("notebook", True, rs, 1, "eval", seed=j, task=t), _r("notebook", True, rs, 1, "eval_disturbed", seed=j, task=t),
                         _r("none", True, rs, 1 if j == 0 else 0, "eval", seed=j, task=t), _r("none", True, rs, 0, "eval_disturbed", seed=j, task=t)]
    c = conditional_recovery(rows, "m", "notebook", "none", n_boot=300)
    assert c["a"] == 1.0 and c["b"] == 0.0 and c["n_clean_wins_b"] == 8 and c["n_clean_wins_a"] == 32
    # the plain drop of the fresh agent is only 0.25 because it fails the clean layouts: that is the floor effect the conditional measure avoids
    from robot_play.analysis import recovery_drop_difference
    d = recovery_drop_difference(rows, "m", "notebook", "none", n_boot=300, quirk=True)
    assert d["drop_b"] == 0.25 and d["drop_a"] == 0.0
    cl = [np.array([1.0])] * 4 + [np.array([0.0])] * 4
    est, lo, hi = bootstrap(cl, np.mean, 500, strata=["a"] * 4 + ["b"] * 4)
    assert est == 0.5 and lo == hi == 0.5                                       # every resample keeps four clusters of each task


def _cluster_rows(model, outcomes_by_run, tasks=("stack", "bins", "flasks")):
    """held-out rows for one model, notebook condition: outcomes_by_run maps run seed -> list of 4 outcomes, repeated for every task"""
    rows = []
    for t in tasks:
        for rs, outs in outcomes_by_run.items():
            for j, o in enumerate(outs):
                rows.append(row(model, t, "notebook", rs, "eval", j, o, seed=100 * rs + j))
    return rows


def test_intraclass_correlation_is_high_for_all_or_nothing_runs_and_zero_for_independent_layouts():
    from robot_play.analysis import intraclass, q3_deff
    together = _cluster_rows("m", {rs: [rs % 2] * 4 for rs in range(6)})              # every layout of a run behaves the same: fully correlated
    assert intraclass(together, "m") > 0.95 and q3_deff(together, "m") > 3.8
    mixed = _cluster_rows("m", {rs: [1, 0, 1, 0] for rs in range(6)})                  # every run looks alike inside: no clustering
    assert intraclass(mixed, "m") == 0.0 and q3_deff(mixed, "m") == 2.0                 # the floor of 2 applies when the data show none
    at_ceiling = _cluster_rows("m", {rs: [1, 1, 1, 1] for rs in range(6)})             # nothing varies: it cannot be estimated, floor of 2
    assert intraclass(at_ceiling, "m") == 0.0 and q3_deff(at_ceiling, "m") == 2.0


def test_q3_interval_at_ceiling_uses_the_fixed_design_effect():
    gap = q3_gap(_q3_rows(20), "big", "small", n_boot=300)                            # 60 of 60 against 60 of 60
    assert gap["deff"] == 2.0 and abs(gap["hi"] - 0.069) < 0.002 and gap["within_margin"] is True
    near = q3_gap(_q3_rows(20, small_ok=lambda s: 0 if s % 20 == 0 else 1), "big", "small", n_boot=300)   # 57 of 60 cheap
    assert near["hi"] > 0.10 and near["within_margin"] is False                      # a perfect frontier against 95% is not shown to be within 10 points


def test_interval_is_never_narrower_than_the_stratified_t_interval():
    from scipy.stats import t
    rng = np.random.default_rng(3)
    clusters = [np.array([float(v)]) for v in rng.binomial(1, 0.5, 15)]
    strata = ["a"] * 5 + ["b"] * 5 + ["c"] * 5
    est, lo, hi = bootstrap(clusters, np.mean, 3000, alpha=0.025, strata=strata)
    means = np.array([c[0] for c in clusters])
    ss = sum(((means[i:i + 5] - means[i:i + 5].mean()) ** 2).sum() for i in (0, 5, 10))
    half = t.ppf(1 - 0.0125, 12) * np.sqrt(ss / 12 / 15)               # 15 clusters, 3 strata: 12 degrees of freedom
    assert lo <= est - half + 1e-9 and hi >= est + half - 1e-9


def test_tool_interaction_compares_notebook_gains_on_the_same_runs():
    from robot_play.analysis import tool_interaction
    sk, po = [], []
    for t in ("stack", "bins"):
        for rs in range(3):
            for j in range(4):
                sk += [row("m", t, "notebook", rs, "eval", j, 1), row("m", t, "none", rs, "eval", j, 1)]     # no gain with skills
                po += [row("m", t, "notebook", rs, "eval", j, 1), row("m", t, "none", rs, "eval", j, 0)]     # full gain with pose tools
    ti = tool_interaction(sk, po, "m", n_boot=300)
    assert ti["n_pairs"] == 6 and abs(ti["diff"] - 1.0) < 1e-9 and abs(ti["gain_skills"]) < 1e-9


def test_frontier_files_count_per_finished_layout(tmp_path):
    import json
    from robot_play.analysis import load

    def ep(i):
        return {"run": "r", "model": "big", "task": "stack", "condition": "none", "quirk": True, "run_seed": 0, "phase": "eval", "idx": i, "seed": 20000 + i, "disturbance": None,
                "toolset": "skills", "max_calls": 20, "memory_tokens_in": 0, "cost_usd": 0.1, "retry_usd": 0.0, "turns": 3, "nudges": 0, "refusal": False,
                "result": {"success": True, "calls": 5, "sim_time_s": 5.0, "claimed_done": True, "false_success_claim": False, "disturbance_fired": False},
                "usage": {"input": 10, "output": 5, "cache_read": 0, "cache_write": 0}}
    plan = [{"phase": "eval", "idx": i, "seed": 20000 + i, "disturbance": None} for i in range(3)]     # a first-try file has no practice phase
    cfg = {"model": "big", "task": "stack", "condition": "none", "quirk": True, "toolset": "skills", "run_seed": 0, "plan": plan}
    (tmp_path / "a.jsonl").write_text("\n".join(json.dumps(x) for x in [{"_config": cfg}, ep(0), ep(1)]) + "\n")       # 2 of 3 layouts finished
    assert len(load(tmp_path, complete_only=True)) == 2


def test_q3_leaves_out_clusters_that_are_only_partly_paired():
    rows = _q3_rows(20)
    rows = [r for r in rows if not (r["model"] == "big" and r["task"] == "stack" and r["seed"] == 3)]       # one frontier layout of one block is missing
    g = q3_gap(rows, "big", "small", n_boot=100)
    assert g["n_partial_clusters"] == 1 and g["n_layouts"] == 56 and g["n_clusters"] == 14
    from robot_play.analysis import q3_cost
    c = q3_cost(rows, "big", "small")
    assert c["n_frontier_episodes"] == 56 and c["n_cheap_eval_episodes"] == 56


def test_sampling_noise_floor_keeps_a_degenerate_interval_open():
    rows = []
    for task in ("stack", "bins", "flasks"):
        for rs in range(6):
            for j in range(4):
                rows.append(row("m", task, "notebook", rs, "eval", j, 1))                 # every episode with a notebook succeeds
                rows.append(row("m", task, "none", rs, "eval", j, 0 if task == "stack" else 1))   # stack always fails without; the other two always succeed
    d = paired_difference(rows, "m", "notebook", "none", n_boot=500, alpha=0.025)
    assert abs(d["diff"] - 1 / 3) < 1e-9 and d["hi"] - d["lo"] > 0.10                     # a plain bootstrap or t interval would have zero width here
    all_same = [row("m", t, c, rs, "eval", j, 1) for t in ("stack", "bins") for rs in range(5) for j in range(4) for c in ("notebook", "none")]
    e = paired_difference(all_same, "m", "notebook", "none", n_boot=300)
    assert e["diff"] == 0 and e["hi"] > 0.02 and e["lo"] < -0.02                          # both arms perfect: the width is the floor, a few points at 40 episodes


def test_recovery_drop_floor_is_open_when_every_layout_behaves_the_same():
    from robot_play.analysis import recovery_drop_difference
    rows = []
    for rs in range(6):
        for task in ("stack", "bins"):
            for j in range(4):
                for cond, dist_ok in (("notebook", 1), ("none", 0)):
                    clean = row("m", task, cond, rs, "eval", j, 1, seed=100 * rs + j)
                    dist = row("m", task, cond, rs, "eval_disturbed", j, dist_ok, seed=100 * rs + j)
                    clean["quirk"] = dist["quirk"] = False
                    rows += [clean, dist]
    d = recovery_drop_difference(rows, "m", "notebook", "none", n_boot=300)
    assert d["diff"] == -1.0 and d["hi"] - d["lo"] > 0.15

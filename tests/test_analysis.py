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
    c = q3_cost(rows, "big", "small", abandoned={("small", "stack", "notebook", True, 0): 0.25})
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

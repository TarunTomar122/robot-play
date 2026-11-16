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


def test_q3_needs_the_whole_interval_under_the_margin():
    rows = []
    for t in ("stack", "bins", "flasks"):
        for s in range(10):
            rows.append(row("big", t, "none", 0, "eval", 0, 1, seed=s))
            rows.append(row("small", t, "notebook", 0, "eval", 0, 1, seed=s))
    g = q3_gap(rows, "big", "small", n_boot=300)
    assert g["n_layouts"] == 30 and g["gap"] == 0 and g["within_margin"] is True
    for r in rows:
        if r["model"] == "small" and r["seed"] < 6:
            r["success"] = 0
    assert q3_gap(rows, "big", "small", n_boot=300)["within_margin"] is False


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


def test_recovery_drop_difference_and_within_k():
    rows = []
    for rs in range(5):
        for j in range(4):
            rows += [_r("notebook", True, rs, 1, "eval", seed=j), _r("notebook", True, rs, 1, "eval_disturbed", seed=j),
                     _r("none", True, rs, 1, "eval", seed=j), _r("none", True, rs, 0, "eval_disturbed", seed=j)]
    from robot_play.analysis import recovery_drop_difference, within_k
    d = recovery_drop_difference(rows, "m", "notebook", "none", n_boot=300)
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

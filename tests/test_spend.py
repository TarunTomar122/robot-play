import json
import multiprocessing as mp

import pytest

from robot_play.spend import BudgetExceeded, SpendMeter, cost_usd, estimate_tokens


def meter(tmp_path, **caps):
    return SpendMeter(tmp_path / "spend", caps={"anthropic": caps.get("anthropic", 1.0), "openai": caps.get("openai", 1.0)})


def test_over_budget_call_is_refused_and_logged(tmp_path):
    m = meter(tmp_path, anthropic=1.0)
    r = m.reserve("claude-fable-5-2", est_input_tokens=50_000, max_output_tokens=10_000)      # worst case $0.80
    with pytest.raises(BudgetExceeded):
        m.reserve("claude-fable-5-2", est_input_tokens=50_000, max_output_tokens=10_000)     # another $0.80 would pass the $1 cap
    rows = [json.loads(l) for l in m.ledger.read_text().splitlines()]
    assert [x["kind"] for x in rows] == ["reserve", "refused"]
    m.release(r)


def test_settle_replaces_reservation_with_real_cost(tmp_path):
    m = meter(tmp_path, anthropic=1.0)
    r = m.reserve("claude-haiku-5-5", 10_000, 4_000)
    real = m.settle(r, input_tokens=9_000, output_tokens=500)
    assert real == pytest.approx(9_000 * 0.10 / 1e6 + 500 * 0.50 / 1e6)
    t = m.totals()["anthropic"]
    assert t["reserved"] == 0 and t["spent"] == pytest.approx(real)


def test_cache_tokens_are_priced(tmp_path):
    base = cost_usd("claude-sonnet-5-5", input_tokens=1000)
    assert cost_usd("claude-sonnet-5-5", cache_read_tokens=1000) == pytest.approx(0.1 * base)
    assert cost_usd("claude-sonnet-5-5", cache_write_tokens=1000) == pytest.approx(1.25 * base)


def test_unknown_outcome_charges_the_whole_reservation(tmp_path):
    m = meter(tmp_path)
    r = m.reserve("gpt-6-luna", 10_000, 4_000)
    assert m.settle_unknown(r, "timeout") == pytest.approx(r.amount)
    assert m.totals()["openai"]["spent"] == pytest.approx(r.amount)


def test_release_costs_nothing(tmp_path):
    m = meter(tmp_path)
    m.release(m.reserve("gpt-6-luna", 10_000, 4_000), "bad request")
    assert m.totals()["openai"]["spent"] == 0


def test_state_survives_a_restart_and_reconciles(tmp_path):
    m = meter(tmp_path)
    m.settle(m.reserve("gpt-6-astra", 2_000, 1_000), 1_800, 300)
    m2 = meter(tmp_path)                                  # a new process opening the same folder
    assert m2.totals()["openai"]["spent"] == pytest.approx(m.totals()["openai"]["spent"])
    rec = m2.reconcile()
    assert rec["matches_state"] and rec["open_reservations"] == 0 and rec["per_model"]["gpt-6-astra"]["calls"] == 1


def test_estimate_is_conservative():
    assert estimate_tokens("x" * 3000) >= 1000


def _worker(args):
    root, n = args
    m = SpendMeter(root, caps={"anthropic": 1.0, "openai": 1.0})
    ok = 0
    for _ in range(n):
        try:
            r = m.reserve("claude-haiku-5-5", 40_000, 20_000)            # worst case $0.014
        except BudgetExceeded:
            continue
        m.settle(r, 40_000, 20_000)                                       # spends the full worst case
        ok += 1
    return ok


def test_concurrent_workers_cannot_exceed_the_cap(tmp_path):
    root = str(tmp_path / "spend")
    SpendMeter(root, caps={"anthropic": 1.0, "openai": 1.0})
    with mp.get_context("fork").Pool(8) as pool:
        done = sum(pool.map(_worker, [(root, 40)] * 8))                   # 320 attempts of $0.014 against a $1 cap
    m = SpendMeter(root, caps={"anthropic": 1.0, "openai": 1.0})
    spent = m.totals()["anthropic"]["spent"]
    assert spent <= 1.0 + 1e-9 and done == round(spent / 0.014) and done >= 60
    assert m.reconcile()["matches_state"]

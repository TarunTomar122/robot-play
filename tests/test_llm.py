"""Provider plumbing against fake SDK clients: the spend meter must see every attempt, and errors must be charged the cautious way."""
from types import SimpleNamespace as NS

import pytest

from robot_play import llm
from robot_play.llm import AnthropicProvider, OpenAIProvider
from robot_play.spend import BudgetExceeded, SpendMeter


def _anthropic(tmp_path, create):
    p = AnthropicProvider.__new__(AnthropicProvider)
    import anthropic
    p.anthropic, p.model, p.meter, p.run_id = anthropic, "claude-haiku-5-5", SpendMeter(tmp_path, {"anthropic": 1.0, "openai": 1.0}), "t"
    p.client = NS(messages=NS(create=create))
    return p


def _msg(stop="end_turn", content=None, **u):
    usage = NS(input_tokens=u.get("i", 1000), output_tokens=u.get("o", 200), cache_read_input_tokens=u.get("cr", 0), cache_creation_input_tokens=u.get("cw", 0))
    return NS(content=content or [NS(type="text", text="hi")], stop_reason=stop, usage=usage)


def test_success_is_settled_with_real_usage_including_cache(tmp_path):
    p = _anthropic(tmp_path, lambda **kw: _msg(i=1000, o=200, cr=5000, cw=100))
    s = p.session("sys", "go")
    turn = s.send()
    assert turn.stop == "end" and turn.usage == {"input": 1000, "output": 200, "cache_read": 5000, "cache_write": 100}
    t = p.meter.totals()["anthropic"]
    assert t["reserved"] == 0 and t["spent"] == pytest.approx((1000 * 0.10 + 200 * 0.50 + 5000 * 0.01 + 100 * 0.125) / 1e6, abs=2e-6)


def test_anthropic_requests_one_tool_call_per_turn_and_default_sampling(tmp_path):
    seen = []
    p = _anthropic(tmp_path, lambda **kw: seen.append(kw) or _msg())
    p.session("sys", "go").send()
    kw = seen[0]
    assert kw["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True} and kw["output_config"] == {"effort": "low"}
    assert not {"temperature", "top_p", "top_k", "thinking"} & set(kw)


def test_tool_use_blocks_become_calls_and_the_assistant_turn_is_kept(tmp_path):
    blocks = [NS(type="thinking", thinking=""), NS(type="tool_use", id="tu1", name="pick", input={"object": "cube_red"})]
    p = _anthropic(tmp_path, lambda **kw: _msg("tool_use", blocks))
    s = p.session("sys", "go")
    turn = s.send()
    assert [(c.id, c.name, c.args) for c in turn.calls] == [("tu1", "pick", {"object": "cube_red"})]
    assert s.messages[-1]["role"] == "assistant" and s.messages[-1]["content"] is blocks      # thinking blocks go back unchanged
    s.send(results=[(turn.calls[0], "{}")])
    assert s.messages[-2]["content"][0]["tool_use_id"] == "tu1"


def test_a_server_error_charges_the_whole_reservation_and_a_bad_request_charges_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    import anthropic
    import httpx2 as httpx
    req = httpx.Request("POST", "http://x")
    n = {"i": 0}

    def flaky(**kw):
        n["i"] += 1
        if n["i"] == 1:
            raise anthropic.InternalServerError("boom", response=httpx.Response(500, request=req), body=None)
        if n["i"] == 2:
            raise anthropic.BadRequestError("bad", response=httpx.Response(400, request=req), body=None)
        return _msg()
    p = _anthropic(tmp_path, flaky)
    turn = p.session("sys", "go").send()
    assert turn.stop == "end"
    kinds = [__import__("json").loads(x)["kind"] for x in p.meter.ledger.read_text().splitlines() if '"kind": "reserve"' not in x]
    assert kinds == ["settle_unknown", "release", "settle"]
    assert p.meter.reconcile()["matches_state"] and p.meter.totals()["anthropic"]["reserved"] == 0


def test_a_refused_budget_sends_nothing(tmp_path):
    calls = []
    p = _anthropic(tmp_path, lambda **kw: calls.append(1) or _msg())
    p.meter.caps["anthropic"] = 0.001
    with pytest.raises(BudgetExceeded):
        p.session("sys" * 5000, "go").send()
    assert calls == []


def test_openai_session_chains_responses_and_reads_cached_tokens(tmp_path):
    seen = []

    def create(**kw):
        seen.append(kw)
        out = [NS(type="function_call", call_id="fc1", name="observe", arguments="{}")] if len(seen) == 1 else [NS(type="message")]
        return NS(id=f"r{len(seen)}", output=out, output_text="" if len(seen) == 1 else "ok", status="completed",
                  usage=NS(input_tokens=3000, output_tokens=100, input_tokens_details=NS(cached_tokens=2000)))
    p = OpenAIProvider.__new__(OpenAIProvider)
    import openai
    p.openai, p.model, p.meter, p.run_id = openai, "gpt-6-luna", SpendMeter(tmp_path, {"anthropic": 1.0, "openai": 1.0}), "t"
    p.client = NS(responses=NS(create=create))
    s = p.session("sys", "go")
    t1 = s.send()
    assert t1.calls[0].name == "observe" and t1.usage == {"input": 1000, "output": 100, "cache_read": 2000, "cache_write": 0}
    t2 = s.send(results=[(t1.calls[0], "{}")])
    assert t2.stop == "end" and seen[1]["previous_response_id"] == "r1" and seen[1]["input"][0]["type"] == "function_call_output"
    assert seen[0]["reasoning"] == {"effort": "low"} and "temperature" not in seen[0] and seen[0]["parallel_tool_calls"] is False

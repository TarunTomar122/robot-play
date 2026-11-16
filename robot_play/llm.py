"""LLM providers: one small interface over Anthropic Messages and OpenAI Responses, with the spend meter around every call.

Plain words: a *session* is one conversation (one episode). `send()` gives the model the latest tool results and returns what it said and
which tools it wants to call. Before each call we reserve its worst-case cost in the spend meter, and after it we settle the real cost.

One tool call per turn (parallel calls are switched off for both providers), so every call sees the result of the one before it.
Sampling is left at each provider's default on purpose (a non-default temperature is rejected by the newer Claude models anyway), and
reasoning effort is `low` for every model, so differences between models come from the models and from memory, not from tuned settings.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .spend import PRICE_SAFETY, PROVIDER_OF, BudgetExceeded, SpendMeter, cost_usd, estimate_tokens
from .tools import TOOLS

MAX_OUTPUT_TOKENS = 6000          # per model turn, thinking included
ATTEMPTS = 8                       # rate limits and outages get patient retries (backoff up to 60 s); every attempt is metered


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class Turn:
    text: str
    calls: list[ToolCall]
    usage: dict                    # input (uncached), output, cache_read, cache_write
    stop: str                      # "tool_use" | "end" | "refusal" | "max_tokens" | "error"
    latency_s: float = 0.0
    error: str = ""


def add_usage(a: dict, b: dict) -> dict:
    """`reasoning` is how many of the output tokens were spent thinking, where the provider reports it (OpenAI does; Anthropic folds it into `output`)."""
    return {k: a.get(k, 0) + b.get(k, 0) for k in ("input", "output", "cache_read", "cache_write", "reasoning")}


def load_env_keys(path: str | Path = "~/Documents/personal/Reset/.env") -> None:
    """Put the provider keys from an env file into os.environ without ever printing them. Existing variables win."""
    p = Path(path).expanduser()
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.removeprefix("export ").split("=", 1)
        if k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY") and k not in os.environ:
            os.environ[k] = v.strip().strip('"').strip("'")


class Tally:
    """Every dollar a provider object has paid, at list price, including attempts that failed and were retried and the notebook-rewriting calls.
    (An attempt that may have been billed but returned no usage is counted at its full reservation, the cautious way.)"""
    def __init__(self):
        self.usd = 0.0
        self.retry_usd = 0.0
        self.attempts = 0
        self.failed_attempts = 0


def _metered(p, est_in: int, call_fn):
    """Run one paid call under the spend meter, retrying a few times. `call_fn()` returns (result, usage_dict).
    Returns (result, usage, seconds, error); result is None if every attempt failed."""
    last = ""
    for attempt in range(ATTEMPTS):
        res = p.meter.reserve(p.model, est_in, MAX_OUTPUT_TOKENS, p.run_id)      # raises BudgetExceeded: nothing is sent
        p.tally.attempts += 1
        t0 = time.time()
        try:
            out, usage = call_fn()
        except Exception as e:                                                   # noqa: BLE001
            kind = p._classify(e)                                                # "free" (never processed), "fatal", or "billed?" (maybe billed)
            last = f"{type(e).__name__}: {str(e)[:200]}"
            p.tally.failed_attempts += 1
            if kind in ("free", "fatal"):
                p.meter.release(res, last)
            else:
                paid = p.meter.settle_unknown(res, last)
                p.tally.usd += paid / max(1.0, PRICE_SAFETY[PROVIDER_OF(p.model)])
                p.tally.retry_usd += paid / max(1.0, PRICE_SAFETY[PROVIDER_OF(p.model)])
            if kind == "fatal":
                raise
            time.sleep(min(2 ** attempt * 2, 60))
            continue
        p.meter.settle(res, usage["input"], usage["output"], usage["cache_read"], usage["cache_write"])
        p.tally.usd += cost_usd(p.model, usage["input"], usage["output"], usage["cache_read"], usage["cache_write"])
        return out, usage, time.time() - t0, ""
    return None, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}, 0.0, last


def _ctx_total(usage: dict) -> int:
    return usage["input"] + usage["cache_read"] + usage["cache_write"] + usage["output"]


# --------------------------------------------------------------------------------------------- Anthropic
class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, meter: SpendMeter, run_id: str = ""):
        import anthropic
        load_env_keys()
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(max_retries=0, timeout=300.0)       # retries are done by `_metered` so each attempt is metered
        self.model, self.meter, self.run_id = model, meter, run_id
        self.tally = Tally()

    def _classify(self, e: Exception) -> str:
        a = self.anthropic
        if isinstance(e, (a.AuthenticationError, a.PermissionDeniedError)):
            return "fatal"
        if isinstance(e, (a.BadRequestError, a.NotFoundError, a.RateLimitError)):
            return "free"
        return "billed?"

    def _usage(self, r) -> dict:
        u = r.usage
        return {"input": u.input_tokens or 0, "output": u.output_tokens or 0,
                "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0, "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}

    def _create(self, **kw):
        return self.client.messages.create(model=self.model, max_tokens=MAX_OUTPUT_TOKENS, output_config={"effort": "low"},
                                           cache_control={"type": "ephemeral"}, **kw)

    def session(self, system: str, first_user: str, tools: list | None = None) -> "AnthropicSession":
        return AnthropicSession(self, system, first_user, tools or TOOLS)

    def complete(self, system: str, user: str) -> tuple[str, dict]:
        """One tool-free call (used to rewrite the notebook)."""
        def go():
            r = self._create(system=system, messages=[{"role": "user", "content": user}])
            return r, self._usage(r)
        r, usage, _, _ = _metered(self, estimate_tokens(system + user), go)
        if r is None:
            return "", usage
        return "".join(b.text for b in r.content if b.type == "text").strip(), usage


class AnthropicSession:
    def __init__(self, p: AnthropicProvider, system: str, first_user: str, tools: list):
        self.p, self.system = p, system
        self.messages = [{"role": "user", "content": first_user}]
        self.tools = [dict(t) for t in tools]
        self.ctx = 0                    # real token count of the conversation so far (input + output of the last call), 0 before the first call

    def send(self, results: list[tuple[ToolCall, str]] | None = None, nudge: str | None = None) -> Turn:
        if results:
            self.messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": c.id, "content": out} for c, out in results]})
        elif nudge:
            self.messages.append({"role": "user", "content": nudge})
        new = results and sum(estimate_tokens(out) for _, out in results) or (estimate_tokens(nudge) if nudge else 0)
        # upper bound on this call's input: everything the last call read and wrote (the provider's own count) plus the new text, with 10% slack;
        # the very first call has no earlier count, so it uses the character-based estimate of the whole prompt
        est = int(self.ctx * 1.1) + new if self.ctx else estimate_tokens(self.system + json.dumps(self.tools) + json.dumps(self.messages, default=str))

        def go():
            r = self.p._create(system=self.system, tools=self.tools, messages=self.messages,
                               tool_choice={"type": "auto", "disable_parallel_tool_use": True})
            return r, self.p._usage(r)
        r, usage, dt, err = _metered(self.p, est, go)
        if r is None:
            return Turn("", [], usage, "error", error=err)
        self.ctx = _ctx_total(usage)
        text = "".join(b.text for b in r.content if b.type == "text").strip()
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in r.content if b.type == "tool_use"]
        self.messages.append({"role": "assistant", "content": r.content})          # thinking blocks must be passed back unchanged
        stop = {"tool_use": "tool_use", "end_turn": "end", "max_tokens": "max_tokens", "refusal": "refusal"}.get(r.stop_reason, r.stop_reason or "end")
        if stop == "tool_use" and not calls:
            stop = "end"
        return Turn(text, calls, usage, stop, dt)


# --------------------------------------------------------------------------------------------- OpenAI
def _openai_tools(tools: list) -> list[dict]:
    return [{"type": "function", "name": t["name"], "description": t["description"], "parameters": t["input_schema"], "strict": False} for t in tools]


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, meter: SpendMeter, run_id: str = ""):
        import openai
        load_env_keys()
        self.openai = openai
        self.client = openai.OpenAI(max_retries=0, timeout=300.0)
        self.model, self.meter, self.run_id = model, meter, run_id
        self.tally = Tally()

    def _classify(self, e: Exception) -> str:
        o = self.openai
        if isinstance(e, (o.AuthenticationError, o.PermissionDeniedError)):
            return "fatal"
        if isinstance(e, (o.BadRequestError, o.NotFoundError, o.RateLimitError)):
            return "free"
        return "billed?"

    def _usage(self, r) -> dict:
        u = r.usage
        cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
        reasoning = getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0
        return {"input": max(0, (u.input_tokens or 0) - cached), "output": u.output_tokens or 0, "cache_read": cached, "cache_write": 0, "reasoning": reasoning}

    def _create(self, **kw):
        return self.client.responses.create(model=self.model, max_output_tokens=MAX_OUTPUT_TOKENS, reasoning={"effort": "low"}, store=True, **kw)

    def session(self, system: str, first_user: str, tools: list | None = None) -> "OpenAISession":
        return OpenAISession(self, system, first_user, tools or TOOLS)

    def complete(self, system: str, user: str) -> tuple[str, dict]:
        def go():
            r = self._create(instructions=system, input=user)
            return r, self._usage(r)
        r, usage, _, _ = _metered(self, estimate_tokens(system + user), go)
        if r is None:
            return "", usage
        return (r.output_text or "").strip(), usage


class OpenAISession:
    def __init__(self, p: OpenAIProvider, system: str, first_user: str, tools: list):
        self.p, self.system = p, system
        self.prev: str | None = None
        self.pending: list = [{"role": "user", "content": first_user}]
        self.tools = _openai_tools(tools)
        self.ctx = 0

    def send(self, results: list[tuple[ToolCall, str]] | None = None, nudge: str | None = None) -> Turn:
        if results:
            self.pending = [{"type": "function_call_output", "call_id": c.id, "output": out} for c, out in results]
        elif nudge:
            self.pending = [{"role": "user", "content": nudge}]
        new = estimate_tokens(json.dumps(self.pending, default=str))
        est = int(self.ctx * 1.1) + new if self.ctx else estimate_tokens(self.system + json.dumps(self.tools)) + new

        def go():
            kw = dict(instructions=self.system, input=self.pending, tools=self.tools, parallel_tool_calls=False)
            if self.prev:
                kw["previous_response_id"] = self.prev
            r = self.p._create(**kw)
            return r, self.p._usage(r)
        r, usage, dt, err = _metered(self.p, est, go)
        if r is None:
            return Turn("", [], usage, "error", error=err)
        self.ctx = _ctx_total(usage)
        self.prev = r.id
        calls = []
        for item in r.output:
            if item.type == "function_call":
                try:
                    args = json.loads(item.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                calls.append(ToolCall(item.call_id, item.name, args if isinstance(args, dict) else {}))
        stop = "tool_use" if calls else ("max_tokens" if getattr(r, "status", "") == "incomplete" else "end")
        return Turn((r.output_text or "").strip(), calls, usage, stop, dt)


# --------------------------------------------------------------------------------------------- scripted fake (tests, no money)
class FakeProvider:
    """Plays back a list of turns; each turn is a list of (tool, args) or a string. Costs nothing and never touches the network."""
    name = "fake"

    def __init__(self, script, notebook_text: str = "notes"):
        self.script, self.notebook_text, self.model = script, notebook_text, "claude-haiku-5-5"
        self.tally = Tally()
        self.sessions = 0
        self.completes = 0
        self.systems: list[str] = []

    def session(self, system: str, first_user: str, tools: list | None = None):
        self.sessions += 1
        self.systems.append(system)
        return _FakeSession(list(self.script), self)

    def complete(self, system: str, user: str):
        self.completes += 1
        u = {"input": 10, "output": 5, "cache_read": 0, "cache_write": 0}
        self.tally.usd += cost_usd(self.model, **{"input_tokens": 10, "output_tokens": 5})
        return self.notebook_text, u


class _FakeSession:
    def __init__(self, script, owner):
        self.script, self.n, self.owner = script, 0, owner

    def send(self, results=None, nudge=None) -> Turn:
        usage = {"input": 100, "output": 20, "cache_read": 0, "cache_write": 0}
        self.owner.tally.usd += cost_usd(self.owner.model, input_tokens=100, output_tokens=20)
        if not self.script:
            return Turn("done", [], usage, "end")
        step = self.script.pop(0)
        if isinstance(step, str):
            return Turn(step, [], usage, "end")
        self.n += 1
        return Turn("", [ToolCall(f"c{self.n}_{i}", name, args) for i, (name, args) in enumerate(step)], usage, "tool_use")


def make_provider(model: str, meter: SpendMeter, run_id: str = ""):
    if model.startswith("claude"):
        return AnthropicProvider(model, meter, run_id)
    return OpenAIProvider(model, meter, run_id)

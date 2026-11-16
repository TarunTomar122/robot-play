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

from .spend import BudgetExceeded, SpendMeter, cost_usd, estimate_tokens
from .tools import TOOLS

MAX_OUTPUT_TOKENS = 6000          # per model turn, thinking included
ATTEMPTS = 3


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
    return {k: a.get(k, 0) + b.get(k, 0) for k in ("input", "output", "cache_read", "cache_write")}


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


def _metered(meter: SpendMeter, model: str, run_id: str, est_in: int, call_fn, classify_error):
    """Run one paid call under the spend meter, retrying a few times. `call_fn()` returns (result, usage_dict)."""
    last = ""
    for attempt in range(ATTEMPTS):
        res = meter.reserve(model, est_in, MAX_OUTPUT_TOKENS, run_id)       # raises BudgetExceeded: nothing is sent
        t0 = time.time()
        try:
            out, usage = call_fn()
        except Exception as e:                                               # noqa: BLE001
            kind = classify_error(e)                                         # "free" (never processed) or "billed?" (maybe billed)
            last = f"{type(e).__name__}: {str(e)[:200]}"
            if kind in ("free", "fatal"):
                meter.release(res, last)
            else:
                meter.settle_unknown(res, last)
            if kind == "fatal":
                raise
            time.sleep(min(2 ** attempt * 2, 20))
            continue
        meter.settle(res, usage["input"], usage["output"], usage["cache_read"], usage["cache_write"])
        return out, usage, time.time() - t0
    return None, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}, 0.0, last


# --------------------------------------------------------------------------------------------- Anthropic
class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, meter: SpendMeter, run_id: str = ""):
        import anthropic
        load_env_keys()
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(max_retries=0, timeout=300.0)       # retries are done by `_metered` so each attempt is metered
        self.model, self.meter, self.run_id = model, meter, run_id

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

    def session(self, system: str, first_user: str) -> "AnthropicSession":
        return AnthropicSession(self, system, first_user)

    def complete(self, system: str, user: str) -> tuple[str, dict]:
        """One tool-free call (used to rewrite the notebook)."""
        def go():
            r = self._create(system=system, messages=[{"role": "user", "content": user}])
            return r, self._usage(r)
        out = _metered(self.meter, self.model, self.run_id, estimate_tokens(system + user), go, self._classify)
        r, usage = out[0], out[1]
        if r is None:
            return "", usage
        return "".join(b.text for b in r.content if b.type == "text").strip(), usage


class AnthropicSession:
    def __init__(self, p: AnthropicProvider, system: str, first_user: str):
        self.p, self.system = p, system
        self.messages = [{"role": "user", "content": first_user}]
        self.tools = [dict(t) for t in TOOLS]

    def send(self, results: list[tuple[ToolCall, str]] | None = None, nudge: str | None = None) -> Turn:
        if results:
            self.messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": c.id, "content": out} for c, out in results]})
        elif nudge:
            self.messages.append({"role": "user", "content": nudge})
        est = estimate_tokens(self.system + json.dumps(self.tools) + json.dumps(self.messages, default=str))

        def go():
            r = self.p._create(system=self.system, tools=self.tools, messages=self.messages,
                               tool_choice={"type": "auto", "disable_parallel_tool_use": True})
            return r, self.p._usage(r)
        out = _metered(self.p.meter, self.p.model, self.p.run_id, est, go, self.p._classify)
        if out[0] is None:
            return Turn("", [], out[1], "error", error=out[3])
        r, usage, dt = out
        text = "".join(b.text for b in r.content if b.type == "text").strip()
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in r.content if b.type == "tool_use"]
        self.messages.append({"role": "assistant", "content": r.content})          # thinking blocks must be passed back unchanged
        stop = {"tool_use": "tool_use", "end_turn": "end", "max_tokens": "max_tokens", "refusal": "refusal"}.get(r.stop_reason, r.stop_reason or "end")
        if stop == "tool_use" and not calls:
            stop = "end"
        return Turn(text, calls, usage, stop, dt)


# --------------------------------------------------------------------------------------------- OpenAI
def _openai_tools() -> list[dict]:
    return [{"type": "function", "name": t["name"], "description": t["description"], "parameters": t["input_schema"], "strict": False} for t in TOOLS]


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, meter: SpendMeter, run_id: str = ""):
        import openai
        load_env_keys()
        self.openai = openai
        self.client = openai.OpenAI(max_retries=0, timeout=300.0)
        self.model, self.meter, self.run_id = model, meter, run_id

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
        return {"input": max(0, (u.input_tokens or 0) - cached), "output": u.output_tokens or 0, "cache_read": cached, "cache_write": 0}

    def _create(self, **kw):
        return self.client.responses.create(model=self.model, max_output_tokens=MAX_OUTPUT_TOKENS, reasoning={"effort": "low"}, store=True, **kw)

    def session(self, system: str, first_user: str) -> "OpenAISession":
        return OpenAISession(self, system, first_user)

    def complete(self, system: str, user: str) -> tuple[str, dict]:
        def go():
            r = self._create(instructions=system, input=user)
            return r, self._usage(r)
        out = _metered(self.meter, self.model, self.run_id, estimate_tokens(system + user), go, self._classify)
        r, usage = out[0], out[1]
        if r is None:
            return "", usage
        return (r.output_text or "").strip(), usage


class OpenAISession:
    def __init__(self, p: OpenAIProvider, system: str, first_user: str):
        self.p, self.system = p, system
        self.prev: str | None = None
        self.pending: list = [{"role": "user", "content": first_user}]
        self.tools = _openai_tools()

    def send(self, results: list[tuple[ToolCall, str]] | None = None, nudge: str | None = None) -> Turn:
        if results:
            self.pending = [{"type": "function_call_output", "call_id": c.id, "output": out} for c, out in results]
        elif nudge:
            self.pending = [{"role": "user", "content": nudge}]
        est = estimate_tokens(self.system + json.dumps(self.tools) + json.dumps(self.pending, default=str)) + (6000 if self.prev else 0)

        def go():
            kw = dict(instructions=self.system, input=self.pending, tools=self.tools, parallel_tool_calls=False)
            if self.prev:
                kw["previous_response_id"] = self.prev
            r = self.p._create(**kw)
            return r, self.p._usage(r)
        out = _metered(self.p.meter, self.p.model, self.p.run_id, est, go, self.p._classify)
        if out[0] is None:
            return Turn("", [], out[1], "error", error=out[3])
        r, usage, dt = out
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
        self.sessions = 0
        self.completes = 0
        self.systems: list[str] = []

    def session(self, system: str, first_user: str):
        self.sessions += 1
        self.systems.append(system)
        return _FakeSession(list(self.script))

    def complete(self, system: str, user: str):
        self.completes += 1
        return self.notebook_text, {"input": 10, "output": 5, "cache_read": 0, "cache_write": 0}


class _FakeSession:
    def __init__(self, script):
        self.script, self.n = script, 0

    def send(self, results=None, nudge=None) -> Turn:
        usage = {"input": 100, "output": 20, "cache_read": 0, "cache_write": 0}
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

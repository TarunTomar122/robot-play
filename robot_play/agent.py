"""The agent loop and the memory conditions.

An *episode* is one attempt at one task: the model calls tools until it says `done` or runs out of calls. A *run* is 12 practice episodes with
memory carried over, then evaluation episodes with the memory frozen. Memory conditions (PROTOCOL.md section 4):

  none      nothing is carried over.
  notebook  after each practice episode the same model rewrites a short notebook (at most 600 tokens) from the simulator's verdict and the transcript.
  replay    the transcript of the most recent successful practice episode on this task (at most 1,200 tokens).

Token caps are enforced as character caps at 4 characters per token (English text averages a little over that, so the caps are slightly generous).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field

from .llm import Turn, add_usage
from .spend import cost_usd
from .llm import MAX_OUTPUT_TOKENS
from .tools import SYSTEM_PROMPT, TOOLSETS, Episode

CHARS_PER_TOKEN = 4
NOTEBOOK_TOKENS, REPLAY_TOKENS = 600, 1200
PRACTICE_EPISODES, EVAL_EPISODES = 12, 4
PRACTICE_SEED_BASE, EVAL_SEED_BASE = 10_000, 20_000      # the validation gates use seeds below 10,000, so nothing here was ever tuned on
MAX_NUDGES = 2
NUDGE = "You did not call a tool. Keep using the tools to finish the task, or call done() if you believe it is finished."

CONDITIONS = ("none", "notebook", "replay")


def fingerprint(instruction: str) -> str:
    """Hash of everything a model is shown or limited by. Stored with every run so a resumed run cannot silently mix two versions of the setup."""
    blob = json.dumps({"system": SYSTEM_PROMPT, "tools": TOOLSETS, "instruction": instruction, "notebook_system": NOTEBOOK_SYSTEM, "nudge": NUDGE,
                       "caps": [NOTEBOOK_TOKENS, REPLAY_TOKENS, CHARS_PER_TOKEN, MAX_NUDGES, MAX_OUTPUT_TOKENS],
                       "notebook_request": notebook_request("I", "N", "V", 1, 2, "T")}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def practice_seeds(run_seed: int) -> list[int]:
    return [PRACTICE_SEED_BASE + 100 * run_seed + i for i in range(PRACTICE_EPISODES)]


def eval_seeds(run_seed: int) -> list[int]:
    """Shared by every model and every memory condition, so comparisons are paired on the same layouts."""
    return [EVAL_SEED_BASE + 100 * run_seed + i for i in range(EVAL_EPISODES)]


# ------------------------------------------------------------------------------------------------ rendering
def _short(x, n: int) -> str:
    s = json.dumps(x, separators=(",", ":"))
    return s if len(s) <= n else s[: n - 3] + "..."


def render_transcript(log: list[dict], max_chars: int, result_chars: int = 260) -> str:
    """A compact numbered list of the tool calls and what came back. If it is too long, the oldest `observe` results are cut first."""
    def build(res_chars: int, drop_observe: set[int]) -> str:
        lines = []
        for e in log:
            res = "(layout shown)" if e["i"] in drop_observe else _short(e["result"], res_chars)
            lines.append(f"{e['i']}. {e['tool']} {_short(e['args'], 120)} -> {res}")
        return "\n".join(lines)

    observes = [e["i"] for e in log if e["tool"] == "observe"]
    text = build(result_chars, set())
    dropped: set[int] = set()
    for i in observes:
        if len(text) <= max_chars:
            break
        dropped.add(i)
        text = build(result_chars, dropped)
    if len(text) > max_chars:
        text = build(max(60, result_chars // 2), dropped)
    return text[:max_chars]


@dataclass
class Memory:
    condition: str = "none"
    notebook: str = ""
    replay: str = ""

    def prompt_block(self) -> str:
        if self.condition == "notebook" and self.notebook:
            return ("\n\nYOUR NOTEBOOK, written by you after earlier attempts at this same task (object positions change between attempts, "
                    "and the notes may be incomplete or wrong):\n" + self.notebook)
        if self.condition in ("borrowed", "borrowed_1", "borrowed_3") and self.notebook:        # a frozen notebook written by a stronger model on the same task (exploratory cell, PROTOCOL.md section 10, v1.4)
            return ("\n\nA NOTEBOOK written by a more capable assistant after it practised this same task (object positions change between attempts, "
                    "and the notes may be incomplete or wrong):\n" + self.notebook)
        if self.condition in ("hint", "hint_generic") and self.notebook:                         # exploratory v1.7: one fixed sentence, no practice
            return ("\n\nA HINT from an experienced operator of this same task (object positions change between attempts):\n" + self.notebook)
        if self.condition in ("lm_inert", "lm_generic", "lm_specific", "lm_frame", "lm_names", "lm_instr", "lm_instr_n", "lm_names2") and self.notebook:        # exploratory v1.9 to v1.11: the same neutral label for different texts, no practice
            return "\n\nNOTES FOR THIS TASK (object positions change between attempts):\n" + self.notebook
        if self.condition == "prior" and self.notebook:                                         # exploratory v1.7: a notebook written by a stronger model that had NOT practised
            return ("\n\nA NOTEBOOK written by a more capable assistant that had read about this task but not yet attempted it (it may be incomplete or wrong; "
                    "object positions change between attempts):\n" + self.notebook)
        if self.condition == "borrowed_other" and self.notebook:  # the control for "borrowed": a stronger model's notebook for a DIFFERENT task, labelled as such
            return ("\n\nA NOTEBOOK written by a more capable assistant after it practised a DIFFERENT task in this same simulator (it may or may not apply to your task; "
                    "object positions change between attempts, and the notes may be incomplete or wrong):\n" + self.notebook)
        if self.condition == "replay" and self.replay:
            return ("\n\nA PREVIOUS ATTEMPT AT THIS SAME TASK THAT SUCCEEDED (object positions were different; tool calls and what came back):\n" + self.replay)
        return ""

    def tokens(self) -> int:
        return len(self.prompt_block()) // CHARS_PER_TOKEN


NOTEBOOK_SYSTEM = ("You keep a short notebook for an agent that controls a simulated robot arm through tools. After each attempt at the task you rewrite "
                   "the whole notebook so the next attempt goes better. You never invent facts: you only record what the tool results and the simulator's verdict showed.")


def notebook_request(instruction: str, notebook: str, verdict: str, calls: int, max_calls: int, transcript: str) -> str:
    return (f"TASK: {instruction}\n\nCURRENT NOTEBOOK:\n{notebook or '(empty)'}\n\n"
            f"The attempt that just ended used {calls} of {max_calls} tool calls. The simulator's verdict: {verdict}\n\n"
            f"WHAT THE AGENT DID (tool, arguments, what came back):\n{transcript}\n\n"
            "Object positions change at every attempt and the transcript is shortened, so do not record positions or coordinates. Rewrite the notebook now. "
            "Replace it, do not append. Keep it under 300 words. Say which settings or approaches worked or failed and what in the results showed that, "
            "and note anything that wasted calls. Output only the notebook text.")


PRIOR_SYSTEM = ("You write a short notebook for an agent that will control a simulated robot arm through tools. The agent has not attempted the task yet. "
                "You only know the task description and the tool descriptions you are given. You never invent facts about the simulator: if you do not know something, say what to check.")


def prior_request(instruction: str, tool_text: str, max_calls: int) -> str:
    """The zero-practice notebook of PROTOCOL.md v1.7: written from the task text and the tool descriptions only, no episode played."""
    return (f"TASK: {instruction}\n\nTOOLS (names, descriptions, parameters):\n{tool_text}\n\nThe agent gets {max_calls} tool calls per attempt. No attempt has been made yet, "
            "so there is no transcript and no verdict. Write the notebook the agent should have in front of it before its first attempt, using only the task and the tool descriptions. "
            "Do not record positions or coordinates. Keep it under 300 words. Output only the notebook text.")


# ------------------------------------------------------------------------------------------------ episodes
@dataclass
class EpisodeRecord:
    result: dict
    log: list
    usage: dict
    mem_usage: dict
    cost_usd: float
    turns: int
    nudges: int
    wall_s: float
    notes: list = field(default_factory=list)
    retry_usd: float = 0.0
    aborted: bool = False          # the provider failed or the reply was cut off: this is not a task outcome and must not be recorded as one
    refusal: bool = False          # the model's safety system declined: recorded as a failed episode, and counted

    def to_dict(self) -> dict:
        return {"result": self.result, "usage": self.usage, "mem_usage": self.mem_usage, "cost_usd": round(self.cost_usd, 6), "retry_usd": round(self.retry_usd, 6), "turns": self.turns, "refusal": self.refusal,
                "nudges": self.nudges, "wall_s": round(self.wall_s, 1), "notes": self.notes, "log": self.log}


def play_episode(provider, task: str, seed: int, quirk: bool, memory: Memory, disturbance: str | None = None, max_calls: int | None = None,
                 toolset: str = "skills") -> EpisodeRecord:
    ep = Episode(task, seed, quirk=quirk, max_calls=max_calls, disturbance=disturbance, toolset=toolset)
    system = ep.prompt + memory.prompt_block()
    paid0, retry0 = provider.tally.usd, provider.tally.retry_usd
    session = provider.session(system, "Begin the task now.", ep.tools)
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    notes: list[str] = []
    turns = nudges = 0
    aborted = refusal = False
    t0 = time.time()
    results = None
    nudge = None
    while not ep.finished:
        turn: Turn = session.send(results=results, nudge=nudge)
        results = nudge = None
        turns += 1
        usage = add_usage(usage, turn.usage)
        if turn.stop == "error":
            notes.append("provider error: " + turn.error)
            aborted = True
            break
        if turn.stop == "max_tokens":              # cut off, even if it carries a call: a half-written call is not an action the model chose
            notes.append("reply cut off at the output limit")
            aborted = True
            break
        if turn.stop == "refusal":
            notes.append("model declined (refusal)")
            refusal = True
            break
        if not turn.calls:
            if nudges >= MAX_NUDGES:
                notes.append("no tool call after nudges; episode ended")
                break
            nudges += 1
            nudge = NUDGE
            continue
        results = []
        for c in turn.calls:
            out = ep.call(c.name, c.args)
            results.append((c, json.dumps(out)))
            if ep.finished:
                break
        if ep.finished:
            break
        if turns > (ep.max_calls or 20) + 2 * MAX_NUDGES + 5:
            notes.append("turn cap reached")
            break
    result = ep.result()
    cost = provider.tally.usd - paid0                 # every paid attempt of this episode, failed retries included
    return EpisodeRecord(result, ep.log, usage, {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}, cost, turns, nudges, time.time() - t0, notes,
                         retry_usd=provider.tally.retry_usd - retry0, aborted=aborted, refusal=refusal)


def verdict_text(result: dict) -> str:
    return ("SUCCESS" if result["success"] else "FAILED") + f" ({result['detail']})"


def update_memory(provider, memory: Memory, rec: EpisodeRecord, task: str, instruction: str, max_calls: int) -> bool:
    """Called after each *practice* episode only. Evaluation episodes never change the memory.
    Returns False if the notebook rewrite failed or was cut off. The caller then stops and redoes the episode, so a run never carries on with a stale notebook
    that is silently one episode behind."""
    if memory.condition == "notebook":
        transcript = render_transcript(rec.log, 6000)
        paid0, retry0 = provider.tally.usd, provider.tally.retry_usd
        text, u = provider.complete(NOTEBOOK_SYSTEM, notebook_request(instruction, memory.notebook, verdict_text(rec.result), rec.result["calls"], max_calls, transcript))
        rec.mem_usage = add_usage(rec.mem_usage, u)
        rec.cost_usd += provider.tally.usd - paid0         # the notebook rewrite is part of the episode's cost, retries included
        rec.retry_usd += provider.tally.retry_usd - retry0
        if not text:
            rec.notes.append("notebook rewrite failed or was cut off at the output limit")
            return False
        memory.notebook = text[: NOTEBOOK_TOKENS * CHARS_PER_TOKEN]
    elif memory.condition == "replay" and rec.result["success"]:
        memory.replay = render_transcript(rec.log, REPLAY_TOKENS * CHARS_PER_TOKEN)
    return True

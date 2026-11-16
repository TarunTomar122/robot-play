"""Runs: 12 practice episodes with memory carried over, then evaluation episodes with memory frozen. Resumable, one JSONL file per run.

Every line of a run's file is one finished episode and also carries the memory as it stood afterwards, so a crashed run continues from its
last line instead of starting again.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
import traceback
from dataclasses import dataclass, asdict, field
from pathlib import Path

from .agent import (CONDITIONS, EVAL_EPISODES, Memory, eval_seeds, play_episode, practice_seeds, update_memory)
from .env import TASKS
from .llm import load_env_keys, make_provider
from .spend import BudgetExceeded, SpendMeter

TASK_LIST = ["stack", "bins", "flasks"]
DISTURBANCES = ["slip", "nudge"]


@dataclass
class RunSpec:
    model: str
    task: str
    condition: str
    run_seed: int
    quirk: bool = True
    practice: int = 12                       # number of practice episodes (0 for a pure first-try run)
    eval_seed_list: list | None = None       # explicit evaluation seeds (frontier first try); default is the shared four per run seed
    disturb_eval: bool = False               # after the clean evaluation episodes, repeat the same layouts with a disturbance
    max_calls: int | None = None
    out_dir: str = "runs/main"
    meter_root: str = "runs/spend"

    @property
    def key(self) -> str:
        return f"{self.model}__{self.task}__{self.condition}__{'quirk' if self.quirk else 'control'}__p{self.practice}__s{self.run_seed}"

    @property
    def path(self) -> Path:
        return Path(self.out_dir) / f"{self.key}.jsonl"

    def episodes(self) -> list[dict]:
        """The full ordered plan of episodes for this run."""
        plan = [{"phase": "practice", "idx": i, "seed": s, "disturbance": None} for i, s in enumerate(practice_seeds(self.run_seed)[: self.practice])]
        seeds = self.eval_seed_list if self.eval_seed_list is not None else eval_seeds(self.run_seed)
        plan += [{"phase": "eval", "idx": j, "seed": s, "disturbance": None} for j, s in enumerate(seeds)]
        if self.disturb_eval and self.quirk:
            plan += [{"phase": "eval_disturbed", "idx": j, "seed": s, "disturbance": DISTURBANCES[j % 2]} for j, s in enumerate(seeds)]
        return plan


def _read_done(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            break                                    # a half-written last line: drop it and redo that episode
    return rows


def run_one(spec: RunSpec, provider=None) -> dict:
    """Run (or resume) one run. Returns a small status dict; the episodes are in the JSONL file."""
    plan = spec.episodes()
    spec.path.parent.mkdir(parents=True, exist_ok=True)
    done = _read_done(spec.path)
    # rewrite the file with only the complete lines so a torn tail cannot confuse later readers
    spec.path.write_text("".join(json.dumps(r) + "\n" for r in done))
    memory = Memory(spec.condition)
    if done:
        memory.notebook, memory.replay = done[-1]["memory"]["notebook"], done[-1]["memory"]["replay"]
    if len(done) >= len(plan):
        return {"key": spec.key, "status": "already_done", "episodes": len(done)}
    task = TASKS[spec.task]
    if provider is None:
        load_env_keys()
        provider = make_provider(spec.model, SpendMeter(spec.meter_root), run_id=spec.key)
    try:
        for step in plan[len(done):]:
            mem_tokens = memory.tokens()
            rec = play_episode(provider, spec.task, step["seed"], spec.quirk, memory, step["disturbance"], spec.max_calls)
            if step["phase"] == "practice":                  # evaluation episodes never change the memory
                update_memory(provider, memory, rec, spec.task, task.instruction, spec.max_calls or task.max_calls)
            row = {"run": spec.key, "model": spec.model, "task": spec.task, "condition": spec.condition, "quirk": spec.quirk, "run_seed": spec.run_seed,
                   **step, "memory_tokens_in": mem_tokens, **rec.to_dict(),
                   "memory": {"notebook": memory.notebook, "replay": memory.replay}, "ts": round(time.time())}
            with open(spec.path, "a") as f:
                f.write(json.dumps(row) + "\n")
            if any(n.startswith("provider error") for n in rec.notes):
                return {"key": spec.key, "status": "provider_error", "episodes": len(_read_done(spec.path)), "note": rec.notes[-1]}
    except BudgetExceeded as e:
        return {"key": spec.key, "status": "budget", "note": str(e), "episodes": len(_read_done(spec.path))}
    return {"key": spec.key, "status": "ok", "episodes": len(plan)}


def _worker(spec: RunSpec) -> dict:
    try:
        return run_one(spec)
    except Exception as e:                                   # noqa: BLE001
        return {"key": spec.key, "status": "crashed", "note": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]}


def run_all(specs: list[RunSpec], workers: int = 8, log=print) -> list[dict]:
    """Run many runs in parallel processes. Stops handing out new runs once the budget has been hit."""
    out: list[dict] = []
    ctx = mp.get_context("spawn")
    stop = False
    with ctx.Pool(workers, maxtasksperchild=4) as pool:
        for res in pool.imap_unordered(_worker, specs):
            out.append(res)
            log(f"[{len(out)}/{len(specs)}] {res['key']}: {res['status']} {res.get('note', '')}".strip())
            if res["status"] == "budget" and not stop:
                stop = True
                log("budget cap reached: terminating the pool")
                pool.terminate()
                break
    return out


# ----------------------------------------------------------------------------------------------- the matrix (PROTOCOL.md section 5)
def build_specs(cell: str, models: list[str], run_seeds: list[int], out_dir: str, meter_root: str = "runs/spend", tasks: list[str] | None = None,
                max_calls: int | None = None) -> list[RunSpec]:
    tasks = tasks or TASK_LIST
    specs: list[RunSpec] = []
    common = dict(out_dir=out_dir, meter_root=meter_root, max_calls=max_calls)
    if cell == "main":
        for m in models:
            for t in tasks:
                for c in CONDITIONS:
                    for s in run_seeds:
                        specs.append(RunSpec(m, t, c, s, True, disturb_eval=c in ("none", "notebook"), **common))
    elif cell == "control":
        for m in models:
            for t in tasks:
                for c in ("none", "notebook"):
                    for s in run_seeds:
                        specs.append(RunSpec(m, t, c, s, False, **common))
    elif cell == "frontier":
        first_ten = [x for r in range(5) for x in eval_seeds(r)][:10]
        for m in models:
            for t in tasks:
                specs.append(RunSpec(m, t, "none", 0, True, practice=0, eval_seed_list=first_ten, **common))
    elif cell == "pilot":                       # no memory, layouts 50000+ (used by nothing else): to choose the call budget before the main run
        for m in models:
            for t in tasks:
                specs.append(RunSpec(m, t, "none", 0, True, practice=0, eval_seed_list=[50_000 + s for s in run_seeds], **common))
    elif cell == "frontier_exp":
        for m in models:
            for t in tasks:
                specs.append(RunSpec(m, t, "notebook", 0, True, **common))
    else:
        raise ValueError(cell)
    return specs

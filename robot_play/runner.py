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

from .agent import (CONDITIONS, EVAL_EPISODES, Memory, eval_seeds, fingerprint, play_episode, practice_seeds, update_memory)
from .env import TASKS
from .llm import load_env_keys, make_provider
from .tools import CALL_BUDGET_FACTOR
from .spend import PROVIDER_OF, BudgetExceeded, SpendMeter

PROTOCOL_VERSION = "1.2"
TASK_LIST = ["stack", "bins", "flasks"]


class ConfigMismatch(Exception):
    """A run file exists but was written with a different setup (budget, seeds, prompts, tools, caps...). It is never silently continued."""
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
    toolset: str = "skills"                  # "pose" removes pick and place (skill-level versus pose-level comparison)
    disturb_eval: bool = False               # after the clean evaluation episodes, repeat the same layouts with a disturbance
    max_calls: int | None = None
    out_dir: str = "runs/main"
    meter_root: str = "runs/spend"

    @property
    def key(self) -> str:
        tag = "" if self.toolset == "skills" else f"__{self.toolset}"
        return f"{self.model}__{self.task}__{self.condition}__{'quirk' if self.quirk else 'control'}__p{self.practice}__s{self.run_seed}{tag}"

    @property
    def path(self) -> Path:
        return Path(self.out_dir) / f"{self.key}.jsonl"

    def config(self) -> dict:
        """Everything that defines this run, stored as the first line of its file and compared on resume."""
        return {"protocol": PROTOCOL_VERSION, "model": self.model, "task": self.task, "condition": self.condition, "run_seed": self.run_seed,
                "quirk": self.quirk, "practice": self.practice, "disturb_eval": self.disturb_eval,
                "toolset": self.toolset, "max_calls": self.max_calls or TASKS[self.task].max_calls * CALL_BUDGET_FACTOR[self.toolset], "plan": self.episodes(), "setup": fingerprint(TASKS[self.task].instruction)}

    def episodes(self) -> list[dict]:
        """The full ordered plan of episodes for this run."""
        plan = [{"phase": "practice", "idx": i, "seed": s, "disturbance": None} for i, s in enumerate(practice_seeds(self.run_seed)[: self.practice])]
        seeds = self.eval_seed_list if self.eval_seed_list is not None else eval_seeds(self.run_seed)
        plan += [{"phase": "eval", "idx": j, "seed": s, "disturbance": None} for j, s in enumerate(seeds)]
        if self.disturb_eval and self.quirk:
            plan += [{"phase": "eval_disturbed", "idx": j, "seed": s, "disturbance": DISTURBANCES[j % 2]} for j, s in enumerate(seeds)]
        return plan


def _read(path: Path) -> tuple[dict | None, list[dict]]:
    """(config, finished episodes). A half-written last line is dropped and that episode is redone."""
    cfg, rows = None, []
    if not path.exists():
        return cfg, rows
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            break
        if "_config" in r:
            cfg = r["_config"]
        else:
            rows.append(r)
    return cfg, rows


def run_one(spec: RunSpec, provider=None) -> dict:
    """Run (or resume) one run. Returns a small status dict; the episodes are in the JSONL file."""
    plan = spec.episodes()
    cfg = json.loads(json.dumps(spec.config()))
    spec.path.parent.mkdir(parents=True, exist_ok=True)
    old_cfg, done = _read(spec.path)
    if old_cfg is not None and old_cfg != cfg:
        diff = sorted(k for k in set(cfg) | set(old_cfg) if cfg.get(k) != old_cfg.get(k))
        raise ConfigMismatch(f"{spec.path.name} was written with a different setup (differs in: {', '.join(diff)}); move it away or use a new output folder")
    if old_cfg is None and done:
        raise ConfigMismatch(f"{spec.path.name} has episodes but no config header")
    # rewrite the file with the header and only the complete lines, so a torn tail cannot confuse later readers
    spec.path.write_text(json.dumps({"_config": cfg}) + "\n" + "".join(json.dumps(r) + "\n" for r in done))
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
            rec = play_episode(provider, spec.task, step["seed"], spec.quirk, memory, step["disturbance"], spec.max_calls, spec.toolset)
            if rec.aborted:                          # a provider failure or a cut-off reply is not a task outcome: record nothing, change no memory
                return {"key": spec.key, "status": "aborted", "episodes": len(_read(spec.path)[1]), "note": rec.notes[-1]}
            if step["phase"] == "practice":          # evaluation episodes never change the memory
                update_memory(provider, memory, rec, spec.task, task.instruction, spec.max_calls or task.max_calls * CALL_BUDGET_FACTOR[spec.toolset])
            row = {"run": spec.key, "model": spec.model, "task": spec.task, "condition": spec.condition, "quirk": spec.quirk, "run_seed": spec.run_seed,
                   **step, "toolset": spec.toolset, "max_calls": spec.max_calls or task.max_calls * CALL_BUDGET_FACTOR[spec.toolset], "memory_tokens_in": mem_tokens, **rec.to_dict(),
                   "memory": {"notebook": memory.notebook, "replay": memory.replay}, "ts": round(time.time())}
            with open(spec.path, "a") as f:
                f.write(json.dumps(row) + "\n")
    except BudgetExceeded as e:
        return {"key": spec.key, "status": "budget", "note": str(e), "episodes": len(_read(spec.path)[1])}
    return {"key": spec.key, "status": "ok", "episodes": len(plan)}


def _worker(spec: RunSpec) -> dict:
    try:
        if SpendMeter(spec.meter_root).exhausted(PROVIDER_OF(spec.model)):
            return {"key": spec.key, "status": "skipped_budget", "note": f"{PROVIDER_OF(spec.model)} cap reached"}
        return run_one(spec)
    except ConfigMismatch as e:
        return {"key": spec.key, "status": "config_mismatch", "note": str(e)}
    except Exception as e:                                   # noqa: BLE001
        return {"key": spec.key, "status": "crashed", "note": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]}


def run_all(specs: list[RunSpec], workers: int = 8, log=print) -> list[dict]:
    """Run many runs in parallel processes. A provider that reaches its cap has its remaining runs skipped; the other provider carries on."""
    out: list[dict] = []
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers, maxtasksperchild=4) as pool:
        for res in pool.imap_unordered(_worker, specs):
            out.append(res)
            log(f"[{len(out)}/{len(specs)}] {res['key']}: {res['status']} {res.get('note', '')}".strip())
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
        first_twenty = [x for r in range(5) for x in eval_seeds(r)]          # run seeds 0 to 4: 20 evaluation layouts
        for m in models:
            for t in tasks:
                specs.append(RunSpec(m, t, "none", 0, True, practice=0, eval_seed_list=first_twenty, **common))
    elif cell == "pilot":                       # no memory, layouts 50000+ (used by nothing else): to choose the call budget before the main run
        for m in models:
            for t in tasks:
                specs.append(RunSpec(m, t, "none", 0, True, practice=0, eval_seed_list=[50_000 + s for s in run_seeds], **common))
    elif cell == "pose":                        # skill-level versus pose-level tools: the same runs with pick and place removed
        for m in models:
            for t in tasks:
                for c in ("none", "notebook"):
                    for s in run_seeds:
                        specs.append(RunSpec(m, t, c, s, True, toolset="pose", **common))
    elif cell == "frontier_exp":
        for m in models:
            for t in tasks:
                specs.append(RunSpec(m, t, "notebook", 0, True, **common))
    else:
        raise ValueError(cell)
    return specs

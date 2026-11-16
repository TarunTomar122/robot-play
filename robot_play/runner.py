"""Runs: 12 practice episodes with memory carried over, then evaluation episodes with memory frozen. Resumable, one JSONL file per run.

Every line of a run's file is one finished episode and also carries the memory as it stood afterwards, so a crashed run continues from its
last line instead of starting again.
"""
from __future__ import annotations

import functools
import hashlib
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

PROTOCOL_VERSION = "1.3"
TASK_LIST = ["stack", "bins", "flasks"]
DISTURBANCES = ["slip", "nudge"]
ROOT = Path(__file__).resolve().parent.parent
ALLOW_CODE_CHANGE = "ROBOT_PLAY_ALLOW_CODE_CHANGE"      # set to 1 to continue a run after a deliberate code change (it is then logged in the file)


class ConfigMismatch(Exception):
    """A run file exists but was written with a different setup (budget, seeds, prompts, tools, caps, code...). It is never silently continued."""


@functools.lru_cache(maxsize=1)
def asset_hash() -> str:
    """Hash of the contents of the Panda model files the simulator actually loads (every XML and every mesh), not of the script that downloads them."""
    h = hashlib.sha256()
    d = ROOT / "third_party" / "mujoco_menagerie" / "franka_emika_panda"
    for f in sorted(x for x in d.rglob("*") if x.is_file() and x.suffix.lower() in (".xml", ".obj", ".stl", ".png")):
        h.update(str(f.relative_to(d)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def code_hash() -> str:
    """Hash of every source file of the package, the pinned dependency lock and the robot model files: the code and the world a run was written with."""
    h = hashlib.sha256()
    code = [f for f in sorted((ROOT / "robot_play").glob("*.py")) if f.name not in ("analysis.py", "render.py")]       # analysis and charts never change what a run does
    for f in code + [ROOT / "uv.lock"]:
        h.update(f.name.encode())
        h.update(f.read_bytes() if f.exists() else b"")
    h.update(asset_hash().encode())
    return h.hexdigest()[:16]


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
    borrowed_notebook: str = ""              # condition "borrowed": a frozen notebook written by a stronger model; never rewritten, no practice
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
                "toolset": self.toolset, "max_calls": self.max_calls or TASKS[self.task].max_calls * CALL_BUDGET_FACTOR[self.toolset], "plan": self.episodes(), "setup": fingerprint(TASKS[self.task].instruction),
                "code": code_hash(), **({"borrowed_notebook": self.borrowed_notebook} if self.borrowed_notebook else {})}

    def episodes(self) -> list[dict]:
        """The full ordered plan of episodes for this run."""
        plan = [{"phase": "practice", "idx": i, "seed": s, "disturbance": None} for i, s in enumerate(practice_seeds(self.run_seed)[: self.practice])]
        seeds = self.eval_seed_list if self.eval_seed_list is not None else eval_seeds(self.run_seed)
        plan += [{"phase": "eval", "idx": j, "seed": s, "disturbance": None} for j, s in enumerate(seeds)]
        if self.disturb_eval:
            # in the no-catch flask scene the nudge topples the plain cylinder and nothing can stand it up again (the retry script recovers 0 of 50,
            # results/disturbance_control.md), so that scene gets the slip on all four layouts
            kinds = ["slip"] * 2 if (self.task == "flasks" and not self.quirk) else DISTURBANCES
            plan += [{"phase": "eval_disturbed", "idx": j, "seed": s, "disturbance": kinds[j % 2]} for j, s in enumerate(seeds)]
        return plan


def _read(path: Path) -> tuple[dict | None, list[dict], list[dict]]:
    """(config, finished episodes, abandoned attempts). A half-written last line is dropped and that episode is redone."""
    cfg, rows, aborts = None, [], []
    if not path.exists():
        return cfg, rows, aborts
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            break
        if "_config" in r:
            cfg = r["_config"]
        elif "_aborted" in r:
            aborts.append(r["_aborted"])
        else:
            rows.append(r)
    return cfg, rows, aborts


def _log_abort(spec: RunSpec, step: dict, usd: float, reason: str) -> None:
    """An attempt that was paid for but produced no episode (provider failure, cut-off reply, failed notebook rewrite, budget stop, crash). Its cost stays
    in the file so no paid call is ever missing from the totals, and the episode is redone on resume."""
    with open(spec.path, "a") as f:
        f.write(json.dumps({"_aborted": {"phase": step["phase"], "idx": step["idx"], "seed": step["seed"], "usd": round(usd, 6), "reason": reason[:200], "ts": round(time.time())}}) + "\n")


def run_one(spec: RunSpec, provider=None) -> dict:
    """Run (or resume) one run. Returns a small status dict; the episodes are in the JSONL file."""
    plan = spec.episodes()
    cfg = json.loads(json.dumps(spec.config()))
    spec.path.parent.mkdir(parents=True, exist_ok=True)
    old_cfg, done, aborts = _read(spec.path)
    if old_cfg is not None:
        cmp_old = {k: v for k, v in old_cfg.items() if k != "code_history"}
        if cmp_old != cfg:
            diff = sorted(k for k in set(cfg) | set(cmp_old) if cfg.get(k) != cmp_old.get(k))
            if diff == ["code"] and os.environ.get(ALLOW_CODE_CHANGE) == "1":
                cfg["code_history"] = old_cfg.get("code_history", []) + [{"from": old_cfg.get("code"), "to": cfg["code"], "at_episode": len(done), "ts": round(time.time())}]
            else:
                raise ConfigMismatch(f"{spec.path.name} was written with a different setup (differs in: {', '.join(diff)}); move it away or use a new output folder")
        elif "code_history" in old_cfg:
            cfg["code_history"] = old_cfg["code_history"]
    if old_cfg is None and done:
        raise ConfigMismatch(f"{spec.path.name} has episodes but no config header")
    # rewrite the file with the header, the abandoned-attempt lines and only the complete lines, so a torn tail cannot confuse later readers
    spec.path.write_text(json.dumps({"_config": cfg}) + "\n" + "".join(json.dumps({"_aborted": a}) + "\n" for a in aborts) + "".join(json.dumps(r) + "\n" for r in done))
    memory = Memory(spec.condition)
    if spec.borrowed_notebook:
        memory.notebook = spec.borrowed_notebook
    if done:
        memory.notebook, memory.replay = done[-1]["memory"]["notebook"], done[-1]["memory"]["replay"]
    if len(done) >= len(plan):
        return {"key": spec.key, "status": "already_done", "episodes": len(done)}
    task = TASKS[spec.task]
    if provider is None:
        load_env_keys()
        provider = make_provider(spec.model, SpendMeter(spec.meter_root), run_id=spec.key)
    n_done = len(done)
    max_calls = spec.max_calls or task.max_calls * CALL_BUDGET_FACTOR[spec.toolset]
    try:
        for step in plan[n_done:]:
            mem_tokens = memory.tokens()
            paid0 = provider.tally.usd
            rec = None
            try:
                rec = play_episode(provider, spec.task, step["seed"], spec.quirk, memory, step["disturbance"], spec.max_calls, spec.toolset)
                ok = not rec.aborted                 # a provider failure or a cut-off reply is not a task outcome: record nothing, change no memory
                if ok and step["phase"] == "practice":          # evaluation episodes never change the memory
                    ok = update_memory(provider, memory, rec, spec.task, task.instruction, max_calls)       # False: the rewrite failed, so stop rather than go on with a stale notebook
            except BaseException as e:               # budget stop or crash: the calls already paid for are kept in the file
                _log_abort(spec, step, provider.tally.usd - paid0, f"{type(e).__name__}: {e}")
                raise
            if not ok:
                _log_abort(spec, step, provider.tally.usd - paid0, rec.notes[-1])
                return {"key": spec.key, "status": "aborted", "episodes": n_done, "note": rec.notes[-1]}
            row = {"run": spec.key, "model": spec.model, "task": spec.task, "condition": spec.condition, "quirk": spec.quirk, "run_seed": spec.run_seed,
                   **step, "toolset": spec.toolset, "max_calls": max_calls, "memory_tokens_in": mem_tokens, **rec.to_dict(),
                   "memory": {"notebook": memory.notebook, "replay": memory.replay}, "ts": round(time.time())}
            with open(spec.path, "a") as f:
                f.write(json.dumps(row) + "\n")
            n_done += 1
    except BudgetExceeded as e:
        return {"key": spec.key, "status": "budget", "note": str(e), "episodes": n_done}
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
    by_provider: dict[str, list[RunSpec]] = {}
    for sp in specs:
        by_provider.setdefault(PROVIDER_OF(sp.model), []).append(sp)
    queues = list(by_provider.values())          # alternate between providers so every worker is not rate-limited by the same one at once
    specs = [q[i] for i in range(max(map(len, queues), default=0)) for q in queues if i < len(q)]
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers, maxtasksperchild=4) as pool:
        for res in pool.imap_unordered(_worker, specs):
            out.append(res)
            log(f"[{len(out)}/{len(specs)}] {res['key']}: {res['status']} {res.get('note', '')}".strip())
    return out


# ----------------------------------------------------------------------------------------------- the matrix (PROTOCOL.md section 5)
def build_specs(cell: str, models: list[str], run_seeds: list[int], out_dir: str, meter_root: str = "runs/spend", tasks: list[str] | None = None,
                max_calls: int | None = None, source_dir: str = "runs/frontier_exp", source_model: str = "claude-fable-5-2") -> list[RunSpec]:
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
                        specs.append(RunSpec(m, t, c, s, False, disturb_eval=True, **common))
    elif cell == "frontier":
        first_twenty = [x for r in range(5) for x in eval_seeds(r)]          # run seeds 0 to 4: 20 evaluation layouts
        for m in models:
            for t in tasks:
                specs.append(RunSpec(m, t, "none", 0, True, practice=0, eval_seed_list=first_twenty, **common))
    elif cell == "pilot":                       # no memory, layouts 50000+ (used by nothing else): to choose the call budget before the main run
        for m in models:
            for t in tasks:
                specs.append(RunSpec(m, t, "none", 0, True, practice=0, eval_seed_list=[50_000 + s for s in run_seeds], **common))
    elif cell == "pilot_pose":                  # the same no-memory pilot with the pose toolset (a check that a model can really work through it)
        for m in models:
            for t in tasks:
                specs.append(RunSpec(m, t, "none", 0, True, practice=0, eval_seed_list=[50_000 + s for s in run_seeds], toolset="pose", **common))
    elif cell == "pose":                        # skill-level versus pose-level tools: the same runs with pick and place removed
        for m in models:
            for t in tasks:
                for c in ("none", "notebook"):
                    for s in run_seeds:
                        specs.append(RunSpec(m, t, c, s, True, toolset="pose", **common))
    elif cell == "frontier_exp":
        for m in models:
            for t in tasks:
                for s in run_seeds:
                    specs.append(RunSpec(m, t, "notebook", s, True, **common))
    elif cell == "borrowed":                    # exploratory (v1.4): a cheap model reads the finished notebook of the frontier model for the same task and run seed, with no practice of its own
        for m in models:
            for t in tasks:
                for s in run_seeds:
                    text = frontier_notebook(source_dir, source_model, t, s)
                    if text:
                        specs.append(RunSpec(m, t, "borrowed", s, True, practice=0, borrowed_notebook=text, **common))
    elif cell in ("borrowed_1", "borrowed_3"):  # exploratory (v1.5): the same, but the notebook as the frontier model had it after only 1 (or 3) practice episodes: how short can the expensive practice be?
        after = int(cell[-1])
        for m in models:
            for t in tasks:
                for s in run_seeds:
                    text = frontier_notebook(source_dir, source_model, t, s, after=after)
                    if text:
                        specs.append(RunSpec(m, t, cell, s, True, practice=0, borrowed_notebook=text, **common))
    elif cell == "borrowed_other":              # the control for "borrowed": the notebook of a DIFFERENT task (stack reads the sort notebook, sort the flask one, flasks the stack one)
        shift = {"stack": "bins", "bins": "flasks", "flasks": "stack"}
        for m in models:
            for t in tasks:
                for s in run_seeds:
                    text = frontier_notebook(source_dir, source_model, shift[t], s)
                    if text:
                        specs.append(RunSpec(m, t, "borrowed_other", s, True, practice=0, borrowed_notebook=text, **common))
    else:
        raise ValueError(cell)
    return specs


def frontier_notebook(source_dir: str, source_model: str, task: str, run_seed: int, after: int | None = None) -> str:
    """The notebook a finished frontier-with-notebook run ended with ("" if that run is missing or unfinished). With `after`, the notebook as it stood after that many practice
    episodes (the rows record the memory after each episode), still only for runs that finished, so every borrowed arm reads from the same set of runs."""
    spec = RunSpec(source_model, task, "notebook", run_seed, True, out_dir=source_dir)
    cfg, rows, _ = _read(spec.path)
    if not cfg or len(rows) < len(cfg["plan"]):
        return ""
    if after is not None:
        return (rows[after - 1].get("memory") or {}).get("notebook", "") if 1 <= after <= len(rows) and rows[after - 1].get("phase") == "practice" else ""
    return (rows[-1].get("memory") or {}).get("notebook", "")

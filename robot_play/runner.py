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
    elif cell in ("hint", "hint_generic"):      # exploratory (v1.7): no practice, the memory slot holds one fixed sentence
        for m in models:
            for t in tasks:
                for s in run_seeds:
                    specs.append(RunSpec(m, t, cell, s, True, practice=0, borrowed_notebook=HINTS[t] if cell == "hint" else GENERIC_HINT, **common))
    elif cell == "prior":                       # exploratory (v1.7): no practice, a notebook Fable wrote with zero practice (source_dir holds the generated files)
        for m in models:
            for t in tasks:
                for s in run_seeds:
                    text = prior_notebook(source_dir, t, s)
                    if text:
                        specs.append(RunSpec(m, t, "prior", s, True, practice=0, borrowed_notebook=text, **common))
    elif cell == "labelmatch":                  # exploratory (v1.9): no practice, the same neutral label over an inert sentence, the generic sentence and the naming sentence
        texts = {"lm_inert": lambda t: INERT_TEXT, "lm_generic": lambda t: GENERIC_HINT, "lm_specific": lambda t: HINTS[t]}
        for m in models:
            for t in tasks:
                for c, fn in texts.items():
                    for s in run_seeds:
                        specs.append(RunSpec(m, t, c, s, True, practice=0, borrowed_notebook=fn(t), **common))
    elif cell == "wordsplit":                   # exploratory (v1.10): the generic sentence taken apart under the same neutral label, no practice
        for m in models:
            for t in tasks:
                for c, text in SPLIT_TEXTS.items():
                    for s in run_seeds:
                        specs.append(RunSpec(m, t, c, s, True, practice=0, borrowed_notebook=text, **common))
    elif cell == "wordsplit2":                  # exploratory (v1.11): the split of v1.10 repeated on fresh layouts (run seeds 30 to 39) with two nested wordings added and a no-memory arm
        for m in models:
            for t in tasks:
                specs += [RunSpec(m, t, "none", s, True, practice=0, **common) for s in run_seeds]
                for c, text in SPLIT2_TEXTS.items():
                    specs += [RunSpec(m, t, c, s, True, practice=0, borrowed_notebook=text, **common) for s in run_seeds]
    elif cell in ("second_none", "second_split"):   # exploratory (v1.13): a second model (the cheap-model split repeated); stage 1 is the no-memory room check, stage 2 the four split arms
        arms = {"second_none": {"none": ""}, "second_split": {c: SPLIT2_TEXTS[c] for c in ("lm_frame", "lm_names", "lm_instr_n", "lm_generic")}}[cell]
        for m in models:
            for t in tasks:
                for c, text in arms.items():
                    specs += [RunSpec(m, t, c, s, True, practice=0, borrowed_notebook=text, **common) for s in run_seeds]
    elif cell == "budget":                      # exploratory (v1.14): run with a stated call budget (--max-calls 12): no memory, the reminder, and the model's own notebook after 1 and after 12 practice episodes
        for m in models:
            for t in tasks:
                for s in run_seeds:
                    specs.append(RunSpec(m, t, "none", s, True, practice=0, **common))
                    specs.append(RunSpec(m, t, "lm_names", s, True, practice=0, borrowed_notebook=SPLIT_TEXTS["lm_names"], **common))
                    specs += [RunSpec(m, t, "notebook", s, True, practice=k, **common) for k in (1, 12)]
    elif cell == "mixed":                       # exploratory (v1.15): the two-sided job: one of the two odd cubes needs a firm grip, the other breaks under one. Run seeds 40 to 49, one job.
        for m in models:
            for s in run_seeds:
                specs.append(RunSpec(m, "mixed", "none", s, True, practice=0, **common))
                for c in ("lm_names", "lm_firm", "lm_proc"):
                    specs.append(RunSpec(m, "mixed", c, s, True, practice=0, borrowed_notebook=MIXED_TEXTS[c], **common))
                specs.append(RunSpec(m, "mixed", "notebook", s, True, practice=12, **common))
                specs.append(RunSpec(m, "mixed", "none", s, False, practice=0, **common))                                     # the control scene: two ordinary cubes
                specs.append(RunSpec(m, "mixed", "lm_proc", s, False, practice=0, borrowed_notebook=MIXED_TEXTS["lm_proc"], **common))
    elif cell == "silent":                      # exploratory (v1.16): the two-sided job with SILENT damage: a firm grip cracks the fragile cube with no message, only the final verdict names it
        for m in models:
            for s in run_seeds:
                specs.append(RunSpec(m, "mixed_silent", "none", s, True, practice=0, **common))
                for c in ("lm_names", "lm_firm", "lm_proc"):
                    specs.append(RunSpec(m, "mixed_silent", c, s, True, practice=0, borrowed_notebook=SILENT_TEXTS[c], **common))
                specs.append(RunSpec(m, "mixed_silent", "notebook", s, True, practice=12, **common))
    elif cell == "dose":                        # exploratory (v1.12): the model's own notebook after 1, 3, 6 (and, on run seeds 30 to 39, 12) practice episodes, held-out layouts of the usual four per run seed
        for m in models:
            for t in tasks:
                for s in run_seeds:
                    for k in (1, 3, 6) + ((12,) if s >= 30 else ()):
                        specs.append(RunSpec(m, t, "notebook", s, True, practice=k, **common))
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


HINTS = {"stack": "Pick the green cube with grip_level firm.",                              # PROTOCOL.md v1.7: one sentence naming the fixing setting of each job
         "bins": "Release each cube from release_height 0.14 or more.",
         "flasks": "Grasp each flask near its top: grasp_height 0.9."}
GENERIC_HINT = ("Defaults do not suit every object or surface. When a pick or place fails or is refused, read the message and change the settings "
                "(grip_level, grasp_height, release_height, speed) one at a time instead of repeating the same call.")


INERT_TEXT = ("Every object in this scene can be handled with the tools you have, one after another. When a call fails or is refused, read the message and look at "
              "the scene again before you carry on, and call done only once the job really is finished.")          # v1.9: about as long as GENERIC_HINT, names no setting and gives no advice about settings


# v1.10: GENERIC_HINT = frame + instruction + names. Each text below keeps the frame sentence and adds one of the other two parts, or neither.
FRAME = "Defaults do not suit every object or surface."
SPLIT_TEXTS = {
    "lm_frame": FRAME + " When a pick or place fails or is refused, read the message before you carry on.",                                   # the frame only
    "lm_names": FRAME + " The adjustable settings are grip_level, grasp_height, release_height and speed.",                                  # the frame and the four names, no instruction
    "lm_instr": FRAME + " When a pick or place fails or is refused, read the message and change how you call it, one thing at a time, instead of repeating the same call.",   # the frame and the instruction, no names
}


# v1.11: every text of v1.9 and v1.10 once more (same wording), plus two nested wordings: generic minus the names (so it keeps the word "settings"), and generic minus the instruction
# (so it keeps "read the message" and the failure frame).
SPLIT2_TEXTS = {
    "lm_inert": INERT_TEXT,
    "lm_frame": SPLIT_TEXTS["lm_frame"],
    "lm_names": SPLIT_TEXTS["lm_names"],
    "lm_instr": SPLIT_TEXTS["lm_instr"],
    "lm_instr_n": FRAME + " When a pick or place fails or is refused, read the message and change the settings one at a time instead of repeating the same call.",
    "lm_names2": FRAME + " When a pick or place fails or is refused, read the message. The adjustable settings are grip_level, grasp_height, release_height and speed.",
    "lm_generic": GENERIC_HINT,
}


# v1.15: the two-sided job. lm_names is the naming sentence of v1.10; lm_firm is the fix of the one-sided stack job given as a rule for every pick (it breaks the fragile cube);
# lm_proc is the answer key: the try, read, switch procedure the scripted player uses (results/gate_mixed.md), in words.
MIXED_TEXTS = {
    "lm_names": SPLIT_TEXTS["lm_names"],
    "lm_firm": "Pick every cube with grip_level firm.",
    "lm_proc": ("Each cube needs its own grip. Pick every cube first with the default grip_level. If the pick fails (holding stays None and the cube does not rise), pick it again "
                "with grip_level firm. If a pick comes back with a squeeze-limit message, the grip was too hard for that cube: use the default grip_level for it. Which cube needs "
                "which changes from layout to layout, so read the result of every pick."),
}


# v1.16: the same three texts for the silent job. The answer key differs only where the world differs: there is no squeeze-limit message, so it says that a firm grip can crack a
# fragile cube with no message and that only the final verdict shows it.
SILENT_TEXTS = {
    "lm_names": SPLIT_TEXTS["lm_names"],
    "lm_firm": MIXED_TEXTS["lm_firm"],
    "lm_proc": ("Each cube needs its own grip. Pick every cube first with the default grip_level. Only if the pick fails (holding stays None and the cube does not rise), pick that "
                "cube again with grip_level firm, and go back to the default grip_level for the next cube: a firm grip can crack a fragile cube with no message, and only the final "
                "verdict shows it. Which cube needs which changes from layout to layout."),
}


def prior_notebook(source_dir: str, task: str, run_seed: int) -> str:
    """The zero-practice notebook Fable wrote for this job and run seed (scripts/make_prior_notebooks.py), "" if there is none."""
    f = Path(source_dir) / f"{task}__s{run_seed}.json"
    return json.loads(f.read_text()).get("text", "") if f.exists() else ""


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

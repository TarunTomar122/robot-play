"""Spend meter: a cross-process budget cap, checked BEFORE every paid call, on estimated worst-case cost plus settled cost at assumed list prices.

What it guarantees and what it does not (PROTOCOL.md section 6): it bounds the sum of (settled cost + worst-case reservations of calls in flight) at
the cap, and it halts a provider's runs early if the estimate was ever too low (overruns are summed and above OVERRUN_STOP_USD the provider counts as
exhausted). It is not an audit against the provider's invoice; the hard stops leave $10 (Anthropic) and $5 (OpenAI) of headroom for that.

How it works, in plain words:
  1. Before a call, `reserve()` works out the most the call could possibly cost (estimated input tokens plus the full `max_tokens` of output)
     and adds it to the money already spent and already reserved. If that would pass the cap, the call is refused and nothing is sent.
  2. After the call, `settle()` replaces the reservation with the real cost from the response's token counts (cache reads and writes included).
  3. If a call fails and we cannot be sure it was not billed (a timeout, a dropped connection), `settle_unknown()` charges the full reservation.
     Only a failure that happens before the provider processes anything (bad request, bad key) is `release()`d for free.
All of this happens under a file lock, so many worker processes share one budget. Every event is appended to a JSONL ledger that survives restarts.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

# US dollars per million tokens: (input, output). Cache reads cost 10% of input and cache writes 125% of input on Anthropic. For OpenAI,
# cached input is assumed to cost 50% of input, which over-estimates cost if it is really cheaper (safe for a budget cap).
# These come from third-party price lists and must be checked against measured usage (see `reconcile`).
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-fable-5-2": (8.00, 40.00),
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-astra": (10.00, 50.00),
}
CACHE_READ = {"anthropic": 0.10, "openai": 0.50}
CACHE_READ_MODEL = {"claude-fable-5-2": 0.025, "claude-sonnet-5-5": 0.05}      # Anthropic's published cache-read multiple differs by model (model docs, checked 2026-11-16)
CACHE_WRITE = {"anthropic": 1.25, "openai": 1.00}
# Anthropic prices (input, output, cache reads and writes) match Anthropic's own model documentation (checked 2026-11-16; Haiku 5.5 prompts here stay under its 100K-token cheap tier). OpenAI prices could not be checked against an official list from here, so the meter
# charges twice the assumed OpenAI price: the cap can only be reached early, never late. Reported dollars in the results use the plain list price.
PRICE_SAFETY = {"anthropic": 1.0, "openai": 2.0}
PROVIDER_OF = lambda model: "anthropic" if model.startswith("claude") else "openai"
DEFAULT_CAPS = {"anthropic": 90.0, "openai": 45.0}
OVERRUN_STOP_USD = 1.0         # if reservations were ever too low by this much in total, the provider is treated as exhausted


class BudgetExceeded(Exception):
    pass


def estimate_tokens(text: str) -> int:
    """Deliberately high (3 characters per token) so that the reservation over-estimates."""
    return int(len(text) / 3) + 50


def cost_usd(model: str, input_tokens: int = 0, output_tokens: int = 0, cache_read_tokens: int = 0, cache_write_tokens: int = 0, safety: bool = False) -> float:
    """Dollars at the assumed list price. With safety=True the meter's pessimistic version (see PRICE_SAFETY)."""
    pin, pout = PRICES[model]
    prov = PROVIDER_OF(model)
    k = PRICE_SAFETY[prov] if safety else 1.0
    return k * (input_tokens * pin + output_tokens * pout + cache_read_tokens * pin * CACHE_READ_MODEL.get(model, CACHE_READ[prov]) + cache_write_tokens * pin * CACHE_WRITE[prov]) / 1e6


def worst_case_usd(model: str, est_input_tokens: int, max_output_tokens: int) -> float:
    """The most one call can cost: every input token billed as a cache write (the dearest input rate) and every output token used."""
    return cost_usd(model, cache_write_tokens=est_input_tokens, output_tokens=max_output_tokens, safety=True)


@dataclass
class Reservation:
    id: str
    provider: str
    model: str
    amount: float


class SpendMeter:
    def __init__(self, root: str | Path = "runs/spend", caps: dict | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.caps = dict(caps or DEFAULT_CAPS)
        self.ledger = self.root / "ledger.jsonl"
        self.state_file = self.root / "state.json"
        self.lock_file = self.root / "lock"
        self.lock_file.touch(exist_ok=True)

    # ------------------------------------------------------------------ internals
    @contextmanager
    def _locked(self):
        with open(self.lock_file, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _load(self) -> dict:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {"spent": {}, "reserved": {}, "open": {}}

    def _save(self, st: dict):
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(st))
        os.replace(tmp, self.state_file)

    def _log(self, **row):
        row["ts"] = round(time.time(), 3)
        with open(self.ledger, "a") as f:
            f.write(json.dumps(row) + "\n")

    # ------------------------------------------------------------------ public
    def totals(self) -> dict:
        with self._locked():
            st = self._load()
        return {p: {"spent": round(st["spent"].get(p, 0.0), 6), "reserved": round(st["reserved"].get(p, 0.0), 6), "cap": self.caps[p],
                    "overrun_usd": round(st.get("overrun", {}).get(p, 0.0), 6), "overrun_calls": st.get("overrun_calls", {}).get(p, 0)} for p in self.caps}

    def exhausted(self, provider: str, frac: float = 0.98) -> bool:
        """True once spent plus reserved is within 2% of the provider's cap: the runner then skips that provider's remaining runs."""
        with self._locked():
            st = self._load()
        if st.get("overrun", {}).get(provider, 0.0) >= OVERRUN_STOP_USD:
            return True
        return st["spent"].get(provider, 0.0) + st["reserved"].get(provider, 0.0) >= frac * self.caps[provider]

    def reserve(self, model: str, est_input_tokens: int, max_output_tokens: int, run_id: str = "") -> Reservation:
        prov = PROVIDER_OF(model)
        worst = worst_case_usd(model, est_input_tokens, max_output_tokens)
        with self._locked():
            st = self._load()
            committed = st["spent"].get(prov, 0.0) + st["reserved"].get(prov, 0.0)
            if st.get("overrun", {}).get(prov, 0.0) >= OVERRUN_STOP_USD:
                self._log(kind="refused", provider=prov, model=model, run_id=run_id, why="overruns passed the stop level", committed=round(committed, 6))
                raise BudgetExceeded(f"{prov}: reservations were too low by ${st['overrun'][prov]:.2f} in total; stopping this provider")
            if committed + worst > self.caps[prov]:
                self._log(kind="refused", provider=prov, model=model, run_id=run_id, worst_case=round(worst, 6), committed=round(committed, 6), cap=self.caps[prov])
                raise BudgetExceeded(f"{prov}: committed ${committed:.4f} + worst case ${worst:.4f} would pass the ${self.caps[prov]:.2f} cap")
            rid = uuid.uuid4().hex[:12]
            st["reserved"][prov] = st["reserved"].get(prov, 0.0) + worst
            st["open"][rid] = [prov, worst]
            self._save(st)
            self._log(kind="reserve", id=rid, provider=prov, model=model, run_id=run_id, amount=round(worst, 6))
        return Reservation(rid, prov, model, worst)

    def _close(self, res: Reservation, real: float, kind: str, **extra):
        with self._locked():
            st = self._load()
            if res.id not in st["open"]:
                raise KeyError(f"reservation {res.id} is not open")
            prov, amount = st["open"].pop(res.id)
            st["reserved"][prov] = max(0.0, st["reserved"].get(prov, 0.0) - amount)
            st["spent"][prov] = st["spent"].get(prov, 0.0) + real
            if real > amount + 1e-12:
                st.setdefault("overrun", {})
                st["overrun"][prov] = st["overrun"].get(prov, 0.0) + (real - amount)
                st.setdefault("overrun_calls", {})
                st["overrun_calls"][prov] = st["overrun_calls"].get(prov, 0) + 1
            self._save(st)
            self._log(kind=kind, id=res.id, provider=prov, model=res.model, amount=round(real, 6), **extra)

    def settle(self, res: Reservation, input_tokens: int, output_tokens: int, cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float:
        """Charge the real (pessimistic-priced) cost. If it is more than was reserved the estimate was too low: that is recorded as an overrun
        in the ledger and in `totals()`, so a too-low estimate is visible instead of silent."""
        real = cost_usd(res.model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, safety=True)
        over = max(0.0, real - res.amount)
        self._close(res, real, "settle", input_tokens=input_tokens, output_tokens=output_tokens,
                    cache_read_tokens=cache_read_tokens, cache_write_tokens=cache_write_tokens, reserved=round(res.amount, 6), overrun=round(over, 6))
        return real

    def settle_unknown(self, res: Reservation, why: str = "") -> float:
        """The call may have been billed but we have no usage numbers: charge the whole reservation."""
        self._close(res, res.amount, "settle_unknown", why=why[:120])
        return res.amount

    def release(self, res: Reservation, why: str = ""):
        """Only for failures that happen before the provider processes anything."""
        self._close(res, 0.0, "release", why=why[:120])

    def reconcile(self) -> dict:
        """Recompute totals from the ledger alone and compare with the running state."""
        per_model, spent, open_res = {}, {}, {}
        if self.ledger.exists():
            for line in self.ledger.read_text().splitlines():
                r = json.loads(line)
                if r["kind"] == "reserve":
                    open_res[r["id"]] = (r["provider"], r["amount"])
                elif r["kind"] in ("settle", "settle_unknown", "release"):
                    open_res.pop(r["id"], None)
                    spent[r["provider"]] = spent.get(r["provider"], 0.0) + r["amount"]
                    m = per_model.setdefault(r["model"], {"calls": 0, "usd": 0.0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0})
                    m["calls"] += 1
                    m["usd"] += r["amount"]
                    m["input"] += r.get("input_tokens", 0)
                    m["output"] += r.get("output_tokens", 0)
                    m["cache_read"] += r.get("cache_read_tokens", 0)
                    m["cache_write"] += r.get("cache_write_tokens", 0)
        st = self._load()
        n_rows = sum(1 for _ in self.ledger.read_text().splitlines()) if self.ledger.exists() else 0
        tol = 5e-7 * n_rows + 1e-9          # every ledger amount is rounded to 6 decimals, so each row can be off by 5e-7
        match = all(abs(spent.get(p, 0.0) - st["spent"].get(p, 0.0)) <= tol for p in set(spent) | set(st["spent"]))
        return {"per_model": per_model, "spent": spent, "open_reservations": len(open_res), "matches_state": match}

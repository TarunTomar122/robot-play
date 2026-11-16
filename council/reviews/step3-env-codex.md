ks using slip on all four layouts after nudge recovery failed **0/50**. Notebook rewrite failures abort, abandoned attempts are logged, `frontier_exp` uses five seeds, per-model cache-read multipliers and the $1 overrun halt are present. The spend cap remains estimate-based, not a guaranteed invoice ceiling. The Q3 cost and asset-binding qualifications above remain open.

I checked all 12 underlying final pilot files: their recorded code hash matches the current source hash, their episode counts and successes match the table, and they contain no aborts. This does not independently prove the external billing or model service identity. Read-only checks passed **44 environment tests** and **11 analysis tests**; the full suite could not start with normal capture because this sandbox has no writable temporary directory, so temporary-file-dependent runner and spend tests were not independently rerun. No paid calls or `.env` reads were made. HEAD is `f74a5cf`; `council/brief-step3.txt` is untracked.

```json
{"novelty": 6.0, "rigour": 5.5, "engineering": 5.5, "validity": 5.5, "clarity": 6.5,
 "fixes": ["Before launch, detect OpenAI refusal content and abort incomplete or truncated responses even when they contain tool calls; add provider-shaped regression tests.",
 "Before launch, bind run and resume fingerprints to the actual Panda XML and meshes, or verify and record the pinned revision and clean asset tree.",
 "Before launch, preregister a cluster-aware Q3 boundary interval and validate its behavior at ceiling, failure, and correlated-layout cases.",
 "Before launch, propagate run and subprocess failures through the night script and distinguish incomplete or aborted cells from a completed matrix.",
 "During the run, correct Q3 cost attribution so pose aborts cannot enter skills costs and frontier abandoned attempts are included.",
 "During the run, report missing planned cells and the limitations of complete-run selection; assess Q1 and Q4 interval boundary behavior and clean-success imbalance.",
 "Correct the protocol's cost-matched claim and update its pilot counts to distinguish the earlier pilot from the final-code pilot."
]}
```
tokens used
81,042
**Do not launch yet.** The round-2 environment changes are substantial and the final-code pilot is real, but the frozen runner still has provider-response and asset-fingerprinting gaps. The preregistered Q3 interval also treats completely correlated layouts as independent at the boundary.

**Novelty — 6.0/10.** [PROTOCOL.md:124](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:124) distinguishes the combined axes from related work. The skill/pose comparison also changes the call budget by 3×, so it cannot isolate abstraction alone. The final pilot has substantial ceilings and only six pose trials per cell.

**Rigour — 5.5/10.** Q3 now resamples notebook clusters, but its boundary correction assumes independent layouts when the observed variance is zero ([analysis.py:170](/Users/tarat/Documents/personal/robot-play/robot_play/analysis.py:170)). The control-scene Q4 design is an improvement, not a cure for floor effects if the model conditions differ on clean success. Complete-run selection can still be informative when failures or caps differ by condition.

**Engineering — 5.5/10.** Resume checks code and plans, but [runner.py:34](/Users/tarat/Documents/personal/robot-play/robot_play/runner.py:34) hashes the *download script*, not the robot XML and meshes actually loaded. [llm.py:255](/Users/tarat/Documents/personal/robot-play/robot_play/llm.py:255) does not identify OpenAI refusal output, and incomplete responses with tool calls can proceed. The night script does not propagate cell failures ([run_night.sh:17](/Users/tarat/Documents/personal/robot-play/scripts/run_night.sh:17)).

**Validity — 5.5/10.** The pose and control disturbance gates support the revised plan, with the documented flask-nudge exception. Q3 cost accounting can attribute pose aborts to skills and omit frontier aborts ([analyze.py:103](/Users/tarat/Documents/personal/robot-play/scripts/analyze.py:103), [analysis.py:182](/Users/tarat/Documents/personal/robot-play/robot_play/analysis.py:182)). The reported interval can produce an unjustified “matches” verdict at ceiling.

**Clarity — 6.5/10.** The protocol records the main design and history well, but [PROTOCOL.md:141](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:141) still calls Q3 cost-matched, contrary to section 1 and the report. Its section 1 pilot counts are from the earlier pilot, not the final-code results.

Before launch:

1. **Fix provider termination handling in `robot_play/`.** Parse OpenAI refusal content and abort every incomplete/truncated response, including one containing a tool call; apply the same truncation rule to Anthropic. Add provider-shaped tests covering both cases. Currently [agent.py:153](/Users/tarat/Documents/personal/robot-play/robot_play/agent.py:153) aborts truncation only when there are no calls, while OpenAI maps a response with calls to `tool_use` first.
2. **Bind runs to the actual robot assets.** Hash the loaded Panda XML and referenced meshes, or verify and record the pinned Menagerie commit *and a clean asset tree* at run start and resume. The checked-out Menagerie HEAD is the expected revision, but its contents are not covered by `code_hash()`.
3. **Revise and preregister Q3’s boundary interval before seeing matrix results.** In a synthetic 60/60 versus 60/60 case across 15 clusters, the code sets design effect to 1 and returns an upper bound of **5.65 percentage points**, declaring “within margin.” The data do not establish independence among the four layouts sharing a notebook; use a defensible cluster-aware boundary method and test its coverage or conservativeness.
4. **Make the launch script report failure honestly.** Propagate background and foreground exit statuses, distinguish aborted/incomplete cells from completion, and do not write `NIGHT_DONE` as an unconditional success marker. Have the runner exit nonzero when requested runs fail, while retaining the intended per-provider budget behavior.

These can follow **during the run, before reporting**, because they only require analysis or documentation changes: correct Q3’s frontier/pose abort attribution; report incomplete and never-started planned cells and selection limitations; assess Q1/Q4 boundary coverage and clean-success imbalance; and correct the protocol’s cost-matched and pilot claims. The final-code pilot gives Haiku skills **1/8, 8/8, 8/8** and Luna **7/8, 8/8, 7/8** for stack, bins and flasks respectively, rather than the older counts in section 1.

Round-2 checks: pose attachment and the 1-second pick dwell are implemented; the published pose gate passes. Control disturbances are scheduled and gated, with control flasks using slip on all four layouts after nudge recovery failed **0/50**. Notebook rewrite failures abort, abandoned attempts are logged, `frontier_exp` uses five seeds, per-model cache-read multipliers and the $1 overrun halt are present. The spend cap remains estimate-based, not a guaranteed invoice ceiling. The Q3 cost and asset-binding qualifications above remain open.

I checked all 12 underlying final pilot files: their recorded code hash matches the current source hash, their episode counts and successes match the table, and they contain no aborts. This does not independently prove the external billing or model service identity. Read-only checks passed **44 environment tests** and **11 analysis tests**; the full suite could not start with normal capture because this sandbox has no writable temporary directory, so temporary-file-dependent runner and spend tests were not independently rerun. No paid calls or `.env` reads were made. HEAD is `f74a5cf`; `council/brief-step3.txt` is untracked.

```json
{"novelty": 6.0, "rigour": 5.5, "engineering": 5.5, "validity": 5.5, "clarity": 6.5,
 "fixes": ["Before launch, detect OpenAI refusal content and abort incomplete or truncated responses even when they contain tool calls; add provider-shaped regression tests.",
 "Before launch, bind run and resume fingerprints to the actual Panda XML and meshes, or verify and record the pinned revision and clean asset tree.",
 "Before launch, preregister a cluster-aware Q3 boundary interval and validate its behavior at ceiling, failure, and correlated-layout cases.",
 "Before launch, propagate run and subprocess failures through the night script and distinguish incomplete or aborted cells from a completed matrix.",
 "During the run, correct Q3 cost attribution so pose aborts cannot enter skills costs and frontier abandoned attempts are included.",
 "During the run, report missing planned cells and the limitations of complete-run selection; assess Q1 and Q4 interval boundary behavior and clean-success imbalance.",
 "Correct the protocol's cost-matched claim and update its pilot counts to distinguish the earlier pilot from the final-code pilot."
]}
```

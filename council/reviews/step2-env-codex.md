nd Q3 reports no total practice/notebook cost. Partial runs can enter paired means on different layout subsets ([analysis.py:58](/Users/tarat/Documents/personal/robot-play/robot_play/analysis.py:58)); the requested bins pilot rerun and a dwell check for slipping objects remain unverified.

**Clarity — 6.0/10.** README, protocol history, pinned dependencies, Menagerie revision, visible-geometry caveat, and fresh disturbance results address the main documentation findings. However, [PROTOCOL.md:143](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:143) says all review defects are fixed and [PROTOCOL.md:90](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:90) calls an estimate a worst-case bound. [scripts/analyze.py:167](/Users/tarat/Documents/personal/robot-play/scripts/analyze.py:167) also crashes when a cheap model has no paired disturbed data, a plausible outcome when a cap interrupts the matrix.

Read-only verification: **50 tests passed, one deselected** across predicates, motion, tools, disturbance, leakage and analysis. The deselected test needs a writable temporary directory; the read-only sandbox prevented running temporary-file-dependent spend and runner tests. No paid APIs were called and no `.env` files were read.

```json
{"novelty": 6.0, "rigour": 4.5, "engineering": 4.5, "validity": 5.0, "clarity": 6.0,
 "fixes": ["Before launch, enforce a defensible per-request input and price upper bound, reserve it across concurrent calls, and reconcile against authoritative billing; otherwise explicitly remove the hard-cap claim and maintain sufficient independently enforced headroom.",
 "Repair Q3 inference to preserve shared-notebook run clusters and paired layouts, use an interval with defensible boundary behavior, and pre-register pooling, multiplicity and minimum complete sample sizes; test all-success and all-failure cases.",
 "Make notebook rewrite errors and truncated outputs explicit aborted run states; preserve and attribute the cost of every abandoned attempt and redo on resume without silently carrying stale memory.",
 "Validate complete planned layout pairs before analysis, report missing and aborted episodes by condition, prevent partial-run selection bias, and make the report handle absent Q4 cells without crashing.",
 "Fix frontier_exp to honor all five run seeds; dry-run and assert every protocol cell count, episode plan, seed overlap and output path before any paid launch.",
 "Report Q3's total cheap-model practice, notebook, retries and evaluation cost alongside frontier cost; add Q2 control difference-in-differences and distinguish descriptive cost from cost-matched claims.",
 "Recheck the slipping-object holding report, planner contact recovery across the original seed range, and the bins pilot under the corrected predicate; state the limits of the sampled one-second stability check and Q4's causal interpretation.",
 "Bind resume to a frozen code and asset revision as well as prompts and plans, verify provider prices and settings, and correct protocol claims that all round-one defects and hard-cap enforcement are already fixed."]
}
```
tokens used
86,934
**Do not launch the matrix yet.** The environment fixes are substantial, but the cap, Q3 inference, missing-run handling, cost accounting, and matrix generation can still corrupt the results.

**Novelty — 6.0/10.** The pose toolset is now implemented and included in the protocol ([tools.py:45](/Users/tarat/Documents/personal/robot-play/robot_play/tools.py:45), [PROTOCOL.md:81](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:81)). The contribution remains a combination of established ideas; only stack’s mass and friction are hidden, while bins and flasks expose geometry ([PROTOCOL.md:37](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:37)). A 3× call budget also changes the resource constraint alongside the abstraction.

**Rigour — 4.5/10.** Q3 bootstraps individual layouts even though four cheap-model evaluations share one notebook ([analysis.py:107](/Users/tarat/Documents/personal/robot-play/robot_play/analysis.py:107)); on a synthetic 60-layout all-success example it returns a zero-width interval and declares the 10-point margin met. Q4’s paired drop and firing-rate reporting improve the prior plan, but a difference of drops does not by itself isolate recovery from ceiling effects or differences in which disturbances fire. The Q2 report omits the control difference-in-differences, and the report does not account for the planned multiple comparisons ([scripts/analyze.py:130](/Users/tarat/Documents/personal/robot-play/scripts/analyze.py:130)).

**Engineering — 4.5/10.** The cap remains soft: first inputs and new tool results use `len(text)/3`, and 10% slack is an estimate, while settlement accepts overruns ([spend.py:46](/Users/tarat/Documents/personal/robot-play/robot_play/spend.py:46), [llm.py:160](/Users/tarat/Documents/personal/robot-play/robot_play/llm.py:160), [spend.py:136](/Users/tarat/Documents/personal/robot-play/robot_play/spend.py:136)). Doubling an unverified price cannot prove a cap. Resume now checks plans and prompts, but not simulator or implementation revisions; and `frontier_exp` ignores requested seeds, generating 48 episodes instead of the planned 240 ([runner.py:183](/Users/tarat/Documents/personal/robot-play/robot_play/runner.py:183)).

**Validity — 5.0/10.** Bins grading and sampled stability were corrected, contact escape has a regression test, and the fresh-layout gates use `Episode`; the published settings audit honestly exposes yaw’s alternate solution. Remaining gaps: failed notebook rewrites silently retain old memory ([llm.py:142](/Users/tarat/Documents/personal/robot-play/robot_play/llm.py:142), [agent.py:189](/Users/tarat/Documents/personal/robot-play/robot_play/agent.py:189)); aborted episodes’ paid attempts never enter episode rows, and Q3 reports no total practice/notebook cost. Partial runs can enter paired means on different layout subsets ([analysis.py:58](/Users/tarat/Documents/personal/robot-play/robot_play/analysis.py:58)); the requested bins pilot rerun and a dwell check for slipping objects remain unverified.

**Clarity — 6.0/10.** README, protocol history, pinned dependencies, Menagerie revision, visible-geometry caveat, and fresh disturbance results address the main documentation findings. However, [PROTOCOL.md:143](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:143) says all review defects are fixed and [PROTOCOL.md:90](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:90) calls an estimate a worst-case bound. [scripts/analyze.py:167](/Users/tarat/Documents/personal/robot-play/scripts/analyze.py:167) also crashes when a cheap model has no paired disturbed data, a plausible outcome when a cap interrupts the matrix.

Read-only verification: **50 tests passed, one deselected** across predicates, motion, tools, disturbance, leakage and analysis. The deselected test needs a writable temporary directory; the read-only sandbox prevented running temporary-file-dependent spend and runner tests. No paid APIs were called and no `.env` files were read.

```json
{"novelty": 6.0, "rigour": 4.5, "engineering": 4.5, "validity": 5.0, "clarity": 6.0,
 "fixes": ["Before launch, enforce a defensible per-request input and price upper bound, reserve it across concurrent calls, and reconcile against authoritative billing; otherwise explicitly remove the hard-cap claim and maintain sufficient independently enforced headroom.",
 "Repair Q3 inference to preserve shared-notebook run clusters and paired layouts, use an interval with defensible boundary behavior, and pre-register pooling, multiplicity and minimum complete sample sizes; test all-success and all-failure cases.",
 "Make notebook rewrite errors and truncated outputs explicit aborted run states; preserve and attribute the cost of every abandoned attempt and redo on resume without silently carrying stale memory.",
 "Validate complete planned layout pairs before analysis, report missing and aborted episodes by condition, prevent partial-run selection bias, and make the report handle absent Q4 cells without crashing.",
 "Fix frontier_exp to honor all five run seeds; dry-run and assert every protocol cell count, episode plan, seed overlap and output path before any paid launch.",
 "Report Q3's total cheap-model practice, notebook, retries and evaluation cost alongside frontier cost; add Q2 control difference-in-differences and distinguish descriptive cost from cost-matched claims.",
 "Recheck the slipping-object holding report, planner contact recovery across the original seed range, and the bins pilot under the corrected predicate; state the limits of the sampled one-second stability check and Q4's causal interpretation.",
 "Bind resume to a frozen code and asset revision as well as prompts and plans, verify provider prices and settings, and correct protocol claims that all round-one defects and hard-cap enforcement are already fixed."]
}
```

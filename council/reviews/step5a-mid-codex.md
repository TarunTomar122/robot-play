ask comparisons answer different questions.
- Reproduce and publish the coverage simulation, assumptions, code and Monte Carlo uncertainty; disclose the **94%** case prominently rather than treating nominal 97.5% coverage as verified. The floor assumes independent episodes despite shared notebooks; zero observed cluster variation does not prove independence. The floor is applied to exploratory success differences too, and can bind without complete collapse.
- Report each cell’s hashes, missing and incomplete files, partial Q3 clusters and complete-case selection. The documented exclusion of unplaceable flasks layout **20801** is defensible with frozen code and symmetric exclusion, but **29/30 is conditional on the remaining pairs actually completing**; it is not a current result. State that the target excludes this layout and show per-task denominators.
- Label the keyword audit exploratory and outcome-informed: regex matches can include negated or ineffective advice, and it checks neither full-plan completion nor semantic correctness. Selected videos deliberately show favorable contrasts; identify them as selected examples. Their replay checks the final success flag, not full trajectory identity. The stale-held script flags symptoms only; absence of its string does not prove the state was correct.

**Can wait:** fix the pose `holding` and stopped-short behaviors after the frozen run, and improve the sampler for future experiments. If pose results are reported now, include the known tool caveats, changed call budget and small sample; do not infer an abstraction-only effect.

```json
{"novelty": 6.0, "rigour": 5.5, "engineering": 5.5, "validity": 5.0, "clarity": 5.5,
 "fixes": ["Exclude incomplete borrowed and wrong-task runs and recompute Q5 on explicitly matched complete layouts with per-comparison counts.",
 "Correct Q5 notebook-production costs, avoid double-counting retries, and disclose discarded attempts and reuse assumptions.",
 "Publish reproducible interval-coverage simulations and disclose the 94% near-ceiling result and dependence assumptions.",
 "Report hashes by cell, all missing and incomplete planned runs, partial Q3 clusters, and complete-case selection limitations.",
 "Disclose the unplaceable layout and use 29 of 30 only if the remaining pairs actually finish.",
 "Qualify the wrong-task control, post-result replication, keyword audit, and selected replay videos in the report.",
 "Fix pose-state and sampler behavior after the frozen experiment; qualify any pose results in the current report."]
}
```
tokens used
74,858
**Do not publish the morning report from the current generator.** The new analysis rules are mostly implemented, but the Q5 cost and comparison displays are materially misleading, incomplete no-practice runs can enter analysis, and the claimed interval coverage is not established by the checked-in evidence.

**Novelty — 6.0.** [PROTOCOL.md](<repo>/PROTOCOL.md:127) credits close prior work and makes a defensible combination claim. The borrowed-notebook experiment adds an interesting transfer question, but the wrong-task control changes both content and its label; it does not isolate content alone. Pose-level evidence remains exploratory.

**Rigour — 5.5.** [analysis.py](<repo>/robot_play/analysis.py:92) implements the stratified t widening; lines 113–123 and 356–376 implement the Q1/Q4 noise floors. Q3 requires four matched layouts, prices those layouts, and uses notebook-only ICC. But the 94% near-ceiling simulation falls below nominal 97.5%; I found no reproducible simulation code establishing the stated 94–99.6% range. Timing of the post-launch changes is documented, not independently verified.

**Engineering — 5.5.** At this snapshot, `main_ext` has 60 complete files; matching borrowed has 58 complete files; wrong-task has 56 complete and two with one episode. The documented hashes match, episode keys have no duplicates or out-of-plan rows, and all 116 borrowed configurations match their intended source notebooks. However, [analysis.py](<repo>/robot_play/analysis.py:60) treats *all* no-practice files as frontier first tries, so the two incomplete wrong-task runs enter complete-only analyses. I did not run pytest; the sandbox could not create a temporary file.

**Validity — 5.0.** [analyze.py](<repo>/scripts/analyze.py:293) counts Fable evaluation as notebook production and adds `retry_usd` again, although it is already included in `cost_usd`; it also includes cheap evaluation in the “12 practice episodes” comparison. Its Q5 table and [chart](<repo>/scripts/make_q5_chart.py:45) do not enforce a common four-condition intersection. The chart says four layouts per bar and uses 5,000 rather than the protocol’s 10,000 resamples.

**Clarity — 5.5.** The generator lists hashes globally but does not attribute them to cells, silently suppresses missing-inventory errors, omits exploratory cells from its planned inventory, and omits the promised complete-run selection warning ([analyze.py](<repo>/scripts/analyze.py:135)). It reports partial Q3 clusters only when no whole cluster exists. The notebook audit discloses its changed threshold in source, but its generated report does not ([notebook_audit.py](<repo>/scripts/notebook_audit.py:63)).

**Before the final report:**

- Restrict complete-only loading to complete borrowed and wrong-task runs; retain per-layout loading only for actual frontier first-try files. Recompute Q5 comparisons on explicit matched, complete layouts and show sample counts for each comparison. Show seeds 0–4, the **post-result-decided** 5–9 replication, and pooled results.
- Correct Q5 costs to practice and rewrites only, counting retries once and abandoned/discarded attempts transparently. Report the roughly **$1.6 versus $0.016 per notebook** comparison as measured, including reuse assumptions and the number of uses needed to amortize it. Do not call it a cost-matched win.
- Describe the wrong-task comparison as suggestive: the model is explicitly told that the control notebook is for a different task and may not apply. A difference can reflect that instruction as well as notebook content. No-memory, own-notebook and wrong-task comparisons answer different questions.
- Reproduce and publish the coverage simulation, assumptions, code and Monte Carlo uncertainty; disclose the **94%** case prominently rather than treating nominal 97.5% coverage as verified. The floor assumes independent episodes despite shared notebooks; zero observed cluster variation does not prove independence. The floor is applied to exploratory success differences too, and can bind without complete collapse.
- Report each cell’s hashes, missing and incomplete files, partial Q3 clusters and complete-case selection. The documented exclusion of unplaceable flasks layout **20801** is defensible with frozen code and symmetric exclusion, but **29/30 is conditional on the remaining pairs actually completing**; it is not a current result. State that the target excludes this layout and show per-task denominators.
- Label the keyword audit exploratory and outcome-informed: regex matches can include negated or ineffective advice, and it checks neither full-plan completion nor semantic correctness. Selected videos deliberately show favorable contrasts; identify them as selected examples. Their replay checks the final success flag, not full trajectory identity. The stale-held script flags symptoms only; absence of its string does not prove the state was correct.

**Can wait:** fix the pose `holding` and stopped-short behaviors after the frozen run, and improve the sampler for future experiments. If pose results are reported now, include the known tool caveats, changed call budget and small sample; do not infer an abstraction-only effect.

```json
{"novelty": 6.0, "rigour": 5.5, "engineering": 5.5, "validity": 5.0, "clarity": 5.5,
 "fixes": ["Exclude incomplete borrowed and wrong-task runs and recompute Q5 on explicitly matched complete layouts with per-comparison counts.",
 "Correct Q5 notebook-production costs, avoid double-counting retries, and disclose discarded attempts and reuse assumptions.",
 "Publish reproducible interval-coverage simulations and disclose the 94% near-ceiling result and dependence assumptions.",
 "Report hashes by cell, all missing and incomplete planned runs, partial Q3 clusters, and complete-case selection limitations.",
 "Disclose the unplaceable layout and use 29 of 30 only if the remaining pairs actually finish.",
 "Qualify the wrong-task control, post-result replication, keyword audit, and selected replay videos in the report.",
 "Fix pose-state and sampler behavior after the frozen experiment; qualify any pose results in the current report."]
}
```

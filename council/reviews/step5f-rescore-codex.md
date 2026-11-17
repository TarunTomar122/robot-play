); the tasks still largely reward finding fixed settings.

**Rigour — 6.7/10.** Paired layouts, a corrected-simulator replication and registered missed predictions help. The split reuses known layouts and tests one wording per part, ten runs and one model; its most revealing comparison was post hoc ([PROTOCOL.md:227](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:227)).

**Engineering — 6.4/10.** The checker catches substantially more corruption, and all 1,274 local reported files pass. It can also report “all clean” after checking zero files, while the generator does not enforce all cross-folder validation ([check_run_files.py:31](/Users/tarat/Documents/personal/robot-play/scripts/check_run_files.py:31), [analyze.py:936](/Users/tarat/Documents/personal/robot-play/scripts/analyze.py:936)).

**Validity — 6.5/10.** The corrected-code replication supports a qualitative notebook gain; the original magnitude remains uncertain. The split supports a strong names-containing sentence on this task, but the README still presents its mechanism and several null comparisons too definitively ([README.md:64](/Users/tarat/Documents/personal/robot-play/README.md:64)).

**Clarity — 7.1/10.** The table, named simulator defects and explicit missed predictions make the work much easier to understand. Some table entries omit qualifications that appear far below, and the split descriptions do not faithfully convey the actual texts ([README.md:17](/Users/tarat/Documents/personal/robot-play/README.md:17), [PROTOCOL.md:223](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:223)).

### 5e fixes and remaining README issues

The requested fixes are mostly present: the original effect size is qualified and the pose defects are named; generic-minus-fresh sits alongside generic-minus-inert; Luna’s `bins` result and the Haiku `flasks` reversal are reported; registration timing is disclosed; and the grip audit includes the label-matched and split arms ([README.md:46](/Users/tarat/Documents/personal/robot-play/README.md:46), [README.md:65](/Users/tarat/Documents/personal/robot-play/README.md:65), [README.md:68](/Users/tarat/Documents/personal/robot-play/README.md:68), [README.md:199](/Users/tarat/Documents/personal/robot-play/README.md:199), [firm_grip_audit.md:13](/Users/tarat/Documents/personal/robot-play/results/firm_grip_audit.md:13)).

A stranger could still take away claims stronger than the evidence:

- **The table’s “list does the work” is too certain** ([line 17](/Users/tarat/Documents/personal/robot-play/README.md:17)). These are different complete sentences, not a clean deletion of words. The purported frame-only arm also says to read the message; the names arm instead says the settings are adjustable. State the observed 92% versus 70% and call the interpretation post hoc.
- **“The list works as a reminder” asserts an internal mechanism** ([line 64](/Users/tarat/Documents/personal/robot-play/README.md:64)). The settings were available in tool descriptions, but the experiment does not establish what the model attended to. Likewise, “what practice adds … is the specific value” and “practice finds one setting” ([line 68](/Users/tarat/Documents/personal/robot-play/README.md:68)) exceed the keyword and outcome evidence; the audit itself shows alternative routes.
- **“The label does not explain it” and “it cost Luna” overstate uncertain comparisons** ([line 65](/Users/tarat/Documents/personal/robot-play/README.md:65)). The observed label contrast was small, not proof of no label effect. The Luna difference’s interval includes zero; the extra observations are consistent with, but do not prove, the stated causal explanation.
- **“Did not name the fix” is a keyword-audit result**, not proof that zero-practice notebooks contained no useful solution; qualify the table and bullet accordingly ([lines 18 and 66](/Users/tarat/Documents/personal/robot-play/README.md:18)).
- **The pose table row needs its simulator caveat beside the result**, particularly because the defects directly affect pose tools ([line 21](/Users/tarat/Documents/personal/robot-play/README.md:21)). The detailed caveat exists later.
- **“Every planned cell has finished”** ([line 9](/Users/tarat/Documents/personal/robot-play/README.md:9)) is awkward alongside the incomplete flasks layout. Say the matrix finished with that prespecified-layout failure and exclusion.

### Generator and checker

Section 6g implements the stated W1/W2/W3 thresholds, reports **missed/missed/met**, reproduces the registered reading, and explicitly labels the incompatible interpretation and names-minus-instruction comparison as post hoc ([analyze.py:923](/Users/tarat/Documents/personal/robot-play/scripts/analyze.py:923), [RESULTS.md:793](/Users/tarat/Documents/personal/robot-play/results/RESULTS.md:793)). The 8-of-10 floor is implemented after completion, but each arm can score as soon as *its* ten pairs exist even if other arms are missing, despite the “pending until every pair exists” language. The registered comparison of **frame versus full generic** is also absent from the comparison loop ([PROTOCOL.md:227](/Users/tarat/Documents/personal/robot-play/PROTOCOL.md:227), [analyze.py:917](/Users/tarat/Documents/personal/robot-play/scripts/analyze.py:917)).

`bad_cov` no longer defaults a missing seed to 20, and the 6e/6g completed-data paths no longer require their marker files. However, 6g validates the split folder alone, even though it scores against `rep_fixed` and interprets `labelmatch`; headerless files are skipped by `coverage` ([analysis.py:39](/Users/tarat/Documents/personal/robot-play/robot_play/analysis.py:39)). Gate-failure voids remain unenforced, as the README discloses.

I ran the checker: **1,274 local files passed**, and all 30 split files passed with the expected hash. I also ran `--reported` from `/tmp`: it returned **“0 run files checked; all clean”** with success. Missing folders should fail, and expected identities and counts should be checked. The archive SHA-256 matches [data/README.md:14](/Users/tarat/Documents/personal/robot-play/data/README.md:14). I could not independently regenerate the report: this session’s filesystem is read-only, including `/tmp`. The claimed empty diff remains unverified by me.

### The proposed rule experiment

**Do it if the aim is a more interesting result, but expect a modest novelty gain, not a breakthrough.** A demonstrated rule that transfers across changing physical layouts would also improve rigour by testing the current constant-setting limitation. A positive result would still be a small simulation experiment, close to existing work on physical inference and memory.

The central danger is that a “rule” wins because the model reads wall height and infers the answer at evaluation time, or because one sufficiently high constant works everywhere. Before calls, gate layouts so the same constant cannot solve all cases, while a physically plausible rule succeeds across them; test collisions, reachability, drop failures and observation accuracy. Keep practice and held-out height ranges distinct, with some interpolation and genuinely unseen extrapolation; freeze notebooks before evaluation.

Preregister paired predictions and minimum effects for **own notebook versus no memory**, **rule hint versus constant hint**, and **rule hint versus a same-label, similar-length placebo**; include uncertainty intervals, a complete-pair floor, failure criteria, and the full spend cap. Use several constants or a tuned best constant, equal practice and call budgets, and a control that supplies the wall measurement without the rule. Audit notebook contents and actions, including whether it actually computes and applies the relation. A rule hint is an answer key, so it tests sufficiency; only the self-written notebook tests acquisition.

Under this budget, I would choose that experiment over another wording ablation **if the physical gates first show that constants fail across the distribution**. Otherwise, spend the budget on a preregistered fresh-layout replication of the names split with a second model and carefully matched wording: it would improve credibility more, though less novelty.

```json
{"novelty": 5.9, "rigour": 6.7, "engineering": 6.4, "validity": 6.5, "clarity": 7.1,
 "fixes": ["Qualify the README's split mechanism, label and inert-sentence claims; describe the actual arm texts and uncertainty.", "Make the checker fail on missing folders, zero files and missing or unexpected planned run identities.", "Enforce all-cell readiness, gate-failure voids and validation of every comparison folder before scoring.", "Add the registered frame-versus-generic comparison and test incomplete-cell and invalid-anchor cases.", "Run a preregistered variable-wall experiment only after physical gates show that no fixed release height can solve all layouts.", "Independently regenerate the report from the tracked archive in a writable clean checkout and verify the empty diff."]}
```

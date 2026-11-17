# Step 5c review (round 5c: interim README, v1.6 replication, three-simulator story) - judge: fable

Read-only review of `main` at `1ab6e8f` (then `cf5846c`) and tag `code-fixed` (`2267bf8`). No paid call, no `.env` read, nothing written to `runs/`, `logs/` or `media/`. Saved by the author from the judge's reply (the judge's text is reproduced in full below, lightly condensed in the lists).

## Verdict

**Do not publish this README as it stands.** Tone about the bug is honest, but it contained six statements that were false or backwards, and its claim 2 attributed 20 points to the bug that the data cannot attribute to anything. The v1.6 replication design is sound and its scorer matches the registration. One process problem: it was launched before the gates passed on the corrected code. All README numbers not listed below matched the judge's own recomputation from raw run files (Q1 table, three-simulator table, Q3 gaps and dollars, Q2 calls, Q5 numbers, 25 of 27, 20/60/60, disturbance drops).

## (A) README claims that were wrong, overstated or missing a caveat

Wrong at the time:

1. Status box: "All experiments have been run" and "Two cells were still finishing" were false (control about half done, pose 0 of 36 files, replication 6 of 120; three cells pending).
2. "A last-success replay works nearly as well for Luna and a little worse for Haiku" is backwards (Haiku: replay 10.4 calls vs notebook 9.9; Luna: replay 9.3 vs notebook 8.1).
3. "Gates run on the registered code and again on the corrected code": every gate file in results/ dates from 20:57 to 21:07; the rerun crashed at 23:50 and had not landed.
4. The pointer to section 6c: the committed RESULTS.md had no section 6c.
5. "Says done when it is not (1 to 2% of held-out episodes)": section 8 counts clean evaluation only. In the disturbed held-out episodes Luna with no memory falsely claims done in 22 of 116 (19%) against 3 of 116 with a notebook; over all held-out catch episodes Luna is 32 of 580 (5.5%) and Haiku 9 of 580 (1.6%).
6. The GIF under claim 1 shows the exploratory borrowed arm (Fable's notebook), not the model's own notebook that claim 1 and its table are about.

Overstated or missing a caveat: claim 2 heading "was inflated by a bug" asserted, not shown; claim 3 "about a tenth of the price" depends on the 12-to-4 practice/evaluation split, the OpenAI prices are unverified, and it is a ceiling result; claim 5 break-even "24 episodes" uses a cherry-picked comparator (against the cheap model's own notebook: 5,322 episodes for Haiku, never for Luna; and the $0.13 one-episode notebook is the right one to cost); "Haiku fell to 67%, below starting fresh" is -8.0 points (95% interval -19.8 to +3.7) and comes from flasks; claim 6 lacks intervals (Haiku -6.9, -19.4 to +5.6) and the disturbed stack rows on the corrected simulator (Haiku fresh 7 of 40 against 14 of 40 registered); the notebook can fail (run seed 5 on the corrected simulator: 0 of 12 in practice, wrote "pick fails. Do not use pick. Do not use place", failed all four held-out layouts); in the no-memory clip a default-grip `pick` did return `holding` and `place` returned ok, and the episode has neither bug symptom.

## (B) The v1.6 replication

Sound: registered 32 seconds before the first episode; right code (clean tree at `code-fixed`, all headers `8fdcf6b2491b68a3`); fresh layouts (12000+, 22000+) shared by both arms so pairing is correct; no contamination path into the registered rows; the shared spend meter is right.

Scorer against registration: all four predictions coded as written, against-the-claim conditions (85%, +5) match.

Weaknesses: (1) launched before the gates passed on this hash, against PROTOCOL section 7 (the replication is void if a gate fails; say so); (2) no rule for an incomplete cell ("pending until all 120" could stay pending forever; register a floor such as the Q1 rule of 24 of 30 pairs); (3) predictions 1 and 3 are barely falsifiable, prediction 2 is the only real test; (4) PROTOCOL v1.6 wrongly says `code-fixed` includes the `borrowed` prompt labels (its robot_play diff from matrix-launch is analysis.py, env.py, motion.py, skills.py only); (5) the "corrected simulator" of 6b (`aef351c5c3033d54`) and 6c (`8fdcf6b2491b68a3`) are two hashes and 6c should say so.

## (C) "About 20 points of the size does not survive"

Not supported as worded. The 20 points split in two halves: ten are the no-memory arm (the arm the bug acted on), which moved from 13 to 15 to 17 of 40, i.e. rerun noise (only 5 of the 13 registered successes repeated on identical layouts on the cause-fixed simulator, 8 flipped to failure, 12 to success; a second set of ten run seeds on the registered simulator gave 9 of 40); ten are the notebook arm, which the bug never touched (0 of 80 episodes), from one run that taught itself not to use `pick`. The generator's paired row gives registered minus cause-fixed +20.0 points, 95% interval -14.6 to +54.6. Suggested wording: "The bug touched 25 of 27 failures, but fixing it did not measurably change the no-memory arm (32% to 42%, inside rerun noise). On the corrected simulator the gain measured +47.5 points (+17.8 to +77.2) against +67.5 registered; the difference is +20 (-14.6 to +54.6), and half of it is one notebook run that learned a wrong rule. The direction holds; ten runs cannot fix the size." The heading should read "may have been inflated"; the +5 "extreme bound" of section 2a should be marked as contradicted by the rerun.

## (D) Best use of the remaining hours

The lowest score is novelty. The single highest-value experiment is a **hint control** on `code-fixed`, run seeds 20 to 29 so it pairs with `rep_fixed`, under $2: (1) a fixed one-sentence hint per job in the notebook slot with the notebook label; (2) a notebook Fable writes with zero practice from the tool descriptions only; both cheap models, three jobs, four held-out layouts, predictions registered first, gates passed first. If the hint matches the notebook, one sentence is enough and practice is how a model finds it; if not, the notebook carries more than the sentence. Cut from the README: the status sentence, the gates-on-corrected-code sentence until true, "a tenth of the price" from the bold line, the 24-episode break-even (or print both comparators), the replay sentence, and the folder map.

## Scores (as if published now)

Novelty 6.8 (unchanged; hint and zero-practice controls still not done, Q3 a ceiling result, pose and Q4 without data). Rigour 8.2 (missed prediction disclosed, replication registered with a mechanical scorer; held back by launch before gates, no incomplete-cell rule, two near-unfalsifiable predictions, README reading a noise-level shift as a bug effect). Engineering 7.8 (cause fix is three lines with two tests, sampler restart tested; fixes unmerged, gates not passed on the fixed hash, first gate rerun crashed on a missing model file, `move_to` still does not report a lost object). Validity 7.5 (up from 7.0: fixing the cause left the no-memory arm at 42%, so the catch, not the bug, does the work; one model, one job, ten runs, replication at 6 of 120 files). Clarity 7.6 (down from 8.0: a stranger is told six false things and the lead GIF illustrates a different arm).

```json
{"novelty": 6.8, "rigour": 8.2, "engineering": 7.8, "validity": 7.5, "clarity": 7.6,
 "fixes": [
  "README claim 2: replace 'was inflated by a bug' and 'about 20 points of the size does not survive'; the no-memory arm moved 13 -> 15 -> 17 of 40, inside rerun noise; the other 10 points are one notebook run (run seed 5, 0 of 12 in practice, notebook says 'Do not use pick'); quote the paired row +20.0 (-14.6 to +54.6); mark the +5 'extreme bound' as contradicted by the rerun.",
  "README statements false at the time: status box; gates on corrected code; pointer to section 6c; replay sentence backwards.",
  "Run the hint control (one-sentence hint per job; Fable notebook with zero practice) on code-fixed, run seeds 20-29, predictions registered first, gates passed first.",
  "Gates before paid runs on a new hash: finish the gate rerun, state that the replication is void if any gate fails, register a floor for an incomplete replication, correct the v1.6 text about the borrowed prompt labels.",
  "False 'done' claims: add the disturbed held-out episodes (Luna no memory 22 of 116 = 19% vs 3 of 116 with a notebook; all held-out: Luna 32 of 580, Haiku 9 of 580).",
  "README claim 1 media: the GIF's right half is the borrowed arm; use an own-notebook episode or move it to claim 5; caption the no-memory half accurately.",
  "README claims 3, 5 and 6 caveats: lead claim 3 with the ceiling, put unverified OpenAI prices next to the dollars, print both break-even comparators and cost the $0.13 notebook, give the intervals for wrong-job vs fresh and for Haiku's disturbance drop difference.",
  "Add to 'What this does not show' and to section 6b: a self-written notebook can lock in a wrong rule, the disturbed evaluation on the three simulators (Haiku stack no memory 14, 14 and 7 of 40; notebook 40, 36 and 36 of 40), and say in 6c that the corrected simulators of 6b and 6c are two code hashes."
 ]}
```

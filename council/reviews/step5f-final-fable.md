# Step 5f review (round 5f: re-score after the split, the README rebuild and the stricter checker) - judge: fable

Saved by the author from the judge's reply (condensed; scores and fix list as given). Read-only review. The judge confirmed against the raw files: the split was registered first (commit df1552a reached origin at 03:07:10, first run file 03:07:29, first episode 03:07:39); 30 split files all with hash `0346eddace878d63`; the three memory texts match PROTOCOL v1.10; success counts (frame 20/40, names 37/40, instruction 28/40, generic 37/40, inert 16/40, none 20/40), every paired interval, the firm-grip counts and the Luna `bins` observe calls (82 against 50); the archive SHA-256 and an empty regeneration diff; the checker's 1,274 clean files. Not verified by the judge: pytest (tests reference `runs/`, which the judge may not write).

## Problems named
1. README.md:9 said only the first three rows are registered (rows 1, 5 and 6 are).
2. README.md:115 said false "done" is 1 to 2% of clean skill-tool episodes (it is 0 to 6%; Luna fresh 7 of 116).
3. The H2 bullet and table row 3 described the generic sentence as one that "only lists the settings"; it also carries the instruction.
4. The instruction arm of the split ("change how you call it, one thing at a time") also lost the word "settings", and the names arm dropped "read the message"; the README never printed the arm texts.
5. "The list does the work" rested on one unregistered comparison (names minus instruction +22.5, +4.7 to +40.3; exact sign-flip p = 0.031 among ten comparisons with no correction).
6. The instruction arm set the firm grip as often as the frame arm (27 against 26) yet solved 28 against 20; unexplained and unmentioned.
7. A one-line naming sentence equals the stronger writer's notebook, so finding 4 shows only that a notebook can contain the answer.
8. Deviation 2 said every borrowed file carries one code hash; `runs/borrowed` has two.
9. Checker: `--reported` checked no hashes without `--expect`, silently skipped a missing folder, swallowed a mistyped folder as a hash, had no completeness or memory-text check and no tests.
10. Generator: the "no reading under 20 points" rule was printed but not enforced; the W3 check order is not in the protocol.
11. The rule-not-constant job as described has no room (fresh Haiku 90%, Luna 92% on `bins`), a constant such as "release from 25 cm" would still pass, and a lookup table passes if held-out heights lie inside the practice range.

## Advice on the next experiment
Replicate the split first (about $1, 15 minutes, no new code): fresh run seeds, a nested instruction arm that keeps "settings", a second wording per part, names minus instruction as the registered primary comparison. Run the rule job only behind registered gates (no single constant solves more than 40% of 100 layouts, the rule solves 100, defaults 0; a fresh-Haiku pilot at most 60%; held-out wall heights outside the practice range; a names-list arm; blind coding of the notebooks; at least 20 runs per arm; new tag and hash).

## Scores
```json
{"novelty": 7.2, "rigour": 8.6, "engineering": 8.7, "validity": 8.5, "clarity": 8.3,
 "fixes": [
  "Fix README.md:9 and README.md:115.",
  "Print the three split-arm texts and the wording differences; retitle the H2 bullet and table row 3.",
  "Replicate the split on fresh run seeds 30 to 39 with a nested instruction arm and a second wording; register names minus instruction as primary.",
  "Run the rule-not-constant job only behind registered gates (two-sided window, constants fail, pilot, extrapolation, names-list arm, blind notebook coding, 20 runs per arm).",
  "Checker: folder-to-hash map, missing folder fails, completeness check, tests.",
  "Mark the names-minus-instruction comparison as unregistered and uncorrected; report the unexplained instruction effect.",
  "Cross-reference the naming sentence in row 4 and finding 4; reconcile deviation 2 with the two borrowed hashes."
 ]}
```

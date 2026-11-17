# Zero-practice notebooks (v1.7 `prior` cell): did they name the fix?

Written by `claude-fable-5-2` with **no practice**, from the task text and the tool descriptions only (`scripts/make_prior_notebooks.py`, 30 files in `results/prior_notebooks/`, one per job and run seed 20 to 29), before any cheap model read them or any episode of the `prior` cell was played. Keyword check with the same rules as `results/notebook_audit.md` (stack: `grip_level` set to firm; sort: `release_height` of 0.14 or more; flasks: `grasp_height` of 0.8 or more), run at the time they were written, plus a looser count of notebooks that merely mention the word. A keyword check, not a judgement of quality.

| job | notebooks | name the fixing setting (strict rule) | mention `firm`, `release_height` or `grasp_height` at all (loose) |
|---|---|---|---|
| stack | 10 | 0 | 9 |
| bins | 10 | 0 | 10 |
| flasks | 10 | 0 | 10 |

Cost of writing all 30: $0.85 (Fable 5.2, list price). The notebooks list the settings as things to check (for example "retry with a different grasp_height or firm grip") and none commits to a value that fixes a job. PROTOCOL.md v1.7 predicted that at least 5 of 10 `stack` notebooks would name `grip_level firm`; by the strict rule that is 0 of 10, so that part of prediction H3 is missed whatever the cheap models then do.

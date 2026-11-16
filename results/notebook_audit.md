# Did the notebooks name the fix?

Exploratory and descriptive: a keyword check of each run's notebooks (the notebook after each of the 12 practice episodes), not a judgement of quality. Complete notebook runs only. 'Names the fix' means the notebook contains the setting that fixes the job: stack (firm grip); sort (release from 14 cm or higher); stand the flasks (grasp at 0.8 or higher).

| model | job | runs | final notebook names the fix | names it already after practice episode 1 | practice episodes until it first does (mean, of the runs that do) | held-out success, notebook names the fix | held-out success, it does not |
|---|---|---|---|---|---|---|---|
| claude-fable-5-2 | bins | 10 | 10/10 | 10/10 | 1.0 | 100% (10 runs) | n/a |
| claude-fable-5-2 | flasks | 9 | 9/9 | 9/9 | 1.0 | 100% (9 runs) | n/a |
| claude-fable-5-2 | stack | 10 | 10/10 | 10/10 | 1.0 | 100% (10 runs) | n/a |
| claude-haiku-5-5 | bins | 10 | 1/10 | 0/10 | 4.0 | 100% (1 runs) | 97% (9 runs) |
| claude-haiku-5-5 | flasks | 9 | 8/9 | 6/9 | 1.4 | 100% (8 runs) | 100% (1 runs) |
| claude-haiku-5-5 | stack | 10 | 8/10 | 7/10 | 1.1 | 100% (8 runs) | 100% (2 runs) |
| gpt-6-luna | bins | 10 | 3/10 | 1/10 | 3.7 | 100% (3 runs) | 100% (7 runs) |
| gpt-6-luna | flasks | 9 | 6/9 | 3/9 | 2.7 | 100% (6 runs) | 100% (3 runs) |
| gpt-6-luna | stack | 10 | 9/10 | 10/10 | 1.0 | 100% (9 runs) | 100% (1 runs) |

**How to read this.** It is exploratory and outcome-informed: the keyword rules are mine, written before the full data but with the pilots in view. The flasks threshold started as `grasp_height` 0.85, a guess from the pose gate (the catch bites below about 80% of the flask height); I changed it to **0.8** after reading Fable's finished notebooks, which use 0.8 and succeed, so that rule is fitted to the outcome it is checked against. The thresholds in force are: stack `grip_level` firm; sort `release_height` 0.14 or more; flasks `grasp_height` 0.8 or more. A regular expression also matches negated or ineffective advice ('do not use firm'), and it checks neither that the plan is complete nor that the advice is right. For sort the rule misses most working notebooks (Haiku succeeds on 99% of held-out sort episodes without writing a release height of 0.14), so that row measures wording more than learning.

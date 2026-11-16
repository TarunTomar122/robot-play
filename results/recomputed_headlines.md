# Headline numbers, recomputed from the raw run files

No use of `robot_play.analysis`. Complete runs: 180; incomplete runs left out: 6. Held-out episodes, catch scenes, skills toolset.

| model | memory | job | episodes | solved | success | calls to success |
|---|---|---|---|---|---|---|
| claude-fable-5-2 | none | bins | 20 | 20 | 100.0% | 11.20 |
| claude-fable-5-2 | none | flasks | 20 | 20 | 100.0% | 7.80 |
| claude-fable-5-2 | none | stack | 20 | 20 | 100.0% | 9.00 |
| claude-haiku-5-5 | none | bins | 40 | 40 | 100.0% | 19.00 |
| claude-haiku-5-5 | notebook | bins | 40 | 39 | 97.5% | 15.62 |
| claude-haiku-5-5 | replay | bins | 40 | 40 | 100.0% | 16.95 |
| claude-haiku-5-5 | none | flasks | 36 | 35 | 97.2% | 9.33 |
| claude-haiku-5-5 | notebook | flasks | 36 | 36 | 100.0% | 7.00 |
| claude-haiku-5-5 | replay | flasks | 36 | 35 | 97.2% | 6.72 |
| claude-haiku-5-5 | none | stack | 40 | 13 | 32.5% | 17.98 |
| claude-haiku-5-5 | notebook | stack | 40 | 40 | 100.0% | 6.88 |
| claude-haiku-5-5 | replay | stack | 40 | 40 | 100.0% | 7.25 |
| gpt-6-astra | none | bins | 20 | 20 | 100.0% | 12.00 |
| gpt-6-astra | none | flasks | 20 | 20 | 100.0% | 6.25 |
| gpt-6-astra | none | stack | 20 | 20 | 100.0% | 8.60 |
| gpt-6-luna | none | bins | 40 | 37 | 92.5% | 15.57 |
| gpt-6-luna | notebook | bins | 40 | 40 | 100.0% | 11.95 |
| gpt-6-luna | replay | bins | 40 | 39 | 97.5% | 14.55 |
| gpt-6-luna | none | flasks | 36 | 29 | 80.6% | 12.97 |
| gpt-6-luna | notebook | flasks | 36 | 36 | 100.0% | 6.00 |
| gpt-6-luna | replay | flasks | 36 | 36 | 100.0% | 7.22 |
| gpt-6-luna | none | stack | 40 | 40 | 100.0% | 7.78 |
| gpt-6-luna | notebook | stack | 40 | 40 | 100.0% | 6.00 |
| gpt-6-luna | replay | stack | 40 | 40 | 100.0% | 6.00 |

Pooled over jobs (episode-weighted; the analysis report weights each job by its number of complete runs, so the two can differ by a point where a job lost a run):

| model | memory | episodes | solved | success | calls to success |
|---|---|---|---|---|---|
| claude-fable-5-2 | none | 60 | 60 | 100.0% | 9.33 |
| claude-haiku-5-5 | none | 116 | 88 | 75.9% | 15.65 |
| claude-haiku-5-5 | notebook | 116 | 115 | 99.1% | 9.93 |
| claude-haiku-5-5 | replay | 116 | 115 | 99.1% | 10.43 |
| gpt-6-astra | none | 60 | 60 | 100.0% | 8.95 |
| gpt-6-luna | none | 116 | 106 | 91.4% | 12.08 |
| gpt-6-luna | notebook | 116 | 116 | 100.0% | 8.05 |
| gpt-6-luna | replay | 116 | 115 | 99.1% | 9.33 |

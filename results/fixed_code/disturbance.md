# Disturbance validation

30 episodes per row (layout seeds 3000+; the nudge was tuned on 2000-2029 and those results are kept in disturbance_tuning_seeds_2000.md), catch scenes, played through the same Episode wrapper and call budget a model gets. 'No reaction' = the script that knows the catch but never retries.

| Job | Disturbance | Fired | Success, no reaction | Success, retries |
|---|---|---|---|---|
| stack | slip | 30/30 | 0/30 | 30/30 |
| stack | nudge | 30/30 | 0/30 | 27/30 |
| bins | slip | 30/30 | 0/30 | 30/30 |
| bins | nudge | 30/30 | 0/30 | 27/30 |
| flasks | slip | 30/30 | 0/30 | 30/30 |
| flasks | nudge | 30/30 | 0/30 | 30/30 |

Checks: stack|slip: PASS, stack|nudge: PASS, bins|slip: PASS, bins|nudge: PASS, flasks|slip: PASS, flasks|nudge: PASS
Crashed runs: 0
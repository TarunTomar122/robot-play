# Disturbance validation

50 episodes per row (layout seeds 3000+; the nudge was tuned on 2000-2029 and those results are kept in disturbance_tuning_seeds_2000.md), no-catch control scenes, played through the same Episode wrapper and call budget a model gets. 'No reaction' = the script that knows the catch but never retries.

| Job | Disturbance | Fired | Success, no reaction | Success, retries |
|---|---|---|---|---|
| stack | slip | 50/50 | 0/50 | 50/50 |
| stack | nudge | 50/50 | 0/50 | 47/50 |
| bins | slip | 50/50 | 0/50 | 50/50 |
| bins | nudge | 50/50 | 0/50 | 47/50 |
| flasks | slip | 50/50 | 0/50 | 50/50 |
| flasks | nudge | 50/50 | 0/50 | 0/50 |

The flask nudge row above is **not used** in the experiment: in the no-catch scene the flask is a plain 5 cm cylinder, the shove topples it and the retry script cannot stand it up again (0 of 50). The control flask scene therefore gets the slip on all four disturbed layouts.

Checks: stack|slip: PASS, stack|nudge: PASS, bins|slip: PASS, bins|nudge: PASS, flasks|slip: PASS
Crashed runs: 0
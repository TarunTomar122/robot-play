# Disturbance validation

30 episodes per row (seeds 2000+), catch scenes. 'No reaction' = the script that knows the catch but never retries.

| Job | Disturbance | Fired | Success, no reaction | Success, retries |
|---|---|---|---|---|
| stack | slip | 30/30 | 0/30 | 30/30 |
| stack | nudge | 30/30 | 0/30 | 27/30 |
| bins | slip | 30/30 | 0/30 | 30/30 |
| bins | nudge | 30/30 | 0/30 | 24/30 |
| flasks | slip | 30/30 | 0/30 | 30/30 |
| flasks | nudge | 30/30 | 0/30 | 30/30 |

Checks: stack|slip: PASS, stack|nudge: PASS, bins|slip: PASS, bins|nudge: PASS, flasks|slip: PASS, flasks|nudge: PASS
Crashed runs: 0
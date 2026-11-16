# Pose-level gate

100 layouts per row (seeds 0 to 99), played through `Episode` with the pose toolset and its 60-call budget.

| Job | Scene | Policy | Success | Mean calls |
|---|---|---|---|---|
| stack | catch | oracle | 100/100 | 24.0 |
| stack | catch | naive | 17/100 | 23.2 |
| stack | control | naive | 100/100 | 24.0 |
| bins | catch | oracle | 100/100 | 46.0 |
| bins | catch | naive | 0/100 | 41.0 |
| bins | control | naive | 96/100 | 45.9 |
| flasks | catch | oracle | 100/100 | 24.0 |
| flasks | catch | naive | 0/100 | 8.0 |
| flasks | control | naive | 100/100 | 24.0 |

Checks (oracle >= 95%, naive in the catch scene <= 30%, naive in the control scene >= 90%): stack: PASS, bins: PASS, flasks: PASS
Crashed runs: 0
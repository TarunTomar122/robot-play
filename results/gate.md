# Validation gates

100 seeds per cell (seeds 0..99); dose-response uses seeds 1000+.

| Task | Scene | Naive script | Oracle script |
|---|---|---|---|
| stack | quirk | 0/100 | 100/100 |
| stack | control | 100/100 | 100/100 |
| bins | quirk | 0/100 | 100/100 |
| bins | control | 100/100 | 100/100 |
| flasks | quirk | 0/100 | 100/100 |
| flasks | control | 100/100 | 100/100 |

Gates: stack: PASS, bins: PASS, flasks: PASS
Crashed runs: 0

## Dose-response (naive / oracle success)

**stack** (green cube mass (kg)): 0.05: 1.00 / 1.00; 0.1: 1.00 / 1.00; 0.15: 1.00 / 1.00; 0.2: 0.90 / 1.00; 0.25: 0.00 / 1.00; 0.3: 0.00 / 1.00

**bins** (bin wall height (m)): 0.015: 1.00 / 1.00; 0.04: 0.80 / 1.00; 0.07: 0.03 / 1.00; 0.1: 0.00 / 1.00; 0.12: 0.00 / 1.00; 0.15: 0.00 / 1.00

**flasks** (flask base height (m; 0 = plain cylinder)): 0: 1.00 / 1.00; 0.02: 1.00 / 1.00; 0.04: 1.00 / 1.00; 0.06: 0.00 / 1.00; 0.07: 0.00 / 1.00

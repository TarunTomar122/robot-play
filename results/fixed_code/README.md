# Validation gates rerun on the corrected code

The five validation checks of the registered setup, rerun on code hash `8fdcf6b2491b68a3` (tag `code-fixed`, commit 2267bf8; the code the replication runs on, and, for `env.py`, `motion.py` and `skills.py`, the code of the v1.7 controls) at 00:00 to 00:32 on 17 Nov 2026, with the same arguments as the registered run (100 seeds per cell, 50 episodes per disturbance row). **All five pass, with zero crashed runs.**

| check | file | result |
|---|---|---|
| oracle and naive scripts, dose response | `gate.md` | stack, sort, flasks: PASS (tables identical to the registered `results/gate.md`) |
| pose-level gate | `gate_pose.md` | stack, sort, flasks: PASS (one cell differs in mean calls, 22.1 against 23.2) |
| disturbances, catch scenes | `disturbance.md` | all six rows PASS (identical to the registered table) |
| disturbances, control scenes | `disturbance_control.md` | all rows PASS (identical to the registered table) |
| one-setting-at-a-time audit | `settings_audit.md` | identical to the registered audit |

A first rerun at 23:48 crashed in every cell because the new checkout had no Panda model files and three workers raced to download them; that run is not a result and its output was overwritten by this one.

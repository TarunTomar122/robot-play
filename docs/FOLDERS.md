# Folder map

- `robot_play/` the code: `world.py` (the physics scene), `motion.py` (inverse kinematics and planning), `skills.py` (the tools), `env.py` (the three jobs), `tools.py` (what the AI sees), `disturb.py`, `scripted.py` (the validation scripts), `llm.py` (Anthropic and OpenAI), `agent.py` (the loop and the memory), `runner.py` (resumable runs), `spend.py` (the spend cap), `analysis.py` (the statistics), `render.py` (videos).
- `scripts/` things you run: the gates (`gate.py`, `gate_pose.py`, `gate_disturbance.py`, `audit_settings.py`), `play.py`, `smoke.py`, `run_experiment.py`, `run_night.sh` (the whole overnight matrix, safe to run again), `analyze.py`, and the checks and charts (`coverage_sim.py`, `recompute_headlines.py`, `notebook_audit.py`, `stale_held_audit.py`, `make_headline_chart.py`, `make_q5_chart.py`, `make_llm_videos.py`), the run-file check (`check_run_files.py`), the firm-grip audit (`firm_grip_audit.py`), the zero-practice notebooks (`make_prior_notebooks.py`).
- `tests/` the automated tests.
- `docs/` plain-language explanations, hand-played transcripts and charts.
- `results/` the generated report (`RESULTS.md`), the audits, the gate tables, the deviations and the code-version table.
- `data/` the raw run files (one archive) and the recipe that regenerates `results/RESULTS.md` from them.
- `council/` the judges' rubric and their reviews.

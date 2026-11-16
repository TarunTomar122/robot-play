#!/bin/bash
# The whole overnight matrix (PROTOCOL.md section 5), in the order that learns the most the earliest. Safe to run again: finished runs are skipped
# and unfinished ones continue from their last finished episode. Do not edit robot_play/ while it runs (workers import the code once; a changed hash makes every
# unfinished run refuse to resume).
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
PY=.venv/bin/python
CHEAP="claude-haiku-5-5 gpt-6-luna"
FRONT="claude-fable-5-2 gpt-6-astra"

# pre-flight: tests green, matrix counts as promised, code hash recorded
$PY -m pytest -q > logs/preflight_tests.log 2>&1 || { echo "tests failed, see logs/preflight_tests.log"; exit 1; }
$PY -c "from robot_play.runner import code_hash; print(code_hash())" > logs/code_hash.txt
date >> logs/night_started.txt

# 1. main matrix (Haiku, Luna) with the frontier first-try runs alongside it, to learn the frontier's real cost early
$PY scripts/run_experiment.py --cell frontier --models $FRONT --workers 2 --out runs/frontier > logs/frontier.log 2>&1 &
$PY scripts/run_experiment.py --cell main --models $CHEAP --seeds 0-9 --workers 8 --out runs/main > logs/main.log 2>&1
wait

# 2. no-catch control (with its disturbed evaluation) and the frontier model with a notebook
$PY scripts/run_experiment.py --cell frontier_exp --models claude-fable-5-2 --seeds 0-4 --workers 5 --out runs/frontier_exp > logs/frontier_exp.log 2>&1 &
$PY scripts/run_experiment.py --cell control --models $CHEAP --seeds 0-4 --workers 5 --out runs/control > logs/control.log 2>&1
wait

# 3. pose-level ablation, only if its gate passed
if grep -q "FAIL" results/gate_pose.md 2>/dev/null || [ ! -f results/gate_pose.md ]; then
  echo "pose gate did not pass; pose cell skipped" > logs/pose.log
else
  $PY scripts/run_experiment.py --cell pose --models $CHEAP --seeds 0-2 --workers 10 --out runs/pose > logs/pose.log 2>&1
fi
echo NIGHT_DONE > logs/night_done.txt

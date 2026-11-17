#!/bin/bash
# The whole overnight matrix (PROTOCOL.md section 5), in the order that learns the most the earliest. Safe to run again: finished runs are skipped and unfinished
# ones continue from their last finished episode. Do not edit robot_play/ while it runs (workers import the code once; a changed hash makes every unfinished run
# refuse to resume). Each cell is retried up to four passes, because a run that ended 'aborted' (a provider outage) is not retried by the runner itself and
# incomplete runs are dropped from every confirmatory number.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
PY=.venv/bin/python
CHEAP="claude-haiku-5-5 gpt-6-luna"
FRONT="claude-fable-5-2 gpt-6-astra"

# keep the Mac awake for as long as this script runs: a sleeping machine charges every hung call its full reservation eight times
caffeinate -dimsu -w $$ > /dev/null 2>&1 &

# pre-flight: clean tree at a known revision, tests green, code hash recorded
if [ "$NIGHT_ALLOW_DIRTY" != "1" ] && [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "tracked files have uncommitted changes; commit them first (or NIGHT_ALLOW_DIRTY=1)"; exit 1
fi
git rev-parse HEAD > logs/night_rev.txt
$PY -m pytest -q > logs/preflight_tests.log 2>&1 || { echo "tests failed, see logs/preflight_tests.log"; exit 1; }
$PY -c "from robot_play.runner import code_hash; print(code_hash())" > logs/code_hash.txt
date >> logs/night_started.txt
rm -f logs/night_done.txt logs/night_incomplete.txt

run_cell() {        # run_cell <name> <run_experiment args...>; retries until every run is ok or four passes are used
  local name="$1"; shift
  local rc=1
  for pass in 1 2 3 4; do
    $PY scripts/run_experiment.py "$@" >> "logs/$name.log" 2>&1
    rc=$?
    echo "$(date +%H:%M) $name pass $pass exit $rc" >> logs/night_status.txt
    [ $rc -eq 0 ] && break
    sleep 60
  done
  return $rc
}

# 1. main matrix (Haiku, Luna) with the frontier first-try runs alongside it, to learn the frontier's real cost early
run_cell frontier --cell frontier --models $FRONT --workers 2 --out runs/frontier &
pf=$!
run_cell main --cell main --models $CHEAP --seeds 0-9 --workers 8 --out runs/main; r_main=$?
wait $pf; r_front=$?

# 2. no-catch control with its disturbed evaluation (10 run seeds) and the frontier model with a notebook
run_cell frontier_exp --cell frontier_exp --models claude-fable-5-2 --seeds 0-4 --workers 5 --out runs/frontier_exp &
pe=$!
run_cell control --cell control --models $CHEAP --seeds 0-9 --workers 6 --out runs/control; r_ctrl=$?
wait $pe; r_exp=$?

# 3. pose-level ablation, only if its gate passed
r_pose=0
rm -f logs/pose_skipped.txt
if grep -q "FAIL" results/gate_pose.md 2>/dev/null || [ ! -f results/gate_pose.md ]; then
  echo "pose gate did not pass; pose cell skipped" > logs/pose.log; touch logs/pose_skipped.txt; r_pose=4          # a skipped cell is not a finished night
else
  run_cell pose --cell pose --models $CHEAP --seeds 0-2 --workers 10 --out runs/pose; r_pose=$?
fi

echo "main=$r_main frontier=$r_front control=$r_ctrl frontier_exp=$r_exp pose=$r_pose" > logs/night_exit_codes.txt
if [ $r_main -eq 0 ] && [ $r_front -eq 0 ] && [ $r_ctrl -eq 0 ] && [ $r_exp -eq 0 ] && [ $r_pose -eq 0 ]; then
  echo NIGHT_DONE > logs/night_done.txt
else
  echo "NIGHT_INCOMPLETE (exit codes: $(cat logs/night_exit_codes.txt)); see logs/night_status.txt and the per-cell logs" > logs/night_incomplete.txt
fi

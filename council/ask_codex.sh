#!/bin/bash
# usage: council/ask_codex.sh <step-name> "<what to review: files, commands, what changed>"
cd "$(dirname "$0")/.." || exit 1
STEP="$1"; WHAT="$2"; mkdir -p council/reviews council/raw
codex exec -m gpt-6.1-terra -c model_reasoning_effort=high --skip-git-repo-check -s read-only \
  "You are judge 'codex' on the robot-play council. Read council/RUBRIC.md first and follow it exactly. \
Review step '$STEP'. What to review: $WHAT. Inspect the actual files in this repo (read-only); you may run \
read-only commands such as pytest or python scripts that do not call paid APIs. Do not edit anything." \
  > "council/raw/${STEP}-codex.txt" 2>&1
python3 - "$STEP" <<'PY'
import re,sys
s=open(f"council/raw/{sys.argv[1]}-codex.txt").read()
open(f"council/reviews/{sys.argv[1]}-codex.md","w").write(s[-9000:])
PY

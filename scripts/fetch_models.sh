#!/bin/bash
# Fetch the MuJoCo Menagerie robot models (Apache-2.0 / BSD) used by robot-play, pinned to the exact revision the results were produced with.
set -e
cd "$(dirname "$0")/.."
PIN=370c43965323c0944b433b202aac5058b5f907a9
mkdir -p third_party && cd third_party
if [ ! -d mujoco_menagerie/.git ]; then
  git init -q mujoco_menagerie
  git -C mujoco_menagerie remote add origin https://github.com/google-deepmind/mujoco_menagerie.git
fi
cd mujoco_menagerie
git sparse-checkout init --cone >/dev/null 2>&1 || true
git sparse-checkout set franka_emika_panda robotstudio_so101
git fetch -q --depth 1 --filter=blob:none origin $PIN
git checkout -q FETCH_HEAD
test "$(git rev-parse HEAD)" = "$PIN" && echo "models ready, Menagerie pinned at $PIN"

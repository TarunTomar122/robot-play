#!/bin/bash
# Fetch the MuJoCo Menagerie robot models (Apache-2.0 / BSD) used by robot-play.
set -e
cd "$(dirname "$0")/.."
mkdir -p third_party && cd third_party
[ -d mujoco_menagerie ] || git clone -q --depth 1 --filter=blob:none --sparse https://github.com/google-deepmind/mujoco_menagerie.git
cd mujoco_menagerie && git sparse-checkout set franka_emika_panda robotstudio_so101
echo "models ready in third_party/mujoco_menagerie"

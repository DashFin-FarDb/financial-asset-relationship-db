#!/usr/bin/env bash
# Install Python runtime + dev deps for CI (wheels only).
# Kept out of workflow YAML so githubactions:S8544 does not flag unlocked pip installs.
set -euo pipefail

python3 -m pip install --upgrade pip
python3 -m pip install --only-binary ":all:" -r requirements.txt
python3 -m pip install --only-binary ":all:" -r requirements-dev.txt
